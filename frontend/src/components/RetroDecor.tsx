import { useId } from 'react';
import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

import { INK, PIXEL_FONT } from '../theme/theme';

// Màu tranh minh hoạ CỐ ĐỊNH, tươi — không đi theo bảng màu giao diện (khung đã
// dịu sang Kem & Vàng; nhân vật vẫn cần má hồng, tia nắng cam để có sức sống).
const RETRO_PINK = '#F59BC0';
const RETRO_YELLOW = '#FFE14D';
const SECONDARY = '#FF7652';

/* ═══════════════════════════════════════════════════════════════════════════
 * ĐỒ TRANG TRÍ RETRO — nhân vật và sticker vẽ tay bằng SVG (tự vẽ, không lấy
 * hình của ai). Phong cách: nét mực dày, màu phẳng, mặt có má hồng — lấy cảm
 * hứng từ ảnh mẫu thẻ sưu tập / neo-brutalism chủ dự án gửi (2026-10-20).
 *
 * Tất cả `aria-hidden`: chỉ để trang trí, không mang thông tin. Chuyển động
 * nhún nhảy tắt khi người dùng bật giảm chuyển động.
 * ═══════════════════════════════════════════════════════════════════════════ */

const STROKE = { stroke: INK, strokeWidth: 3.5, strokeLinejoin: 'round', strokeLinecap: 'round' } as const;

type DecorProps = { size?: number; sx?: SxProps<Theme> };

function Svg({ size = 80, viewBox = '0 0 100 100', sx, children, bob = false }: DecorProps & {
  viewBox?: string;
  children: ReactNode;
  bob?: boolean;
}) {
  return (
    <Box
      component="svg"
      aria-hidden
      viewBox={viewBox}
      sx={{
        width: size,
        height: size,
        display: 'block',
        flexShrink: 0,
        overflow: 'visible',
        ...(bob && {
          animation: 'decorBob 2.6s ease-in-out infinite',
          '@keyframes decorBob': {
            '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
            '50%': { transform: 'translateY(-5px) rotate(-2deg)' },
          },
          '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
        }),
        ...sx,
      }}
    >
      {children}
    </Box>
  );
}

/** Mặt cười dùng chung: hai mắt tròn có đốm sáng, má hồng, miệng. */
function Face({ cx, cy, scale = 1, mood = 'happy' }: { cx: number; cy: number; scale?: number; mood?: 'happy' | 'wow' | 'wink' }) {
  const s = scale;
  return (
    <g transform={`translate(${cx} ${cy}) scale(${s})`}>
      <ellipse cx={-9} cy={4} rx={4.5} ry={2.6} fill={RETRO_PINK} opacity={0.9} />
      <ellipse cx={9} cy={4} rx={4.5} ry={2.6} fill={RETRO_PINK} opacity={0.9} />
      {mood === 'wink' ? (
        <path d="M-9 -4 q3 -3 6 0" fill="none" {...STROKE} strokeWidth={2.6} />
      ) : (
        <>
          <ellipse cx={-6} cy={-4} rx={2.6} ry={3.4} fill={INK} />
          <circle cx={-5.2} cy={-5.2} r={0.9} fill="#fff" />
        </>
      )}
      <ellipse cx={6} cy={-4} rx={2.6} ry={3.4} fill={INK} />
      <circle cx={6.8} cy={-5.2} r={0.9} fill="#fff" />
      {mood === 'wow' ? (
        <ellipse cx={0} cy={5} rx={2.6} ry={3.2} fill={INK} />
      ) : (
        <path d="M-4 3 q4 5 8 0" fill="#E0484E" stroke={INK} strokeWidth={2.2} strokeLinejoin="round" />
      )}
    </g>
  );
}

/* ─────────────────────────────── NHÂN VẬT ─────────────────────────────── */

/** Ông Mặt Trời — nhân vật chính, xuất hiện ở hero. */
export function SunnyCharacter({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  const rays = Array.from({ length: 10 }, (_, i) => i * 36);
  return (
    <Svg size={size} sx={sx} bob={bob}>
      {rays.map((deg) => (
        <path key={deg} d="M50 4 L56 18 L44 18 Z" fill={SECONDARY} {...STROKE} strokeWidth={3}
          transform={`rotate(${deg} 50 50)`} />
      ))}
      <circle cx={50} cy={50} r={30} fill={RETRO_YELLOW} {...STROKE} />
      <Face cx={50} cy={52} scale={1.25} />
    </Svg>
  );
}

/** Bạn Sách — đứng, vẫy tay. */
export function BookCharacter({ size, sx, bob, color = '#5B8DEF' }: DecorProps & { bob?: boolean; color?: string }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      {/* chân + giày */}
      <path d="M40 84 v8 M60 84 v8" {...STROKE} fill="none" />
      <ellipse cx={37} cy={94} rx={7} ry={4} fill="#E0484E" {...STROKE} strokeWidth={3} />
      <ellipse cx={63} cy={94} rx={7} ry={4} fill="#E0484E" {...STROKE} strokeWidth={3} />
      {/* tay */}
      <path d="M26 50 q-12 -6 -14 -18" fill="none" {...STROKE} />
      <path d="M74 52 q10 6 12 16" fill="none" {...STROKE} />
      {/* thân sách */}
      <rect x={24} y={14} width={52} height={72} rx={6} fill={color} {...STROKE} />
      <rect x={66} y={18} width={7} height={64} rx={2} fill="#FFFFFF" {...STROKE} strokeWidth={2.5} />
      <rect x={32} y={22} width={28} height={9} rx={2} fill="#FFFFFF" {...STROKE} strokeWidth={2.5} />
      <Face cx={46} cy={54} scale={1.15} mood="wink" />
    </Svg>
  );
}

/** Hoa Cúc — đầu hoa có mặt. */
export function DaisyCharacter({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  const petals = Array.from({ length: 8 }, (_, i) => i * 45);
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <path d="M50 62 q-4 18 2 34" fill="none" stroke="#2B9152" strokeWidth={5} strokeLinecap="round" />
      <path d="M51 82 q12 -10 22 -6 q-8 12 -22 6 Z" fill="#3DB86A" {...STROKE} strokeWidth={3} />
      {petals.map((deg) => (
        <ellipse key={deg} cx={50} cy={20} rx={10} ry={15} fill="#FFFFFF" {...STROKE} strokeWidth={3}
          transform={`rotate(${deg} 50 42)`} />
      ))}
      <circle cx={50} cy={42} r={17} fill={RETRO_YELLOW} {...STROKE} />
      <Face cx={50} cy={44} scale={0.85} />
    </Svg>
  );
}

/** Bóng Đèn — "à, nhớ ra rồi!" */
export function BulbCharacter({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <path d="M14 22 l8 6 M86 22 l-8 6 M50 2 v8 M8 48 h9 M92 48 h-9" {...STROKE} fill="none" />
      <path d="M50 12 C28 12 20 30 24 44 C27 54 36 58 37 68 H63 C64 58 73 54 76 44 C80 30 72 12 50 12 Z"
        fill="#FFF3A6" {...STROKE} />
      <rect x={36} y={68} width={28} height={8} rx={2} fill="#C9C3D9" {...STROKE} strokeWidth={3} />
      <rect x={38} y={76} width={24} height={8} rx={2} fill="#C9C3D9" {...STROKE} strokeWidth={3} />
      <path d="M44 84 h12 l-3 6 h-6 Z" fill={INK} />
      <Face cx={50} cy={40} scale={1.05} mood="wow" />
    </Svg>
  );
}

/** Máy tính CRT có mặt — dùng ở màn đăng nhập và thông báo. */
export function RoboCharacter({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <rect x={14} y={10} width={72} height={56} rx={8} fill="#EFE6CF" {...STROKE} />
      <rect x={22} y={18} width={56} height={38} rx={5} fill="#22A699" {...STROKE} strokeWidth={3} />
      {/* mắt pixel */}
      <rect x={36} y={28} width={6} height={8} fill="#FFFFFF" />
      <rect x={58} y={28} width={6} height={8} fill="#FFFFFF" />
      <path d="M40 44 h20 v3 h-20 z" fill="#FFFFFF" />
      <rect x={30} y={40} width={5} height={3} fill={RETRO_PINK} />
      <rect x={65} y={40} width={5} height={3} fill={RETRO_PINK} />
      <circle cx={74} cy={61} r={2} fill="#3DB86A" />
      <path d="M40 66 v8 M60 66 v8" {...STROKE} fill="none" />
      <rect x={18} y={74} width={64} height={14} rx={4} fill="#EFE6CF" {...STROKE} />
      <path d="M26 81 h48" {...STROKE} strokeWidth={2.5} strokeDasharray="4 3" fill="none" />
    </Svg>
  );
}

export const CHARACTERS = [SunnyCharacter, BookCharacter, DaisyCharacter, BulbCharacter, RoboCharacter] as const;

/** Chọn nhân vật ổn định theo một số (VD id từ) — mỗi từ luôn có cùng một bạn đồng hành. */
export function characterFor(seed: number) {
  return CHARACTERS[Math.abs(Math.trunc(seed)) % CHARACTERS.length];
}

/* ─────────────────────────────── STICKER ─────────────────────────────── */

/** Lấp lánh 4 cánh. */
export function Sparkle({ size = 24, color = RETRO_YELLOW, sx }: DecorProps & { color?: string }) {
  return (
    <Svg size={size} sx={sx}>
      <path d="M50 4 C54 38 62 46 96 50 C62 54 54 62 50 96 C46 62 38 54 4 50 C38 46 46 38 50 4 Z"
        fill={color} {...STROKE} strokeWidth={6} />
    </Svg>
  );
}

/** Đám mây trắng viền mực. */
export function Cloud({ size = 90, sx }: DecorProps) {
  return (
    <Svg size={size} viewBox="0 0 120 64" sx={sx}>
      <path d="M22 56 C6 56 4 36 20 34 C18 18 40 12 48 24 C54 6 84 6 88 26 C104 22 116 36 106 50 C104 54 100 56 96 56 Z"
        fill="#FFFFFF" {...STROKE} />
    </Svg>
  );
}

/** Ngôi sao nổ có chữ — "LET'S GO!". */
export function Starburst({ text, size = 92, color = '#5B8DEF', textColor = '#FFFFFF', sx }: DecorProps & {
  text: string;
  color?: string;
  textColor?: string;
}) {
  const pts = Array.from({ length: 24 }, (_, i) => {
    const r = i % 2 === 0 ? 48 : 38;
    const a = (Math.PI * 2 * i) / 24 - Math.PI / 2;
    return `${50 + r * Math.cos(a)},${50 + r * Math.sin(a)}`;
  }).join(' ');
  return (
    <Svg size={size} sx={sx}>
      <polygon points={pts} fill={color} {...STROKE} />
      <text x={50} y={50} textAnchor="middle" dominantBaseline="central"
        style={{ font: `${text.length > 7 ? 19 : 25}px ${PIXEL_FONT}`, fill: textColor }}>
        {text}
      </text>
    </Svg>
  );
}

/** Bong bóng thoại hình bầu dục — "OMG!", "CHUẨN!". */
export function SpeechSticker({ text, size = 84, color = '#FFFFFF', sx }: DecorProps & { text: string; color?: string }) {
  return (
    <Svg size={size} viewBox="0 0 100 70" sx={sx}>
      <path d="M50 6 C78 6 94 16 94 32 C94 48 78 58 50 58 C44 58 38 57 33 56 L18 66 L22 52 C12 47 6 40 6 32 C6 16 22 6 50 6 Z"
        fill={color} {...STROKE} />
      <text x={50} y={32} textAnchor="middle" dominantBaseline="central"
        style={{ font: `24px ${PIXEL_FONT}`, fill: INK }}>
        {text}
      </text>
    </Svg>
  );
}

/** Huy hiệu tròn có chữ chạy vòng quanh, giữa là hoa cúc — "HỌC MỖI NGÀY". */
export function RoundBadge({ text, size = 110, color = '#7FD8CC', spin = true, sx }: DecorProps & {
  text: string;
  color?: string;
  spin?: boolean;
}) {
  const id = useId().replace(/:/g, '');
  const petals = Array.from({ length: 8 }, (_, i) => i * 45);
  return (
    <Svg size={size} sx={sx}>
      <circle cx={50} cy={50} r={46} fill={color} {...STROKE} />
      <defs>
        <path id={`rb${id}`} d="M50 50 m-34 0 a34 34 0 1 1 68 0 a34 34 0 1 1 -68 0" />
      </defs>
      <g style={spin ? { transformOrigin: '50px 50px', animation: 'badgeSpin 18s linear infinite' } : undefined}>
        <text style={{ font: `15px ${PIXEL_FONT}`, fill: INK, letterSpacing: '0.12em' }}>
          <textPath href={`#rb${id}`}>{text}</textPath>
        </text>
      </g>
      <style>{'@keyframes badgeSpin{to{transform:rotate(360deg)}}@media (prefers-reduced-motion:reduce){g{animation:none!important}}'}</style>
      {petals.map((deg) => (
        <ellipse key={deg} cx={50} cy={36} rx={5} ry={9} fill="#FFFFFF" stroke={INK} strokeWidth={2.2}
          transform={`rotate(${deg} 50 50)`} />
      ))}
      <circle cx={50} cy={50} r={9} fill={RETRO_YELLOW} stroke={INK} strokeWidth={2.5} />
      <circle cx={47} cy={49} r={1.3} fill={INK} />
      <circle cx={53} cy={49} r={1.3} fill={INK} />
      <path d="M47 53 q3 3 6 0" fill="none" stroke={INK} strokeWidth={1.6} strokeLinecap="round" />
    </Svg>
  );
}

/** Dải nền caro (sàn nhà kiểu ảnh mẫu) — đặt ở chân một khối lớn. */
export function checkerSx(a = '#FFFFFF', b = '#F9D3E3', cell = 18) {
  return {
    backgroundColor: a,
    backgroundImage: `linear-gradient(45deg, ${b} 25%, transparent 25%, transparent 75%, ${b} 75%), linear-gradient(45deg, ${b} 25%, transparent 25%, transparent 75%, ${b} 75%)`,
    backgroundSize: `${cell * 2}px ${cell * 2}px`,
    backgroundPosition: `0 0, ${cell}px ${cell}px`,
  } as const;
}

/* ─────────────────────────────── ĐỒ VẬT ─────────────────────────────── */

/** Thư mục vàng có tờ giấy thò ra — đúng hình trong ảnh mẫu máy bán nước. */
export function FolderObject({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <path d="M10 26 H40 L46 34 H90 V84 H10 Z" fill="#F2C200" {...STROKE} />
      <rect x={22} y={24} width={58} height={34} fill="#FFFFFF" {...STROKE} strokeWidth={3} />
      <path d="M30 34 H70 M30 42 H62" {...STROKE} strokeWidth={2.5} fill="none" />
      <path d="M8 44 H92 L88 88 H12 Z" fill={RETRO_YELLOW} {...STROKE} />
    </Svg>
  );
}

/** Đồng hồ báo thức đỏ — "đến giờ ôn bài". */
export function ClockObject({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <path d="M22 26 a14 14 0 0 1 20 -10 Z" fill="#FF7652" {...STROKE} strokeWidth={3} />
      <path d="M78 26 a14 14 0 0 0 -20 -10 Z" fill="#FF7652" {...STROKE} strokeWidth={3} />
      <path d="M30 84 l-6 10 M70 84 l6 10" {...STROKE} fill="none" />
      <circle cx={50} cy={55} r={34} fill="#FF4B4B" {...STROKE} />
      <circle cx={50} cy={55} r={25} fill="#FFFFFF" {...STROKE} strokeWidth={3} />
      <path d="M50 55 V38 M50 55 L62 61" {...STROKE} fill="none" />
      <circle cx={50} cy={55} r={2.5} fill={INK} />
      <path d="M50 33 v3 M50 74 v3 M28 55 h3 M69 55 h3" {...STROKE} strokeWidth={2.5} fill="none" />
    </Svg>
  );
}

/** Cốc trà chiều trên đĩa hồng, có hơi bốc lên. */
export function CupObject({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <path d="M38 8 q-6 8 0 14 q6 6 0 12 M54 6 q-6 8 0 14 q6 6 0 12" {...STROKE} strokeWidth={3} fill="none" />
      <ellipse cx={48} cy={86} rx={40} ry={9} fill={RETRO_PINK} {...STROKE} />
      <path d="M74 50 q16 0 14 14 q-2 12 -18 10" fill="none" {...STROKE} strokeWidth={6} />
      <path d="M74 50 q16 0 14 14 q-2 12 -18 10" fill="none" stroke="#5B8DEF" strokeWidth={2} strokeLinecap="round" />
      <path d="M18 40 H78 L72 82 Q70 88 64 88 H32 Q26 88 24 82 Z" fill="#5B8DEF" {...STROKE} />
      <ellipse cx={48} cy={40} rx={30} ry={7} fill="#7A3E1C" {...STROKE} strokeWidth={3} />
      <path d="M44 60 c-6 -6 -14 0 -6 8 l6 6 l6 -6 c8 -8 0 -14 -6 -8 Z" fill="#FF4B4B" stroke={INK} strokeWidth={2.5} strokeLinejoin="round" />
    </Svg>
  );
}

/** Cúp vàng — cho bảng xếp hạng & huy hiệu. */
export function TrophyObject({ size, sx, bob }: DecorProps & { bob?: boolean }) {
  return (
    <Svg size={size} sx={sx} bob={bob}>
      <path d="M26 22 H12 q0 22 20 24 M74 22 H88 q0 22 -20 24" fill="none" {...STROKE} strokeWidth={4} />
      <path d="M24 12 H76 V36 Q76 62 50 64 Q24 62 24 36 Z" fill={RETRO_YELLOW} {...STROKE} />
      <path d="M38 22 V40" stroke="#FFFFFF" strokeWidth={5} strokeLinecap="round" />
      <rect x={44} y={64} width={12} height={12} fill="#F2C200" {...STROKE} strokeWidth={3} />
      <rect x={30} y={76} width={40} height={14} rx={3} fill="#FF7652" {...STROKE} />
      <path d="M50 26 l3 6 l7 1 l-5 5 l1 7 l-6 -3 l-6 3 l1 -7 l-5 -5 l7 -1 Z" fill="#FFFFFF" stroke={INK} strokeWidth={2} strokeLinejoin="round" />
    </Svg>
  );
}

export const OBJECTS = [FolderObject, ClockObject, CupObject, TrophyObject] as const;

/** Một "cảnh nhỏ" cho ô trống: nhân vật + đồ vật + lấp lánh, chọn ổn định theo chuỗi. */
export function EmptyScene({ seed, size = 96 }: { seed: string; size?: number }) {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const Character = CHARACTERS[h % CHARACTERS.length];
  const Thing = OBJECTS[(h >>> 3) % OBJECTS.length];
  return (
    <Box aria-hidden sx={{ position: 'relative', display: 'inline-flex', alignItems: 'flex-end', gap: 0.5, pt: 1.5, px: 2 }}>
      <Sparkle size={18} sx={{ position: 'absolute', top: 0, left: 0 }} />
      <Character size={size} bob />
      <Thing size={size * 0.62} />
      <Sparkle size={13} color="#C77DFF" sx={{ position: 'absolute', top: 6, right: 0 }} />
    </Box>
  );
}
