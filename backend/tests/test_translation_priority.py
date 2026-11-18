import threading
import time
from types import SimpleNamespace
from uuid import uuid4
from app.models.learning import Translation


def test_reprioritize_existing_queue_latest_click_and_keep_display_order(client,monkeypatch):
    service=client.app.state.learning
    translator=service.translator
    translator.available=True
    started,release,focused,next_release=threading.Event(),threading.Event(),threading.Event(),threading.Event()
    calls=[]
    segments=[SimpleNamespace(id=uuid4(),revision=0,text=f'句子{i}',start_time=i*10) for i in range(12)]
    doc=SimpleNamespace(video_id=uuid4(),analysis=None,segments=segments)
    def translate(text):
        calls.append(text)
        if text=='句子0':
            started.set();assert release.wait(10)
        if text=='句子6':
            focused.set();assert next_release.wait(10)
        return Translation(status='completed',text='translation:'+text,model=translator.identity)
    monkeypatch.setattr(translator,'translate',translate)
    try:
        service.document(doc)
        assert started.wait(5)
        result=service.document(doc,focus=60)
        assert [s.id for s in result.segments]==[s.id for s in segments]
        release.set();assert focused.wait(5)
        service.document(doc,focus=90)
        next_release.set()
        deadline=time.monotonic()+5
        while service.scheduled and time.monotonic()<deadline:time.sleep(.01)
        assert calls[:3]==['句子0','句子6','句子9']
        assert len(calls)==len(set(calls))==12
        for item in service.document(doc).segments:
            assert item.translation.text=='translation:'+item.text
    finally:
        release.set();next_release.set()


def test_focus_beyond_queue_capacity_is_not_blocked_by_earlier_sentences(client,monkeypatch):
    service=client.app.state.learning
    translator=service.translator;translator.available=True
    entered,release=threading.Event(),threading.Event()
    calls=[]
    def translate(text):
        calls.append(text)
        if text=='句子0':entered.set();assert release.wait(15)
        return Translation(status='completed',text=text,model=translator.identity)
    monkeypatch.setattr(translator,'translate',translate)
    segments=[SimpleNamespace(id=uuid4(),revision=0,text=f'句子{i}',start_time=i*10) for i in range(600)]
    doc=SimpleNamespace(video_id=uuid4(),analysis=None,segments=segments)
    try:
        service.document(doc);assert entered.wait(5)
        service.document(doc,focus=5990)
        release.set()
        deadline=time.monotonic()+5
        while len(calls)<2 and time.monotonic()<deadline:time.sleep(.01)
        assert calls[:2]==['句子0','句子599']
        service.release_memory()
    finally:release.set()
