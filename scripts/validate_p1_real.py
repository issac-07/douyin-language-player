"""Verify live stages on an isolated eight-second clip of authorized library media."""
import json
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

def main():
    folder=ROOT/'data/validation'/f'v47-real-{uuid4().hex}'
    folder.mkdir(parents=True)
    source=ROOT/'data/media/3c7e8121-18c8-4987-b848-b8cd2bd3dd3f.mp4'
    clip=folder/'source-prefix.mp4'
    subprocess.run(['ffmpeg','-v','error','-i',str(source),'-t','8','-c','copy',str(clip)],check=True)
    settings=Settings(data_dir=folder)
    snapshots=[]
    with TestClient(create_app(settings)) as client:
        with clip.open('rb') as f:
            imported=client.post('/api/videos',files={'file':('real-prefix.mp4',f,'video/mp4')})
        imported.raise_for_status()
        video=imported.json()['video']
        base=f"/api/videos/{video['id']}"
        response=client.post(base+'/analyses',json={'settings':{'sample_fps':2,'roi':{'x':0,'y':.89,'width':1,'height':.11},'performance':{'backend':'intel-gpu','mode':'accurate','gpu_requests':4,'refine_timing':True}}})
        response.raise_for_status()
        job=response.json()['job']
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            job=client.get(f"/api/analysis-jobs/{job['id']}").json()
            snapshots.append({'stage':job['stage'],'status':job['status'],'progress':job['progress'],'elapsed':job['metrics']['total_seconds'],'updated_at':job['updated_at'],'done':job['stage_completed'],'total':job['stage_total']})
            if job['status'] not in ('pending','processing'):break
            time.sleep(.5)
        assert job['status']=='completed',job
        assert job['stage']=='completed' and job['progress']==1
        document=client.get(base+'/subtitles').json()
        report={'source':str(source),'prefix_duration':video['duration'],'job':job,'snapshots':snapshots,'segments':document['segments']}
        path=ROOT/'data/validation/v47-real-job.json'
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'stages':list(dict.fromkeys(s['stage'] for s in snapshots)),'metrics':job['metrics'],'segments':len(document['segments'])}))

if __name__=='__main__':main()
