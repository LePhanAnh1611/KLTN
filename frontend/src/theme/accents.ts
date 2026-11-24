// Bảng màu accent cho tag/category & khu vực — bản flat (2026-10-26).
// `bg` là nền nhạt, `fg` là chữ đạt AA trên `bg`, `solid` là màu tươi đặc của
// minh hoạ phẳng (đi với icon/chữ TRẮNG).

export interface AccentColor {
  bg: string;
  fg: string;
  solid: string;
}

const ACCENTS: AccentColor[] = [
  { bg: '#DDF2E1', fg: '#1F7A39', solid: '#3DAA4A' }, // Xanh lá
  { bg: '#E6E7FC', fg: '#4A4DB8', solid: '#7C7FEA' }, // Xanh tím
  { bg: '#D9F1EC', fg: '#1D7A6E', solid: '#2BB3A3' }, // Xanh ngọc
  { bg: '#FDF0CC', fg: '#8A5A00', solid: '#F0B323' }, // Vàng
  { bg: '#EFE4FB', fg: '#6A33B0', solid: '#8E4BD8' }, // Tím
  { bg: '#FDE6D3', fg: '#A3480F', solid: '#F39A3D' }, // Cam
  { bg: '#F3EAE1', fg: '#6B5F55', solid: '#A69A8F' }, // Trung tính
  { bg: '#FCE3EE', fg: '#A3285E', solid: '#E86FA3' }, // Hồng
];

/** Accent theo tên gọi ngữ nghĩa (dùng cho StatCard...). */
export const namedAccent: Record<
  'blue' | 'violet' | 'teal' | 'orange' | 'pink' | 'green' | 'amber' | 'sky',
  AccentColor
> = {
  blue: ACCENTS[1],
  violet: ACCENTS[4],
  teal: ACCENTS[0],
  orange: ACCENTS[5],
  pink: ACCENTS[7],
  green: ACCENTS[2],
  amber: ACCENTS[3],
  sky: ACCENTS[1],
};

/** Chọn 1 accent ổn định theo tên danh mục (hash đơn giản). */
export function categoryAccent(name: string | null | undefined): AccentColor {
  if (!name) return ACCENTS[0];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  return ACCENTS[hash % ACCENTS.length];
}

/**
 * Accent ổn định theo ID bộ từ.
 *
 * Khác `categoryAccent`: hash theo tên danh mục làm mọi bộ cùng danh mục ra
 * đúng một màu, nhìn không phân biệt được bộ nào với bộ nào. Bìa bộ từ vì vậy
 * lấy màu từ id — mỗi bộ một màu riêng và không đổi qua các lần tải trang.
 */
export function accentById(id: number): AccentColor {
  const index = Math.abs(Math.trunc(id)) % ACCENTS.length;
  return ACCENTS[index];
}

/** Màu riêng cho từng KHU VỰC của ứng dụng. */
const SECTION_COLORS: Record<string, AccentColor> = {
  '/': ACCENTS[0],              // Trang chủ — Teal
  '/roadmap': ACCENTS[1],       // Lộ trình — Sky
  '/word-sets': ACCENTS[0],     // Bộ từ vựng — Teal
  '/discover': ACCENTS[3],      // Khám phá — Amber
  '/reviews': ACCENTS[5],       // Lịch ôn — Cam
  '/pronunciation': ACCENTS[1], // Luyện phát âm — Sky
  '/speaking': ACCENTS[0],      // Luyện nói — Teal
  '/shadowing': ACCENTS[0],     // UC-97 Shadowing video — cùng màu luyện nói
  '/notebook': ACCENTS[3],      // Sổ tay — Amber
  '/progress': ACCENTS[2],      // Tiến độ — Emerald
  '/community': ACCENTS[7],     // Cộng đồng — Hồng
  '/achievements': ACCENTS[3],  // Huy hiệu — Amber
  '/settings': ACCENTS[6],
  '/admin': ACCENTS[4],
  '/games': ACCENTS[4],
  '/dictionary': ACCENTS[1],
  '/conversation': ACCENTS[7],
};

/** Màu của khu vực chứa đường dẫn hiện tại. */
export function sectionAccent(pathname: string): AccentColor {
  if (pathname === '/') return SECTION_COLORS['/'];
  const match = Object.keys(SECTION_COLORS)
    .filter((key) => key !== '/' && pathname.startsWith(key))
    .sort((a, b) => b.length - a.length)[0];
  return match ? SECTION_COLORS[match] : ACCENTS[0];
}

/** Màu chip cho độ khó bộ từ. */
export function difficultyAccent(difficulty: string | null | undefined): AccentColor {
  switch ((difficulty ?? '').toLowerCase()) {
    case 'beginner':
      return ACCENTS[2];
    case 'intermediate':
      return ACCENTS[3];
    case 'advanced':
      return ACCENTS[5];
    default:
      return ACCENTS[0];
  }
}
