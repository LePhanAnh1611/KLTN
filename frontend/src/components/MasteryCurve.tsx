import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

import type { MasteryHistory, MasteryPoint } from '../api/progress';
import { formatLabel } from '../types/labels';

/** UC-92 — đường cong mastery của một từ theo thời gian.
 *
 * Vì sao dấu đúng/sai dùng HÌNH DẠNG chứ không chỉ màu: cặp xanh/đỏ của theme
 * có ΔE 5,9 với người mù màu deutan (đo bằng bộ kiểm palette) — dưới cả ngưỡng
 * sàn, tức hai màu đó gần như không phân biệt được. Chấm ĐẶC = đúng, vòng RỖNG
 * = sai; màu chỉ là lớp củng cố.
 */

const W = 640;
const H = 220;
const PAD = { top: 16, right: 16, bottom: 34, left: 42 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

interface Props {
  data: MasteryHistory;
}

interface Plotted {
  point: MasteryPoint;
  index: number;
  x: number;
  y: number | null;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getDate()}/${d.getMonth() + 1} ${String(d.getHours()).padStart(2, '0')}:${String(
    d.getMinutes(),
  ).padStart(2, '0')}`;
}

function MasteryCurve({ data }: Props) {
  const theme = useTheme();
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const [hover, setHover] = useState<number | null>(null);

  const points: Plotted[] = useMemo(() => {
    const n = data.points.length;
    return data.points.map((point, index) => ({
      point,
      index,
      x: PAD.left + (n <= 1 ? PLOT_W / 2 : (index / (n - 1)) * PLOT_W),
      y: point.mastery === null ? null : PAD.top + (1 - point.mastery) * PLOT_H,
    }));
  }, [data.points]);

  if (data.points.length === 0) {
    return (
      <Alert severity="info">
        Chưa có lượt trả lời nào cho từ này - học một phiên là đường cong bắt đầu hiện.
      </Alert>
    );
  }

  const line = theme.palette.primary.main;
  const ink = theme.palette.text.primary;
  const muted = theme.palette.text.secondary;
  const surface = theme.palette.background.paper;
  const grid = alpha(ink, 0.12);
  const thresholdY = PAD.top + (1 - data.mastered_threshold) * PLOT_H;

  // Chỉ nối các điểm LIỀN NHAU có dự đoán. Nối xuyên qua chỗ thiếu dữ liệu là
  // vẽ ra một đoạn đường không tồn tại.
  const segments: Plotted[][] = [];
  let run: Plotted[] = [];
  for (const p of points) {
    if (p.y === null) {
      if (run.length > 1) segments.push(run);
      run = [];
    } else {
      run.push(p);
    }
  }
  if (run.length > 1) segments.push(run);

  const active = hover === null ? null : points[hover];

  if (view === 'table') {
    return (
      <Box>
        <ViewToggle view={view} onChange={setView} />
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Thời điểm</TableCell>
              <TableCell>Mức nhớ trước khi trả lời</TableCell>
              <TableCell>Kết quả</TableCell>
              <TableCell>Nguồn</TableCell>
              <TableCell>Dạng bài</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.points.map((p, i) => (
              <TableRow key={`${p.answered_at}-${i}`}>
                <TableCell>{formatTime(p.answered_at)}</TableCell>
                <TableCell>{p.mastery === null ? '-' : `${Math.round(p.mastery * 100)}%`}</TableCell>
                <TableCell>{p.is_correct ? 'Đúng' : 'Sai'}</TableCell>
                <TableCell>{p.source === 'model' ? 'Mô hình' : p.source === 'prior' ? 'Khởi tạo' : '-'}</TableCell>
                <TableCell>{formatLabel(p.exercise_format) || '-'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    );
  }

  return (
    <Box>
      <ViewToggle view={view} onChange={setView} />

      <Box sx={{ width: '100%', overflowX: 'auto' }}>
        <Box
          component="svg"
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`Mức nhớ của từ ${data.word} qua ${data.total_answers} lượt trả lời`}
          sx={{ width: '100%', minWidth: 420, display: 'block' }}
          onMouseLeave={() => setHover(null)}
        >
          {/* lưới ngang — lùi hẳn về sau, không tranh chỗ với dữ liệu */}
          {[0, 0.25, 0.5, 0.75, 1].map((v) => {
            const y = PAD.top + (1 - v) * PLOT_H;
            return (
              <g key={v}>
                <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke={grid} strokeWidth={1} />
                <text x={PAD.left - 8} y={y + 4} textAnchor="end" fontSize={11} fill={muted}>
                  {Math.round(v * 100)}%
                </text>
              </g>
            );
          })}

          {/* vạch "đã thuộc" (BR-01) — có nhãn chữ, không chỉ dựa vào nét đứt */}
          <line
            x1={PAD.left} y1={thresholdY} x2={W - PAD.right} y2={thresholdY}
            stroke={theme.palette.warning.main} strokeWidth={1.5} strokeDasharray="5 4"
          />
          <text
            x={W - PAD.right} y={thresholdY - 6} textAnchor="end" fontSize={11}
            fill={theme.palette.warning.main}
          >
            Đã thuộc ({Math.round(data.mastered_threshold * 100)}%)
          </text>

          {segments.map((seg, i) => (
            <polyline
              key={i}
              points={seg.map((p) => `${p.x},${p.y}`).join(' ')}
              fill="none" stroke={line} strokeWidth={2}
              strokeLinecap="round" strokeLinejoin="round"
            />
          ))}

          {active && active.y !== null && (
            <line
              x1={active.x} y1={PAD.top} x2={active.x} y2={PAD.top + PLOT_H}
              stroke={alpha(ink, 0.28)} strokeWidth={1}
            />
          )}

          {points.map((p) =>
            p.y === null ? null : (
              <circle
                key={p.index}
                cx={p.x} cy={p.y} r={5}
                // Đặc = đúng · rỗng = sai. Đây là phân biệt CHÍNH, màu chỉ củng cố.
                fill={p.point.is_correct ? theme.palette.success.main : surface}
                stroke={p.point.is_correct ? surface : theme.palette.error.main}
                strokeWidth={2}
              />
            ),
          )}

          {/* vùng bắt chuột rộng hơn dấu để dễ trỏ */}
          {points.map((p) => (
            <rect
              key={`hit-${p.index}`}
              x={p.x - PLOT_W / Math.max(points.length, 1) / 2} y={PAD.top}
              width={PLOT_W / Math.max(points.length, 1)} height={PLOT_H}
              fill="transparent"
              onMouseEnter={() => setHover(p.index)}
            />
          ))}

          <text x={PAD.left} y={H - 10} fontSize={11} fill={muted}>
            {formatTime(data.points[0].answered_at)}
          </text>
          {data.points.length > 1 && (
            <text x={W - PAD.right} y={H - 10} textAnchor="end" fontSize={11} fill={muted}>
              {formatTime(data.points[data.points.length - 1].answered_at)}
            </text>
          )}
        </Box>
      </Box>

      {active && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          <strong>{formatTime(active.point.answered_at)}</strong>
          {' · '}
          {active.point.mastery === null
            ? 'chưa có dự đoán'
            : `mastery trước khi trả lời ${Math.round(active.point.mastery * 100)}%`}
          {' · '}
          {active.point.is_correct ? 'trả lời đúng' : 'trả lời sai'}
          {formatLabel(active.point.exercise_format)
            ? ` · ${formatLabel(active.point.exercise_format)}`
            : ''}
        </Typography>
      )}

      <Stack direction="row" spacing={2} sx={{ mt: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
        <LegendMark filled label="Trả lời đúng" />
        <LegendMark filled={false} label="Trả lời sai" />
        <Typography variant="caption" color="text.secondary">
          Mỗi chấm là mức hệ thống đoán bạn nhớ từ này <strong>ngay trước</strong> lần trả lời đó
          {data.answers_without_prediction > 0
            && ` · ${data.answers_without_prediction} lượt chưa có dự đoán nên đường bị ngắt`}
        </Typography>
      </Stack>
    </Box>
  );
}

function LegendMark({ filled, label }: { filled: boolean; label: string }) {
  const theme = useTheme();
  return (
    <Stack direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
      <Box
        component="span"
        sx={{
          width: 10, height: 10, borderRadius: '50%',
          bgcolor: filled ? 'success.main' : 'background.paper',
          border: filled ? 'none' : `2px solid ${theme.palette.error.main}`,
        }}
      />
      <Typography variant="caption" color="text.secondary">{label}</Typography>
    </Stack>
  );
}

function ViewToggle({ view, onChange }: {
  view: 'chart' | 'table'; onChange: (v: 'chart' | 'table') => void;
}) {
  return (
    <ToggleButtonGroup
      size="small" exclusive value={view} sx={{ mb: 1.5 }}
      onChange={(_, v) => v && onChange(v)}
    >
      <ToggleButton value="chart">Biểu đồ</ToggleButton>
      <ToggleButton value="table">Bảng số</ToggleButton>
    </ToggleButtonGroup>
  );
}

export default MasteryCurve;
