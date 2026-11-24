import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

import { INK, SECONDARY, SOFT_SHADOW } from '../theme/theme';

/* ═══════════════════════════════════════════════════════════════════════════
 * HỘP "MÁY BÁN NƯỚC" — khối chữ ký của giao diện (2026-10-20, theo ảnh mẫu chủ
 * dự án gửi): mặt trước màu đặc viền đen, MẶT HÔNG 3D bên phải có chữ chạy dọc,
 * bên trong là "màn hình" màu bo góc có một khấc ở góc dưới-phải để đặt nút,
 * kèm hàng nút tròn.
 *
 * Mặt hông vẽ bằng clip-path theo px nên độ nghiêng không đổi khi hộp cao/thấp.
 * ═══════════════════════════════════════════════════════════════════════════ */

// Bản flat (2026-10-26): hộp là thẻ phẳng bo lớn + bóng mờ, không viền.
const BORDER = 'none';

interface VendingBoxProps {
  /** Màu mặt trước. */
  face: string;
  /** Màu mặt hông (mặc định tối hơn mặt trước một chút nhờ lớp phủ). */
  side?: string;
  /** Chữ chạy dọc trên mặt hông. */
  sideLabel?: ReactNode;
  /** Độ sâu mặt hông (px). Đặt 0 để bỏ mặt hông (VD màn hẹp). */
  depth?: number | { xs?: number; sm?: number; md?: number };
  radius?: number;
  children: ReactNode;
  sx?: SxProps<Theme>;
  /** sx cho mặt trước (padding…). */
  faceSx?: SxProps<Theme>;
}

// Flat design (2026-10-24): không còn mặt hông 3D — mọi hộp phẳng, `depth` bị bỏ qua.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
function resolveDepth(_depth: VendingBoxProps['depth']) {
  return { xs: 0 } as { xs: number; sm?: number; md?: number };
}

export function VendingBox({ face, side, sideLabel, depth, radius = 22, children, sx, faceSx }: VendingBoxProps) {
  const d = resolveDepth(depth);
  const px = (v: number | undefined) => (v == null ? undefined : `${v}px`);
  const mr = { xs: px(d.xs), sm: px(d.sm), md: px(d.md) };
  const sideDisplay = {
    xs: d.xs ? 'block' : 'none',
    ...(d.sm != null && { sm: d.sm ? 'block' : 'none' }),
    ...(d.md != null && { md: d.md ? 'block' : 'none' }),
  };
  const sideWidth = {
    xs: px((d.xs ?? 0) + radius),
    ...(d.sm != null && { sm: px(d.sm + radius) }),
    ...(d.md != null && { md: px(d.md + radius) }),
  };

  return (
    <Box sx={{ position: 'relative', mr, ...sx }}>
      {/* Mặt hông — nằm SAU mặt trước, mép trái lùi vào dưới góc bo */}
      <Box
        aria-hidden
        sx={{
          display: sideDisplay,
          position: 'absolute',
          top: 0,
          bottom: 0,
          right: { xs: px(-(d.xs ?? 0)), sm: d.sm != null ? px(-d.sm) : undefined, md: d.md != null ? px(-d.md) : undefined },
          width: sideWidth,
        }}
      >
        {/* Vẽ bằng clip-path theo PX: độ nghiêng mép trên/dưới cố định 20px dù hộp
            cao bao nhiêu (bản SVG co giãn theo % làm hộp cao bị cong như cánh).
            Lớp ngoài màu mực = viền, lớp trong lùi 2px = mặt màu. */}
        <Box sx={{ position: 'absolute', inset: 0, bgcolor: INK,
                   clipPath: 'polygon(0 6px, 100% 26px, 100% calc(100% - 26px), 0 calc(100% - 6px))' }} />
        <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: '2px', bgcolor: side ?? face,
                   clipPath: 'polygon(0 8.5px, 100% 28.5px, 100% calc(100% - 28.5px), 0 calc(100% - 8.5px))' }} />
        {/* lớp tối nhẹ để mặt hông đọc ra là mặt khuất */}
        <Box sx={{ position: 'absolute', top: 0, bottom: 0, left: 0, right: '2px', bgcolor: 'rgba(0,0,0,0.10)',
                   clipPath: 'polygon(0 8.5px, 100% 28.5px, 100% calc(100% - 28.5px), 0 calc(100% - 8.5px))' }} />
        {sideLabel && (
          <Box
            sx={{
              position: 'absolute',
              top: '28px',
              bottom: '28px',
              left: radius,
              right: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              writingMode: 'vertical-rl',
              fontWeight: 900,
              fontSize: 16,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: INK,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
            }}
          >
            {sideLabel}
          </Box>
        )}
      </Box>

      {/* Mặt trước */}
      <Box
        sx={{
          position: 'relative',
          zIndex: 1,
          bgcolor: face,
          border: BORDER,
          boxShadow: SOFT_SHADOW,
          borderRadius: `${Math.max(radius, 20)}px`,
          ...faceSx,
        }}
      >
        {children}
      </Box>
    </Box>
  );
}

/**
 * "Màn hình" bên trong hộp: khối màu bo góc, góc dưới-phải bị khấc một ô (cùng
 * màu mặt hộp) để đặt nút nhỏ — đúng kiểu máy bán nước trong ảnh mẫu.
 */
export function VendingScreen({
  color,
  faceColor,
  notch,
  children,
  sx,
}: {
  color: string;
  /** Màu mặt hộp — để vẽ khấc. */
  faceColor: string;
  /** Nội dung trong khấc (thường là một nút vuông). Bỏ trống = không khấc. */
  notch?: ReactNode;
  children: ReactNode;
  sx?: SxProps<Theme>;
}) {
  return (
    <Box sx={{ position: 'relative', bgcolor: color, borderRadius: '18px', overflow: 'hidden', ...sx }}>
      {children}
      {notch && (
        <Box
          sx={{
            position: 'absolute',
            right: 0,
            bottom: 0,
            p: '8px 0 0 8px',
            bgcolor: faceColor,
            borderTopLeftRadius: '18px',
            zIndex: 2,
          }}
        >
          {notch}
        </Box>
      )}
    </Box>
  );
}

/** Hàng nút tròn trang trí (cam · chanh · đen như ảnh mẫu). */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function VendingDots({ colors = [SECONDARY, '#D6F45B', INK], size = 22 }: { colors?: string[]; size?: number }) {
  // Bản flat: bỏ hàng nút trang trí của hộp máy bán nước.
  if (colors.length) return null;
  return (
    <Box aria-hidden sx={{ display: 'flex', gap: 1 }}>
      {colors.map((c, i) => (
        <Box key={i} sx={{ width: size, height: size, borderRadius: '50%', bgcolor: c, border: BORDER }} />
      ))}
    </Box>
  );
}

/** Nút vuông nhỏ trắng viền đen (▼, ♥, loa…). */
export function VendingKey({ children, onClick, label }: { children: ReactNode; onClick?: () => void; label?: string }) {
  return (
    <Box
      component={onClick ? 'button' : 'span'}
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      aria-label={label}
      sx={{
        width: 40,
        height: 40,
        display: 'grid',
        placeItems: 'center',
        bgcolor: '#FFFFFF',
        border: BORDER,
        borderRadius: '50%',
        boxShadow: SOFT_SHADOW,
        color: INK,
        fontSize: 15,
        p: 0,
        cursor: onClick ? 'pointer' : 'default',
        '&:active': onClick ? { transform: 'none', boxShadow: 'none' } : undefined,
      }}
    >
      {children}
    </Box>
  );
}
