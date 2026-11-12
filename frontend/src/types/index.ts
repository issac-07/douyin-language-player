export interface Video {
  id: string;
  original_name: string;
  sha256: string;
  size_bytes: number;
  duration: number;
  width: number;
  height: number;
  fps: number;
  video_codec: string;
  audio_codec: string | null;
  created_at: string;
  media_url: string;
  codec_warning: string | null;
  title?: string | null;
  source_url?: string | null;
  uploader?: string | null;
  imported_from?: string;
}

export interface URLImportJob {
  id: string;
  input_url: string;
  canonical_url: string | null;
  status: 'pending' | 'resolving' | 'downloading' | 'validating' | 'importing' | 'completed' | 'failed' | 'cancelled';
  bytes_downloaded: number;
  total_bytes: number | null;
  attempt: number;
  max_attempts: number;
  metadata: { title: string | null; uploader: string | null; duration: number | null } | null;
  video: Video | null;
  reused: boolean;
  error: string | null;
  error_code?: string | null;
  error_operation?: string | null;
  upstream_http_status?: number | null;
  extractor_version?: string | null;
  diagnostics?: { operation: string; event: string; category: string | null; http_status: number | null; host: string | null; endpoint: string | null; exception_type: string | null; upstream_reason: string | null }[];
  conversion: string;
  elapsed_seconds: number;
  analysis_message: string | null;
}

export interface ProcessingSettings {
  roi: { x: number; y: number; width: number; height: number };
  sample_fps: number;
  performance?: { backend: 'auto' | 'cpu' | 'intel-gpu'; mode: 'accurate' | 'balanced' | 'fast'; cpu_threads: 2 | 4 | 8; cpu_runtime: 'ort' | 'openvino-cpu' };
}

export interface Health {
  status: string;
  ffprobe_available: boolean;
  max_upload_bytes: number;
  ocr_available: boolean;
}

// Shared shape for the future timestamp-based subtitle renderer.
export interface SubtitleSegment {
  id: string;
  start_time: number;
  end_time: number;
  text: string;
  confidence: number;
  edited: boolean;
  revision: number;
  metadata: Record<string, unknown>;
}

export interface AnalysisJob {
  id: string;
  video_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  settings: ProcessingSettings;
  progress: number;
  total_frames: number;
  error: string | null;
  engine_version: string;
  timestamp_uncertainty: number;
  execution?: { requested_backend?: string; actual_backend?: string; threads?: number | null; decoder?: string; reuse?: string; fallback?: boolean; stages?: Record<string, unknown> };
  metrics: {
    frames_processed: number; ocr_calls: number; reused_frames: number;
    total_seconds: number; inference_seconds: number;
    unique_segments: number; average_confidence: number;
  };
}

export interface SubtitleDocument {
  video_id: string;
  analysis: AnalysisJob | null;
  segments: SubtitleSegment[];
}

export interface WordToken { text: string; start: number; end: number; pinyin: string; selectable: boolean }
export interface Translation { status: 'pending' | 'completed' | 'failed' | 'unavailable' | 'manual'; text: string | null; model: string | null; error: string | null; seconds: number | null }
export interface LearningSegment { id: string; revision: number; text: string; tokens: WordToken[]; translation: Translation }
export interface LearningDocument { video_id: string; analysis_id: string | null; segments: LearningSegment[]; dictionary_available: boolean }
export interface DictionaryEntry { traditional: string; simplified: string; pinyin: string; meanings: string[] }
export interface DictionaryResult { word: string; entries: DictionaryEntry[]; available: boolean; source: string; language: string; license: string }
export interface SavedWord { id: string; word: string; pinyin: string; entries: DictionaryEntry[]; status: 'new' | 'learning' | 'known'; notes: string; updated_at: string }
export interface PlayerSettings {
  mode: 'interactive' | 'minimal'; font_size: number; pinyin_size: number; translation_size: number;
  vertical_offset: number; horizontal_offset: number; background_opacity: number; text_color: string; text_shadow: boolean;
  show_pinyin: boolean; show_chinese: boolean; show_translation: boolean; show_all: boolean; pause_on_word: boolean; auto_pause: boolean;
}
