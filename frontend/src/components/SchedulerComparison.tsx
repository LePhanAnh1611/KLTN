import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

import { useSchedulerComparison } from '../api/admin';
import type { SchedulerArm } from '../api/admin';

/** UC-93 — so sánh định lượng lịch ôn DKT (UC-66) với SM-2 (UC-34).
 *
 * Màn NỘI BỘ. Đây là số liệu cho chương thực nghiệm, không nói gì về việc học
 * của người dùng — đặt vào giao diện người học chỉ gây hiểu lầm.
 *
 * Bảng màu bốn chuỗi đã qua bộ kiểm mù màu trên MỌI CẶP, không chỉ cặp liền kề
 * — bốn đường cùng hiện một lúc nên cặp nào cũng phải phân biệt được. Chính phép
 * kiểm này bắt được bộ màu tối trước đó: tím và xanh chỉ cách ΔE 2,0 với người
 * mù màu deutan, lọt qua vì chúng không nằm cạnh nhau trong thứ tự.
 *
 * Bộ tối còn một cặp ở mức 6,8 (vùng sàn 6–8), chỉ hợp lệ khi có mã hóa phụ:
 * mỗi đường đều có NHÃN CHỮ ngay đầu mút, và nhánh đối chứng vẽ nét đứt.
 */

const SERIES = {
  light: { dkt: '#1CB0F6', sm2: '#FF9600', dkt_hl: '#D4479B', fixed: '#2E9E6B' },
  dark: { dkt: '#2E9BD4', sm2: '#B8862F', dkt_hl: '#C05A9E', fixed: '#3F9E6B' },
} as const;

const LABEL: Record<string, string> = {
  dkt: 'DKT theo bậc (cũ)',
  sm2: 'SM-2',
  dkt_hl: 'DKT nhắm 90% (đang dùng)',
  fixed: 'Cố định 3 ngày',
};
const ORDER: string[] = ['dkt_hl', 'sm2', 'dkt', 'fixed'];

const W = 820;
const H = 260;
// Lề phải chứa nhãn chữ đầu mút — nhãn dài nhất là "DKT nhắm 90% (đang dùng)",
// hẹp hơn là bị cắt cụt và mất luôn tác dụng mã hóa phụ cho người mù màu.
const PAD = { top: 14, right: 176, bottom: 32, left: 46 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

function SchedulerComparison() {
  const theme = useTheme();
  const query = useSchedulerComparison();
  const [pool, setPool] = useState<number | null>(null);
  const [budget, setBudget] = useState<number | null>(null);
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const [hover, setHover] = useState<number | null>(null);

  const data = query.data;
  const activePool = pool ?? data?.setup.main_pool ?? 0;
  const activeBudget = budget ?? data?.setup.main_budget ?? 0;

  const arms = useMemo(
    () => (data?.arms ?? [])
      .filter((a) => a.pool === activePool && a.budget === activeBudget)
      .sort((a, b) => ORDER.indexOf(a.scheduler) - ORDER.indexOf(b.scheduler)),
    [data, activePool, activeBudget],
  );

  if (query.isLoading) {
    return <Box sx={{ textAlign: 'center', mt: 4 }}><CircularProgress /></Box>;
  }
  if (query.isError || !data) {
    return (
      <Alert severity="info">
        Chưa có kết quả thí nghiệm. Chạy <code>cd ml &amp;&amp; python -m src.schedule_sim</code>{' '}
        rồi tải lại trang.
      </Alert>
    );
  }

  const colors = SERIES[theme.palette.mode];
  const perLearner = (v: number) => v / data.setup.learners;
  const maxY = Math.max(1, ...arms.flatMap((a) => a.daily_recall.map((v) => perLearner(v))));
  const days = arms[0]?.daily_recall.length ?? 0;
  const x = (i: number) => PAD.left + (days <= 1 ? 0 : (i / (days - 1)) * PLOT_W);
  const y = (v: number) => PAD.top + (1 - v / maxY) * PLOT_H;

  // Nhãn đầu mút: xếp theo chiều dọc rồi giãn ra cho khỏi đè nhau.
  const LABEL_GAP = 15;
  const endLabels = arms
    .map((a) => ({
      scheduler: a.scheduler,
      y: y(perLearner(a.daily_recall[a.daily_recall.length - 1] ?? 0)) + 4,
    }))
    .sort((p1, p2) => p1.y - p2.y)
    .map((l, i, all) => {
      if (i > 0 && l.y - all[i - 1].y < LABEL_GAP) l.y = all[i - 1].y + LABEL_GAP;
      return l;
    });

  const suffix = `@b${activeBudget}p${activePool}`;
  const gapNow = data.gaps.find((g) => g.key === `dkt_vs_sm2${suffix}`);
  const gapFix = data.gaps.find((g) => g.key === `dkthl_vs_sm2${suffix}`);
  const best = arms.reduce<SchedulerArm | null>(
    (acc, a) => (acc === null || a.recall_delayed > acc.recall_delayed ? a : acc),
    null,
  );

  return (
    <Box>
      <Alert severity="info" sx={{ mb: 2 }}>
        Số liệu <strong>mô phỏng</strong>, không phải đo trên người học thật. Trí nhớ giả lập
        theo đường quên hàm mũ, độ khó từng từ lấy từ tỉ lệ sai thực tế trên SLAM - cả hai bộ
        lập lịch đều KHÔNG biết công thức đó. SM-2 còn được cấp mức tự chấm suy từ xác suất
        nhớ thật, tức được ưu ái hơn so với ngoài đời.
      </Alert>

      <Stack direction="row" spacing={1.5} sx={{ mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          select size="small" label="Kho từ" sx={{ width: 150 }} value={activePool}
          onChange={(e) => setPool(Number(e.target.value))}
        >
          {data.setup.pools.map((p) => (
            <MenuItem key={p} value={p}>{p} từ</MenuItem>
          ))}
        </TextField>
        <TextField
          select size="small" label="Ngân sách mỗi ngày" sx={{ width: 180 }} value={activeBudget}
          onChange={(e) => setBudget(Number(e.target.value))}
        >
          {data.setup.budgets.map((b) => (
            <MenuItem key={b} value={b}>{b} lượt/ngày</MenuItem>
          ))}
        </TextField>
        <ToggleButtonGroup size="small" exclusive value={view} onChange={(_, v) => v && setView(v)}>
          <ToggleButton value="chart">Biểu đồ</ToggleButton>
          <ToggleButton value="table">Bảng số</ToggleButton>
        </ToggleButtonGroup>
        <Typography variant="caption" color="text.secondary">
          {data.setup.learners} người học · {data.setup.horizon_days} ngày học · nghỉ{' '}
          {data.setup.delay_days} ngày rồi mới đo
        </Typography>
      </Stack>

      <Stack direction="row" spacing={2} sx={{ mb: 3, flexWrap: 'wrap' }}>
        {arms.map((a) => (
          <Paper key={a.scheduler} variant="outlined" sx={{ p: 2, minWidth: 190 }}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
              <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: colors[a.scheduler] }} />
              <Typography variant="caption" color="text.secondary">{LABEL[a.scheduler]}</Typography>
              {best?.scheduler === a.scheduler && (
                <Chip size="small" label="cao nhất" variant="outlined" />
              )}
            </Stack>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              {perLearner(a.recall_delayed).toFixed(1)}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              từ còn nhớ / người, sau {data.setup.delay_days} ngày nghỉ
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              {a.reviews.toLocaleString('vi-VN')} lượt ôn · thừa {a.wasted_pct}% · trễ {a.late_pct}%
            </Typography>
          </Paper>
        ))}
      </Stack>

      {[
        { g: gapNow, label: 'Luật cũ (bảng bậc) so với SM-2' },
        { g: gapFix, label: 'Luật đang dùng (nhắm mức nhớ 90%) so với SM-2' },
      ].map(({ g, label }) => g && (
        <Alert key={label} severity={g.ci_low > 0 ? 'success' : 'warning'} sx={{ mb: 1.5 }}>
          <strong>{label}:</strong> {g.mean_diff >= 0 ? '+' : ''}
          {g.mean_diff.toFixed(2)} từ mỗi người học (khoảng tin cậy 95%:{' '}
          {g.ci_low.toFixed(2)} … {g.ci_high.toFixed(2)}; thắng ở{' '}
          {Math.round(g.win_rate * 100)}% trong {g.n_learners} người).
          {g.ci_low > 0 || g.ci_high < 0
            ? ' Khoảng tin cậy không chứa 0 - chênh lệch này không phải do ngẫu nhiên.'
            : ' Khoảng tin cậy có chứa 0 - chưa kết luận được bên nào hơn.'}
        </Alert>
      ))}

      <Alert severity="warning" sx={{ mb: 3 }}>
        Nhánh <strong>DKT nhắm mức nhớ 90%</strong> và bộ mô phỏng cùng giả định quên theo hàm
        mũ. Mô phỏng vì thế chỉ chứng minh được luật này có ích <em>dưới</em> giả định đó, không
        chứng minh được giả định đúng với người thật.
      </Alert>

      {view === 'table' ? (
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Lịch ôn</TableCell>
              <TableCell align="right">Từ đã học</TableCell>
              <TableCell align="right">Lượt ôn</TableCell>
              <TableCell align="right">Nhớ khi kết thúc</TableCell>
              <TableCell align="right">Nhớ sau khi nghỉ</TableCell>
              <TableCell align="right">Nhớ / 100 lượt ôn</TableCell>
              <TableCell align="right">Ôn thừa</TableCell>
              <TableCell align="right">Ôn trễ</TableCell>
              <TableCell align="right">Khoảng cách TB</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {arms.map((a) => (
              <TableRow key={a.scheduler}>
                <TableCell>{LABEL[a.scheduler]}</TableCell>
                <TableCell align="right">{a.introduced.toLocaleString('vi-VN')}</TableCell>
                <TableCell align="right">{a.reviews.toLocaleString('vi-VN')}</TableCell>
                <TableCell align="right">{perLearner(a.recall_end).toFixed(1)}</TableCell>
                <TableCell align="right">{perLearner(a.recall_delayed).toFixed(1)}</TableCell>
                <TableCell align="right">{a.recall_per_100_reviews.toFixed(2)}</TableCell>
                <TableCell align="right">{a.wasted_pct}%</TableCell>
                <TableCell align="right">{a.late_pct}%</TableCell>
                <TableCell align="right">{a.mean_gap_days} ngày</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <Box sx={{ width: '100%', overflowX: 'auto' }}>
          <Box
            component="svg" viewBox={`0 0 ${W} ${H}`} role="img"
            aria-label={`Số từ còn nhớ trung bình mỗi người học qua ${days} ngày, so ${arms.length} lịch ôn: ${arms.map((a) => LABEL[a.scheduler]).join(", ")}`}
            sx={{ width: '100%', minWidth: 560, display: 'block' }}
            onMouseLeave={() => setHover(null)}
          >
            {[0, 0.5, 1].map((f) => {
              const yy = PAD.top + (1 - f) * PLOT_H;
              return (
                <g key={f}>
                  <line
                    x1={PAD.left} y1={yy} x2={PAD.left + PLOT_W} y2={yy}
                    stroke={alpha(theme.palette.text.primary, 0.12)}
                  />
                  <text
                    x={PAD.left - 8} y={yy + 4} textAnchor="end" fontSize={11}
                    fill={theme.palette.text.secondary}
                  >
                    {(maxY * f).toFixed(0)}
                  </text>
                </g>
              );
            })}

            {arms.map((a) => (
              <polyline
                key={a.scheduler} fill="none" strokeWidth={2}
                stroke={colors[a.scheduler]} strokeLinejoin="round" strokeLinecap="round"
                /* Nhánh đối chứng vẽ nét đứt: nó là mốc tham chiếu, không phải
                   một lựa chọn ngang hàng với hai lịch kia. */
                strokeDasharray={a.scheduler === 'fixed' ? '6 4' : undefined}
                points={a.daily_recall.map((v, i) => `${x(i)},${y(perLearner(v))}`).join(' ')}
              />
            ))}

            {/* Nhãn chữ ngay đầu mút — danh tính đường không chỉ dựa vào màu.
                Hai đường hội tụ thì nhãn đè lên nhau và không đọc được nữa, nên
                đẩy chúng cách nhau tối thiểu LABEL_GAP. */}
            {endLabels.map((l) => (
              <text
                key={`lb-${l.scheduler}`} x={PAD.left + PLOT_W + 8} y={l.y}
                fontSize={12} fill={colors[l.scheduler]} fontWeight={600}
              >
                {LABEL[l.scheduler]}
              </text>
            ))}

            {hover !== null && (
              <line
                x1={x(hover)} y1={PAD.top} x2={x(hover)} y2={PAD.top + PLOT_H}
                stroke={alpha(theme.palette.text.primary, 0.3)}
              />
            )}
            {Array.from({ length: days }, (_, i) => (
              <rect
                key={`hit-${i}`} x={x(i) - PLOT_W / Math.max(days, 1) / 2} y={PAD.top}
                width={PLOT_W / Math.max(days, 1)} height={PLOT_H} fill="transparent"
                onMouseEnter={() => setHover(i)}
              />
            ))}

            <text x={PAD.left} y={H - 8} fontSize={11} fill={theme.palette.text.secondary}>
              ngày 1
            </text>
            <text
              x={PAD.left + PLOT_W} y={H - 8} textAnchor="end" fontSize={11}
              fill={theme.palette.text.secondary}
            >
              ngày {days}
            </text>
          </Box>

          <Typography variant="body2" sx={{ mt: 1 }}>
            {hover === null
              ? 'Trục dọc: số từ còn nhớ kỳ vọng của một người học tại thời điểm đó.'
              : `Ngày ${hover + 1} - ${arms
                  .map((a) => `${LABEL[a.scheduler]} ${perLearner(a.daily_recall[hover]).toFixed(1)}`)
                  .join(' · ')}`}
          </Typography>
        </Box>
      )}

      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
        Chạy lúc {data.generated_at} · mô hình {data.setup.model} · {data.setup.n_words} từ có đủ
        lượt để ước lượng độ khó
      </Typography>
    </Box>
  );
}

export default SchedulerComparison;
