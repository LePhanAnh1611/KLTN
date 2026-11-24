import { useState } from 'react';
import { useNavigate, useSearchParams, Link as RouterLink } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Stack from '@mui/material/Stack';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import InputAdornment from '@mui/material/InputAdornment';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import Rating from '@mui/material/Rating';
import Snackbar from '@mui/material/Snackbar';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import {
  useCategories,
  useDiscover,
  usePopularTags,
  useDownloadWordSet,
  useFeatured,
  usePublicDetail,
  useRateWordSet,
  useRatings,
  useReportWordSet,
  type DiscoverSort,
  type PublicWordSetCard,
} from '../api/discover';
import { ApiError } from '../api/client';
import ReportDialog from '../components/ReportDialog';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import WordSetCard, { wordSetGridSx } from '../components/WordSetCard';
import { DownloadIcon, SearchIcon } from '../components/icons';

const PAGE_SIZE = 12;

function DownloadButton({ card, onResult }: { card: PublicWordSetCard; onResult: (msg: string) => void }) {
  const download = useDownloadWordSet();
  if (card.is_downloaded) {
    return <Chip size="small" color="success" label="Đã tải" />;
  }
  return (
    <Button
      size="small"
      startIcon={<DownloadIcon size={16} />}
      disabled={download.isPending}
      onClick={() =>
        download.mutate(card.id, {
          onSuccess: () => onResult(`Đã tải "${card.name}" về thư viện.`),
          onError: (e) => onResult(e instanceof ApiError ? e.message : 'Tải thất bại.'),
        })
      }
    >
      Tải về
    </Button>
  );
}

/** UC-23 — điểm trung bình, chấm sao của mình (chặn khi chưa tải) và nhận xét gần đây. */
function RatingSection({ id, onResult }: { id: number; onResult: (msg: string) => void }) {
  const { data } = useRatings(id);
  const rate = useRateWordSet(id);
  if (!data) return null;

  const stars = (
    <Rating
      value={data.my_stars ?? 0}
      readOnly={!data.can_rate || rate.isPending}
      onChange={(_, v) => {
        if (v == null) return;
        rate.mutate(
          { stars: v },
          {
            onSuccess: () => onResult('Đã lưu đánh giá của bạn.'),
            onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không gửi được đánh giá.'),
          },
        );
      }}
    />
  );

  return (
    <>
      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle2">Đánh giá</Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
        <Rating value={data.average ?? 0} precision={0.5} size="small" readOnly />
        <Typography variant="body2" color="text.secondary">
          {data.count > 0 ? `${data.average} / 5 · ${data.count} lượt` : 'Chưa có đánh giá'}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
        <Typography variant="body2">{data.my_stars ? 'Bạn đã chấm:' : 'Chấm điểm:'}</Typography>
        {data.can_rate ? stars : (
          <Tooltip title="Tải bộ từ vựng về thư viện trước khi đánh giá">
            <span>{stars}</span>
          </Tooltip>
        )}
      </Box>

      {data.items.length > 0 && (
        <List dense>
          {data.items.filter((it) => it.comment).slice(0, 5).map((it, i) => (
            <ListItem key={i} disableGutters>
              <ListItemText primary={`${it.user_name} · ${it.stars}★`} secondary={it.comment} />
            </ListItem>
          ))}
        </List>
      )}
    </>
  );
}

/** UC-24 — gửi báo cáo bộ từ vi phạm (E1: báo cáo trùng được gộp ở backend). */
function WordSetReportDialog({ id, name, open, onClose, onResult }: {
  id: number; name: string; open: boolean; onClose: () => void; onResult: (msg: string) => void;
}) {
  const report = useReportWordSet(id);
  return (
    <ReportDialog
      title={`Báo cáo "${name}"`}
      open={open}
      pending={report.isPending}
      onClose={onClose}
      onSubmit={(body) =>
        report.mutate(body, {
          onSuccess: (res) => {
            onResult(res.merged
              ? 'Bạn đã báo cáo bộ từ vựng này rồi - báo cáo được gộp.'
              : 'Đã gửi báo cáo tới quản trị viên.');
            onClose();
          },
          onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không gửi được báo cáo.'),
        })
      }
    />
  );
}

function DetailDialog({ id, onClose, onResult }: {
  id: number | null; onClose: () => void; onResult: (msg: string) => void;
}) {
  const query = usePublicDetail(id);
  const download = useDownloadWordSet();
  const [reportOpen, setReportOpen] = useState(false);
  const d = query.data;

  return (
    <Dialog open={id != null} onClose={onClose} maxWidth="sm" fullWidth>
      {query.isLoading && <DialogContent sx={{ textAlign: 'center' }}><CircularProgress /></DialogContent>}
      {query.isError && <DialogContent><Alert severity="error">Bộ từ vựng không còn khả dụng.</Alert></DialogContent>}
      {d && (
        <>
          <DialogTitle>{d.name}</DialogTitle>
          <DialogContent dividers>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {d.description || 'Không có mô tả'}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', my: 1 }}>
              {d.difficulty && <Chip size="small" label={d.difficulty} />}
              {d.category && <Chip size="small" label={d.category} />}
              <Chip size="small" label={`${d.item_count} từ`} />
              <Chip size="small" label={`${d.download_count} lượt tải`} />
              <Chip size="small" variant="outlined" label={`Bởi ${d.owner_name}`} />
              {d.tags.map((t) => (
                <Chip key={t} size="small" variant="outlined" label={`#${t}`} />
              ))}
            </Box>
            <Typography variant="subtitle2" sx={{ mt: 2 }}>Xem trước</Typography>
            <List dense>
              {d.preview_items.map((it, i) => (
                <ListItem key={i} disableGutters>
                  <ListItemText
                    primary={`${it.word}${it.phonetic ? ` ${it.phonetic}` : ''}`}
                    secondary={it.meaning}
                  />
                </ListItem>
              ))}
            </List>
            <RatingSection id={d.id} onResult={onResult} />
          </DialogContent>
          <DialogActions>
            <Button color="error" onClick={() => setReportOpen(true)} sx={{ mr: 'auto' }}>
              Báo cáo
            </Button>
            <Button onClick={onClose}>Đóng</Button>
            {d.is_downloaded ? (
              <Chip size="small" color="success" label="Đã tải" sx={{ mr: 1 }} />
            ) : (
              <Button
                variant="contained"
                startIcon={<DownloadIcon size={16} />}
                disabled={download.isPending}
                onClick={() =>
                  download.mutate(d.id, {
                    onSuccess: () => { onResult(`Đã tải "${d.name}" về thư viện.`); onClose(); },
                    onError: (e) => onResult(e instanceof ApiError ? e.message : 'Tải thất bại.'),
                  })
                }
              >
                Tải về
              </Button>
            )}
          </DialogActions>
          <WordSetReportDialog
            id={d.id} name={d.name} open={reportOpen}
            onClose={() => setReportOpen(false)} onResult={onResult}
          />
        </>
      )}
    </Dialog>
  );
}

function Discover() {
  const navigate = useNavigate();
  // Ô tìm kiếm ở topbar điều hướng sang đây kèm ?q= — nhận làm giá trị khởi tạo,
  // nếu không thì bấm Enter trên topbar sẽ mở trang này mà không lọc gì cả.
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get('q') ?? '');
  const [category, setCategory] = useState('');
  const [difficulty, setDifficulty] = useState('');
  // UC-96 — nhãn nhận cả từ URL để link chia sẻ '/discover?tag=ielts' mở đúng bộ lọc
  const [tag, setTag] = useState(params.get('tag') ?? '');
  const [sort, setSort] = useState<DiscoverSort>('popular');
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [snack, setSnack] = useState<string | null>(null);

  const query = useDiscover({
    q: q || undefined, category: category || undefined,
    difficulty: difficulty || undefined, tag: tag || undefined,
    sort, page, page_size: PAGE_SIZE,
  });
  const featured = useFeatured();
  const categories = useCategories();
  const tags = usePopularTags();
  const data = query.data;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  const reset = () => setPage(1);

  return (
    <Box>
      <PageHeader
        title="Khám phá bộ từ vựng"
        subtitle="Bộ từ người khác chia sẻ, tải về để học."
      />

      {/* UC-22: khu vực nổi bật — E1 chưa có bộ nào thì ẩn hẳn */}
      {featured.data && featured.data.length > 0 && (
        <Box sx={{ mb: 4 }}>
          <Typography variant="h6" gutterBottom>Nổi bật</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
            Bộ từ vựng được ban quản trị chọn lọc.
          </Typography>
          <Box sx={{ display: 'flex', gap: 2, overflowX: 'auto', pb: 1 }}>
            {featured.data.map((c) => (
              <Box key={c.id} sx={{ flex: '0 0 auto', width: 280 }}>
                <WordSetCard
                  id={c.id}
                  name={c.name}
                  coverImageUrl={c.cover_image_url}
                  description={c.description}
                  itemCount={c.item_count}
                  category={c.category}
                  difficulty={c.difficulty}
                  ratingAvg={c.rating_avg}
                  ratingCount={c.rating_count}
                  onOpen={() => setDetailId(c.id)}
                  actions={
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', px: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        {c.download_count} lượt tải · {c.owner_name}
                      </Typography>
                      <DownloadButton card={c} onResult={setSnack} />
                    </Box>
                  }
                />
              </Box>
            ))}
          </Box>
          <Divider sx={{ mt: 2 }} />
        </Box>
      )}

      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center', mb: 3 }}>
        <TextField
          size="small"
          placeholder="Tìm theo tên..."
          value={q}
          onChange={(e) => { setQ(e.target.value); reset(); }}
          slotProps={{ input: { startAdornment: (
            <InputAdornment position="start"><SearchIcon size={18} /></InputAdornment>
          ) } }}
          sx={{ minWidth: { xs: 0, sm: 240 }, flex: { xs: '1 1 100%', sm: '0 1 auto' } }}
        />
        {/* UC-76: danh mục do Admin quản lý, không hardcode ở FE */}
        {(categories.data?.length ?? 0) > 0 && (
          <TextField
            size="small" select label="Danh mục" value={category}
            onChange={(e) => { setCategory(e.target.value); reset(); }}
            sx={{ minWidth: { xs: 0, sm: 170 }, flex: { xs: '1 1 calc(50% - 6px)', sm: '0 1 auto' } }}
          >
            <MenuItem value="">Tất cả</MenuItem>
            {categories.data?.map((c) => (
              <MenuItem key={c.id} value={c.name}>{c.name}</MenuItem>
            ))}
          </TextField>
        )}
        <TextField
          size="small" select label="Độ khó" value={difficulty}
          onChange={(e) => { setDifficulty(e.target.value); reset(); }}
          sx={{ minWidth: { xs: 0, sm: 150 }, flex: { xs: '1 1 calc(50% - 6px)', sm: '0 1 auto' } }}
        >
          <MenuItem value="">Tất cả</MenuItem>
          <MenuItem value="beginner">beginner</MenuItem>
          <MenuItem value="intermediate">intermediate</MenuItem>
          <MenuItem value="advanced">advanced</MenuItem>
        </TextField>
        <ToggleButtonGroup
          size="small" exclusive value={sort}
          onChange={(_, v) => { if (v) { setSort(v); reset(); } }}
          // Điện thoại: nhóm sắp xếp xuống hàng riêng, 3 nút chia đều — để chung hàng
          // với 2 ô chọn thì cả hai bị ép còn "D…".
          sx={{ width: { xs: '100%', sm: 'auto' }, '& .MuiToggleButton-root': { flex: { xs: 1, sm: 'none' } } }}
        >
          <ToggleButton value="popular">Phổ biến</ToggleButton>
          <ToggleButton value="new">Mới</ToggleButton>
          <ToggleButton value="rating">Đánh giá cao</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* UC-96 — dải nhãn: lọc chéo trình độ × mục tiêu thi × nguồn, thứ mà một
          ô "Danh mục" chọn-một không làm được. Chỉ hiện nhãn có bộ công khai. */}
      {(tags.data?.length ?? 0) > 0 && (
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1, mb: 2 }}>
          {tag !== '' && (
            <Chip
              label="Bỏ lọc nhãn" variant="outlined" color="primary"
              onDelete={() => { setTag(''); reset(); }}
            />
          )}
          {tags.data?.map((t) => (
            <Chip
              key={t.tag}
              label={`#${t.tag} (${t.count})`}
              color={tag === t.tag ? 'primary' : 'default'}
              variant={tag === t.tag ? 'filled' : 'outlined'}
              onClick={() => { setTag(tag === t.tag ? '' : t.tag); reset(); }}
            />
          ))}
        </Stack>
      )}

      {/* UC-95 — ô tìm kiếm hứa "tìm từ", nhưng trang này chỉ trả BỘ TỪ. Gõ một
          từ đơn vào đây mà chỉ nhận danh sách bộ là cụt đường, nên bắc cầu sang
          trang Tra từ thay vì đoán xem người dùng muốn đi đâu. */}
      {/^[a-zA-Z][a-zA-Z'-]*$/.test(q.trim()) && (
        <Alert
          severity="info" sx={{ mb: 2 }}
          action={
            <Button
              size="small" component={RouterLink}
              to={`/dictionary?q=${encodeURIComponent(q.trim())}`}
            >
              Tra từ
            </Button>
          }
        >
          Đang tìm bộ từ vựng có tên chứa “{q.trim()}”. Muốn tra <strong>nghĩa</strong> của từ này?
        </Alert>
      )}

      {query.isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {query.isError && <Alert severity="error">Không tải được danh sách.</Alert>}

      {data && data.items.length === 0 && (
        <EmptyState
          title="Không tìm thấy bộ từ nào"
          description="Thử bỏ bớt bộ lọc hoặc gõ ngắn hơn."
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <Box sx={wordSetGridSx}>
            {data.items.map((c) => (
              <WordSetCard
                key={c.id}
                id={c.id}
                name={c.name}
                coverImageUrl={c.cover_image_url}
                description={c.description}
                itemCount={c.item_count}
                category={c.category}
                difficulty={c.difficulty}
                ratingAvg={c.rating_avg}
                ratingCount={c.rating_count}
                onOpen={() => setDetailId(c.id)}
                actions={
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', px: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      {c.download_count} lượt tải · {c.owner_name}
                    </Typography>
                    <DownloadButton card={c} onResult={setSnack} />
                  </Box>
                }
              />
            ))}
          </Box>

          {pageCount > 1 && (
            <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
              <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
            </Box>
          )}
        </>
      )}

      <DetailDialog id={detailId} onClose={() => setDetailId(null)} onResult={setSnack} />

      <Snackbar
        open={snack !== null}
        autoHideDuration={3500}
        onClose={() => setSnack(null)}
        message={snack ?? ''}
        action={
          snack?.startsWith('Đã tải') ? (
            <Button color="inherit" size="small" onClick={() => navigate('/word-sets')}>Xem thư viện</Button>
          ) : undefined
        }
      />
    </Box>
  );
}

export default Discover;
