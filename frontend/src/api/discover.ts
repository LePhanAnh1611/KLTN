import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost, apiPut } from './client';
import type { WordSet } from '../types/wordSet';

export interface ItemPreview {
  word: string;
  meaning: string;
  phonetic?: string | null;
  part_of_speech?: string | null;
}

export interface PublicWordSetCard {
  id: number;
  name: string;
  description: string | null;
  category: string | null;
  difficulty: string | null;
  cover_image_url: string | null;
  download_count: number;
  is_featured: boolean;
  owner_name: string;
  item_count: number;
  is_downloaded: boolean;
  rating_avg: number | null;
  rating_count: number;
  tags: string[];              // UC-96
}

export interface PublicListResponse {
  items: PublicWordSetCard[];
  total: number;
  page: number;
  page_size: number;
}

export interface PublicWordSetDetail extends PublicWordSetCard {
  created_at: string;
  preview_items: ItemPreview[];
}

export type DiscoverSort = 'popular' | 'new' | 'rating';

export interface DiscoverParams {
  q?: string;
  category?: string;
  difficulty?: string;
  tag?: string;                // UC-96
  sort?: DiscoverSort;
  page?: number;
  page_size?: number;
}

/** UC-23 — điểm đánh giá của một bộ từ. */
export interface RatingItem {
  user_name: string;
  stars: number;
  comment: string | null;
  created_at: string;
}

export interface RatingSummary {
  average: number | null;
  count: number;
  my_stars: number | null;
  my_comment: string | null;
  can_rate: boolean;
  items: RatingItem[];
}

/** UC-24 — báo cáo bộ từ vi phạm. */
export type ReportReason = 'wrong_content' | 'spam' | 'copyright' | 'offensive' | 'other';

/** Lý do báo cáo dùng chung cho bộ từ (UC-24) và bài viết (UC-53). */
export const REPORT_REASONS: { value: ReportReason; label: string }[] = [
  { value: 'wrong_content', label: 'Nội dung sai' },
  { value: 'spam', label: 'Spam / quảng cáo' },
  { value: 'copyright', label: 'Vi phạm bản quyền' },
  { value: 'offensive', label: 'Nội dung phản cảm' },
  { value: 'other', label: 'Lý do khác' },
];

export interface ReportResponse {
  id: number;
  target_type: string;
  target_id: number;
  reason: string;
  status: string;
  merged: boolean;
}

function buildQuery(params: DiscoverParams): string {
  const sp = new URLSearchParams();
  if (params.q) sp.set('q', params.q);
  if (params.category) sp.set('category', params.category);
  if (params.difficulty) sp.set('difficulty', params.difficulty);
  if (params.sort) sp.set('sort', params.sort);
  if (params.tag) sp.set('tag', params.tag);
  if (params.page) sp.set('page', String(params.page));
  if (params.page_size) sp.set('page_size', String(params.page_size));
  const qs = sp.toString();
  return qs ? `?${qs}` : '';
}

export function useDiscover(params: DiscoverParams) {
  return useQuery({
    queryKey: ['discover', params],
    queryFn: () => apiGet<PublicListResponse>(`/api/v1/discover${buildQuery(params)}`),
  });
}

export function usePublicDetail(id: number | null) {
  return useQuery({
    queryKey: ['discover', 'detail', id],
    queryFn: () => apiGet<PublicWordSetDetail>(`/api/v1/discover/${id}`),
    enabled: id != null,
  });
}

/** UC-76 → UC-19 — danh mục đang bật, dùng cho bộ lọc Khám phá. */
export interface DiscoverCategory {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export function useCategories() {
  return useQuery({
    queryKey: ['discover', 'categories'],
    queryFn: () => apiGet<DiscoverCategory[]>('/api/v1/discover/categories'),
  });
}

/** UC-96 — nhãn phổ biến kèm số bộ công khai đang mang nhãn đó. */
export interface TagCount {
  tag: string;
  count: number;
}

export function usePopularTags() {
  return useQuery({
    queryKey: ['discover', 'tags'],
    queryFn: () => apiGet<TagCount[]>('/api/v1/discover/tags'),
  });
}

/** UC-22 — bộ từ nổi bật do Admin gắn cờ. */
export function useFeatured() {
  return useQuery({
    queryKey: ['discover', 'featured'],
    queryFn: () => apiGet<PublicWordSetCard[]>('/api/v1/discover/featured'),
  });
}

export function useDownloadWordSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiPost<WordSet>(`/api/v1/discover/${id}/download`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['discover'] });
      qc.invalidateQueries({ queryKey: ['word-sets'] });
    },
  });
}

/** UC-23 — xem điểm đánh giá của bộ từ. */
export function useRatings(id: number | null) {
  return useQuery({
    queryKey: ['discover', 'ratings', id],
    queryFn: () => apiGet<RatingSummary>(`/api/v1/discover/${id}/ratings`),
    enabled: id != null,
  });
}

/** UC-23 — chấm sao (gửi lại = sửa đánh giá cũ). */
export function useRateWordSet(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { stars: number; comment?: string | null }) =>
      apiPut<RatingSummary>(`/api/v1/discover/${id}/rating`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['discover'] });
    },
  });
}

/** UC-24 — báo cáo bộ từ vi phạm. */
export function useReportWordSet(id: number) {
  return useMutation({
    mutationFn: (body: { reason: ReportReason; description?: string | null }) =>
      apiPost<ReportResponse>(`/api/v1/discover/${id}/report`, body),
  });
}
