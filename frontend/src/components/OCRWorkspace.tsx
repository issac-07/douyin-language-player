import { useEffect, useRef, useState } from 'react';
import type { AnalysisJob, ProcessingSettings, SubtitleDocument, SubtitleSegment, Video } from '../types';
import { api } from '../services/api';
import { formatTime } from '../services/playback';
import { VideoPlayer } from './VideoPlayer';
import { ROIEditor } from './ROIEditor';
import { Transcript } from './Transcript';
import { Icon } from './Icon';

const activeJob = (job: AnalysisJob | null) => Boolean(job && ['pending', 'processing'].includes(job.status));

// App keys this component by video ID. All requests and results also carry that ID.
export function OCRWorkspace({ video }: { video: Video }) {
  const [settings, setSettings] = useState<ProcessingSettings | null>(null);
  const [document, setDocument] = useState<SubtitleDocument | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [time, setTime] = useState(0);
  const [previewTime, setPreviewTime] = useState(Math.min(1, video.duration / 2));
  const media = useRef<HTMLVideoElement>(null);
  const mounted = useRef(true);
  const operation = useRef(false);
  const running = activeJob(job);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    Promise.all([api.settings(video.id), api.subtitles(video.id, controller.signal), api.latestAnalysis(video.id, controller.signal)])
      .then(([value, result, latest]) => {
        if (!controller.signal.aborted && result.video_id === video.id) {
          setSettings(value); setDocument(result); setJob(latest);
        }
      }).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => { mounted.current = false; controller.abort(); };
  }, [video.id]);

  useEffect(() => {
    if (!job || !activeJob(job)) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await api.job(job.id, controller.signal);
        if (controller.signal.aborted || next.video_id !== video.id || next.id !== job.id) return;
        if (!activeJob(next)) {
          const result = await api.subtitles(video.id, controller.signal);
          if (!controller.signal.aborted && result.video_id === video.id) { setDocument(result); setJob(next); }
        } else { setJob(next); timer = setTimeout(poll, 750); }
      } catch (cause) {
        if (!controller.signal.aborted) { setError(`Progress connection failed: ${(cause as Error).message} Retrying…`); timer = setTimeout(poll, 2000); }
      }
    };
    timer = setTimeout(poll, 250);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [job?.id, job?.status, video.id]);

  const analyze = async (force: boolean) => {
    if (!settings || operation.current) return;
    operation.current = true; setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.analyze(video.id, settings, force);
      if (!mounted.current || result.job.video_id !== video.id) return;
      setJob(result.job);
      if (result.cached) {
        const saved = await api.subtitles(video.id);
        if (mounted.current && saved.video_id === video.id) { setDocument(saved); setMessage('Loaded cached subtitles, including your corrections. No OCR rerun was needed.'); }
      } else setMessage('Analysis queued locally. You can keep watching or switch videos.');
    } catch (cause) { if (mounted.current) setError((cause as Error).message); }
    finally { operation.current = false; if (mounted.current) setBusy(false); }
  };

  const seek = (value: number) => {
    if (media.current) { media.current.currentTime = value; setTime(value); }
  };
  const saveSegment = async (segment: SubtitleSegment, text: string, start: number, end: number) => {
    if (!document?.analysis) return;
    const result = await api.editSubtitle(video.id, document.analysis.id, segment, text, start, end);
    if (mounted.current && result.video_id === video.id) setDocument(result);
  };
  const removeSegment = async (segment: SubtitleSegment) => {
    if (!document?.analysis) return;
    const result = await api.deleteSubtitle(video.id, document.analysis.id, segment);
    if (mounted.current && result.video_id === video.id) setDocument(result);
  };

  return <div className="workspace-grid">
    <section className="viewing-column" aria-label="Video workspace">
      <VideoPlayer video={video} segments={document?.segments ?? []} mediaRef={media} onTimeChange={setTime} />
      <div className="video-details"><div><h2 title={video.original_name}>{video.original_name}</h2><p>{video.width} × {video.height} <span>·</span> {formatTime(video.duration)} <span>·</span> {video.video_codec.toUpperCase()} {video.audio_codec && ` / ${video.audio_codec.toUpperCase()}`} <span>·</span> {(video.size_bytes / 1024 / 1024).toFixed(1)} MB</p></div><span className="subtle-tag">Imported locally</span></div>
      {video.codec_warning && <p className="codec-warning" role="status">{video.codec_warning}</p>}
      <details className="processing-panel">
        <summary><span><Icon name="settings" size={17} /> Subtitle analysis settings</span><span className="muted">Local Chinese OCR</span></summary>
        <p>Pause on a subtitle, then use that frame below. Draw a rectangle around the Chinese text; drag it to move or drag a corner to resize. Black bars are excluded.</p>
        {settings && <>
          <div className="preview-toolbar"><button className="secondary-button" onClick={() => setPreviewTime(Math.min(media.current?.currentTime ?? 0, Math.max(0, video.duration - 0.1)))}>Use current frame</button><span>Preview at {previewTime.toFixed(2)}s</span></div>
          <ROIEditor video={video} roi={settings.roi} onChange={(roi) => { setSettings({ ...settings, roi }); setMessage(''); }} timestamp={previewTime} />
          <form onSubmit={async (event) => {
            event.preventDefault(); if (operation.current) return; operation.current = true; setBusy(true); setError('');
            try { const result = await api.saveSettings(video.id, settings); if (mounted.current) { setSettings(result); setMessage('Settings saved locally. No analysis has been run.'); } }
            catch (cause) { if (mounted.current) setError((cause as Error).message); }
            finally { operation.current = false; if (mounted.current) setBusy(false); }
          }}>
            <div className="settings-grid">
              <label>Samples / second<input type="number" min="0.25" max="10" step="0.25" required value={settings.sample_fps} onChange={(event) => { setMessage(''); setSettings({ ...settings, sample_fps: Number(event.target.value) }); }} /></label>
              {(['x', 'y', 'width', 'height'] as const).map((key) => <label key={key}>{`Region ${key}`}<input type="number" min={key === 'width' || key === 'height' ? '0.001' : '0'} max="1" step="any" required value={Number(settings.roi[key].toFixed(4))} onChange={(event) => { setMessage(''); setSettings({ ...settings, roi: { ...settings.roi, [key]: Number(event.target.value) } }); }} /></label>)}
            </div>
            <div className="analysis-actions"><button className="secondary-button" disabled={busy}>Save settings</button><button className="primary-button" type="button" disabled={busy || running} onClick={() => void analyze(false)}>Analyze Video</button>{document?.analysis && <button className="secondary-button" type="button" disabled={busy || running} onClick={() => void analyze(true)}>Rerun OCR</button>}</div>
          </form>
        </>}
        {job && <div className="analysis-status" data-testid="analysis-status" data-status={job.status}>
          <div className="analysis-status-heading"><strong>{({ pending: 'Queued', processing: 'Analyzing video', completed: 'Analysis complete', failed: 'Analysis failed', cancelled: 'Analysis cancelled' })[job.status]}</strong>{running && <button className="text-action" disabled={busy} onClick={async () => {
            setBusy(true); setError('');
            try {
              const result = await api.cancel(job.id);
              const saved = await api.subtitles(video.id);
              if (mounted.current && result.video_id === video.id && saved.video_id === video.id) { setJob(result); setDocument(saved); }
            }
            catch (cause) { if (mounted.current) setError((cause as Error).message); }
            finally { if (mounted.current) setBusy(false); }
          }}>Cancel analysis</button>}</div>
          <progress max="1" value={job.progress} aria-label="OCR processing progress" />
          <p>{job.metrics.frames_processed} sampled frames · {Math.round(job.progress * 100)}% · {job.metrics.total_seconds.toFixed(1)}s elapsed{job.status === 'completed' ? ` · ${job.metrics.unique_segments} detected segments` : ''}</p>
          {job.error && <p role="alert" className="error-text">{job.error}</p>}
          {job.status === 'cancelled' && <p>The previous completed transcript is preserved. Cancellation is checked between frames and after in-flight inference.</p>}
        </div>}
        {document?.analysis && settings && JSON.stringify(document.analysis.settings) !== JSON.stringify(settings) && <p className="codec-warning">The displayed transcript uses earlier analysis settings. Analyze with the selected region to update it.</p>}
        {document?.analysis && <p>Timing comes from sampled video frames, with approximately {document.analysis.timestamp_uncertainty.toFixed(2)}s sampling uncertainty. It does not identify exact speech or word boundaries. A forced rerun creates a fresh transcript; export corrections you wish to keep.</p>}
        {message && <p className="success" role="status">{message}</p>}
        {error && <p className="error-text" role="alert">{error}</p>}
      </details>
      <details className="keyboard-help"><summary>Keyboard shortcuts</summary><p><kbd>Space</kbd> / <kbd>K</kbd> play or pause <span>·</span> <kbd>←</kbd> <kbd>→</kbd> seek 5 seconds <span>·</span> <kbd>M</kbd> mute <span>·</span> <kbd>F</kbd> fullscreen. Focus the crop rectangle and use arrow keys to move it; Shift moves faster.</p></details>
    </section>
    <Transcript document={document} currentTime={time} seek={seek} save={saveSegment} remove={removeSegment} />
  </div>;
}
