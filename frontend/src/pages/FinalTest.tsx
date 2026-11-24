import { useRef, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import StudyPrompt from '../components/StudyPrompt';
import { completeSession, recordAnswer } from '../api/sessions';
import { startValidation, useValidationStatus, type ValidationQuestion } from '../api/pilot';
import { ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { SessionSummary } from '../types/session';

type Phase = 'intro' | 'running' | 'saving' | 'done' | 'error';

/**
 * Pilot — bài kiểm tra cuối. Thấy nghĩa tiếng Việt, gõ lại từ tiếng Anh.
 * KHÔNG hiện đáp án từng câu: đây là phép đo độc lập để kiểm chứng mastery
 * của DKT, không phải bài luyện. Hệ thống chấm và bốc đề ở backend.
 */
function FinalTest() {
  const auth = useAuth();
  const navigate = useNavigate();
  const status = useValidationStatus();

  const [phase, setPhase] = useState<Phase>('intro');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [questions, setQuestions] = useState<ValidationQuestion[]>([]);
  const [total, setTotal] = useState(0);
  const [index, setIndex] = useState(0);
  const [typed, setTyped] = useState('');
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [error, setError] = useState('');
  const shownAt = useRef(Date.now());

  if (!auth.token) return <Navigate to="/login" replace />;

  async function begin() {
    try {
      const res = await startValidation();
      setSessionId(res.session_id);
      setQuestions(res.questions);
      // vào lại giữa chừng: tổng = số câu dự kiến, tiến độ tính từ phần đã làm
      const planned = status.data?.size ?? res.questions.length;
      setTotal(Math.max(planned, res.questions.length));
      setIndex(0);
      shownAt.current = Date.now();
      if (res.questions.length === 0) {
        await finish(res.session_id);
      } else {
        setPhase('running');
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không mở được bài kiểm tra.');
      setPhase('error');
    }
  }

  async function finish(id: number) {
    setPhase('saving');
    setSummary(await completeSession(id));
    setPhase('done');
    void status.refetch();
  }

  async function submit(answer: string) {
    if (sessionId == null || phase !== 'running') return;
    const q = questions[index];
    setPhase('saving');
    try {
      await recordAnswer(sessionId, {
        item_id: q.item_id,
        is_correct: false, // server tự chấm theo đáp án gõ vào
        answer,
        response_time_ms: Date.now() - shownAt.current,
        exercise_format: 'typing',
      });
      if (index + 1 >= questions.length) {
        await finish(sessionId);
        return;
      }
      setIndex((i) => i + 1);
      setTyped('');
      shownAt.current = Date.now();
      setPhase('running');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Không lưu được câu trả lời.');
      setPhase('error');
    }
  }

  const back = { to: '/', label: 'Về trang chủ' };

  if (status.isLoading) {
    return <StudyPrompt bare maxWidth={200}><Box sx={{ textAlign: 'center' }}><CircularProgress /></Box></StudyPrompt>;
  }
  const st = status.data;

  if (phase === 'error') {
    return (
      <StudyPrompt back={back}>
        <Alert severity="error">{error}</Alert>
      </StudyPrompt>
    );
  }

  if (phase === 'done' && summary) {
    return (
      <StudyPrompt back={back} maxWidth={520}>
        <Typography variant="h4" gutterBottom>Cảm ơn bạn!</Typography>
        <Typography sx={{ mb: 1 }}>
          Bạn nhớ đúng <b>{summary.correct_count}/{summary.total_answered}</b> từ.
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Kết quả này dùng để kiểm tra xem hệ thống đánh giá mức độ thuộc từ của bạn có chính xác không.
          Bạn đã hoàn thành phần thử nghiệm - nhớ điền phiếu khảo sát cuối nhé.
        </Typography>
        <Button variant="contained" onClick={() => navigate('/')}>Về trang chủ</Button>
      </StudyPrompt>
    );
  }

  if (phase === 'intro') {
    let blocker: string | null = null;
    if (!st?.open) blocker = 'Bài kiểm tra cuối chưa mở. Bạn sẽ được báo khi đến ngày làm bài.';
    else if (st.done) blocker = 'Bạn đã làm bài kiểm tra cuối rồi. Cảm ơn bạn!';
    else if (st.eligible_items < st.min_items) {
      blocker = `Bạn cần học ít nhất ${st.min_items} từ trước khi làm bài (hiện mới ${st.eligible_items}).`;
    }
    return (
      <StudyPrompt back={back} maxWidth={560}>
        <Typography variant="h4" gutterBottom>Bài kiểm tra cuối</Typography>
        {blocker ? (
          <Alert severity="info">{blocker}</Alert>
        ) : (
          <>
            <Typography sx={{ mb: 2 }}>
              Khoảng {st?.size} câu, chừng 10 phút. Mỗi câu cho nghĩa tiếng Việt - bạn gõ lại từ tiếng Anh.
            </Typography>
            <Box component="ul" sx={{ textAlign: 'left', pl: 3, mb: 3, '& li': { mb: 0.75 } }}>
              <li>Các từ đều là từ bạn <b>đã học</b> trong mấy ngày qua.</li>
              <li><b>Không tra từ điển</b>, không hỏi người khác - cứ làm theo trí nhớ.</li>
              <li>Không nhớ thì bấm <b>"Không nhớ"</b>, đừng đoán bừa.</li>
              <li>Sẽ không hiện đáp án sau từng câu. Thoát giữa chừng thì lần sau làm tiếp.</li>
            </Box>
            <Button variant="contained" size="large" onClick={() => void begin()}>
              {st?.in_progress_session_id ? 'Làm tiếp' : 'Bắt đầu'}
            </Button>
          </>
        )}
      </StudyPrompt>
    );
  }

  // running | saving
  const q = questions[index];
  const doneCount = total - questions.length + index;
  return (
    <Box sx={{ p: { xs: 2, sm: 4 }, maxWidth: 640, mx: 'auto' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Button onClick={() => navigate('/')}>← Thoát</Button>
        <Chip size="small" color="primary" label="Bài kiểm tra cuối" />
        <Typography variant="body2" color="text.secondary">{doneCount + 1} / {total}</Typography>
      </Box>
      <LinearProgress variant="determinate" value={(doneCount / Math.max(total, 1)) * 100} sx={{ mb: 3 }} />
      <Card>
        <CardContent sx={{ textAlign: 'center', py: 5 }}>
          {q.part_of_speech && <Chip size="small" label={q.part_of_speech} sx={{ mb: 1.5 }} />}
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>{q.meaning}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Bắt đầu bằng chữ <b>"{q.first_letter}"</b> · {q.length} ký tự
          </Typography>
          <TextField
            autoFocus fullWidth label="Từ tiếng Anh" value={typed}
            disabled={phase === 'saving'}
            autoComplete="off" slotProps={{ htmlInput: { autoCapitalize: 'none', autoCorrect: 'off', spellCheck: false } }}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && typed.trim()) void submit(typed); }}
          />
          <Box sx={{ display: 'flex', gap: 1.5, justifyContent: 'center', mt: 3 }}>
            <Button variant="outlined" disabled={phase === 'saving'} onClick={() => void submit('')}>
              Không nhớ
            </Button>
            <Button variant="contained" disabled={phase === 'saving' || !typed.trim()} onClick={() => void submit(typed)}>
              Trả lời <Box component="span" sx={{ ml: 1 }}><kbd>Enter</kbd></Box>
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
}

export default FinalTest;
