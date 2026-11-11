import type { ProcessingSettings } from '../types';
export type ROI = ProcessingSettings['roi'];
export interface Point { x: number; y: number }
export type DragMode = 'draw' | 'move' | 'nw' | 'ne' | 'sw' | 'se';
const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));

export function containRect(width: number, height: number, videoWidth: number, videoHeight: number) {
  const scale = Math.min(width / videoWidth, height / videoHeight);
  const w = videoWidth * scale, h = videoHeight * scale;
  return { left: (width - w) / 2, top: (height - h) / 2, width: w, height: h };
}

export function updateROI(initial: ROI, origin: Point, point: Point, mode: DragMode): ROI {
  const dx = point.x - origin.x, dy = point.y - origin.y;
  if (mode === 'move') return { ...initial, x: clamp(initial.x + dx, 0, 1 - initial.width), y: clamp(initial.y + dy, 0, 1 - initial.height) };
  let left = initial.x, top = initial.y, right = initial.x + initial.width, bottom = initial.y + initial.height;
  if (mode === 'draw') {
    left = clamp(Math.min(origin.x, point.x), 0, 0.98); top = clamp(Math.min(origin.y, point.y), 0, 0.98);
    right = clamp(Math.max(origin.x, point.x), left + 0.02); bottom = clamp(Math.max(origin.y, point.y), top + 0.02);
  } else {
    if (mode.includes('w')) left = clamp(initial.x + dx, 0, right - 0.02);
    if (mode.includes('e')) right = clamp(initial.x + initial.width + dx, left + 0.02);
    if (mode.includes('n')) top = clamp(initial.y + dy, 0, bottom - 0.02);
    if (mode.includes('s')) bottom = clamp(initial.y + initial.height + dy, top + 0.02);
  }
  return { x: left, y: top, width: right - left, height: bottom - top };
}
