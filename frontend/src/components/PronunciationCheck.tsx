import { useEffect, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import {
  BAND_TEXT,
  scorePronunciation,
  type PronunciationBand,
  type PronunciationResult,
} from '../lib/pronunciation';
import {
  recognitionErrorText,
  useSpeechRecognition,
  type RecognitionError,
} from '../hooks/useSpeechRecognition';
import { useAudioRecorder } from '../hooks/useAudioRecorder';
import RecordingPlayback from './RecordingPlayback';
import { MicIcon } from './icons';

const BAND_COLOR: Record<PronunciationBand, 'success' | 'warning' | 'error'> = {
  good: 'success',
  fair: 'warning',
  poor: 'error',
};

/** Chấm phát âm một từ: bấm mic → đọc → so với từ đích → điểm + nhận xét.
 *
 * Dùng bộ nhận dạng có sẵn của trình duyệt, không gọi dịch vụ ngoài. Kết quả chỉ
 * hiển thị tại chỗ, KHÔNG ghi vào Interaction/mastery — chấm phát âm không phải
 * tín hiệu học của DKT (BR-05 chỉ ghi kết quả trả lời đúng/sai).
 */
interface PronunciationCheckProps {
  word: string;
  /** Báo kết quả ra ngoài để nơi gọi thống kê phiên luyện. */
  onResult?: (result: PronunciationResult) => void;
  /** Nút chấm là hành động chính của màn (trang Luyện phát âm). */
  prominent?: boolean;
}

function PronunciationCheck({ word, onResult, prominent = false }: PronunciationCheckProps) {
  const { supported, listening, listen, cancel } = useSpeechRecognition();
  const [result, setResult] = useState<PronunciationResult | null>(null);
  const [error, setError] = useState<RecognitionError | null>(null);
  // Web Speech API chỉ trả chữ, không trả audio — nên thu song song bằng
  // MediaRecorder để người học nghe lại chính mình. Thu không được (Safari cũ,
  // từ chối quyền) thì vẫn chấm bình thường, chỉ không có nút nghe lại.
  const recorder = useAudioRecorder(15);

  // Bộ nhận dạng tự dừng khi hết tiếng (hoặc lỗi/hủy) → dừng thu theo
  useEffect(() => {
    if (!listening && recorder.recording) recorder.stop();
  }, [listening, recorder.recording, recorder.stop]);

  if (!supported) {
    return (
      <Tooltip title="Trình duyệt này không hỗ trợ nhận dạng giọng nói (hãy dùng Chrome hoặc Edge)">
        <span>
          <Button size="small" startIcon={<MicIcon size={16} />} disabled>
            Chấm phát âm
          </Button>
        </span>
      </Tooltip>
    );
  }

  const start = async () => {
    setResult(null);
    setError(null);
    // Mở micro cho bộ thu trước, để không mất âm đầu của từ
    await recorder.start();
    listen(
      (alternatives) => {
        const scored = scorePronunciation(word, alternatives);
        setResult(scored);
        onResult?.(scored);
      },
      (code) => setError(code),
    );
  };

  return (
    <Box sx={{ mt: 1.5 }}>
      <Button
        size={prominent ? 'medium' : 'small'}
        variant={listening || prominent ? 'contained' : 'outlined'}
        color={listening ? 'error' : 'primary'}
        startIcon={<MicIcon size={16} />}
        // Bug #5: bấm lại lần nữa khi đang nghe = hủy thu, không chấm điểm.
        onClick={listening ? cancel : () => void start()}
        aria-pressed={listening}
      >
        {listening ? 'Đang nghe… bấm để hủy' : result ? 'Đọc lại' : 'Chấm phát âm'}
      </Button>

      {listening && <LinearProgress sx={{ mt: 1, borderRadius: 1 }} />}

      {error && (
        <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1 }}>
          {recognitionErrorText(error)}
        </Typography>
      )}

      {result && (
        <Box sx={{ mt: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
            <Chip size="small" color={BAND_COLOR[result.band]}
                  label={`${result.score}/100`} sx={{ fontWeight: 700 }} />
            <Typography variant="body2" color="text.secondary">
              {BAND_TEXT[result.band]}
            </Typography>
          </Box>
          {!result.exact && result.heard && (
            <Typography variant="caption" color="text.secondary"
                        sx={{ display: 'block', mt: 0.5 }}>
              Máy nghe được: “{result.heard}”
            </Typography>
          )}
          {recorder.objectUrl && !recorder.recording && (
            <Box sx={{ mt: 1, display: 'flex', justifyContent: 'center' }}>
              <RecordingPlayback src={recorder.objectUrl} label="Giọng bạn" compact />
            </Box>
          )}
        </Box>
      )}
    </Box>
  );
}

export default PronunciationCheck;
