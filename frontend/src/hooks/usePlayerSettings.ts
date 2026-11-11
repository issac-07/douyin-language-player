import { useEffect, useRef, useState } from 'react';
import type { PlayerSettings } from '../types';
import { api } from '../services/api';

export const DEFAULT_PLAYER_SETTINGS: PlayerSettings = {
  mode: 'interactive', font_size: 20, pinyin_size: 12, translation_size: 13,
  vertical_offset: 0, horizontal_offset: 0, background_opacity: .35, text_color: '#ffffff', text_shadow: true,
  show_pinyin: true, show_chinese: true, show_translation: true, show_all: true, pause_on_word: false, auto_pause: false,
};

export function usePlayerSettings() {
  const [settings, setSettings] = useState(DEFAULT_PLAYER_SETTINGS);
  const [status, setStatus] = useState('');
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const changed = useRef(false);
  const generation = useRef(0);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    api.playerSettings().then((value) => { if (alive.current && !changed.current) setSettings(value); }).catch((cause) => { if (alive.current) setStatus(cause.message); });
    return () => { alive.current = false; };
  }, []);
  const update = (value: PlayerSettings) => {
    changed.current = true; setSettings(value); setStatus('Saving appearance…');
    const version = ++generation.current;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      queue.current = queue.current.catch(() => undefined).then(() => api.savePlayerSettings(value))
        .then(() => { if (alive.current && version === generation.current) setStatus('Appearance saved'); })
        .catch((cause) => { if (alive.current && version === generation.current) setStatus(`Appearance was not saved: ${cause.message}`); });
    }, 250);
  };
  return { settings, update, status };
}
