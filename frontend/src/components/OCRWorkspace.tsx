import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { AnalysisJob, DictionaryResult, LearningDocument, ProcessingSettings, SavedWord, SubtitleDocument, SubtitleSegment, Video, WordToken } from '../types';
import { api } from '../services/api';
import { formatTime } from '../services/playback';
import { VideoPlayer } from './VideoPlayer';
import { ROIEditor } from './ROIEditor';
import { Transcript } from './Transcript';
import { Icon } from './Icon';
import { usePlayerSettings } from '../hooks/usePlayerSettings';

const activeJob = (job: AnalysisJob | null) => Boolean(job && ['pending', 'processing'].includes(job.status));

// App keys this component by video ID. All requests and results also carry that ID.
export function OCRWorkspace({ video, appearance, library, vocabularyRevision, libraryActions }: { libraryActions?:ReactNode; library:ReactNode; vocabularyRevision:number; video: Video; appearance: ReturnType<typeof usePlayerSettings> }) {
  const [settings, setSettings] = useState<ProcessingSettings | null>(null);
  const [document, setDocument] = useState<SubtitleDocument | null>(null);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [learning, setLearning] = useState<LearningDocument | null>(null);
  useEffect(()=>setLearning(null),[appearance.settings.sentence_language]);
  const [languageRetry, setLanguageRetry] = useState(0);
  const [dictionary, setDictionary] = useState<DictionaryResult | null>(null);
  const [selection, setSelection] = useState<{ word: string; pinyin: string; nonce: number } | null>(null);
  const [dictionaryError, setDictionaryError] = useState('');
  const [vocabulary, setVocabulary] = useState<SavedWord[]>([]);
  const workspace = useRef<HTMLDivElement>(null);
  const dictionaryRequest = useRef<AbortController | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const [capabilities, setCapabilities] = useState<{openvino_cpu: boolean; intel_gpu: boolean} | null>(null);
  useEffect(() => { const c = new AbortController(); api.ocrCapabilities().then(value => { if (!c.signal.aborted) setCapabilities(value); }).catch(() => {}); return () => c.abort(); }, []);
  const presetCompatible = settings?.performance?.backend === 'auto' && settings.performance.cpu_runtime === 'ort' && settings.performance.cpu_threads === 4 && (settings.performance.gpu_requests ?? 1) === 1;
  const preset = !presetCompatible ? 'custom' : settings?.sample_fps === 1 && settings.performance?.mode === 'balanced' && !settings.performance?.refine_timing ? 'speed' : settings?.sample_fps === 2 && settings.performance?.mode === 'balanced' && !settings.performance?.refine_timing ? 'balanced' : settings?.sample_fps === 5 && settings.performance?.refine_timing && settings.performance?.mode === 'balanced' ? 'timing' : 'custom';

  const [time, setTime] = useState(0);
  const [seekRequest,setSeekRequest]=useState<{time:number;nonce:number}|null>(null);
  const seekNonce=useRef(0);
  const [previewTime, setPreviewTime] = useState(Math.min(1, video.duration / 2));
  const media = useRef<HTMLVideoElement>(null);
  const mounted = useRef(true);
  const operation = useRef(false);
  const currentLanguage = useRef(appearance.settings.sentence_language ?? "vi");
  currentLanguage.current = appearance.settings.sentence_language ?? "vi";
  const running = activeJob(job);
  const [clock, setClock] = useState(Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setClock(Date.now()), 250);
    return () => clearInterval(timer);
  }, [running]);
  const elapsed = running && job?.started_at ? Math.max(job.metrics.total_seconds, (clock - Date.parse(job.started_at)) / 1000) : job?.metrics.total_seconds ?? 0;
  const stages: Record<string, string> = { queued: 'Queued', initializing: 'Preparing subtitles', reading_and_ocr: 'Finding subtitles', refining: 'Refining subtitle timing', saving: 'Saving subtitles', completed: 'Subtitles saved' };


  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    Promise.all([api.settings(video.id), api.subtitles(video.id, controller.signal), api.latestAnalysis(video.id, controller.signal)])
      .then(([value, result, latest]) => {
        if (!controller.signal.aborted && result.video_id === video.id) {
          setSettings(value); setDocument(result); setJob(latest);
        }
      }).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    api.vocabulary().then((words) => { if (!controller.signal.aborted) setVocabulary(words); }).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => { mounted.current = false; controller.abort(); dictionaryRequest.current?.abort(); };
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

  const languageSignature = document?.segments.map((segment) => `${segment.id}:${segment.revision}:${segment.text}`).join('|') ?? '';
  useEffect(() => {
    if (!document?.analysis) { setLearning(null); return; }
    const analysisId = document.analysis.id;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api.learning(video.id, controller.signal, appearance.settings.sentence_language ?? "vi");
        if (controller.signal.aborted || result.video_id !== video.id || result.analysis_id !== analysisId || result.target_language !== currentLanguage.current) return;
        setLearning(result);
        if (result.segments.some((segment) => segment.translation.status === 'pending')) timer = setTimeout(poll, 700);
      } catch (cause) {
        if (!controller.signal.aborted) setError(`Language processing failed: ${(cause as Error).message}`);
      }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [document?.analysis?.id, languageSignature, video.id, languageRetry, appearance.settings.sentence_language]);

  useEffect(()=>{let alive=true;api.vocabulary().then(words=>{if(alive)setVocabulary(words);}).catch(cause=>{if(alive)setError(cause.message);});return()=>{alive=false;};},[vocabularyRevision]);
  const selectWord = (token: WordToken) => {
    dictionaryRequest.current?.abort();
    const controller = new AbortController(); dictionaryRequest.current = controller;
    setSelection({ word: token.text, pinyin: token.pinyin, nonce: Date.now() }); setDictionary(null); setDictionaryError('');
    if (appearance.settings.pause_on_word) media.current?.pause();

  };

  useEffect(() => {
    if (!selection) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    dictionaryRequest.current?.abort();
    dictionaryRequest.current = controller;
    const poll = async () => {
      try {
        const result = await api.dictionary(selection.word, controller.signal, appearance.settings.dictionary_language ?? 'en');
        if (controller.signal.aborted) return;
        setDictionary(result);
        if (result.translation?.status === 'pending') timer = setTimeout(poll, 750);
      } catch (e) { if (!controller.signal.aborted) setDictionaryError((e as Error).message); }
    };
    setDictionary(null); setDictionaryError(''); void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [selection?.nonce, appearance.settings.dictionary_language]);

  const analyze = async (force: boolean) => {
    if (!settings || operation.current) return;
    operation.current = true; setBusy(true); setError(''); setMessage('');
    try {
      const result = await api.analyze(video.id, settings, force);
      if (!mounted.current || result.job.video_id !== video.id) return;
      setJob(result.job);
      if (result.cached) {
        const saved = await api.subtitles(video.id);
        if (mounted.current && saved.video_id === video.id) { setDocument(saved); setMessage('Opened saved subtitles.'); }
      } else setMessage('Subtitle processing started.');
    } catch (cause) { if (mounted.current) setError((cause as Error).message); }
    finally { operation.current = false; if (mounted.current) setBusy(false); }
  };

  const seek = (value: number) => {
    if (media.current) { setTime(value);setSeekRequest({time:value,nonce:++seekNonce.current}); }
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

  return <div className="workspace-grid learning-workspace" ref={workspace}>
    <section className="viewing-column" aria-label="Video workspace">
      <div className="language-progress" role="status">{learning?.segments.some(item => item.translation.status === 'pending') ? 'Preparing sentence translations…' : learning?.segments.some(item => ['failed', 'unavailable'].includes(item.translation.status)) ? 'Some translations are unavailable. See Transcript for details.' : ''}</div>
      <VideoPlayer seekRequest={seekRequest} libraryActions={libraryActions} video={video} segments={document?.segments ?? []} mediaRef={media} onTimeChange={setTime} learning={learning} settings={appearance.settings} updateSettings={appearance.update} settingsStatus={appearance.status} roi={document?.analysis?.settings.roi ?? settings?.roi} onWord={selectWord} fullscreenTarget={workspace} />
      <div className="video-details"><div><h2 title={video.original_name}>{video.title ?? video.original_name}</h2><details className="video-file-details"><summary>Video details</summary><p>{video.width} × {video.height} <span>·</span> {formatTime(video.duration)} <span>·</span> {video.video_codec.toUpperCase()} {video.audio_codec && ` / ${video.audio_codec.toUpperCase()}`} <span>·</span> {(video.size_bytes / 1024 / 1024).toFixed(1)} MB</p></details>{video.source_url && <p>{video.uploader && `${video.uploader} · `}<a href={video.source_url} target="_blank" rel="noreferrer">Douyin source</a></p>}</div><span className="subtle-tag">{video.imported_from === 'douyin' ? 'Douyin · local copy' : 'Imported locally'}</span></div>
      {video.codec_warning && <p className="codec-warning" role="status">{video.codec_warning}</p>}
      <details className="processing-panel">
        <summary><span><Icon name="settings" size={17} /> Subtitle analysis settings</span><span className="muted">Local Chinese OCR</span></summary>
<details className="inline-help"><summary>How to choose the subtitle region</summary><p>Pause on a subtitle and choose Use current frame. Draw around the Chinese text. Drag to move or resize the region. Black bars are excluded.</p></details>
        {settings && <>
          <div className="preview-toolbar"><button className="secondary-button" onClick={() => setPreviewTime(Math.min(media.current?.currentTime ?? 0, Math.max(0, video.duration - 0.1)))}>Use current frame</button><span>Preview at {previewTime.toFixed(2)}s</span></div>
          <ROIEditor video={video} roi={settings.roi} onChange={(roi) => { setSettings({ ...settings, roi }); setMessage(''); }} timestamp={previewTime} />
          <form onSubmit={async (event) => {
            event.preventDefault(); if (operation.current) return; operation.current = true; setBusy(true); setError('');
            try { const result = await api.saveSettings(video.id, settings); if (mounted.current) { setSettings(result); setMessage('Settings saved.'); } }
            catch (cause) { if (mounted.current) setError((cause as Error).message); }
            finally { operation.current = false; if (mounted.current) setBusy(false); }
          }}>
            <label>OCR controls <select aria-label="OCR controls" value={advanced ? 'advanced' : 'basic'} onChange={(e) => setAdvanced(e.target.value === 'advanced')}><option value="basic">Basic</option><option value="advanced">Advanced</option></select></label>
            {!advanced && <div><label>Preset <select aria-label="OCR preset" value={preset} onChange={(e) => {
              const key = e.target.value;
              if (key === 'custom') return;
              setSettings({ ...settings, sample_fps: key === 'speed' ? 1 : key === 'balanced' ? 2 : 5, performance: { backend: 'auto', mode: 'balanced', cpu_threads: 4, cpu_runtime: 'ort', refine_timing: key === 'timing' } });
            }}><option value="speed">Faster scan</option><option value="balanced">Balanced</option><option value="timing">Closer subtitle timing</option><option value="custom" disabled>Custom · see Advanced</option></select></label><details className="inline-help"><summary>About these presets</summary><p>All presets use the same model. Faster scan uses 1 sample/second; Balanced uses 2; Closer subtitle timing uses 5 plus extra checks. Fewer samples can miss brief captions. No preset guarantees correct recognition.</p><p>Current settings: {settings.sample_fps} samples/second · {settings.performance?.backend ?? 'cpu'} · {settings.performance?.mode ?? 'accurate'} · {settings.performance?.cpu_runtime ?? 'ort'} · refine {settings.performance?.refine_timing ? 'on' : 'off'}. The selected region is preserved.</p></details></div>}
            <div hidden={!advanced}>
            <div className="settings-grid">
              <label>Samples / second<input type="number" min="0.25" max="10" step="0.25" required value={settings.sample_fps} onChange={(event) => { setMessage(''); setSettings({ ...settings, sample_fps: Number(event.target.value) }); }} /></label>
              {(['x', 'y', 'width', 'height'] as const).map((key) => <label key={key}>{`Region ${key}`}<input type="number" min={key === 'width' || key === 'height' ? '0.001' : '0'} max="1" step="any" required value={Number(settings.roi[key].toFixed(4))} onChange={(event) => { setMessage(''); setSettings({ ...settings, roi: { ...settings.roi, [key]: Number(event.target.value) } }); }} /></label>)}
            </div>
            <fieldset className="ocr-performance">
              <legend>OCR performance</legend>
              <div className="settings-grid">
                <label>Inference backend<select aria-label="Inference backend" value={settings.performance?.backend ?? 'cpu'} onChange={(event) => setSettings({ ...settings, performance: { mode: 'accurate', cpu_threads: 4, cpu_runtime: 'ort', ...settings.performance, backend: event.target.value as 'auto' | 'cpu' | 'intel-gpu' } })}>
                  <option value="auto">Auto (measured CPU policy)</option><option value="cpu">CPU</option><option value="intel-gpu" disabled={capabilities !== null && !capabilities.intel_gpu}>Intel GPU (OpenVINO){capabilities && !capabilities.intel_gpu ? " — unavailable in backend runtime" : ""}</option>
                </select></label>
                <label>Processing mode<select aria-label="Processing mode" value={settings.performance?.mode ?? 'accurate'} onChange={(event) => setSettings({ ...settings, performance: { backend: 'auto', cpu_threads: 4, cpu_runtime: 'ort', ...settings.performance, mode: event.target.value as 'accurate' | 'balanced' | 'fast' } })}>
                  <option value="accurate">Accurate</option><option value="balanced">Balanced</option><option value="fast">Fast (experimental stroke reuse)</option>
                </select></label>
                <label>CPU runtime<select aria-label="CPU runtime" disabled={settings.performance?.backend === 'intel-gpu'} value={settings.performance?.cpu_runtime ?? 'ort'} onChange={(event) => setSettings({ ...settings, performance: { backend: 'cpu', mode: 'balanced', cpu_threads: 4, ...settings.performance, cpu_runtime: event.target.value as 'ort' | 'openvino-cpu' } })}>
                  <option value="ort">ONNX Runtime</option><option value="openvino-cpu" disabled={capabilities !== null && !capabilities.openvino_cpu}>OpenVINO CPU (optional runtime){capabilities && !capabilities.openvino_cpu ? " — unavailable" : ""}</option>
                </select></label>
              </div>
              <label>CPU threads (Balanced / Fast)<select aria-label="CPU threads" disabled={settings.performance?.backend === 'intel-gpu' || settings.performance?.mode === 'accurate'} value={settings.performance?.cpu_threads ?? 4} onChange={e => setSettings({...settings, performance: {backend: 'auto', mode: 'balanced', cpu_runtime: 'ort', ...settings.performance, cpu_threads: Number(e.target.value) as 2 | 4 | 8}})}><option value="2">2</option><option value="4">4</option><option value="8">8</option></select></label>
              <details className="inline-help"><summary>About CPU & runtime</summary><p>Accurate uses timestamp seeking and 2 CPU threads. Balanced uses sequential decoding/prefetch. They use the same OCR model. Auto selects the portable CPU path. GPU requires the optional OpenVINO backend launcher; higher concurrency uses more memory.</p></details>
              <label><input type="checkbox" checked={settings.performance?.refine_timing ?? false} onChange={(event) => setSettings({ ...settings, performance: { backend: 'auto', mode: 'balanced', cpu_threads: 4, cpu_runtime: 'ort', ...settings.performance, refine_timing: event.target.checked } })} /> Refine subtitle start timing (extra OCR near transitions)</label>
              <label>Parallel GPU requests<select aria-label="Parallel GPU requests" disabled={settings.performance?.backend !== 'intel-gpu' || settings.performance?.mode === 'fast'} value={settings.performance?.gpu_requests ?? 1} onChange={(event) => setSettings({ ...settings, performance: { backend: 'intel-gpu', mode: 'balanced', cpu_threads: 4, cpu_runtime: 'ort', ...settings.performance, gpu_requests: Number(event.target.value) as 1 | 2 | 4 } })}><option value="1">1 — lower memory/startup</option><option value="2">2 — experimental parallel OCR</option><option value="4">4 — experimental, higher memory</option></select></label>
              <details className="inline-help"><summary>About performance & timing</summary><p>Balanced prepares upcoming frames while OCR runs. Parallel GPU requests use separate OCR engines and preserve media-time order; more requests may increase memory/startup and are not guaranteed faster. Fast is experimental and serial; it may save no OCR calls. Timing refinement checks two adjacent frames before moving a subtitle start earlier. Sample rate and ROI stay unchanged.</p></details>
              <button className="text-action" type="button" onClick={() => { const { performance: _performance, ...original } = settings; setSettings(original); }}>Restore original CPU OCR</button>
            </fieldset>
            </div>
            <details className="inline-help"><summary>How subtitle processing works</summary><p>Create / open subtitles opens matching saved subtitles, or runs OCR when none exist. Scan OCR again always scans again. Words/pinyin and translation are prepared afterwards; these are not two separate OCR/translation buttons.</p></details>
            {document?.analysis && <p className="correction-notice">Rescanning creates a new transcript. Export corrections you want to keep.</p>}
            <div className="analysis-actions"><button className="secondary-button" disabled={busy}>Save settings</button><button className="primary-button" type="button" disabled={busy || running} onClick={() => void analyze(false)}>Create / open subtitles</button>{document?.analysis && <button className="secondary-button" type="button" disabled={busy || running} onClick={() => void analyze(true)}>Scan OCR again</button>}</div>
          </form>
        </>}
        {document?.analysis && settings && JSON.stringify(document.analysis.settings) !== JSON.stringify(settings) && <p className="codec-warning">The displayed transcript uses earlier analysis settings. Analyze with the selected region to update it.</p>}
        {document?.analysis && <details className="inline-help"><summary>Timing & saved corrections</summary><p>Timing comes from sampled video frames, with approximately {document.analysis.timestamp_uncertainty.toFixed(2)}s sampling uncertainty. It does not identify exact speech or word boundaries. A forced rerun creates a fresh transcript; export corrections you wish to keep.</p></details>}
        {message && <p className="success" role="status">{message}</p>}
      </details>
        {job && <div className={`analysis-status ${running ? "is-running" : "is-finished"}`} data-testid="analysis-status" data-status={job.status}>
          <div className="analysis-status-heading"><strong role="status">{running ? stages[job.stage ?? ''] ?? 'Processing subtitles' : ({ pending: 'Queued', processing: 'Analyzing video', completed: 'Subtitles ready', failed: 'Analysis failed', cancelled: 'Analysis cancelled' })[job.status]}</strong>{running && <button className="text-action" disabled={busy} onClick={async () => {
            setBusy(true); setError('');
            try {
              const result = await api.cancel(job.id);
              const saved = await api.subtitles(video.id);
              if (mounted.current && result.video_id === video.id && saved.video_id === video.id) { setJob(result); setDocument(saved); }
            }
            catch (cause) { if (mounted.current) setError((cause as Error).message); }
            finally { if (mounted.current) setBusy(false); }
          }}>Cancel analysis</button>}</div>

          {running && <progress max="1" value={job.status === 'completed' ? 1 : job.stage === 'reading_and_ocr' ? job.progress : undefined} aria-label="OCR processing progress" />}
          {running && job.updated_at && clock - Date.parse(job.updated_at) > 10000 && <p className="codec-warning">No worker update for over 10 seconds. The model may still be busy; check the backend connection or cancel. This is not proof of a stalled job.</p>}
          <details className="processing-details" key={job.id}><summary>Processing details</summary>
          <p>{job.stage === "refining" ? `${job.stage_completed ?? 0}/${job.stage_total ?? "?"} segments checked · ` : ""}{job.metrics.frames_processed} sampled frames · {job.status === 'completed' ? '100% · ' : job.stage === 'reading_and_ocr' ? `${Math.floor(job.progress * 100)}% of video sampled · ` : ''}{Math.max(0, elapsed).toFixed(1)}s elapsed{job.status === 'completed' ? ` · ${job.metrics.unique_segments} detected segments` : ''}</p>

          <p>OCR saves Chinese subtitles first. Words/pinyin and sentence translation are prepared separately afterwards. No completion-time estimate is shown.</p>
          <p>OCR calls: {job.metrics.ocr_calls} · Reused sampled frames: {job.metrics.reused_frames} · Extra timing frames: {job.metrics.refinement_frames ?? 0}. Reuse counts do not measure time saved.</p>
          <p data-testid="ocr-device">Requested: {job.execution?.requested_backend ?? job.settings.performance?.backend ?? 'cpu'} · Actual: {job.execution?.actual_backend ?? (activeJob(job) ? 'initializing' : job.status === 'failed' ? 'unavailable' : 'original CPU')} {job.execution?.threads ? `(${job.execution.threads} threads)` : ''} · Fallback: {job.execution?.fallback ? 'yes' : 'none'}</p>
          {job.execution?.stages && <p>{Object.entries(job.execution.stages).map(([key, value]) => `${key}: ${String(value)}`).join(' · ')}</p>}
          <details><summary>OCR model and runtime identity</summary><p className="ocr-identity">{job.engine_version}</p></details>
          {job.error && <p className="error-text">{job.error}</p>}
          {job.status === 'cancelled' && <p>The previous completed transcript is preserved. Cancellation is checked between frames and after in-flight inference.</p>}
          </details>
          {job.status === 'failed' && document?.analysis && <p className="correction-notice">Export corrections before retrying with a new transcript.</p>}
          {job.status === 'failed' && <button className="text-action" disabled={busy} onClick={() => void analyze(true)}>Try analysis again</button>}
        </div>}

      {error && <div className="compact-error" role="alert">Action could not be completed.<details key={error}><summary>View error details</summary><p>{error}</p></details></div>}
      <details className="keyboard-help"><summary>Keyboard shortcuts</summary><p><kbd>Space</kbd> / <kbd>K</kbd> play or pause <span>·</span> <kbd>←</kbd> <kbd>→</kbd> seek 5 seconds <span>·</span> <kbd>M</kbd> mute <span>·</span> <kbd>F</kbd> fullscreen. Focus the crop rectangle and use arrow keys to move it; Shift moves faster.</p></details>
    </section>
    <Transcript library={library} document={document} currentTime={time} seek={seek} save={saveSegment} remove={removeSegment}
      learning={learning} onWord={selectWord} selection={selection} dictionary={dictionary} dictionaryError={dictionaryError}
      vocabulary={vocabulary} saveWord={async (word, status, notes) => {
        const saved = await api.saveWord(word, status, notes);
        if (mounted.current) setVocabulary((words) => [saved, ...words.filter((item) => item.id !== saved.id)]);
      }} deleteWord={async (id) => { await api.deleteWord(id); if (mounted.current) setVocabulary((words) => words.filter((item) => item.id !== id)); }}
      saveTranslation={async (segment, text) => { if (document?.analysis) { const result = await api.editTranslation(video.id, document.analysis.id, segment, text, appearance.settings.sentence_language ?? "vi"); if (mounted.current && result.video_id === video.id && result.target_language === currentLanguage.current) setLearning(result); } }}
      retryTranslation={async () => { try { const result = await api.retryLearning(video.id, appearance.settings.sentence_language ?? "vi"); if (mounted.current && result.target_language === currentLanguage.current) { setLearning(result); setLanguageRetry((value) => value + 1); } } catch (cause) { if (mounted.current) setError((cause as Error).message); } }} />
  </div>;
}
