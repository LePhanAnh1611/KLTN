import { useEffect } from 'react';
import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';

import { FeedbackBar, OptionGrid, OptionTile } from './StudyShell';
import { useAnswerSound, useSoundOnResult } from '../hooks/useAnswerSound';
import type { QuizQuestion } from '../types/session';

/**
 * Câu hỏi chọn nghĩa đặt TRƯỚC khi lật thẻ (Học thông minh, Ôn tập).
 *
 * Vì sao: thẻ lật cũ để người học tự bấm "Đã thuộc/Chưa thuộc" — dữ liệu tự
 * khai, không dùng được để kiểm chứng mastery của DKT. Ở đây người học chọn
 * một trong 4 nghĩa, hệ thống chấm. "Tôi không biết" có sẵn để khỏi đoán mò:
 * đoán bừa làm nhiễu dữ liệu nhiều hơn là trả lời sai thật.
 *
 * Bản flat: 4 lựa chọn xếp lưới 2×2; kết quả + nút Tiếp tục hiện trong dải ở
 * đáy màn (FeedbackBar) kèm âm báo đúng/sai.
 *
 * Component chỉ hiển thị; ghi câu trả lời do trang cha làm (`onAnswer`).
 * Phím tắt: 1–4 chọn đáp án, 0 = không biết, Enter = tiếp tục.
 */
interface Props {
  question: QuizQuestion;
  /** undefined = chưa trả lời · null = "không biết" · chuỗi = nghĩa đã chọn */
  chosen: string | null | undefined;
  busy?: boolean;
  onAnswer: (choice: string | null) => void;
  onNext: () => void;
  /** Hiện trong dải kết quả sau khi trả lời (VD câu ví dụ). */
  detail?: ReactNode;
  nextLabel?: string;
}

function QuizGate({ question, chosen, busy = false, onAnswer, onNext, detail, nextLabel }: Props) {
  const answered = chosen !== undefined;
  const correctText = question.options[question.correct_index];
  const right = chosen === correctText;
  const { play } = useAnswerSound();
  useSoundOnResult(answered ? right : undefined, play);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (document.activeElement?.tagName ?? '').toUpperCase();
      if (['INPUT', 'TEXTAREA'].includes(tag) || busy) return;
      if (!answered) {
        const n = Number(e.key);
        if (n >= 1 && n <= question.options.length) {
          e.preventDefault();
          onAnswer(question.options[n - 1]);
        } else if (e.key === '0') {
          e.preventDefault();
          onAnswer(null);
        }
      } else if (e.key === 'Enter' || e.code === 'Space') {
        e.preventDefault();
        onNext();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [answered, busy, question, onAnswer, onNext]);

  return (
    <>
      <Box sx={{ mt: { xs: 2, sm: 2.5 }, width: '100%' }}>
        <Typography sx={{ mb: 1.25, fontWeight: 800, color: 'text.secondary', fontSize: 15, textAlign: 'center' }}>
          Chọn nghĩa đúng của từ này
        </Typography>
        <OptionGrid>
          {question.options.map((opt, i) => {
            const isCorrect = opt === correctText;
            const isChosen = opt === chosen;
            const state = !answered ? 'idle' : isCorrect ? 'right' : isChosen ? 'wrong' : 'muted';
            return (
              <OptionTile
                key={opt}
                index={i + 1}
                label={opt}
                state={state}
                disabled={busy || answered}
                onClick={() => { if (!answered) onAnswer(opt); }}
              />
            );
          })}
        </OptionGrid>
      </Box>

      {!answered ? (
        <Box sx={{ mt: { xs: 'auto', sm: 0 }, pt: { xs: 2, sm: 2.5 }, textAlign: 'center', flexShrink: 0 }}>
          <Button disabled={busy} onClick={() => onAnswer(null)} sx={{ color: 'text.secondary', fontSize: 15 }}>
            <Box component="span" sx={{ mr: 0.75, display: { xs: 'none', md: 'inline' } }}><kbd>0</kbd></Box>
            Tôi không biết từ này
          </Button>
        </Box>
      ) : (
        <FeedbackBar
          tone={right ? 'right' : 'wrong'}
          title={right ? 'Chính xác!' : chosen === null ? 'Không sao, nhớ nghĩa này nhé' : 'Chưa đúng rồi'}
          detail={(
            <>
              {!right && <Box component="span">Đáp án: <b>{correctText}</b></Box>}
              {detail && <Box sx={{ mt: right ? 0 : 0.25, fontWeight: 600, color: 'text.secondary', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{detail}</Box>}
            </>
          )}
          nextLabel={nextLabel}
          onNext={onNext}
          busy={busy}
        />
      )}
    </>
  );
}

export default QuizGate;
