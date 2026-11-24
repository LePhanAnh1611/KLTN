import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import type { MatchingRound } from '../../types/session';
import { roundScore, useGameSession } from './useGameSession';

/** UC-94 — Ghép cặp tốc độ. Ghép từ với nghĩa cho hết bảng trước khi hết giờ.
 *
 * Dạng bài thật: `matching` (nhận diện) — cùng loại với UC-28.
 *
 * Ghép SAI vẫn là một lượt trả lời và vẫn được ghi (BR-05). Nếu chỉ ghi lượt
 * đúng thì DKT sẽ thấy một người học không bao giờ nhầm.
 */

const ROUND_MS = 60000;
const TICK_MS = 100;
const WRONG_PENALTY_MS = 3000;   // ghép sai bị trừ thời gian, không trừ điểm âm

interface Props {
  round: MatchingRound;
  wordSetId: number;
  onFinish: (score: number) => void;
}

function WordMatch({ round, wordSetId, onFinish }: Props) {
  const game = useGameSession('game_match');
  const [ready, setReady] = useState(false);
  const [left, setLeft] = useState(ROUND_MS);
  const [score, setScore] = useState(0);
  const [streak, setStreak] = useState(0);
  const [pickedWord, setPickedWord] = useState<number | null>(null);
  const [cleared, setCleared] = useState<Set<number>>(new Set());
  const [wrongPair, setWrongPair] = useState<string | null>(null);

  const sid = useRef<number | null>(null);
  const pickedAt = useRef<number>(Date.now());
  const done = useRef(false);
  const finalScoreRef = useRef(0);
  const deadline = useRef(0);
  const answering = useRef(false);

  const meanings = useMemo(
    () => round.shuffled_meanings.map((m) => ({
      meaning: m,
      itemId: round.pairs.find((p) => p.meaning === m)?.item_id ?? -1,
    })),
    [round],
  );

  useEffect(() => {
    let alive = true;
    game.start(wordSetId).then((id) => {
      if (!alive) return;
      sid.current = id;
      deadline.current = Date.now() + ROUND_MS;
      setReady(true);
    }).catch(() => {}); // The hook exposes the error for display below.
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const end = useCallback(async (finalScore: number) => {
    if (done.current) return;
    done.current = true;
    finalScoreRef.current = finalScore;
    if (sid.current === null || !await game.finish(sid.current)) return;
    onFinish(finalScore);
  }, [game, onFinish]);

  useEffect(() => {
    if (!ready || done.current) return undefined;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, deadline.current - Date.now());
      setLeft(remaining);
      if (!remaining) void end(score);
    }, TICK_MS);
    return () => window.clearInterval(timer);
  }, [ready, end, score]);

  const pickWord = (itemId: number) => {
    if (cleared.has(itemId)) return;
    setPickedWord(itemId);
    answering.current = false;
    setWrongPair(null);
    pickedAt.current = Date.now();
  };

  const pickMeaning = (meaning: string, itemId: number) => {
    if (done.current || answering.current || pickedWord === null || cleared.has(itemId)) return;
    answering.current = true;
    const spent = Date.now() - pickedAt.current;
    const correct = pickedWord === itemId;

    if (sid.current !== null) void game.answer(sid.current, pickedWord, correct, spent, meaning);

    if (correct) {
      const nextStreak = streak + 1;
      const gained = roundScore(1 - Math.min(1, spent / 6000), nextStreak);
      const nextCleared = new Set(cleared).add(itemId);
      setCleared(nextCleared);
      setStreak(nextStreak);
      const total = score + gained;
      setScore(total);
      if (nextCleared.size >= round.pairs.length) {
        void end(total + Math.round(left / 100));
      }
    } else {
      setStreak(0);
      setWrongPair(meaning);
      deadline.current -= WRONG_PENALTY_MS;
      setLeft((ms) => Math.max(0, ms - WRONG_PENALTY_MS));
    }
    setPickedWord(null);
  };

  if (done.current) {
    return <Stack spacing={2}>
      {game.saving ? <LinearProgress /> : <>
        <Alert severity="error">{game.error || 'Chưa lưu xong kết quả. Đáp án vẫn được giữ để gửi lại.'}</Alert>
        <Button onClick={() => { done.current = false; void end(finalScoreRef.current); }}>Thử lưu lại</Button>
      </>}
    </Stack>;
  }
  if (!ready && game.error) return <Alert severity="error">{game.error}</Alert>;
  if (!ready) return <LinearProgress sx={{ mt: 4 }} />;

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 1.5, alignItems: 'center' }}>
        <Chip label={`Điểm ${score}`} color="primary" />
        {streak > 1 && <Chip label={`Chuỗi ×${streak}`} color="warning" />}
        <Box sx={{ flexGrow: 1 }} />
        <Typography variant="body2" color="text.secondary">
          còn {cleared.size}/{round.pairs.length} · {Math.ceil(left / 1000)}s
        </Typography>
        {/* Dừng sớm — cùng cách xử lý như WordRain: chỉ các lượt đã trả lời được ghi. */}
        <Button size="small" color="inherit" variant="outlined" onClick={() => void end(score)}>
          Kết thúc ván
        </Button>
      </Stack>

      <LinearProgress
        variant="determinate" value={(left / ROUND_MS) * 100}
        color={left < ROUND_MS * 0.25 ? 'error' : 'primary'}
        sx={{ mb: 2 }}
      />

      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
        <Stack spacing={1}>
          <Typography variant="overline" color="text.secondary">Từ</Typography>
          {round.pairs.map((p) => (
            <Button
              key={p.item_id} fullWidth
              variant={pickedWord === p.item_id ? 'contained' : 'outlined'}
              color={cleared.has(p.item_id) ? 'success' : 'primary'}
              disabled={cleared.has(p.item_id)}
              onClick={() => pickWord(p.item_id)}
            >
              {p.word}
            </Button>
          ))}
        </Stack>

        <Stack spacing={1}>
          <Typography variant="overline" color="text.secondary">Nghĩa</Typography>
          {meanings.map((m) => (
            <Button
              key={m.meaning} fullWidth variant="outlined"
              color={
                cleared.has(m.itemId) ? 'success' : wrongPair === m.meaning ? 'error' : 'inherit'
              }
              disabled={cleared.has(m.itemId)}
              onClick={() => pickMeaning(m.meaning, m.itemId)}
              sx={{ justifyContent: 'flex-start', textAlign: 'left' }}
            >
              {m.meaning}
            </Button>
          ))}
        </Stack>
      </Box>

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
        Chọn một từ rồi chọn nghĩa của nó. Ghép sai bị trừ {WRONG_PENALTY_MS / 1000} giây.
      </Typography>
    </Box>
  );
}

export default WordMatch;
