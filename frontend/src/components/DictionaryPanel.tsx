import { useEffect, useState } from 'react';
import type { DictionaryResult, SavedWord, WordToken } from '../types';

export function DictionaryPanel({ selection, result, error, vocabulary, save, editable = true }: {
  editable?: boolean; selection: { word: string; pinyin: string } | null; result: DictionaryResult | null; error: string;
  vocabulary: SavedWord[]; save: (word: string, status: SavedWord['status'], notes: string) => Promise<void>;
}) {
  const existing = vocabulary.find((word) => word.word === selection?.word);
  const [status, setStatus] = useState<SavedWord['status']>('new');
  const [notes, setNotes] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => { setStatus(existing?.status ?? 'new'); setNotes(existing?.notes ?? ''); }, [selection?.word,existing?.status,existing?.notes]);
  useEffect(()=>setMessage(''),[selection?.word]);
  return <details className="dictionary-details" open data-testid="dictionary-panel">
    <summary>Word details</summary>
    {!selection ? <p>Choose a Chinese word in the video or transcript to see its verified dictionary meanings here.</p> : <>
      <div className="dictionary-word" lang="zh">{selection.word}</div><p className="dictionary-pinyin" lang="zh-Latn">{selection.pinyin || result?.entries[0]?.pinyin}</p>
      {error && <p className="error-text" role="alert">{error}</p>}
      {!result && !error && <p role="status">Looking up the local dictionary…</p>}
      {result?.translation && <div><strong>Tiếng Việt · dịch máy trực tiếp từ từ Trung (không phải định nghĩa CC-CEDICT)</strong><p>{result.translation.text ?? (result.translation.status === 'pending' ? 'Translating locally…' : result.translation.error ?? 'Unavailable')}</p><small>Từ đứng riêng có thể thiếu ngữ cảnh, đặc biệt với tên riêng.</small></div>}
      {result?.parts && result.parts.length > 0 && <div><strong>Không có mục từ nguyên cụm. Các mục từ thành phần đã xác minh:</strong><ul>{result.parts.map((part, i) => <li key={i}>{part.simplified} ({part.pinyin}): {part.meanings.join('; ')}</li>)}</ul><p>Không ghép các nghĩa này thành nghĩa chắc chắn của cụm hoặc tên riêng.</p></div>}
      {result?.entries.map((entry, index) => <div className="dictionary-entry" key={index}><span lang="zh-Latn">{entry.pinyin}</span>{entry.traditional !== entry.simplified && <span lang="zh" className="dictionary-traditional">{entry.traditional}</span>}<ul>{entry.meanings.map((meaning, number) => <li key={number}>{meaning}</li>)}</ul></div>)}
      {result && !result.available && <p>The local dictionary is unavailable. Install the language resources described in the README and restart the backend.</p>}
      {result?.available && result.entries.length === 0 && <p>No CC-CEDICT entry was found for this exact word. You can still save the original word with your own notes.</p>}
      {editable && <form onSubmit={async (event) => {
        event.preventDefault(); setBusy(true); setMessage('');
        try { await save(selection.word, status, notes); setMessage('Vocabulary saved locally.'); }
        catch (cause) { setMessage((cause as Error).message); }
        finally { setBusy(false); }
      }}>
        <label className="sidebar-field">Learning status<select aria-label="Vocabulary learning status" value={status} onChange={(event) => setStatus(event.target.value as SavedWord['status'])}><option value="new">New</option><option value="learning">Learning</option><option value="known">Known</option></select></label>
        <label className="sidebar-field">Personal notes<textarea aria-label="Vocabulary notes" rows={3} maxLength={5000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
        <button className="primary-button" disabled={busy}>{busy ? 'Saving…' : existing ? 'Update saved word' : 'Save Vocabulary'}</button>
        {message && <p role="status">{message}</p>}
      </form>}
    </>}
    <details className="dictionary-attribution"><summary>Data source & license</summary><p><a href="https://www.mdbg.net/chinese/dictionary?page=cedict" target="_blank" rel="noreferrer">CC-CEDICT contributors / MDBG</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">CC BY-SA 4.0</a>. Verified definitions are English; optional Vietnamese word translations and English/Vietnamese sentence translations are machine-generated separately.</p></details>
  </details>;
}

function SavedWordCard({ word, save, remove, onWord }: { word: SavedWord; save: (word: string, status: SavedWord['status'], notes: string) => Promise<void>; remove: (id: string) => Promise<void>; onWord: (token: WordToken) => void }) {
  const [status, setStatus] = useState(word.status);
  const [notes, setNotes] = useState(word.notes);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  return <form className="saved-word-card" onSubmit={async (event) => {
    event.preventDefault(); setBusy(true); setMessage('');
    try { await save(word.word, status, notes); setMessage('Saved'); } catch (cause) { setMessage((cause as Error).message); }
    finally { setBusy(false); }
  }}>
    <button type="button" className="saved-word-title" lang="zh" onClick={() => onWord({ text: word.word, pinyin: word.pinyin, start: 0, end: word.word.length, selectable: true })}>{word.word}</button><p lang="zh-Latn">{word.pinyin}</p>
    <label className="sidebar-field">Status<select aria-label={`Status for ${word.word}`} value={status} onChange={(event) => setStatus(event.target.value as SavedWord['status'])}><option value="new">New</option><option value="learning">Learning</option><option value="known">Known</option></select></label>
    <label className="sidebar-field">Notes<textarea aria-label={`Notes for ${word.word}`} rows={2} maxLength={5000} value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
    <div className="segment-actions"><button className="text-action" disabled={busy}>Save word changes</button><button type="button" className="text-action danger" disabled={busy} onClick={async () => { setBusy(true); try { await remove(word.id); } catch (cause) { setMessage((cause as Error).message); setBusy(false); } }}>Remove saved word</button></div>
    {message && <p role="status">{message}</p>}
  </form>;
}

export function VocabularyPanel({ words, save, remove, onWord }: { words: SavedWord[]; save: (word: string, status: SavedWord['status'], notes: string) => Promise<void>; remove: (id: string) => Promise<void>; onWord: (token: WordToken) => void }) {
  return <div className="saved-vocabulary"><div className="export-links"><a href="/api/vocabulary/export/csv" download>Export vocabulary CSV</a></div>{words.length === 0 && <p>Save words from the dictionary to build your personal wordbook.</p>}{words.map((word) => <SavedWordCard key={`${word.id}-${word.updated_at}`} word={word} save={save} remove={remove} onWord={onWord} />)}</div>;
}
