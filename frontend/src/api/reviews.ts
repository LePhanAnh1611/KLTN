import type { ReviewCalendar, ReviewItem, WeakReviewItem } from '../types/review';
import type { StudySession } from '../types/session';
import { apiGet, apiPost } from './client';
import { useQuery } from '@tanstack/react-query';

export function getCalendar(): Promise<ReviewCalendar> {
  return apiGet<ReviewCalendar>('/api/v1/reviews/calendar');
}

export function pauseLowerLevelReviews(): Promise<{ paused_count: number }> {
  return apiPost('/api/v1/reviews/pause-lower-level', {});
}

export function getDue(limit?: number): Promise<ReviewItem[]> {
  return apiGet<ReviewItem[]>(`/api/v1/reviews/due${limit ? `?limit=${limit}` : ''}`);
}

export function createSrsSession(): Promise<StudySession> {
  // ôn SRS xuyên thư viện -> không gắn word_set_id
  return apiPost<StudySession>('/api/v1/sessions', { mode: 'srs_review' });
}

/** UC-86 — từ yếu nhất trong thư viện, không phụ thuộc lịch ôn. */
export function getWeak(limit?: number): Promise<WeakReviewItem[]> {
  return apiGet<WeakReviewItem[]>(`/api/v1/reviews/weak${limit ? `?limit=${limit}` : ''}`);
}

export function useWeakItems() {
  return useQuery({ queryKey: ['reviews', 'weak'], queryFn: () => getWeak() });
}

export function createWeakSession(): Promise<StudySession> {
  // ôn điểm yếu xuyên thư viện -> không gắn word_set_id (giống phiên SRS)
  return apiPost<StudySession>('/api/v1/sessions', { mode: 'weak_review' });
}
