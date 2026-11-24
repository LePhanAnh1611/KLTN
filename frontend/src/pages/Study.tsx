import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import SpeakButton from '../components/SpeakButton';
import {
  AnswerBar,
  AnswerButton,
  FeedbackBar,
  OptionGrid,
  OptionTile,
  SessionSummaryView,
  StudyCard,
  StudyMessage,
  StudyShell,
} from '../components/StudyShell';
import WordCard, { QUESTION_BG } from '../components/WordCard';
import { apiGet } from '../api/client';
import {
  completeSession,
  createSession,
  getActiveSession,
  getCloze,
  getTyping,
  getMatching,
  getQuiz,
  getQuizForItems,
  getRecommend,
  getTodayStudyItems,
  recordAnswer,
} from '../api/sessions';
import { useAuth } from '../context/AuthContext';
import { useSpeech } from '../hooks/useSpeech';
import { SpeakerIcon } from '../components/icons';
import MeaningConfidenceMark from '../components/MeaningConfidenceMark';
import QuizGate from '../components/QuizGate';
import { useWordSet } from '../api/wordSets';
import type {
  ClozeQuestion, MatchingRound, QuizQuestion, SessionSummary, StudyMode, TypingQuestion,
} from '../types/session';
import type { Item } from '../types/wordSet';
import { useAnswerSound } from '../hooks/useAnswerSound';
import { FLAT, PRIMARY, SOFT_SHADOW, WRONG_RED } from '../theme/theme';
import { newAnswerId } from '../utils/answerId';

type Phase = 'loading' | 'resume' | 'running' | 'summary' | 'empty' | 'error';

/** Tên chế độ hiển thị trên thanh trên của phòng học. */
const MODE_LABELS: Partial<Record<StudyMode, string>> = {
  flashcard: 'Thẻ lật',
  dkt_smart: 'Học từ mới vừa sức',
  sm2: 'Thẻ lật 4 mức (kiểu Anki)',
  quiz: 'Trắc nghiệm',
  cloze: 'Điền từ',
  typing: 'Gõ từ',
  dictation: 'Nghe chép',
  mixed: 'Trộn trắc nghiệm + gõ từ',
  matching: 'Ghép cặp',
};

function Study() {
  const auth = useAuth();
  const { id, mode } = useParams();
  const navigate = useNavigate();
  // UC-35 — ?practice=1 nghĩa là luyện thường: vẫn ghi kết quả, không đổi lịch ôn
  const [searchParams] = useSearchParams();
  const practiceOnly = searchParams.get('practice') === '1';
  // /study/today?ids=… — "Học N từ mới" từ trang chủ: học ĐÚNG các từ đã gợi ý,
  // có thể thuộc nhiều bộ nên phiên không gắn bộ nào (wordSetId = null).
  const isToday = id == null;
  const todayIds = (searchParams.get('ids') ?? '')
    .split(',').map(Number).filter((n) => Number.isInteger(n) && n > 0);
  const wordSetId = isToday ? null : Number(id);
  const studyMode = (isToday ? 'dkt_smart' : mode) as StudyMode;

  const [phase, setPhase] = useState<Phase>('loading');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [masteryById, setMasteryById] = useState<Record<number, number>>({});
  // Pilot — câu chọn nghĩa đặt trước thẻ lật (chấm khách quan) và lý do từ được
  // chọn ('band' vừa sức / 'explore' ngẫu nhiên), gửi kèm khi ghi câu trả lời.
  const [gateById, setGateById] = useState<Record<number, QuizQuestion>>({});
  const [selectionById, setSelectionById] = useState<Record<number, 'band' | 'explore'>>({});
  const [gateChoice, setGateChoice] = useState<string | null | undefined>(undefined);
  const [gateBusy, setGateBusy] = useState(false);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [clozes, setClozes] = useState<ClozeQuestion[]>([]);
  const [typings, setTypings] = useState<TypingQuestion[]>([]);
  // UC-29 dùng lại cho UC-90: đọc từ bằng Web Speech API của trình duyệt
  const speech = useSpeech();
  const sound = useAnswerSound();
  const [matching, setMatching] = useState<MatchingRound | null>(null);
  // Ghép cặp không đi theo index: người học ghép tới đâu tính tới đó
  const [matchedIds, setMatchedIds] = useState<number[]>([]);
  const [pickedWord, setPickedWord] = useState<number | null>(null);
  const [wrongMeaning, setWrongMeaning] = useState<string | null>(null);
  const [typed, setTyped] = useState('');
  const [checked, setChecked] = useState(false);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [resumeAnswered, setResumeAnswered] = useState<number[]>([]);
  /** Đúng/sai từng câu đã làm — chỉ để tô thanh tiến độ, không gửi đi đâu. */
  const [results, setResults] = useState<boolean[]>([]);

  const startedRef = useRef(false);
  const shownAtRef = useRef<number>(Date.now());

  useEffect(() => {
    if (startedRef.current || !auth.token) return;
    startedRef.current = true;

    getActiveSession(wordSetId, studyMode)
      .then((active) => {
        if (active.session && active.session.mode === studyMode) {
          setSessionId(active.session.id);
          setResumeAnswered(active.answered_item_ids);
          setPhase('resume');
        } else {
          void startNew();
        }
      })
      .catch(() => setPhase('error'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const wordSetQuery = useWordSet(wordSetId ?? NaN);
  const setTitle = isToday ? 'Từ mới hôm nay' : wordSetQuery.data?.name || 'Phiên học từ vựng';

  const half = Math.floor(index / 2);
  const stepMode: StudyMode =
    studyMode === 'mixed' ? (index % 2 === 0 ? 'quiz' : 'typing') : studyMode;
  const stepIndex = studyMode === 'mixed' ? half : index;

  // Điều khiển bằng bàn phím (Keyboard-First UX theo Taste Skill & HSK Web 2)
  useEffect(() => {
    if (phase !== 'running') return;
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = (document.activeElement?.tagName ?? '').toUpperCase();
      if (['INPUT', 'TEXTAREA'].includes(activeTag)) return;
      // Thẻ có câu chọn nghĩa: phím do QuizGate xử lý, không cho lật trước khi trả lời
      if (stepMode === 'dkt_smart' && items[stepIndex] && gateById[items[stepIndex].id]) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setFlipped((f) => !f);
      } else if (flipped && (stepMode === 'sm2' || stepMode === 'flashcard' || stepMode === 'dkt_smart')) {
        const curItem = items[stepIndex];
        if (!curItem) return;
        if (stepMode === 'sm2') {
          if (e.key === '1') { e.preventDefault(); void submitSm2(curItem.id, 'again'); }
          else if (e.key === '2') { e.preventDefault(); void submitSm2(curItem.id, 'hard'); }
          else if (e.key === '3') { e.preventDefault(); void submitSm2(curItem.id, 'good'); }
          else if (e.key === '4') { e.preventDefault(); void submitSm2(curItem.id, 'easy'); }
        } else {
          if (e.key === '1') { e.preventDefault(); void submitAndNext(curItem.id, false); }
          else if (e.key === '2' || e.key === '3' || e.key === '4') { e.preventDefault(); void submitAndNext(curItem.id, true); }
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [phase, flipped, stepMode, stepIndex, items, gateById]);

  async function loadContent(skipItemIds: number[] = []): Promise<boolean> {
    if (studyMode === 'dkt_smart') {
      // UC-27: item đã được /recommend sắp theo "vừa sức" (P đúng ∈ [0.6,0.8])
      const recs = wordSetId == null
        ? await getTodayStudyItems(todayIds)      // đúng N từ trang chủ đã gợi ý
        : await getRecommend(wordSetId);          // học trong một bộ: như cũ
      const remaining = recs.filter((r) => !skipItemIds.includes(r.id));
      setItems(remaining.map((r) => ({
        id: r.id, word_set_id: wordSetId ?? 0, word: r.word, phonetic: r.phonetic,
        part_of_speech: r.part_of_speech, meaning: r.meaning, example: r.example,
        example_vi: r.example_vi, meaning_confidence: r.meaning_confidence, meaning_source: null, example_source: null,
        created_at: '',
      })));
      setMasteryById(Object.fromEntries(remaining.map((r) => [r.id, r.mastery])));
      setSelectionById(Object.fromEntries(remaining.map((r) => [r.id, r.selection])));
      // Thiếu đáp án nhiễu (bộ quá ít từ) -> từ đó rơi về thẻ lật tự đánh giá như cũ
      const gates = await getQuizForItems(remaining.map((r) => r.id)).catch(() => []);
      setGateById(Object.fromEntries(gates.map((q) => [q.item_id, q])));
      return remaining.length > 0;
    }
    // Các chế độ còn lại chỉ mở được từ trang một bộ từ, nên luôn có bộ.
    const setId = wordSetId as number;
    if (studyMode === 'flashcard' || studyMode === 'sm2') {
      const all = await apiGet<Item[]>(`/api/v1/word-sets/${setId}/items`);
      const remaining = all.filter((it) => !skipItemIds.includes(it.id));
      setItems(remaining);
      return remaining.length > 0;
    }
    if (studyMode === 'cloze') {
      const rows = await getCloze(setId);
      const remaining = rows.filter((c) => !skipItemIds.includes(c.item_id));
      setClozes(remaining);
      return remaining.length > 0;
    }
    if (studyMode === 'typing' || studyMode === 'dictation') {
      const rows = await getTyping(setId);
      const remaining = rows.filter((q) => !skipItemIds.includes(q.item_id));
      setTypings(remaining);
      return remaining.length > 0;
    }
    if (studyMode === 'mixed') {
      // UC-91 — xen kẽ trắc nghiệm (nhận diện) và gõ từ (nhớ chủ động).
      // Lấy hai nguồn rồi lọc trùng: một phiên hỏi cùng một từ hai lần bằng hai
      // dạng bài thì người học chỉ thấy phiền, không học thêm được gì.
      const [quizRows, typeRows] = await Promise.all([
        getQuiz(setId, 20),
        getTyping(setId, 20),
      ]);
      const quizKeep = quizRows.filter((q) => !skipItemIds.includes(q.item_id));
      const usedIds = new Set(quizKeep.map((q) => q.item_id));
      const typeKeep = typeRows.filter(
        (t) => !skipItemIds.includes(t.item_id) && !usedIds.has(t.item_id),
      );
      setQuestions(quizKeep);
      setTypings(typeKeep);
      return quizKeep.length > 0 && typeKeep.length > 0;
    }
    if (studyMode === 'matching') {
      // Một lượt ghép là một khối, không cắt bớt theo item đã trả lời
      const round = await getMatching(setId);
      setMatching(round);
      return round.pairs.length > 0;
    }
    const quiz = await getQuiz(setId);
    const remaining = quiz.filter((q) => !skipItemIds.includes(q.item_id));
    setQuestions(remaining);
    return remaining.length > 0;
  }

  async function startNew() {
    try {
      const session = await createSession(wordSetId, studyMode, practiceOnly);
      setSessionId(session.id);
      const hasContent = await loadContent();
      resetUnit();
      setPhase(hasContent ? 'running' : 'empty');
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : 'Không bắt đầu được phiên học.');
      setPhase('error');
    }
  }

  async function resumeExisting() {
    try {
      const hasContent = await loadContent(resumeAnswered);
      resetUnit();
      if (!hasContent) {
        await finish();
        return;
      }
      setPhase('running');
    } catch (error) {
      setErrorMsg(error instanceof Error ? error.message : 'Không tiếp tục được phiên.');
      setPhase('error');
    }
  }

  function resetUnit() {
    setGateChoice(undefined);
    setFlipped(false);
    setSelected(null);
    setTyped('');
    setChecked(false);
    setWrongMeaning(null);
    shownAtRef.current = Date.now();
  }

  /** Chấm câu gõ: hiện kết quả + phát âm báo. Ghi câu trả lời vẫn đợi bấm Tiếp. */
  function checkTyped(correct: boolean) {
    setChecked(true);
    sound.play(correct);
  }

  async function finish() {
    if (sessionId == null) return;
    const result = await completeSession(sessionId);
    setSummary(result);
    setPhase('summary');
  }

  const total =
    studyMode === 'quiz' ? questions.length
    : studyMode === 'cloze' ? clozes.length
    : studyMode === 'typing' || studyMode === 'dictation' ? typings.length
    : studyMode === 'mixed' ? Math.min(questions.length, typings.length) * 2
    : studyMode === 'matching' ? (matching?.pairs.length ?? 0)
    : items.length;

  async function advance() {
    if (index + 1 >= total) {
      await finish();
    } else {
      setIndex((i) => i + 1);
      resetUnit();
    }
  }

  async function submitAndNext(itemId: number, isCorrect: boolean, answer?: string) {
    if (sessionId == null) return;
    await recordAnswer(sessionId, {
      item_id: itemId,
      is_correct: isCorrect,
      // Dạng bài chấm khách quan: server chấm lại từ chính đáp án này (thiếu là 422).
      answer,
      response_time_ms: Date.now() - shownAtRef.current,
      exercise_format: studyMode === 'mixed' ? (index % 2 === 0 ? 'quiz' : 'typing') : studyMode,
      selection_reason: studyMode === 'dkt_smart' ? selectionById[itemId] ?? null : undefined,
    });
    setResults((r) => [...r, isCorrect]);
    await advance();
  }

  /** Pilot — người học chọn nghĩa (hoặc "không biết"): ghi ngay, rồi mở mặt sau thẻ. */
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
        selection_reason: selectionById[itemId] ?? null,
      });
      setGateChoice(choice);
      setResults((r) => [...r, choice === gate.options[gate.correct_index]]);
      setFlipped(true);
    } finally {
      setGateBusy(false);
    }
  }

  /** UC-28 — chấm một lần ghép cặp. Ghép đúng thì cặp đó biến mất khỏi lượt. */
  async function submitMatch(meaning: string) {
    if (sessionId == null || matching == null || pickedWord == null) return;
    const pair = matching.pairs.find((p) => p.item_id === pickedWord);
    if (!pair) return;

    const isCorrect = pair.meaning === meaning;
    await recordAnswer(sessionId, {
      item_id: pair.item_id,
      is_correct: isCorrect,
      answer: meaning,
      response_time_ms: Date.now() - shownAtRef.current,
      exercise_format: 'matching',
    });

    sound.play(isCorrect);
    if (isCorrect) {
      setResults((r) => [...r, true]);
      const done = [...matchedIds, pair.item_id];
      setMatchedIds(done);
      setPickedWord(null);
      setWrongMeaning(null);
      shownAtRef.current = Date.now();
      if (done.length >= matching.pairs.length) await finish();
    } else {
      // Giữ lại từ đang chọn để thử tiếp, chỉ nháy đỏ ô nghĩa vừa chọn sai
      setWrongMeaning(meaning);
      setTimeout(() => setWrongMeaning(null), 600);
    }
  }

  async function submitSm2(itemId: number, rating: 'again' | 'hard' | 'good' | 'easy') {
    if (sessionId == null) return;
    await recordAnswer(sessionId, {
      item_id: itemId,
      is_correct: rating !== 'again',  // Lại = quên
      response_time_ms: Date.now() - shownAtRef.current,
      exercise_format: 'sm2',
      sm2_rating: rating,
    });
    setResults((r) => [...r, rating !== 'again']);
    await advance();
  }

  if (!auth.token) {
    return <Navigate to="/login" replace />;
  }

  const backToSet = () => navigate(wordSetId == null ? '/' : `/word-sets/${wordSetId}`);
  const backLabel = wordSetId == null ? 'Về trang chủ' : 'Về bộ từ';

  if (phase === 'loading') {
    return <StudyMessage title="Đang xếp thẻ cho bạn…" mood="nghi" />;
  }

  if (phase === 'error') {
    return (
      <StudyMessage title="Ối, có lỗi rồi" mood="nghi"
        actions={<Button variant="contained" onClick={backToSet}>{backLabel}</Button>}>
        {errorMsg || 'Đã xảy ra lỗi.'}
      </StudyMessage>
    );
  }

  if (phase === 'empty') {
    return (
      <StudyMessage title="Chưa có từ nào để học" mood="ngu"
        actions={<Button variant="contained" onClick={backToSet}>{backLabel}</Button>}>
        {isToday
          ? 'Hôm nay không còn từ mới nào cần học. Quay lại trang chủ nhé.'
          : 'Bộ từ vựng này chưa có từ nào cho chế độ này.'}
      </StudyMessage>
    );
  }

  if (phase === 'resume') {
    return (
      <StudyMessage
        title="Bạn còn một phiên học dở"
        mood="vui"
        actions={
          <>
            <Button variant="contained" onClick={() => void resumeExisting()}>Học tiếp phiên trước</Button>
            <Button variant="outlined" onClick={() => void startNew()}>Bắt đầu mới</Button>
          </>
        }
      >
        Đã làm {resumeAnswered.length} từ. Học tiếp để không mất tiến độ nhé.
      </StudyMessage>
    );
  }

  if (phase === 'summary' && summary) {
    return (
      <SessionSummaryView
        summary={summary}
        primary={{ label: backLabel, onClick: backToSet }}
        secondary={{ label: 'Trang chủ', onClick: () => navigate('/') }}
      />
    );
  }

  // phase === 'running'
  const answeredUnits = studyMode === 'matching' ? matchedIds.length : index;

  // So khớp bỏ qua hoa/thường và khoảng trắng thừa
  const isTypingCorrect =
    (stepMode === 'typing' || stepMode === 'dictation') && typings[stepIndex]
      ? typed.trim().toLowerCase() === typings[stepIndex].answer.trim().toLowerCase()
      : false;

  const isClozeCorrect =
    studyMode === 'cloze' && clozes[stepIndex]
      ? typed.trim().toLowerCase() === clozes[stepIndex].answer.trim().toLowerCase()
      : false;

  const isCardMode = stepMode === 'flashcard' || stepMode === 'dkt_smart' || stepMode === 'sm2';
  const card = isCardMode ? items[stepIndex] : undefined;
  const gate = card && stepMode === 'dkt_smart' ? gateById[card.id] : undefined;
  const nextLabel = index + 1 >= total ? 'Hoàn thành' : 'Tiếp tục';

  const hints = gate
    ? <><span><kbd>1-4</kbd>chọn nghĩa</span><span><kbd>0</kbd>không biết</span><span><kbd>Enter</kbd>tiếp</span></>
    : isCardMode
      ? <><span><kbd>Space</kbd>lật thẻ</span><span><kbd>{stepMode === 'sm2' ? '1-4' : '1-2'}</kbd>đánh giá</span></>
      : stepMode === 'quiz' || stepMode === 'matching'
        ? undefined
        : <><span><kbd>Enter</kbd>kiểm tra</span></>;

  /** Ô nhập cho ba dạng gõ (điền từ, gõ từ, nghe chép) — nằm trong thẻ. */
  const typeInput = (opts: { label: string; correct: boolean }) => (
    <TextField
      fullWidth autoFocus label={opts.label}
      value={typed} disabled={checked}
      onChange={(e) => setTyped(e.target.value)}
      onKeyDown={(e) => { if (e.key === 'Enter' && typed.trim() && !checked) checkTyped(opts.correct); }}
      slotProps={{ htmlInput: { autoCapitalize: 'off', autoCorrect: 'off', spellCheck: false } }}
      sx={{ '& .MuiInputBase-input': { fontSize: 18, fontWeight: 800, textAlign: 'center' } }}
    />
  );

  /** Nút Kiểm tra, hoặc dải kết quả sau khi kiểm tra — ở đáy màn. */
  const typeFooter = (opts: { correct: boolean; answer: string; onNext: () => void }) => (
    !checked ? (
      <AnswerBar>
        <AnswerButton shortcut="Enter" label="Kiểm tra" color={PRIMARY} disabled={!typed.trim()} onClick={() => checkTyped(opts.correct)} />
      </AnswerBar>
    ) : (
      <FeedbackBar
        tone={opts.correct ? 'right' : 'wrong'}
        title={opts.correct ? 'Chính xác!' : 'Chưa đúng rồi'}
        detail={opts.correct ? undefined : <>Đáp án: <b>{opts.answer}</b></>}
        nextLabel={nextLabel}
        onNext={opts.onNext}
      />
    )
  );

  const quizQ = stepMode === 'quiz' ? questions[stepIndex] : undefined;

  return (
    <StudyShell
      title={setTitle}
      modeLabel={MODE_LABELS[studyMode] ?? studyMode}
      note={practiceOnly ? 'Luyện thêm - không đổi lịch ôn' : undefined}
      done={answeredUnits}
      total={total}
      results={results}
      onExit={backToSet}
      hints={hints}
    >
      {/* THẺ TỪ: FLASHCARD / HỌC THÔNG MINH / SM-2 */}
      {card && (
        <>
          <WordCard
            seed={card.id}
            no={stepIndex + 1}
            word={card.word}
            phonetic={card.phonetic}
            partOfSpeech={card.part_of_speech}
            // Chỉ hiện SAU khi trả lời: thấy trước con số dễ khiến người học trả lời theo nó
            mastery={stepMode === 'dkt_smart' && flipped ? masteryById[card.id] : undefined}
            footer={setTitle}
            // Có câu chọn nghĩa thì thẻ giữ nguyên mặt trước: nghĩa đúng đã tô xanh
            // trong lưới và nhắc lại ở dải kết quả — lật thẻ sẽ đẩy nút xuống dưới màn.
            flipped={gate ? false : flipped}
            onFlip={!gate && !flipped ? () => setFlipped(true) : undefined}
            back={
              <>
                <Typography sx={{ fontWeight: 900, fontSize: { xs: 21, sm: 25 }, lineHeight: 1.35 }}>
                  {card.meaning}
                  <MeaningConfidenceMark confidence={card.meaning_confidence} />
                </Typography>
                {card.example && (
                  <Box
                    sx={{
                      mt: 1.5, p: 1.5, display: 'flex', alignItems: 'center', gap: 1, textAlign: 'left',
                      bgcolor: '#FAF5F0', borderRadius: '16px',
                    }}
                  >
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography sx={{ fontStyle: 'italic', fontSize: 15, fontWeight: 700 }}>{card.example}</Typography>
                      {card.example_vi && (
                        <Typography sx={{ mt: 0.5, fontSize: 14, color: 'text.secondary' }}>
                          {card.example_vi}
                        </Typography>
                      )}
                    </Box>
                    <SpeakButton text={card.example} label="Nghe câu ví dụ" />
                  </Box>
                )}
              </>
            }
          />

          {gate ? (
            <QuizGate
              question={gate}
              chosen={gateChoice}
              busy={gateBusy}
              onAnswer={(c) => void answerGate(card.id, c)}
              onNext={() => void advance()}
              nextLabel={nextLabel}
              detail={card.example ? <>“{card.example}”</> : undefined}
            />
          ) : !flipped ? (
            <AnswerBar>
              <AnswerButton shortcut="Space" label="Lật thẻ" color={PRIMARY} onClick={() => setFlipped(true)} />
            </AnswerBar>
          ) : stepMode === 'sm2' ? (
            <AnswerBar>
              <AnswerButton shortcut="1" label="Quên" color={WRONG_RED} onClick={() => void submitSm2(card.id, 'again')} />
              <AnswerButton shortcut="2" label="Khó" color={FLAT.yellow} onClick={() => void submitSm2(card.id, 'hard')} />
              <AnswerButton shortcut="3" label="Nhớ" color={PRIMARY} onClick={() => void submitSm2(card.id, 'good')} />
              <AnswerButton shortcut="4" label="Dễ" color={FLAT.blue} onClick={() => void submitSm2(card.id, 'easy')} />
            </AnswerBar>
          ) : (
            <AnswerBar>
              <AnswerButton shortcut="1" label="Chưa nhớ" color={WRONG_RED} onClick={() => void submitAndNext(card.id, false)} />
              <AnswerButton shortcut="2" label="Nhớ rồi" color={PRIMARY} onClick={() => void submitAndNext(card.id, true)} />
            </AnswerBar>
          )}
        </>
      )}

      {/* ĐIỀN TỪ */}
      {stepMode === 'cloze' && clozes[stepIndex] && (
        <>
          <StudyCard label="Điền từ còn thiếu" tone={checked ? (isClozeCorrect ? 'right' : 'wrong') : 'default'}>
            <Typography sx={{ fontSize: { xs: 19, sm: 22 }, fontWeight: 800, lineHeight: 1.6, mb: 1.5 }}>
              {clozes[stepIndex].sentence}
            </Typography>
            <Chip size="small" label={`Gợi ý: ${clozes[stepIndex].hint}`} sx={{ mb: 2.5 }} />
            {typeInput({ label: 'Từ cần điền', correct: isClozeCorrect })}
          </StudyCard>
          {typeFooter({
            correct: isClozeCorrect,
            answer: clozes[stepIndex].answer,
            onNext: () => void submitAndNext(clozes[stepIndex].item_id, isClozeCorrect, typed),
          })}
        </>
      )}

      {/* GÕ TỪ */}
      {stepMode === 'typing' && typings[stepIndex] && (
        <>
          <StudyCard label="Gõ từ tiếng Anh có nghĩa là" tone={checked ? (isTypingCorrect ? 'right' : 'wrong') : 'default'}>
            <Typography sx={{ fontSize: { xs: 23, sm: 28 }, fontWeight: 900, lineHeight: 1.35, mb: 1.5 }}>
              {typings[stepIndex].meaning}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', mb: 2.5 }}>
              {typings[stepIndex].part_of_speech && <Chip size="small" label={typings[stepIndex].part_of_speech} />}
              <Chip
                size="small"
                color="secondary"
                sx={{ fontWeight: 900, letterSpacing: '0.08em' }}
                label={`${typings[stepIndex].first_letter}${'_'.repeat(Math.max(typings[stepIndex].length - 1, 0))} · ${typings[stepIndex].length} chữ cái`}
              />
            </Box>
            {typeInput({ label: 'Từ tiếng Anh', correct: isTypingCorrect })}
          </StudyCard>
          {typeFooter({
            correct: isTypingCorrect,
            answer: typings[stepIndex].answer,
            onNext: () => void submitAndNext(typings[stepIndex].item_id, isTypingCorrect, typed),
          })}
        </>
      )}

      {/* NGHE CHÉP */}
      {stepMode === 'dictation' && typings[stepIndex] && (
        <>
          <StudyCard label="Nghe rồi gõ lại" tone={checked ? (isTypingCorrect ? 'right' : 'wrong') : 'default'}>
            {!speech.supported ? (
              <Alert severity="warning" sx={{ mb: 2, textAlign: 'left' }}>
                Trình duyệt này không đọc được. Hãy dùng Chrome hoặc Edge, hoặc chọn chế độ &quot;Gõ từ&quot; thay thế.
              </Alert>
            ) : (
              <Box sx={{ mb: 2.5 }}>
                <Button
                  variant="contained"
                  color="info"
                  size="large"
                  startIcon={<SpeakerIcon />}
                  onClick={() => speech.speak(typings[stepIndex].answer)}
                  sx={{ px: 4 }}
                >
                  {speech.speaking ? 'Đang đọc…' : 'Nghe lại'}
                </Button>
                <Typography sx={{ mt: 1.25, color: 'text.secondary', fontWeight: 700 }}>
                  Nghĩa: {typings[stepIndex].meaning}
                </Typography>
              </Box>
            )}
            {typeInput({ label: 'Từ vừa nghe', correct: isTypingCorrect })}
          </StudyCard>
          {typeFooter({
            correct: isTypingCorrect,
            answer: typings[stepIndex].answer,
            onNext: () => void submitAndNext(typings[stepIndex].item_id, isTypingCorrect, typed),
          })}
        </>
      )}

      {/* GHÉP CẶP */}
      {stepMode === 'matching' && matching && (
        <StudyCard label="Ghép từ với nghĩa">
          <Typography sx={{ color: 'text.secondary', fontWeight: 700, mb: 2 }}>
            Chọn một từ bên trái, rồi chọn nghĩa đúng bên phải.
          </Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: { xs: 1, sm: 2 }, textAlign: 'left' }}>
            <Box sx={{ display: 'grid', gap: 1, alignContent: 'start' }}>
              {matching.pairs.map((pair) => {
                const done = matchedIds.includes(pair.item_id);
                return (
                  <Button
                    key={pair.item_id}
                    variant={pickedWord === pair.item_id ? 'contained' : 'outlined'}
                    color={done ? 'success' : pickedWord === pair.item_id ? 'secondary' : 'primary'}
                    disabled={done}
                    onClick={() => setPickedWord(pair.item_id)}
                    sx={{ justifyContent: 'flex-start', py: 1.1, borderRadius: '14px' }}
                  >
                    {pair.word}
                  </Button>
                );
              })}
            </Box>
            <Box sx={{ display: 'grid', gap: 1, alignContent: 'start' }}>
              {matching.shuffled_meanings.map((meaning) => {
                const done = matching.pairs.some((p) => p.meaning === meaning && matchedIds.includes(p.item_id));
                const wrong = wrongMeaning === meaning;
                return (
                  <Button
                    key={meaning}
                    variant={wrong ? 'contained' : 'outlined'}
                    color={done ? 'success' : wrong ? 'error' : 'inherit'}
                    disabled={done || pickedWord === null}
                    onClick={() => void submitMatch(meaning)}
                    sx={{ justifyContent: 'flex-start', py: 1.1, fontWeight: 700, borderRadius: '14px' }}
                  >
                    {meaning}
                  </Button>
                );
              })}
            </Box>
          </Box>
        </StudyCard>
      )}

      {/* TRẮC NGHIỆM */}
      {quizQ && (
        <>
          {/* Câu hỏi nền xanh đậm, khác màu với các ô đáp án trắng */}
          <Box sx={{ flexShrink: 0, bgcolor: QUESTION_BG, color: '#FFFFFF', borderRadius: '28px', boxShadow: SOFT_SHADOW, px: 3, py: { xs: 3, sm: 4 }, textAlign: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
              <Typography sx={{ fontWeight: 900, fontSize: { xs: 32, sm: 40 }, letterSpacing: '-0.015em', lineHeight: 1.15, color: '#FFFFFF' }}>
                {quizQ.word}
              </Typography>
              <Box sx={{ bgcolor: 'rgba(255,255,255,0.18)', borderRadius: '50%', '& .MuiIconButton-root': { color: '#FFFFFF' } }}>
                <SpeakButton text={quizQ.word} size={22} />
              </Box>
            </Box>
          </Box>
          <Typography sx={{ mt: { xs: 2, sm: 2.5 }, mb: 1.25, color: 'text.secondary', fontWeight: 800, textAlign: 'center' }}>
            Từ này nghĩa là gì?
          </Typography>
          <OptionGrid>
            {quizQ.options.map((opt, optIndex) => {
              const isCorrect = optIndex === quizQ.correct_index;
              const answered = selected !== null;
              const state = !answered ? 'idle' : isCorrect ? 'right' : optIndex === selected ? 'wrong' : 'muted';
              return (
                <OptionTile
                  key={optIndex}
                  index={optIndex + 1}
                  label={opt}
                  state={state}
                  disabled={answered}
                  onClick={() => {
                    setSelected(optIndex);
                    sound.play(optIndex === quizQ.correct_index);
                  }}
                />
              );
            })}
          </OptionGrid>
          {selected !== null && (
            <FeedbackBar
              tone={selected === quizQ.correct_index ? 'right' : 'wrong'}
              title={selected === quizQ.correct_index ? 'Chính xác!' : 'Chưa đúng rồi'}
              detail={selected === quizQ.correct_index ? undefined : <>Đáp án: <b>{quizQ.options[quizQ.correct_index]}</b></>}
              nextLabel={nextLabel}
              onNext={() =>
                void submitAndNext(quizQ.item_id, selected === quizQ.correct_index, quizQ.options[selected])
              }
            />
          )}
        </>
      )}
    </StudyShell>
  );
}

export default Study;
