import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Typography from '@mui/material/Typography';
import type { SxProps, Theme } from '@mui/material/styles';

import { sectionAccent } from '../theme/accents';

interface SectionCardProps {
  title?: ReactNode;
  /** Dòng mô tả nhỏ dưới tiêu đề. */
  caption?: ReactNode;
  /** Icon nhỏ bên trái tiêu đề. */
  icon?: ReactNode;
  /** Liên kết / nút phụ canh phải hàng tiêu đề. */
  action?: ReactNode;
  children: ReactNode;
  sx?: SxProps<Theme>;
}

/** Giữ export cho chỗ gọi cũ — bản flat không còn nút cửa sổ trang trí. */
export function WindowControls() {
  return null;
}

/**
 * Khối nội dung dùng chung (bản flat 2026-10-26): thẻ trắng bo lớn, tiêu đề
 * đậm kèm icon trong vòng tròn màu của khu vực — không còn thanh tiêu đề
 * kiểu cửa sổ. Cùng padding, cùng cỡ chữ ở mọi trang.
 */
function SectionCard({ title, caption, icon, action, children, sx }: SectionCardProps) {
  const tone = sectionAccent(useLocation().pathname);
  const hasHead = Boolean(title || action);

  return (
    <Card sx={{ p: { xs: 2.25, sm: 2.75 }, ...sx }}>
      {hasHead && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, mb: caption ? 0.5 : 2 }}>
          {icon && (
            <Box
              sx={{
                width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
                display: 'grid', placeItems: 'center',
                bgcolor: tone.solid, color: '#FFFFFF',
              }}
            >
              {icon}
            </Box>
          )}
          <Typography variant="h6" sx={{ flexGrow: 1, minWidth: 0, fontSize: 17, fontWeight: 900, lineHeight: 1.5, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', textTransform: 'uppercase', letterSpacing: '0.03em' }}>
            {title}
          </Typography>
          {action}
        </Box>
      )}
      {caption && (
        <Typography variant="body2" color="text.secondary" sx={{ display: 'block', mb: 2, pl: icon ? 6 : 0 }}>
          {caption}
        </Typography>
      )}
      {children}
    </Card>
  );
}

export default SectionCard;
