import threading
import time
import pytest
import numpy as np
from app.services.ocr_scheduling import prefetch, OCRLanes
from app.services.pipeline import FrameSample, OCRObservation
from app.services.boundary_refinement import refine_starts
from app.models.schemas import ProcessingSettings, AnalysisMetrics, SubtitleSegment
from uuid import uuid4


def test_ordered_lanes_overlap_and_cancel():
    entered=threading.Barrier(2)
    class Engine:
        def recognize(self,sample):
            entered.wait(timeout=5)
            if sample.timestamp==0: time.sleep(.03)
            return OCRObservation(sample.timestamp,str(sample.timestamp),.99)
    samples=(FrameSample(i,np.zeros((1,1,3),np.uint8)) for i in range(4))
    result=list(OCRLanes([Engine(),Engine()]).observations(samples,lambda:False))
    assert [s.timestamp for s,_ in result]==[0,1,2,3]
    assert [o.timestamp for _,o in result]==[0,1,2,3]


def test_prefetch_closes_decoder_and_propagates_errors():
    closed=threading.Event()
    def source():
        try:
            yield FrameSample(0,None)
            raise RuntimeError('decode failure')
        finally: closed.set()
    with pytest.raises(RuntimeError,match='decode failure'):
        list(prefetch(source(),lambda:False))
    assert closed.is_set()
    stream=prefetch((FrameSample(i,None) for i in range(20)),lambda:False)
    assert next(stream).timestamp==0
    stream.close()


def test_real_two_frame_refinement_preserves_known_boundaries(video_path):
    from app.services.ocr_engine import RapidOCREngine
    segment=SubtitleSegment(id=uuid4(),start_time=.7,end_time=2.5,text='今天我们一起去吃饭',confidence=.99)
    metrics=AnalysisMetrics()
    refine_starts(video_path,[segment],ProcessingSettings(sample_fps=5),RapidOCREngine(threads=4),lambda:False,metrics)
    assert segment.start_time==pytest.approx(.5,abs=1/24)
    assert segment.metadata['coarse_start_time']==.7
    assert metrics.refinement_frames>=2
    assert metrics.ocr_calls>=2


def test_runtime_new_flags_do_not_change_legacy_serialization():
    from app.models.schemas import OCRPerformance
    from app.services.ocr_runtime import resolve_runtime
    assert 'gpu_requests' not in OCRPerformance().model_dump()
    assert 'refine_timing' not in OCRPerformance().model_dump()
    settings=ProcessingSettings(performance=OCRPerformance(backend='intel-gpu',gpu_requests=2,refine_timing=True))
    plan=resolve_runtime(settings)
    assert plan.requests==2 and plan.refine
    assert 'ordered-lanes=2' in plan.identity and 'two-frame-boundary' in plan.identity


def test_reuse_tolerates_compression_but_rejects_changed_stroke():
    from backend.tests.test_ocr_performance import caption, observation
    from app.services.ocr_reuse import SubtitleReuse
    image=caption()
    reuse=SubtitleReuse()
    reuse.remember(image,observation())
    compressed=np.clip(image.astype(np.int16)-3,0,255).astype(np.uint8)
    assert reuse.can_reuse(compressed,.2)
    assert not reuse.can_reuse(caption('我不喜欢你'),.2)
    assert not reuse.can_reuse(caption('我喜欢他'),.2)
    assert not reuse.can_reuse(caption('我喜欢你\n今天吃饭'),.2)


def test_real_gpu_parallel_job(client, imported):
    ov=pytest.importorskip('openvino')
    if 'GPU' not in ov.Core().available_devices:
        pytest.skip('Intel GPU is unavailable')
    from backend.tests.test_analysis_api import wait_for_job
    settings=ProcessingSettings(sample_fps=5).model_dump()
    settings['performance']={'backend':'intel-gpu','mode':'balanced','gpu_requests':2}
    base=f"/api/videos/{imported['id']}"
    serial_settings={**settings,'performance':{**settings['performance'],'gpu_requests':1}}
    serial=client.post(base+'/analyses',json={'settings':serial_settings}).json()['job']
    assert wait_for_job(client,serial['id'],timeout=120)['status']=='completed'
    reference=client.get(base+'/subtitles').json()['segments']
    result=client.post(base+'/analyses',json={'settings':settings})
    assert result.status_code==202,result.text
    job=wait_for_job(client,result.json()['job']['id'],timeout=120)
    assert job['status']=='completed',job
    assert job['execution']['ocr_lanes']==2
    assert job['execution']['stages']['detection'].startswith('GPU')
    assert job['execution']['fallback'] is False
    assert job['metrics']['frames_processed']==40
    actual=client.get(base+'/subtitles').json()['segments']
    assert [(s['text'],s['start_time'],s['end_time']) for s in actual]==[(s['text'],s['start_time'],s['end_time']) for s in reference]
    for expected in ['今天我们一起去吃饭','你在干什么','我不知道发生了什么']:
        assert any(expected in s['text'] for s in actual)
