import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';

import { ACCENT_FONT, INK, hardShadow, LINE } from '../theme/theme';
import { EmptyScene } from './RetroDecor';

/** Khung thẻ dùng chung của Trang chủ.
 *
 * Tách khỏi `pages/Dashboard.tsx` để các thẻ cộng đồng dùng lại đúng một ngôn
 * ngữ hình khối. Chép lại kiểu dáng ở file thứ hai là cách chắc chắn nhất để
 * hai nửa trang trôi khỏi nhau sau vài lần chỉnh.
 */

/** Thẻ kem viền mực, bóng đổ cứng (Retro Pixel Pop). */
export function Panel({
  children,
  sx,
}: {
  children: React.ReactNode;
  sx?: Record<string, unknown>;
}) {
  return (
    <Box
      sx={{
        p: { xs: 2, sm: 2.25 },
        borderRadius: '16px',
        bgcolor: 'background.paper',
        border: `1.5px solid ${LINE}`,
        boxShadow: hardShadow(4),
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}

export function PanelHead({
  icon,
  title,
  hint,
  tint,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  hint?: string;
  tint: string;
  action?: React.ReactNode;
}) {
  // Bug #3: bản cũ để icon · (tiêu đề + mô tả) · nút trên CÙNG một hàng — màn
  // 375px chỉ còn ~150px cho chữ nên "Bảng xếp hạng tuần" vỡ 2 dòng và mô tả bị ép
  // thành cột hẹp 4–5 dòng. Giờ hàng trên chỉ có icon · tiêu đề · nút; mô tả xuống
  // hàng riêng, trên điện thoại chạy hết chiều ngang thẻ.
  return (
    <Box sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
        <Box
          aria-hidden
          sx={{
            width: 40,
            height: 40,
            borderRadius: '10px',
            flexShrink: 0,
            display: 'grid',
            placeItems: 'center',
            bgcolor: alpha(tint, 0.85),
            border: `1.5px solid ${LINE}`,
            color: INK,
          }}
        >
          {icon}
        </Box>
        <Typography
          sx={{
            flexGrow: 1,
            minWidth: 0,
            fontFamily: ACCENT_FONT,
            fontWeight: 800,
            fontSize: { xs: 17, sm: 19 },
            letterSpacing: '-0.02em',
            lineHeight: 1.3,
          }}
        >
          {title}
        </Typography>
        {action}
      </Box>
      {hint && (
        <Typography sx={{ fontSize: 14.5, color: 'text.secondary', mt: 0.75, lineHeight: 1.5,
                          pl: { xs: 0, sm: '50px' } }}>
          {hint}
        </Typography>
      )}
    </Box>
  );
}

/** Trạng thái rỗng của một thẻ: nói RÕ vì sao trống và làm gì để hết trống.
 *
 * Để trắng thì người học tưởng hỏng; viết "Không có dữ liệu" thì đúng nhưng vô
 * dụng. Mỗi trạng thái rỗng ở đây đều kèm một lối đi tiếp.
 */
export function PanelEmpty({
  message,
  action,
}: {
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <Box sx={{ py: 1 }}>
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1.5 }}>
        <EmptyScene seed={message} size={72} />
      </Box>
      <Typography sx={{ fontSize: 14, color: 'text.secondary', lineHeight: 1.6, mb: action ? 1.75 : 0 }}>
        {message}
      </Typography>
      {action}
    </Box>
  );
}

/** Khung chờ giữ đúng chiều cao của danh sách thật để trang không giật. */
export function PanelSkeleton({ rows = 3, height = 52 }: { rows?: number; height?: number }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      {Array.from({ length: rows }, (_, i) => (
        <Box
          key={i}
          sx={{
            height,
            borderRadius: '10px',
            border: '2px dashed',
            borderColor: 'divider',
            animation: 'panelPulse 1.4s ease-in-out infinite',
            animationDelay: `${i * 0.12}s`,
            '@keyframes panelPulse': {
              '0%, 100%': { opacity: 0.45 },
              '50%': { opacity: 0.85 },
            },
            '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
          }}
        />
      ))}
    </Box>
  );
}
