export interface ReviewItem {
  item_id: number;
  word: string;
  meaning: string;
  word_set_id: number;
  word_set_name: string;
  next_review_at: string;
  interval_days: number;
  scheduled_for: string | null;
  mastery: number | null;
  at_risk: boolean;
}

export interface ReviewCalendar {
  today: ReviewItem[];
  tomorrow: ReviewItem[];
  this_week: ReviewItem[];
  daily_limit: number;
  reviewed_today: number;
  backlog_count: number;
  estimated_minutes: number;
  lower_level_count: number;
  entry_level: string;
}

/** UC-86 — từ mastery thấp; không có next_review_at vì không dựa vào lịch ôn. */
export interface WeakReviewItem {
  item_id: number;
  word: string;
  meaning: string;
  word_set_id: number;
  word_set_name: string;
  mastery: number;
}
