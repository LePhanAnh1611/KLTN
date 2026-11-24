import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActionArea from '@mui/material/CardActionArea';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  thumbnailUrl,
  useAddShadowingVideo,
  useShadowingTopics,
  useShadowingVideos,
  type ShadowingVideoCard,
} from '../api/shadowing';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';

function formatDuration(sec: number | null): string {
  if (!sec) return '';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function VideoCard({ video }: { video: ShadowingVideoCard }) {
  const navigate = useNavigate();
  const ratio = video.segment_count ? video.passed_count / video.segment_count : 0;

  return (
    <Card variant="outlined" sx={{ borderWidth: 2, overflow: 'hidden' }}>
      <CardActionArea onClick={() => navigate(`/shadowing/${video.id}`)} sx={{ height: '100%' }}>
        <Box sx={{ position: 'relative', aspectRatio: '16 / 9', bgcolor: 'action.hover' }}>
          <Box
            component="img" src={thumbnailUrl(video.youtube_id)} alt="" loading="lazy"
            onError={(e: React.SyntheticEvent<HTMLImageElement>) => { e.currentTarget.style.visibility = 'hidden'; }}
            sx={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
          />
          {video.duration_sec && (
            <Chip size="small" label={formatDuration(video.duration_sec)}
                  sx={{ position: 'absolute', right: 8, bottom: 8, bgcolor: 'grey.900', color: 'common.white' }} />
          )}
        </Box>
        <Box sx={{ p: 2 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.3, mb: 1 }}>
            {video.title}
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1.5 }}>
            {video.cefr_level && <Chip size="small" color="primary" label={video.cefr_level} />}
            {video.source === 'user'
              ? <Chip size="small" variant="outlined" label="Video của tôi" />
              : video.topic && <Chip size="small" variant="outlined" label={video.topic} />}
            {video.words_per_minute && (
              <Chip size="small" variant="outlined" label={`${Math.round(video.words_per_minute)} từ/phút`} />
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <LinearProgress variant="determinate" value={ratio * 100}
                            sx={{ flexGrow: 1, height: 8, borderRadius: 4 }} />
            <Typography variant="caption" sx={{ fontWeight: 700, minWidth: 48, textAlign: 'right' }}>
              {video.passed_count}/{video.segment_count} câu
            </Typography>
          </Box>
        </Box>
      </CardActionArea>
    </Card>
  );
}

function AddVideoDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const add = useAddShadowingVideo();
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const close = () => {
    add.reset();
    setUrl('');
    setFile(null);
    onClose();
  };

  const submit = () => {
    add.mutate({ url, captions: file }, {
      onSuccess: (video) => {
        close();
        navigate(`/shadowing/${video.id}`);
      },
    });
  };

  const blocked = add.error instanceof ApiError && add.error.status === 503;

  return (
    <Dialog open={open} onClose={close} fullWidth maxWidth="sm">
      <DialogTitle>Luyện với video của bạn</DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Dán link video YouTube có phụ đề tiếng Anh. Hệ thống tự cắt phụ đề thành từng câu
          để bạn nghe và nhại lại. Video chỉ hiện với riêng bạn.
        </Typography>
        <TextField
          autoFocus fullWidth label="Link YouTube" placeholder="https://www.youtube.com/watch?v=..."
          value={url} onChange={(e) => setUrl(e.target.value)} sx={{ mb: 2 }}
        />
        <Button component="label" variant="outlined" size="small">
          {file ? `Phụ đề: ${file.name}` : 'Tải file phụ đề (.srt/.vtt) — không bắt buộc'}
          <input hidden type="file" accept=".srt,.vtt"
                 onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Button>
        {add.error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {add.error instanceof ApiError ? add.error.message : 'Không thêm được video.'}
            {blocked && !file && ' Bạn có thể tải file phụ đề lên rồi thử lại.'}
          </Alert>
        )}
        {add.isPending && <LinearProgress sx={{ mt: 2 }} />}
      </DialogContent>
      <DialogActions>
        <Button onClick={close}>Hủy</Button>
        <Button variant="contained" disabled={!url.trim() || add.isPending} onClick={submit}>
          {add.isPending ? 'Đang lấy phụ đề...' : 'Thêm video'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** UC-97 — kho video shadowing theo chủ đề và cấp độ. */
function Shadowing() {
  const [topic, setTopic] = useState<string | null>(null);
  const [level, setLevel] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const topics = useShadowingTopics();
  const videos = useShadowingVideos(topic, level);

  return (
    <Box>
      <PageHeader
        title="Shadowing video"
        subtitle="Nghe từng câu trong video, nhại lại và xem bạn nói đúng tới đâu."
        actions={<Button variant="contained" onClick={() => setAdding(true)}>Dùng video của tôi</Button>}
      />

      <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mb: 3 }}>
        <TextField
          select size="small" label="Chủ đề" value={topic ?? ''} sx={{ minWidth: 240 }}
          onChange={(e) => setTopic(e.target.value || null)}
        >
          <MenuItem value="">Tất cả chủ đề</MenuItem>
          {(topics.data?.topics ?? []).map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
        </TextField>
        <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
          <Chip label="Mọi cấp độ" color={level === null ? 'primary' : 'default'}
                onClick={() => setLevel(null)} />
          {(topics.data?.levels ?? []).map((lv) => (
            <Chip key={lv} label={lv} color={level === lv ? 'primary' : 'default'}
                  onClick={() => setLevel(level === lv ? null : lv)} />
          ))}
        </Box>
      </Box>

      {videos.isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}
      {videos.error && <Alert severity="error">Không tải được danh sách video.</Alert>}
      {videos.data && videos.data.length === 0 && (
        <EmptyState
          title={topic || level ? 'Chưa có video phù hợp bộ lọc' : 'Kho video đang trống'}
          description="Bạn có thể dán link một video YouTube có phụ đề tiếng Anh để luyện ngay."
          action={<Button variant="contained" onClick={() => setAdding(true)}>Dùng video của tôi</Button>}
        />
      )}
      {videos.data && videos.data.length > 0 && (
        <Box sx={{
          display: 'grid', gap: 2,
          gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(3, 1fr)' },
        }}>
          {videos.data.map((v) => <VideoCard key={v.id} video={v} />)}
        </Box>
      )}

      <AddVideoDialog open={adding} onClose={() => setAdding(false)} />
    </Box>
  );
}

export default Shadowing;
