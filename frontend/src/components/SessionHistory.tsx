import { useState } from 'react';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Pagination from '@mui/material/Pagination';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';

import { useSessionHistory } from '../api/sessions';
import { modeLabel } from '../types/labels';
import EmptyState from './EmptyState';
import SectionCard from './SectionCard';
import StatCard from './StatCard';
import { CalendarIcon, ChartIcon, StarIcon } from './icons';
import { namedAccent } from '../theme/accents';

const PAGE_SIZE = 10;

/** Nhãn tiếng Việt cho từng chế độ học — khớp với `mode` backend lưu. */

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/`
    + `${d.getFullYear()} ${d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}`;
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '-';
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}p ${seconds % 60}s`;
}

/** UC-45 — nhật ký học tập: mỗi phiên đã kết thúc là một dòng. */
function SessionHistory() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useSessionHistory(page, PAGE_SIZE);

  if (isLoading) return <LinearProgress />;
  if (!data) return null;

  if (data.total === 0) {
    return (
      <EmptyState
        icon={<CalendarIcon size={24} />}
        title="Chưa có phiên học nào"
        description="Học xong một phiên, kết quả sẽ hiện ở đây."
      />
    );
  }

  const pageCount = Math.max(1, Math.ceil(data.total / data.page_size));

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
        <StatCard icon={<CalendarIcon />} value={data.total_sessions} label="Tổng số phiên"
                  accent={namedAccent.blue} />
        <StatCard icon={<ChartIcon />} value={data.total_items_answered} label="Lượt trả lời"
                  accent={namedAccent.teal} />
        <StatCard icon={<StarIcon />} value={data.total_xp} label="Tổng XP đã nhận"
                  accent={namedAccent.amber} />
      </Box>

      <SectionCard
        title="Nhật ký học tập"
        caption="Chỉ hiện các phiên đã kết thúc."
        sx={{ overflow: 'hidden', pb: 0 }}
      >
        {/* Giữ lề cho tiêu đề; riêng bảng trải sát hai mép thẻ bằng lề âm. */}
        <Box sx={{ overflowX: 'auto', mx: { xs: -2.25, sm: -2.75 } }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Thời điểm</TableCell>
                <TableCell>Nội dung</TableCell>
                <TableCell>Kiểu</TableCell>
                <TableCell align="right">Số từ</TableCell>
                <TableCell align="right">Đúng</TableCell>
                <TableCell align="right">Thời lượng</TableCell>
                <TableCell align="right">XP</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.items.map((row) => (
                <TableRow key={row.id} hover>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>
                    {formatWhen(row.started_at)}
                    {row.status === 'abandoned' && (
                      <Chip size="small" label="bỏ dở" sx={{ ml: 1 }} />
                    )}
                  </TableCell>
                  <TableCell>
                    {/* Phiên xuyên thư viện không gắn bộ nào */}
                    {row.word_set_name ?? <em>Nhiều bộ từ vựng</em>}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" variant="outlined"
                          label={modeLabel(row.mode) || '-'} />
                  </TableCell>
                  <TableCell align="right">{row.item_count}</TableCell>
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={{ fontWeight: 700, color: row.accuracy >= 0.8 ? 'success.main' : 'text.primary' }}
                    >
                      {row.item_count ? `${Math.round(row.accuracy * 100)}%` : '-'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">{formatDuration(row.duration_seconds)}</TableCell>
                  <TableCell align="right">+{row.xp_earned}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      </SectionCard>

      {pageCount > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination count={pageCount} page={page} color="primary"
                      onChange={(_, p) => setPage(p)} />
        </Box>
      )}
    </Box>
  );
}

export default SessionHistory;
