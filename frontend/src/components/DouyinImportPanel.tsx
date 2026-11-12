import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import type { URLImportJob, Video } from '../types';

const terminal = (job: URLImportJob) => ['completed', 'failed', 'cancelled'].includes(job.status);
const megabytes = (value: number) => `${(value / 1024 / 1024).toFixed(1)} MB`;
const errorLabels: Record<string, string> = {
  site_http_403: 'Site returned HTTP 403',
  extractor_compatibility: 'Extractor compatibility problem',
  unsupported_extractor: 'Unsupported extractor',
  login_required: 'Authentication required',
  geographic_restriction: 'Geographic restriction reported',
  video_unavailable: 'Video or link unavailable',
  network_error: 'Network connection failed',
  timeout: 'Import timed out',
  download_failure: 'Media download failed',
  invalid_url: 'Invalid URL',
  unsupported_platform: 'Unsupported URL',
};
const operationLabels: Record<string, string> = { resolve_url: 'Resolve sharing link', extract_metadata: 'Extract metadata', download_media: 'Download media', validate_media: 'Validate media', import_library: 'Save to library' };

export function DouyinImportPanel({ onImported, onLocal, localBusy }: { onImported: (video: Video, reused: boolean) => void; onLocal: () => void; localBusy: boolean }) {
  const [mode, setMode] = useState<'url' | 'local'>('url');
  const [text, setText] = useState('');
  const [analyze, setAnalyze] = useState(false);
  const [publicPage, setPublicPage] = useState(false);
  const [job, setJob] = useState<URLImportJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState(true);
  const callback = useRef(onImported);
  const follow = useRef(false);
  const submission = useRef(false);
  const generation = useRef(0);
  callback.current = onImported;
  const active = job !== null && !terminal(job);

  useEffect(() => {
    const controller = new AbortController();
    const version = generation.current;
    let remembered: string | null = null;
    try { remembered = localStorage.getItem('dlp-import-job'); } catch { /* Optional browser storage. */ }
    if (remembered) void api.urlImport(remembered, controller.signal).then((current) => {
      if (controller.signal.aborted || generation.current !== version) return;
      follow.current = !terminal(current); setJob(current);
      if (current.status === 'completed') setExpanded(false);
    }).catch(() => { /* An isolated library or cleared job history can invalidate this ID. */ });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!job || terminal(job)) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const current = await api.urlImport(job.id, controller.signal);
        if (controller.signal.aborted) return;
        setJob((previous) => previous?.id === current.id && terminal(previous) && !terminal(current) ? previous : current); setError('');
        if (current.status === 'completed' && current.video && follow.current) {
          follow.current = false; setExpanded(false); callback.current(current.video, current.reused);
        }
        if (!terminal(current)) timer = setTimeout(() => void poll(), 650);
      } catch (cause) {
        if (!controller.signal.aborted) { setError((cause as Error).message); timer = setTimeout(() => void poll(), 2000); }
      }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [job?.id, active]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submission.current || active) return;
    generation.current += 1;
    submission.current = true; setBusy(true); setError('');
    try {
      const current = await api.importDouyin(text, analyze, publicPage);
      follow.current = true; setJob(current);
      try { localStorage.setItem('dlp-import-job', current.id); } catch { /* Import continues without storage. */ }
    } catch (cause) { setError((cause as Error).message); }
    finally { submission.current = false; setBusy(false); }
  };

  return <section className="import-panel" aria-label="Import video sources">
    <button className="text-button import-options-toggle" aria-expanded={expanded} aria-controls="import-options-content" onClick={() => setExpanded(!expanded)}>{expanded ? 'Hide import options' : 'Import another video'}</button>
    <div id="import-options-content" hidden={!expanded}>
    <div className="import-options" role="tablist" aria-label="Video import method">
      <button id="url-import-tab" role="tab" aria-selected={mode === 'url'} aria-controls="import-source-content" onClick={() => setMode('url')}>Import from Douyin URL</button>
      <button id="local-import-tab" role="tab" aria-selected={mode === 'local'} aria-controls="import-source-content" onClick={() => setMode('local')}>Import Local MP4</button>
    </div>
    <div id="import-source-content" role="tabpanel" aria-labelledby={mode === 'url' ? 'url-import-tab' : 'local-import-tab'}>
      {mode === 'url' ? <form onSubmit={(event) => void submit(event)}>
        <label htmlFor="douyin-link">Douyin link or sharing text</label>
        <div className="url-input-row"><textarea id="douyin-link" rows={2} maxLength={8192} value={text} onChange={(event) => setText(event.target.value)} placeholder="https://v.douyin.com/… or https://www.douyin.com/video/…" disabled={active || busy} required /><button className="primary-button" type="submit" disabled={!text.trim() || busy || active}>{busy ? 'Starting…' : 'Import link'}</button></div>
        <div className="import-help"><label><input type="checkbox" checked={analyze} onChange={(event) => setAnalyze(event.target.checked)} disabled={active || busy} /> Analyze after import</label><small>Uses a saved subtitle region. For a new video, select its region first.</small></div>
        <div className="import-help"><label><input type="checkbox" checked={publicPage} onChange={(event) => setPublicPage(event.target.checked)} disabled={active || busy} /> Use public-page import (isolated Edge)</label><small>Opens the official page in a temporary session. Site cookies stay there; your existing profile is never read. No login or verification interaction.</small></div>
        <small className="muted">Public videos only. If Douyin restricts access, you can import a local MP4.</small>
      </form> : <div className="local-import-choice"><p>Choose an MP4 from this computer. The original video and audio stay intact.</p><button className="secondary-button" disabled={localBusy} onClick={onLocal}>Choose local MP4</button></div>}
    </div>
    </div>
    {error && <div className="alert error" role="alert">{error}</div>}
    {job && <div className={`url-import-status ${job.status}`} aria-label="Douyin import status">
      <div className="import-status-heading"><strong role="status">{job.status === 'completed' ? (job.reused ? 'Opened existing video' : 'Douyin video imported') : job.status === 'failed' ? `Douyin import failed${job.error_code && errorLabels[job.error_code] ? ` · ${errorLabels[job.error_code]}` : ''}` : job.status === 'cancelled' ? 'Import cancelled' : `${job.status[0].toUpperCase()}${job.status.slice(1)}…`}</strong>{active && <button className="text-button" onClick={() => void api.cancelImport(job.id).then(setJob).catch((cause: Error) => setError(cause.message))}>Cancel import</button>}</div>
      {job.metadata && <p className="import-metadata">{job.metadata.title ?? 'Douyin video'}{job.metadata.uploader && <span> · {job.metadata.uploader}</span>}</p>}
      {active && <><progress aria-label="Download progress" max={job.total_bytes || 1} value={job.status === 'downloading' && job.total_bytes ? job.bytes_downloaded : undefined} /><small>{job.status === 'downloading' ? `${megabytes(job.bytes_downloaded)}${job.total_bytes ? ` / ${megabytes(job.total_bytes)}` : ' downloaded · total size unknown'}` : 'Working in the background'}{job.attempt > 1 && ` · attempt ${job.attempt}/${job.max_attempts}`}</small></>}
      {job.error && <p role="alert">{job.error_code === 'access_denied' && !job.diagnostics?.length ? 'This earlier import used a generic access-denied message and did not retain its HTTP status. Retry the link for current diagnostics.' : job.error}</p>}
      {job.status === 'failed' && job.diagnostics && job.diagnostics.length > 0 && <details className="import-diagnostics"><summary>Diagnostic details</summary>
        <p>{job.error_operation && `Stage: ${operationLabels[job.error_operation] ?? job.error_operation}. `}{job.upstream_http_status && `HTTP ${job.upstream_http_status}. `}{job.extractor_version && `yt-dlp ${job.extractor_version}.`}</p>
        <ol>{job.diagnostics.map((entry, index) => <li key={index}>{operationLabels[entry.operation] ?? entry.operation}: {entry.event}{entry.http_status ? ` · HTTP ${entry.http_status}` : ''}{entry.host ? ` · ${entry.host}` : ''}{entry.exception_type ? ` · ${entry.exception_type}` : ''}{entry.upstream_reason ? ` · ${entry.upstream_reason.replaceAll('_', ' ')}` : ''}</li>)}</ol>
      </details>}
      {job.analysis_message && <p>{job.analysis_message}</p>}
      {job.status === 'completed' && job.video && <button className="text-button" onClick={() => callback.current(job.video!, job.reused)}>Open imported video</button>}
      {(job.status === 'failed' || job.status === 'cancelled') && <button className="secondary-button" onClick={onLocal} disabled={localBusy}>Import a local MP4 instead</button>}
    </div>}
  </section>;
}
