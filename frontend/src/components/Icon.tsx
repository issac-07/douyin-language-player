type IconName = 'play' | 'pause' | 'upload' | 'film' | 'book' | 'captions' | 'volume' | 'mute' | 'expand' | 'back' | 'forward' | 'check' | 'settings';
const paths: Record<IconName, string> = {
  play: 'm9 5 11 7-11 7Z',
  pause: 'M8 5v14M16 5v14',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5',
  film: 'M4 3h16v18H4ZM4 8h16M4 16h16M8 3v18M16 3v18',
  book: 'M12 5c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1Zm0 0v15',
  captions: 'M3 5h18v14H3Zm4 5H6v4h3m6-4h-3v4h3m3-4h-1v4h1',
  volume: 'm11 4-5 4H2v8h4l5 4Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14',
  mute: 'm11 4-5 4H2v8h4l5 4Zm5 5 5 6m0-6-5 6',
  expand: 'M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5',
  back: 'm11 5-7 7 7 7M4 12h15',
  forward: 'm13 5 7 7-7 7M20 12H5',
  check: 'm5 12 4 4L20 5',
  settings: 'M4 7h16M4 17h16M8 4v6m8 4v6',
};

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
