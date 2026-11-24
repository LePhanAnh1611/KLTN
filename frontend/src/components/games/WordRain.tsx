import { useCallback, useEffect, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

import type { TypingQuestion } from '../../types/session';
import { roundScore, useGameSession } from './useGameSession';
import { HeartIcon } from '../icons';

/** UC-94 — Mưa từ. Nghĩa tiếng Việt rơi xuống, gõ từ tiếng Anh trước khi chạm đáy.
 *
 * Dạng bài thật: `typing` (nhớ chủ động) — cùng loại với UC-89, chỉ thêm áp lực
 * thời gian. Đó là lý do trò này không cần mô hình học lại gì: DKT đã biết định
 * giá độ khó của dạng gõ từ.
 */

const FALL_MS = 9000;      // thời gian một từ rơi từ đỉnh xuống đáy
const LIVES = 3;
const TICK_MS = 50;

interface Props {
  questions: TypingQuestion[];
  wordSetId: number;
  onFinish: (score: number) => void;
}

function WordRain({ questions, wordSetId, onFinish }: Props) {
  const theme = useTheme();
  const game = useGameSession('game_rain');
  const [ready, setReady] = useState(false);
  const [index, setIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const [lives, setLives] = useState(LIVES);
  const [streak, setStreak] = useState(0);
  const [score, setScore] = useState(0);
  const [draft, setDraft] = useState('');
  const [flash, setFlash] = useState<'ok' | 'miss' | null>(null);

  const sid = useRef<number | null>(null);
  const shownAt = useRef<number>(Date.now());
  const done = useRef(false);
  const finalScoreRef = useRef(0);
  const submittedIndex = useRef(-1);

  useEffect(() => {
    let alive = true;
    game.start(wordSetId).then((id) => {
      if (!alive) return;
      sid.current = id;
      shownAt.current = Date.now();
      setReady(true);
    }).catch(() => {}); // The hook exposes the error for display below.
    return () => { alive = false; };
    // Chỉ mở phiên MỘT lần cho cả ván; thêm phụ thuộc vào đây sẽ mở phiên mới
    // giữa chừng và làm vỡ thống kê của ván đang chơi.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const current = questions[index];

  const end = useCallback(async (finalScore: number) => {
    if (done.current) return;
    done.current = true;
    finalScoreRef.current = finalScore;
    if (sid.current === null || !await game.finish(sid.current)) return;
    onFinish(finalScore);
  }, [game, onFinish]);

  const next = useCallback((gained: number, lostLife: boolean) => {
    const total = score + gained;
    const livesLeft = lostLife ? lives - 1 : lives;
    setScore(total);
    if (livesLeft <= 0 || index + 1 >= questions.length) void end(total);
    if (lostLife) setLives((l) => l - 1);
    setIndex((i) => i + 1);
    setElapsed(0);
    setDraft('');
    shownAt.current = Date.now();
  }, [end, index, lives, questions.length, score]);

  const submit = useCallback((expired: boolean) => {
    if (!ready || !current || done.current || submittedIndex.current === index) return;
    submittedIndex.current = index;
    const spent = Date.now() - shownAt.current;
    const correct = !expired
      && draft.trim().toLowerCase() === current.answer.trim().toLowerCase();

    // BR-05: gửi CẢ lượt sai và lượt hết giờ.
    if (sid.current !== null) void game.answer(sid.current, current.item_id, correct, spent, expired ? '' : draft);

    if (correct) {
      const nextStreak = streak + 1;
      setStreak(nextStreak);
      setFlash('ok');
      next(roundScore(1 - spent / FALL_MS, nextStreak), false);
    } else {
      setStreak(0);
      setFlash('miss');
      next(0, true);
    }
    window.setTimeout(() => setFlash(null), 250);
  }, [current, draft, game, next, ready, streak, index]);

  // Đồng hồ rơi
  useEffect(() => {
    if (!ready || !current || done.current) return undefined;
    const timer = window.setInterval(() => {
      const spent = Date.now() - shownAt.current;
      setElapsed(spent);
      if (spent >= FALL_MS) submit(true);
    }, TICK_MS);
    return () => window.clearInterval(timer);
  }, [ready, current, submit]);

  if (done.current) {
    return <Stack spacing={2}>
      {game.saving ? <LinearProgress /> : <>
        <Alert severity="error">{game.error || 'Chưa lưu xong kết quả. Đáp án vẫn được giữ để gửi lại.'}</Alert>
        <Button onClick={() => { done.current = false; void end(finalScoreRef.current); }}>Thử lưu lại</Button>
      </>}
    </Stack>;
  }
  if (!ready && game.error) return <Alert severity="error">{game.error}</Alert>;
  if (!ready || !current) {
    return <LinearProgress sx={{ mt: 4 }} />;
  }

  const fallRatio = Math.min(1, elapsed / FALL_MS);

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 1.5, alignItems: 'center' }}>
        <Chip label={`Điểm ${score}`} color="primary" />
        <Box
          sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'error.main' }}
          role="img"
          aria-label={`Còn ${Math.max(0, lives)} mạng`}
        >
          {Array.from({ length: Math.max(0, lives) }, (_, i) => (
            <HeartIcon key={i} size={18} filled />
          ))}
        </Box>
        {streak > 1 && <Chip label={`Chuỗi ×${streak}`} color="warning" />}
        <Box sx={{ flexGrow: 1 }} />
        <Typography variant="body2" color="text.secondary">
          {index + 1}/{questions.length}
        </Typography>
        {/* Dừng sớm: đóng phiên như kết thúc bình thường. Các lượt ĐÃ trả lời đã
            được gửi (BR-05); từ đang rơi dở chưa có câu trả lời nên không ghi —
            ghi nó là sai sẽ làm DKT tưởng người học không biết từ đó. */}
        <Button size="small" color="inherit" variant="outlined" onClick={() => void end(score)}>
          Kết thúc ván
        </Button>
      </Stack>

      <Box
        sx={{
          position: 'relative', height: 240, borderRadius: '16px', overflow: 'hidden',
          border: `1px solid ${alpha(theme.palette.text.primary, 0.12)}`,
          bgcolor: flash === 'ok'
            ? alpha(theme.palette.success.main, 0.12)
            : flash === 'miss'
              ? alpha(theme.palette.error.main, 0.12)
              : 'background.paper',
          transition: 'background-color .2s',
        }}
      >
        <Box
          sx={{
            position: 'absolute', left: 0, right: 0, textAlign: 'center',
            top: `${fallRatio * 82}%`, transition: `top ${TICK_MS}ms linear`, px: 2,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 700 }}>{current.meaning}</Typography>
          <Typography variant="caption" color="text.secondary">
            {current.length} chữ cái · bắt đầu bằng “{current.first_letter}”
          </Typography>
        </Box>
        {/* Vạch đáy: chạm vạch là mất một mạng */}
        <Box sx={{
          position: 'absolute', left: 0, right: 0, bottom: 0, height: 3,
          bgcolor: 'error.main', opacity: 0.6,
        }} />
      </Box>

      <TextField
        fullWidth autoFocus sx={{ mt: 2 }} value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit(false); }}
        placeholder="Gõ từ tiếng Anh rồi Enter"
        slotProps={{ htmlInput: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false } }}
      />
    </Box>
  );
}

export default WordRain;
