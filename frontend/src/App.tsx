import { useEffect, useRef, useState } from 'react';
import { StoragePanel } from './components/StoragePanel';
import { Icon } from './components/Icon';
import { OCRWorkspace } from './components/OCRWorkspace';
import { api, uploadVideo } from './services/api';
import { VocabularyPage } from './components/VocabularyPage';
import { VideoLibrary } from './components/VideoLibrary';
import type { Health, Video } from './types';
import { usePlayerSettings } from './hooks/usePlayerSettings';
import { DouyinImportPanel } from './components/DouyinImportPanel';

export default function App() {
  const appearance = usePlayerSettings();
  const [theme,setTheme]=useState<'light'|'dark'>(()=>document.documentElement.dataset.theme==='dark'?'dark':'light');
  const [openImport,setOpenImport]=useState(0);
  const [vocabularyOpen,setVocabularyOpen]=useState(()=>window.location.hash==='#vocabulary');
  const [vocabularyRevision,setVocabularyRevision]=useState(0);
  const watchScroll=useRef(0);
  const previousFocus=useRef<HTMLElement|null>(null);
  const enteredFromWatch=useRef(false);
  const importScrollRequested=useRef(false);
  const navigateBook=()=>{watchScroll.current=window.scrollY;previousFocus.current=document.activeElement as HTMLElement;document.querySelector('video')?.pause();enteredFromWatch.current=true;history.pushState(null,'','#vocabulary');setVocabularyOpen(true);window.scrollTo(0,0);};
  const returnToWatch=()=>{if(enteredFromWatch.current){enteredFromWatch.current=false;history.back();}else{history.replaceState(null,'',location.pathname+location.search);setVocabularyOpen(false);}};
  useEffect(()=>{const changed=()=>setVocabularyOpen(location.hash==='#vocabulary');addEventListener('popstate',changed);addEventListener('hashchange',changed);return()=>{removeEventListener('popstate',changed);removeEventListener('hashchange',changed);};},[]);
  useEffect(()=>{if(vocabularyOpen){document.querySelector('video')?.pause();return;}setVocabularyRevision(v=>v+1);const frame=requestAnimationFrame(()=>{window.scrollTo(0,watchScroll.current);previousFocus.current?.focus({preventScroll:true});});return()=>cancelAnimationFrame(frame);},[vocabularyOpen]);
  useEffect(()=>{if(vocabularyOpen || !importScrollRequested.current)return;const frame=requestAnimationFrame(()=>{document.getElementById('import-zone')?.scrollIntoView({block:'center'});importScrollRequested.current=false;});return()=>cancelAnimationFrame(frame);},[openImport,vocabularyOpen]);
  useEffect(()=>{document.documentElement.dataset.theme=theme;try{localStorage.setItem('dlp-theme',theme);}catch{}},[theme]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [selected, setSelected] = useState<Video | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const uploadLock = useRef(false);
  const libraryRevision = useRef(0);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = async () => {
    const revision = libraryRevision.current;
    setLoading(true); setError('');
    try {
      const [status, library] = await Promise.all([api.health(), api.videos()]);
      setHealth(status);
      if (revision !== libraryRevision.current) return;
      setVideos(library);
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
      libraryRevision.current += 1;
      setVideos((current) => [result.video, ...current.filter((video) => video.id !== result.video.id)]);
      setSelected(result.video);
      setNotice(result.reused ? 'Opened the existing local copy. No duplicate was stored.' : 'Video imported and saved to your local library.');
    } catch (cause) { setError((cause as Error).message); }
    finally { uploadLock.current = false; setUploading(false); if (fileInput.current) fileInput.current.value = ''; }
  };

  const deleteSelected = async () => {
    if (!selected || deleting || uploading) return;
    const target = selected;
    if (!window.confirm(`Delete "${target.title ?? target.original_name}" from this library? Its cached MP4, OCR results and subtitle corrections will be removed. Your original source file and saved vocabulary will be kept.`)) return;
    setDeleting(true); setError(''); setNotice('');
    try {
      const result = await api.deleteVideo(target.id);
      libraryRevision.current += 1;
      const remaining = videos.filter((video) => video.id !== target.id);
      setVideos(remaining); setSelected(remaining[0] ?? null);
      try { localStorage.removeItem('dlp-last-video'); } catch { /* Optional storage. */ }
      setNotice(result.media_cleanup_pending ? 'Video removed. A locked cache file still needs cleanup after playback stops.' : 'Video deleted from the library. Original source file and saved vocabulary were kept.');
    } catch (cause) { setError((cause as Error).message); }
    finally { setDeleting(false); }
  };

  const library=<VideoLibrary videos={videos} selected={selected?.id} onSelect={setSelected} refresh={()=>void load()} loading={loading}/>;
  return <div className="app-shell v2-app"><div className="main-shell">
    <header className="topbar"><a className="v2-brand" href="/" aria-label="Douyin Language Player home"><span aria-hidden="true">▷</span> Douyin Language Player</a><div id="toolbar-languages" hidden={vocabularyOpen}/><div className="toolbar-actions"><button className="primary-button" disabled={uploading} onClick={()=>{importScrollRequested.current=true;if(vocabularyOpen)returnToWatch();setOpenImport(v=>v+1);}}>+ Add video</button><button className="theme-switch" type="button" role="switch" aria-label="Dark mode" aria-checked={theme==='dark'} onClick={()=>setTheme(theme==='light'?'dark':'light')}><svg aria-hidden="true" viewBox="0 0 24 24" className="theme-sun"><circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/></svg><svg aria-hidden="true" viewBox="0 0 24 24" className="theme-moon"><path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/></svg><span className="theme-switch-knob"/></button><button aria-label="Saved words" aria-current={vocabularyOpen?'page':undefined} onClick={()=>vocabularyOpen?returnToWatch():navigateBook()}>▤ Vocabulary</button><span className="phase-badge">V2.1 UI</span></div></header>
    <main>
      {vocabularyOpen && <VocabularyPage onBack={returnToWatch} language={appearance.settings.dictionary_language??'en'}/>}
      <div className="watch-surface" hidden={vocabularyOpen}>
        <input ref={fileInput} id="video-file" className="sr-only" type="file" accept=".mp4,video/mp4" aria-label="Choose MP4 file" disabled={uploading} onChange={(event) => void importFile(event.target.files?.[0])} />
        {error && <div className="alert error" role="alert">Action could not be completed.<details key={error}><summary>View error details</summary><p>{error}</p></details><button className="text-button" onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
        {notice && <div className="alert success" role="status"><Icon name="check" size={16} /><span>{notice}</span><button className="text-button" aria-label="Dismiss notification" onClick={() => setNotice('')}>×</button></div>}
        {health && !health.ffprobe_available && <div className="alert error" role="alert">FFprobe is missing. Add FFmpeg to PATH and restart the backend before importing.</div>}
        {uploading && <div className="upload-progress" role="status"><span>{progress < 100 ? `Uploading your video · ${progress}%` : 'Upload received · inspecting the MP4…'}</span><progress max="100" value={progress} /></div>}

        {selected ? <OCRWorkspace libraryActions={<button className="text-action danger" disabled={deleting || uploading} onClick={() => void deleteSelected()}>{deleting ? 'Deleting…' : 'Delete selected video'}</button>} library={library} vocabularyRevision={vocabularyRevision} key={selected.id} video={selected} appearance={appearance} /> : <div className="workspace-grid">
          <section className="viewing-column" aria-label="Video workspace">
            <div className={`empty-player ${dragging ? 'dragging' : ''}`} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); void importFile(event.dataTransfer.files[0]); }}>
              <div className="empty-art" aria-hidden="true"><div className="art-frame back-frame" /><div className="art-frame"><span>字</span><div className="art-lines"><i /><i /><i /></div><div className="art-play"><Icon name="play" size={23} /></div></div><span className="art-spark">✦</span></div>
              <span className="eyebrow">YOUR VIDEOS. YOUR PACE.</span><h2>Bring a little Mandarin<br />into your day.</h2><p>Drop a local MP4 here to start watching.<br />Your original video and audio stay intact.</p>
              <button className="primary-button" onClick={() => fileInput.current?.click()} disabled={uploading}><Icon name="upload" size={18} /> Choose an MP4</button><small>MP4 · {health ? `${Math.round(health.max_upload_bytes / 1024 / 1024)} MB maximum` : 'Local files'} · No account needed</small>
            </div>
          </section>

          <aside className="learning-column"><section className="transcript-panel"><h2>Transcript</h2><p>Import a video to start learning.</p></section>{library}</aside>
        </div>}
        <div id="import-zone" className="below-video-import"><DouyinImportPanel openToken={openImport} collapseToken={selected?.id} localBusy={uploading} onLocal={() => fileInput.current?.click()} onImported={(video, reused) => {
          libraryRevision.current += 1;
          setVideos((current) => [video, ...current.filter((item) => item.id !== video.id)]);
          setSelected(video); setNotice(reused ? 'Opened the existing local copy. Cached analysis remains available.' : 'Douyin video imported into your local library.');
        }} /></div>
        <StoragePanel />
        <footer className="workspace-footer"><span>Built for focused, everyday learning.</span><span>Local video · Chinese OCR · Mandarin · English / Vietnamese</span></footer>
      </div>
      </main>
    </div>
  </div>;
}
