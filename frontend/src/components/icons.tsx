// Bộ icon SVG inline (stroke = currentColor) — tránh phụ thuộc @mui/icons-material.
import type { SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 22, children, ...props }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export const HomeIcon = (p: IconProps) => (
  <Svg {...p}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V21h14V9.5" /><path d="M9.5 21v-6h5v6" /></Svg>
);
export const BookIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2z" /><path d="M18 3v18" /><path d="M8 7h6M8 11h6" /></Svg>
);
export const CalendarIcon = (p: IconProps) => (
  <Svg {...p}><rect x="3" y="4.5" width="18" height="16" rx="2.5" /><path d="M3 9h18M8 3v3M16 3v3" /></Svg>
);
export const ChartIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 20V4" /><path d="M4 20h16" /><rect x="7" y="12" width="3" height="5" rx="1" /><rect x="12" y="8" width="3" height="9" rx="1" /><rect x="17" y="5" width="3" height="12" rx="1" /></Svg>
);
export const TrophyIcon = (p: IconProps) => (
  <Svg {...p}><path d="M7 4h10v5a5 5 0 0 1-10 0z" /><path d="M7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3" /><path d="M10 14h4M9 20h6M12 14v6" /></Svg>
);
export const UserIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Svg>
);
export const MicIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="9" y="2.5" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0" /><path d="M12 17.5V21M9 21h6" />
  </Svg>
);
export const SpeakerIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 9.5h3L11 6v12l-4-3.5H4z" />
    <path d="M14.5 9a4 4 0 0 1 0 6" /><path d="M17 6.5a7.5 7.5 0 0 1 0 11" />
  </Svg>
);
export const GearIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3.2" />
    <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" />
  </Svg>
);
export const RouteIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="6" cy="19" r="2.5" /><circle cx="18" cy="5" r="2.5" />
    <path d="M8.5 19h4a4 4 0 0 0 0-8h-2a4 4 0 0 1 0-8h5" />
  </Svg>
);
export const LockIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="4.5" y="10.5" width="15" height="10" rx="2" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
  </Svg>
);
export const CheckIcon = (p: IconProps) => (
  <Svg {...p}><path d="m5 12.5 4.5 4.5L19 7" /></Svg>
);
export const ShieldIcon = (p: IconProps) => (
  <Svg {...p}><path d="M12 3l7 3v6c0 4.2-2.9 7.6-7 9-4.1-1.4-7-4.8-7-9V6z" /><path d="m9 12 2 2 4-4" /></Svg>
);
export const UsersIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="9" cy="8" r="3.5" /><path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M16 5.2a3.5 3.5 0 0 1 0 6.6" /><path d="M17.5 14.5A6.5 6.5 0 0 1 21.5 20" />
  </Svg>
);
export const LogoutIcon = (p: IconProps) => (
  <Svg {...p}><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" /><path d="M10 12H3M6 8l-3 4 3 4" /></Svg>
);
export const BellIcon = (p: IconProps) => (
  <Svg {...p}><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6" /><path d="M10 20a2 2 0 0 0 4 0" /></Svg>
);
export const SunIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4 12H2M22 12h-2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" /></Svg>
);
export const MoonIcon = (p: IconProps) => (
  <Svg {...p}><path d="M21 12.5A9 9 0 1 1 11.5 3a7 7 0 0 0 9.5 9.5" /></Svg>
);
export const MenuIcon = (p: IconProps) => (
  <Svg {...p}><path d="M4 6h16M4 12h16M4 18h16" /></Svg>
);
/** `filled`: tô đặc ruột lửa (đã học hôm nay); bỏ trống = chỉ có viền. */
export const FlameIcon = ({ filled = false, ...p }: IconProps & { filled?: boolean }) => (
  <Svg {...p}><path d="M12 3s5 4 5 9a5 5 0 0 1-10 0c0-1.5.7-2.8 1.5-3.5C8.5 10 9 12 9 12s0-4 3-9" fill={filled ? 'currentColor' : 'none'} /></Svg>
);
export const StarIcon = (p: IconProps) => (
  <Svg {...p}><path d="m12 3 2.6 5.5 6 .8-4.4 4.2 1.1 6L12 16.9 6.7 19.5l1.1-6L3.4 9.3l6-.8z" /></Svg>
);
export const CompassIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5z" /></Svg>
);
export const DownloadIcon = (p: IconProps) => (
  <Svg {...p}><path d="M12 3v12M8 11l4 4 4-4" /><path d="M5 19h14" /></Svg>
);
export const SearchIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.2-3.2" /></Svg>
);
export const GraduationIcon = (p: IconProps) => (
  <Svg {...p}><path d="m2 8 10-4 10 4-10 4z" /><path d="M6 10v5c0 1.2 2.7 2.5 6 2.5s6-1.3 6-2.5v-5" /><path d="M22 8v5" /></Svg>
);

/** UC-94 — tay cầm chơi game. */
export const GamepadIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 12h4M9 10v4" /><circle cx="15.5" cy="11" r=".6" fill="currentColor" />
    <circle cx="17.5" cy="13.5" r=".6" fill="currentColor" />
    <path d="M6.5 7h11a4 4 0 0 1 4 4v2a4 4 0 0 1-4 4c-1.6 0-2.3-1-3.2-2H9.7c-.9 1-1.6 2-3.2 2a4 4 0 0 1-4-4v-2a4 4 0 0 1 4-4z" />
  </Svg>
);

/** UC-95 — tra từ: quyển sách mở kèm kính lúp. */
export const DictionaryIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v13H5.5A1.5 1.5 0 0 0 4 18.5z" />
    <path d="M11 4h5.5A1.5 1.5 0 0 1 18 5.5V9" />
    <circle cx="16.5" cy="15" r="3" /><path d="m18.8 17.2 2.2 2.2" />
  </Svg>
);

/** UC-39 — bong bong hoi thoai. */
export const ChatIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20 12a7 7 0 0 1-7 7H8l-4 3v-4.2A7 7 0 0 1 4 12a7 7 0 0 1 7-7h2a7 7 0 0 1 7 7z" />
    <path d="M9 11h6M9 14h4" />
  </Svg>
);

/** Trái tim — nút "Thích" ở bài cộng đồng và mạng còn lại trong trò chơi.
 * `filled` đổi đặc/rỗng: cùng một hình, nên mắt đọc được thay đổi trạng thái
 * mà không phải đổi sang glyph khác. */
export const HeartIcon = ({ filled = false, ...p }: IconProps & { filled?: boolean }) => (
  <Svg {...p} fill={filled ? 'currentColor' : 'none'}>
    <path d="M12 20s-7-4.6-7-9.3A4.2 4.2 0 0 1 12 7.6a4.2 4.2 0 0 1 7 3.1C19 15.4 12 20 12 20z" />
  </Svg>
);
export const CloseIcon = (p: IconProps) => (
  <Svg {...p}><path d="M6 6l12 12M18 6 6 18" /></Svg>
);
export const ChevronRightIcon = (p: IconProps) => (
  <Svg {...p}><path d="M9 6l6 6-6 6" /></Svg>
);
export const PanelRightIcon = (p: IconProps) => (
  <Svg {...p}><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M15 4v16" /></Svg>
);
export const ExpandIcon = (p: IconProps) => (
  <Svg {...p}><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M8 21H5a2 2 0 0 1-2-2v-3M16 21h3a2 2 0 0 0 2-2v-3" /></Svg>
);
export const TargetIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></Svg>
);

export const EyeIcon = (p: IconProps) => (
  <Svg {...p}><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" /><circle cx="12" cy="12" r="3.2" /></Svg>
);
export const EyeOffIcon = (p: IconProps) => (
  <Svg {...p}><path d="M10.6 6.1A8.9 8.9 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-3.2 3.9M6.6 7.9A17 17 0 0 0 2.5 12S6 18 12 18a8.9 8.9 0 0 0 3.6-.74" /><path d="M9.8 9.9a3.1 3.1 0 0 0 4.3 4.3" /><path d="M3.5 3.5l17 17" /></Svg>
);
export const MailIcon = (p: IconProps) => (
  <Svg {...p}><rect x="2.5" y="5" width="19" height="14" rx="2.5" /><path d="m3.5 7 8.5 6 8.5-6" /></Svg>
);
export const ArrowLeftIcon = (p: IconProps) => (
  <Svg {...p}><path d="M19 12H5" /><path d="m11 6-6 6 6 6" /></Svg>
);
export const AlertIcon = (p: IconProps) => (
  <Svg {...p}><circle cx="12" cy="12" r="9.5" /><path d="M12 7.5v5.5" /><path d="M12 16.3h.01" /></Svg>
);
