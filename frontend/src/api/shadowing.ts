import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPatch, apiPostForm, apiPut } from './client';
import type { ReadAloudAspect, WordCheck } from './extras';

/** UC-97 — Shadowing theo phụ đề video YouTube.
 *
 * Câu gốc do máy chủ lấy theo `segment_index`; frontend chỉ gửi bản ghi âm. */

export interface ShadowingSegment {
  index: number;
  start: number;
  end: number;
  text: string;
  words_per_minute: number | null;
}

export interface SegmentProgress {
  index: number;
  attempts: number;
  best_accuracy: number | null;
  passed: boolean;
}

export interface ShadowingVideoCard {
  id: number;
  youtube_id: string;
  title: string;
  channel: string | null;
  topic: string | null;
  cefr_level: string | null;
  words_per_minute: number | null;
  duration_sec: number | null;
  segment_count: number;
  source: 'catalog' | 'user';
  license: string | null;
  attribution: string | null;
  passed_count: number;
}

export interface VocabProfile {
  level: string | null;
  total_words: number;
  known_words: number;
  known_ratio: number;
  by_level: Record<string, number>;
  coverage_threshold: number;
  source: string;
}

export interface ShadowingVideoDetail extends ShadowingVideoCard {
  caption_kind: 'manual' | 'generated' | 'upload';
  segments: ShadowingSegment[];
  vocab_profile: VocabProfile | null;
  progress: SegmentProgress[];
  pass_accuracy: number;
}

export interface ShadowingTopics {
  topics: string[];
  levels: string[];
  licenses: string[];
}

export interface ShadowingAttemptResult {
  attempt_id: number;
  video_id: number;
  segment_index: number;
  expected_text: string;
  transcript: string;
  accuracy: number;
  clarity: number;
  overall_level: number;
  aspects: ReadAloudAspect[];
  words: WordCheck[];
  missed_words: string[];
  extra_words: string[];
  audio_metrics: Record<string, number>;
  feedback: string;
  warnings: string[];
  learner_wpm: number | null;
  original_wpm: number | null;
  speed_ratio: number | null;
  speed_feedback: string | null;
  passed: boolean;
  pass_accuracy: number;
}

export const LICENSE_LABELS: Record<string, string> = {
  'public-domain': 'Phạm vi công cộng',
  'cc-by': 'Creative Commons BY',
  'cc-by-sa': 'Creative Commons BY-SA',
  'youtube-standard': 'Giấy phép YouTube chuẩn',
};

export const CAPTION_LABELS: Record<string, string> = {
  manual: 'Phụ đề do người đăng tạo',
  generated: 'Phụ đề tự động',
  upload: 'Phụ đề tải lên',
};

export function thumbnailUrl(youtubeId: string): string {
  return `https://i.ytimg.com/vi/${youtubeId}/mqdefault.jpg`;
}

export function useShadowingTopics() {
  return useQuery({
    queryKey: ['shadowing', 'topics'],
    queryFn: () => apiGet<ShadowingTopics>('/api/v1/shadowing/topics'),
    staleTime: Infinity,
  });
}

export function useShadowingVideos(topic: string | null, level: string | null) {
  const params = new URLSearchParams();
  if (topic) params.set('topic', topic);
  if (level) params.set('level', level);
  const qs = params.toString();
  return useQuery({
    queryKey: ['shadowing', 'videos', topic, level],
    queryFn: () => apiGet<ShadowingVideoCard[]>(`/api/v1/shadowing/videos${qs ? `?${qs}` : ''}`),
  });
}

export function useShadowingVideo(id: number) {
  return useQuery({
    queryKey: ['shadowing', 'video', id],
    queryFn: () => apiGet<ShadowingVideoDetail>(`/api/v1/shadowing/videos/${id}`),
    enabled: Number.isFinite(id),
  });
}

function videoForm(url: string, captions: File | null, extra: Record<string, string> = {}): FormData {
  const form = new FormData();
  form.append('url', url.trim());
  Object.entries(extra).forEach(([k, v]) => { if (v) form.append(k, v); });
  if (captions) form.append('captions', captions, captions.name);
  return form;
}

export function useAddShadowingVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ url, captions }: { url: string; captions: File | null }) =>
      apiPostForm<ShadowingVideoDetail>('/api/v1/shadowing/videos', videoForm(url, captions)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shadowing', 'videos'] }),
  });
}

export function useDeleteShadowingVideo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/shadowing/videos/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['shadowing', 'videos'] }),
  });
}

export function useShadowingAttempt(videoId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blob, segmentIndex }: { blob: Blob; segmentIndex: number }) => {
      const form = new FormData();
      form.append('audio', blob, 'shadowing.webm');
      return apiPostForm<ShadowingAttemptResult>(
        `/api/v1/shadowing/videos/${videoId}/segments/${segmentIndex}/attempts`, form,
      );
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['shadowing', 'video', videoId] });
      qc.invalidateQueries({ queryKey: ['shadowing', 'videos'] });
    },
  });
}

// ------------------------------------------------------------------ Admin

export interface ShadowingAdminRow extends ShadowingVideoCard {
  status: 'draft' | 'published';
  caption_kind: string;
  created_at: string;
  published_at: string | null;
}

export interface ShadowingAdminDetail extends ShadowingAdminRow {
  segments: ShadowingSegment[];
  vocab_profile: VocabProfile | null;
}

export interface ShadowingVideoUpdate {
  title?: string;
  topic?: string | null;
  license?: string | null;
  attribution?: string | null;
  segments?: { start: number; end: number; text: string }[];
}

export function useAdminShadowingVideos() {
  return useQuery({
    queryKey: ['admin', 'shadowing', 'videos'],
    queryFn: () => apiGet<ShadowingAdminRow[]>('/api/v1/admin/shadowing/videos'),
  });
}

export function useAdminShadowingVideo(id: number | null) {
  return useQuery({
    queryKey: ['admin', 'shadowing', 'video', id],
    queryFn: () => apiGet<ShadowingAdminDetail>(`/api/v1/admin/shadowing/videos/${id}`),
    enabled: id !== null,
  });
}

function useAdminInvalidate() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ['admin', 'shadowing'] });
    qc.invalidateQueries({ queryKey: ['shadowing'] });
  };
}

export function useAdminCreateShadowingVideo() {
  const invalidate = useAdminInvalidate();
  return useMutation({
    mutationFn: (v: { url: string; topic: string; license: string; attribution: string; captions: File | null }) =>
      apiPostForm<ShadowingAdminDetail>('/api/v1/admin/shadowing/videos', videoForm(v.url, v.captions, {
        topic: v.topic, license: v.license, attribution: v.attribution,
      })),
    onSuccess: invalidate,
  });
}

export function useAdminUpdateShadowingVideo() {
  const invalidate = useAdminInvalidate();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ShadowingVideoUpdate }) =>
      apiPatch<ShadowingAdminDetail>(`/api/v1/admin/shadowing/videos/${id}`, data),
    onSuccess: invalidate,
  });
}

export function useAdminShadowingStatus() {
  const invalidate = useAdminInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'draft' | 'published' }) =>
      apiPut<ShadowingAdminDetail>(`/api/v1/admin/shadowing/videos/${id}/status`, { status }),
    onSuccess: invalidate,
  });
}

export function useAdminDeleteShadowingVideo() {
  const invalidate = useAdminInvalidate();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/admin/shadowing/videos/${id}`),
    onSuccess: invalidate,
  });
}
