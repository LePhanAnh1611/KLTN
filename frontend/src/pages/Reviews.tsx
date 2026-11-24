import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TablePagination from '@mui/material/TablePagination';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getCalendar, pauseLowerLevelReviews, useWeakItems } from '../api/reviews';
import SpeakButton from '../components/SpeakButton';

import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import { CalendarIcon } from '../components/icons';

import type { ReviewItem } from '../types/review';

const WEEKDAYS = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7'];
const DAYS_AHEAD = 7;

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/** Số ngày từ hôm nay tới ngày đến hạn (âm = đã quá hạn). */
function daysFromToday(iso: string): number {
  const today = startOfDay(new Date());
  const target = startOfDay(new Date(iso));
  return Math.round((target.getTime() - today.getTime()) / 86_400_000);
}


/** Dải 7 ngày: mỗi cột là một ngày, chiều cao cột theo số từ đến hạn.
 * Bấm để lọc bảng bên dưới. */
function WeekStrip({ counts, selected, onSelect }: {
  counts: number[]; selected: number | null; onSelect: (offset: number | null) => void;
}) {
  const theme = useTheme();
  const max = Math.max(...counts, 1);
  const today = startOfDay(new Date());

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        7 ngày tới - bấm một ngày để lọc
      </Typography>
      <Box sx={{ display: 'flex', gap: { xs: 0.75, sm: 1.5 }, alignItems: 'flex-end' }}>
        {counts.map((count, offset) => {
          const date = new Date(today);
          date.setDate(today.getDate() + offset);
          const isSelected = selected === offset;
          const isToday = offset === 0;

          return (
            <Box
              key={offset}
              component="button"
              type="button"
              onClick={() => onSelect(isSelected ? null : offset)}
              aria-label={`${count} từ ngày ${date.toLocaleDateString('vi-VN')}`}
              sx={{
                flex: 1, minWidth: 0, border: 0, p: 0.75, borderRadius: '10px', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.5,
                bgcolor: isSelected ? alpha(theme.palette.primary.main, 0.12) : 'transparent',
                '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.08) },
              }}
            >
              <Typography variant="caption" sx={{ fontWeight: 700 }}>
                {count > 0 ? count : ''}
              </Typography>
              <Box
                sx={{
                  width: '100%', borderRadius: 1,
                  height: count ? 8 + (count / max) * 44 : 4,
                  bgcolor: count === 0
                    ? 'action.disabledBackground'
                    : 'primary.main',
                  opacity: count === 0 ? 0.5 : 1,
                }}
              />
              <Typography variant="caption" color={isToday ? 'primary.main' : 'text.secondary'}
                          sx={{ fontWeight: isToday ? 800 : 500 }}>
                {WEEKDAYS[date.getDay()]}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {date.getDate()}/{date.getMonth() + 1}
              </Typography>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}

function ScheduleTable({ items }: { items: (ReviewItem & { offset: number })[] }) {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const currentPage = Math.min(page, Math.max(0, Math.ceil(items.length / rowsPerPage) - 1));
  if (items.length === 0) {
    return <Alert severity="info">Không có từ nào cần ôn trong khoảng đã chọn.</Alert>;
  }

  return (
    <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
      <Table size="small" sx={{ minWidth: 620 }}>
        <TableHead>
          <TableRow>
            <TableCell sx={{ fontWeight: 700 }}>Từ</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Nghĩa</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Bộ từ vựng</TableCell>
            <TableCell sx={{ fontWeight: 700 }}>Ôn lúc</TableCell>
            <TableCell sx={{ fontWeight: 700 }} align="right">Gặp lại sau</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {items.slice(currentPage * rowsPerPage, (currentPage + 1) * rowsPerPage).map((it) => {

            return (
              <TableRow key={it.item_id} hover>
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>{it.word}</Typography>
                    <SpeakButton text={it.word} size={16} />
                  </Box>
                </TableCell>
                <TableCell sx={{ color: 'text.secondary' }}>{it.meaning}</TableCell>
                <TableCell>
                  <Chip size="small" variant="outlined" label={it.word_set_name} />
                </TableCell>
                <TableCell>
                  {it.at_risk ? (
                    <Chip size="small" color="error" label="Cần ôn sớm" />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      {new Date(`${it.scheduled_for}T00:00:00`).toLocaleDateString('vi-VN')}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  <Tooltip title="Số ngày nữa từ này quay lại - bạn càng nhớ chắc thì càng lâu">
                    <Typography variant="body2" color="text.secondary">
                      {it.interval_days} ngày
                    </Typography>
                  </Tooltip>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      <TablePagination component="div" count={items.length} page={currentPage}
        rowsPerPage={rowsPerPage} rowsPerPageOptions={[10, 20, 50]}
        onPageChange={(_, next) => setPage(next)}
        onRowsPerPageChange={(event) => { setRowsPerPage(Number(event.target.value)); setPage(0); }}
        labelRowsPerPage="Số từ mỗi trang" />
    </TableContainer>
  );
}

/** UC-36 — lịch ôn theo tuần. */
function Reviews() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const cleanup = useMutation({
    mutationFn: pauseLowerLevelReviews,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['review-calendar'] });
      qc.invalidateQueries({ queryKey: ['reviews'] });
      qc.invalidateQueries({ queryKey: ['home'] });
    },
  });
  const weak = useWeakItems();
  const { data, isLoading, isError } = useQuery({
    queryKey: ['review-calendar'], queryFn: getCalendar,
  });
  const [selectedDay, setSelectedDay] = useState<number | null>(0);

  // Gộp 3 nhóm của API thành một danh sách kèm khoảng cách ngày, để vẽ dải tuần
  const all = useMemo(() => {
    if (!data) return [];
    return [...data.today, ...data.tomorrow, ...data.this_week]
      .map((it) => ({ ...it, offset: daysFromToday(`${it.scheduled_for}T00:00:00`) }))
      .sort((a, b) => a.offset - b.offset
        || a.next_review_at.localeCompare(b.next_review_at));
  }, [data]);

  const counts = useMemo(() => {
    const buckets = Array(DAYS_AHEAD).fill(0) as number[];
    for (const it of all) {
      if (it.offset >= 0 && it.offset < DAYS_AHEAD) buckets[it.offset] += 1;
    }
    return buckets;
  }, [all]);

  const visible = useMemo(() => {
    if (selectedDay === null) return all;
    return all.filter((it) => it.offset === selectedDay);
  }, [all, selectedDay]);

  const weakCount = weak.data?.length ?? 0;
  const dueToday = data?.today.length ?? 0;


  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (isError || !data) return <Alert severity="error">Không tải được lịch ôn.</Alert>;

  return (
    <Box>
      <PageHeader
        title="Lịch ôn tập"
        subtitle="Từ nhớ chắc gặp lại lâu, từ hay quên gặp lại sớm."
        actions={
          <>
            {/* UC-86: từ yếu chưa chắc đã "đến hạn", nên đây là lối vào riêng */}
            <Button variant="outlined" size="large" disabled={weakCount === 0}
                    onClick={() => navigate('/reviews/study?source=weak')}>
              Ôn điểm yếu{weakCount > 0 ? ` (${weakCount})` : ''}
            </Button>
            <Button variant="contained" size="large" disabled={dueToday === 0}
                    onClick={() => navigate('/reviews/study')}>
              Ôn ngay{dueToday > 0 ? ` (${dueToday})` : ''}
            </Button>
          </>
        }
      />

      {/* Trái: hôm nay và 7 ngày tới. Phải: từ của ngày đang chọn (2026-11-04). */}
      <Box sx={{
        display: 'grid', gap: 2.5, alignItems: 'start',
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '380px minmax(0, 1fr)' },
      }}>
      <Box sx={{ display: 'grid', gap: 2.5, minWidth: 0 }}>
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="h6">{/* Bug #12: "~0 phút" trông như lỗi — khi không có từ đến hạn thì nói thẳng,
            khi có thì ghi "khoảng N phút" (tối thiểu 1). */}
          {dueToday === 0
            ? (data.reviewed_today > 0 ? 'Hôm nay: đã ôn xong!' : 'Hôm nay: không có từ cần ôn')
            : `Hôm nay còn ${dueToday} từ · khoảng ${Math.max(1, data.estimated_minutes)} phút`}</Typography>
        {/* Mẫu số là khối lượng THẬT của hôm nay = đã ôn + còn lại. Trước đây ghi
            daily_limit (giới hạn tối đa/ngày, mặc định 30) nên ra "0 / 30" trong khi
            hôm nay chỉ có 6 từ - người dùng thử đọc thành lỗi (2026-10-27). */}
        {data.reviewed_today + dueToday > 0 && (
          <Typography variant="body2" color="text.secondary">
            {`Đã ôn ${data.reviewed_today} / ${data.reviewed_today + dueToday} từ hôm nay.`}
          </Typography>
        )}
        {data.backlog_count > 0 && <Typography variant="body2" color="text.secondary">
          {`Còn ${data.backlog_count} từ tồn đọng, hệ thống đang dàn đều sang các ngày sau.`}
        </Typography>}
        {data.lower_level_count > 0 && <Box sx={{ mt: 1 }}>
          <Button variant="outlined" disabled={cleanup.isPending} onClick={() => cleanup.mutate()}>
            {'Tôi đã biết các từ dưới trình độ của mình'}
          </Button>
          <Typography variant="caption" sx={{ display: 'block' }}>
            {`Tạm ngưng ôn ${data.lower_level_count} từ dưới mức ${data.entry_level}; vẫn giữ bộ từ và lịch sử học.`}
          </Typography>
        </Box>}
        {cleanup.isError && <Alert severity="error">{'Không dọn được lịch ôn. Hãy thử lại.'}</Alert>}
        {cleanup.isSuccess && <Alert severity="success">{`Đã tạm ngưng ôn ${cleanup.data.paused_count} từ.`}</Alert>}
      </Paper>
      {all.length > 0 && <WeekStrip counts={counts} selected={selectedDay} onSelect={setSelectedDay} />}
      </Box>

      <Box sx={{ minWidth: 0 }}>
      {all.length === 0 ? (
        <EmptyState
          icon={<CalendarIcon size={24} />}
          title="Chưa có lịch ôn nào"
          description="Học xong một bộ từ, lịch ôn sẽ tự xếp ở đây."
          action={<Button variant="contained" onClick={() => navigate('/word-sets')}>Chọn bộ từ vựng để học</Button>}
        />
      ) : (
        <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
            <Typography variant="h6">
              {selectedDay === null ? 'Tất cả' : selectedDay === 0 ? 'Hôm nay'
                : selectedDay === 1 ? 'Ngày mai' : `Sau ${selectedDay} ngày`}
            </Typography>
            <Chip size="small" label={`${visible.length} từ`} />
            {selectedDay !== null && (
              <Button size="small" onClick={() => setSelectedDay(null)}>Bỏ lọc</Button>
            )}
          </Box>

          {visible.length === 0 && (
            <Typography variant="body2" color="text.secondary"
                        sx={{ p: 2.5, borderRadius: '16px', bgcolor: 'background.paper', textAlign: 'center' }}>
              Ngày này không có từ nào cần ôn.
            </Typography>
          )}

          {[...new Set(visible.map((it) => it.word_set_id))].map((setId, groupIndex) => {
            const items = visible.filter((it) => it.word_set_id === setId);
            // Mở sẵn nhóm đầu để cột phải không trống khi vừa vào trang
            return <Box component="details" key={setId} open={groupIndex === 0} sx={{ mb: 1.5 }}>
              <Typography component="summary" sx={{ cursor: 'pointer', py: 1, fontWeight: 600 }}>
                {items[0].word_set_name} · {items.length} {'từ'}
              </Typography>
              <ScheduleTable items={items} />
            </Box>;
          })}
        </>
      )}
      </Box>
      </Box>
    </Box>
  );
}

export default Reviews;
