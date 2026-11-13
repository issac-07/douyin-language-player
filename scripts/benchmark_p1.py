"""Read-only real-media comparison. Writes only the named JSON report."""
import argparse
import gc
import json
import sqlite3
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import cv2
import numpy as np
from app.models.schemas import ProcessingSettings
from app.services.ocr_engine import RapidOCREngine
from app.services.ocr_scheduling import prefetch, OCRLanes
from app.services.ocr_reuse import SubtitleReuse
from app.services.subtitle_detection import SubtitleDetector
from app.services.video_frames import SequentialFrameSource, OpenCVFrameSource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=8)
    parser.add_argument('--repetitions', type=int, default=2)
    parser.add_argument('--output', type=Path, default=ROOT/'data/validation/v47-benchmark.json')
    args = parser.parse_args()
    db = sqlite3.connect(f'{(ROOT / "data/library.sqlite3").as_uri()}?mode=ro', uri=True)
    videos = [json.loads(row[0]) for row in db.execute('SELECT payload FROM videos')]
    sources = []
    for width in (1920,1280):
        video = next((v for v in videos if v['width'] == width), None)
        if not video: continue
        row = db.execute('SELECT payload FROM processing_settings WHERE video_id=?',(video['id'],)).fetchone()
        settings = ProcessingSettings.model_validate_json(row[0]) if row else ProcessingSettings()
        settings.sample_fps = 5
        sources.append((video,settings))
    db.close()
    configs = [('original_cpu','ort',2,1,False,False),('balanced_cpu','ort',4,1,True,False),('fast_cpu','ort',4,1,True,True)]
    try:
        import openvino
        if any(d.startswith('GPU') for d in openvino.Core().available_devices):
            configs += [(f'gpu_{n}','openvino-gpu',4,n,True,False) for n in (1,2,4)]
    except ImportError:
        pass
    output = {'duration_per_source':args.seconds, 'sample_fps':5, 'runs':[], 'limits':'Prefixes only. No human OCR ground truth, utilization or peak device-memory measurement. Inference sum overlaps decode/lane work; do not add durations.'}
    for name,backend,threads,lanes,sequential,fast in configs:
        tick=time.perf_counter()
        engines=[RapidOCREngine(threads=threads,backend=backend) for _ in range(lanes)]
        initialization=time.perf_counter()-tick
        for video,settings in sources:
            row={'config':name,'video_id':video['id'],'source_sha256':video['sha256'],'dimensions':[video['width'],video['height']], 'roi':settings.roi.model_dump(),'initialization_seconds':initialization,'runs':[]}
            for repetition in range(args.repetitions+1):
                started=time.perf_counter()
                decode=[0.0]
                def decoded(seconds):decode[0]+=seconds
                source=(SequentialFrameSource(args.seconds) if sequential else OpenCVFrameSource(args.seconds))
                samples=source.samples(str(ROOT/'data/media'/f"{video['id']}.mp4"),settings)
                if sequential:samples=prefetch(samples,lambda:False,on_decode=decoded)
                if lanes>1:samples=OCRLanes(engines).observations(samples,lambda:False)
                detector=SubtitleDetector(5,args.seconds)
                reuse=SubtitleReuse() if fast else None
                previous_image=previous_observation=None
                calls=skips=frames=0
                inference=0.0
                texts=[]
                try:
                    while True:
                        tick=time.perf_counter()
                        try:item=next(samples)
                        except StopIteration:break
                        if not sequential:decode[0]+=time.perf_counter()-tick
                        sample,computed=item if lanes>1 else (item,None)
                        gray=cv2.cvtColor(sample.image,cv2.COLOR_BGR2GRAY)
                        identical=previous_image is not None and np.array_equal(gray,previous_image)
                        if computed is not None:observation=computed
                        elif identical or (reuse and reuse.can_reuse(sample.image,sample.timestamp)):
                            observation=replace(previous_observation,timestamp=sample.timestamp,calls=0,inference_seconds=0);skips+=1
                        else:
                            observation=engines[0].recognize(sample)
                            if reuse:reuse.remember(sample.image,observation)
                        previous_image,previous_observation=gray,observation
                        frames+=1;calls+=observation.calls;inference+=observation.inference_seconds
                        texts.append(observation.text);detector.observe(observation)
                finally:samples.close()
                segments=detector.finish()
                row['runs'].append({'first_for_source':repetition==0,'seconds':time.perf_counter()-started,'decode_seconds':decode[0],'inference_work_seconds':inference,'frames':frames,'calls':calls,'skipped':skips,'texts':texts,'segments':[(s.text,s.start_time,s.end_time) for s in segments]})
            row['warm_median_seconds']=statistics.median(r['seconds'] for r in row['runs'][1:])
            output['runs'].append(row)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
            print(name,video['width'],round(row['warm_median_seconds'],3), 'calls',row['runs'][-1]['calls'],'skips',row['runs'][-1]['skipped'],flush=True)
        del engines
        gc.collect()

if __name__=='__main__':main()
