"""Compare ordered GPU lanes, same media/ROI/5 FPS. No application DB writes."""
import json,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.models.schemas import ProcessingSettings,ROI
from app.services.ocr_engine import RapidOCREngine
from app.services.video_frames import SequentialFrameSource
from app.services.ocr_scheduling import OCRLanes,prefetch
from app.services.subtitle_detection import SubtitleDetector

if __name__=='__main__':
    source=Path('D:/Projects/douyin-language-player/data/media/3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4')
    settings=ProcessingSettings(sample_fps=5,roi=ROI(x=.1,y=.87,width=.8,height=.12))
    output=ROOT/'data/ocr-lanes.json'
    results=[]
    baseline=None
    for lanes in [1,2,4]:
        tick=time.perf_counter()
        engines=[RapidOCREngine(backend='openvino-gpu',threads=4) for _ in range(lanes)]
        initialization=time.perf_counter()-tick
        row={'lanes':lanes,'initialization':initialization,'runs':[],'execution':[engine.execution for engine in engines]}
        for repetition in range(4):
            tick=time.perf_counter()
            detector=SubtitleDetector(5,8)
            samples=prefetch(SequentialFrameSource(8).samples(str(source),settings),lambda:False)
            observations=[]
            for sample,observation in OCRLanes(engines).observations(samples,lambda:False):
                detector.observe(observation)
                observations.append({'time':sample.timestamp,'text':observation.text,'calls':observation.calls})
            segments=[{'text':s.text,'start':s.start_time,'end':s.end_time} for s in detector.finish()]
            elapsed=time.perf_counter()-tick
            if baseline is None: baseline=(observations,segments)
            run={'kind':'cold' if repetition==0 else 'warm','seconds':elapsed,'frames':len(observations),
                 'calls':sum(o['calls'] for o in observations),'exact':baseline==(observations,segments),
                 'observations':observations,'segments':segments}
            row['runs'].append(run)
            print(json.dumps({k:v for k,v in run.items() if k not in ('observations','segments')}|{'lanes':lanes}),flush=True)
        row['median']=statistics.median(run['seconds'] for run in row['runs'][1:])
        results.append(row)
        output.write_text(json.dumps({'source':str(source),'seconds':8,'settings':settings.model_dump(),'results':results},ensure_ascii=False,indent=2),encoding='utf8')
        del engines
