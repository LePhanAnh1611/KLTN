import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from './client';
import type { WordSet } from '../types/wordSet';

/** UC-84 — trạng thái một chặng trên bản đồ lộ trình. */
export type StageState = 'mastered' | 'achieved' | 'current' | 'in_progress' | 'locked';

export interface RoadmapStage {
  id: number;
  title: string;
  cefr_level: string;
  order_index: number;
  word_set_id: number;
  /** Lộ trình v2: 'topic' (chủ đề) | 'core' (cốt lõi). null = chặng v1. */
  track?: 'topic' | 'core' | null;
  /** Tên chủ đề khi track = 'topic'. */
  topic?: string | null;
  state: StageState;
  progress_pct: number;
  items_mastered: number;
  items_total: number;
  /** Số từ cần đạt để qua chặng (chặng xong ở ~80%, không phải 100%). */
  items_needed?: number;
  /** Đã học >= 1 lần nhưng chưa đạt ngưỡng chặng. */
  items_learning?: number;
  is_recommended: boolean;
  /** Bản sao trong thư viện người học (Q1) — null nghĩa là chưa tải về. */
  user_word_set_id: number | null;
  is_skipped: boolean;
}

export interface RoadmapResponse {
  entry_level: string;
  /** UC-10 — mục tiêu CEFR người học tự đặt. null = chưa đặt. */
  target_level: string | null;
  stages: RoadmapStage[];
}

export function useRoadmap() {
  return useQuery({
    queryKey: ['roadmap'],
    queryFn: () => apiGet<RoadmapResponse>('/api/v1/me/roadmap'),
  });
}

/** Chặng chưa tải: tải bộ từ về thư viện (UC-21) rồi mới vào học được. */
export function useDownloadStageSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (wordSetId: number) =>
      apiPost<WordSet>(`/api/v1/discover/${wordSetId}/download`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roadmap'] });
      qc.invalidateQueries({ queryKey: ['word-sets'] });
    },
  });
}

/** UC-85 — đề xuất nâng trình độ đang chờ người học quyết định. */
export interface LevelUpSuggestion {
  id: number;
  from_level: string;
  to_level: string;
  status: string;
  avg_mastery: number;
  items_considered: number;
  created_at: string;
}

export interface LevelUpStatus {
  current_level: string;
  next_level: string | null;
  eligible: boolean;
  stages_total: number;
  stages_mastered: number;
  avg_mastery: number;
  items_considered: number;
  required_avg_mastery: number;
  required_items: number;
  suggestion: LevelUpSuggestion | null;
}

export function useLevelUpStatus() {
  return useQuery({
    queryKey: ['level-up'],
    queryFn: () => apiGet<LevelUpStatus>('/api/v1/me/level-up'),
  });
}

/** Đồng ý -> lộ trình sinh lại từ mức mới, nên phải nạp lại cả roadmap. */
export function useDecideLevelUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: 'accept' | 'decline' }) =>
      apiPost<LevelUpStatus>(`/api/v1/me/level-up/${id}/${decision}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['level-up'] });
      qc.invalidateQueries({ queryKey: ['roadmap'] });
      qc.invalidateQueries({ queryKey: ['placement'] });
      qc.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

/** UC-84 — một từ trong bảng tổng kết chặng. */
export interface StageWord {
  item_id: number;
  word: string;
  meaning: string;
  mastery: number;
}

export interface StageSummary {
  stage_id: number;
  title: string;
  cefr_level: string;
  state: StageState;
  is_complete: boolean;
  items_total: number;
  items_mastered: number;
  progress_pct: number;
  answers_total: number;
  answers_correct: number;
  accuracy: number;
  strongest: StageWord[];
  weakest: StageWord[];
  next_stage_id: number | null;
  next_stage_title: string | null;
}

/** `stageId` null = chưa mở bảng tổng kết nào. */
export function useStageSummary(stageId: number | null) {
  return useQuery({
    queryKey: ['roadmap', 'stage-summary', stageId],
    queryFn: () => apiGet<StageSummary>(`/api/v1/me/roadmap/stages/${stageId}/summary`),
    enabled: stageId !== null,
  });
}
