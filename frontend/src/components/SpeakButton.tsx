import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';

import { useSpeech } from '../hooks/useSpeech';
import { SpeakerIcon } from './icons';

interface SpeakButtonProps {
  text: string;
  size?: number;
  label?: string;
}

/** UC-29 — nút loa dùng chung. E1: trình duyệt không hỗ trợ TTS thì nút vẫn hiện
 * nhưng bị khóa kèm giải thích, thay vì biến mất khó hiểu. */
function SpeakButton({ text, size = 18, label = 'Nghe phát âm' }: SpeakButtonProps) {
  const { supported, speak, speaking } = useSpeech();

  const title = supported ? label : 'Trình duyệt của bạn không hỗ trợ đọc phát âm';

  return (
    <Tooltip title={title}>
      <span>
        <IconButton
          size="small"
          disabled={!supported}
          aria-label={label}
          onClick={(e) => { e.stopPropagation(); speak(text); }}
          sx={{ color: speaking ? 'primary.main' : 'text.secondary' }}
        >
          <SpeakerIcon size={size} />
        </IconButton>
      </span>
    </Tooltip>
  );
}

export default SpeakButton;
