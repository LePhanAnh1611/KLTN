import { apiGet } from './client';

export interface AchievementStatus {
  code: string;
  name: string;
  description: string;
  unlocked: boolean;
  unlocked_at: string | null;
}

export function getAchievements(): Promise<AchievementStatus[]> {
  return apiGet<AchievementStatus[]>('/api/v1/achievements');
}
