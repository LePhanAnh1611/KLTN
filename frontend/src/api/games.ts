import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiGet, apiPost } from './client';

/** UC-94 — trò chơi từ vựng.
 *
 * `exercise_format` được backend trả ra để thấy rõ: trò chơi KHÔNG phải dạng
 * bài mới, mỗi trò ánh xạ về một dạng bài mô hình đã được huấn luyện. Mọi lượt
 * trả lời vẫn đi qua luồng phiên học và ghi INTERACTION (BR-05).
 */
export interface GameDefinition {
  key: 'rain' | 'spelling' | 'match';
  name: string;
  description: string;
  session_mode: string;
  exercise_format: string;
  source: 'typing' | 'matching';
  best_score: number | null;
  plays: number;
}

export interface GameScoreResult {
  game: string;
  score: number;
  best_score: number;
  is_new_best: boolean;
  plays: number;
  rank: number;
}

export interface GameLeaderboardRow {
  rank: number;
  user_id: number;
  display_name: string;
  best_score: number;
  best_at: string;
}

export function useGames() {
  return useQuery({
    queryKey: ['games'],
    queryFn: () => apiGet<GameDefinition[]>('/api/v1/games'),
  });
}

export function useGameLeaderboard(key: string | null) {
  return useQuery({
    queryKey: ['games', key, 'leaderboard'],
    queryFn: () => apiGet<GameLeaderboardRow[]>(`/api/v1/games/${key}/leaderboard`),
    enabled: key != null,
  });
}

export function useSubmitScore(key: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (score: number) =>
      apiPost<GameScoreResult>(`/api/v1/games/${key}/scores`, { score }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['games'] });
    },
  });
}
