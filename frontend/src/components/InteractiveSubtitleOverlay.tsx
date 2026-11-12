import { useLayoutEffect, useRef, useState, type CSSProperties } from 'react';
import type { LearningSegment, PlayerSettings, ProcessingSettings, SubtitleSegment, WordToken } from '../types';
import { containRect } from '../services/roi';

export function InteractiveSubtitleOverlay({ active, language, settings, roi, width, height, stageWidth, stageHeight, onWord }: {
  active: SubtitleSegment; language?: LearningSegment; settings: PlayerSettings; roi: ProcessingSettings['roi'];
  width: number; height: number; stageWidth: number; stageHeight: number; onWord: (token: WordToken) => void;
}) {
  const box = containRect(stageWidth, stageHeight, width, height);
  const content = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [fit, setFit] = useState(1);
  const availableHeight = Math.max(24, Math.min(box.height - 8, box.height * (roi.y + settings.vertical_offset / 100) - 12));
  useLayoutEffect(() => { setFit(1); }, [active.id, box.width, box.height, settings.font_size, settings.pinyin_size, settings.translation_size, settings.vertical_offset, settings.mode, settings.show_pinyin, settings.show_chinese, settings.show_translation]);
  useLayoutEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      const width = entry.borderBoxSize[0]?.inlineSize ?? entry.contentRect.width;
      const height = entry.borderBoxSize[0]?.blockSize ?? entry.contentRect.height;
      setSize({ width, height });
      const naturalHeight = Math.max(height, content.current?.scrollHeight ?? 0);
      if (naturalHeight > availableHeight + 1) setFit((scale) => Math.max(.35, scale * availableHeight / naturalHeight * .97));
    });
    if (content.current) observer.observe(content.current);
    return () => observer.disconnect();
  }, [box.width, box.height, settings.show_all, availableHeight]);
  const hasLanguage = language?.text === active.text && language.revision === active.revision;
  const tokens = hasLanguage ? language.tokens : [];
  const chinese = settings.show_chinese && settings.mode === 'interactive';
  const factor = Math.min(1, Math.max(.85, box.width / 360)) * fit;
  const x = Math.min(box.width - size.width / 2 - 4, Math.max(size.width / 2 + 4, box.width * (.5 + settings.horizontal_offset / 100)));
  const bottom = Math.min(box.height - 4, Math.max(size.height + 4, box.height * (roi.y + settings.vertical_offset / 100) - 8));
  const style = {
    left: x, top: bottom, color: settings.text_color, backgroundColor: `rgba(0,0,0,${settings.background_opacity})`,
    textShadow: settings.text_shadow ? '0 1px 2px #000, 1px 1px 3px #000' : 'none',
    '--chinese-size': `${settings.font_size * factor}px`, '--pinyin-size': `${settings.pinyin_size * factor}px`, '--translation-size': `${settings.translation_size * factor}px`,
  } as CSSProperties;
  if (!settings.show_all || (!settings.show_pinyin && !chinese && !settings.show_translation)) return null;
  return <div className="subtitle-image-bounds" data-testid="subtitle-image-bounds" style={{ left: box.left, top: box.top, width: box.width, height: box.height }}>
    <div className="interactive-subtitle-overlay" data-testid="interactive-overlay" data-translation-status={hasLanguage ? language.translation.status : 'pending'} data-roi-top={box.height * roi.y} ref={content} style={style}>
      {hasLanguage ? (chinese || settings.show_pinyin) && <div className="subtitle-word-line" lang="zh">{tokens.map((token) => token.selectable ? <button key={token.start} className={`subtitle-word ${chinese ? '' : 'pinyin-only'}`} aria-label={`Look up ${token.text}`} disabled={!chinese} onClick={(event) => { event.stopPropagation(); onWord(token); }}>
        {settings.show_pinyin && <span className="word-pinyin" lang="zh-Latn" data-testid="word-pinyin">{token.pinyin}</span>}
        {chinese && <span className="word-chinese" data-word-text>{token.text}</span>}
      </button> : chinese && <span key={token.start} className="subtitle-punctuation">{token.text}</span>)}</div> : chinese && <div className="subtitle-fallback" lang="zh">{active.text}</div>}
      {settings.show_translation && <div className="subtitle-vietnamese" lang={settings.sentence_language ?? "vi"} data-testid="subtitle-vietnamese">{hasLanguage && language.translation.text ? language.translation.text : hasLanguage && ['failed', 'unavailable'].includes(language.translation.status) ? `${settings.sentence_language === 'en' ? 'English' : 'Vietnamese'} unavailable` : 'Translating locally…'}</div>}
    </div>
  </div>;
}
