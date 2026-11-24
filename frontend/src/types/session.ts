export type StudyMode =
  | 'flashcard' | 'quiz' | 'cloze' | 'typing' | 'dictation'
  /** UC-91 — phiên trộn: xen kẽ nhận diện (trắc nghiệm) và nhớ chủ động (gõ từ). */
  | 'mixed'
  | 'matching' | 'dkt_smart' | 'sm2'
  /** UC-94 — chế độ trò chơi. KHÔNG phải dạng bài mới: server ánh xạ mỗi trò về
   *  một dạng bài đã có khi ghi INTERACTION (rain→typing, spelling→dictation,
   *  match→matching), nên client không gửi `exercise_format` cho các chế độ này. */
  | 'game_rain' | 'game_spelling' | 'game_match';

export type Sm2Rating = 'again' | 'hard' | 'good' | 'easy';

export interface StudySession {
  id: number;
  word_set_id: number | null;
  mode: string | null;
  /** UC-35 — phiên luyện thường: không đụng tới lịch ôn. */
  practice_only: boolean;
  status: string;
  started_at: string;
  ended_at: string | null;
  item_count: number | null;
  correct_count: number | null;
}

export interface ActiveSession {
  session: StudySession | null;
  answered_item_ids: number[];
}

export interface AnswerInput {
  client_answer_id?: string;
  item_id: number;
  is_correct: boolean;
  answer?: string;
  response_time_ms?: number | null;
  exercise_format?: string | null;
  sm2_rating?: Sm2Rating | null;
  /** Pilot — gửi lại `RecommendedItem.selection` (chỉ ở phiên Học thông minh) */
  selection_reason?: 'band' | 'explore' | null;
}

export interface WrongItem {
  item_id: number;
  word: string;
  meaning: string;
}

export interface SessionSummary {
  session_id: number;
  total_answered: number;
  correct_count: number;
  wrong_count: number;
  accuracy: number;
  duration_seconds: number;
  mastered_count: number;
  xp_earned: number;
  /** Chuỗi ngày học sau phiên này (UC-47). */
  streak_count: number;
  /** True khi đây là phiên đầu tiên trong ngày — chuỗi vừa +1. */
  streak_extended: boolean;
  new_achievements: string[];
  wrong_items: WrongItem[];
}

export interface QuizQuestion {
  item_id: number;
  word: string;
  options: string[];
  correct_index: number;
}

/** UC-28 — điền khuyết. */
export interface ClozeQuestion {
  item_id: number;
  sentence: string;
  answer: string;
  hint: string;
}

/** UC-89 — gõ từ: thấy nghĩa tiếng Việt, tự gõ lại từ tiếng Anh.
 *
 *  Khác trắc nghiệm (nhận diện đáp án bày sẵn) và khác điền khuyết (đòi câu ví
 *  dụ chứa chính từ đó) — dạng này chạy được trên mọi bộ từ. */
export interface TypingQuestion {
  item_id: number;
  meaning: string;
  answer: string;
  part_of_speech: string | null;
  first_letter: string;
  length: number;
}

/** UC-28 — ghép cặp. */
export interface MatchPair {
  item_id: number;
  word: string;
  meaning: string;
}

export interface MatchingRound {
  pairs: MatchPair[];
  shuffled_meanings: string[];
}

/** UC-45 — một dòng nhật ký học tập. */
export interface SessionHistoryRow {
  id: number;
  mode: string | null;
  status: string;
  word_set_id: number | null;
  word_set_name: string | null;
  started_at: string;
  ended_at: string | null;
  item_count: number;
  correct_count: number;
  accuracy: number;
  xp_earned: number;
  duration_seconds: number | null;
}

export interface SessionHistoryResponse {
  items: SessionHistoryRow[];
  total: number;
  page: number;
  page_size: number;
  total_sessions: number;
  total_items_answered: number;
  total_xp: number;
}

/** Phiên đang dở gần nhất (UC-31) — null nếu không có. */
export interface ResumableSession {
  session_id: number;
  mode: string | null;
  word_set_id: number | null;
  word_set_name: string | null;
  started_at: string;
  answered_count: number;
}
