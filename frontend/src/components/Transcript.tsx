import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { DictionaryResult, LearningDocument, LearningSegment, SavedWord, SubtitleDocument, SubtitleSegment, WordToken } from '../types';
import { transcriptSubtitle } from '../services/playback';
import { WordSummary } from './WordSummary';

function SubtitleRow({ segment, active, seek, save, remove, language, onWord, saveTranslation }: {
  segment: SubtitleSegment; active: boolean; seek: (time: number) => void;
  save: (segment: SubtitleSegment, text: string, start: number, end: number) => Promise<void>;
  remove: (segment: SubtitleSegment) => Promise<void>;
  language?: LearningSegment; onWord: (word: WordToken) => void; saveTranslation: (segment: SubtitleSegment, text: string) => Promise<void>;
}) {
  const target = language?.translation.target_language === 'en' ? 'English' : 'Vietnamese';
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(segment.text);
  const [start, setStart] = useState(segment.start_time);
  const [end, setEnd] = useState(segment.end_time);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [translationEditing, setTranslationEditing] = useState(false);
  const [translation, setTranslation] = useState('');
  return <article className={`subtitle-row ${active ? 'active' : ''}`} data-testid="subtitle-row" data-source-text={segment.text} tabIndex={0} aria-current={active?'true':undefined} onClick={event=>{if(!(event.target as HTMLElement).closest('button,details,a,input,textarea,select'))seek(segment.start_time);}} onKeyDown={event=>{if(event.target===event.currentTarget && ['Enter',' '].includes(event.key)){event.preventDefault();event.stopPropagation();seek(segment.start_time);}}}>
    {!editing && <div lang="zh" className="reading-sentence">{language?.text===segment.text ? language.tokens.map(token=>token.selectable ? <button className="transcript-word" key={token.start} onClick={()=>onWord(token)} aria-label={`Look up ${token.text} from transcript`}><ruby>{token.text}<rt>{token.pinyin.normalize('NFC')}</rt></ruby></button> : <span key={token.start}>{token.text}</span>) : segment.text}</div>}
    {language && !editing && <p className="reading-translation" lang={language.translation.target_language==='en'?'en':'vi'}>{language.translation.text ?? (language.translation.status==='pending'?'Translating…':'Translation unavailable')}</p>}
    <details className="row-tools"><summary aria-label="Subtitle tools">⋯</summary><button className="text-action" onClick={()=>seek(segment.start_time)}>Go to this sentence</button><small>{Math.round(segment.confidence*100)}% OCR confidence{segment.edited?' · edited':''}</small>
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
    </form> : <><div className="segment-actions"><button className="text-action" onClick={() => { setText(segment.text); setStart(segment.start_time); setEnd(segment.end_time); setEditing(true); setError(''); }}>Edit subtitle</button><button className="text-action danger" disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      try { await remove(segment); } catch (cause) { setError((cause as Error).message); setBusy(false); }
    }}>Delete subtitle</button></div></>}
    {language && <div className="transcript-translation"><small>{language.translation.status === 'manual' ? `Your ${target} translation` : `${target} · local machine translation`}</small><p lang={target === "English" ? "en" : "vi"}>{language.translation.text ?? (language.translation.status === 'pending' ? 'Translating locally…' : `${target} translation unavailable.`)}</p>{language.translation.error && <p className="error-text">{language.translation.error}</p>}
      <button className="text-action" onClick={() => { setTranslation(language.translation.text ?? ''); setTranslationEditing(!translationEditing); }}>Edit {target} translation</button>
      {translationEditing && <form onSubmit={async (event) => { event.preventDefault(); setBusy(true); setError(''); try { await saveTranslation(segment, translation); setTranslationEditing(false); } catch (cause) { setError((cause as Error).message); } finally { setBusy(false); } }}><label className="sidebar-field">{target} sentence translation<textarea lang={target === "English" ? "en" : "vi"} aria-label={`${target} sentence translation`} value={translation} onChange={(event) => setTranslation(event.target.value)} required maxLength={5000} rows={3} /></label><button className="secondary-button" disabled={busy}>Save translation</button></form>}
    </div>}
    {error && <p role="alert" className="error-text">{error}</p>}
    </details>
  </article>;
}

export function Transcript({ document, currentTime, seek, save, remove, learning, onWord, selection, dictionary, dictionaryError, vocabulary, saveWord, deleteWord, saveTranslation, retryTranslation, library }: {
  library: ReactNode;
  document: SubtitleDocument | null; currentTime: number; seek: (time: number) => void;
  save: (segment: SubtitleSegment, text: string, start: number, end: number) => Promise<void>;
  remove: (segment: SubtitleSegment) => Promise<void>;
  learning: LearningDocument | null; onWord: (word: WordToken) => void;
  selection: { word: string; pinyin: string; nonce: number } | null; dictionary: DictionaryResult | null; dictionaryError: string;
  vocabulary: SavedWord[]; saveWord: (word: string, status: SavedWord['status'], notes: string) => Promise<void>; deleteWord: (id: string) => Promise<void>;
  saveTranslation: (segment: SubtitleSegment, text: string) => Promise<void>; retryTranslation: () => Promise<void>;
}) {
  const list=useRef<HTMLDivElement>(null);
  const activeId=transcriptSubtitle(document?.segments??[],currentTime)?.id;
  useEffect(()=>{
    const parent=list.current;const row=parent?.querySelector<HTMLElement>('[aria-current="true"]');
    if(!parent || !row)return;
    const outer=parent.getBoundingClientRect(),inner=row.getBoundingClientRect();
    if(inner.top<outer.top)parent.scrollTop-=outer.top-inner.top;
    else if(inner.bottom>outer.bottom)parent.scrollTop+=inner.bottom-outer.bottom;
  },[activeId,learning]);
  return <aside className="learning-column" aria-label="Learning tools">
    <section className="transcript-panel"><header className="transcript-heading"><h2>Transcript</h2><details className="transcript-tools"><summary aria-label="Transcript tools">⋯</summary>
    {document?.analysis && <div className="export-links"><a href={`/api/videos/${document.video_id}/export?format=json&analysis_id=${document.analysis.id}`} download>Export JSON</a><a href={`/api/videos/${document.video_id}/export?format=srt&analysis_id=${document.analysis.id}`} download>Export SRT</a></div>}
    <button className="text-action" onClick={()=>void retryTranslation()}>Retry sentence translations</button></details></header>
    <div className="transcript-content" ref={list} tabIndex={0} role="region" aria-label="Transcript sentences">
      {document?.segments.map(segment=><SubtitleRow key={`${document.analysis?.id}-${segment.id}-${segment.revision}`} segment={segment} active={segment.id===activeId} seek={seek} save={save} remove={remove} language={learning?.segments.find(item=>item.id===segment.id && item.revision===segment.revision && item.text===segment.text)} onWord={onWord} saveTranslation={saveTranslation}/>)}
      {!document?.segments.length && <p className="reading-empty">{document?.analysis?'No subtitles detected. Check the selected region.':'Choose the subtitle region below the player to create your transcript.'}</p>}
    </div></section>
    <WordSummary selection={selection} result={dictionary} error={dictionaryError} vocabulary={vocabulary} save={saveWord}/>

    {library}
  </aside>;
}
