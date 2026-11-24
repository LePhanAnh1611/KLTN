import { useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  useItemAttempts,
  useReadAloud,
  type ReadAloudResult,
} from '../api/extras';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import ReadAloudResultView from './ReadAloudResult';
import RecordingPlayback from './RecordingPlayback';
import SpeakButton from './SpeakButton';
import { MicIcon } from './icons';

interface Props {
  itemId: number;
  word: string;
  example: string | null;
  onResult: (msg: string) => void;
}

/** Dựng lại kết quả đầy đủ từ bản ghi đã lưu trên máy chủ.
 *
 * Nhờ vậy kết quả KHÔNG nằm trong state của màn hình: chuyển sang tab khác rồi
 * quay lại vẫn thấy lần chấm gần nhất, thay vì mất trắng như bản trước. */
function useLastResult(itemId: number, word: string): ReadAloudResult | null {
  const { data } = useItemAttempts(itemId);

  return useMemo(() => {
    const latest = (data ?? []).find((row) => row.kind === 'sentence' && row.detail);
    if (!latest?.detail) return null;

    return {
      ...latest.detail,
      attempt_id: latest.id,
      item_id: latest.item_id,
      word,
      expected_text: latest.target_text ?? '',
      transcript: latest.transcript ?? '',
    };
  }, [data, word]);
}

/** Luyện đọc CÂU MẪU chứa từ đang học — máy chủ chấm bằng Whisper.
 *
 * Khác ô luyện từ ngay phía trên (trình duyệt chấm, chỉ một từ): ở đây biết
 * trước cả câu nên chỉ ra được đúng từ nào đọc sai, và không cần mô hình ngôn
 * ngữ nên chấm xong trong khoảng hai giây.
 */
function SentencePractice({ itemId, word, example, onResult }: Props) {
  const recorder = useAudioRecorder(60);
  const assess = useReadAloud();
  const saved = useLastResult(itemId, word);
  // Bản thu đã gửi chấm: giữ lại để nghe đối chiếu với kết quả, chỉ ẩn nút "Chấm"
  const [assessedBlob, setAssessedBlob] = useState<Blob | null>(null);

  if (!example?.trim()) {
    return (
      <Alert severity="info">
        Từ này chưa có câu ví dụ nên chưa luyện đọc câu được. Thêm ví dụ cho từ
        trong màn chi tiết bộ từ vựng rồi quay lại.
      </Alert>
    );
  }

  const submit = () => {
    if (!recorder.blob) return;
    const blob = recorder.blob;
    assess.mutate(
      { blob, itemId },
      {
        onSuccess: () => setAssessedBlob(blob),
        onError: (e) => onResult(
          e instanceof ApiError ? e.message : 'Không chấm được câu vừa đọc.',
        ),
      },
    );
  };

  // Ưu tiên kết quả vừa chấm, không có thì lấy bản đã lưu gần nhất
  const shown = assess.data ?? saved;

  return (
    <Box sx={{ textAlign: 'left' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5, flexWrap: 'wrap' }}>
        <Typography sx={{ fontWeight: 900, fontSize: 18, lineHeight: 1.5, textTransform: 'uppercase', flexGrow: 1 }}>
          Đọc câu mẫu
        </Typography>
        <SpeakButton text={example} label="Nghe câu mẫu" />
      </Box>

      <Typography variant="h6" sx={{ fontStyle: 'italic', mb: 2 }}>
        “{example}”
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
        {!recorder.recording ? (
          <Button
            variant="contained" startIcon={<MicIcon size={18} />}
            disabled={!recorder.supported || assess.isPending}
            onClick={() => void recorder.start()}
          >
            {recorder.blob ? 'Đọc lại' : 'Đọc câu này'}
          </Button>
        ) : (
          <Button variant="contained" color="error" onClick={recorder.stop}>
            Dừng
          </Button>
        )}

        {(recorder.recording || recorder.blob) && (
          <Chip color={recorder.recording ? 'error' : 'default'}
                label={`${recorder.elapsedSec.toFixed(1)}s`} />
        )}

        {recorder.blob && !recorder.recording && recorder.blob !== assessedBlob && (
          <Button variant="contained" color="success"
                  disabled={assess.isPending} onClick={submit}>
            {assess.isPending ? 'Đang chấm...' : 'Chấm câu này'}
          </Button>
        )}
      </Box>

      {recorder.objectUrl && !recorder.recording && (
        <Box sx={{ mt: 1.5 }}>
          <RecordingPlayback src={recorder.objectUrl} label="Nghe lại giọng bạn" />
        </Box>
      )}

      {recorder.error && <Alert severity="error" sx={{ mt: 1.5 }}>{recorder.error}</Alert>}
      {(recorder.recording || assess.isPending) && (
        <LinearProgress sx={{ mt: 1.5 }} />
      )}

      {!shown && !recorder.recording && !recorder.blob && (
        <Typography variant="body2" color="text.secondary"
                    sx={{ mt: 2.5, p: 2.5, borderRadius: '16px', bgcolor: '#F4F8FD', textAlign: 'center' }}>
          Đọc xong, kết quả sẽ hiện ở đây: từ nào đúng, từ nào cần đọc lại.
        </Typography>
      )}

      {shown && (
        <Box sx={{ mt: 2.5 }}>
          {!assess.data && (
            <Typography variant="caption" color="text.secondary"
                        sx={{ display: 'block', mb: 1 }}>
              Kết quả lần đọc gần nhất của bạn.
            </Typography>
          )}
          <ReadAloudResultView result={shown} />
        </Box>
      )}
    </Box>
  );
}

export default SentencePractice;
