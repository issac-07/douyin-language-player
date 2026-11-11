import { describe, expect, it } from 'vitest';
import { containRect, updateROI } from './roi';
import { formatSubtitleTime } from './playback';

describe('OCR region mapping', () => {
  it('shows sampled subtitle boundaries with millisecond precision', () => {
    expect(formatSubtitleTime(.5)).toBe('0:00.500');
    expect(formatSubtitleTime(59.9996)).toBe('1:00.000');
    expect(formatSubtitleTime(125.25)).toBe('2:05.250');
  });
  it('excludes pillarboxing for a portrait video in a wide player', () => {
    expect(containRect(800, 400, 360, 640)).toEqual({ left: 287.5, top: 0, width: 225, height: 400 });
  });
  it('excludes letterboxing for a landscape video in a tall player', () => {
    expect(containRect(400, 400, 1920, 1080)).toEqual({ left: 0, top: 87.5, width: 400, height: 225 });
  });
  it('moves without changing size and clamps all edges', () => {
    expect(updateROI({ x: .1, y: .5, width: .8, height: .3 }, { x: 0, y: 0 }, { x: -1, y: 1 }, 'move')).toEqual({ x: 0, y: .7, width: .8, height: .3 });
  });
  it('draws in either direction and prevents zero-size rectangles', () => {
    const roi = updateROI({ x: 0, y: 0, width: 1, height: 1 }, { x: .8, y: .9 }, { x: .2, y: .6 }, 'draw');
    expect(roi.x).toBe(.2); expect(roi.width).toBeCloseTo(.6); expect(roi.height).toBeCloseTo(.3);
    const tiny = updateROI(roi, { x: 1, y: 1 }, { x: 1, y: 1 }, 'draw');
    expect(tiny.x + tiny.width).toBeLessThanOrEqual(1);
    expect(tiny.width).toBeCloseTo(.02);
  });
  it('resizes a corner without crossing the opposite corner or video edge', () => {
    const result = updateROI({ x: .1, y: .5, width: .8, height: .3 }, { x: 0, y: 0 }, { x: 2, y: 2 }, 'se');
    expect(result.x + result.width).toBe(1);
    expect(result.y + result.height).toBe(1);
  });
});
