import { useQuery } from '@tanstack/react-query';

import type {
  ActiveSession,
  AnswerInput,
  ClozeQuestion,
  MatchingRound,
  QuizQuestion,
  ResumableSession,
  SessionHistoryResponse,
  SessionSummary,
  StudyMode,
  StudySession,
  TypingQuestion,
} from '../types/session';
import type { RecommendedItem } from '../types/wordSet';
import { apiGet, apiPost } from './client';

export function getRecommend(wordSetId: number, limit = 20): Promise<RecommendedItem[]> {
  return apiGet<RecommendedItem[]>(`/api/v1/word-sets/${wordSetId}/recommend?limit=${limit}`);
}

/**
 * Nội dung phiên "Học N từ mới" mở từ trang chủ: ĐÚNG các từ trang chủ đã gợi ý
 * (có thể thuộc nhiều bộ), server không chọn lại — chỉ trộn từ thăm dò bằng phép
 * thay nên số từ không đổi.
 */
export function getTodayStudyItems(itemIds: number[]): Promise<RecommendedItem[]> {
  if (itemIds.length === 0) return Promise.resolve([]);
  return apiGet<RecommendedItem[]>(`/api/v1/recommendations/today/items?ids=${itemIds.join(',')}`);
}

/** Pilot — câu chọn nghĩa cho đúng các từ sắp học/ôn (chấm khách quan thay vì tự khai). */
export function getQuizForItems(itemIds: number[]): Promise<QuizQuestion[]> {
  if (itemIds.length === 0) return Promise.resolve([]);
  return apiPost<QuizQuestion[]>('/api/v1/sessions/quiz-questions', { item_ids: itemIds });
}

/** `wordSetId = null` → phiên xuyên thư viện (ôn tập, hoặc "Học từ mới" từ trang chủ). */
export function createSession(
  wordSetId: number | null, mode: StudyMode, practiceOnly = false,
): Promise<StudySession> {
  return apiPost<StudySession>('/api/v1/sessions', {
    word_set_id: wordSetId, mode, practice_only: practiceOnly,
  });
}

/** Phiên dở của một bộ; `wordSetId = null` → phiên dở xuyên thư viện của `mode`. */
export function getActiveSession(wordSetId: number | null, mode?: StudyMode): Promise<ActiveSession> {
  const query = wordSetId != null ? `word_set_id=${wordSetId}` : `mode=${mode}`;
  return apiGet<ActiveSession>(`/api/v1/sessions/active?${query}`);
}

export function recordAnswer(sessionId: number, data: AnswerInput): Promise<unknown> {
  return apiPost(`/api/v1/sessions/${sessionId}/answer`, data);
}

export function completeSession(sessionId: number): Promise<SessionSummary> {
  return apiPost<SessionSummary>(`/api/v1/sessions/${sessionId}/complete`, {});
}

export function abandonSession(sessionId: number): Promise<unknown> {
  return apiPost(`/api/v1/sessions/${sessionId}/abandon`, {});
}

export function getQuiz(wordSetId: number, limit = 10): Promise<QuizQuestion[]> {
  return apiGet<QuizQuestion[]>(`/api/v1/word-sets/${wordSetId}/quiz?limit=${limit}`);
}

/** UC-28 — bài điền khuyết dựng từ câu ví dụ. */
export function getCloze(wordSetId: number, limit = 10): Promise<ClozeQuestion[]> {
  return apiGet<ClozeQuestion[]>(`/api/v1/word-sets/${wordSetId}/cloze?limit=${limit}`);
}

/** UC-89 — bài gõ từ. */
export function getTyping(wordSetId: number, limit = 10): Promise<TypingQuestion[]> {
  return apiGet<TypingQuestion[]>(`/api/v1/word-sets/${wordSetId}/typing?limit=${limit}`);
}

/** UC-28 — một lượt ghép cặp từ ↔ nghĩa. */
export function getMatching(wordSetId: number): Promise<MatchingRound> {
  return apiGet<MatchingRound>(`/api/v1/word-sets/${wordSetId}/matching`);
}

/** UC-45 — nhật ký học tập. */
export function useSessionHistory(page: number, pageSize = 10) {
  return useQuery({
    queryKey: ['sessions', 'history', page, pageSize],
    queryFn: () => apiGet<SessionHistoryResponse>(
      `/api/v1/sessions/history?page=${page}&page_size=${pageSize}`,
    ),
  });
}

/** Phiên đang dở gần nhất — trang chủ mời học tiếp (UC-31). */
export function useResumableSession() {
  return useQuery({
    queryKey: ['sessions', 'resume'],
    queryFn: () => apiGet<ResumableSession | null>('/api/v1/sessions/resume'),
  });
}
