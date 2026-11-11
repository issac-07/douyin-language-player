import type { AnalysisJob, DictionaryResult, Health, LearningDocument, PlayerSettings, ProcessingSettings, SavedWord, SubtitleDocument, SubtitleSegment, Video } from '../types';

export function errorMessage(body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) return detail.map((item) => item.msg ?? 'Invalid input').join('. ');
  }
  return 'The request failed. Check that the backend is running and try again.';
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(url, options); }
  catch { throw new Error('Cannot reach the backend. Start FastAPI on port 8000 and retry.'); }
  if (!response.ok) throw new Error(errorMessage(await response.json().catch(() => null)));
  return response.json() as Promise<T>;
}

export const api = {
  learning: (id: string, signal?: AbortSignal) => request<LearningDocument>(`/api/videos/${id}/learning`, { signal }),
  retryLearning: (id: string) => request<LearningDocument>(`/api/videos/${id}/learning/retry`, { method: 'POST' }),
  dictionary: (word: string, signal?: AbortSignal) => request<DictionaryResult>(`/api/dictionary?word=${encodeURIComponent(word)}`, { signal }),
  vocabulary: () => request<SavedWord[]>('/api/vocabulary'),
  saveWord: (word: string, status: SavedWord['status'], notes: string) => request<SavedWord>('/api/vocabulary', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ word, status, notes }) }),
  deleteWord: async (id: string) => { const response = await fetch(`/api/vocabulary/${id}`, { method: 'DELETE' }); if (!response.ok) throw new Error(errorMessage(await response.json())); },
  playerSettings: () => request<PlayerSettings>('/api/player-settings'),
  savePlayerSettings: (settings: PlayerSettings) => request<PlayerSettings>('/api/player-settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) }),
  editTranslation: (videoId: string, analysisId: string, segment: SubtitleSegment, translation: string) => request<LearningDocument>(`/api/videos/${videoId}/subtitles/${segment.id}/translation`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ analysis_id: analysisId, revision: segment.revision, source_text: segment.text, translation }),
  }),
  health: () => request<Health>('/api/health'),
  videos: () => request<Video[]>('/api/videos'),
  settings: (id: string) => request<ProcessingSettings>(`/api/videos/${id}/processing-settings`),
  saveSettings: (id: string, settings: ProcessingSettings) => request<ProcessingSettings>(`/api/videos/${id}/processing-settings`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings),
  }),
  subtitles: (id: string, signal?: AbortSignal) => request<SubtitleDocument>(`/api/videos/${id}/subtitles`, { signal }),
  latestAnalysis: (id: string, signal?: AbortSignal) => request<AnalysisJob | null>(`/api/videos/${id}/analyses/latest`, { signal }),
  analyze: (id: string, settings: ProcessingSettings, force: boolean) => request<{ job: AnalysisJob; cached: boolean }>(`/api/videos/${id}/analyses`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings, force }),
  }),
  job: (id: string, signal?: AbortSignal) => request<AnalysisJob>(`/api/analysis-jobs/${id}`, { signal }),
  cancel: (id: string) => request<AnalysisJob>(`/api/analysis-jobs/${id}/cancel`, { method: 'POST' }),
  editSubtitle: (videoId: string, analysisId: string, segment: SubtitleSegment, text: string, start: number, end: number) => request<SubtitleDocument>(`/api/videos/${videoId}/subtitles/${segment.id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ analysis_id: analysisId, revision: segment.revision, text, start_time: start, end_time: end }),
  }),
  deleteSubtitle: (videoId: string, analysisId: string, segment: SubtitleSegment) => request<SubtitleDocument>(`/api/videos/${videoId}/subtitles/${segment.id}?analysis_id=${analysisId}&revision=${segment.revision}`, { method: 'DELETE' }),
};

export function uploadVideo(file: File, onProgress: (percent: number) => void): Promise<{ video: Video; reused: boolean }> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/videos');
    xhr.responseType = 'json';
    xhr.timeout = 300_000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response?.video) resolve(xhr.response);
      else reject(new Error(errorMessage(xhr.response)));
    };
    xhr.onerror = () => reject(new Error('Upload failed. Check the backend connection and retry.'));
    xhr.ontimeout = () => reject(new Error('Upload timed out. Try a smaller file or check the backend.'));
    const form = new FormData();
    form.append('file', file);
    xhr.send(form);
  });
}
