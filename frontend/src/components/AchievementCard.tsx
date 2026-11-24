import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { LockArt, TrophyArt } from './FlatArt';
import { CARD_SX, GO_GREEN_TEXT, INK, MUTED } from '../theme/theme';

interface AchievementCardProps {
  name: string;
  description: string;
  unlocked: boolean;
}

/**
 * Thẻ huy hiệu dạng "huy chương sưu tập" (bản flat): đã mở = cúp vàng trong
 * vòng tròn ngọc trên nền vàng nhạt; chưa mở = ổ khoá xám trên nền be ĐẶC
 * (không làm mờ bằng opacity — thẻ trong suốt trông như lỗi hiển thị).
 */
function AchievementCard({ name, description, unlocked }: AchievementCardProps) {
  return (
    <Box sx={{ ...CARD_SX, width: 220, p: 1.25, color: INK }}>
      <Box sx={{ height: 112, mb: 1.25, display: 'grid', placeItems: 'center', bgcolor: unlocked ? '#FDF0CC' : '#F3EAE1', borderRadius: '16px' }}>
        {unlocked ? <TrophyArt size={84} /> : <LockArt size={72} />}
      </Box>
      <Box sx={{ px: 0.75, pb: 0.5 }}>
        <Typography sx={{ fontWeight: 900, fontSize: 16 }}>{name}</Typography>
        <Typography sx={{ fontSize: 14, fontWeight: 600, color: MUTED, minHeight: 40, mb: 1 }}>{description}</Typography>
        <Box
          component="span"
          sx={{
            px: 1.25,
            py: 0.25,
            borderRadius: 999,
            bgcolor: unlocked ? '#DDF2E1' : '#F3EAE1',
            color: unlocked ? GO_GREEN_TEXT : MUTED,
            fontWeight: 900,
            fontSize: 12.5,
          }}
        >
          {unlocked ? '★ Đã mở khoá' : 'Chưa mở'}
        </Box>
      </Box>
    </Box>
  );
}

export default AchievementCard;
