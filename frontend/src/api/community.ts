import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPost } from './client';
import type { ReportReason, ReportResponse } from './discover';

/** UC-49 — loại bài viết (khớp Literal PostType ở backend). */
export type PostType =
  | 'tip' | 'word' | 'question' | 'resource' | 'word_set' | 'progress' | 'share';

/** Nhãn tiếng Việt cho từng loại bài (UC-49). */
export const POST_TYPE_LABELS: Record<PostType, string> = {
  tip: 'Mẹo học',
  word: 'Từ hay',
  question: 'Câu hỏi',
  resource: 'Tài nguyên',
  word_set: 'Bộ từ vựng',
  progress: 'Tiến độ',
  share: 'Chia sẻ',
};

export interface PostCard {
  id: number;
  post_type: PostType;
  content: string;
  image_url: string | null;
  status: string;
  created_at: string;
  author_id: number;
  author_name: string;
  author_avatar_url: string | null;
  like_count: number;
  comment_count: number;
  liked_by_me: boolean;
  is_mine: boolean;
}

export interface PostListResponse {
  items: PostCard[];
  total: number;
  page: number;
  page_size: number;
}

export interface Comment {
  id: number;
  post_id: number;
  content: string;
  created_at: string;
  author_id: number;
  author_name: string;
  is_mine: boolean;
}

export interface FeedParams {
  post_type?: PostType | '';
  author_id?: number;
  page?: number;
  page_size?: number;
}

function buildQuery(params: FeedParams): string {
  const sp = new URLSearchParams();
  if (params.post_type) sp.set('post_type', params.post_type);
  if (params.author_id) sp.set('author_id', String(params.author_id));
  if (params.page) sp.set('page', String(params.page));
  if (params.page_size) sp.set('page_size', String(params.page_size));
  const qs = sp.toString();
  return qs ? `?${qs}` : '';
}

/** UC-49 — bảng tin cộng đồng. */
export function useFeed(params: FeedParams) {
  return useQuery({
    queryKey: ['community', 'feed', params],
    queryFn: () => apiGet<PostListResponse>(`/api/v1/community/posts${buildQuery(params)}`),
  });
}

export function useCreatePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { post_type: PostType; content: string; image_url?: string | null }) =>
      apiPost<PostCard>('/api/v1/community/posts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['community', 'feed'] }),
  });
}

/** UC-52 — gỡ bài của mình. */
export function useDeletePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/community/posts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['community', 'feed'] }),
  });
}

/** UC-51 — thích / bỏ thích. */
export function useToggleLike() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiPost<{ post_id: number; like_count: number; liked_by_me: boolean }>(
        `/api/v1/community/posts/${id}/like`, {},
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['community', 'feed'] }),
  });
}

/** UC-50 — bình luận. */
export function useComments(postId: number | null) {
  return useQuery({
    queryKey: ['community', 'comments', postId],
    queryFn: () => apiGet<Comment[]>(`/api/v1/community/posts/${postId}/comments`),
    enabled: postId != null,
  });
}

export function useAddComment(postId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: string) =>
      apiPost<Comment>(`/api/v1/community/posts/${postId}/comments`, { content }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['community', 'comments', postId] });
      qc.invalidateQueries({ queryKey: ['community', 'feed'] });
    },
  });
}

/** UC-54 — bảng xếp hạng theo XP. */
export type LeaderboardScope = 'all' | 'week';

export interface LeaderboardRow {
  rank: number;
  user_id: number;
  display_name: string;
  avatar_url: string | null;
  xp: number;
  level: number;
  level_title: string;
  /** Chuỗi ngày học liên tiếp — luôn là giá trị hiện tại, không đổi theo scope. */
  streak_count: number;
  is_me: boolean;
}

export interface LeaderboardResponse {
  scope: LeaderboardScope;
  items: LeaderboardRow[];
  my_rank: number | null;
  my_row: LeaderboardRow | null;
}

export function useLeaderboard(scope: LeaderboardScope) {
  return useQuery({
    queryKey: ['community', 'leaderboard', scope],
    queryFn: () => apiGet<LeaderboardResponse>(`/api/v1/community/leaderboard?scope=${scope}`),
  });
}

/** UC-53 — báo cáo bài viết. */
export function useReportPost(postId: number) {
  return useMutation({
    mutationFn: (body: { reason: ReportReason; description?: string | null }) =>
      apiPost<ReportResponse>(`/api/v1/community/posts/${postId}/report`, body),
  });
}
