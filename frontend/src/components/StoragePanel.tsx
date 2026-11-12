import { useState } from 'react';
import { api } from '../services/api';
type Inventory = { data_directory: string; groups: Record<string, { path: string; bytes: number }>; counts: Record<string, number>; reusable_database_bytes: number; videos: { id: string; name: string; bytes: number }[] };
export function StoragePanel() {
  const [data, setData] = useState<Inventory | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const refresh = async () => { setBusy(true); try { setData(await api.storage()); } catch (e) { setMessage((e as Error).message); } finally { setBusy(false); } };
  const clean = async (kind: 'translation_cache' | 'language_cache' | 'uncorrected_history') => {
    if (!window.confirm(`Remove ${kind}? Active/corrected subtitles, manual translations, saved vocabulary, models and media are kept. Cache data will be regenerated when needed.`)) return;
    setBusy(true);
    try { const result = await api.cleanStorage(kind); setMessage(`${result.deleted_records} records removed. ${result.note}`); setData(await api.storage()); }
    catch (e) { setMessage((e as Error).message); } finally { setBusy(false); }
  };
  return <details className="processing-panel"><summary>Local storage / Dung lượng lưu trữ</summary><button className="secondary-button" disabled={busy} onClick={() => void refresh()}>Check storage usage</button>
    {data && <><p>Data: {data.data_directory}</p><ul>{Object.entries(data.groups).map(([name, item]) => <li key={name}>{name}: {(item.bytes / 1048576).toFixed(1)} MiB <small>{item.path}</small></li>)}</ul><p>Counts: {Object.entries(data.counts).map(([k,v]) => `${k}: ${v}`).join(' · ')}</p><ul>{data.videos.map(v => <li key={v.id}>{v.name}: {(v.bytes / 1048576).toFixed(1)} MiB</li>)}</ul><p>SQLite has {(data.reusable_database_bytes / 1048576).toFixed(1)} MiB available for reuse. Cleanup does not necessarily shrink its file immediately. Test/validation folders are measured here; this screen does not delete them.</p></>}
    <div className="analysis-actions"><button disabled={busy} onClick={() => void clean('translation_cache')}>Clear machine translation cache</button><button disabled={busy} onClick={() => void clean('language_cache')}>Clear word/pinyin cache</button><button disabled={busy} onClick={() => void clean('uncorrected_history')}>Remove inactive, uncorrected OCR history</button></div><p>Caches regenerate when opened. Original video sources, library media, dictionaries, models, vocabulary and corrected transcripts are kept. Repeated OCR creates history; use the history cleanup to control it.</p>{message && <p role="status">{message}</p>}
  </details>;
}
