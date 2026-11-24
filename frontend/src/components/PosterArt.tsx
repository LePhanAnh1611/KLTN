import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';
import type { ReactNode } from 'react';

import { INK, PIXEL_FONT } from '../theme/theme';
import { RoboCharacter, TrophyObject } from './RetroDecor';

/* ═══════════════════════════════════════════════════════════════════════════
 * TRANH POSTER — đồ vật & nhân vật cỡ lớn, nét dày, màu tươi (theo ảnh mẫu
 * "small objects in time" chủ dự án gửi 2026-10-20). Tự vẽ bằng SVG.
 *
 * Mỗi chức năng của app có một "biểu tượng" riêng để nhận ra ngay khi vào trang:
 *   Ôn tập → đồng hồ báo thức · Học từ mới → hũ "FUN COOL" · Bộ từ → hộp đồ hộp
 *   Trò chơi → máy nhắn tin · Sổ tay → cốc trà · Luyện nói → hai nhân vật đại
 *   diện Mona (nữ) & Hét (nam), lấy cảm hứng từ hai bức tranh đã thuộc phạm vi
 *   công cộng (Mona Lisa — da Vinci, The Scream — Munch).
 *
 * Tất cả chỉ để trang trí: `aria-hidden`.
 * ═══════════════════════════════════════════════════════════════════════════ */

const S = { stroke: INK, strokeWidth: 4, strokeLinejoin: 'round', strokeLinecap: 'round' } as const;

type ArtProps = { size?: number; sx?: SxProps<Theme>; bob?: boolean };

function Art({ size = 120, sx, bob, children }: ArtProps & { children: ReactNode }) {
  return (
    <Box
      component="svg"
      aria-hidden
      viewBox="0 0 120 120"
      sx={{
        width: size,
        height: size,
        display: 'block',
        flexShrink: 0,
        overflow: 'visible',
        ...(bob && {
          animation: 'artBob 3s ease-in-out infinite',
          '@keyframes artBob': {
            '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
            '50%': { transform: 'translateY(-6px) rotate(-2deg)' },
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

/** Đồng hồ báo thức đỏ vuông — "Ôn tập / đến giờ rồi". */
export function AlarmClockArt(p: ArtProps) {
  const ticks = Array.from({ length: 12 }, (_, i) => i * 30);
  return (
    <Art {...p}>
      <path d="M20 22 l-8 -8 M100 22 l8 -8 M14 50 h-8 M106 50 h8" {...S} fill="none" />
      <rect x={48} y={10} width={24} height={12} rx={4} fill="#FFE14D" {...S} />
      <path d="M28 104 l-4 10 M92 104 l4 10" {...S} fill="none" />
      <rect x={14} y={20} width={92} height={86} rx={26} fill="#E8332E" {...S} />
      <rect x={22} y={28} width={76} height={70} rx={20} fill="#FF5A4E" />
      <circle cx={60} cy={63} r={31} fill="#FFF4D6" {...S} />
      {ticks.map((d) => (
        <path key={d} d="M60 37 v5" stroke={INK} strokeWidth={3} strokeLinecap="round" transform={`rotate(${d} 60 63)`} />
      ))}
      <path d="M60 63 L60 44" {...S} />
      <path d="M60 63 L74 70" {...S} />
      <circle cx={60} cy={63} r={4} fill="#E8332E" stroke={INK} strokeWidth={2.5} />
    </Art>
  );
}

/** Cốc trà chiều xanh có quả cà chua, đĩa hồng — "Sổ tay". */
export function TeaCupArt(p: ArtProps) {
  return (
    <Art {...p}>
      <path d="M44 8 q-8 8 0 16 q8 8 0 16 M62 6 q-8 8 0 16 q8 8 0 16" {...S} strokeWidth={3.5} fill="none" />
      <ellipse cx={58} cy={104} rx={52} ry={12} fill="#FF9EC7" {...S} />
      <ellipse cx={58} cy={102} rx={34} ry={6} fill="none" stroke={INK} strokeWidth={2.5} />
      <path d="M88 56 q22 -2 20 18 q-2 18 -24 14" fill="none" stroke={INK} strokeWidth={12} strokeLinecap="round" />
      <path d="M88 56 q22 -2 20 18 q-2 18 -24 14" fill="none" stroke="#3D7BE0" strokeWidth={5} strokeLinecap="round" />
      <path d="M20 46 H96 L90 94 Q88 102 80 102 H36 Q28 102 26 94 Z" fill="#3D7BE0" {...S} />
      <ellipse cx={58} cy={46} rx={38} ry={9} fill="#FF7BA8" {...S} />
      <ellipse cx={58} cy={47} rx={28} ry={6} fill="#5A2E12" />
      <rect x={44} y={42} width={9} height={7} rx={2} fill="#FFFFFF" stroke={INK} strokeWidth={2} />
      <rect x={58} y={43} width={9} height={7} rx={2} fill="#FFFFFF" stroke={INK} strokeWidth={2} />
      <circle cx={58} cy={74} r={12} fill="#E8332E" {...S} strokeWidth={3} />
      <path d="M52 63 l6 4 l6 -4 M58 67 v-6" stroke="#2F9E44" strokeWidth={3.5} strokeLinecap="round" fill="none" />
    </Art>
  );
}

/** Máy nhắn tin "Hi! Học nào" — "Trò chơi". */
export function PagerArt(p: ArtProps) {
  return (
    <Art {...p}>
      <path d="M8 26 l10 6 M14 12 l8 10 M106 30 l-10 6" {...S} strokeWidth={3} fill="none" />
      <rect x={10} y={34} width={100} height={62} rx={16} fill="#3A3A3A" {...S} />
      <rect x={20} y={44} width={62} height={24} rx={5} fill="#A6E07A" {...S} strokeWidth={3} />
      <text x={51} y={57} textAnchor="middle" dominantBaseline="central"
        style={{ font: `16px ${PIXEL_FONT}`, fill: INK }}>HỌC NÀO!</text>
      <circle cx={30} cy={82} r={6} fill="#FF7652" stroke={INK} strokeWidth={2.5} />
      <circle cx={48} cy={82} r={6} fill="#FFE14D" stroke={INK} strokeWidth={2.5} />
      <circle cx={66} cy={82} r={6} fill="#5B8DEF" stroke={INK} strokeWidth={2.5} />
      <rect x={88} y={46} width={14} height={40} rx={5} fill="#555" stroke={INK} strokeWidth={2.5} />
      <path d="M20 96 q-4 14 8 18 M30 96 q2 12 12 14" stroke="#FF9EC7" strokeWidth={5} strokeLinecap="round" strokeDasharray="1 7" fill="none" />
    </Art>
  );
}

/** Hũ thuỷ tinh "FUN COOL" — "Học từ mới". */
export function JarArt(p: ArtProps) {
  return (
    <Art {...p}>
      <rect x={30} y={10} width={60} height={18} rx={6} fill="#FFE14D" {...S} />
      <path d="M36 28 H84 L96 44 V100 Q96 112 84 112 H36 Q24 112 24 100 V44 Z" fill="#DDF2FB" {...S} />
      <path d="M28 62 H92 V100 Q92 108 84 108 H36 Q28 108 28 100 Z" fill="#FFB020" />
      <rect x={32} y={60} width={56} height={30} rx={4} fill="#E8332E" {...S} strokeWidth={3} />
      <rect x={38} y={66} width={44} height={18} rx={3} fill="#FFF4D6" stroke={INK} strokeWidth={2} />
      <text x={60} y={75.5} textAnchor="middle" dominantBaseline="central"
        style={{ font: `14px ${PIXEL_FONT}`, fill: '#E8332E' }}>FUN COOL</text>
      <path d="M36 40 v14" stroke="#FFFFFF" strokeWidth={5} strokeLinecap="round" />
    </Art>
  );
}

/** Hộp đồ hộp vàng in hình bánh — "Bộ từ vựng" (kho từ để dành). */
export function CanArt(p: ArtProps) {
  return (
    <Art {...p}>
      <path d="M16 34 L60 18 L104 34 L104 92 L60 110 L16 92 Z" fill="#FFE14D" {...S} />
      <path d="M16 34 L60 50 L104 34" fill="none" {...S} />
      <path d="M60 50 V110" {...S} />
      <path d="M22 36 L60 22 L98 36 L60 48 Z" fill="#FFD000" />
      <ellipse cx={60} cy={34} rx={10} ry={5} fill="none" stroke={INK} strokeWidth={3} />
      <path d="M20 52 L56 64 V96 L20 84 Z" fill="#3D7BE0" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
      <text x={38} y={72} textAnchor="middle" transform="skewY(18) translate(0 -12)"
        style={{ font: `bold 12px ${PIXEL_FONT}`, fill: '#FFE14D' }}>WORDS</text>
      <path d="M28 80 q10 -8 20 2" fill="#FF9F43" stroke={INK} strokeWidth={2.5} />
      <path d="M27 84 q11 3 21 6" stroke="#2F9E44" strokeWidth={3} strokeLinecap="round" fill="none" />
      <path d="M66 62 L98 52 V84 L66 94 Z" fill="#3D7BE0" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
      <path d="M72 70 h6 v8 h-6 z M82 66 h6 v8 h-6 z" fill="#FFFFFF" stroke={INK} strokeWidth={2} />
    </Art>
  );
}

/** Má hồng + mắt dùng chung cho hai nhân vật người. */
function Cheeks({ y, l, r }: { y: number; l: number; r: number }) {
  return (
    <>
      <ellipse cx={l} cy={y} rx={7} ry={4.5} fill="#FF8FA3" opacity={0.85} />
      <ellipse cx={r} cy={y} rx={7} ry={4.5} fill="#FF8FA3" opacity={0.85} />
    </>
  );
}

/** "Mona" — nhân vật đại diện nữ cho Luyện nói (cảm hứng Mona Lisa). */
export function MonaArt(p: ArtProps) {
  return (
    <Art {...p}>
      {/* tóc sau */}
      <path d="M22 60 Q20 18 60 16 Q100 18 98 60 L102 112 H18 Z" fill="#5A3418" {...S} />
      {/* vai áo */}
      <path d="M16 118 Q20 92 60 92 Q100 92 104 118 Z" fill="#2E4A2A" {...S} />
      <path d="M44 94 Q60 104 76 94" fill="none" stroke="#FFE14D" strokeWidth={3} />
      {/* cổ + mặt */}
      <rect x={52} y={78} width={16} height={16} fill="#F6C9A0" {...S} strokeWidth={3} />
      <ellipse cx={60} cy={56} rx={26} ry={30} fill="#F6C9A0" {...S} />
      {/* tóc mái rẽ ngôi */}
      <path d="M34 50 Q36 28 60 26 Q84 28 86 50 Q74 36 60 34 Q46 36 34 50 Z" fill="#5A3418" {...S} strokeWidth={3} />
      <path d="M60 26 V36" stroke={INK} strokeWidth={2.5} />
      {/* mắt lim dim + lông mi */}
      <path d="M44 56 q6 -4 12 0 M64 56 q6 -4 12 0" {...S} strokeWidth={3} fill="none" />
      <path d="M44 56 q6 4 12 0 M64 56 q6 4 12 0" fill="#FFFFFF" stroke={INK} strokeWidth={2.5} />
      <circle cx={51} cy={57} r={2.4} fill={INK} />
      <circle cx={71} cy={57} r={2.4} fill={INK} />
      <path d="M43 54 l-3 -2 M77 54 l3 -2" stroke={INK} strokeWidth={2.5} strokeLinecap="round" />
      <Cheeks y={66} l={42} r={78} />
      {/* nụ cười bí ẩn */}
      <path d="M54 74 q6 3 12 -1" fill="none" {...S} strokeWidth={3} />
    </Art>
  );
}

/** "Hét" — nhân vật đại diện nam cho Luyện nói (cảm hứng The Scream). */
export function ScreamArt(p: ArtProps) {
  return (
    <Art {...p}>
      {/* áo */}
      <path d="M14 118 Q18 92 60 90 Q102 92 106 118 Z" fill="#3D7BE0" {...S} />
      <path d="M50 92 L60 106 L70 92" fill="#FFFFFF" stroke={INK} strokeWidth={3} strokeLinejoin="round" />
      {/* mặt dài */}
      <path d="M60 14 C86 14 90 44 86 66 C82 86 72 94 60 94 C48 94 38 86 34 66 C30 44 34 14 60 14 Z" fill="#F7E3C0" {...S} />
      {/* tóc xoăn */}
      <path d="M34 36 q-4 -14 8 -18 q2 -12 16 -8 q8 -10 20 -2 q14 -2 14 12 q10 6 2 18 q-6 -12 -16 -10 q-10 -8 -20 -2 q-12 -6 -24 10 Z"
        fill="#2B2B2B" {...S} strokeWidth={3} />
      {/* mắt tròn hoảng hốt */}
      <circle cx={49} cy={50} r={8} fill="#FFFFFF" {...S} strokeWidth={3} />
      <circle cx={71} cy={50} r={8} fill="#FFFFFF" {...S} strokeWidth={3} />
      <circle cx={49} cy={51} r={3.5} fill={INK} />
      <circle cx={71} cy={51} r={3.5} fill={INK} />
      <path d="M40 38 l8 3 M80 38 l-8 3" stroke={INK} strokeWidth={3} strokeLinecap="round" />
      <Cheeks y={64} l={40} r={80} />
      {/* miệng "Ô!" */}
      <ellipse cx={60} cy={76} rx={7} ry={10} fill="#C2283A" {...S} strokeWidth={3} />
      {/* hai tay áp má */}
      <path d="M26 92 Q20 70 30 58 Q36 54 38 62 Q36 76 40 88 Z" fill="#F7E3C0" {...S} strokeWidth={3} />
      <path d="M94 92 Q100 70 90 58 Q84 54 82 62 Q84 76 80 88 Z" fill="#F7E3C0" {...S} strokeWidth={3} />
    </Art>
  );
}

/** Cặp đại diện Luyện nói đứng cạnh nhau. */
export function SpeakingDuo({ size = 120, sx }: { size?: number; sx?: SxProps<Theme> }) {
  return (
    <Box aria-hidden sx={{ display: 'flex', alignItems: 'flex-end', ...sx }}>
      <MonaArt size={size} bob />
      <ScreamArt size={size * 0.92} sx={{ ml: `${-size * 0.12}px` }} />
    </Box>
  );
}

/** Loa phóng thanh hồng — "Cộng đồng" (chia sẻ, hỏi đáp). */
export function MegaphoneArt(p: ArtProps) {
  return (
    <Art {...p}>
      <path d="M96 30 l12 -8 M100 52 h14 M96 74 l12 8" {...S} strokeWidth={3.5} fill="none" />
      <path d="M30 78 L40 106 Q42 112 48 110 L56 107 Q60 105 58 99 L50 76 Z" fill="#FFE14D" {...S} />
      <path d="M16 44 H34 L86 16 V92 L34 68 H16 Q10 68 10 62 V50 Q10 44 16 44 Z" fill="#FF7BA8" {...S} />
      <path d="M34 44 V68" {...S} />
      <ellipse cx={86} cy={54} rx={8} ry={38} fill="#FF4F8B" {...S} />
      <path d="M44 50 l6 -2 M44 60 l10 0" stroke="#FFFFFF" strokeWidth={4} strokeLinecap="round" />
    </Art>
  );
}

/** Bảng biểu đồ cột đi lên — "Tiến độ". */
export function ChartArt(p: ArtProps) {
  return (
    <Art {...p}>
      <rect x={10} y={14} width={100} height={84} rx={12} fill="#FFFFFF" {...S} />
      <path d="M22 84 H98" {...S} strokeWidth={3} />
      <rect x={26} y={60} width={14} height={24} rx={3} fill="#FF7652" {...S} strokeWidth={3} />
      <rect x={46} y={48} width={14} height={36} rx={3} fill="#FFE14D" {...S} strokeWidth={3} />
      <rect x={66} y={36} width={14} height={48} rx={3} fill="#5B8DEF" {...S} strokeWidth={3} />
      <rect x={86} y={24} width={10} height={60} rx={3} fill="#7BD957" {...S} strokeWidth={3} />
      <path d="M24 52 L44 40 L62 30 L86 16" fill="none" stroke="#E8332E" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
      <path d="M78 14 L90 14 L88 26" fill="none" stroke="#E8332E" strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" />
      <path d="M40 98 l-6 16 M80 98 l6 16" {...S} />
    </Art>
  );
}

/** Hình đại diện cho từng khu vực của app (dùng ở tiêu đề trang, ô chức năng). */
export function artForPath(pathname: string): ((p: ArtProps) => ReactNode) | 'duo' | null {
  if (pathname.startsWith('/reviews')) return AlarmClockArt;
  if (pathname.startsWith('/word-sets') || pathname.startsWith('/discover')) return CanArt;
  if (pathname.startsWith('/roadmap') || pathname.startsWith('/placement')) return JarArt;
  if (pathname.startsWith('/games')) return PagerArt;
  if (pathname.startsWith('/notebook') || pathname.startsWith('/dictionary')) return TeaCupArt;
  if (pathname.startsWith('/pronunciation') || pathname.startsWith('/speaking') || pathname.startsWith('/shadowing') || pathname.startsWith('/conversation')) return 'duo';
  if (pathname.startsWith('/community') || pathname.startsWith('/users/')) return MegaphoneArt;
  if (pathname.startsWith('/progress')) return ChartArt;
  if (pathname.startsWith('/achievements')) return TrophyArt;
  if (pathname.startsWith('/settings') || pathname.startsWith('/admin')) return SettingsArt;
  if (pathname.startsWith('/profile')) return MonaArt;
  return null;
}

/** Cúp & máy tính dùng lại từ bộ trang trí, bọc cho cùng chữ ký với tranh poster. */
function TrophyArt({ size = 120, sx, bob }: ArtProps) {
  return <TrophyObject size={size} sx={sx} bob={bob} />;
}
function SettingsArt({ size = 120, sx, bob }: ArtProps) {
  return <RoboCharacter size={size} sx={sx} bob={bob} />;
}
