import type { SyntheticEvent } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

/** Nghe lại bản thu của chính người học — dùng chung cho mọi màn có ghi âm.
 *
 * Phát thẳng object URL trong trình duyệt, KHÔNG tải lại từ máy chủ: máy chủ
 * chỉ dùng file tạm để nhận dạng rồi bỏ, nên bản thu chỉ sống trong phiên này.
 */
interface Props {
  src: string;
  label?: string;
  /** Bản gọn cho chỗ chật như bong bóng hội thoại. */
  compact?: boolean;
}

/** Chrome ghi WebM qua MediaRecorder mà KHÔNG ghi thời lượng vào header, nên
 * `duration` = Infinity: thanh tua đứng im và hiện "0:00". Mẹo phổ biến: tua tới
 * một mốc rất xa để trình duyệt đọc hết file và tự tính thời lượng, rồi tua về 0. */
function fixInfiniteDuration(event: SyntheticEvent<HTMLAudioElement>) {
  const audio = event.currentTarget;
  if (audio.duration !== Infinity) return;
  const restore = () => {
    audio.removeEventListener('timeupdate', restore);
    audio.currentTime = 0;
  };
  audio.addEventListener('timeupdate', restore);
  audio.currentTime = 1e101;
}

function RecordingPlayback({ src, label = 'Nghe lại bản thu', compact = false }: Props) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700 }}>
        {label}
      </Typography>
      <Box
        component="audio"
        controls
        preload="metadata"
        src={src}
        onLoadedMetadata={fixInfiniteDuration}
        sx={{ height: compact ? 32 : 40, maxWidth: '100%', width: compact ? 240 : 300 }}
      />
    </Box>
  );
}

export default RecordingPlayback;
