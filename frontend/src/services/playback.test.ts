import { describe, expect, it } from 'vitest';
import { activeSubtitle, clampSeek, formatTime, PLAYBACK_RATES } from './playback';
import { errorMessage } from './api';

describe('playback helpers', () => {
  it('formats finite durations and handles unknown metadata', () => {
    expect(formatTime(0)).toBe('0:00');
    expect(formatTime(125.9)).toBe('2:05');
    expect(formatTime(3661)).toBe('1:01:01');
    expect(formatTime(Infinity)).toBe('0:00');
    expect(formatTime(-1)).toBe('0:00');
  });
  it('constrains seeks to actual media bounds', () => {
    expect(clampSeek(-10, 8)).toBe(0);
    expect(clampSeek(20, 8)).toBe(8);
    expect(clampSeek(3, 8)).toBe(3);
    expect(clampSeek(3, NaN)).toBe(0);
  });
  it('exposes all required playback rates', () => {
    expect(PLAYBACK_RATES).toEqual([0.5, 0.75, 1, 1.25, 1.5, 2]);
  });
  it('selects a subtitle from video time with exclusive end boundaries and gaps', () => {
    const segments = [
      { id: '1', start: 1, end: 2, text: '一', confidence: 0.9 },
      { id: '2', start: 3, end: 4, text: '二', confidence: 0.9 },
    ];
    expect(activeSubtitle(segments, 1)?.id).toBe('1');
    expect(activeSubtitle(segments, 2)).toBeUndefined();
    expect(activeSubtitle(segments, 3)?.id).toBe('2');
    expect(activeSubtitle(segments, 0)).toBeUndefined();
    expect(activeSubtitle([], 1)).toBeUndefined();
  });
});

describe('API error messages', () => {
  it('preserves actionable backend errors and validation details', () => {
    expect(errorMessage({ detail: 'Install FFmpeg.' })).toBe('Install FFmpeg.');
    expect(errorMessage({ detail: [{ msg: 'Region is out of bounds' }] })).toBe('Region is out of bounds');
    expect(errorMessage(null)).toContain('backend');
  });
});
