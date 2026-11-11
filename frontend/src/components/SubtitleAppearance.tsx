import type { PlayerSettings } from '../types';
import { DEFAULT_PLAYER_SETTINGS } from '../hooks/usePlayerSettings';

export function SubtitleAppearance({ settings, update, status, close }: { settings: PlayerSettings; update: (settings: PlayerSettings) => void; status: string; close: () => void }) {
  const sliders = [
    ['font_size', 'Chinese font size', 10, 44, 1], ['pinyin_size', 'Pinyin font size', 7, 26, 1],
    ['translation_size', 'Vietnamese font size', 8, 28, 1], ['vertical_offset', 'Subtitle vertical position', -40, 40, 1],
    ['horizontal_offset', 'Subtitle horizontal position', -40, 40, 1], ['background_opacity', 'Subtitle background opacity', 0, 1, .05],
  ] as const;
  const toggles = [['show_all', 'Show generated subtitles'], ['show_pinyin', 'Show pinyin'], ['show_chinese', 'Show Chinese'], ['show_translation', 'Show Vietnamese'], ['text_shadow', 'Text shadow'], ['pause_on_word', 'Pause when selecting a word'], ['auto_pause', 'Auto-pause after each subtitle']] as const;
  return <section className="subtitle-settings-menu" aria-label="Subtitle appearance settings" onClick={(event) => event.stopPropagation()}>
    <div className="settings-menu-heading"><strong>Subtitle appearance</strong><button className="text-action" onClick={close} aria-label="Close subtitle settings">Close</button></div>
    <label>Display mode<select aria-label="Subtitle display mode" value={settings.mode} onChange={(event) => update({ ...settings, mode: event.target.value as PlayerSettings['mode'] })}><option value="interactive">Interactive</option><option value="minimal">Minimal · pinyin + Vietnamese</option></select></label>
    {sliders.map(([key, label, min, max, step]) => <label key={key} className="appearance-slider"><span>{label}<output>{settings[key]}</output></span><input aria-label={label} type="range" min={min} max={max} step={step} value={settings[key]} onChange={(event) => update({ ...settings, [key]: Number(event.target.value) })} /></label>)}
    <label className="appearance-color">Text color<input type="color" aria-label="Subtitle text color" value={settings.text_color} onChange={(event) => update({ ...settings, text_color: event.target.value })} /></label>
    {toggles.map(([key, label]) => <label key={key} className="appearance-toggle"><input type="checkbox" checked={settings[key]} onChange={(event) => update({ ...settings, [key]: event.target.checked })} />{label}</label>)}
    <button className="secondary-button" onClick={() => update({ ...DEFAULT_PLAYER_SETTINGS })}>Reset to Defaults</button>
    <p role="status">{status || 'Position is relative to the OCR region. Positive values move down/right.'}</p>
  </section>;
}
