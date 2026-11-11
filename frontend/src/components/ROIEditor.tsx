import { useEffect, useRef, useState } from 'react';
import type { Video } from '../types';
import { containRect, updateROI, type DragMode, type Point, type ROI } from '../services/roi';

export function ROIEditor({ video, roi, onChange, timestamp }: { video: Video; roi: ROI; onChange: (roi: ROI) => void; timestamp: number }) {
  const host = useRef<HTMLDivElement>(null);
  const [rect, setRect] = useState({ left: 0, top: 0, width: 0, height: 0 });
  const source = `/api/videos/${video.id}/preview?timestamp=${timestamp.toFixed(3)}`;
  const [errorSource, setErrorSource] = useState('');
  const [loadedSource, setLoadedSource] = useState('');
  const error = errorSource === source;
  const loaded = loadedSource === source;
  const drag = useRef<{ origin: Point; initial: ROI; mode: DragMode } | null>(null);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setRect(containRect(entry.contentRect.width, entry.contentRect.height, video.width, video.height)));
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, [video.width, video.height]);

  return <div className="roi-preview" ref={host}>
    <img key={source} src={source} alt="Video frame for selecting the Chinese subtitle region" draggable={false} onLoad={() => { setLoadedSource(source); setErrorSource(''); }} onError={() => setErrorSource(source)} />
    {error && <p className="roi-preview-error" role="alert">Could not load this preview. Choose an earlier time or reimport the video.</p>}
    {!loaded && !error && <p className="roi-preview-error" role="status">Loading preview frame…</p>}
    {loaded && <div className="roi-canvas" data-testid="roi-canvas" style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        const bounds = event.currentTarget.getBoundingClientRect();
        const point = { x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height };
        const target = event.target as HTMLElement;
        const mode = target.dataset.handle as DragMode || (target.closest('.roi-selection') ? 'move' : 'draw');
        drag.current = { origin: point, initial: roi, mode };
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (!drag.current) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        onChange(updateROI(drag.current.initial, drag.current.origin, { x: (event.clientX - bounds.left) / bounds.width, y: (event.clientY - bounds.top) / bounds.height }, drag.current.mode));
      }}
      onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <div className="roi-selection" role="group" aria-label="OCR subtitle region" tabIndex={0}
        style={{ left: `${roi.x * 100}%`, top: `${roi.y * 100}%`, width: `${roi.width * 100}%`, height: `${roi.height * 100}%` }}
        onKeyDown={(event) => {
          if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
          event.preventDefault(); event.stopPropagation();
          const step = event.shiftKey ? 0.05 : 0.01;
          onChange(updateROI(roi, { x: 0, y: 0 }, { x: event.key === 'ArrowLeft' ? -step : event.key === 'ArrowRight' ? step : 0, y: event.key === 'ArrowUp' ? -step : event.key === 'ArrowDown' ? step : 0 }, 'move'));
        }}>
        <span className="roi-label">SUBTITLE REGION</span>
        {(['nw', 'ne', 'sw', 'se'] as const).map((corner) => <span key={corner} data-handle={corner} className={`roi-handle ${corner}`} />)}
      </div>
    </div>}
  </div>;
}
