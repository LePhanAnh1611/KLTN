import { useQuery } from '@tanstack/react-query';

import { apiGet } from './client';

/** API tổng hợp cho trang chủ học viên — tất cả chỉ đọc. */

export interface DailyGoal {
  done: number;
  target: number;
  reached: boolean;
}

export interface GamificationSummary {
  xp: number;
  level: number;
  level_title: string;
  xp_into_level: number;
  xp_for_next_level: number;
  streak_count: number;
  daily_goal: DailyGoal;
}

export interface StatsOverview {
  total_items: number;
  mastered: number;
  in_progress: number;
  not_started: number;
  mastery_percent: number;
}

export interface CourseProgress {
  id: number;
  name: string;
  cover_image_url: string | null;
  /** Mức CEFR của bộ (A1…C2); null = bộ tự tạo, không khai mức. */
  cefr_level: string | null;
  total_items: number;
  mastered_items: number;
  /** Đã học >= 1 lần nhưng chưa thuộc. */
  learning_items?: number;
  percent: number;
}

export interface RecommendedWord {
  item_id: number;
  word: string;
  meaning: string;
  word_set_id: number;
  word_set_name: string;
  predicted_p: number;
}

export interface TodayRecommendation {
  count: number;
  band_low: number;
  band_high: number;
  /** true = service DKT không sẵn sàng, điểm là cold-start prior chứ không phải dự đoán. */
  degraded: boolean;
  items: RecommendedWord[];
  /** Số từ được học lần đầu trong hôm nay — ≥ 1 thì bước "Học từ mới" coi như xong. */
  new_learned_today: number;
}

export interface ReviewDay {
  date: string;          // YYYY-MM-DD
  due_count: number;
}

export interface UpcomingReview {
  id: number;            // word_set_id
  title: string;
  group: string | null;
  due_count: number;
  scheduled_at: string;
}

export function useGamificationSummary() {
  return useQuery({
    queryKey: ['home', 'gamification'],
    queryFn: () => apiGet<GamificationSummary>('/api/v1/gamification/summary'),
  });
}

export function useStatsOverview() {
  return useQuery({
    queryKey: ['home', 'stats'],
    queryFn: () => apiGet<StatsOverview>('/api/v1/stats/overview'),
  });
}

export function useCourseProgress() {
  return useQuery({
    queryKey: ['home', 'courses'],
    queryFn: () => apiGet<CourseProgress[]>('/api/v1/progress/courses'),
  });
}

export function useTodayRecommendation() {
  return useQuery({
    queryKey: ['home', 'recommendations'],
    queryFn: () => apiGet<TodayRecommendation>('/api/v1/recommendations/today'),
  });
}

/** `month` dạng YYYY-MM. */
export function useReviewDays(month: string) {
  return useQuery({
    queryKey: ['home', 'review-days', month],
    queryFn: () => apiGet<ReviewDay[]>(`/api/v1/review-schedules?month=${month}`),
  });
}

export function useUpcomingReviews(limit = 3) {
  return useQuery({
    queryKey: ['home', 'upcoming', limit],
    queryFn: () => apiGet<UpcomingReview[]>(`/api/v1/review-schedules/upcoming?limit=${limit}`),
  });
}
