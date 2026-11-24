import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CircularProgress from '@mui/material/CircularProgress';
import MenuItem from '@mui/material/MenuItem';
import Pagination from '@mui/material/Pagination';
import Snackbar from '@mui/material/Snackbar';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  POST_TYPE_LABELS,
  useCreatePost,
  useFeed,
  useLeaderboard,
  type LeaderboardScope,
  type PostType,
} from '../api/community';
import EmptyState from '../components/EmptyState';
import FriendsTab from '../components/FriendsTab';
import PageHeader from '../components/PageHeader';
import SectionCard from '../components/SectionCard';
import PostCard from '../components/PostCard';
import { useFriendRequests } from '../api/extras';
import { UsersIcon } from '../components/icons';

const PAGE_SIZE = 10;
const POST_TYPES = Object.keys(POST_TYPE_LABELS) as PostType[];
// Bug #10: loại "Tiến độ" chỉ sinh ra từ nút khoe XP/streak (đã bỏ) — không cho
// chọn khi tự đăng bài nữa. Bộ lọc vẫn giữ để còn tìm được bài cũ.
const COMPOSER_POST_TYPES = POST_TYPES.filter((t) => t !== 'progress');

/** UC-49 — ô soạn bài: loại + nội dung + URL ảnh (tùy chọn). */
function PostComposer({ onResult }: { onResult: (msg: string) => void }) {
  const [postType, setPostType] = useState<PostType>('tip');
  const [content, setContent] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const createPost = useCreatePost();

  const submit = () => {
    createPost.mutate(
      { post_type: postType, content: content.trim(), image_url: imageUrl.trim() || null },
      {
        onSuccess: () => { setContent(''); setImageUrl(''); onResult('Đã đăng bài.'); },
        onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không đăng được bài.'),
      },
    );
  };

  return (
    <Card sx={{ p: 2, mb: 3 }}>
      <TextField
        fullWidth multiline minRows={3} placeholder="Chia sẻ mẹo học, từ hay, hoặc đặt câu hỏi..."
        value={content} onChange={(e) => setContent(e.target.value)}
      />
      <Box sx={{ display: 'flex', gap: 1.5, mt: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          select size="small" label="Loại bài" value={postType} sx={{ minWidth: 150, flex: { xs: '1 1 0', sm: '0 0 auto' } }}
          onChange={(e) => setPostType(e.target.value as PostType)}
        >
          {COMPOSER_POST_TYPES.map((t) => (
            <MenuItem key={t} value={t}>{POST_TYPE_LABELS[t]}</MenuItem>
          ))}
        </TextField>
        <TextField
          size="small" label="URL ảnh (tùy chọn)" sx={{ flexGrow: 1, minWidth: { xs: '100%', sm: 220 }, order: { xs: -1, sm: 0 } }}
          value={imageUrl} onChange={(e) => setImageUrl(e.target.value)}
        />
        <Button
          variant="contained" disabled={!content.trim() || createPost.isPending} onClick={submit}
        >
          Đăng
        </Button>
      </Box>
    </Card>
  );
}

/** UC-54 — bảng xếp hạng theo XP, đánh dấu dòng của người đang xem. */
function LeaderboardTab({ onOpenUser }: { onOpenUser: (userId: number) => void }) {
  const [scope, setScope] = useState<LeaderboardScope>('all');
  const { data, isLoading, isError } = useLeaderboard(scope);

  const row = (r: NonNullable<typeof data>['items'][number]) => (
    <Card
      key={r.user_id}
      sx={{
        display: 'flex', alignItems: 'center', gap: 2, p: 1.5, mb: 1,
        bgcolor: r.is_me ? 'action.selected' : undefined,
      }}
    >
      <Typography variant="h6" sx={{ width: 40, textAlign: 'center', fontWeight: 800 }}>
        {r.rank}
      </Typography>
      <Avatar src={r.avatar_url ?? undefined} sx={{ width: 36, height: 36 }}>
        {r.display_name.charAt(0).toUpperCase()}
      </Avatar>
      <Box sx={{ flexGrow: 1, minWidth: 0 }}>
        <Typography
          variant="subtitle2" sx={{ fontWeight: 700, cursor: 'pointer' }}
          onClick={() => onOpenUser(r.user_id)}
        >
          {r.display_name}{r.is_me ? ' (bạn)' : ''}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Cấp {r.level} · {r.level_title}
        </Typography>
      </Box>
      <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{r.xp} XP</Typography>
    </Card>
  );

  return (
    <Box>
      <ToggleButtonGroup
        size="small" exclusive value={scope} sx={{ mb: 2 }}
        onChange={(_, v) => { if (v) setScope(v); }}
      >
        <ToggleButton value="all">Toàn thời gian</ToggleButton>
        <ToggleButton value="week">7 ngày qua</ToggleButton>
      </ToggleButtonGroup>

      {isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {isError && <Alert severity="error">Không tải được bảng xếp hạng.</Alert>}

      {data?.items.map(row)}
      {data?.my_row && (
        <>
          <Typography variant="caption" color="text.secondary">Vị trí của bạn</Typography>
          {row(data.my_row)}
        </>
      )}
    </Box>
  );
}

/** Xếp hạng tuần gọn cạnh bảng tin; bảng đầy đủ nằm ở tab Bảng xếp hạng. */
function WeekLeaderboardSide({ onOpenUser, onSeeAll }: {
  onOpenUser: (userId: number) => void; onSeeAll: () => void;
}) {
  const { data } = useLeaderboard('week');
  if (!data) return null;
  const top = data.items.slice(0, 5);
  const rows = data.my_row && !top.some((r) => r.is_me) ? [...top, data.my_row] : top;

  return (
    <SectionCard title="Xếp hạng tuần" action={<Button size="small" onClick={onSeeAll}>Tất cả</Button>}>
      {rows.map((r) => (
        <Box
          key={r.user_id} component="button" type="button" onClick={() => onOpenUser(r.user_id)}
          sx={{
            display: 'flex', alignItems: 'center', gap: 1, width: '100%', p: 1, mb: 0.5,
            border: 0, borderRadius: '12px', cursor: 'pointer', textAlign: 'left', font: 'inherit',
            bgcolor: r.is_me ? 'action.selected' : 'transparent',
            '&:hover': { bgcolor: 'action.hover' },
          }}
        >
          <Typography sx={{ width: 22, fontWeight: 900, flexShrink: 0 }}>{r.rank}</Typography>
          <Typography noWrap sx={{ flexGrow: 1, minWidth: 0, fontWeight: 700, fontSize: 14 }}>
            {r.display_name}{r.is_me ? ' (bạn)' : ''}
          </Typography>
          <Typography sx={{ fontWeight: 900, fontSize: 13, whiteSpace: 'nowrap' }}>{r.xp} XP</Typography>
        </Box>
      ))}
    </SectionCard>
  );
}

function Community() {
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const [postType, setPostType] = useState<PostType | ''>('');
  const [page, setPage] = useState(1);
  const [snack, setSnack] = useState<string | null>(null);

  const query = useFeed({ post_type: postType || undefined, page, page_size: PAGE_SIZE });
  const data = query.data;
  const pageCount = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const openUser = (userId: number) => navigate(`/users/${userId}`);
  // Số lời mời chưa trả lời hiện ngay trên nhãn tab để không bị bỏ sót
  const requestCount = useFriendRequests().data?.length ?? 0;

  return (
    <Box sx={{ maxWidth: 1120, mx: 'auto' }}>
      <PageHeader
        title="Cộng đồng"
        subtitle="Đăng bài, hỏi đáp và chia sẻ mẹo học."
      />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Bảng tin" />
        <Tab label="Bảng xếp hạng" />
        <Tab label={requestCount > 0 ? `Bạn bè (${requestCount})` : 'Bạn bè'} />
      </Tabs>

      {tab === 2 ? (
        <FriendsTab onOpenUser={openUser} onResult={setSnack} />
      ) : tab === 1 ? (
        <LeaderboardTab onOpenUser={openUser} />
      ) : (
      // Bảng tin giữa, xếp hạng tuần bên phải; điện thoại đã có tab riêng (2026-11-04).
      <Box sx={{
        display: 'grid', gap: 2.5, alignItems: 'start',
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 1fr) 300px' },
      }}>
      <Box sx={{ minWidth: 0 }}>
      <PostComposer onResult={setSnack} />

      <TextField
        select size="small" label="Lọc theo loại" value={postType} sx={{ minWidth: 180, width: { xs: '100%', sm: 'auto' }, mb: 2 }}
        onChange={(e) => { setPostType(e.target.value as PostType | ''); setPage(1); }}
      >
        <MenuItem value="">Tất cả</MenuItem>
        {POST_TYPES.map((t) => (
          <MenuItem key={t} value={t}>{POST_TYPE_LABELS[t]}</MenuItem>
        ))}
      </TextField>

      {query.isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {query.isError && <Alert severity="error">Không tải được bảng tin.</Alert>}

      {data && data.items.length === 0 && (
        <EmptyState
          icon={<UsersIcon size={24} />}
          title="Bảng tin còn trống"
          description="Chưa có bài nào. Hãy là người đầu tiên chia sẻ."
        />
      )}

      {data?.items.map((p) => (
        <PostCard key={p.id} post={p} onResult={setSnack} onOpenAuthor={openUser} />
      ))}

      {pageCount > 1 && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
          <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} color="primary" />
        </Box>
      )}
      </Box>
      <Box sx={{ display: { xs: 'none', md: 'block' }, position: 'sticky', top: 16 }}>
        <WeekLeaderboardSide onOpenUser={openUser} onSeeAll={() => setTab(1)} />
      </Box>
      </Box>
      )}

      <Snackbar
        open={snack !== null} autoHideDuration={3500}
        onClose={() => setSnack(null)} message={snack ?? ''}
      />
    </Box>
  );
}

export default Community;
