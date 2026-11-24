import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import {
  CRITERIA,
  CRITERION_CODES,
  CRITERION_LABELS,
  useCreateAppeal,
  type AudioMetrics,
  type Criterion,
  type CriterionResult,
} from '../api/speaking';
import { ApiError } from '../api/client';
import SectionCard from './SectionCard';

const LEVEL_COLOR: Record<number, 'error' | 'warning' | 'info' | 'success'> = {
  1: 'error', 2: 'warning', 3: 'info', 4: 'success',
};

/** Nhãn nguồn chấm. `fallback` PHẢI phân biệt rõ với mức thật, nếu không người
 * học sẽ đọc "mức 1" thành "mình yếu" trong khi thực ra là hệ thống chưa chấm. */
const SCORED_BY_LABEL: Record<string, { text: string; hint: string }> = {
  rule: {
    text: 'Đo tự động',
    hint: 'Suy từ mốc thời gian và độ tin cậy nhận dạng - cùng một bản ghi luôn ra cùng một mức.',
  },
  llm: {
    text: 'Mô hình chấm',
    hint: 'Mô hình ngôn ngữ chạy trên máy chủ chấm theo mô tả rubric.',
  },
  fallback: {
    text: 'CHƯA chấm được',
    hint: 'Mô hình ngôn ngữ không sẵn sàng. Mức hiển thị KHÔNG phản ánh bài nói của bạn.',
  },
};

function CriterionCard({ criterion, result, onAppeal }: {
  criterion: Criterion;
  result: CriterionResult;
  onAppeal?: (criterion: Criterion) => void;
}) {
  const unscored = result.scored_by === 'fallback';
  const badge = SCORED_BY_LABEL[result.scored_by] ?? SCORED_BY_LABEL.rule;

  return (
    <SectionCard sx={{ mb: 2, opacity: unscored ? 0.75 : 1 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
        <Chip size="small" label={CRITERION_CODES[criterion]} />
        <Typography variant="subtitle1" sx={{ fontWeight: 700, flexGrow: 1 }}>
          {CRITERION_LABELS[criterion]}
        </Typography>
        <Tooltip title={badge.hint}>
          <Chip
            size="small" variant="outlined"
            color={unscored ? 'warning' : 'default'}
            label={badge.text}
          />
        </Tooltip>
        <Chip
          color={unscored ? 'default' : LEVEL_COLOR[result.level]}
          label={unscored ? '-' : `Mức ${result.level} · ${result.label}`}
        />
      </Box>

      {unscored ? (
        <Alert severity="warning">{result.reason}</Alert>
      ) : (
        <>
          {result.evidence.length > 0 && (
            <Box component="ul" sx={{ pl: 2.5, my: 1 }}>
              {result.evidence.map((line, index) => (
                <Typography key={index} component="li" variant="body2"
                            color="text.secondary" sx={{ mb: 0.5 }}>
                  {line}
                </Typography>
              ))}
            </Box>
          )}

          <Alert severity="info" sx={{ mt: 1 }}>
            <strong>Gợi ý cải thiện:</strong> {result.suggestion}
          </Alert>

          {result.reason && (
            <Typography variant="caption" color="text.secondary"
                        sx={{ display: 'block', mt: 1 }}>
              Vì sao mức này: {result.reason}
            </Typography>
          )}
        </>
      )}

      {onAppeal && !unscored && (
        <Button size="small" sx={{ mt: 1 }} onClick={() => onAppeal(criterion)}>
          Tôi thấy chấm chưa đúng
        </Button>
      )}
    </SectionCard>
  );
}

function MetricsRow({ metrics }: { metrics: AudioMetrics }) {
  const items = [
    { label: 'Thời lượng', value: `${metrics.duration_sec.toFixed(1)}s` },
    { label: 'Tốc độ', value: `${Math.round(metrics.words_per_minute)} từ/phút` },
    { label: 'Ngắt nghỉ', value: `${Math.round(metrics.pause_ratio * 100)}%` },
    { label: 'Từ đệm', value: String(metrics.filler_count) },
    { label: 'Nhận dạng', value: `${Math.round(metrics.asr_avg_confidence * 100)}%` },
    { label: 'Số từ', value: String(metrics.word_count) },
  ];

  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
      {items.map((item) => (
        <Box key={item.label} sx={{ minWidth: 96 }}>
          <Typography variant="caption" color="text.secondary">{item.label}</Typography>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>{item.value}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function AppealDialog({ attemptId, criterion, onClose, onResult }: {
  attemptId: number;
  criterion: Criterion | null;
  onClose: () => void;
  onResult: (msg: string) => void;
}) {
  const [expected, setExpected] = useState<number | ''>('');
  const [comment, setComment] = useState('');
  const appeal = useCreateAppeal();

  return (
    <Dialog open={criterion !== null} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Phản hồi về kết quả chấm</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Phản hồi của bạn <strong>không làm thay đổi điểm</strong> - nó được gửi cho
          người phụ trách rubric để rà lại mô tả tiêu chí. Chỗ nhiều người thấy chấm
          sai chính là chỗ rubric còn mơ hồ.
        </Typography>

        <TextField
          select fullWidth size="small" label="Theo bạn thì đúng ra là mức nào?"
          value={expected} onChange={(e) => setExpected(Number(e.target.value))}
          sx={{ mb: 2 }}
        >
          {[1, 2, 3, 4].map((level) => (
            <MenuItem key={level} value={level}>Mức {level}</MenuItem>
          ))}
        </TextField>

        <TextField
          fullWidth multiline minRows={3} label="Vì sao bạn nghĩ vậy?"
          value={comment} onChange={(e) => setComment(e.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Hủy</Button>
        <Button
          variant="contained"
          disabled={!comment.trim() || appeal.isPending}
          onClick={() => appeal.mutate(
            {
              attemptId,
              criterion: criterion ?? 'overall',
              expectedLevel: expected === '' ? null : expected,
              comment: comment.trim(),
            },
            {
              onSuccess: () => {
                setComment(''); setExpected('');
                onResult('Đã gửi phản hồi. Cảm ơn bạn.');
                onClose();
              },
              onError: (e) => onResult(
                e instanceof ApiError ? e.message : 'Gửi phản hồi thất bại.',
              ),
            },
          )}
        >
          Gửi
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface Props {
  transcript: string;
  audioMetrics: AudioMetrics;
  scores: Record<Criterion, CriterionResult>;
  overallLevel: number;
  developmentalFeedback: string;
  warnings: string[];
  rubricVersion: string;
  attemptId?: number | null;
  onResult?: (msg: string) => void;
}

/** Hiển thị kết quả chấm nói — dùng chung cho màn luyện và màn xem lại lịch sử. */
function SpeakingResult({
  transcript, audioMetrics, scores, overallLevel, developmentalFeedback,
  warnings, rubricVersion, attemptId, onResult,
}: Props) {
  const [appealFor, setAppealFor] = useState<Criterion | null>(null);
  const anyUnscored = CRITERIA.some((key) => scores[key]?.scored_by === 'fallback');

  return (
    <Box>
      {warnings.map((warning) => (
        <Alert key={warning} severity="warning" sx={{ mb: 1.5 }}>{warning}</Alert>
      ))}

      <SectionCard
        title="Nhận xét cho bạn"
        caption={`Rubric v${rubricVersion}`}
        action={
          <Chip
            color={anyUnscored ? 'default' : LEVEL_COLOR[overallLevel]}
            label={`Mức chung: ${overallLevel}`}
          />
        }
        sx={{ mb: 3 }}
      >
        <Typography variant="body1" sx={{ mb: 2 }}>{developmentalFeedback}</Typography>
        <MetricsRow metrics={audioMetrics} />
      </SectionCard>

      {CRITERIA.map((key) => scores[key] && (
        <CriterionCard
          key={key} criterion={key} result={scores[key]}
          onAppeal={attemptId && onResult ? setAppealFor : undefined}
        />
      ))}

      <SectionCard title="Bản gỡ băng" caption="Do Whisper nhận dạng - có thể sai đôi chỗ.">
        <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
          {transcript || '(không nhận dạng được nội dung nào)'}
        </Typography>
      </SectionCard>

      {attemptId && onResult && (
        <AppealDialog
          attemptId={attemptId} criterion={appealFor}
          onClose={() => setAppealFor(null)} onResult={onResult}
        />
      )}
    </Box>
  );
}

export default SpeakingResult;
export { LEVEL_COLOR };
