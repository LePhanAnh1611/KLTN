import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Typography from '@mui/material/Typography';
import type { ReactNode } from 'react';

import type { AccentColor } from '../theme/accents';
import { INK, MUTED, PRIMARY } from '../theme/theme';

interface StatCardProps {
  icon?: ReactNode;
  value: ReactNode;
  label: string;
  accent?: AccentColor;
}

/** Thẻ chỉ số: icon trong vòng tròn màu + số lớn + nhãn (Cấp độ / Chuỗi / XP…).
 *
 * Bug #3 (responsive): dưới `sm` xếp 2 thẻ/hàng (cha luôn dùng `gap: 2`), icon
 * nằm trên số cho gọn. */
function StatCard({ icon, value, label, accent }: StatCardProps) {
  return (
    <Card sx={{
      // Số không bao giờ bị ngắt giữa chừng ("138/42|0"): ô nào chật thì cả ô xuống hàng.
      flex: { xs: '1 1 calc(50% - 8px)', sm: '1 1 200px' },
      minWidth: { xs: 0, sm: 200 },
      p: { xs: 1.75, sm: 2.25 },
      bgcolor: accent?.bg ?? 'background.paper',
      boxShadow: 'none',
    }}>
      <Box sx={{
        display: 'flex',
        flexDirection: { xs: 'column', sm: 'row' },
        alignItems: { xs: 'flex-start', sm: 'center' },
        gap: { xs: 1, sm: 1.75 },
      }}>
        {icon && (
          <Box
            sx={{
              display: 'grid',
              placeItems: 'center',
              width: { xs: 40, sm: 50 },
              height: { xs: 40, sm: 50 },
              borderRadius: '50%',
              flexShrink: 0,
              bgcolor: accent?.solid ?? PRIMARY,
              color: '#FFFFFF',
            }}
          >
            {icon}
          </Box>
        )}
        <Box sx={{ minWidth: 0 }}>
          <Typography sx={{ fontWeight: 900, lineHeight: 1, color: INK,
                            fontSize: { xs: '1.5rem', sm: '1.75rem' }, whiteSpace: 'nowrap' }}>
            {value}
          </Typography>
          <Typography variant="body2" sx={{ color: MUTED, fontWeight: 800, lineHeight: 1.3, mt: 0.25 }}>
            {label}
          </Typography>
        </Box>
      </Box>
    </Card>
  );
}

export default StatCard;
