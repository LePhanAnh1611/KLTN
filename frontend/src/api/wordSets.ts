import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { ImportReport, Item, ItemInput, WordSet, WordSetInput } from '../types/wordSet';
import { API_BASE_URL, apiDelete, apiGet, apiPatch, apiPost, apiUpload } from './client';
import { getToken } from './token';

// ---- Word sets ----

export function useWordSets() {
  return useQuery({
    queryKey: ['word-sets'],
    queryFn: () => apiGet<WordSet[]>('/api/v1/word-sets'),
  });
}

export function useWordSet(id: number) {
  return useQuery({
    queryKey: ['word-sets', id],
    queryFn: () => apiGet<WordSet>(`/api/v1/word-sets/${id}`),
    // Phiên "Học từ mới" mở từ trang chủ không gắn bộ nào (id = NaN)
    enabled: Number.isFinite(id) && id > 0,
  });
}

export function useCreateWordSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WordSetInput) => apiPost<WordSet>('/api/v1/word-sets', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['word-sets'] }),
  });
}

export function useUpdateWordSet(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WordSetInput) => apiPatch<WordSet>(`/api/v1/word-sets/${id}`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['word-sets'] });
      qc.invalidateQueries({ queryKey: ['word-sets', id] });
    },
  });
}

/** UC-13 — tải ảnh bìa cho bộ từ. Trả về bộ từ đã cập nhật. */
export function useUploadCover(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => apiUpload<WordSet>(`/api/v1/word-sets/${id}/cover`, file),
    onSuccess: () => invalidateCover(qc, id),
  });
}

/** UC-13 — gỡ ảnh bìa, thẻ quay về bìa sinh tự động. */
export function useDeleteCover(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiDelete(`/api/v1/word-sets/${id}/cover`),
    onSuccess: () => invalidateCover(qc, id),
  });
}

/** Bìa hiện ở 3 chỗ: thư viện, chi tiết bộ, và thẻ tiến độ ngoài Trang chủ. */
function invalidateCover(qc: ReturnType<typeof useQueryClient>, id: number) {
  qc.invalidateQueries({ queryKey: ['word-sets'] });
  qc.invalidateQueries({ queryKey: ['word-sets', id] });
  qc.invalidateQueries({ queryKey: ['home', 'courses'] });
}

export function useDeleteWordSet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/word-sets/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['word-sets'] }),
  });
}

export function usePublishWordSet(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (isPublic: boolean) =>
      apiPatch<WordSet>(`/api/v1/word-sets/${id}/publish`, { is_public: isPublic }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['word-sets'] });
      qc.invalidateQueries({ queryKey: ['word-sets', id] });
    },
  });
}

// ---- Items ----

export function useItems(wordSetId: number) {
  return useQuery({
    queryKey: ['word-sets', wordSetId, 'items'],
    queryFn: () => apiGet<Item[]>(`/api/v1/word-sets/${wordSetId}/items`),
  });
}

function invalidateSet(qc: ReturnType<typeof useQueryClient>, wordSetId: number) {
  qc.invalidateQueries({ queryKey: ['word-sets', wordSetId, 'items'] });
  qc.invalidateQueries({ queryKey: ['word-sets', wordSetId] });
  qc.invalidateQueries({ queryKey: ['word-sets'] });
}

export function useCreateItem(wordSetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ItemInput) =>
      apiPost<Item>(`/api/v1/word-sets/${wordSetId}/items`, data),
    onSuccess: () => invalidateSet(qc, wordSetId),
  });
}

export function useUpdateItem(wordSetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, data }: { itemId: number; data: ItemInput }) =>
      apiPatch<Item>(`/api/v1/word-sets/${wordSetId}/items/${itemId}`, data),
    onSuccess: () => invalidateSet(qc, wordSetId),
  });
}

export function useDeleteItem(wordSetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: number) =>
      apiDelete(`/api/v1/word-sets/${wordSetId}/items/${itemId}`),
    onSuccess: () => invalidateSet(qc, wordSetId),
  });
}

export function useImportItems(wordSetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<ImportReport> => {
      const formData = new FormData();
      formData.append('file', file);
      const token = getToken();
      const response = await fetch(
        `${API_BASE_URL}/api/v1/word-sets/${wordSetId}/items/import`,
        {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        },
      );
      const data = await response.json().catch(() => undefined);
      if (!response.ok) {
        throw new Error(typeof data?.detail === 'string' ? data.detail : 'Import thất bại');
      }
      return data as ImportReport;
    },
    onSuccess: () => invalidateSet(qc, wordSetId),
  });
}
