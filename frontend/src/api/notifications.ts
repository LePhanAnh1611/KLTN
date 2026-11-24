import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPost, apiPut } from './client';

/** UC-58 — thông báo in-app. */
export type NotificationType =
  | 'review_due' | 'streak_risk' | 'achievement' | 'community' | 'level_up' | 'system';

export interface AppNotification {
  id: number;
  type: NotificationType;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: AppNotification[];
  unread_count: number;
}

export interface NotificationPreferences {
  notify_review: boolean;
  notify_achievement: boolean;
  notify_community: boolean;
}

const LIST_KEY = ['notifications'];

export function useNotifications(enabled = true) {
  return useQuery({
    queryKey: LIST_KEY,
    queryFn: () => apiGet<NotificationListResponse>('/api/v1/notifications'),
    enabled,
  });
}

/** UC-59 — đánh dấu một thông báo đã đọc. */
export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiPost(`/api/v1/notifications/${id}/read`, {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

/** UC-59 — đọc tất cả. */
export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<{ marked: number }>('/api/v1/notifications/read-all', {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

/** UC-59 — xóa thông báo. */
export function useDeleteNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/notifications/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

/** UC-60 — tùy chọn loại thông báo. */
export function useNotificationPreferences() {
  return useQuery({
    queryKey: ['notifications', 'preferences'],
    queryFn: () => apiGet<NotificationPreferences>('/api/v1/notifications/preferences'),
  });
}

export function useUpdateNotificationPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: NotificationPreferences) =>
      apiPut<NotificationPreferences>('/api/v1/notifications/preferences', body),
    onSuccess: (data) => qc.setQueryData(['notifications', 'preferences'], data),
  });
}
