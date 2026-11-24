import { useCallback, useEffect, useRef, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import type { TypingQuestion } from '../../types/session';
import { useSpeech } from '../../hooks/useSpeech';
import { SpeakerIcon } from '../icons';
import { roundScore, useGameSession } from './useGameSession';

/** UC-94 — Nghe đánh vần. Nghe phát âm rồi viết lại đúng chính tả.
 *
 * Dạng bài thật: `dictation` (nghe + sản sinh) — cùng loại với UC-90.
 *
 * Trò này phụ thuộc Web Speech API của trình duyệt. Không có thì KHÔNG chơi
 * được, và phải nói thẳng thay vì để người chơi ngồi chờ một âm thanh không bao
 * giờ phát.
 */

const LIMIT_MS = 15000;
const TICK_MS = 100;

interface Props {
  questions: TypingQuestion[];
  wordSetId: number;
  onFinish: (score: number) => void;
}

function SpellingBee({ questions, wordSetId, onFinish }: Props) {
  const game = useGameSession('game_spelling');
  const [ready, setReady] = useState(false);
  const [index, setIndex] = useState(0);
  const [left, setLeft] = useState(LIMIT_MS);
  const [streak, setStreak] = useState(0);
  const [score, setScore] = useState(0);
  const [draft, setDraft] = useState('');
  const [lastResult, setLastResult] = useState<{ ok: boolean; answer: string } | null>(null);

  const sid = useRef<number | null>(null);
  const shownAt = useRef<number>(Date.now());
  const done = useRef(false);
  const finalScoreRef = useRef(0);
  const submittedIndex = useRef(-1);
  // UC-29 — hook chung, giữ tốc độ đọc người dùng đã chọn ở trang khác.
  const speech = useSpeech();
  const supported = speech.supported;

  const current = questions[index];
  const speak = speech.speak;

  useEffect(() => {
    if (!supported) return undefined;
    let alive = true;
    game.start(wordSetId).then((id) => {
      if (!alive) return;
      sid.current = id;
      shownAt.current = Date.now();
      setReady(true);
    }).catch(() => {}); // The hook exposes the error for display below.
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported]);

  // Đọc từ mới mỗi khi sang câu kế
  useEffect(() => {
    if (ready && current) speak(current.answer);
  }, [ready, current, speak]);

  const end = useCallback(async (finalScore: number) => {
    if (done.current) return;
    done.current = true;
    finalScoreRef.current = finalScore;
    speech.stop();
    if (sid.current === null || !await game.finish(sid.current)) return;
    onFinish(finalScore);
  }, [game, onFinish, speech]);

  const submit = useCallback((expired: boolean) => {
    if (!ready || !current || done.current || submittedIndex.current === index) return;
    submittedIndex.current = index;
    const spent = Date.now() - shownAt.current;
    const correct = !expired
      && draft.trim().toLowerCase() === current.answer.trim().toLowerCase();

    if (sid.current !== null) void game.answer(sid.current, current.item_id, correct, spent, expired ? '' : draft);
    setLastResult({ ok: correct, answer: current.answer });

    const gained = correct ? roundScore(1 - spent / LIMIT_MS, streak + 1) : 0;
    setStreak(correct ? streak + 1 : 0);
    const total = score + gained;
    setScore(total);
    if (index + 1 >= questions.length) void end(total);
    setIndex((i) => i + 1);
    setLeft(LIMIT_MS);
    setDraft('');
    shownAt.current = Date.now();
  }, [current, draft, end, game, index, questions.length, ready, streak, score]);

  useEffect(() => {
    if (!ready || !current || done.current) return undefined;
    const timer = window.setInterval(() => {
      const remaining = Math.max(0, LIMIT_MS - (Date.now() - shownAt.current));
      setLeft(remaining);
      if (!remaining) submit(true);
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
  if (!supported) {
    return (
      <Alert severity="warning">
        Trình duyệt này không hỗ trợ đọc phát âm (Web Speech API), nên không chơi được
        “Nghe đánh vần”. Hãy thử trên Chrome hoặc Edge bản mới.
      </Alert>
    );
  }
  if (!ready || !current) return <LinearProgress sx={{ mt: 4 }} />;

  return (
    <Box>
      <Stack direction="row" spacing={2} sx={{ mb: 1.5, alignItems: 'center' }}>
        <Chip label={`Điểm ${score}`} color="primary" />
        {streak > 1 && <Chip label={`Chuỗi ×${streak}`} color="warning" />}
        <Box sx={{ flexGrow: 1 }} />
        <Typography variant="body2" color="text.secondary">
          {index + 1}/{questions.length}
        </Typography>
        {/* Dừng sớm — cùng cách xử lý như WordRain: chỉ các lượt đã trả lời được ghi. */}
        <Button size="small" color="inherit" variant="outlined" onClick={() => void end(score)}>
          Kết thúc ván
        </Button>
      </Stack>

      <LinearProgress
        variant="determinate" value={(left / LIMIT_MS) * 100}
        color={left < LIMIT_MS * 0.3 ? 'error' : 'primary'}
        sx={{ mb: 3 }}
      />

      <Box sx={{ textAlign: 'center', mb: 3 }}>
        <Button
          size="large" variant="outlined" startIcon={<SpeakerIcon size={20} />}
          onClick={() => speak(current.answer)}
        >
          Nghe lại
        </Button>
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
          {current.length} chữ cái · nghĩa: {current.meaning}
        </Typography>
      </Box>

      <TextField
        fullWidth autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit(false); }}
        placeholder="Viết lại từ vừa nghe rồi Enter"
        slotProps={{ htmlInput: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false } }}
      />

      {lastResult && (
        <Typography
          variant="body2" sx={{ mt: 1.5 }}
          color={lastResult.ok ? 'success.main' : 'error.main'}
        >
          {lastResult.ok ? '✓ Chính xác' : `✗ Đáp án: ${lastResult.answer}`}
        </Typography>
      )}
    </Box>
  );
}

export default SpellingBee;
