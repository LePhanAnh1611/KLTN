import { useState } from 'react';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import {
  CRITERIA,
  CRITERION_LABELS,
  useAssessSpeaking,
  useSpeakingHealth,
  useSpeakingHistory,
  type SpeakingAssessment,
} from '../api/speaking';
import { ApiError } from '../api/client';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import RecordingPlayback from '../components/RecordingPlayback';
import SectionCard from '../components/SectionCard';
import SpeakingResult, { LEVEL_COLOR } from '../components/SpeakingResult';
import { MicIcon } from '../components/icons';

/** Đề mẫu — người học sửa được hoặc tự nhập đề riêng. */
const SAMPLE_PROMPTS = [
  'Describe a place you enjoy visiting and explain why.',
  'Talk about a skill you would like to learn and how you plan to learn it.',
  'Describe a person who has influenced you.',
  'What do you usually do at the weekend? Give details.',
  'Talk about a book or film that made an impression on you.',
];

const MIN_USEFUL_SEC = 15;

/** Trạng thái phụ thuộc cục bộ — nói rõ trước khi người học tốn công ghi âm. */
function DependencyBanner() {
  const { data, isLoading } = useSpeakingHealth();
  if (isLoading || !data) return null;

  const problems: string[] = [];
  if (!data.asr_ready) problems.push(data.asr_detail);
  if (!data.llm_ready) problems.push(data.llm_detail);
  // Thiếu rubric thì KHÔNG chấm được tiêu chí nào cả, kể cả C1/C2
  if (!data.rubric_ready) problems.push(`Chưa nạp được rubric: ${data.rubric_detail}`);

  if (problems.length === 0) {
    return (
      <Alert severity="success" sx={{ mb: 3 }}>
        Sẵn sàng - nhận dạng giọng nói và mô hình chấm đều đang chạy trên máy chủ
        (rubric v{data.rubric_version}).
        {!data.rubric_calibrated
          && ' Lưu ý: rubric chưa calibrate với người chấm thật, hãy đọc kết quả như một tham chiếu.'}
      </Alert>
    );
  }

  return (
    <Alert severity={data.asr_ready && data.rubric_ready ? 'warning' : 'error'} sx={{ mb: 3 }}>
      <AlertTitle>
        {!data.rubric_ready
          ? 'Chưa chấm được - thiếu file rubric'
          : data.asr_ready
            ? 'Chấm được một phần'
            : 'Chưa chấm được - thiếu dịch vụ nhận dạng giọng nói'}
      </AlertTitle>
      {problems.map((problem) => (
        <Typography key={problem} variant="body2">• {problem}</Typography>
      ))}
      {data.asr_ready && data.rubric_ready && !data.llm_ready && (
        <Typography variant="body2" sx={{ mt: 1 }}>
          Độ trôi chảy và độ dễ hiểu vẫn chấm bình thường; ngữ pháp và mạch lạc sẽ
          để trống thay vì đoán bừa.
        </Typography>
      )}
    </Alert>
  );
}

function PracticeTab({ onResult }: { onResult: (msg: string) => void }) {
  const [prompt, setPrompt] = useState(SAMPLE_PROMPTS[0]);
  const [result, setResult] = useState<SpeakingAssessment | null>(null);

  const recorder = useAudioRecorder();
  const assess = useAssessSpeaking();

  const tooShort = recorder.blob !== null && recorder.elapsedSec < MIN_USEFUL_SEC;

  const submit = () => {
    if (!recorder.blob) return;
    assess.mutate(
      { blob: recorder.blob, taskPrompt: prompt.trim() },
      {
        onSuccess: setResult,
        onError: (e) => onResult(
          e instanceof ApiError ? e.message : 'Không chấm được bài nói.',
        ),
      },
    );
  };

  const restart = () => {
    setResult(null);
    recorder.reset();
  };

  if (result) {
    return (
      <Box>
        <Box sx={{ display: 'flex', gap: 1.5, mb: 3, flexWrap: 'wrap' }}>
          <Button variant="contained" onClick={restart}>Luyện bài khác</Button>
          {recorder.objectUrl && (
            <RecordingPlayback src={recorder.objectUrl} />
          )}
        </Box>
        <SpeakingResult
          transcript={result.transcript}
          audioMetrics={result.audio_metrics}
          scores={result.scores}
          overallLevel={result.overall_level}
          developmentalFeedback={result.developmental_feedback}
          warnings={result.warnings}
          rubricVersion={result.rubric_version}
          attemptId={result.attempt_id}
          onResult={onResult}
        />
      </Box>
    );
  }

  return (
    <Box>
      <SectionCard
        title="Đề bài"
        caption="Chọn đề mẫu hoặc tự viết đề."
        sx={{ mb: 3 }}
      >
        <TextField
          select fullWidth size="small" label="Đề mẫu" sx={{ mb: 2 }}
          value={SAMPLE_PROMPTS.includes(prompt) ? prompt : ''}
          onChange={(e) => setPrompt(e.target.value)}
        >
          {SAMPLE_PROMPTS.map((sample) => (
            <MenuItem key={sample} value={sample}>{sample}</MenuItem>
          ))}
        </TextField>
        <TextField
          fullWidth multiline minRows={2} label="Đề bài đang dùng"
          value={prompt} onChange={(e) => setPrompt(e.target.value)}
        />
      </SectionCard>

      <SectionCard title="Ghi âm câu trả lời">
        {!recorder.supported && (
          <Alert severity="error">
            Trình duyệt này không hỗ trợ ghi âm. Hãy dùng Chrome, Edge hoặc Firefox.
          </Alert>
        )}
        {recorder.error && <Alert severity="error" sx={{ mb: 2 }}>{recorder.error}</Alert>}

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
          {!recorder.recording ? (
            <Button
              variant="contained" size="large" startIcon={<MicIcon size={18} />}
              disabled={!recorder.supported || assess.isPending}
              onClick={() => { setResult(null); void recorder.start(); }}
            >
              {recorder.blob ? 'Ghi lại' : 'Bắt đầu ghi âm'}
            </Button>
          ) : (
            <Button variant="contained" color="error" size="large" onClick={recorder.stop}>
              Dừng ghi
            </Button>
          )}

          {(recorder.recording || recorder.blob) && (
            <Chip
              color={recorder.recording ? 'error' : 'default'}
              label={`${recorder.elapsedSec.toFixed(1)}s`}
            />
          )}

          {recorder.objectUrl && !recorder.recording && (
            <RecordingPlayback src={recorder.objectUrl} />
          )}
        </Box>

        {recorder.recording && (
          <LinearProgress sx={{ mt: 2 }} />
        )}

        {tooShort && (
          <Alert severity="warning" sx={{ mt: 2 }}>
            Bản ghi chỉ {recorder.elapsedSec.toFixed(1)}s. Dưới {MIN_USEFUL_SEC}s thì
            kết quả chấm gần như không có ý nghĩa - nên nói dài hơn.
          </Alert>
        )}

        {recorder.blob && !recorder.recording && (
          <Box sx={{ mt: 2.5 }}>
            <Button
              variant="contained" size="large"
              disabled={assess.isPending || !prompt.trim()}
              onClick={submit}
            >
              {assess.isPending ? 'Đang chấm...' : 'Gửi đi chấm'}
            </Button>
            {assess.isPending && (
              <>
                <LinearProgress sx={{ mt: 2 }} />
                <Typography variant="caption" color="text.secondary"
                            sx={{ display: 'block', mt: 1 }}>
                  Nhận dạng giọng nói rồi chấm 4 tiêu chí - chạy trên máy chủ, có thể
                  mất vài chục giây tùy cấu hình.
                </Typography>
              </>
            )}
          </Box>
        )}
      </SectionCard>
    </Box>
  );
}

function HistoryTab({ onResult }: { onResult: (msg: string) => void }) {
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const { data, isLoading } = useSpeakingHistory(page);

  if (isLoading) return <LinearProgress />;
  if (!data || data.total === 0) {
    return (
      <EmptyState
        icon={<MicIcon size={24} />}
        title="Chưa có bài nói nào"
        description="Sang tab Luyện nói để ghi âm bài đầu tiên."
      />
    );
  }

  const open = data.items.find((item) => item.id === openId);

  if (open) {
    return (
      <Box>
        <Button sx={{ mb: 2 }} onClick={() => setOpenId(null)}>← Về danh sách</Button>
        <SpeakingResult
          transcript={open.transcript}
          audioMetrics={open.audio_metrics}
          scores={open.scores}
          overallLevel={open.overall_level}
          developmentalFeedback={open.developmental_feedback}
          warnings={open.warnings}
          rubricVersion={open.rubric_version}
          attemptId={open.id}
          onResult={onResult}
        />
      </Box>
    );
  }

  return (
    <Box>
      {data.progress.length > 1 && (
        <SectionCard
          title="Tiến bộ theo thời gian"
          caption={
            `${data.progress.length} lần chấm gần nhất trên rubric v`
            + `${data.progress_rubric_version}. Chỉ so các lần cùng phiên bản rubric - `
            + 'sau khi rubric được calibrate lại, mức cũ và mới không so trực tiếp được.'
          }
          sx={{ mb: 3 }}
        >
          {/* Bảng thay vì biểu đồ: dữ liệu là mức rời rạc 1-4, vẽ đường cong sẽ
              gợi ý một độ chính xác mà thang 4 mức không có */}
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {data.progress.map((point) => (
              <Box key={point.attempt_id} sx={{ textAlign: 'center', minWidth: 64 }}>
                <Chip
                  size="small" color={LEVEL_COLOR[point.overall_level]}
                  label={point.overall_level}
                />
                <Typography variant="caption" color="text.secondary"
                            sx={{ display: 'block', mt: 0.5 }}>
                  {new Date(point.created_at).toLocaleDateString('vi-VN', {
                    day: '2-digit', month: '2-digit',
                  })}
                </Typography>
              </Box>
            ))}
          </Box>
        </SectionCard>
      )}

      {data.items.map((item) => (
        <SectionCard key={item.id} sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
            <Chip color={LEVEL_COLOR[item.overall_level]} label={`Mức ${item.overall_level}`} />
            <Box sx={{ flexGrow: 1, minWidth: 180 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                {item.task_prompt}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {new Date(item.created_at).toLocaleString('vi-VN')}
                {' · '}
                {CRITERIA.map((key) => `${CRITERION_LABELS[key]} ${item.scores[key]?.level ?? '-'}`)
                  .join(' · ')}
              </Typography>
            </Box>
            {item.has_appeal && <Chip size="small" variant="outlined" label="đã phản hồi" />}
            <Button size="small" onClick={() => setOpenId(item.id)}>Xem chi tiết</Button>
          </Box>
        </SectionCard>
      ))}

      {data.total > data.page_size && (
        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, mt: 2 }}>
          <Button disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Trước</Button>
          <Button
            disabled={page * data.page_size >= data.total}
            onClick={() => setPage((p) => p + 1)}
          >
            Sau
          </Button>
        </Box>
      )}
    </Box>
  );
}

/** Module luyện nói — độc lập với lộ trình DKT. */
function Speaking() {
  const [tab, setTab] = useState(0);
  const [snack, setSnack] = useState<string | null>(null);

  return (
    <Box>
      <PageHeader
        title="Luyện nói & nhận xét"
        subtitle="Ghi âm câu trả lời, nhận điểm 4 tiêu chí và gợi ý sửa."
      />

      <DependencyBanner />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Luyện nói" />
        <Tab label="Lịch sử" />
      </Tabs>

      {tab === 0 ? <PracticeTab onResult={setSnack} /> : <HistoryTab onResult={setSnack} />}

      <Snackbar open={snack !== null} autoHideDuration={4000}
                onClose={() => setSnack(null)} message={snack ?? ''} />
    </Box>
  );
}

export default Speaking;
