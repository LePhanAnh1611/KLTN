import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost, apiPostForm } from './client';

/** Module luyện nói — chấm theo rubric 4 tiêu chí × 4 mức.
 *
 * Toàn bộ suy luận chạy cục bộ trên máy chủ (faster-whisper + Ollama). File ghi
 * âm được xóa ngay sau khi chấm; chỉ transcript và kết quả được lưu. */

export const CRITERIA = [
  'fluency', 'pronunciation', 'grammar_vocab', 'coherence_task',
] as const;
export type Criterion = (typeof CRITERIA)[number];

export const CRITERION_LABELS: Record<Criterion, string> = {
  fluency: 'Độ trôi chảy',
  pronunciation: 'Độ dễ hiểu',
  grammar_vocab: 'Ngữ pháp & từ vựng',
  coherence_task: 'Mạch lạc & bám đề',
};

export const CRITERION_CODES: Record<Criterion, string> = {
  fluency: 'C1', pronunciation: 'C2', grammar_vocab: 'C3', coherence_task: 'C4',
};

export interface CriterionResult {
  level: number;
  label: string;
  evidence: string[];
  suggestion: string;
  /** 'rule' = suy từ số đo · 'llm' = mô hình chấm · 'fallback' = CHƯA chấm được. */
  scored_by: 'rule' | 'llm' | 'fallback';
  reason: string;
}

export interface AudioMetrics {
  duration_sec: number;
  speech_sec: number;
  words_per_minute: number;
  pause_ratio: number;
  pause_count: number;
  longest_pause_sec: number;
  filler_count: number;
  filler_per_100_words: number;
  asr_avg_confidence: number;
  word_count: number;
  language: string;
  pronunciation_source: string;
}

export interface SpeakingAssessment {
  attempt_id: number | null;
  transcript: string;
  audio_metrics: AudioMetrics;
  scores: Record<Criterion, CriterionResult>;
  overall_level: number;
  developmental_feedback: string;
  warnings: string[];
  rubric_version: string;
}

export interface SpeakingHealth {
  asr_ready: boolean;
  asr_detail: string;
  llm_ready: boolean;
  llm_detail: string;
  ollama_model: string;
  installed_models: string[];
  /** Rubric nằm ở docs/, ngoài package — có thể thiếu khi triển khai. */
  rubric_ready: boolean;
  rubric_detail: string;
  rubric_version: string;
  rubric_calibrated: boolean;
}

export interface SpeakingAttemptRow {
  id: number;
  task_prompt: string;
  transcript: string;
  overall_level: number;
  scores: Record<Criterion, CriterionResult>;
  audio_metrics: AudioMetrics;
  developmental_feedback: string;
  warnings: string[];
  rubric_version: string;
  created_at: string;
  has_appeal: boolean;
}

export interface SpeakingProgressPoint {
  attempt_id: number;
  created_at: string;
  overall_level: number;
  levels: Record<string, number>;
  words_per_minute: number;
}

export interface SpeakingHistoryResponse {
  items: SpeakingAttemptRow[];
  total: number;
  page: number;
  page_size: number;
  progress: SpeakingProgressPoint[];
  progress_rubric_version: string;
}

export function useSpeakingHealth() {
  return useQuery({
    queryKey: ['speaking', 'health'],
    queryFn: () => apiGet<SpeakingHealth>('/api/v1/speaking/health'),
    retry: false,
  });
}

export interface AssessInput {
  blob: Blob;
  taskPrompt: string;
  weights?: Partial<Record<Criterion, number>>;
}

/** Gửi bản ghi âm đi chấm. */
export function useAssessSpeaking() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blob, taskPrompt, weights }: AssessInput) => {
      const form = new FormData();
      // Đặt đuôi .webm cho khớp định dạng MediaRecorder xuất ra
      form.append('audio', blob, 'bai-noi.webm');
      form.append('task_prompt', taskPrompt);
      if (weights && Object.keys(weights).length > 0) {
        form.append('weights', JSON.stringify(weights));
      }
      return apiPostForm<SpeakingAssessment>('/api/v1/speaking/assess', form);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['speaking', 'attempts'] }),
  });
}

export function useSpeakingHistory(page: number) {
  return useQuery({
    queryKey: ['speaking', 'attempts', page],
    queryFn: () => apiGet<SpeakingHistoryResponse>(
      `/api/v1/speaking/attempts?page=${page}&page_size=10`,
    ),
  });
}

export interface AppealInput {
  attemptId: number;
  criterion: string;
  expectedLevel: number | null;
  comment: string;
}

/** Rubric mục 9 — báo kết quả chấm chưa đúng. KHÔNG sửa điểm, chỉ ghi nhận. */
export function useCreateAppeal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ attemptId, criterion, expectedLevel, comment }: AppealInput) =>
      apiPost(`/api/v1/speaking/attempts/${attemptId}/appeals`, {
        criterion, expected_level: expectedLevel, comment,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['speaking', 'attempts'] }),
  });
}
