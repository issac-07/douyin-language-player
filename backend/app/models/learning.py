from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class WordToken(BaseModel):
    text: str
    start: int
    end: int
    pinyin: str
    selectable: bool


class Translation(BaseModel):
    status: Literal['pending', 'completed', 'failed', 'unavailable', 'manual']
    text: str | None = None
    model: str | None = None
    error: str | None = None
    seconds: float | None = None


class LearningSegment(BaseModel):
    id: UUID
    revision: int
    text: str
    tokens: list[WordToken]
    translation: Translation


class LearningDocument(BaseModel):
    video_id: UUID
    analysis_id: UUID | None
    segments: list[LearningSegment]
    dictionary_available: bool


class DictionaryEntry(BaseModel):
    traditional: str
    simplified: str
    pinyin: str
    meanings: list[str]


class DictionaryResult(BaseModel):
    word: str
    entries: list[DictionaryEntry]
    available: bool
    source: str = 'CC-CEDICT contributors / MDBG'
    language: str = 'English'
    license: str = 'CC-BY-SA-4.0'


class VocabularyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    word: str = Field(min_length=1, max_length=64)
    status: Literal['new', 'learning', 'known'] = 'new'
    notes: str = Field(default='', max_length=5000)


class SavedWord(VocabularyInput):
    id: UUID
    pinyin: str
    entries: list[DictionaryEntry]
    updated_at: str


class TranslationEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    analysis_id: UUID
    revision: int = Field(ge=0)
    source_text: str = Field(min_length=1, max_length=5000)
    translation: str = Field(min_length=1, max_length=5000)


class PlayerSettings(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    mode: Literal['interactive', 'minimal'] = 'interactive'
    font_size: float = Field(default=20, ge=10, le=44)
    pinyin_size: float = Field(default=12, ge=7, le=26)
    translation_size: float = Field(default=13, ge=8, le=28)
    vertical_offset: float = Field(default=0, ge=-40, le=40)
    horizontal_offset: float = Field(default=0, ge=-40, le=40)
    background_opacity: float = Field(default=.35, ge=0, le=1)
    text_color: str = Field(default='#ffffff', pattern=r'^#[0-9a-fA-F]{6}$')
    text_shadow: bool = True
    show_pinyin: bool = True
    show_chinese: bool = True
    show_translation: bool = True
    show_all: bool = True
    pause_on_word: bool = False
    auto_pause: bool = False
