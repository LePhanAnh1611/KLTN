export interface DashboardData {
  xp: number;
  level: number;
  xp_into_level: number;
  xp_for_next_level: number;
  streak_count: number;
  items_mastered: number;
  word_set_count: number;
  review_due_count: number;
  daily_item_goal: number | null;
}
