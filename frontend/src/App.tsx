import { useEffect, useRef, useState } from 'react';
import { Icon } from './components/Icon';
import { OCRWorkspace } from './components/OCRWorkspace';
import { api, uploadVideo } from './services/api';
import { formatTime } from './services/playback';
import type { Health, Video } from './types';
import { usePlayerSettings } from './hooks/usePlayerSettings';
import { DouyinImportPanel } from './components/DouyinImportPanel';

export default function App() {
  const appearance = usePlayerSettings();
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<Video | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const uploadLock = useRef(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [tab, setTab] = useState<'transcript' | 'vocabulary'>('transcript');
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [status, library] = await Promise.all([api.health(), api.videos()]);
      setHealth(status); setVideos(library);
      let remembered: string | null = null;
      try { remembered = localStorage.getItem('dlp-last-video'); } catch { /* Browser storage can be disabled. */ }
      setSelected((current) => library.find((video) => video.id === current?.id) ?? library.find((video) => video.id === remembered) ?? library[0] ?? null);
    } catch (cause) { setError((cause as Error).message); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  useEffect(() => { if (selected) { try { localStorage.setItem('dlp-last-video', selected.id); } catch { /* Library still works without browser storage. */ } } }, [selected?.id]);

  const importFile = async (file?: File) => {
    if (!file || uploadLock.current) return;
    setError(''); setNotice('');
    if (!file.name.toLowerCase().endsWith('.mp4')) { setError('Choose an .mp4 video file.'); return; }
    if (file.size === 0) { setError('This file is empty. Choose a readable MP4 video.'); return; }
    if (health && file.size > health.max_upload_bytes) { setError(`This file exceeds the ${Math.round(health.max_upload_bytes / 1024 / 1024)} MB upload limit.`); return; }
    uploadLock.current = true; setUploading(true); setProgress(0);
    try {
      const result = await uploadVideo(file, setProgress);
      setVideos((current) => [result.video, ...current.filter((video) => video.id !== result.video.id)]);
      setSelected(result.video);
      setNotice(result.reused ? 'Opened the existing local copy. No duplicate was stored.' : 'Video imported and saved to your local library.');
    } catch (cause) { setError((cause as Error).message); }
    finally { uploadLock.current = false; setUploading(false); if (fileInput.current) fileInput.current.value = ''; }
  };

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="Douyin Language Player home"><span className="brand-mark">语</span><span>Douyin<span className="brand-sub">LANGUAGE PLAYER</span></span></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <div className="nav-active"><Icon name="film" /> Video library <span>{videos.length}</span></div>
      <button className="primary-button sidebar-import" onClick={() => fileInput.current?.click()} disabled={uploading}><Icon name="upload" size={17} /> Import MP4</button>
      <div className="library-heading"><span>RECENT VIDEOS</span><button className="text-button" onClick={() => void load()} disabled={loading || uploading} aria-label="Refresh library">↻</button></div>
      <div className="recent-list" aria-label="Recent videos">
        {loading && <p className="sidebar-empty">Loading your library…</p>}
        {!loading && videos.length === 0 && <p className="sidebar-empty">Your videos will appear here.<br />Start with a local MP4.</p>}
        {videos.map((video) => <button key={video.id} className={`recent-video ${selected?.id === video.id ? 'selected' : ''}`} onClick={() => setSelected(video)} aria-pressed={selected?.id === video.id}>
          <span className="recent-icon"><Icon name="film" size={19} /></span><span className="recent-info"><strong title={video.title ?? video.original_name}>{video.title ?? video.original_name}</strong><small>{formatTime(video.duration)} · {video.width} × {video.height}{video.imported_from === 'douyin' ? ' · Douyin' : ''}</small></span>
        </button>)}
      </div>
      <div className="local-note"><span className="status-dot" /><span>Local workspace<small>Files stay on this computer.</small></span></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div><span className="muted">Workspace</span><span className="breadcrumb">/</span><span>Player</span></div><span className="phase-badge">PHASE 04 <span>·</span> WATCH & LEARN</span></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow">A LITTLE EVERY DAY</div><h1>Your next conversation<br className="mobile-break" /> starts here.</h1><p>Watch at your own pace. Make room for the words.</p></div><button className="secondary-button heading-import" onClick={() => fileInput.current?.click()} disabled={uploading}><Icon name="upload" size={17} /> Import video</button></div>

        <input ref={fileInput} id="video-file" className="sr-only" type="file" accept=".mp4,video/mp4" aria-label="Choose MP4 file" disabled={uploading} onChange={(event) => void importFile(event.target.files?.[0])} />
        {error && <div className="alert error" role="alert">{error}<button className="text-button" onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
        {notice && <div className="alert success" role="status"><Icon name="check" size={16} />{notice}</div>}
        {health && !health.ffprobe_available && <div className="alert error" role="alert">FFprobe is missing. Add FFmpeg to PATH and restart the backend before importing.</div>}
        {uploading && <div className="upload-progress" role="status"><span>{progress < 100 ? `Uploading your video · ${progress}%` : 'Upload received · inspecting the MP4…'}</span><progress max="100" value={progress} /></div>}

        <DouyinImportPanel localBusy={uploading} onLocal={() => fileInput.current?.click()} onImported={(video, reused) => {
          setVideos((current) => [video, ...current.filter((item) => item.id !== video.id)]);
          setSelected(video); setNotice(reused ? 'Opened the existing local copy. Cached analysis remains available.' : 'Douyin video imported into your local library.');
        }} />
        {selected ? <OCRWorkspace key={selected.id} video={selected} appearance={appearance} /> : <div className="workspace-grid">
          <section className="viewing-column" aria-label="Video workspace">
            <div className={`empty-player ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); void importFile(event.dataTransfer.files[0]); }}>
              <div className="empty-art" aria-hidden="true"><div className="art-frame back-frame" /><div className="art-frame"><span>字</span><div className="art-lines"><i /><i /><i /></div><div className="art-play"><Icon name="play" size={23} /></div></div><span className="art-spark">✦</span></div>
              <span className="eyebrow">YOUR VIDEOS. YOUR PACE.</span><h2>Bring a little Mandarin<br />into your day.</h2><p>Drop a local MP4 here to start watching.<br />Your original video and audio stay intact.</p>
              <button className="primary-button" onClick={() => fileInput.current?.click()} disabled={uploading}><Icon name="upload" size={18} /> Choose an MP4</button><small>MP4 · {health ? `${Math.round(health.max_upload_bytes / 1024 / 1024)} MB maximum` : 'Local files'} · No account needed</small>
            </div>
          </section>

          <aside className="learning-panel" aria-label="Learning tools">
            <div className="panel-tabs" role="tablist" aria-label="Learning panel"><button id="transcript-tab" role="tab" aria-controls="learning-content" aria-selected={tab === 'transcript'} onClick={() => setTab('transcript')}><Icon name="captions" size={17} /> Transcript</button><button id="vocabulary-tab" role="tab" aria-controls="learning-content" aria-selected={tab === 'vocabulary'} onClick={() => setTab('vocabulary')}><Icon name="book" size={17} /> Vocabulary</button></div>
            <div id="learning-content" role="tabpanel" aria-labelledby={`${tab}-tab`} className="panel-content">
              <span className="panel-counter">{tab === 'transcript' ? 'SUBTITLES' : 'SAVED WORDS'}<span>—</span></span>
              <div className="learning-empty"><span className="empty-tool-icon"><Icon name={tab === 'transcript' ? 'captions' : 'book'} size={28} /></span><h3>{tab === 'transcript' ? 'Every sentence, a small step.' : 'Build your own wordbook.'}</h3><p>{tab === 'transcript' ? 'Import a video, choose its Chinese subtitle region, and analyze it to create your transcript.' : 'Import and analyze a video, then select Chinese words to view definitions and save vocabulary.'}</p></div>
            </div>
            <div className="panel-footnote"><span className="status-dot" />{selected ? 'Video ready for local playback' : 'Import a video to begin'}</div>
          </aside>
        </div>}
        <footer className="workspace-footer"><span>Built for focused, everyday learning.</span><span>Local video · Chinese OCR · Mandarin & Vietnamese</span></footer>
      </main>
    </div>
  </div>;
}
