import { useEffect, useRef, useState, type RefObject } from 'react';
import type { SubtitleSegment, Video } from '../types';
import { activeSubtitle, clampSeek, formatTime, PLAYBACK_RATES } from '../services/playback';
import { Icon } from './Icon';

export function VideoPlayer({ video, segments = [], mediaRef, onTimeChange }: {
  video: Video; segments?: SubtitleSegment[]; mediaRef?: RefObject<HTMLVideoElement | null>; onTimeChange?: (time: number) => void;
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
  const [showSubtitles, setShowSubtitles] = useState(true);
  const active = activeSubtitle(segments, time);

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
      else await container.current?.requestFullscreen();
    } catch { setError('Fullscreen is unavailable in this browser window.'); }
  };

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      if (target.closest('input, select, textarea, button, [contenteditable="true"]') || event.ctrlKey || event.metaKey || event.altKey) return;
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
    <div className="video-stage">
      <video
        ref={element} src={video.media_url} preload="metadata" playsInline aria-label={video.original_name}
        onLoadedMetadata={(event) => { setDuration(event.currentTarget.duration); setReady(true); }}
        onTimeUpdate={(event) => { setTime(event.currentTarget.currentTime); onTimeChange?.(event.currentTarget.currentTime); }}
        onSeeked={(event) => { setTime(event.currentTarget.currentTime); onTimeChange?.(event.currentTarget.currentTime); }}
        onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
        onVolumeChange={(event) => { setVolume(event.currentTarget.volume); setMuted(event.currentTarget.muted); }}
        onError={() => { setReady(false); setError('The browser could not load this video. Reimport if the file is missing; for an unsupported codec, convert a copy to H.264 video and AAC audio (see README).'); }}
        onClick={() => void togglePlay()}
      />
      {!playing && ready && !error && <button className="center-play" aria-label="Start playback" onClick={() => void togglePlay()}><Icon name="play" size={30} /></button>}
      {!ready && !error && <span className="loading-media" role="status">Loading video…</span>}
      <span className="video-badge">LOCAL MP4</span>
      {showSubtitles && active && <div className="subtitle-overlay" data-testid="active-subtitle" lang="zh">{active.text}</div>}
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
        {segments.length > 0 && <button className="icon-button" aria-label="Show extracted subtitles" aria-pressed={showSubtitles} onClick={() => setShowSubtitles(!showSubtitles)}><Icon name="captions" /></button>}
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
    </div>
  </div>;
}
