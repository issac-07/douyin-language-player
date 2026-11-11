"""Sentence-context pinyin with exact source offsets, independent of HTTP/UI."""
import logging
import re
import threading
from functools import lru_cache

import jieba
from pypinyin import Style, lazy_pinyin
from pypinyin.contrib.tone_convert import to_tone

from app.models.learning import WordToken

VERSION = 'jieba-0.42.1:pypinyin-0.55.0:sentence-sandhi-v2'
CHINESE = re.compile(r'[\u3400-\u9fff]')
_lock = threading.Lock()
_tokenizer = jieba.Tokenizer()
jieba.setLogLevel(logging.WARNING)


@lru_cache(maxsize=4096)
def process_chinese(text: str) -> tuple[WordToken, ...]:
    # Single-character fallback preserves one pronunciation slot per source codepoint.
    pronunciations = lazy_pinyin(text, style=Style.TONE3, tone_sandhi=True,
                                 neutral_tone_with_five=True, errors=lambda value: list(value))
    # Phrase data handles polyphony; apply productive 一/不 tone changes across
    # word boundaries as well, preserving ordinals and serial-number readings.
    digits = '零〇一二三四五六七八九'
    for index in range(len(text) - 2, -1, -1):
        if not CHINESE.search(text[index + 1]):
            continue
        next_tone = pronunciations[index + 1][-1:]
        if text[index] == '一' and not (index and text[index - 1] in digits + '第') and text[index + 1] not in digits + '月':
            if next_tone == '4': pronunciations[index] = 'yi2'
            elif next_tone in ('1', '2', '3'): pronunciations[index] = 'yi4'
        elif text[index] == '不' and next_tone == '4':
            pronunciations[index] = 'bu2'
    pronunciations = [to_tone(value) for value in pronunciations]
    with _lock:
        spans = list(_tokenizer.tokenize(text, mode='default', HMM=True))
    tokens = []
    for word, start, end in spans:
        selectable = bool(CHINESE.search(word))
        syllables = pronunciations[start:end]
        pinyin = ' '.join(syllables) if selectable else ''
        tokens.append(WordToken(text=word, start=start, end=end, pinyin=pinyin, selectable=selectable))
    return tuple(tokens)
