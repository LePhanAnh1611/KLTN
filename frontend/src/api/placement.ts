import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from './client';

/** UC-11 — kiểm tra trình độ đầu vào. */
export interface PlacementQuestion {
  id: number;
  cefr_level: string;
  word: string;
  options: string[];
}

export interface PlacementLevelBreakdown {
  cefr_level: string;
  answered: number;
  correct: number;
}

export interface PlacementResult {
  estimated_level: string;
  entry_cefr_level: string;
  answered_count: number;
  correct_count: number;
  per_level: PlacementLevelBreakdown[];
  skipped: boolean;
}

export interface PlacementStatus {
  has_placement: boolean;
  entry_cefr_level: string | null;
  completed_at: string | null;
  question_count: number;
}

export function usePlacementStatus() {
  return useQuery({
    queryKey: ['placement', 'status'],
    queryFn: () => apiGet<PlacementStatus>('/api/v1/placement/status'),
  });
}

export function usePlacementQuestions(enabled: boolean) {
  return useQuery({
    queryKey: ['placement', 'questions'],
    queryFn: () => apiGet<PlacementQuestion[]>('/api/v1/placement/questions'),
    enabled,
    staleTime: Infinity,   // giữ nguyên bộ câu hỏi trong suốt lần làm bài
  });
}

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['placement'] });
  qc.invalidateQueries({ queryKey: ['roadmap'] });   // đổi điểm xuất phát -> đổi bản đồ
}

export function useSubmitPlacement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (answers: { question_id: number; answer: string }[]) =>
      apiPost<PlacementResult>('/api/v1/placement/submit', { answers }),
    onSuccess: () => invalidate(qc),
  });
}

/** Luồng thay thế 1a — "Tôi mới bắt đầu". */
export function useSkipPlacement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<PlacementResult>('/api/v1/placement/skip', {}),
    onSuccess: () => invalidate(qc),
  });
}
