import { useCallback, useRef, useState } from 'react';

import { completeSession, createSession, recordAnswer } from '../../api/sessions';
import type { StudyMode } from '../../types/session';
import { AnswerQueue } from './answerQueue';

/** UC-94 — vòng đời một ván chơi.
 *
 * Ba trò dùng chung hook này vì phần *nghiệp vụ* của chúng giống hệt nhau và
 * chỉ khác cách trình bày: mở phiên học → mỗi lượt trả lời gửi lên server →
 * đóng phiên → nộp điểm.
 *
 * Điểm phải giữ đúng: **mọi lượt trả lời đều gửi lên server** (BR-05), kể cả
 * lượt sai và lượt hết giờ. Bỏ qua lượt sai sẽ làm DKT chỉ thấy phần đẹp của
 * lịch sử và ước lượng mastery cao hơn thực tế.
 *
 * Dạng bài KHÔNG gửi từ đây: server tự suy từ chế độ phiên (`game_*`). Xem
 * `game_service._exercise_format` — gửi từ client là chỗ dễ sai âm thầm.
 */
export function useGameSession(sessionMode: StudyMode) {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [pending, setPending] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const queue = useRef<AnswerQueue | null>(null);
  const startPromise = useRef<Promise<number> | null>(null);
  const startedAt = useRef<number>(0);

  const start = useCallback((wordSetId: number) => {
    if (!startPromise.current) {
      startPromise.current = createSession(wordSetId, sessionMode).then((session) => {
        queue.current = new AnswerQueue((data) => recordAnswer(session.id, data), setPending);
        setSessionId(session.id);
        startedAt.current = Date.now();
        return session.id;
      }).catch((cause) => {
        startPromise.current = null;
        setError(cause instanceof Error ? cause.message : 'Không mở được phiên chơi.');
        throw cause;
      });
    }
    return startPromise.current;
  }, [sessionMode]);

  /** Ghi một lượt. Lỗi mạng KHÔNG được làm sập ván đang chơi. */
  const answer = useCallback(
    (id: number, itemId: number, isCorrect: boolean, responseMs: number, submittedAnswer: string) => {
      if (!queue.current) throw new Error(`Phiên ${id} chưa sẵn sàng.`);
      queue.current.enqueue({
        item_id: itemId,
        is_correct: isCorrect,
        answer: submittedAnswer,
        response_time_ms: Math.max(0, Math.round(responseMs)),
      });
      return queue.current.flush().catch((cause) => {
        setError(cause instanceof Error ? cause.message : 'Chưa lưu được đáp án.');
      });
    },
    [],
  );

  const finish = useCallback(async (id: number) => {
    setSaving(true);
    setError(null);
    try {
      await queue.current?.flush();
      const result = await completeSession(id);
      setSessionId(null);
      return result;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Chưa lưu được kết quả.');
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  return { sessionId, start, answer, finish, pending, startedAt, error, saving };
}

/** Điểm một lượt đúng: điểm nền + thưởng tốc độ + thưởng chuỗi.
 *
 * Ba trò dùng chung một công thức để điểm giữa các trò còn so được với nhau.
 * `speedRatio` = phần thời gian còn lại (1 = trả lời tức thì, 0 = sát giờ).
 */
export const BASE_POINTS = 100;
export const MAX_SPEED_BONUS = 100;
export const STREAK_BONUS = 20;
export const MAX_STREAK_BONUS = 200;

export function roundScore(speedRatio: number, streak: number): number {
  const speed = Math.round(MAX_SPEED_BONUS * Math.max(0, Math.min(1, speedRatio)));
  const bonus = Math.min(MAX_STREAK_BONUS, STREAK_BONUS * Math.max(0, streak - 1));
  return BASE_POINTS + speed + bonus;
}
