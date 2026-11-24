import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';

import { useStageSummary, type StageWord } from '../api/roadmap';
import { ACCENT_FONT } from '../theme/theme';

interface Props {
  stageId: number | null;
  onClose: () => void;
  /** Mở phiên ôn đúng những từ còn yếu của chặng (UC-86). */
  onReviewWeak: () => void;
}

function WordColumn({ title, caption, words, tone }: {
  title: string; caption: string; words: StageWord[]; tone: 'success' | 'warning';
}) {
  return (
    <Box>
      <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{title}</Typography>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        {caption}
      </Typography>
      {words.length === 0 ? (
        <Typography variant="body2" color="text.secondary">-</Typography>
      ) : words.map((w) => (
        <Box key={w.item_id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
          <Typography variant="body2" sx={{ flexGrow: 1, minWidth: 0 }} noWrap title={w.meaning}>
            <strong>{w.word}</strong> - {w.meaning}
          </Typography>
          <Chip size="small" color={tone} label={`${Math.round(w.mastery * 100)}%`} />
        </Box>
      ))}
    </Box>
  );
}

/** UC-84 — bảng tổng kết một chặng, mở khi bấm vào mốc trên bản đồ lộ trình. */
function StageSummaryDialog({ stageId, onClose, onReviewWeak }: Props) {
  const { data, isLoading } = useStageSummary(stageId);

  return (
    <Dialog open={stageId !== null} onClose={onClose} fullWidth maxWidth="sm">
      {isLoading && <LinearProgress />}
      {data && (
        <>
          <DialogTitle sx={{ pb: 1 }}>
            <Chip size="small" color="primary" label={data.cefr_level} sx={{ mr: 1 }} />
            <Box component="span" sx={{ fontFamily: ACCENT_FONT, fontWeight: 700 }}>
              {data.title}
            </Box>
          </DialogTitle>

          <DialogContent>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {data.is_complete
                ? 'Bạn đã hoàn thành chặng này.'
                : 'Chặng đang học - đây là tình hình hiện tại.'}
            </Typography>

            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 0.5 }}>
              <LinearProgress
                variant="determinate" value={data.progress_pct}
                sx={{ flexGrow: 1 }}
              />
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {data.items_mastered}/{data.items_total} từ
              </Typography>
            </Box>
            {/* Hai con số khác nhau: "thuộc bao nhiêu" (hiện tại) vs "làm bao nhiêu
                lượt, đúng bao nhiêu" (quá trình) — nói rõ để không bị hiểu lẫn. */}
            <Typography variant="caption" color="text.secondary">
              {data.answers_total > 0
                ? `Đã trả lời ${data.answers_total} lượt, đúng ${data.answers_correct} `
                  + `(${Math.round(data.accuracy * 100)}%).`
                : 'Chưa có lượt trả lời nào trong chặng này.'}
            </Typography>

            <Box sx={{ display: 'grid', gap: 3, mt: 3,
                       gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
              <WordColumn
                title="Nắm chắc nhất" caption="Những từ bạn đã vững"
                words={data.strongest} tone="success"
              />
              <WordColumn
                title="Cần ôn lại" caption="Dưới ngưỡng nắm vững"
                words={data.weakest} tone="warning"
              />
            </Box>

            {data.next_stage_title && (
              <Typography variant="body2" sx={{ mt: 3 }}>
                Chặng tiếp theo: <strong>{data.next_stage_title}</strong>
              </Typography>
            )}
          </DialogContent>

          <DialogActions>
            {data.weakest.length > 0 && (
              <Button onClick={onReviewWeak}>Ôn lại từ còn yếu</Button>
            )}
            <Button variant="contained" onClick={onClose}>Đóng</Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
}

export default StageSummaryDialog;
