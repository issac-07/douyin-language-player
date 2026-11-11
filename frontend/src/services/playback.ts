export const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 2] as const;

export function formatTime(seconds: number): string {
  const total = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor(total / 60) % 60;
  return `${hours ? `${hours}:${String(minutes).padStart(2, '0')}` : Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

export function clampSeek(time: number, duration: number): number {
  return Math.max(0, Math.min(time, Number.isFinite(duration) ? duration : 0));
}

export function formatSubtitleTime(seconds: number): string {
  const milliseconds = Math.max(0, Math.round((Number.isFinite(seconds) ? seconds : 0) * 1000));
  return `${formatTime(Math.floor(milliseconds / 1000))}.${String(milliseconds % 1000).padStart(3, '0')}`;
}

type TimedSegment = { start: number; end: number } | { start_time: number; end_time: number };
export function activeSubtitle<T extends TimedSegment>(segments: T[], currentTime: number): T | undefined {
  return segments.find((segment) => {
    const start = 'start_time' in segment ? segment.start_time : segment.start;
    const end = 'end_time' in segment ? segment.end_time : segment.end;
    return start <= currentTime && currentTime < end;
  });
}
