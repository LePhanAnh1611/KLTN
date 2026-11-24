import { useQuery } from '@tanstack/react-query';

import { apiGet } from './client';

export interface MasteryBand {
  label: string;
  count: number;
}

export interface WeakItem {
  item_id: number;
  word: string;
  meaning: string;
  word_set_name: string;
  mastery: number;
}

export interface ProgressData {
  level: number;
  level_title: string;
  xp: number;
  xp_into_level: number;
  xp_for_next_level: number;
  streak_count: number;
  today_xp: number;
  daily_xp_goal: number;
  daily_goal_reached: boolean;
  total_items: number;
  learned_items: number;
  mastered_items: number;
  mastery_distribution: MasteryBand[];
  weak_items: WeakItem[];
}

export function getProgress(): Promise<ProgressData> {
  return apiGet<ProgressData>('/api/v1/progress');
}

/** UC-92 — một điểm trên đường cong học tập. */
export interface MasteryPoint {
  answered_at: string;
  /** Mastery hệ thống nắm giữ TRƯỚC lượt này. null = chưa có dự đoán nào. */
  mastery: number | null;
  is_correct: boolean;
  /** 'model' = DKT chấm · 'prior' = giá trị cold-start · null = chưa có. */
  source: string | null;
  exercise_format: string | null;
}

export interface MasteryHistory {
  item_id: number;
  word: string;
  meaning: string;
  current_mastery: number | null;
  mastered_threshold: number;
  total_answers: number;
  answers_without_prediction: number;
  points: MasteryPoint[];
}

/** UC-92 — đường cong mastery của một từ, dựng lại từ lịch sử trả lời. */
export function useMasteryHistory(itemId: number | null) {
  return useQuery({
    queryKey: ['mastery-history', itemId],
    queryFn: () => apiGet<MasteryHistory>(`/api/v1/progress/items/${itemId}/mastery-history`),
    enabled: itemId !== null,
  });
}
