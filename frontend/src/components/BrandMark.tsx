import Box from '@mui/material/Box';

import { PRIMARY } from '../theme/theme';

/**
 * Nhận diện Learning Hub — MỘT nguồn duy nhất cho mọi nơi hiển thị logo
 * (thanh bên, trang đăng nhập; favicon vẽ tay cùng hình ở `public/favicon.svg`).
 *
 * Phương án 3 "Sách mở" (chủ dự án chọn 2026-10-28, thay "Mọt sách" cho hợp bảng
 * màu navy): hai nửa hình tròn chạm nhau ở gáy là quyển sách mở, chấm tròn phía
 * trên là người học. Một màu, hình học, chữ in hoa hai dòng - tinh thần giống
 * logo British Council nhưng là hình riêng.
 */

export function BrandGlyph({
  size = 40,
  /** Bản cho nền tối: biểu tượng trắng. */
  inverted = false,
}: {
  size?: number;
  inverted?: boolean;
}) {
  return (
    <Box
      component="svg"
      aria-hidden
      viewBox="0 0 64 64"
      sx={{ width: size, height: size, flexShrink: 0, display: 'block', fill: inverted ? '#FFFFFF' : PRIMARY }}
    >
      <path d="M2 46 A15 15 0 0 1 31 46 V52 H2 Z" />
      <path d="M33 46 A15 15 0 0 1 62 46 V52 H33 Z" />
      <circle cx="32" cy="14" r="8" />
    </Box>
  );
}

type BrandMarkProps = {
  /** Cỡ glyph (px). */
  size?: number;
  /** Cỡ chữ wordmark (px). */
  fontSize?: number;
  /** Màu chữ wordmark. */
  color?: string;
  /** Bản cho nền tối. */
  inverted?: boolean;
};

export default function BrandMark({
  size = 40,
  fontSize = 19,
  color = PRIMARY,
  inverted = false,
}: BrandMarkProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, minWidth: 0 }}>
      <BrandGlyph size={size} inverted={inverted} />
      <Box
        component="span"
        sx={{
          fontFamily: '"Lexend", "Nunito", sans-serif',
          fontWeight: 600,
          fontSize,
          lineHeight: 1,
          letterSpacing: '0.02em',
          textTransform: 'uppercase',
          whiteSpace: 'nowrap',
          color: inverted ? '#FFFFFF' : color,
        }}
      >
        Learning
        <br />
        Hub
      </Box>
    </Box>
  );
}
