import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

import { FLAT } from '../theme/theme';

/* ═══════════════════════════════════════════════════════════════════════════
 * NHÂN VẬT + CẢNH VẬT PHẲNG (2026-10-26, theo mẫu "Your course" chủ dự án gửi)
 *
 * Hai bạn nhỏ đồng hành cùng người học:
 *  - Bin: cậu bé đội mũ lưỡi trai tím vành vàng, đeo kính tròn;
 *  - Na : cô bé tóc búi nơ hồng, váy vàng.
 * Mỗi bạn có 4 nét mặt (vui · buồn · nghĩ · reo) và 2 tư thế (ôm sách · vẫy tay),
 * `bust` = chỉ đầu và vai (cho ô nhỏ như dải kết quả).
 *
 * Cảnh vật (mây, cây, núi, hồ có vịt, nhà, nấm, hoa…) dùng để lấp chỗ trống
 * trên bản đồ lộ trình và mảng minh hoạ của trang chủ — khối màu đặc, không viền.
 * ═══════════════════════════════════════════════════════════════════════════ */

export type Mood = 'happy' | 'sad' | 'think' | 'cheer';

interface KidProps {
  size?: number;
  mood?: Mood;
  pose?: 'book' | 'wave';
  /** Chỉ đầu và vai — khung vuông. */
  bust?: boolean;
  sx?: SxProps<Theme>;
  title?: string;
}

const DARK = FLAT.dark;
const WHITE = '#FFFFFF';
const SKIN = '#F6C6A8';

function Svg({ viewBox, width, height, sx, title, children }: {
  viewBox: string; width: number; height?: number; sx?: SxProps<Theme>; title?: string; children: ReactNode;
}) {
  return (
    <Box
      component="svg"
      viewBox={viewBox}
      width={width}
      height={height}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      sx={{ display: 'block', flexShrink: 0, overflow: 'visible', pointerEvents: 'none', ...sx }}
    >
      {children}
    </Box>
  );
}

function Mouth({ mood, y = 76 }: { mood: Mood; y?: number }) {
  if (mood === 'sad') return <path d={`M53 ${y + 4} Q60 ${y - 2} 67 ${y + 4}`} stroke={DARK} strokeWidth="3" strokeLinecap="round" fill="none" />;
  if (mood === 'think') return <path d={`M55 ${y + 2} H65`} stroke={DARK} strokeWidth="3" strokeLinecap="round" />;
  if (mood === 'cheer') return (
    <>
      <path d={`M52 ${y - 1} Q60 ${y + 12} 68 ${y - 1}Z`} fill={DARK} />
      <path d={`M56 ${y + 5} Q60 ${y + 8} 64 ${y + 5}`} stroke={FLAT.pink} strokeWidth="3" strokeLinecap="round" fill="none" />
    </>
  );
  return <path d={`M53 ${y} Q60 ${y + 7} 67 ${y}`} stroke={DARK} strokeWidth="3" strokeLinecap="round" fill="none" />;
}

/** Bin — cậu bé đội mũ, đeo kính (nhân vật chính). */
export function KidBin({ size = 120, mood = 'happy', pose = 'book', bust = false, sx, title }: KidProps) {
  const viewBox = bust ? '10 18 100 100' : '0 0 120 160';
  return (
    <Svg viewBox={viewBox} width={size} height={bust ? size : (size * 160) / 120} sx={sx} title={title}>
      {!bust && (
        <>
          <ellipse cx="60" cy="155" rx="32" ry="5" fill="rgba(74,52,36,0.12)" />
          <rect x="46" y="124" width="11" height="27" rx="5" fill="#3D4A8A" />
          <rect x="63" y="124" width="11" height="27" rx="5" fill="#3D4A8A" />
          <ellipse cx="50" cy="151" rx="9" ry="5" fill={DARK} />
          <ellipse cx="70" cy="151" rx="9" ry="5" fill={DARK} />
        </>
      )}
      {/* áo */}
      <path d="M34 102 Q34 86 50 86 H70 Q86 86 86 102 V128 Q86 133 81 133 H39 Q34 133 34 128Z" fill={FLAT.purple} />
      <path d="M51 86 L60 97 L69 86Z" fill={WHITE} />
      {!bust && (pose === 'wave' ? (
        <>
          <path d="M82 96 Q96 86 95 66" stroke={FLAT.purple} strokeWidth="11" strokeLinecap="round" fill="none" />
          <circle cx="95" cy="61" r="7" fill={SKIN} />
          <path d="M38 96 Q30 112 36 122" stroke={FLAT.purple} strokeWidth="11" strokeLinecap="round" fill="none" />
          <rect x="20" y="108" width="20" height="26" rx="3" fill={FLAT.green} transform="rotate(-10 30 121)" />
          <circle cx="36" cy="124" r="6" fill={SKIN} />
          <path d="M101 52 L106 46 M104 60 L111 58" stroke={FLAT.yellow} strokeWidth="3.5" strokeLinecap="round" />
        </>
      ) : (
        <>
          <path d="M39 96 Q28 110 44 116" stroke={FLAT.purple} strokeWidth="11" strokeLinecap="round" fill="none" />
          <path d="M81 96 Q92 110 76 116" stroke={FLAT.purple} strokeWidth="11" strokeLinecap="round" fill="none" />
          <rect x="41" y="102" width="38" height="26" rx="3" fill={FLAT.green} />
          <rect x="43" y="104" width="34" height="5" rx="1" fill={WHITE} opacity="0.55" />
          <text x="60" y="123" textAnchor="middle" fontFamily="Nunito, sans-serif" fontWeight="900" fontSize="11" fill={WHITE}>ABC</text>
          <circle cx="44" cy="116" r="6" fill={SKIN} />
          <circle cx="76" cy="116" r="6" fill={SKIN} />
        </>
      ))}
      {/* đầu */}
      <rect x="54" y="78" width="12" height="11" fill={SKIN} />
      <circle cx="33" cy="62" r="6" fill={SKIN} />
      <circle cx="87" cy="62" r="6" fill={SKIN} />
      <circle cx="60" cy="58" r="27" fill={SKIN} />
      <path d="M34 54 Q34 42 44 40 L41 58Z M86 54 Q86 42 76 40 L79 58Z" fill={FLAT.brown} />
      {/* mũ */}
      <path d="M32 51 Q32 25 60 25 Q88 25 88 51Z" fill={FLAT.purple} />
      <path d="M58 47 H99 Q104 47 101 52 Q97 56 86 55 H58Z" fill={FLAT.yellow} />
      <circle cx="60" cy="25" r="3.5" fill={FLAT.yellow} />
      <path d="M44 33 Q50 29 56 29" stroke={WHITE} strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.35" />
      {/* kính + mắt */}
      <circle cx="48.5" cy="63" r="9.5" fill={WHITE} stroke={DARK} strokeWidth="3" />
      <circle cx="71.5" cy="63" r="9.5" fill={WHITE} stroke={DARK} strokeWidth="3" />
      <path d="M58 63 H62" stroke={DARK} strokeWidth="3" />
      {mood === 'cheer' ? (
        <path d="M44 64 Q48.5 59 53 64 M67 64 Q71.5 59 76 64" stroke={DARK} strokeWidth="3" strokeLinecap="round" fill="none" />
      ) : (
        <>
          <circle cx="49.5" cy={mood === 'sad' ? 65 : 64} r="3.8" fill="#4B2F9A" />
          <circle cx="72.5" cy={mood === 'sad' ? 65 : 64} r="3.8" fill="#4B2F9A" />
          <circle cx="50.8" cy="62.6" r="1.3" fill={WHITE} />
          <circle cx="73.8" cy="62.6" r="1.3" fill={WHITE} />
        </>
      )}
      <circle cx="41" cy="76" r="4" fill={FLAT.pink} opacity="0.55" />
      <circle cx="79" cy="76" r="4" fill={FLAT.pink} opacity="0.55" />
      <Mouth mood={mood} />
    </Svg>
  );
}

/** Na — cô bé tóc búi (nhân vật thứ hai). */
export function KidNa({ size = 120, mood = 'happy', pose = 'book', bust = false, sx, title }: KidProps) {
  const viewBox = bust ? '10 14 100 100' : '0 0 120 160';
  return (
    <Svg viewBox={viewBox} width={size} height={bust ? size : (size * 160) / 120} sx={sx} title={title}>
      {!bust && (
        <>
          <ellipse cx="60" cy="155" rx="30" ry="5" fill="rgba(74,52,36,0.12)" />
          <rect x="48" y="126" width="9" height="25" rx="4" fill={SKIN} />
          <rect x="63" y="126" width="9" height="25" rx="4" fill={SKIN} />
          <ellipse cx="51" cy="151" rx="8" ry="4.5" fill={FLAT.red} />
          <ellipse cx="69" cy="151" rx="8" ry="4.5" fill={FLAT.red} />
        </>
      )}
      {/* tóc phía sau */}
      <circle cx="60" cy="56" r="30" fill="#4A2C22" />
      <rect x="31" y="54" width="14" height="30" rx="7" fill="#4A2C22" />
      <rect x="75" y="54" width="14" height="30" rx="7" fill="#4A2C22" />
      <circle cx="60" cy="22" r="12" fill="#4A2C22" />
      <path d="M48 20 L39 13 L40 27Z M72 20 L81 13 L80 27Z" fill={FLAT.pink} />
      <circle cx="60" cy="20" r="4" fill="#E4789F" />
      {/* váy */}
      <path d="M44 86 H76 Q80 86 81 90 L90 128 Q91 134 85 134 H35 Q29 134 30 128 L39 90 Q40 86 44 86Z" fill={FLAT.yellow} />
      <path d="M36 118 H84" stroke={WHITE} strokeWidth="4" opacity="0.6" />
      {!bust && (pose === 'wave' ? (
        <>
          <path d="M79 94 Q94 86 94 68" stroke={SKIN} strokeWidth="9" strokeLinecap="round" fill="none" />
          <circle cx="94" cy="63" r="6.5" fill={SKIN} />
          <path d="M41 94 Q32 108 38 120" stroke={SKIN} strokeWidth="9" strokeLinecap="round" fill="none" />
        </>
      ) : (
        <>
          <path d="M41 94 Q30 108 45 115" stroke={SKIN} strokeWidth="9" strokeLinecap="round" fill="none" />
          <path d="M79 94 Q90 108 75 115" stroke={SKIN} strokeWidth="9" strokeLinecap="round" fill="none" />
          <rect x="42" y="101" width="36" height="25" rx="3" fill={FLAT.blue} />
          <rect x="44" y="103" width="32" height="5" rx="1" fill={WHITE} opacity="0.55" />
          <path d="M53 115 l3 3 l7 -7" stroke={WHITE} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </>
      ))}
      {/* mặt */}
      <rect x="54" y="78" width="12" height="10" fill={SKIN} />
      <circle cx="60" cy="58" r="25" fill={SKIN} />
      <path d="M35 54 Q36 31 60 31 Q84 31 85 54 Q76 42 66 44 Q62 50 52 48 Q42 46 35 54Z" fill="#4A2C22" />
      {mood === 'cheer' ? (
        <path d="M45 62 Q50 57 55 62 M65 62 Q70 57 75 62" stroke={DARK} strokeWidth="3" strokeLinecap="round" fill="none" />
      ) : (
        <>
          <ellipse cx="50" cy={mood === 'sad' ? 64 : 62} rx="4" ry="5" fill={DARK} />
          <ellipse cx="70" cy={mood === 'sad' ? 64 : 62} rx="4" ry="5" fill={DARK} />
          <circle cx="51.4" cy="60.4" r="1.5" fill={WHITE} />
          <circle cx="71.4" cy="60.4" r="1.5" fill={WHITE} />
          <path d="M45 56 L43 54 M75 56 L77 54" stroke={DARK} strokeWidth="2" strokeLinecap="round" />
        </>
      )}
      <circle cx="43" cy="71" r="4.5" fill={FLAT.pink} opacity="0.6" />
      <circle cx="77" cy="71" r="4.5" fill={FLAT.pink} opacity="0.6" />
      <Mouth mood={mood} y={72} />
    </Svg>
  );
}

/* ─────────────────────────────── CẢNH VẬT ─────────────────────────────── */

interface DecorProps {
  size?: number;
  sx?: SxProps<Theme>;
}

export function Cloud({ size = 120, sx, color = WHITE }: DecorProps & { color?: string }) {
  return (
    <Svg viewBox="0 0 120 56" width={size} height={(size * 56) / 120} sx={sx}>
      <path d="M14 52 Q2 52 2 42 Q2 30 16 30 Q18 12 38 12 Q52 2 68 12 Q90 6 96 26 Q118 26 118 40 Q118 52 104 52Z" fill={color} />
    </Svg>
  );
}

export function TreeRound({ size = 70, sx, leaf = FLAT.green }: DecorProps & { leaf?: string }) {
  return (
    <Svg viewBox="0 0 70 96" width={size} height={(size * 96) / 70} sx={sx}>
      <ellipse cx="35" cy="92" rx="20" ry="4" fill="rgba(74,52,36,0.12)" />
      <rect x="30" y="56" width="10" height="36" rx="4" fill={FLAT.brown} />
      <circle cx="35" cy="36" r="30" fill={leaf} />
      <circle cx="24" cy="28" r="12" fill={WHITE} opacity="0.18" />
    </Svg>
  );
}

export function TreeTall({ size = 46, sx, leaf = '#F0866A' }: DecorProps & { leaf?: string }) {
  return (
    <Svg viewBox="0 0 46 110" width={size} height={(size * 110) / 46} sx={sx}>
      <rect x="19" y="70" width="8" height="38" rx="3" fill={FLAT.brown} />
      <rect x="3" y="2" width="40" height="80" rx="20" fill={leaf} />
      <rect x="10" y="12" width="8" height="40" rx="4" fill={WHITE} opacity="0.2" />
    </Svg>
  );
}

export function Pine({ size = 50, sx, snow = false }: DecorProps & { snow?: boolean }) {
  return (
    <Svg viewBox="0 0 50 80" width={size} height={(size * 80) / 50} sx={sx}>
      <rect x="21" y="62" width="8" height="16" rx="2" fill={FLAT.brown} />
      <path d="M25 2 L46 40 H4Z" fill="#2E8B6A" />
      <path d="M25 22 L48 64 H2Z" fill="#2E8B6A" />
      {snow && <path d="M25 2 L33 16 Q29 19 25 15 Q21 19 17 16Z M25 22 L35 40 Q30 43 25 38 Q20 43 15 40Z" fill={WHITE} />}
    </Svg>
  );
}

export function Mountains({ size = 160, sx, snow = false }: DecorProps & { snow?: boolean }) {
  return (
    <Svg viewBox="0 0 160 80" width={size} height={size / 2} sx={sx}>
      <path d="M0 80 L48 14 L96 80Z" fill="#5E6B7A" />
      <path d="M58 80 L108 4 L160 80Z" fill="#7A8796" />
      {snow ? (
        <path d="M108 4 L122 26 Q115 30 108 24 Q101 30 94 26Z M48 14 L59 30 Q53 33 48 28 Q43 33 37 30Z" fill={WHITE} />
      ) : (
        <path d="M108 4 L118 20 L108 16 L98 20Z" fill="#9AA6B3" />
      )}
    </Svg>
  );
}

export function Pond({ size = 150, sx }: DecorProps) {
  return (
    <Svg viewBox="0 0 150 80" width={size} height={(size * 80) / 150} sx={sx}>
      <path d="M12 44 Q6 16 44 14 Q80 6 116 16 Q148 24 142 50 Q136 74 92 72 Q52 76 28 68 Q14 62 12 44Z" fill="#7CC6E8" />
      <path d="M36 32 H58 M92 56 H118" stroke={WHITE} strokeWidth="3" strokeLinecap="round" opacity="0.6" />
      {/* vịt */}
      <g transform="translate(64 26)">
        <ellipse cx="18" cy="22" rx="18" ry="11" fill={FLAT.yellow} />
        <circle cx="30" cy="8" r="9" fill={FLAT.yellow} />
        <path d="M38 8 L46 10 L38 13Z" fill={FLAT.orange} />
        <circle cx="32" cy="6" r="1.8" fill={DARK} />
        <path d="M6 18 Q14 12 20 20" stroke="#E0A82E" strokeWidth="3" fill="none" strokeLinecap="round" />
      </g>
      <g transform="translate(26 40) scale(0.6)">
        <ellipse cx="18" cy="22" rx="18" ry="11" fill={FLAT.yellow} />
        <circle cx="30" cy="8" r="9" fill={FLAT.yellow} />
        <path d="M38 8 L46 10 L38 13Z" fill={FLAT.orange} />
        <circle cx="32" cy="6" r="2" fill={DARK} />
      </g>
    </Svg>
  );
}

export function House({ size = 120, sx, wall = '#D9473F' }: DecorProps & { wall?: string }) {
  return (
    <Svg viewBox="0 0 120 96" width={size} height={(size * 96) / 120} sx={sx}>
      <ellipse cx="60" cy="92" rx="54" ry="4" fill="rgba(74,52,36,0.12)" />
      <path d="M10 46 L60 8 L110 46 V90 H10Z" fill={wall} />
      <path d="M2 50 L60 4 L118 50 L110 54 L60 15 L10 54Z" fill="#4B3F5C" />
      <rect x="48" y="58" width="24" height="32" rx="2" fill="#7A3A2F" />
      <path d="M48 58 L72 90 M72 58 L48 90" stroke={WHITE} strokeWidth="3" opacity="0.7" />
      <rect x="18" y="58" width="20" height="16" rx="2" fill={WHITE} />
      <rect x="82" y="58" width="20" height="16" rx="2" fill={WHITE} />
      <path d="M28 58 V74 M92 58 V74" stroke={wall} strokeWidth="2.5" />
      <circle cx="60" cy="38" r="7" fill={WHITE} />
    </Svg>
  );
}

export function Mushroom({ size = 40, sx }: DecorProps) {
  return (
    <Svg viewBox="0 0 40 40" width={size} height={size} sx={sx}>
      <rect x="15" y="20" width="10" height="18" rx="4" fill={FLAT.cream} />
      <path d="M2 22 Q2 4 20 4 Q38 4 38 22Z" fill={FLAT.red} />
      <circle cx="13" cy="13" r="3.5" fill={WHITE} />
      <circle cx="26" cy="10" r="2.5" fill={WHITE} />
      <circle cx="29" cy="18" r="2.5" fill={WHITE} />
    </Svg>
  );
}

export function Bush({ size = 70, sx, color = '#3E9E62' }: DecorProps & { color?: string }) {
  return (
    <Svg viewBox="0 0 70 34" width={size} height={(size * 34) / 70} sx={sx}>
      <path d="M4 34 Q0 18 14 16 Q18 2 34 6 Q46 0 54 12 Q70 12 66 34Z" fill={color} />
    </Svg>
  );
}

export function Flower({ size = 30, sx, color = FLAT.pink }: DecorProps & { color?: string }) {
  return (
    <Svg viewBox="0 0 30 46" width={size} height={(size * 46) / 30} sx={sx}>
      <path d="M15 20 V44" stroke="#3E9E62" strokeWidth="3" strokeLinecap="round" />
      <path d="M15 34 Q22 28 26 32 Q20 38 15 36Z" fill="#3E9E62" />
      {[0, 72, 144, 216, 288].map((d) => (
        <ellipse key={d} cx="15" cy="7" rx="5" ry="7" fill={color} transform={`rotate(${d} 15 14)`} />
      ))}
      <circle cx="15" cy="14" r="4.5" fill={FLAT.yellow} />
    </Svg>
  );
}

export function SunFlat({ size = 60, sx }: DecorProps) {
  return (
    <Svg viewBox="0 0 60 60" width={size} height={size} sx={sx}>
      {Array.from({ length: 8 }, (_, i) => (
        <rect key={i} x="27" y="1" width="6" height="12" rx="3" fill="#F7B53B" transform={`rotate(${i * 45} 30 30)`} />
      ))}
      <circle cx="30" cy="30" r="16" fill={FLAT.yellow} />
    </Svg>
  );
}

export function Snowman({ size = 44, sx }: DecorProps) {
  return (
    <Svg viewBox="0 0 44 64" width={size} height={(size * 64) / 44} sx={sx}>
      <circle cx="22" cy="46" r="16" fill={WHITE} />
      <circle cx="22" cy="20" r="11" fill={WHITE} />
      <rect x="13" y="2" width="18" height="10" rx="2" fill={DARK} />
      <rect x="9" y="10" width="26" height="4" rx="2" fill={DARK} />
      <path d="M22 21 L31 23 L22 25Z" fill={FLAT.orange} />
      <circle cx="18" cy="18" r="1.6" fill={DARK} />
      <circle cx="26" cy="18" r="1.6" fill={DARK} />
      <path d="M12 30 H32" stroke={FLAT.red} strokeWidth="4" strokeLinecap="round" />
    </Svg>
  );
}

export function Bench({ size = 70, sx }: DecorProps) {
  return (
    <Svg viewBox="0 0 70 40" width={size} height={(size * 40) / 70} sx={sx}>
      <rect x="4" y="6" width="62" height="7" rx="2" fill="#B5652E" />
      <rect x="4" y="17" width="62" height="7" rx="2" fill="#B5652E" />
      <rect x="10" y="24" width="5" height="16" fill={DARK} />
      <rect x="55" y="24" width="5" height="16" fill={DARK} />
    </Svg>
  );
}

/** Bóng cảnh nền xa: đồi thoải hai lớp (cho mảng minh hoạ trang chủ). */
export function Hills({ width = 400, sx, front = '#BFE3B4', back = '#D5EDCB' }: { width?: number; sx?: SxProps<Theme>; front?: string; back?: string }) {
  return (
    <Svg viewBox="0 0 400 90" width={width} height={(width * 90) / 400} sx={sx}>
      <path d="M0 60 Q90 10 190 44 Q280 74 400 30 V90 H0Z" fill={back} />
      <path d="M0 78 Q120 40 230 70 Q320 92 400 66 V90 H0Z" fill={front} />
    </Svg>
  );
}
