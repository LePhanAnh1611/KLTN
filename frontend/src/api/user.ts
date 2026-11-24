import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { UserResponse } from '../types/auth';
import type { AvatarResponse, UserUpdateRequest } from '../types/user';
import { apiGet, apiPatch, apiUpload } from './client';

function fetchProfile(): Promise<UserResponse> {
  return apiGet<UserResponse>('/api/v1/users/me');
}

export function useProfile() {
  return useQuery({ queryKey: ['profile'], queryFn: fetchProfile });
}

function updateProfile(data: UserUpdateRequest): Promise<UserResponse> {
  return apiPatch<UserResponse>('/api/v1/users/me', data);
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: (data) => {
      queryClient.setQueryData(['profile'], data);
    },
  });
}

/** UC-55 — hồ sơ công khai của một người học. */
export interface PublicProfile {
  user_id: number;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  joined_at: string | null;
  is_private: boolean;
  is_me: boolean;
  level: number | null;
  level_title: string | null;
  xp: number | null;
  streak_count: number | null;
  items_mastered: number | null;
  achievements: { code: string; name: string; description: string; unlocked: boolean }[];
}

export function usePublicProfile(userId: number | null) {
  return useQuery({
    queryKey: ['public-profile', userId],
    queryFn: () => apiGet<PublicProfile>(`/api/v1/users/${userId}/public`),
    enabled: userId != null,
  });
}

function uploadAvatar(file: File): Promise<AvatarResponse> {
  return apiUpload<AvatarResponse>('/api/v1/users/me/avatar', file);
}

export function useUploadAvatar() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadAvatar,
    onSuccess: (data) => {
      queryClient.setQueryData<UserResponse | undefined>(['profile'], (old) =>
        old ? { ...old, avatar_url: data.avatar_url } : old,
      );
    },
  });
}
