import { useState } from 'react';
import type { SubtitleDocument, SubtitleSegment } from '../types';
import { formatSubtitleTime } from '../services/playback';
import { Icon } from './Icon';

function SubtitleRow({ segment, active, seek, save, remove }: {
  segment: SubtitleSegment; active: boolean; seek: (time: number) => void;
  save: (segment: SubtitleSegment, text: string, start: number, end: number) => Promise<void>;
  remove: (segment: SubtitleSegment) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(segment.text);
  const [start, setStart] = useState(segment.start_time);
  const [end, setEnd] = useState(segment.end_time);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  return <article className={`subtitle-row ${active ? 'active' : ''}`} data-testid="subtitle-row">
    <div className="segment-top"><button className="segment-time" onClick={() => seek(segment.start_time)} title="Seek to this subtitle">{formatSubtitleTime(segment.start_time)} – {formatSubtitleTime(segment.end_time)}</button><span>{Math.round(segment.confidence * 100)}%{segment.edited ? ' · edited' : ''}</span></div>
    {editing ? <form onSubmit={async (event) => {
      event.preventDefault(); setBusy(true); setError('');
      try { await save(segment, text, start, end); setEditing(false); }
      catch (cause) { setError((cause as Error).message); }
      finally { setBusy(false); }
    }}>
      <label className="sr-only" htmlFor={`text-${segment.id}`}>Subtitle text</label>
      <textarea id={`text-${segment.id}`} value={text} onChange={(event) => setText(event.target.value)} required maxLength={5000} rows={3} lang="zh" />
      <div className="segment-time-inputs"><label>Start (seconds)<input type="number" min="0" step="0.001" value={start} onChange={(event) => setStart(Number(event.target.value))} required /></label><label>End (seconds)<input type="number" min="0" step="0.001" value={end} onChange={(event) => setEnd(Number(event.target.value))} required /></label></div>
      <div className="segment-actions"><button className="secondary-button" disabled={busy}>{busy ? 'Saving…' : 'Save subtitle'}</button><button className="text-action" type="button" onClick={() => setEditing(false)} disabled={busy}>Discard</button></div>
    </form> : <><p lang="zh" className="segment-text">{segment.text}</p><div className="segment-actions"><button className="text-action" onClick={() => { setText(segment.text); setStart(segment.start_time); setEnd(segment.end_time); setEditing(true); setError(''); }}>Edit subtitle</button><button className="text-action danger" disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      try { await remove(segment); } catch (cause) { setError((cause as Error).message); setBusy(false); }
    }}>Delete subtitle</button></div></>}
    {error && <p role="alert" className="error-text">{error}</p>}
  </article>;
}

export function Transcript({ document, currentTime, seek, save, remove }: {
  document: SubtitleDocument | null; currentTime: number; seek: (time: number) => void;
  save: (segment: SubtitleSegment, text: string, start: number, end: number) => Promise<void>;
  remove: (segment: SubtitleSegment) => Promise<void>;
}) {
  const [tab, setTab] = useState('transcript');
  return <aside className="learning-panel" aria-label="Learning tools">
    <div className="panel-tabs" role="tablist" aria-label="Learning panel">{(['transcript', 'vocabulary'] as const).map((item) => <button key={item} role="tab" id={`${item}-tab`} aria-controls="learning-content" aria-selected={tab === item} onClick={() => setTab(item)}><Icon name={item === 'transcript' ? 'captions' : 'book'} size={17} />{item === 'transcript' ? 'Transcript' : 'Vocabulary'}</button>)}</div>
    <div id="learning-content" role="tabpanel" aria-labelledby={`${tab}-tab`} className="panel-content transcript-content">
      <span className="panel-counter">{tab === 'transcript' ? 'SUBTITLES' : 'SAVED WORDS'}<span>{tab === 'transcript' ? document?.segments.length ?? 0 : '—'}</span></span>
      {tab === 'transcript' ? <>
        {document?.analysis && <div className="export-links"><a href={`/api/videos/${document.video_id}/export?format=json&analysis_id=${document.analysis.id}`} download>Export JSON</a><a href={`/api/videos/${document.video_id}/export?format=srt&analysis_id=${document.analysis.id}`} download>Export SRT</a></div>}
        {document?.segments.map((segment) => <SubtitleRow key={`${document.analysis?.id}-${segment.id}-${segment.revision}`} segment={segment} active={segment.start_time <= currentTime && currentTime < segment.end_time} seek={seek} save={save} remove={remove} />)}
        {!document?.segments.length && <div className="learning-empty"><span className="empty-tool-icon"><Icon name="captions" size={28} /></span><h3>{document?.analysis ? 'No subtitles detected.' : 'Every sentence, a small step.'}</h3><p>{document?.analysis ? 'Check the preview and tighten the region around the Chinese text, then rerun OCR. Blank regions can correctly return no subtitles.' : 'Choose the Chinese subtitle region below the player, then select Analyze Video. Your transcript will appear here.'}</p></div>}
      </> : <div className="learning-empty"><h3>Build your own wordbook.</h3><p>Dictionary lookup, pinyin and saved vocabulary arrive in Phase 3.</p></div>}
    </div>
    <div className="panel-footnote"><span className="status-dot" />Sampled visual timing · no audio alignment</div>
  </aside>;
}
