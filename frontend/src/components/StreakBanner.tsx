import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { KidBin } from './FlatScene';
import { FlameIcon } from './icons';
import { FLAT, WARM_TEXT } from '../theme/theme';

interface StreakBannerProps {
  /** Chuỗi ngày SAU phiên vừa xong. */
  streakCount: number;
  /** Chỉ hiện khi phiên này là phiên đầu tiên trong ngày. */
  extended: boolean;
}

/**
 * Báo "chuỗi +1" sau phiên đầu tiên trong ngày (UC-47).
 *
 * Chỉ hiện đúng một lần mỗi ngày, ở phiên đầu tiên. Hiện ở mọi phiên thì con số
 * mất ý nghĩa và người học hết tin vào nó — mà không hiện gì thì thành tích lớn
 * nhất trong ngày trôi qua lặng lẽ.
 *
 * Nền cam nhạt, không phải màu chủ đạo: chuỗi là thứ cần bật lên khỏi nền.
 */
function StreakBanner({ streakCount, extended }: StreakBannerProps) {
  if (!extended) return null;

  const milestone = streakCount > 0 && streakCount % 7 === 0;

  return (
    <Box
      role="status"
      sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 1.5, pr: 2, mb: 2.5, borderRadius: '20px', bgcolor: '#FDE6D3' }}
    >
      <Box sx={{ width: 64, height: 64, borderRadius: '50%', bgcolor: '#FFFFFF', overflow: 'hidden', flexShrink: 0, display: 'grid', placeItems: 'end center' }}>
        <KidBin bust size={64} mood="cheer" />
      </Box>
      <Box sx={{ minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, color: FLAT.orange }}>
          <FlameIcon size={22} filled />
          <Typography variant="h6" sx={{ color: WARM_TEXT, fontWeight: 900 }}>
            Chuỗi {streakCount} ngày!
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          {milestone
            ? `Tròn ${streakCount} ngày liên tiếp - mai học tiếp để giữ nhé.`
            : 'Đây là buổi học đầu tiên hôm nay. Chuỗi vừa cộng thêm 1.'}
        </Typography>
      </Box>
    </Box>
  );
}

export default StreakBanner;
