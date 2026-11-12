"""Fresh OCR benchmarks in isolated SQLite libraries; never opens the user's database.

Reference modules are frozen from commit 31da9f3, not from a changing working tree.
Timings are nested (inference is part of stage/recognize time), not additive.
"""
import argparse
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import cv2
import numpy as np
from app.models.schemas import AnalysisJob, JobStatus, ProcessingSettings, ROI, Video
from app.services.repository import Repository


def load_reference(folder, name):
    path = folder / f'{name}.py'
    source = subprocess.check_output(['git', 'show', f'31da9f3:backend/app/services/{name}.py'], cwd=ROOT)
    path.write_bytes(source)
    spec = importlib.util.spec_from_file_location(f'original_{name}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Timed:
    def __init__(self, target, metrics, key):
        self.target, self.metrics, self.key = target, metrics, key

    def __getattr__(self, key):
        return getattr(self.target, key)

    def __call__(self, *args, **kwargs):
        started = perf_counter()
        try:
            return self.target(*args, **kwargs)
        finally:
            self.metrics[self.key] += perf_counter() - started
            self.metrics[self.key + '_calls'] += 1


def instrument(engine, metrics):
    raw = engine.engine
    preprocess = raw.text_det.get_preprocess
    raw.text_det.get_preprocess = lambda *args: Timed(preprocess(*args), metrics, 'preprocessing')
    raw.text_rec.resize_norm_img = Timed(raw.text_rec.resize_norm_img, metrics, 'preprocessing')
    raw.text_det.postprocess_op = Timed(raw.text_det.postprocess_op, metrics, 'ocr_postprocessing')
    raw.text_rec.postprocess_op = Timed(raw.text_rec.postprocess_op, metrics, 'ocr_postprocessing')
    raw.text_det.infer = Timed(raw.text_det.infer, metrics, 'detection_inference')
    raw.text_rec.session = Timed(raw.text_rec.session, metrics, 'recognition_inference')
    raw.text_det = Timed(raw.text_det, metrics, 'detection_stage')
    raw.text_rec = Timed(raw.text_rec, metrics, 'recognition_stage')
    class PassTimer(Timed):
        count = 0

        def __call__(self, *args, **kwargs):
            key = 'primary_pass' if self.count == 0 else 'fallback_pass'
            self.count += 1
            started = perf_counter()
            try:
                return self.target(*args, **kwargs)
            finally:
                self.metrics[key] += perf_counter() - started
    engine.engine = PassTimer(raw, metrics, 'rapidocr')
    return engine


def memory():
    if os.name != 'nt':
        return None
    class Counters(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t)]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
        return counters.PeakWorkingSetSize / 1024**2


def system_info():
    versions = {}
    for name in ['rapidocr', 'rapidocr-onnxruntime', 'rapidocr-openvino', 'onnxruntime', 'numpy', 'opencv-python', 'openvino']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    result = dict(platform=platform.platform(), python=sys.version, logical_cpus=os.cpu_count(), packages=versions,
                  opencv_threads=cv2.getNumThreads(), power_scheme=subprocess.getoutput('powercfg /getactivescheme'))
    import rapidocr_onnxruntime
    result['models'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(rapidocr_onnxruntime.__file__).parent / 'models').glob('*.onnx')}
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                result['cpu'] = winreg.QueryValueEx(key, 'ProcessorNameString')[0]
        except OSError:
            pass
        class Power(ctypes.Structure):
            _fields_ = [('ACLineStatus', ctypes.c_byte), ('BatteryFlag', ctypes.c_byte),
                        ('BatteryLifePercent', ctypes.c_byte), ('SystemStatusFlag', ctypes.c_byte),
                        ('BatteryLifeTime', ctypes.c_ulong), ('BatteryFullLifeTime', ctypes.c_ulong)]
        power = Power()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
            result['power'] = dict(ac_line_status=power.ACLineStatus, battery_percent=power.BatteryLifePercent)
    return result


def compare(reference, current):
    import difflib
    left, right = reference['segments'], current['segments']
    a, b = '\n'.join(s['text'] for s in left), '\n'.join(s['text'] for s in right)
    changed = [i for i, (x, y) in enumerate(zip(reference['observations'], current['observations'])) if x['text'] != y['text']]
    false_reuse = [i for i in changed if current['observations'][i]['reused']]
    timing = max((max(abs(x['start_time'] - y['start_time']), abs(x['end_time'] - y['end_time']))
                  for x, y in zip(left, right)), default=0)
    return dict(reference_segments=len(left), candidate_segments=len(right),
                exact_text_and_times=left == right, changed_observation_indices=changed,
                false_reuse_indices=false_reuse, character_similarity=difflib.SequenceMatcher(None, a, b).ratio(),
                max_paired_timestamp_difference=timing,
                segment_diff=list(difflib.unified_diff(json.dumps(left, ensure_ascii=False, indent=2).splitlines(),
                                                       json.dumps(right, ensure_ascii=False, indent=2).splitlines())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path)
    parser.add_argument('--roi', default='.05,.60,.90,.30')
    parser.add_argument('--fps', type=float, default=2)
    parser.add_argument('--seconds', type=float, help='Benchmark only this prefix; never relabel it as the full video')
    parser.add_argument('--runs', type=int, default=3, help='Warm repetitions after a cold full run')
    parser.add_argument('--engine', choices=['reference', 'ort', 'openvino-cpu', 'openvino-gpu'], default='reference')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--opencv-threads', type=int)
    parser.add_argument('--decoder', choices=['seek', 'sequential'], default='seek')
    parser.add_argument('--reuse', choices=['accurate', 'balanced', 'fast'], default='accurate')
    parser.add_argument('--decode-only', action='store_true')
    parser.add_argument('--write-policy', choices=['baseline', 'throttled'], default='baseline')
    parser.add_argument('--reference', type=Path, help='JSON reference to compare exact text and timestamps')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    destination = args.output.parent / f'isolated-{uuid4().hex}'
    destination.mkdir()
    original = load_reference(destination, 'ocr_engine')
    frames = load_reference(destination, 'video_frames')
    detector_module = load_reference(destination, 'subtitle_detection')
    if args.opencv_threads is not None:
        cv2.setNumThreads(args.opencv_threads)
    metadata = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_format', '-of', 'json', str(args.video)]))
    stream = metadata['streams'][0]
    source_duration = float(metadata['format']['duration'])
    duration = min(source_duration, args.seconds) if args.seconds else source_duration
    settings = ProcessingSettings(roi=ROI(**dict(zip(('x', 'y', 'width', 'height'), map(float, args.roi.split(',')), strict=True))), sample_fps=args.fps)
    report = dict(system=system_info(), configuration=vars(args) | {'video': str(args.video.resolve()), 'output': str(args.output), 'reference': str(args.reference) if args.reference else None},
                  source=dict(sha256=hashlib.file_digest(args.video.open('rb'), 'sha256').hexdigest(), duration=source_duration, analyzed_seconds=duration,
                              width=stream['width'], height=stream['height'], roi=settings.roi.model_dump(), sample_fps=args.fps),
                  original_source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in destination.glob('*.py')}, runs=[])
    started = perf_counter()
    if args.decode_only:
        engine = None
    elif args.engine == 'reference':
        engine = original.RapidOCREngine()
    else:
        from app.services.ocr_engine import RapidOCREngine
        engine = RapidOCREngine(threads=args.threads, backend=args.engine)
    init_seconds = perf_counter() - started
    metrics = defaultdict(float)
    if engine:
        instrument(engine, metrics)
        report['engine_identity'] = engine.version
        report['execution'] = getattr(engine, 'execution', {'detection': 'CPUExecutionProvider', 'recognition': 'CPUExecutionProvider', 'classification': 'disabled'})
    if args.decoder == 'sequential':
        from app.services.video_frames import SequentialFrameSource
        source_class = SequentialFrameSource
    else:
        source_class = frames.OpenCVFrameSource
    reference = json.loads(args.reference.read_text(encoding='utf-8'))['runs'][0] if args.reference else None
    for repetition in range(args.runs + 1):
        metrics.clear()
        repo = Repository(destination / f'run-{repetition}.sqlite3')
        repo.initialize()
        video = Video(id=uuid4(), original_name=args.video.name, sha256=report['source']['sha256'], size_bytes=args.video.stat().st_size,
                      duration=duration, width=stream['width'], height=stream['height'], fps=eval_fraction(stream['avg_frame_rate']),
                      video_codec=stream['codec_name'], audio_codec=None, created_at=datetime.now(timezone.utc), media_url='')
        repo.add(video)
        job = AnalysisJob(id=uuid4(), video_id=video.id, cache_key=uuid4().hex, engine_version=engine.version if engine else 'decode-only',
                          settings=settings, created_at=datetime.now(timezone.utc), total_frames=int(np.ceil(duration*args.fps)), timestamp_uncertainty=1/args.fps)
        repo.save_job(job)
        detector = detector_module.SubtitleDetector(args.fps, duration)
        started = perf_counter()
        cpu_started = time.process_time()
        last_saved = started
        samples = iter(source_class(duration).samples(str(args.video), settings))
        previous_image, previous_observation = None, None
        observations = []
        reuser = None
        if args.reuse != 'accurate':
            from app.services.ocr_reuse import SubtitleReuse
            reuser = SubtitleReuse(args.reuse)
        try:
            while True:
                tick = perf_counter()
                try:
                    sample = next(samples)
                except StopIteration:
                    metrics['decode'] += perf_counter() - tick
                    break
                metrics['decode'] += perf_counter() - tick
                tick = perf_counter()
                fingerprint = cv2.cvtColor(sample.image, cv2.COLOR_BGR2GRAY)
                reused = previous_image is not None and fingerprint.shape == previous_image.shape and np.array_equal(fingerprint, previous_image)
                if reuser and not reused:
                    reused = reuser.can_reuse(sample.image, sample.timestamp)
                metrics['change_detection'] += perf_counter() - tick
                if args.decode_only:
                    observations.append(dict(timestamp=sample.timestamp, hash=hashlib.sha256(sample.image.tobytes()).hexdigest()))
                    continue
                if reused:
                    observation = replace(previous_observation, timestamp=sample.timestamp, inference_seconds=0, calls=0)
                else:
                    tick = perf_counter()
                    engine.engine.count = 0
                    observation = engine.recognize(sample)
                    metrics['recognize'] += perf_counter() - tick
                    if reuser:
                        reuser.remember(sample.image, observation)
                previous_image, previous_observation = fingerprint, observation
                tick = perf_counter()
                detector.observe(observation)
                metrics['merging'] += perf_counter() - tick
                observations.append(dict(timestamp=sample.timestamp, text=observation.text, confidence=observation.confidence,
                                         calls=observation.calls, reused=bool(reused)))
                job.metrics.frames_processed += 1
                job.metrics.ocr_calls += observation.calls
                job.metrics.reused_frames += int(reused)
                tick = perf_counter()
                if args.write_policy == 'baseline' or perf_counter() - last_saved >= .75:
                    repo.save_job(job)
                    last_saved = perf_counter()
                metrics['database'] += perf_counter() - tick
        finally:
            samples.close()
        tick = perf_counter()
        segments = detector.finish()
        metrics['merging'] += perf_counter() - tick
        tick = perf_counter()
        job.status = JobStatus.COMPLETED
        repo.complete(job, segments)
        metrics['database'] += perf_counter() - tick
        elapsed = perf_counter() - started
        result = dict(kind='cold' if repetition == 0 else 'warm', repetition=repetition,
                      initialization_seconds=init_seconds if repetition == 0 else 0, processing_seconds=elapsed,
                      end_to_end_seconds=elapsed + (init_seconds if repetition == 0 else 0), timings=dict(metrics),
                      frames=len(observations), ocr_calls=job.metrics.ocr_calls, reused_frames=job.metrics.reused_frames,
                      process_lifetime_peak_memory_mib=memory(), observations=observations,
                      process_cpu_seconds=time.process_time() - cpu_started,
                      segments=[{k: s.model_dump()[k] for k in ('start_time', 'end_time', 'text')} for s in segments])
        if reference and not args.decode_only:
            result['quality'] = compare(reference, result)
        if args.decode_only and reference:
            result['identical_samples'] = result['observations'] == reference['observations']
        report['runs'].append(result)
        report['warm_median_seconds'] = statistics.median(r['processing_seconds'] for r in report['runs'][1:]) if repetition else None
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k not in ('observations', 'segments', 'quality')}, ensure_ascii=True), flush=True)


def eval_fraction(text):
    numerator, denominator = text.split('/')
    return float(numerator) / max(1, float(denominator))


if __name__ == '__main__':
    main()
