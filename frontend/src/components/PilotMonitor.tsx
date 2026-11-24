import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';

import StatCard from './StatCard';
import { usePilotReport, useSendPilotReport } from '../api/pilot';
import { ApiError } from '../api/client';

function ago(days: number | null): string {
  if (days === null) return 'chưa học';
  if (days === 0) return 'hôm nay';
  if (days === 1) return 'hôm qua';
  return `${days} ngày trước`;
}

const pct = (x: number) => `${Math.round(x * 100)}%`;

/**
 * Pilot — theo dõi đợt thử nghiệm: ai đang học, dữ liệu có sạch không, đã đủ
 * dữ liệu để kiểm chứng/hiệu chuẩn DKT chưa. Mọi con số do backend tính
 * (`pilot_service`); trang này chỉ hiển thị.
 */
function PilotMonitor({ onResult }: { onResult: (msg: string) => void }) {
  const { data, isLoading } = usePilotReport();
  const send = useSendPilotReport();

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (!data) return <Alert severity="error">Không tải được báo cáo pilot.</Alert>;

  const met = data.criteria.filter((c) => c.met).length;
  const maxBin = Math.max(1, ...data.bins.map((b) => b.count));

  return (
    <Box>
      {data.ready ? (
        <Alert severity="success" sx={{ mb: 2 }}>
          Đã đủ dữ liệu để kiểm chứng và hiệu chuẩn DKT.
        </Alert>
      ) : (
        <Alert severity="info" sx={{ mb: 2 }}>
          {data.pilot_day ? `Ngày ${data.pilot_day} của pilot · ` : ''}
          Đạt {met}/{data.criteria.length} điều kiện đủ dữ liệu.
        </Alert>
      )}
      {data.model_share !== null && data.model_share < 0.8 && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Chỉ {pct(data.model_share)} câu trả lời có dự đoán của DKT - dịch vụ mô hình có thể đang tắt.
        </Alert>
      )}

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', md: 'repeat(4, 1fr)' }, gap: 1.5, mb: 3 }}>
        <StatCard label="Học hôm nay" value={data.active_today} />
        <StatCard label="Câu hôm nay" value={data.answers_today} />
        <StatCard label={`Đã học / đã đăng ký`} value={`${data.participants}/${data.registered}`} />
        <StatCard label="Tổng câu trả lời" value={data.answers_total} />
      </Box>

      <Typography variant="h6" sx={{ mb: 1 }}>Điều kiện đủ dữ liệu</Typography>
      <Box sx={{ display: 'grid', gap: 1.5, mb: 3 }}>
        {data.criteria.map((c) => (
          <Paper key={c.key} variant="outlined" sx={{ p: 1.75 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, alignItems: 'baseline' }}>
              <Typography sx={{ fontWeight: 700 }}>{c.met ? '✓ ' : ''}{c.label}</Typography>
              <Typography sx={{ fontWeight: 800, whiteSpace: 'nowrap' }}>{c.current} / {c.target}</Typography>
            </Box>
            <LinearProgress variant="determinate" color={c.met ? 'success' : 'primary'}
              value={Math.min(100, (c.current / c.target) * 100)} sx={{ my: 1, height: 8, borderRadius: 999 }} />
            <Typography variant="body2" color="text.secondary">{c.why}</Typography>
          </Paper>
        ))}
      </Box>

      <Typography variant="h6" sx={{ mb: 0.5 }}>Dự đoán của DKT so với thực tế</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        Mỗi cột là một khoảng mastery DKT dự đoán. Số trong ngoặc là tỉ lệ trả lời đúng thực tế -
        mô hình hiệu chuẩn tốt thì tỉ lệ này nằm trong khoảng của cột.
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 0.75, alignItems: 'end', height: 140, mb: 0.5 }}>
        {data.bins.map((b) => (
          <Box key={b.low} title={`${b.count} câu`}
            sx={{ height: `${Math.max(4, (b.count / maxBin) * 100)}%`, bgcolor: b.count >= 100 ? 'success.main' : 'primary.main',
                  borderRadius: '4px 4px 0 0', opacity: b.count ? 1 : 0.25 }} />
        ))}
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 0.75, mb: 3 }}>
        {data.bins.map((b) => (
          <Box key={b.low} sx={{ textAlign: 'center' }}>
            <Typography variant="caption" sx={{ display: 'block', fontWeight: 700 }}>{Math.round(b.low * 100)}-{Math.round(b.high * 100)}</Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>{b.count}</Typography>
            <Typography variant="caption" sx={{ display: 'block' }}>{b.accuracy === null ? '-' : `(${pct(b.accuracy)})`}</Typography>
          </Box>
        ))}
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="h6">Từng người</Typography>
        <Button size="small" variant="outlined" disabled={send.isPending}
          onClick={() => send.mutate(undefined, {
            onSuccess: () => onResult('Đã xếp email báo cáo vào hàng đợi.'),
            onError: (e) => onResult(e instanceof ApiError ? e.message : 'Gửi báo cáo thất bại.'),
          })}>
          Gửi email báo cáo ngay
        </Button>
      </Box>
      <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Người học</TableCell>
              <TableCell align="right">Số ngày</TableCell>
              <TableCell align="right">Tổng câu</TableCell>
              <TableCell align="right">Hôm nay</TableCell>
              <TableCell>Lần cuối</TableCell>
              <TableCell>Ghi chú</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.people.map((p) => (
              <TableRow key={p.user_id} sx={p.needs_nudge ? { bgcolor: 'error.light' } : undefined}>
                <TableCell>
                  <Typography sx={{ fontWeight: 700, fontSize: '0.9rem' }}>{p.display_name}</Typography>
                  <Typography variant="caption" color="text.secondary">{p.email}</Typography>
                </TableCell>
                <TableCell align="right">{p.active_days}</TableCell>
                <TableCell align="right">{p.answers_total}</TableCell>
                <TableCell align="right">{p.answers_today}</TableCell>
                <TableCell>{ago(p.days_inactive)}</TableCell>
                <TableCell>
                  <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {p.needs_nudge && <Chip size="small" color="error" label="Cần nhắc" />}
                    {!p.placement_done && <Chip size="small" variant="outlined" label="Chưa xếp lớp" />}
                    {p.validation_done && <Chip size="small" color="success" label="Đã làm bài cuối" />}
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default PilotMonitor;
