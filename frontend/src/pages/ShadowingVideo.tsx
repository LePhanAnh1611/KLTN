import { useEffect, useRef, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import type { ReadAloudResult } from '../api/extras';
import {
  CAPTION_LABELS,
  LICENSE_LABELS,
  useShadowingAttempt,
  useShadowingVideo,
  type ShadowingAttemptResult,
} from '../api/shadowing';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import { useYouTubePlayer } from '../hooks/useYouTubePlayer';
import PageHeader from '../components/PageHeader';
import ReadAloudResultView from '../components/ReadAloudResult';
import RecordingPlayback from '../components/RecordingPlayback';
import SectionCard from '../components/SectionCard';
import { ArrowLeftIcon, CheckIcon, MicIcon, SpeakerIcon } from '../components/icons';

/** Kết quả shadowing dùng chung khung hiển thị với "đọc theo câu mẫu". */
function toReadAloud(r: ShadowingAttemptResult): ReadAloudResult {
  return { ...r, item_id: r.segment_index, word: '' };
}

function SpeedCard({ result }: { result: ShadowingAttemptResult }) {
  if (result.speed_ratio === null) return null;
  return (
    <SectionCard sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', alignItems: 'baseline' }}>
        <Box>
          <Typography variant="caption" color="text.secondary">Bạn nói</Typography>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>{Math.round(result.learner_wpm ?? 0)} từ/phút</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Người trong video</Typography>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>{Math.round(result.original_wpm ?? 0)} từ/phút</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Bắt nhịp</Typography>
          <Typography variant="h6" sx={{ fontWeight: 800 }}>{Math.round(result.speed_ratio * 100)}%</Typography>
        </Box>
      </Box>
      {result.speed_feedback && (
        <Typography variant="body2" sx={{ mt: 1 }}>{result.speed_feedback}</Typography>
      )}
    </SectionCard>
  );
}

/** UC-97 — luyện từng câu của một video: nghe → video dừng → nhại lại → chấm. */
function ShadowingVideo() {
  const { id } = useParams();
  const videoId = Number(id);
  const { data: video, isLoading, error } = useShadowingVideo(videoId);
  const player = useYouTubePlayer(video?.youtube_id);
  const recorder = useAudioRecorder();
  const attempt = useShadowingAttempt(videoId);

  const [current, setCurrent] = useState(0);
  const [result, setResult] = useState<ShadowingAttemptResult | null>(null);
  const submittedBlob = useRef<Blob | null>(null);

  const segments = video?.segments ?? [];
  const segment = segments[current];
  const progress = video?.progress.find((p) => p.index === segment?.index);

  const goTo = (index: number) => {
    if (index < 0 || index >= segments.length) return;
    player.pause();
    recorder.reset();
    attempt.reset();
    setResult(null);
    setCurrent(index);
  };

  const listen = (rate = 1) => {
    if (segment) player.playSegment(segment.start, segment.end, rate);
  };

  const toggleRecord = () => {
    if (recorder.recording) {
      recorder.stop();
    } else {
      player.pause();
      setResult(null);
      void recorder.start();
    }
  };

  // Dừng ghi là chấm luôn — giữ nhịp nghe → nhại → xem kết quả liền mạch.
  useEffect(() => {
    if (!recorder.blob || recorder.recording || !segment) return;
    if (submittedBlob.current === recorder.blob) return;
    submittedBlob.current = recorder.blob;
    attempt.mutate({ blob: recorder.blob, segmentIndex: segment.index }, { onSuccess: setResult });
  }, [recorder.blob, recorder.recording]); // chỉ chạy khi có bản ghi mới

  // Giữ hàm mới nhất cho phím tắt mà không phải gắn lại listener mỗi lần render
  const keys = useRef({ listen, toggleRecord, goTo, current });
  keys.current = { listen, toggleRecord, goTo, current };

  // Phím tắt: Space nghe · R ghi/dừng · ← → chuyển câu
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)) return;
      const k = keys.current;
      if (e.code === 'Space') { e.preventDefault(); k.listen(); }
      else if (e.key === 'r' || e.key === 'R') { e.preventDefault(); k.toggleRecord(); }
      else if (e.key === 'ArrowRight') k.goTo(k.current + 1);
      else if (e.key === 'ArrowLeft') k.goTo(k.current - 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (error || !video) {
    return (
      <Alert severity="error">
        {error instanceof ApiError ? error.message : 'Không tìm thấy video.'}
      </Alert>
    );
  }

  return (
    <Box>
      <PageHeader
        title={video.title}
        subtitle={[
          video.cefr_level && `Cấp độ ${video.cefr_level}`,
          video.words_per_minute && `${Math.round(video.words_per_minute)} từ/phút`,
          `${video.passed_count}/${video.segments.length} câu đạt`,
        ].filter(Boolean).join(' · ')}
        actions={
          <Button component={RouterLink} to="/shadowing" startIcon={<ArrowLeftIcon size={18} />}>
            Kho video
          </Button>
        }
      />

      <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: '1fr', lg: 'minmax(0, 2fr) minmax(280px, 1fr)' } }}>
        <Box sx={{ minWidth: 0 }}>
          <Box sx={{
            position: 'relative', aspectRatio: '16 / 9', bgcolor: 'grey.900',
            borderRadius: '20px', overflow: 'hidden', mb: 1,
          }}>
            <Box ref={player.containerRef} sx={{ position: 'absolute', inset: 0, '& iframe': { width: '100%', height: '100%' } }} />
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 2 }}>
            {[video.channel, video.license && LICENSE_LABELS[video.license], video.attribution,
              CAPTION_LABELS[video.caption_kind]].filter(Boolean).join(' · ')}
          </Typography>
          {player.error && <Alert severity="error" sx={{ mb: 2 }}>{player.error}</Alert>}
          {video.caption_kind === 'generated' && (
            <Alert severity="info" sx={{ mb: 2 }}>
              Video này dùng phụ đề tự động nên một vài câu có thể bị cắt chưa tròn ý.
            </Alert>
          )}

          {segment && (
            <SectionCard
              title={`Câu ${current + 1}/${segments.length}`}
              action={progress?.passed
                ? <Chip color="success" icon={<CheckIcon size={16} />} label="Đã đạt" />
                : progress?.best_accuracy != null
                  ? <Chip label={`Tốt nhất ${Math.round(progress.best_accuracy * 100)}%`} />
                  : undefined}
              sx={{ mb: 2 }}
            >
              <Typography variant="h5" sx={{ fontWeight: 600, mb: 2.5, lineHeight: 1.5 }}>
                {segment.text}
              </Typography>

              <Box sx={{ display: 'flex', gap: 1.25, flexWrap: 'wrap', alignItems: 'center' }}>
                <Button variant="outlined" startIcon={<SpeakerIcon size={18} />}
                        disabled={!player.ready || recorder.recording} onClick={() => listen()}>
                  Nghe câu <Box component="kbd" sx={{ ml: 1, fontSize: 11, opacity: 0.7 }}>Space</Box>
                </Button>
                <Button variant="outlined" disabled={!player.ready || recorder.recording}
                        onClick={() => listen(0.75)}>
                  Nghe chậm 0,75×
                </Button>
                <Button
                  variant="contained" color={recorder.recording ? 'error' : 'primary'}
                  startIcon={<MicIcon size={18} />}
                  disabled={!recorder.supported || attempt.isPending}
                  onClick={toggleRecord}
                >
                  {recorder.recording ? 'Dừng và chấm' : 'Nhại lại'}
                  <Box component="kbd" sx={{ ml: 1, fontSize: 11, opacity: 0.7 }}>R</Box>
                </Button>
                {recorder.recording && <Chip color="error" label={`${recorder.elapsedSec.toFixed(1)}s`} />}
              </Box>

              {!recorder.supported && (
                <Alert severity="warning" sx={{ mt: 2 }}>Trình duyệt này không ghi âm được.</Alert>
              )}
              {recorder.error && <Alert severity="error" sx={{ mt: 2 }}>{recorder.error}</Alert>}
              {(recorder.recording || attempt.isPending) && <LinearProgress sx={{ mt: 2 }} />}
              {attempt.error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {attempt.error instanceof ApiError ? attempt.error.message : 'Không chấm được.'}
                </Alert>
              )}
              {recorder.objectUrl && !recorder.recording && (
                <Box sx={{ mt: 2 }}>
                  <RecordingPlayback src={recorder.objectUrl} label="Nghe lại giọng bạn" />
                </Box>
              )}

              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 2.5 }}>
                <Button disabled={current === 0} onClick={() => goTo(current - 1)}>← Câu trước</Button>
                <Button disabled={current >= segments.length - 1} onClick={() => goTo(current + 1)}>
                  Câu sau →
                </Button>
              </Box>
            </SectionCard>
          )}

          {result && (
            <Box>
              <Alert severity={result.passed ? 'success' : 'warning'} sx={{ mb: 2 }}>
                {result.passed
                  ? 'Câu này đã đạt. Chuyển sang câu sau, hoặc nhại lại để bắt nhịp sát hơn.'
                  : `Cần nhại đúng từ ${Math.round(result.pass_accuracy * 100)}% số từ để đạt. Nghe lại rồi thử lần nữa.`}
              </Alert>
              <SpeedCard result={result} />
              <ReadAloudResultView result={toReadAloud(result)} />
            </Box>
          )}
        </Box>

        <SectionCard title="Các câu trong video" sx={{ alignSelf: 'start' }}>
          <List dense sx={{ maxHeight: { lg: 640 }, overflowY: 'auto', mx: -1 }}>
            {segments.map((s, i) => {
              const p = video.progress.find((x) => x.index === s.index);
              return (
                <ListItemButton key={s.index} selected={i === current} onClick={() => goTo(i)}
                                sx={{ borderRadius: 2, alignItems: 'flex-start', gap: 1 }}>
                  <Typography variant="caption" sx={{ fontWeight: 700, minWidth: 24, pt: 0.25 }}>
                    {i + 1}
                  </Typography>
                  <Typography variant="body2" sx={{ flexGrow: 1 }}>{s.text}</Typography>
                  {p?.passed && <Box sx={{ color: 'success.main', pt: 0.25 }}><CheckIcon size={16} /></Box>}
                </ListItemButton>
              );
            })}
          </List>
        </SectionCard>
      </Box>
    </Box>
  );
}

export default ShadowingVideo;
