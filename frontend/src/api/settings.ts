import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost, apiPut } from './client';

/** UC-09 + UC-10 — tùy chọn giao diện & mục tiêu học. */
export interface UserSettings {
  dark_mode: boolean;
  ui_language: string;
  reminder_time: string | null;      // "HH:MM:SS"
  /** UC-88 — tên múi giờ IANA. Quyết định "hôm nay" cho streak, mục tiêu ngày
   *  và thử thách ngày. Sai múi giờ là sai luôn cả ba. */
  timezone: string;
  profile_visibility: string;
  daily_item_goal: number | null;
  daily_xp_goal: number | null;
  target_cefr_level: string | null;
  entry_cefr_level: string | null;
}

const KEY = ['user-settings'];

export function useSettings() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => apiGet<UserSettings>('/api/v1/users/me/settings'),
  });
}

/** UC-09 — chỉ gửi field cần đổi. */
export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Pick<UserSettings,
      'dark_mode' | 'ui_language' | 'reminder_time' | 'timezone' | 'profile_visibility'>>) =>
      apiPut<UserSettings>('/api/v1/users/me/settings', body),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  });
}

/** UC-10 — mục tiêu học. */
export function useUpdateGoals() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Pick<UserSettings,
      'daily_item_goal' | 'daily_xp_goal' | 'target_cefr_level' | 'entry_cefr_level'>>) =>
      apiPut<UserSettings>('/api/v1/users/me/goals', body),
    onSuccess: (data) => {
      qc.setQueryData(KEY, data);
      qc.invalidateQueries({ queryKey: ['dashboard'] });
      qc.invalidateQueries({ queryKey: ['progress'] });
      // Đổi trình độ đầu vào -> lộ trình (UC-84) và điều kiện nâng mức (UC-85) đổi theo
      qc.invalidateQueries({ queryKey: ['roadmap'] });
      qc.invalidateQueries({ queryKey: ['level-up'] });
    },
  });
}

/** UC-07 — đổi mật khẩu. */
export function useChangePassword() {
  return useMutation({
    mutationFn: (body: {
      current_password: string; new_password: string; new_password_confirm: string;
    }) => apiPost<void>('/api/v1/users/me/password', body),
  });
}
