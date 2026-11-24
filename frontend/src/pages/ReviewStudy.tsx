import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import QuizGate from '../components/QuizGate';
import {
  AnswerBar,
  AnswerButton,
  SessionSummaryView,
  StudyMessage,
  StudyShell,
} from '../components/StudyShell';
import WordCard from '../components/WordCard';

import { completeSession, getQuizForItems, recordAnswer } from '../api/sessions';
import { createSrsSession, createWeakSession, getDue, getWeak } from '../api/reviews';
import { useAuth } from '../context/AuthContext';
import type { QuizQuestion, SessionSummary } from '../types/session';
import { PRIMARY, WRONG_RED } from '../theme/theme';
import { newAnswerId } from '../utils/answerId';

type Phase = 'loading' | 'running' | 'summary' | 'empty' | 'error';

/** Phần chung của thẻ ôn — dùng cho cả lịch ôn (UC-33) lẫn điểm yếu (UC-86). */
interface Card {
  item_id: number;
  word: string;
  meaning: string;
  word_set_name: string;
}

/** Hai nguồn từ để ôn, khác nhau ở tiêu chí chọn chứ không khác cách học. */
const SOURCES = {
  due: {
    title: 'Ôn theo lịch',
    exitLabel: '← Lịch ôn',
    emptyText: 'Không có từ nào đến hạn ôn. Quay lại sau nhé!',
    format: 'srs_review',
    load: () => getDue(),
    createSession: createSrsSession,
  },
  weak: {
    title: 'Ôn điểm yếu',
    exitLabel: '← Lịch ôn',
    emptyText: 'Chưa có từ nào bị xếp vào nhóm điểm yếu. Học thêm để hệ thống có căn cứ.',
    format: 'weak_review',
    load: () => getWeak(),
    createSession: createWeakSession,
  },
} as const;

function ReviewStudy() {
  const auth = useAuth();
  const navigate = useNavigate();

  // ?source=weak -> phiên ôn điểm yếu (UC-86); mặc định là ôn theo lịch (UC-33)
  const [params] = useSearchParams();
  const source = SOURCES[params.get('source') === 'weak' ? 'weak' : 'due'];

  const [phase, setPhase] = useState<Phase>('loading');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [items, setItems] = useState<Card[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  // Pilot — câu chọn nghĩa trước khi lật thẻ: hệ thống chấm thay vì tự khai
  const [gateById, setGateById] = useState<Record<number, QuizQuestion>>({});
  const [gateChoice, setGateChoice] = useState<string | null | undefined>(undefined);
  const [gateBusy, setGateBusy] = useState(false);
  /** Đúng/sai từng thẻ đã làm — chỉ để tô thanh tiến độ, không gửi đi đâu. */
  const [results, setResults] = useState<boolean[]>([]);

  const startedRef = useRef(false);
  const shownAtRef = useRef<number>(Date.now());

  useEffect(() => {
    if (startedRef.current || !auth.token) return;
    startedRef.current = true;
    (async () => {
      try {
        const list = await source.load();
        if (list.length === 0) {
          setPhase('empty');
          return;
        }
        const session = await source.createSession();
        setSessionId(session.id);
        const gates = await getQuizForItems(list.map((c) => c.item_id)).catch(() => []);
        setGateById(Object.fromEntries(gates.map((q) => [q.item_id, q])));
        setItems(list);
        shownAtRef.current = Date.now();
        setPhase('running');
      } catch {
        setPhase('error');
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Phím tắt cho thẻ lật (thẻ có câu chọn nghĩa do QuizGate tự xử lý phím).
  useEffect(() => {
    if (phase !== 'running') return;
    const current = items[index];
    if (!current || gateById[current.item_id]) return;
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName ?? '').toUpperCase();
      if (['INPUT', 'TEXTAREA'].includes(tag)) return;
      if (!flipped && e.code === 'Space') {
        e.preventDefault();
        setFlipped(true);
      } else if (flipped && (e.key === '1' || e.key === '2')) {
        e.preventDefault();
        void submitAndNext(current.item_id, e.key === '2');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, index, flipped, items, gateById]);

  async function submitAndNext(itemId: number, isCorrect: boolean) {
    if (sessionId == null) return;
    await recordAnswer(sessionId, {
      item_id: itemId,
      is_correct: isCorrect,
      response_time_ms: Date.now() - shownAtRef.current,
      exercise_format: source.format,
    });
    setResults((r) => [...r, isCorrect]);
    await next();
  }

  async function answerGate(itemId: number, choice: string | null) {
    if (sessionId == null || gateBusy || gateChoice !== undefined) return;
    const gate = gateById[itemId];
    setGateBusy(true);
    try {
      await recordAnswer(sessionId, {
        item_id: itemId,
        is_correct: choice === gate.options[gate.correct_index],
        answer: choice ?? '',
        client_answer_id: newAnswerId(),
        response_time_ms: Date.now() - shownAtRef.current,
        exercise_format: 'quiz',
      });
      setGateChoice(choice);
      setResults((r) => [...r, choice === gate.options[gate.correct_index]]);
      setFlipped(true);
    } finally {
      setGateBusy(false);
    }
  }

  async function next() {
    if (sessionId == null) return;
    setGateChoice(undefined);
    if (index + 1 >= items.length) {
      setSummary(await completeSession(sessionId));
      setPhase('summary');
    } else {
      setIndex((i) => i + 1);
      setFlipped(false);
      shownAtRef.current = Date.now();
    }
  }

  if (!auth.token) return <Navigate to="/login" replace />;

  const backToReviews = () => navigate('/reviews');

  if (phase === 'loading') {
    return <StudyMessage title="Đang chuẩn bị thẻ ôn…" mood="nghi" />;
  }
  if (phase === 'error') {
    return (
      <StudyMessage title="Ối, có lỗi rồi" mood="nghi"
        actions={<Button variant="contained" onClick={backToReviews}>Về lịch ôn</Button>}>
        Không tải được phiên ôn. Thử lại sau ít phút nhé.
      </StudyMessage>
    );
  }
  if (phase === 'empty') {
    return (
      <StudyMessage title="Chưa có gì để ôn" mood="ngu"
        actions={<Button variant="contained" onClick={backToReviews}>Về lịch ôn</Button>}>
        {source.emptyText}
      </StudyMessage>
    );
  }
  if (phase === 'summary' && summary) {
    return (
      <SessionSummaryView
        summary={summary}
        primary={{ label: 'Về lịch ôn', onClick: backToReviews }}
        secondary={{ label: 'Trang chủ', onClick: () => navigate('/') }}
      />
    );
  }

  // running
  const it = items[index];
  const gate = gateById[it.item_id];

  return (
    <StudyShell
      title={source.title}
      modeLabel={gate ? 'Chọn nghĩa đúng' : 'Thẻ lật'}
      done={index}
      total={items.length}
      results={results}
      onExit={backToReviews}
      hints={gate
        ? <><span><kbd>1-4</kbd>chọn nghĩa</span><span><kbd>0</kbd>không biết</span><span><kbd>Enter</kbd>tiếp</span></>
        : <><span><kbd>Space</kbd>lật thẻ</span></>}
    >
      <WordCard
        seed={it.item_id}
        no={index + 1}
        word={it.word}
        footer={it.word_set_name}
        flipped={gate ? false : flipped}
        onFlip={!gate && !flipped ? () => setFlipped(true) : undefined}
        back={
          <Typography sx={{ fontWeight: 900, fontSize: { xs: 21, sm: 25 }, lineHeight: 1.35 }}>
            {it.meaning}
          </Typography>
        }
      />

      {gate ? (
        <QuizGate question={gate} chosen={gateChoice} busy={gateBusy}
          onAnswer={(c) => void answerGate(it.item_id, c)} onNext={() => void next()}
          nextLabel={index + 1 >= items.length ? 'Hoàn thành' : 'Tiếp tục'} />
      ) : flipped ? (
        <AnswerBar>
          <AnswerButton shortcut="1" label="Chưa nhớ" color={WRONG_RED} onClick={() => void submitAndNext(it.item_id, false)} />
          <AnswerButton shortcut="2" label="Nhớ rồi" color={PRIMARY} onClick={() => void submitAndNext(it.item_id, true)} />
        </AnswerBar>
      ) : (
        <AnswerBar>
          <AnswerButton shortcut="Space" label="Lật thẻ" color={PRIMARY} onClick={() => setFlipped(true)} />
        </AnswerBar>
      )}
    </StudyShell>
  );
}

export default ReviewStudy;
