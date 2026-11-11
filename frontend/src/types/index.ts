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
}

export interface ProcessingSettings {
  roi: { x: number; y: number; width: number; height: number };
  sample_fps: number;
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
