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

// Transcript reading cursor intentionally holds through a gap; video captions use activeSubtitle.
export function transcriptSubtitle<T extends {start_time:number}>(segments:T[], currentTime:number):T|undefined {
 return segments.reduce<T|undefined>((latest,segment)=>segment.start_time<=currentTime && (!latest || segment.start_time>=latest.start_time)?segment:latest,undefined);
}

// Browser media timestamps can round a decimal boundary down by a fraction of a microsecond.
export function subtitleMediaTime(time:number,segments:{start_time:number}[]):number {
 return segments.find(segment=>Math.abs(segment.start_time-time)<0.000001)?.start_time??time;
}

export function formatDuration(seconds: number): string {
  const total = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor(total / 60) % 60;
  const rest = total % 60;
  return hours ? `${hours}h${minutes}m${rest}s` : total >= 60 ? `${minutes}m${rest}s` : `${rest}s`;
}

export function translationModelLabel(identity: string | null | undefined): string {
  if (identity?.includes('Hy-MT2-7B')) return 'Hy-MT2 7B Q4_K_M';
  if (identity?.includes('Hy-MT2-1.8B')) return 'Hy-MT2 1.8B Q8';
  if (identity?.includes('opus-mt')) return 'OPUS / Marian (original)';
  return 'Local model';
}
