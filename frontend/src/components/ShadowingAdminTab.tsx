import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  CAPTION_LABELS,
  LICENSE_LABELS,
  useAdminCreateShadowingVideo,
  useAdminDeleteShadowingVideo,
  useAdminShadowingStatus,
  useAdminShadowingVideo,
  useAdminShadowingVideos,
  useAdminUpdateShadowingVideo,
  useShadowingTopics,
} from '../api/shadowing';
import SectionCard from './SectionCard';
import { CloseIcon } from './icons';

type OnResult = (msg: string) => void;

function errorText(e: unknown, fallback: string): string {
  return e instanceof ApiError ? e.message : fallback;
}

function AddVideoForm({ onResult, onCreated }: { onResult: OnResult; onCreated: (id: number) => void }) {
  const topics = useShadowingTopics();
  const create = useAdminCreateShadowingVideo();
  const [url, setUrl] = useState('');
  const [topic, setTopic] = useState('');
  const [license, setLicense] = useState('');
  const [attribution, setAttribution] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const submit = () => {
    create.mutate({ url, topic, license, attribution, captions: file }, {
      onSuccess: (v) => {
        onResult(`Đã tạo bản nháp “${v.title}” (${v.segments.length} câu).`);
        setUrl(''); setAttribution(''); setFile(null);
        onCreated(v.id);
      },
    });
  };

  return (
    <SectionCard title="Thêm video vào kho" caption="Video vào kho ở dạng nháp. Duyệt các câu rồi mới xuất bản." sx={{ mb: 3 }}>
      <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '2fr 1fr 1fr' } }}>
        <TextField label="Link YouTube" value={url} onChange={(e) => setUrl(e.target.value)} size="small" />
        <TextField select label="Chủ đề" value={topic} onChange={(e) => setTopic(e.target.value)} size="small">
          <MenuItem value="">Chọn sau</MenuItem>
          {(topics.data?.topics ?? []).map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
        </TextField>
        <TextField select label="Giấy phép" value={license} onChange={(e) => setLicense(e.target.value)} size="small">
          <MenuItem value="">Chọn sau</MenuItem>
          {(topics.data?.licenses ?? []).map((l) => <MenuItem key={l} value={l}>{LICENSE_LABELS[l] ?? l}</MenuItem>)}
        </TextField>
      </Box>
      <TextField fullWidth size="small" label="Ghi công (bắt buộc với Creative Commons)" sx={{ mt: 2 }}
                 placeholder="VD: VOA Learning English — phạm vi công cộng"
                 value={attribution} onChange={(e) => setAttribution(e.target.value)} />
      <Box sx={{ display: 'flex', gap: 1.5, mt: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <Button component="label" variant="outlined" size="small">
          {file ? `Phụ đề: ${file.name}` : 'File phụ đề .srt/.vtt (không bắt buộc)'}
          <input hidden type="file" accept=".srt,.vtt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </Button>
        <Button variant="contained" disabled={!url.trim() || create.isPending} onClick={submit}>
          {create.isPending ? 'Đang lấy phụ đề...' : 'Tạo bản nháp'}
        </Button>
      </Box>
      {create.isPending && <LinearProgress sx={{ mt: 2 }} />}
      {create.error && <Alert severity="error" sx={{ mt: 2 }}>{errorText(create.error, 'Không tạo được video.')}</Alert>}
    </SectionCard>
  );
}

interface EditableSegment { start: string; end: string; text: string }

function ReviewDialog({ id, onClose, onResult }: { id: number | null; onClose: () => void; onResult: OnResult }) {
  const topics = useShadowingTopics();
  const { data: video, isLoading } = useAdminShadowingVideo(id);
  const update = useAdminUpdateShadowingVideo();
  const setStatus = useAdminShadowingStatus();

  const [title, setTitle] = useState('');
  const [topic, setTopic] = useState('');
  const [license, setLicense] = useState('');
  const [attribution, setAttribution] = useState('');
  const [segments, setSegments] = useState<EditableSegment[]>([]);
  const [dirtySegments, setDirtySegments] = useState(false);

  useEffect(() => {
    if (!video) return;
    setTitle(video.title);
    setTopic(video.topic ?? '');
    setLicense(video.license ?? '');
    setAttribution(video.attribution ?? '');
    setSegments(video.segments.map((s) => ({ start: String(s.start), end: String(s.end), text: s.text })));
    setDirtySegments(false);
  }, [video]);

  const editSegment = (i: number, field: keyof EditableSegment, value: string) => {
    setSegments((rows) => rows.map((r, j) => (j === i ? { ...r, [field]: value } : r)));
    setDirtySegments(true);
  };
  const removeSegment = (i: number) => {
    setSegments((rows) => rows.filter((_, j) => j !== i));
    setDirtySegments(true);
  };

  const save = () => {
    if (id === null) return;
    update.mutate({
      id,
      data: {
        title, topic: topic || null, license: license || null, attribution: attribution || null,
        ...(dirtySegments ? {
          segments: segments.map((s) => ({ start: Number(s.start), end: Number(s.end), text: s.text })),
        } : {}),
      },
    }, { onSuccess: () => { onResult('Đã lưu thay đổi.'); setDirtySegments(false); } });
  };

  const toggleStatus = () => {
    if (!video) return;
    const next = video.status === 'published' ? 'draft' : 'published';
    setStatus.mutate({ id: video.id, status: next }, {
      onSuccess: () => onResult(next === 'published' ? 'Đã xuất bản video.' : 'Đã gỡ xuất bản.'),
    });
  };

  const error = update.error ?? setStatus.error;

  return (
    <Dialog open={id !== null} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Duyệt video</DialogTitle>
      <DialogContent dividers>
        {isLoading || !video ? <Box sx={{ textAlign: 'center', py: 4 }}><CircularProgress /></Box> : (
          <Box>
            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
              <Chip size="small" color={video.status === 'published' ? 'success' : 'default'}
                    label={video.status === 'published' ? 'Đã xuất bản' : 'Nháp'} />
              {video.cefr_level && <Chip size="small" color="primary" label={`Cấp độ ${video.cefr_level}`} />}
              <Chip size="small" variant="outlined" label={CAPTION_LABELS[video.caption_kind] ?? video.caption_kind} />
              {video.vocab_profile && (
                <Chip size="small" variant="outlined"
                      label={`Tra được ${Math.round(video.vocab_profile.known_ratio * 100)}% số từ`} />
              )}
              <Button size="small" href={`https://www.youtube.com/watch?v=${video.youtube_id}`} target="_blank" rel="noreferrer">
                Mở trên YouTube
              </Button>
            </Box>

            <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, mb: 2 }}>
              <TextField size="small" label="Tiêu đề" value={title} onChange={(e) => setTitle(e.target.value)} />
              <TextField select size="small" label="Chủ đề" value={topic} onChange={(e) => setTopic(e.target.value)}>
                <MenuItem value="">Chưa chọn</MenuItem>
                {(topics.data?.topics ?? []).map((t) => <MenuItem key={t} value={t}>{t}</MenuItem>)}
              </TextField>
              <TextField select size="small" label="Giấy phép" value={license} onChange={(e) => setLicense(e.target.value)}>
                <MenuItem value="">Chưa chọn</MenuItem>
                {(topics.data?.licenses ?? []).map((l) => <MenuItem key={l} value={l}>{LICENSE_LABELS[l] ?? l}</MenuItem>)}
              </TextField>
              <TextField size="small" label="Ghi công" value={attribution} onChange={(e) => setAttribution(e.target.value)} />
            </Box>

            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
              {segments.length} câu — sửa chữ hoặc mốc thời gian (giây) của câu bị cắt sai
            </Typography>
            <Box sx={{ maxHeight: 420, overflowY: 'auto' }}>
              {segments.map((s, i) => (
                <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '32px 80px 80px 1fr 36px', gap: 1, mb: 1, alignItems: 'center' }}>
                  <Typography variant="caption" sx={{ fontWeight: 700 }}>{i + 1}</Typography>
                  <TextField size="small" value={s.start} onChange={(e) => editSegment(i, 'start', e.target.value)}
                             slotProps={{ htmlInput: { inputMode: 'decimal', 'aria-label': `Bắt đầu câu ${i + 1}` } }} />
                  <TextField size="small" value={s.end} onChange={(e) => editSegment(i, 'end', e.target.value)}
                             slotProps={{ htmlInput: { inputMode: 'decimal', 'aria-label': `Kết thúc câu ${i + 1}` } }} />
                  <TextField size="small" value={s.text} onChange={(e) => editSegment(i, 'text', e.target.value)} multiline
                             slotProps={{ htmlInput: { 'aria-label': `Nội dung câu ${i + 1}` } }} />
                  <IconButton size="small" aria-label={`Xóa câu ${i + 1}`} onClick={() => removeSegment(i)}>
                    <CloseIcon size={16} />
                  </IconButton>
                </Box>
              ))}
            </Box>
            {error && <Alert severity="error" sx={{ mt: 2 }}>{errorText(error, 'Không lưu được.')}</Alert>}
          </Box>
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Đóng</Button>
        <Button variant="outlined" disabled={!video || update.isPending} onClick={save}>Lưu thay đổi</Button>
        {video && (
          <Button variant="contained" color={video.status === 'published' ? 'warning' : 'success'}
                  disabled={setStatus.isPending || dirtySegments} onClick={toggleStatus}>
            {video.status === 'published' ? 'Gỡ xuất bản' : 'Xuất bản'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

/** UC-97 — admin duyệt kho video shadowing (quyền admin.content). */
function ShadowingAdminTab({ onResult }: { onResult: OnResult }) {
  const { data, isLoading } = useAdminShadowingVideos();
  const remove = useAdminDeleteShadowingVideo();
  const [reviewing, setReviewing] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  return (
    <Box>
      <AddVideoForm onResult={onResult} onCreated={setReviewing} />

      {isLoading && <Box sx={{ textAlign: 'center', py: 6 }}><CircularProgress /></Box>}
      {data && data.length === 0 && <Alert severity="info">Kho video chưa có video nào.</Alert>}
      {data && data.length > 0 && (
        <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Video</TableCell>
                <TableCell>Chủ đề</TableCell>
                <TableCell>Cấp độ</TableCell>
                <TableCell>Số câu</TableCell>
                <TableCell>Giấy phép</TableCell>
                <TableCell>Trạng thái</TableCell>
                <TableCell align="right">Thao tác</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.map((v) => (
                <TableRow key={v.id}>
                  <TableCell sx={{ maxWidth: 320 }}>{v.title}</TableCell>
                  <TableCell>{v.topic ?? '—'}</TableCell>
                  <TableCell>{v.cefr_level ?? '—'}</TableCell>
                  <TableCell>{v.segment_count}</TableCell>
                  <TableCell>{v.license ? LICENSE_LABELS[v.license] ?? v.license : '—'}</TableCell>
                  <TableCell>
                    <Chip size="small" color={v.status === 'published' ? 'success' : 'default'}
                          label={v.status === 'published' ? 'Đã xuất bản' : 'Nháp'} />
                  </TableCell>
                  <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                    <Button size="small" onClick={() => setReviewing(v.id)}>Duyệt</Button>
                    <Button size="small" color="error" onClick={() => setConfirmDelete(v.id)}>Xóa</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <ReviewDialog id={reviewing} onClose={() => setReviewing(null)} onResult={onResult} />

      <Dialog open={confirmDelete !== null} onClose={() => setConfirmDelete(null)}>
        <DialogTitle>Xóa video khỏi kho?</DialogTitle>
        <DialogContent>
          <Typography variant="body2">
            Người học sẽ không thấy video này nữa. Lịch sử luyện cũ vẫn được giữ lại.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDelete(null)}>Hủy</Button>
          <Button color="error" variant="contained" disabled={remove.isPending} onClick={() => {
            if (confirmDelete === null) return;
            remove.mutate(confirmDelete, {
              onSuccess: () => { onResult('Đã xóa video.'); setConfirmDelete(null); },
              onError: (e) => onResult(errorText(e, 'Không xóa được.')),
            });
          }}>Xóa</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

export default ShadowingAdminTab;
