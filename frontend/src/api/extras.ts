import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiDelete, apiGet, apiPatch, apiPost, apiPostForm, apiPut } from './client';

/** Gom các tính năng bổ sung dùng chung một lớp gọi API:
 *  UC-32 đánh dấu từ khó · UC-44 thử thách · UC-56/57 bạn bè & chia sẻ tiến độ
 *  · UC-37/38 luyện viết & sổ tay · lưu kết quả phát âm · UC-12 xóa tài khoản. */

// ---------------------------------------------------------------- UC-32

export interface FlaggedItem {
  item_id: number;
  word: string;
  meaning: string;
  word_set_id: number;
  word_set_name: string;
  note: string | null;
  /** null = chưa từng học từ này nên chưa có mastery để đối chiếu. */
  mastery: number | null;
  flagged_at: string;
}

export function useFlaggedItems() {
  return useQuery({
    queryKey: ['flagged-items'],
    queryFn: () => apiGet<FlaggedItem[]>('/api/v1/me/flagged-items'),
  });
}

export function useSetItemFlag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, note }: { itemId: number; note?: string | null }) =>
      apiPut(`/api/v1/me/flagged-items/${itemId}`, { note: note ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['flagged-items'] }),
  });
}

export function useClearItemFlag() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (itemId: number) => apiDelete(`/api/v1/me/flagged-items/${itemId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['flagged-items'] }),
  });
}

// ---------------------------------------------------------------- UC-44

export interface ChallengeItem {
  code: string;
  title: string;
  description: string;
  target: number;
  progress: number;
  completed: boolean;
  claimed: boolean;
  xp_reward: number;
}

export interface DailyChallenges {
  date: string;
  items: ChallengeItem[];
  claimable_count: number;
}

export function useDailyChallenges() {
  return useQuery({
    queryKey: ['challenges', 'today'],
    queryFn: () => apiGet<DailyChallenges>('/api/v1/challenges/today'),
  });
}

export function useClaimChallenge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      apiPost<DailyChallenges>(`/api/v1/challenges/${code}/claim`, {}),
    onSuccess: (data) => {
      qc.setQueryData(['challenges', 'today'], data);
      // XP đổi -> mọi chỗ hiện XP phải nạp lại
      qc.invalidateQueries({ queryKey: ['progress'] });
      qc.invalidateQueries({ queryKey: ['home'] });
    },
  });
}

// ---------------------------------------------------------------- UC-56/57

export type FriendStatus = 'self' | 'none' | 'pending' | 'accepted';

export interface FriendshipState {
  status: FriendStatus;
  friendship_id: number | null;
  /** true = lời mời đang chờ TÔI trả lời. */
  is_incoming: boolean;
}

export interface FriendRow {
  user_id: number;
  display_name: string;
  avatar_url: string | null;
  level: number;
  level_title: string;
  xp: number;
  streak_count: number;
}

export interface FriendRequestRow {
  friendship_id: number;
  user_id: number;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
}

export function useFriends() {
  return useQuery({
    queryKey: ['friends'],
    queryFn: () => apiGet<FriendRow[]>('/api/v1/community/friends'),
  });
}

export function useFriendRequests() {
  return useQuery({
    queryKey: ['friends', 'requests'],
    queryFn: () => apiGet<FriendRequestRow[]>('/api/v1/community/friends/requests'),
  });
}

export function useFriendshipState(userId: number | null) {
  return useQuery({
    queryKey: ['friends', 'state', userId],
    queryFn: () => apiGet<FriendshipState>(`/api/v1/community/friends/state/${userId}`),
    enabled: userId !== null,
  });
}

export interface UserSearchRow {
  user_id: number;
  display_name: string;
  avatar_url: string | null;
  friendship: FriendshipState;
}

/** UC-56 — tìm người để kết bạn theo tên (≥ 2 ký tự) hoặc ID ("12" / "#12"). */
export function useUserSearch(q: string) {
  const term = q.trim();
  return useQuery({
    queryKey: ['friends', 'search', term],
    queryFn: () => apiGet<UserSearchRow[]>(
      `/api/v1/community/friends/search?q=${encodeURIComponent(term)}`,
    ),
    enabled: term.length > 0,
    staleTime: 10_000,
  });
}

function invalidateFriends(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ['friends'] });
  qc.invalidateQueries({ queryKey: ['notifications'] });
}

export function useSendFriendRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) =>
      apiPost<FriendshipState>(`/api/v1/community/friends/${userId}`, {}),
    onSuccess: () => invalidateFriends(qc),
  });
}

export function useRespondFriendRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) =>
      apiPost<FriendshipState>(
        `/api/v1/community/friends/requests/${id}/${accept ? 'accept' : 'decline'}`, {},
      ),
    onSuccess: () => invalidateFriends(qc),
  });
}

export function useUnfriend() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) => apiDelete(`/api/v1/community/friends/${userId}`),
    onSuccess: () => invalidateFriends(qc),
  });
}

export function useShareProgress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (message: string | null) =>
      apiPost('/api/v1/community/share-progress', { message }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['community', 'feed'] }),
  });
}

// ------------------------------------------------- Kết quả luyện phát âm

export interface PronunciationAttemptRow {
  id: number;
  item_id: number;
  word: string;
  meaning: string;
  score: number;
  transcript: string | null;
  created_at: string;
}

export interface PronunciationStats {
  total_attempts: number;
  words_practiced: number;
  average_score: number;
  best_score: number;
  recent: PronunciationAttemptRow[];
}

export function usePronunciationStats() {
  return useQuery({
    queryKey: ['pronunciation', 'stats'],
    queryFn: () => apiGet<PronunciationStats>('/api/v1/pronunciation/stats'),
  });
}

export interface ItemBestScore {
  item_id: number;
  best_score: number;
  attempts: number;
}

/** Kỷ lục phát âm từng từ trong một bộ (đọc từ + đọc câu) — lưu trên server,
 * nên F5 hay chuyển trang không làm mất tiến độ luyện. */
export function usePronunciationBestScores(wordSetId: number) {
  return useQuery({
    queryKey: ['pronunciation', 'best-scores', wordSetId],
    queryFn: () => apiGet<ItemBestScore[]>(
      `/api/v1/pronunciation/best-scores?word_set_id=${wordSetId}`,
    ),
  });
}

export function useRecordPronunciation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { item_id: number; score: number; transcript?: string | null }) =>
      apiPost<PronunciationAttemptRow>('/api/v1/pronunciation/attempts', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pronunciation'] }),
  });
}

// ---------------------------------------------------------------- UC-37/38

export interface WritingPrompt {
  item_id: number;
  word: string;
  prompt_vi: string;
  reference_en: string | null;
}

export interface WritingResult {
  id: number;
  prompt_vi: string;
  answer_en: string;
  score: number | null;
  feedback: string | null;
  suggestion: string | null;
  /** 'llm' = mô hình ngôn ngữ · 'heuristic' = bộ kiểm tra dự phòng. PHẢI hiển thị. */
  grader: string;
  created_at: string;
}

export function useWritingPrompts(wordSetId: number | null) {
  return useQuery({
    queryKey: ['writing', 'prompts', wordSetId],
    queryFn: () => apiGet<WritingPrompt[]>(
      `/api/v1/writing/prompts?word_set_id=${wordSetId}&limit=5`,
    ),
    enabled: wordSetId !== null,
    retry: false,      // bộ từ vựng chưa có câu ví dụ -> 400, thử lại cũng vô ích
  });
}

export function useWritingSubmissions() {
  return useQuery({
    queryKey: ['writing', 'submissions'],
    queryFn: () => apiGet<WritingResult[]>('/api/v1/writing/submissions'),
  });
}

export function useSubmitWriting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { prompt_vi: string; answer_en: string }) =>
      apiPost<WritingResult>('/api/v1/writing/submissions', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['writing', 'submissions'] }),
  });
}

export interface NoteRow {
  id: number;
  text_en: string;
  text_vi: string | null;
  note: string | null;
  submission_id: number | null;
  created_at: string;
}

export function useNotes(q: string) {
  return useQuery({
    queryKey: ['notes', q],
    queryFn: () => apiGet<NoteRow[]>(`/api/v1/notes${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      text_en: string; text_vi?: string | null; note?: string | null;
      submission_id?: number | null;
    }) => apiPost<NoteRow>('/api/v1/notes', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number; note?: string | null; text_en?: string }) =>
      apiPatch<NoteRow>(`/api/v1/notes/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/api/v1/notes/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  });
}

// ---------------------------------------------------------------- UC-12

export function useDeleteAccount() {
  return useMutation({
    mutationFn: (password: string) =>
      apiDelete('/api/v1/users/me', { password, confirm: true }),
  });
}

// ------------------------------------------- Đọc câu mẫu (máy chủ chấm)

export interface WordCheck {
  expected: string;
  heard: string | null;
  ok: boolean;
  confidence: number | null;
}

export interface ReadAloudAspect {
  key: 'accuracy' | 'clarity' | 'fluency';
  label: string;
  level: number;
  level_label: string;
  detail: string;
  suggestion: string;
}

export interface ReadAloudResult {
  attempt_id: number | null;
  item_id: number;
  word: string;
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
}

/** Đúng những trường backend lưu vào cột `detail` — KHÔNG gồm transcript và
 *  target_text, hai cái đó nằm ở cột riêng để truy vấn được. */
export interface ReadAloudDetail {
  overall_level: number;
  accuracy: number;
  clarity: number;
  missed_words: string[];
  extra_words: string[];
  words: WordCheck[];
  aspects: ReadAloudAspect[];
  audio_metrics: Record<string, number>;
  feedback: string;
  warnings: string[];
}

export interface ItemAttemptRow {
  id: number;
  item_id: number;
  word: string;
  kind: 'word' | 'sentence';
  score: number;
  transcript: string | null;
  target_text: string | null;
  /** Chỉ có ở kind='sentence'; luyện từ chấm ở trình duyệt nên không có chi tiết. */
  detail: ReadAloudDetail | null;
  created_at: string;
}

/** Lịch sử luyện của MỘT từ — nguồn sự thật cho kết quả đã chấm.
 *
 * Màn luyện đọc từ đây chứ không giữ kết quả trong state, nên chuyển tab rồi
 * quay lại vẫn thấy lần chấm gần nhất. */
export function useItemAttempts(itemId: number | null) {
  return useQuery({
    queryKey: ['pronunciation', 'item-attempts', itemId],
    queryFn: () => apiGet<ItemAttemptRow[]>(
      `/api/v1/pronunciation/items/${itemId}/attempts`,
    ),
    enabled: itemId !== null,
  });
}

export function useReadAloud() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blob, itemId }: { blob: Blob; itemId: number }) => {
      const form = new FormData();
      form.append('audio', blob, 'doc-cau.webm');
      form.append('item_id', String(itemId));
      return apiPostForm<ReadAloudResult>('/api/v1/pronunciation/read-aloud', form);
    },
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: ['pronunciation', 'item-attempts', variables.itemId],
      });
      qc.invalidateQueries({ queryKey: ['pronunciation', 'stats'] });
      // đọc câu cũng tính là đã luyện từ → cập nhật thống kê đầu trang
      qc.invalidateQueries({ queryKey: ['pronunciation', 'best-scores'] });
    },
  });
}
