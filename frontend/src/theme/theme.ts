import { createTheme } from '@mui/material/styles';
import type { PaletteMode, Theme } from '@mui/material';

/* ═══════════════════════════════════════════════════════════════════════════
 * HỆ THIẾT KẾ "FLAT ẤM" (2026-10-26)
 *
 * Cảm hứng: ứng dụng học Woofz mà chủ dự án gửi — nền be hồng ấm, xanh lá làm
 * màu hành động, minh hoạ phẳng đặt trong vòng tròn màu, chữ tròn đậm.
 * Thay cho bản neo-brutalism (viền mực dày, bóng đổ cứng) mà người dùng thử
 * thấy nặng nề.
 *
 * Quy tắc:
 *  - Không viền mực. Thẻ trắng bo lớn (20px) + bóng rất mờ để tách khỏi nền.
 *  - Nút hình viên thuốc (bo tròn hẳn). Nút chính xanh lá chữ trắng.
 *  - MỘT màu hành động (xanh lá). Vàng chỉ cho huy hiệu / số đếm. Các màu
 *    tươi khác (tím, ô liu, đỏ, xanh dương) CHỈ nằm trong minh hoạ `FLAT`.
 *  - Một font: Nunito (tròn, có đủ dấu tiếng Việt), đậm 800–900 cho tiêu đề.
 *  Tên các hằng cũ giữ nguyên vì nhiều file đang import — chỉ đổi giá trị.
 * ═══════════════════════════════════════════════════════════════════════════ */

/** Chữ đọc và giao diện chung. */
export const ACCENT_FONT = '"Nunito","Be Vietnam Pro",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif';
/** Tiêu đề — cùng Nunito, nơi dùng phải tự đặt fontWeight 900. */
export const DISPLAY_FONT = ACCENT_FONT;
/** Chỉ còn cho chữ trang trí trong sticker cũ. */
export const PIXEL_FONT = '"VT323","JetBrains Mono",ui-monospace,monospace';
/** Con số và nhãn ngắn — Nunito với chữ số đều cột. */
export const LABEL_FONT = ACCENT_FONT;
export const MONO_FONT = '"JetBrains Mono",SFMono-Regular,Consolas,monospace';

// --- Bảng màu ------------------------------------------------------------------
/** Chữ chính: nâu than ấm, dịu hơn đen tuyền. */
export const INK = '#2E2A26';
export const MUTED = '#7A6F66';
/** Nền app: be hồng ấm như ảnh mẫu. */
export const PAPER = '#D9E9F7'; // xanh pastel nhạt (chủ dự án chốt 2026-10-28)
export const SURFACE = '#FFFFFF';
/** Mảng nhấn lớn nhạt (cột giới thiệu đăng nhập…). */
export const SKY = '#E3F3E4';
/** Màn hình bên trong hộp cũ (VendingScreen) — xanh lá nhạt. */
export const SCREEN_GREEN = '#E3F3E4';

/** Màu hành động duy nhất: xanh lá. */
export const PRIMARY = '#1E3A6E'; // xanh navy thay xanh lá (chủ dự án chốt 2026-10-28); màu "đúng" vẫn là GO_GREEN
export const PRIMARY_DARK = '#152B54';
export const PRIMARY_LIGHT = '#DCE6F5';
export const SECONDARY = '#F6C445';
export const RETRO_YELLOW = '#F6C445';
/** "Info" (trạng thái Đang học…): tím xanh dịu. */
export const RETRO_PURPLE = '#7C7FEA';
export const RETRO_PINK = '#FFFFFF';
export const RETRO_BLUE = '#FFFFFF';

export const STUDY_ACCENT = '#E5484D';
export const STUDY_ACCENT_DARK = '#B8333A';

export const GO_GREEN = '#2FA84F';
export const GO_GREEN_DARK = '#228A3E';
export const ACCENT_WARM = '#F6A93B';
export const WRONG_RED = '#E5484D';

// Biến thể chữ đạt tương phản AA trên nền sáng.
export const PRIMARY_TEXT = '#1E3A6E';
export const GO_GREEN_TEXT = '#1F7A39';
export const WARM_TEXT = '#9A5A00';
export const SECONDARY_TEXT = '#B4501A';

/** Màu logo — CỐ ĐỊNH, không đi theo bảng màu giao diện (logo là nhận diện riêng). */
export const BRAND_BLUE = '#9DBDF5';
export const BRAND_YELLOW = '#FFE27A';
export const BRAND_ORANGE = '#FF9472';

/** Màu minh hoạ phẳng (vòng tròn nhân vật, đồ vật) — lấy theo ảnh mẫu Woofz. */
export const FLAT = {
  purple: '#8E4BD8',
  green: '#3DAA4A',
  path: '#93C572',
  lime: '#B5C22B',
  red: '#E5413A',
  blue: '#7C7FEA',
  yellow: '#F6C445',
  orange: '#F39A3D',
  brown: '#8A5A44',
  peach: '#F6B89A',
  pink: '#F29BBF',
  teal: '#2BB3A3',
  cream: '#FFF4E3',
  skin: '#F3C9A5',
  dark: '#2E2A26',
} as const;

/** Đường kẻ mảnh — chỉ dùng khi thật cần tách (danh sách, ô nhập). */
export const LINE = '#EDE3D9';
export const LINE_STRONG = '#DCCFC2';
/** Bóng của thẻ trên nền be: rất mờ, đủ để thẻ "nổi" mà vẫn phẳng. */
export const SOFT_SHADOW = '0 1px 2px rgba(74, 52, 36, 0.05), 0 6px 20px rgba(74, 52, 36, 0.06)';
/** Bóng lớp nổi (menu, hộp thoại, bảng đáy). */
export const FLOAT_SHADOW = '0 16px 40px rgba(74, 52, 36, 0.16)';

/** Bóng đổ cứng của bản cũ — đã tắt; giữ hàm để chỗ gọi cũ tự phẳng theo. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function hardShadow(_size = 4, _color = INK): string {
  return 'none';
}

/** Hiệu ứng nút bấm dùng chung: chỉ đổi sắc khi rê chuột, lún nhẹ khi bấm. */
export function pressable(borderHighlight?: string, shadow = 3) {
  return {
    transition: 'background-color 0.15s ease, border-color 0.15s ease, transform 0.08s ease',
    '&:hover': {
      filter: shadow ? 'brightness(0.97)' : undefined,
      ...(borderHighlight ? { borderColor: borderHighlight } : {}),
    },
    '&:active': { transform: 'scale(0.98)' },
    '@media (prefers-reduced-motion: reduce)': {
      transition: 'none',
      '&:hover, &:active': { transform: 'none' },
    },
  } as const;
}

/** Nền app (be trơn). */
export const GRID_BACKGROUND = {
  backgroundColor: PAPER,
} as const;

/** Nền mảng nhấn lớn (cột giới thiệu đăng nhập). */
export const PANEL_GRID_BACKGROUND = {
  backgroundColor: SKY,
} as const;

/** Thẻ trắng chuẩn của hệ — dùng trong sx: `{ ...CARD_SX }`. */
export const CARD_SX = {
  bgcolor: SURFACE,
  borderRadius: '20px',
  boxShadow: SOFT_SHADOW,
} as const;

declare module '@mui/material/styles' {
  interface TypeBackground {
    muted: string;
  }
}

/** Tạo theme MUI. Dark mode đã bỏ (bug #4) — tham số giữ cho chữ ký cũ. */
export function buildTheme(mode: PaletteMode): Theme {
  return createTheme({
    palette: {
      mode,
      primary: { main: PRIMARY, light: PRIMARY_LIGHT, dark: PRIMARY_DARK, contrastText: '#FFFFFF' },
      secondary: { main: SECONDARY, light: '#FBE3A0', dark: '#C99A1E', contrastText: INK },
      success: { main: GO_GREEN, light: '#BFE6C8', dark: GO_GREEN_DARK, contrastText: '#FFFFFF' },
      warning: { main: ACCENT_WARM, light: '#FCE3B8', dark: '#B9730F', contrastText: INK },
      error: { main: WRONG_RED, light: '#F8C4C6', dark: '#B8333A', contrastText: '#FFFFFF' },
      info: { main: RETRO_PURPLE, light: '#DADBFA', dark: '#5154C4', contrastText: '#FFFFFF' },
      background: { default: PAPER, paper: SURFACE, muted: '#FAF5F0' },
      text: { primary: INK, secondary: MUTED, disabled: '#B0A69C' },
      divider: LINE,
      action: { hover: 'rgba(74,52,36,0.05)', selected: 'rgba(47,168,79,0.12)' },
    },
    shape: { borderRadius: 14 },
    typography: {
      fontFamily: ACCENT_FONT,
      fontSize: 15,
      h1: { fontWeight: 900, letterSpacing: '-0.01em', lineHeight: 1.2 },
      h2: { fontWeight: 900, letterSpacing: '-0.01em', lineHeight: 1.2 },
      h3: { fontWeight: 900, letterSpacing: '-0.01em', lineHeight: 1.25 },
      h4: { fontWeight: 900, letterSpacing: '-0.01em', lineHeight: 1.25 },
      h5: { fontWeight: 900, letterSpacing: '-0.01em' },
      h6: { fontWeight: 800, letterSpacing: '-0.005em' },
      subtitle1: { fontWeight: 700 },
      subtitle2: { fontWeight: 700 },
      overline: { fontWeight: 800, fontSize: '0.75rem', letterSpacing: '0.08em', lineHeight: 1.5 },
      body1: { fontWeight: 600, lineHeight: 1.55 },
      body2: { fontWeight: 600, lineHeight: 1.5 },
      caption: { fontWeight: 600 },
      // Chữ trên nút IN HOA toàn hệ thống cho nổi (chủ dự án 2026-10-27).
      button: { textTransform: 'uppercase', fontWeight: 900, letterSpacing: '0.04em' },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          html: { colorScheme: 'light' },
          body: { fontVariantNumeric: 'tabular-nums', ...GRID_BACKGROUND },
          '::selection': { backgroundColor: '#FBE3A0', color: INK },
          ':focus-visible': { outline: `3px solid ${RETRO_PURPLE}`, outlineOffset: 2 },
          '@media (prefers-reduced-motion: reduce)': {
            '*, *::before, *::after': {
              animationDuration: '.01ms !important',
              transitionDuration: '.01ms !important',
            },
          },
        },
      },
      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            borderRadius: 20,
            border: 'none',
            boxShadow: SOFT_SHADOW,
            backgroundImage: 'none',
            backgroundColor: SURFACE,
          },
        },
      },
      MuiPaper: {
        styleOverrides: {
          root: { backgroundImage: 'none' },
          rounded: { borderRadius: 20 },
          elevation0: { border: 'none', boxShadow: SOFT_SHADOW },
          elevation1: { border: 'none', boxShadow: SOFT_SHADOW },
          outlined: { border: `1px solid ${LINE}` },
          elevation8: { border: 'none', boxShadow: FLOAT_SHADOW, borderRadius: 16 },
        },
      },
      MuiButton: {
        defaultProps: { disableElevation: true, disableRipple: true },
        styleOverrides: {
          root: {
            borderRadius: 999,
            // Chữ nút luôn một dòng (chủ dự án 2026-10-27: "cấm xuống dòng dở").
            whiteSpace: 'nowrap',
            paddingInline: 20,
            paddingBlock: 8,
            fontWeight: 800,
          },
          contained: {
            border: 'none',
            ...pressable(),
            '&.Mui-disabled': { backgroundColor: '#ECE3DA', color: '#ADA299' },
          },
          outlined: {
            border: `1.5px solid ${LINE_STRONG}`,
            backgroundColor: SURFACE,
            color: INK,
            ...pressable(),
            '&:hover': { border: `1.5px solid ${LINE_STRONG}`, backgroundColor: '#FAF5F0' },
            '&.Mui-disabled': { border: `1.5px solid ${LINE}` },
          },
          text: {
            '&:hover': { backgroundColor: 'rgba(74,52,36,0.06)' },
          },
          sizeSmall: { paddingInline: 14, paddingBlock: 5 },
          sizeLarge: { paddingInline: 28, paddingBlock: 12, fontSize: '1.05rem' },
        },
        variants: [
          { props: { variant: 'contained', color: 'primary' }, style: { backgroundColor: PRIMARY, color: '#FFFFFF', '&:hover': { backgroundColor: PRIMARY_DARK } } },
          { props: { variant: 'contained', color: 'secondary' }, style: { backgroundColor: SECONDARY, color: INK, '&:hover': { backgroundColor: '#EDB52C' } } },
          { props: { variant: 'contained', color: 'success' }, style: { backgroundColor: GO_GREEN, color: '#FFFFFF', '&:hover': { backgroundColor: GO_GREEN_DARK } } },
          { props: { variant: 'contained', color: 'warning' }, style: { backgroundColor: SECONDARY, color: INK, '&:hover': { backgroundColor: '#EDB52C' } } },
          { props: { variant: 'contained', color: 'error' }, style: { backgroundColor: WRONG_RED, color: '#FFFFFF', '&:hover': { backgroundColor: '#CF3A40' } } },
          { props: { variant: 'contained', color: 'info' }, style: { backgroundColor: RETRO_PURPLE, color: '#FFFFFF', '&:hover': { backgroundColor: '#6567D8' } } },
          { props: { variant: 'contained', color: 'inherit' }, style: { backgroundColor: SURFACE, color: INK, boxShadow: SOFT_SHADOW, '&:hover': { backgroundColor: '#FAF5F0' } } },
          { props: { variant: 'outlined', color: 'error' }, style: { color: '#B8333A' } },
          { props: { variant: 'text', color: 'primary' }, style: { color: PRIMARY_TEXT } },
          { props: { variant: 'text', color: 'error' }, style: { color: '#B8333A' } },
        ],
      },
      MuiIconButton: {
        styleOverrides: {
          root: { '&:hover': { backgroundColor: 'rgba(74,52,36,0.06)' } },
        },
      },
      MuiToggleButton: {
        styleOverrides: {
          root: {
            fontWeight: 900,
            textTransform: 'uppercase',
            letterSpacing: '0.04em',
            whiteSpace: 'nowrap',
            border: 'none',
            borderRadius: '999px !important',
            color: MUTED,
            paddingInline: 16,
            '&.Mui-selected': { backgroundColor: SURFACE, color: INK, boxShadow: SOFT_SHADOW, '&:hover': { backgroundColor: SURFACE } },
          },
        },
      },
      MuiToggleButtonGroup: {
        styleOverrides: {
          root: { border: 'none', borderRadius: 999, backgroundColor: '#EDE3D9', padding: 3, gap: 2 },
          grouped: { border: 0, '&:not(:first-of-type)': { borderLeft: 0, marginLeft: 0 } },
        },
      },
      MuiLink: {
        styleOverrides: {
          root: {
            color: PRIMARY_TEXT,
            fontWeight: 800,
            textDecorationColor: 'rgba(31,122,57,0.35)',
            textUnderlineOffset: '3px',
            '&:hover': { textDecorationColor: PRIMARY_TEXT },
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 999,
            fontWeight: 800,
            fontSize: '0.75rem',
            border: 'none',
            color: INK,
          },
          filled: { backgroundColor: '#F3EAE1' },
          outlined: { backgroundColor: SURFACE, border: `1px solid ${LINE_STRONG}` },
          colorPrimary: { backgroundColor: PRIMARY_LIGHT, color: PRIMARY_TEXT },
          colorSecondary: { backgroundColor: '#FDEFC4', color: INK },
          colorSuccess: { backgroundColor: '#DDF2E1', color: GO_GREEN_TEXT },
          colorWarning: { backgroundColor: '#FDEBC8', color: WARM_TEXT },
          colorError: { backgroundColor: '#FCE0E1', color: '#B8333A' },
          colorInfo: { backgroundColor: '#E6E7FC', color: '#4A4DB8' },
        },
      },
      MuiLinearProgress: {
        styleOverrides: {
          root: {
            borderRadius: 999,
            height: 10,
            border: 'none',
            backgroundColor: '#EDE3D9',
          },
          bar: { borderRadius: 999 },
        },
      },
      MuiTooltip: {
        defaultProps: { arrow: true },
        styleOverrides: {
          tooltip: {
            backgroundColor: INK,
            color: '#FFFFFF',
            fontSize: '0.8rem',
            fontWeight: 700,
            borderRadius: 10,
          },
          arrow: { color: INK },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: 14,
            backgroundColor: '#FFFFFF',
            '& .MuiOutlinedInput-notchedOutline': { borderWidth: 1.5, borderColor: LINE_STRONG },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#BFAE9F' },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderWidth: 2, borderColor: PRIMARY },
            '&.Mui-error .MuiOutlinedInput-notchedOutline': { borderColor: WRONG_RED },
          },
        },
      },
      MuiInputLabel: {
        styleOverrides: {
          root: { fontWeight: 700, '&.Mui-focused': { color: PRIMARY_TEXT } },
        },
      },
      MuiAlert: {
        styleOverrides: {
          root: {
            borderRadius: 16,
            fontWeight: 650,
            border: 'none',
            color: INK,
          },
        },
        variants: [
          { props: { variant: 'standard', severity: 'success' }, style: { backgroundColor: '#DDF2E1' } },
          { props: { variant: 'standard', severity: 'info' }, style: { backgroundColor: '#ECEDFC' } },
          { props: { variant: 'standard', severity: 'warning' }, style: { backgroundColor: '#FDF0D3' } },
          { props: { variant: 'standard', severity: 'error' }, style: { backgroundColor: '#FCE0E1' } },
        ],
      },
      MuiDialog: {
        styleOverrides: {
          paper: { borderRadius: 24, border: 'none', boxShadow: FLOAT_SHADOW, backgroundImage: 'none' },
        },
      },
      MuiDialogTitle: {
        styleOverrides: { root: { fontWeight: 900 } },
      },
      MuiTabs: {
        styleOverrides: {
          indicator: { height: 3, borderRadius: 2, backgroundColor: PRIMARY },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            whiteSpace: 'nowrap',
            fontWeight: 800,
            '&.Mui-selected': { color: INK },
          },
        },
      },
      MuiDivider: {
        styleOverrides: { root: { borderColor: LINE } },
      },
      MuiSwitch: {
        styleOverrides: {
          track: { border: 'none', opacity: '1 !important', backgroundColor: '#E2D7CC' },
          thumb: { border: 'none', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' },
          switchBase: {
            '&.Mui-checked + .MuiSwitch-track': { backgroundColor: PRIMARY },
          },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: { fontWeight: 700, borderRadius: 10, marginInline: 6, '&:hover': { backgroundColor: '#F6EFE8' } },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { borderBottom: `1px solid ${LINE}` },
          head: { fontWeight: 800, color: MUTED },
        },
      },
      MuiAvatar: {
        styleOverrides: {
          colorDefault: { backgroundColor: '#FDEFC4', color: INK },
        },
      },
      MuiSkeleton: {
        styleOverrides: { root: { backgroundColor: 'rgba(74,52,36,0.08)' } },
      },
    },
  });
}
