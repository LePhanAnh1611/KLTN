import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

import { FLAT } from '../theme/theme';
import { KidBin } from './FlatScene';

/* ═══════════════════════════════════════════════════════════════════════════
 * MINH HOẠ PHẲNG (2026-10-26) — theo ngôn ngữ ảnh mẫu Woofz: đồ vật khối màu
 * đặc, KHÔNG viền, đặt trong vòng tròn màu tươi. Nhìn là hiểu ngay đồ vật gì
 * (đồng hồ = ôn tập, sách = từ mới, micro = luyện nói…).
 *
 * Mọi hình vẽ trên khung 100×100. `bg` = màu vòng tròn nền; `bg={null}` để
 * vẽ đồ vật trần (VD đặt lên thẻ đã có màu).
 * ═══════════════════════════════════════════════════════════════════════════ */

export interface FlatArtProps {
  size?: number;
  /** Màu vòng tròn nền; null = không vẽ nền. */
  bg?: string | null;
  sx?: SxProps<Theme>;
  title?: string;
}

const WHITE = '#FFFFFF';
/** Bảng màu khi vẽ trần lên nền navy (ô Trang chủ, vòng tiêu đề trang): chi tiết
 *  tối đổi sang trắng / xanh nhạt để không chìm vào nền (2026-10-28). */
const NAVY = '#1E3A6E';
const PALE = '#B9C6DC';

function Frame({ size = 96, bg, sx, title, children }: FlatArtProps & { children: ReactNode }) {
  return (
    <Box
      component="svg"
      viewBox="0 0 100 100"
      width={size}
      height={size}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      sx={{ display: 'block', flexShrink: 0, overflow: 'visible', ...sx }}
    >
      {bg && <circle cx="50" cy="50" r="50" fill={bg} />}
      {children}
    </Box>
  );
}

/** Ngôi sao bốn cánh lấp lánh. */
function Spark({ x, y, r = 6, color = FLAT.yellow }: { x: number; y: number; r?: number; color?: string }) {
  const k = r * 0.28;
  return (
    <path
      d={`M${x} ${y - r} Q${x + k} ${y - k} ${x + r} ${y} Q${x + k} ${y + k} ${x} ${y + r} Q${x - k} ${y + k} ${x - r} ${y} Q${x - k} ${y - k} ${x} ${y - r}Z`}
      fill={color}
    />
  );
}

/** Đồng hồ báo thức — Ôn tập. */
export function ClockArt({ bg = FLAT.yellow, ...p }: FlatArtProps) {
  // Không có vòng nền (đặt thẳng lên ô navy): vẽ đồng hồ một màu trắng, kim xanh
  // nhạt - bản đỏ/đen bị chê "chói" trên nền tối (2026-10-28).
  const mono = !bg;
  const frame = mono ? WHITE : FLAT.dark;
  return (
    <Frame bg={bg} {...p}>
      <path d="M33 74 L27 84 M67 74 L73 84" stroke={frame} strokeWidth="5" strokeLinecap="round" />
      <circle cx="30" cy="28" r="9" fill={frame} />
      <circle cx="70" cy="28" r="9" fill={frame} />
      <rect x="45" y="19" width="10" height="9" rx="3" fill={frame} />
      <circle cx="50" cy="55" r="27" fill={mono ? WHITE : FLAT.red} />
      <circle cx="50" cy="55" r="20" fill={mono ? '#DCE6F5' : FLAT.cream} />
      <path d="M50 55 V41 M50 55 L59 61" stroke={mono ? NAVY : FLAT.dark} strokeWidth="4" strokeLinecap="round" />
      <circle cx="50" cy="55" r="3.2" fill={mono ? NAVY : FLAT.dark} />
      {!mono && <path d="M36 40 Q40 35 46 34" stroke={WHITE} strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.8" />}
    </Frame>
  );
}

/** Quyển sách mở — Từ mới. */
export function BookArt({ bg = FLAT.purple, ...p }: FlatArtProps) {
  // Không có vòng nền (ô navy): sách trắng, chữ và dòng kẻ xanh nhạt.
  const mono = !bg;
  return (
    <Frame bg={bg} {...p}>
      <path d="M16 42 Q33 33 50 42 Q67 33 84 42 V76 Q67 67 50 76 Q33 67 16 76Z" fill={mono ? PALE : FLAT.green} />
      <path d="M19 37 Q35 29 50 37 V71 Q35 63 19 71Z" fill={WHITE} />
      <path d="M81 37 Q65 29 50 37 V71 Q65 63 81 71Z" fill={mono ? WHITE : FLAT.cream} />
      <text x="34.5" y="58" textAnchor="middle" fontFamily="Nunito, sans-serif" fontWeight="900" fontSize="17" fill={mono ? NAVY : FLAT.purple}>Aa</text>
      <path d="M57 45 Q65 41 74 45 M57 53 Q65 49 74 53 M57 61 Q63 58 68 60" stroke={mono ? PALE : '#E6D6C3'} strokeWidth="3" strokeLinecap="round" fill="none" />
      <Spark x={77} y={22} r={8} />
      <Spark x={22} y={24} r={4.5} color={WHITE} />
    </Frame>
  );
}

/** Micro — Luyện nói. */
export function MicArt({ bg = FLAT.lime, ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      {/* Không có vòng nền (đặt thẳng lên ô navy): thân micro màu sáng, nếu không sẽ chìm mất */}
      <rect x="38" y="16" width="24" height="42" rx="12" fill={bg ? FLAT.dark : '#FFFFFF'} />
      <path d="M44 27 H56 M44 35 H56 M44 43 H56" stroke={bg ? '#5E554D' : PALE} strokeWidth="3" strokeLinecap="round" />
      <path d="M29 46 Q29 68 50 68 Q71 68 71 46" stroke={WHITE} strokeWidth="5" strokeLinecap="round" fill="none" />
      <path d="M50 68 V80 M39 82 H61" stroke={WHITE} strokeWidth="5" strokeLinecap="round" />
      <path d="M78 30 Q83 37 78 44 M84 25 Q92 37 84 49" stroke={WHITE} strokeWidth="3.5" strokeLinecap="round" fill="none" />
    </Frame>
  );
}

/** Tay cầm chơi game — Trò chơi. */
export function GameArt({ bg = FLAT.blue, ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      <path d="M21 46 Q21 34 33 34 H67 Q79 34 79 46 L83 64 Q85 75 75 75 Q68 75 64 67 H36 Q32 75 25 75 Q15 75 17 64Z" fill={WHITE} />
      <path d="M33 46 V60 M26 53 H40" stroke={FLAT.dark} strokeWidth="5" strokeLinecap="round" />
      <circle cx="63" cy="49" r="4.5" fill={FLAT.red} />
      <circle cx="72" cy="56" r="4.5" fill={FLAT.yellow} />
      <circle cx="63" cy="61" r="4.5" fill={FLAT.green} />
      <Spark x={78} y={22} r={7} />
    </Frame>
  );
}

/** Bia bắn có mũi tên — Mục tiêu hôm nay. */
export function TargetArt({ bg = null, ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      <ellipse cx="46" cy="86" rx="24" ry="5" fill="rgba(74,52,36,0.12)" />
      <circle cx="46" cy="54" r="31" fill={FLAT.red} />
      <circle cx="46" cy="54" r="23" fill={WHITE} />
      <circle cx="46" cy="54" r="15" fill={FLAT.red} />
      <circle cx="46" cy="54" r="7" fill={WHITE} />
      <path d="M46 54 L80 20" stroke={FLAT.brown} strokeWidth="4" strokeLinecap="round" />
      <path d="M76 16 L88 12 L84 24 Z" fill={FLAT.red} />
      <path d="M73 21 L80 16 L79 28 Z" fill="#C2342E" />
    </Frame>
  );
}

/** Lá cờ — Lộ trình. */
export function FlagArt({ bg = FLAT.green, ...p }: FlatArtProps) {
  const mono = !bg;
  return (
    <Frame bg={bg} {...p}>
      {!mono && <ellipse cx="44" cy="82" rx="20" ry="5" fill="rgba(0,0,0,0.12)" />}
      <path d="M36 18 V81" stroke={mono ? WHITE : FLAT.dark} strokeWidth="5" strokeLinecap="round" />
      <path d="M38 21 H74 L65 34 L74 47 H38Z" fill={FLAT.yellow} />
      <path d="M38 21 H56 V47 H38Z" fill={WHITE} opacity="0.35" />
      <Spark x={76} y={66} r={6} color={WHITE} />
    </Frame>
  );
}

/** Cúp — Huy hiệu, bảng vàng. */
export function TrophyArt({ bg = FLAT.teal, ...p }: FlatArtProps) {
  const mono = !bg;
  return (
    <Frame bg={bg} {...p}>
      <path d="M35 30 H25 Q23 45 37 47 M65 30 H75 Q77 45 63 47" stroke={FLAT.yellow} strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M33 22 H67 V39 Q67 59 50 59 Q33 59 33 39Z" fill={FLAT.yellow} />
      <rect x="45" y="58" width="10" height="10" fill="#E0A82E" />
      <rect x="35" y="67" width="30" height="10" rx="4" fill={mono ? WHITE : FLAT.brown} />
      <path d="M41 29 V42" stroke={WHITE} strokeWidth="4" strokeLinecap="round" opacity="0.7" />
      <Spark x={78} y={20} r={6} color={WHITE} />
    </Frame>
  );
}

/** Hai bong bóng chat — Hội thoại, cộng đồng. */
export function ChatArt({ bg = FLAT.peach, ...p }: FlatArtProps) {
  const mono = !bg;
  return (
    <Frame bg={bg} {...p}>
      <path d="M17 30 Q17 21 26 21 H58 Q67 21 67 30 V47 Q67 56 58 56 H37 L26 66 V56 Q17 56 17 47Z" fill={WHITE} />
      <circle cx="31" cy="39" r="3.5" fill={mono ? NAVY : FLAT.dark} />
      <circle cx="42" cy="39" r="3.5" fill={mono ? NAVY : FLAT.dark} />
      <circle cx="53" cy="39" r="3.5" fill={mono ? NAVY : FLAT.dark} />
      <path d="M44 48 Q44 41 51 41 H76 Q83 41 83 48 V63 Q83 70 76 70 H74 V79 L65 70 H51 Q44 70 44 63Z" fill={mono ? PALE : FLAT.purple} />
      <path d="M53 52 H74 M53 60 H67" stroke={mono ? NAVY : WHITE} strokeWidth="3.5" strokeLinecap="round" />
    </Frame>
  );
}

/** Chồng thẻ từ — Bộ từ, khám phá. */
export function CardsArt({ bg = FLAT.yellow, ...p }: FlatArtProps) {
  const mono = !bg;
  return (
    <Frame bg={bg} {...p}>
      <rect x="24" y="27" width="40" height="50" rx="9" fill={mono ? PALE : FLAT.green} transform="rotate(-12 44 52)" />
      <rect x="34" y="23" width="40" height="50" rx="9" fill={WHITE} transform="rotate(7 54 48)" />
      <text x="54" y="55" textAnchor="middle" fontFamily="Nunito, sans-serif" fontWeight="900" fontSize="19" fill={mono ? NAVY : FLAT.dark} transform="rotate(7 54 48)">Aa</text>
      <path d="M45 62 H62" stroke={FLAT.red} strokeWidth="3.5" strokeLinecap="round" transform="rotate(7 54 48)" />
    </Frame>
  );
}

/** Biểu đồ cột — Tiến độ. */
export function ChartArt({ bg = FLAT.blue, ...p }: FlatArtProps) {
  const mono = !bg;
  return (
    <Frame bg={bg} {...p}>
      <rect x="25" y="50" width="13" height="27" rx="4" fill={WHITE} />
      <rect x="44" y="37" width="13" height="40" rx="4" fill={FLAT.yellow} />
      <rect x="63" y="25" width="13" height="52" rx="4" fill={WHITE} />
      <path d="M21 80 H80" stroke={mono ? PALE : FLAT.dark} strokeWidth="4" strokeLinecap="round" />
      <Spark x={30} y={30} r={6} color={FLAT.yellow} />
    </Frame>
  );
}

/** Bóng đèn — Sổ tay, mẹo. */
export function BulbArt({ bg = FLAT.purple, ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      <path d="M50 16 Q72 16 72 38 Q72 50 62 58 V64 H38 V58 Q28 50 28 38 Q28 16 50 16Z" fill={FLAT.yellow} />
      <rect x="38" y="64" width="24" height="7" rx="2" fill="#D9D2CA" />
      <rect x="40" y="71" width="20" height="7" rx="2" fill="#BDB4AA" />
      <path d="M46 80 H54" stroke="#BDB4AA" strokeWidth="5" strokeLinecap="round" />
      <path d="M40 30 Q42 24 48 23" stroke={WHITE} strokeWidth="4" strokeLinecap="round" fill="none" />
      <path d="M17 26 L11 22 M14 42 H7 M83 26 L89 22 M86 42 H93" stroke={WHITE} strokeWidth="4" strokeLinecap="round" />
    </Frame>
  );
}

/** Hai người — Cộng đồng, bạn bè. */
export function PeopleArt({ bg = FLAT.teal, ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      <circle cx="36" cy="38" r="12" fill={FLAT.skin} />
      <path d="M24 34 Q26 22 38 24 Q47 26 48 35 Q40 30 24 34Z" fill={bg ? FLAT.dark : FLAT.brown} />
      <path d="M16 78 Q16 56 36 56 Q56 56 56 78Z" fill={FLAT.yellow} />
      <circle cx="64" cy="42" r="11" fill="#C98E64" />
      <path d="M53 40 Q53 28 64 29 Q76 29 75 41 Q70 34 53 40Z" fill={FLAT.brown} />
      <path d="M46 80 Q46 59 64 59 Q82 59 82 80Z" fill={WHITE} />
    </Frame>
  );
}

/** Bánh răng — Cài đặt, quản trị. */
export function GearArt({ bg = FLAT.brown, ...p }: FlatArtProps) {
  const teeth = Array.from({ length: 8 }, (_, i) => i * 45);
  return (
    <Frame bg={bg} {...p}>
      {teeth.map((deg) => (
        <rect key={deg} x="44" y="16" width="12" height="16" rx="3" fill={FLAT.cream} transform={`rotate(${deg} 50 50)`} />
      ))}
      <circle cx="50" cy="50" r="24" fill={FLAT.cream} />
      <circle cx="50" cy="50" r="10" fill={bg || NAVY} />
    </Frame>
  );
}

/** Kính lúp — Tra từ điển. */
export function SearchArt({ bg = FLAT.green, ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      <path d="M58 58 L78 78" stroke={bg ? FLAT.dark : PALE} strokeWidth="9" strokeLinecap="round" />
      <circle cx="44" cy="44" r="22" fill={WHITE} />
      <circle cx="44" cy="44" r="15" fill="#CDEBF3" />
      <path d="M35 38 Q38 32 45 31" stroke={WHITE} strokeWidth="4" strokeLinecap="round" fill="none" />
    </Frame>
  );
}

/** Mèo cam — linh vật cho thông báo, tổng kết, ô trống. */
export function CatArt({ bg = null, mood = 'happy', ...p }: FlatArtProps & { mood?: 'happy' | 'sad' | 'think' }) {
  return (
    <Frame bg={bg} {...p}>
      <path d="M24 44 L27 14 L47 30Z" fill={FLAT.orange} />
      <path d="M76 44 L73 14 L53 30Z" fill={FLAT.orange} />
      <path d="M29 34 L30 21 L40 30Z" fill={FLAT.pink} />
      <path d="M71 34 L70 21 L60 30Z" fill={FLAT.pink} />
      <ellipse cx="50" cy="54" rx="32" ry="28" fill={FLAT.orange} />
      <path d="M43 28 Q50 34 57 28" stroke="#D97F22" strokeWidth="3" strokeLinecap="round" fill="none" />
      <ellipse cx="50" cy="65" rx="15" ry="11" fill={FLAT.cream} />
      {mood === 'sad' ? (
        <>
          <path d="M34 51 Q39 47 44 51 M56 51 Q61 47 66 51" stroke={FLAT.dark} strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M44 71 Q50 66 56 71" stroke={FLAT.dark} strokeWidth="3" strokeLinecap="round" fill="none" />
        </>
      ) : (
        <>
          <circle cx="39" cy="51" r="4.5" fill={FLAT.dark} />
          <circle cx="61" cy="51" r="4.5" fill={FLAT.dark} />
          <circle cx="40.5" cy="49.5" r="1.5" fill={WHITE} />
          <circle cx="62.5" cy="49.5" r="1.5" fill={WHITE} />
          {mood === 'think' ? (
            <path d="M45 70 H55" stroke={FLAT.dark} strokeWidth="3" strokeLinecap="round" />
          ) : (
            <path d="M44 66 Q50 74 56 66" stroke={FLAT.dark} strokeWidth="3" strokeLinecap="round" fill="none" />
          )}
        </>
      )}
      <path d="M47 60 H53 L50 63.5Z" fill={FLAT.pink} />
      <circle cx="30" cy="62" r="5" fill={FLAT.pink} opacity="0.6" />
      <circle cx="70" cy="62" r="5" fill={FLAT.pink} opacity="0.6" />
    </Frame>
  );
}

/** Dấu tích tròn xanh — trạng thái đã xong (giống huy hiệu trên nút lộ trình mẫu). */
export function CheckBadge({ size = 30, sx }: { size?: number; sx?: SxProps<Theme> }) {
  return (
    <Box component="svg" viewBox="0 0 30 30" width={size} height={size} aria-hidden sx={{ display: 'block', ...sx }}>
      <circle cx="15" cy="15" r="15" fill={WHITE} />
      <circle cx="15" cy="15" r="12" fill={FLAT.green} />
      <path d="M9.5 15.5 L13.5 19.5 L20.5 11.5" stroke={WHITE} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </Box>
  );
}

/** Ổ khoá — chặng chưa mở. */
export function LockArt({ bg = '#E6DCD2', ...p }: FlatArtProps) {
  return (
    <Frame bg={bg} {...p}>
      <path d="M38 46 V36 Q38 24 50 24 Q62 24 62 36 V46" stroke="#B4A79A" strokeWidth="7" fill="none" />
      <rect x="30" y="44" width="40" height="32" rx="8" fill="#B4A79A" />
      <circle cx="50" cy="58" r="5" fill="#E6DCD2" />
    </Frame>
  );
}

/** Bóng cây mờ trang trí nền (như chậu cây ẩn sau lộ trình mẫu). */
export function PlantDecor({ size = 120, color = '#EADDD1', sx }: { size?: number; color?: string; sx?: SxProps<Theme> }) {
  return (
    <Box component="svg" viewBox="0 0 100 100" width={size} height={size} aria-hidden sx={{ display: 'block', pointerEvents: 'none', ...sx }}>
      <path d="M50 92 Q48 60 30 36 Q48 44 52 70 Q56 40 74 22 Q66 52 56 92Z" fill={color} />
      <path d="M46 70 Q30 64 18 48 Q38 50 48 66Z" fill={color} />
      <rect x="34" y="84" width="34" height="14" rx="5" fill={color} />
    </Box>
  );
}

/** Bin trong vòng tròn vàng — đại diện Hồ sơ cá nhân. */
export function ProfileArt({ size = 96, bg = FLAT.yellow, sx }: FlatArtProps) {
  return (
    <Box aria-hidden sx={{ width: size, height: size, borderRadius: '50%', bgcolor: bg ?? 'transparent', overflow: 'hidden', display: 'grid', placeItems: 'end center', flexShrink: 0, ...sx }}>
      <KidBin bust size={size} />
    </Box>
  );
}

type ArtComponent = (p: FlatArtProps) => ReactNode;

/** Minh hoạ đại diện cho từng khu vực — PageHeader dùng để người học nhận ra mình đang ở đâu. */
export function flatArtForPath(pathname: string): ArtComponent | null {
  if (pathname.startsWith('/reviews')) return ClockArt;
  if (pathname.startsWith('/word-sets') || pathname.startsWith('/discover')) return CardsArt;
  if (pathname.startsWith('/roadmap') || pathname.startsWith('/placement')) return FlagArt;
  if (pathname.startsWith('/games')) return GameArt;
  if (pathname.startsWith('/notebook')) return BulbArt;
  if (pathname.startsWith('/dictionary')) return SearchArt;
  if (pathname.startsWith('/pronunciation') || pathname.startsWith('/speaking') || pathname.startsWith('/shadowing')) return MicArt;
  if (pathname.startsWith('/conversation')) return ChatArt;
  if (pathname.startsWith('/community') || pathname.startsWith('/users/')) return PeopleArt;
  if (pathname.startsWith('/progress')) return ChartArt;
  if (pathname.startsWith('/achievements')) return TrophyArt;
  if (pathname.startsWith('/settings') || pathname.startsWith('/admin')) return GearArt;
  if (pathname.startsWith('/profile') || pathname.startsWith('/users/')) return ProfileArt;
  return null;
}
