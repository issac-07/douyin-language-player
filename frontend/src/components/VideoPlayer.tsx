import { useEffect, useRef, useState, type RefObject, type ReactNode } from 'react';
import type { LearningDocument, PlayerSettings, ProcessingSettings, SubtitleSegment, Video, WordToken } from '../types';
import { activeSubtitle, clampSeek, formatTime, PLAYBACK_RATES } from '../services/playback';
import { Icon } from './Icon';
import { InteractiveSubtitleOverlay } from './InteractiveSubtitleOverlay';
import { SubtitleAppearance } from './SubtitleAppearance';
import { DEFAULT_PLAYER_SETTINGS } from '../hooks/usePlayerSettings';

export function VideoPlayer({ video, segments = [], mediaRef, onTimeChange, learning, settings = DEFAULT_PLAYER_SETTINGS, updateSettings = () => {}, settingsStatus = '', roi = { x: .05, y: .6, width: .9, height: .3 }, onWord = () => {}, fullscreenTarget, libraryActions }: {
  libraryActions?: ReactNode; video: Video; segments?: SubtitleSegment[]; mediaRef?: RefObject<HTMLVideoElement | null>; onTimeChange?: (time: number) => void;
  learning?: LearningDocument | null; settings?: PlayerSettings; updateSettings?: (settings: PlayerSettings) => void; settingsStatus?: string;
  roi?: ProcessingSettings['roi']; onWord?: (token: WordToken) => void; fullscreenTarget?: RefObject<HTMLDivElement | null>;
}) {
  const ownRef = useRef<HTMLVideoElement>(null);
  const element = mediaRef ?? ownRef;
  const container = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(video.duration);
  const [rate, setRate] = useState(1);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState('');
  const stage = useRef<HTMLDivElement>(null);
  const [stageSize, setStageSize] = useState({ width: 0, height: 0 });
  const [appearanceOpen, setAppearanceOpen] = useState(false);
  const previous = useRef<SubtitleSegment | undefined>(undefined);
  const seeking = useRef(false);
  const displayedSegment = useRef<string | undefined>(undefined);
  const lastUiRefresh = useRef(0);
  const active = activeSubtitle(segments, time);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setStageSize({ width: entry.contentRect.width, height: entry.contentRect.height }));
    if (stage.current) observer.observe(stage.current);
    return () => observer.disconnect();
  }, []);
  const updateTime = (media: HTMLVideoElement, allowPause = true) => {
    const value = media.currentTime;
    if (allowPause && settings.auto_pause && !media.paused && !seeking.current && previous.current && value >= previous.current.end_time && value < previous.current.end_time + 1) {
      media.pause(); media.currentTime = previous.current.end_time;
    }
    previous.current = activeSubtitle(segments, media.currentTime);
    const nextId = previous.current?.id;
    const now = performance.now();
    // Inspect every presented frame, but avoid rebuilding a long transcript on
    // every frame while the active sentence stays the same.
    if (allowPause && nextId === displayedSegment.current && now - lastUiRefresh.current < 100) return;
    displayedSegment.current = nextId;
    lastUiRefresh.current = now;
    setTime(media.currentTime); onTimeChange?.(media.currentTime);
  };
  const frameUpdate = useRef(updateTime);
  frameUpdate.current = updateTime;
  useEffect(() => {
    const media = element.current;
    if (!media) return;
    let stopped = false;
    let handle = 0;
    const native = typeof media.requestVideoFrameCallback === 'function';
    const tick = () => {
      if (stopped) return;
      if (!media.paused && !media.seeking) frameUpdate.current(media);
      handle = native ? media.requestVideoFrameCallback(tick) : requestAnimationFrame(tick);
    };
    handle = native ? media.requestVideoFrameCallback(tick) : requestAnimationFrame(tick);
    return () => {
      stopped = true;
      if (native) media.cancelVideoFrameCallback(handle);
      else cancelAnimationFrame(handle);
    };
  }, [video.id]);

  const seek = (value: number) => {
    const media = element.current;
    if (media && ready) {
      media.currentTime = clampSeek(value, media.duration);
      setTime(media.currentTime);
      onTimeChange?.(media.currentTime);
    }
  };

  const togglePlay = async () => {
    const media = element.current;
    if (!media || !ready) return;
    if (!media.paused) media.pause();
    else {
      try { await media.play(); setError(''); }
      catch { setError('Playback could not start. Try again, or convert a copy to H.264/AAC (see README).'); }
    }
  };

  const fullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await (fullscreenTarget?.current ?? container.current)?.requestFullscreen();
    } catch { setError('Fullscreen is unavailable in this browser window.'); }
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (container.current?.closest('[hidden]')) return;
      const target = event.target as HTMLElement;
      if (event.defaultPrevented || target.closest('input, select, textarea, button, summary, [contenteditable="true"]') || event.ctrlKey || event.metaKey || event.altKey) return;
      if (![' ', 'k', 'ArrowLeft', 'ArrowRight', 'm', 'f'].includes(event.key)) return;
      event.preventDefault();
      const media = element.current;
      if (!media) return;
      if (event.key === ' ' || event.key === 'k') void togglePlay();
      if (event.key === 'ArrowLeft') seek(media.currentTime - 5);
      if (event.key === 'ArrowRight') seek(media.currentTime + 5);
      if (event.key === 'm') { media.muted = !media.muted; setMuted(media.muted); }
      if (event.key === 'f') void fullscreen();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  });

  return <div className="player" ref={container}>
    <div className="video-stage" ref={stage}>
      <video
        ref={element} src={video.media_url} preload="metadata" playsInline aria-label={video.original_name}
        onLoadedMetadata={(event) => { setDuration(event.currentTarget.duration); setReady(true); }}
        onTimeUpdate={(event) => updateTime(event.currentTarget)}
        onSeeking={() => { seeking.current = true; }}
        onSeeked={(event) => { seeking.current = false; updateTime(event.currentTarget, false); }}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onVolumeChange={(event) => { setVolume(event.currentTarget.volume); setMuted(event.currentTarget.muted); }}
        onError={() => { setReady(false); setError('The browser could not load this video. Reimport if the file is missing; for an unsupported codec, convert a copy to H.264 video and AAC audio (see README).'); }}
        onClick={() => void togglePlay()}
      />
      {!playing && ready && !error && (!active || !settings.show_all) && <button className="center-play" aria-label="Start playback" onClick={() => void togglePlay()}><Icon name="play" size={30} /></button>}
      {!ready && !error && <span className="loading-media" role="status">Loading video…</span>}
      <span className="video-badge">LOCAL MP4</span>
      {active && <InteractiveSubtitleOverlay key={active.id} active={active} language={learning?.segments.find((item) => item.id === active.id)} settings={settings} roi={roi} width={video.width} height={video.height} stageWidth={stageSize.width} stageHeight={stageSize.height} onWord={onWord} />}
    </div>
    {error && <div className="player-error" role="alert">{error}</div>}
    <div className="playback-controls">
      <label className="sr-only" htmlFor="seek">Seek video</label>
      <input id="seek" className="seek-slider" type="range" min="0" max={duration || 0} step="0.05" value={Math.min(time, duration)} disabled={!ready} onChange={(event) => seek(Number(event.target.value))} aria-valuetext={`${formatTime(time)} of ${formatTime(duration)}`} />
      <div className="control-row">
        <button className="icon-button" aria-label={playing ? 'Pause' : 'Play'} title="Play / pause (Space)" disabled={!ready} onClick={() => void togglePlay()}><Icon name={playing ? 'pause' : 'play'} /></button>
        <button className="icon-button skip" aria-label="Back 5 seconds" title="Back 5 seconds (←)" disabled={!ready} onClick={() => seek(time - 5)}><Icon name="back" /></button>
        <button className="icon-button skip" aria-label="Forward 5 seconds" title="Forward 5 seconds (→)" disabled={!ready} onClick={() => seek(time + 5)}><Icon name="forward" /></button>
        <span className="timecode" aria-live="off">{formatTime(time)} <span>/ {formatTime(duration)}</span></span>
        <div className="control-spacer" />
        {segments.length > 0 && <button className="icon-button" aria-label="Show extracted subtitles" aria-pressed={settings.show_all} onClick={() => updateSettings({ ...settings, show_all: !settings.show_all })}><Icon name="captions" /></button>}
        <button className="icon-button" aria-label="Subtitle appearance" aria-expanded={appearanceOpen} onClick={() => setAppearanceOpen(!appearanceOpen)}><Icon name="settings" /></button>
        <button className="icon-button" aria-label={muted ? 'Unmute' : 'Mute'} title="Mute (M)" onClick={() => { if (element.current) { element.current.muted = !muted; setMuted(!muted); } }}><Icon name={muted || volume === 0 ? 'mute' : 'volume'} /></button>
        <label className="sr-only" htmlFor="volume">Volume</label>
        <input id="volume" className="volume-slider" type="range" min="0" max="1" step="0.05" value={muted ? 0 : volume} onChange={(event) => {
          if (element.current) { element.current.volume = Number(event.target.value); element.current.muted = false; }
        }} />
        <label className="sr-only" htmlFor="speed">Playback speed</label>
        <select id="speed" value={rate} onChange={(event) => { const next = Number(event.target.value); setRate(next); if (element.current) element.current.playbackRate = next; }}>
          {PLAYBACK_RATES.map((value) => <option key={value} value={value}>{value}×</option>)}
        </select>
        <button className="icon-button" aria-label="Fullscreen" title="Fullscreen (F)" onClick={() => void fullscreen()}><Icon name="expand" /></button>
      </div>
      {libraryActions && <div className="player-library-actions">{libraryActions}</div>}
    </div>
    {appearanceOpen && <SubtitleAppearance settings={settings} update={updateSettings} status={settingsStatus} close={() => setAppearanceOpen(false)} />}
  </div>;
}
