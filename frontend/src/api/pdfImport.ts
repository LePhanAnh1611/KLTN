import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import type { WordSet } from '../types/wordSet';
import { apiGet, apiPost, apiPostForm } from './client';

/** UC-87 — tạo bộ từ từ tài liệu PDF.
 *
 * Luồng HAI bước: `useExtractPdf` chỉ trích để xem trước (không ghi gì vào thư
 * viện), người học bỏ từ rác xong mới gọi `useCreateWordSetFromPdf`. Vì bước 1
 * không có state phía máy chủ nên danh sách ứng viên do trang này giữ. */

export const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'] as const;
export type CefrLevel = (typeof CEFR_LEVELS)[number];

export interface PdfCandidateWord {
  /** Từ điển hình (lemma) — thứ được đưa vào bộ từ. */
  word: string;
  lemma: string;
  /** Dạng đúng như tài liệu viết, VD "absorbs" cho từ "absorb". */
  surface_form: string;
  part_of_speech: string | null;
  /** null = wordlist chuẩn không có từ này. Hệ thống KHÔNG đoán mức. */
  cefr_level: string | null;
  /** null = chưa gán được chủ đề (Ollama không sẵn sàng). */
  topic: string | null;
  example_sentence: string | null;
  occurrences: number;
}

export interface PdfExtractResponse {
  filename: string;
  page_count: number;
  total_words: number;
  topics_available: boolean;
  warnings: string[];
  candidates: PdfCandidateWord[];
}

export interface PdfDependency {
  name: string;
  ready: boolean;
  detail: string;
}

export interface PdfImportHealth {
  ready: boolean;
  dependencies: PdfDependency[];
  max_file_mb: number;
  max_pages: number;
  max_words: number;
  cefr_source: string;
  cefr_word_count: number;
}

export interface PdfWordSelection {
  word: string;
  lemma?: string | null;
  part_of_speech?: string | null;
  meaning: string;
  example?: string | null;
  cefr_level?: string | null;
  topic?: string | null;
}

export interface WordSetFromPdfInput {
  name: string;
  description?: string | null;
  category?: string | null;
  difficulty?: string | null;
  source_filename?: string | null;
  words: PdfWordSelection[];
}

export function usePdfImportHealth() {
  return useQuery({
    queryKey: ['pdf-import', 'health'],
    queryFn: () => apiGet<PdfImportHealth>('/api/v1/word-sets/pdf-import/health'),
    staleTime: 60_000,
  });
}

export function useExtractPdf() {
  return useMutation({
    mutationFn: ({ file, cefrLevels }: { file: File; cefrLevels: string[] }) => {
      const form = new FormData();
      form.append('file', file);
      if (cefrLevels.length > 0) form.append('cefr_levels', cefrLevels.join(','));
      return apiPostForm<PdfExtractResponse>('/api/v1/word-sets/extract-pdf', form);
    },
  });
}

export function useCreateWordSetFromPdf() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WordSetFromPdfInput) =>
      apiPost<WordSet>('/api/v1/word-sets/from-pdf', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['word-sets'] }),
  });
}
