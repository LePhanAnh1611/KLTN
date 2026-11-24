import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import { MUTED, PRIMARY, PRIMARY_TEXT } from '../theme/theme';
import { describeSetProgress } from '../utils/setProgress';

/** Màu đoạn "đang học": xanh nhạt cùng họ với "đã thuộc" — đọc như "sắp tới nơi". */
const LEARNING = '#A8DDB5';
const TRACK = '#EDE3D9';

interface SetProgressProps {
  total: number;
  mastered: number;
  learning?: number;
  /** Số từ cần thuộc để xong (chặng lộ trình). Bỏ trống = cả bộ. */
  goal?: number;
  /** Nhãn cho "đã thuộc" — chặng lộ trình dùng "đã đạt" vì ngưỡng khác BR-01. */
  masteredLabel?: string;
  /** Ẩn câu gợi ý (khi chỗ hiển thị quá chật). */
  hideHint?: boolean;
}

function Dot({ color }: { color: string }) {
  return <Box component="span" sx={{ display: 'inline-block', width: 9, height: 9, borderRadius: '50%', bgcolor: color, mr: 0.5, verticalAlign: 'middle' }} />;
}

/**
 * Thanh tiến độ 3 nấc của một bộ từ: đã thuộc · đang học · chưa học, kèm một
 * câu gợi bước tiếp theo. Thay cho thanh % một màu cũ — xem utils/setProgress.
 */
function SetProgress({ total, mastered, learning = 0, goal, masteredLabel = 'đã thuộc', hideHint }: SetProgressProps) {
  const v = describeSetProgress({ total, mastered, learning, goal });
  const legend = `${v.mastered} ${masteredLabel} · ${v.learning} đang học · ${v.fresh} chưa học`;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1, mb: 0.5 }}>
        <Typography component="span" sx={{ fontWeight: 900, fontSize: 14, color: v.done ? PRIMARY_TEXT : 'text.primary', flexGrow: 1, minWidth: 0 }} noWrap>
          {v.mastered}/{v.goal < total ? v.goal : total} {v.goal < total ? 'để qua chặng' : masteredLabel}
        </Typography>
        {v.learning > 0 && (
          <Typography component="span" sx={{ fontWeight: 800, fontSize: 12.5, color: MUTED, whiteSpace: 'nowrap' }}>
            <Dot color={LEARNING} />+{v.learning} đang học
          </Typography>
        )}
      </Box>

      <Tooltip title={legend}>
        <Box
          role="img"
          aria-label={legend}
          sx={{ position: 'relative', display: 'flex', height: 10, borderRadius: 999, bgcolor: TRACK, overflow: 'hidden' }}
        >
          <Box sx={{ width: `${v.masteredPct}%`, bgcolor: PRIMARY, transition: 'width 0.4s ease' }} />
          <Box sx={{ width: `${v.learningPct}%`, bgcolor: LEARNING, transition: 'width 0.4s ease' }} />
          {v.goalPct != null && (
            // Mốc "qua chặng" — cho thấy đích ở 80% chứ không phải cuối thanh
            <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: `calc(${v.goalPct}% - 1px)`, width: 2, bgcolor: 'rgba(46,42,38,0.45)' }} />
          )}
        </Box>
      </Tooltip>

      {!hideHint && (
        <Typography sx={{ mt: 0.5, fontSize: 12.5, fontWeight: 700, color: v.done ? PRIMARY_TEXT : MUTED }} noWrap title={v.hint}>
          {v.hint}
        </Typography>
      )}
    </Box>
  );
}

export default SetProgress;
