import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link as RouterLink, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import Divider from '@mui/material/Divider';
import Drawer from '@mui/material/Drawer';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import LinearProgress from '@mui/material/LinearProgress';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';
import { useQuery } from '@tanstack/react-query';

import { API_BASE_URL } from '../api/client';
import { useMyPermissions } from '../api/admin';
import { useGamificationSummary } from '../api/home';
import { getCalendar } from '../api/reviews';
import { useProfile } from '../api/user';
import { useAuth } from '../context/AuthContext';
import NotificationBell from './NotificationBell';
import {
  BookIcon,
  CalendarIcon,
  ChartIcon,
  ChatIcon,
  CompassIcon,
  DictionaryIcon,
  FlameIcon,
  GamepadIcon,
  GearIcon,
  HomeIcon,
  LogoutIcon,
  MenuIcon,
  MicIcon,
  RouteIcon,
  SearchIcon,
  ShieldIcon,
  SpeakerIcon,
  TrophyIcon,
  UserIcon,
  UsersIcon,
} from './icons';
import BrandMark, { BrandGlyph } from './BrandMark';
import {
  BookArt, BulbArt, ChartArt, ChatArt, ClockArt, CardsArt, FlagArt, GameArt, GearArt, MicArt,
  PeopleArt, SearchArt, TrophyArt,
} from './FlatArt';
import { KidBin } from './FlatScene';
import type { FlatArtProps } from './FlatArt';
import {
  FLAT,
  GRID_BACKGROUND,
  INK,
  MUTED,
  PAPER,
  PRIMARY,
  PRIMARY_TEXT,
  SOFT_SHADOW,
  SURFACE,
} from '../theme/theme';

/* ═══════════════════════════════════════════════════════════════════════════
 * KHUNG APP — bản flat (2026-10-26)
 *
 * Góp ý người dùng thử: "nút quan trọng phải hiện đầy đủ, dễ thấy ngay khi vào".
 * Bản trước giấu Luyện tập / Tiến độ trong menu thả xuống → phải bấm mới thấy.
 *
 *  - Desktop (≥ lg): THANH BÊN TRÁI hiện MỌI mục, chia ba nhóm theo vòng học
 *    (Học hằng ngày → Luyện thêm → Tiến độ). Mục đang mở là viên trắng chữ xanh.
 *    Chuỗi ngày, mục tiêu hôm nay, chuông, tài khoản nằm hàng trên vùng nội dung.
 *  - Dưới lg: thanh trên gọn (avatar + lời chào | chuỗi ngày, chuông) và THANH
 *    TAB ĐÁY kiểu ảnh mẫu: biểu tượng nét + nhãn, mục đang mở màu xanh. "Thêm"
 *    mở bảng đáy với minh hoạ tròn cho từng mục.
 * ═══════════════════════════════════════════════════════════════════════════ */

const SIDEBAR_WIDTH = 248;
const BOTTOM_BAR_HEIGHT = 66;

interface NavLeaf {
  to: string;
  label: string;
  icon: ReactNode;
  art?: (p: FlatArtProps) => ReactNode;
  badge?: number;
}

interface NavGroupDef {
  label: string;
  items: NavLeaf[];
}

/** Đường dẫn đang mở có thuộc mục `to` không ('/' chỉ khớp đúng trang chủ). */
function matches(pathname: string, to: string): boolean {
  return to === '/' ? pathname === '/' : pathname === to || pathname.startsWith(`${to}/`);
}

/** Số liệu điều hướng dùng chung cho thanh bên, thanh tab đáy và bảng Thêm. */
function useNavData() {
  const { data: permissions } = useMyPermissions();
  const calendar = useQuery({ queryKey: ['reviews', 'calendar'], queryFn: getCalendar });

  const dueToday = calendar.data?.today.length ?? 0;

  /** Bốn việc chính — có mặt ở cả thanh bên lẫn thanh tab đáy. */
  const primary: NavLeaf[] = [
    { to: '/', label: 'Trang chủ', icon: <HomeIcon size={21} /> },
    { to: '/reviews', label: 'Ôn tập', icon: <CalendarIcon size={21} />, art: ClockArt, badge: dueToday || undefined },
    { to: '/roadmap', label: 'Lộ trình', icon: <RouteIcon size={21} />, art: FlagArt },
    { to: '/word-sets', label: 'Bộ từ', icon: <BookIcon size={21} />, art: CardsArt },
  ];
  const practice: NavGroupDef = {
    label: 'Luyện thêm',
    items: [
      { to: '/pronunciation', label: 'Phát âm', icon: <MicIcon size={21} />, art: MicArt },
      { to: '/shadowing', label: 'Shadowing video', icon: <SpeakerIcon size={21} />, art: MicArt },
      { to: '/conversation', label: 'Hội thoại AI', icon: <ChatIcon size={21} />, art: ChatArt },
      { to: '/games', label: 'Trò chơi', icon: <GamepadIcon size={21} />, art: GameArt },
      { to: '/dictionary', label: 'Tra từ điển', icon: <DictionaryIcon size={21} />, art: SearchArt },
      { to: '/notebook', label: 'Sổ tay', icon: <BookIcon size={21} />, art: BulbArt },
      { to: '/discover', label: 'Khám phá bộ từ', icon: <CompassIcon size={21} />, art: BookArt },
      { to: '/community', label: 'Cộng đồng', icon: <UsersIcon size={21} />, art: PeopleArt },
    ],
  };
  const progress: NavGroupDef = {
    label: 'Tiến độ',
    items: [
      { to: '/progress', label: 'Tiến độ học', icon: <ChartIcon size={21} />, art: ChartArt },
      { to: '/achievements', label: 'Huy hiệu', icon: <TrophyIcon size={21} />, art: TrophyArt },
    ],
  };

  return { primary, practice, progress, isAdmin: (permissions?.length ?? 0) > 0 };
}

function CountBadge({ value }: { value: number }) {
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 22,
        height: 22,
        px: 0.75,
        borderRadius: 999,
        bgcolor: FLAT.red,
        color: '#FFFFFF',
        fontWeight: 900,
        fontSize: 12.5,
        lineHeight: 1,
      }}
    >
      {value > 99 ? '99+' : value}
    </Box>
  );
}

/* ─────────────────────────── THANH BÊN (≥ lg) ─────────────────────────────── */

function SideLink({ item }: { item: NavLeaf }) {
  const { pathname } = useLocation();
  const active = matches(pathname, item.to);
  return (
    <Box
      component={RouterLink}
      to={item.to}
      aria-current={active ? 'page' : undefined}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        height: 44,
        px: 1.5,
        borderRadius: '14px',
        textDecoration: 'none',
        fontSize: 15.5,
        fontWeight: active ? 900 : 700,
        color: active ? PRIMARY_TEXT : INK,
        // Thanh bên "xanh băng" (phương án B, 2026-10-28): mục đang mở là ô trắng
        bgcolor: active ? SURFACE : 'transparent',
        transition: 'background-color 0.12s ease',
        '& .nav-icon': { color: active ? PRIMARY : MUTED, display: 'grid' },
        '&:hover': { bgcolor: active ? SURFACE : '#E8F0FA' },
        '&:focus-visible': { outline: `3px solid ${PRIMARY}`, outlineOffset: 1 },
      }}
    >
      <Box component="span" className="nav-icon">{item.icon}</Box>
      <Box component="span" sx={{ flexGrow: 1, minWidth: 0, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {item.label}
      </Box>
      {item.badge != null && <CountBadge value={item.badge} />}
    </Box>
  );
}

function Sidebar({ nav }: { nav: ReturnType<typeof useNavData> }) {
  const groups: NavGroupDef[] = [nav.practice, nav.progress];
  return (
    <Box
      component="nav"
      aria-label="Điều hướng chính"
      sx={{
        position: 'sticky',
        top: 0,
        height: '100vh',
        width: SIDEBAR_WIDTH,
        flexShrink: 0,
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        px: 2,
        pt: 2.5,
        pb: 2,
        overflowY: 'auto',
        bgcolor: '#F4F8FD',
        borderRight: '1px solid #E3ECF5',
      }}
    >
      <Box component={RouterLink} to="/" aria-label="Learning Hub - Trang chủ" sx={{ display: 'block', px: 1, mb: 2.5, textDecoration: 'none' }}>
        <BrandMark size={34} fontSize={17} />
      </Box>
      <Box sx={{ display: 'grid', gap: 0.5 }}>
        {nav.primary.map((item) => <SideLink key={item.to} item={item} />)}
      </Box>
      {groups.map((g) => (
        <Box key={g.label} sx={{ mt: 2.25 }}>
          <Typography sx={{ px: 1.5, mb: 0.75, fontSize: 12.5, fontWeight: 900, letterSpacing: '0.06em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', color: '#A69A8F' }}>
            {g.label}
          </Typography>
          <Box sx={{ display: 'grid', gap: 0.25 }}>
            {g.items.map((item) => <SideLink key={item.to} item={item} />)}
          </Box>
        </Box>
      ))}
    </Box>
  );
}

/* ─────────────────────────────── HUD ─────────────────────────────────────── */

const pillSx = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 0.75,
  height: 40,
  px: 1.5,
  borderRadius: 999,
  bgcolor: SURFACE,
  boxShadow: SOFT_SHADOW,
  color: INK,
  textDecoration: 'none',
  fontWeight: 900,
  fontSize: 15,
  lineHeight: 1,
} as const;

/** Chuỗi ngày học. */
function StreakPill() {
  const { data } = useGamificationSummary();
  const streak = data?.streak_count ?? 0;
  // Lửa chỉ "cháy" (tô đặc) khi hôm nay đã học ít nhất một từ; chưa học thì
  // chỉ còn viền xám - nhắc nhẹ là chuỗi đang chờ.
  const litToday = (data?.daily_goal?.done ?? 0) > 0;
  return (
    <Tooltip title={litToday ? `Học liên tiếp ${streak} ngày - hôm nay đã giữ chuỗi` : `Học liên tiếp ${streak} ngày - học hôm nay để giữ chuỗi`}>
      <Box sx={{ ...pillSx, cursor: 'default', color: litToday ? INK : MUTED }}>
        <Box component="span" sx={{ display: 'grid', color: litToday ? FLAT.orange : '#B8ADA2' }}><FlameIcon size={18} filled={litToday} /></Box>
        {streak}
      </Box>
    </Tooltip>
  );
}

/** Mục tiêu hôm nay: nhãn + thanh xanh, như thanh "Level" ở đầu ảnh mẫu. */
function DailyGoalMeter({ compact = false }: { compact?: boolean }) {
  const { data } = useGamificationSummary();
  const goal = data?.daily_goal;
  if (!goal) return null;
  const pct = goal.target > 0 ? Math.min(100, Math.round((goal.done / goal.target) * 100)) : 0;
  const done = goal.reached || goal.done >= goal.target;
  const extra = Math.max(0, goal.done - goal.target);

  return (
    <Tooltip title={done
      ? `Đã đạt mục tiêu · hôm nay học ${goal.done} từ`
      : `Hôm nay còn ${Math.max(0, goal.target - goal.done)} từ nữa là đạt mục tiêu`}>
      <Box
        component={RouterLink}
        to="/progress"
        aria-label={done
          ? `Đã đạt mục tiêu hôm nay, đã học ${goal.done} từ (mục tiêu ${goal.target})`
          : `Mục tiêu hôm nay ${goal.done}/${goal.target} từ`}
        sx={{ ...pillSx, gap: 1.25, px: compact ? 1.5 : 2 }}
      >
        {!compact && <Box component="span" sx={{ fontSize: 13.5, fontWeight: 800, color: MUTED }}>Hôm nay</Box>}
        {!compact && (
          <LinearProgress variant="determinate" value={pct} sx={{ width: 96, height: 10 }} />
        )}
        {done ? (
          // Đã vượt mục tiêu: giữ phân số ở dạng "10/10" cho khớp thanh 100%,
          // phần vượt hiện nhỏ bên cạnh thay vì in "49/10" (tử > mẫu, khó đọc).
          <Box component="span" sx={{ whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'baseline', gap: 0.5 }}>
            <Box component="span" sx={{ color: 'success.main' }}>✓</Box>
            {goal.target}/{goal.target}
            {extra > 0 && (
              <Box component="span" sx={{ fontSize: 12, fontWeight: 700, color: 'success.main' }}>+{extra}</Box>
            )}
          </Box>
        ) : (
          <Box component="span" sx={{ whiteSpace: 'nowrap' }}>{goal.done}/{goal.target}</Box>
        )}
      </Box>
    </Tooltip>
  );
}

/** Ô tìm kiếm mở bằng nút hoặc Ctrl+K. */
function SearchLauncher() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    setOpen(false);
    setValue('');
    navigate(`/discover?q=${encodeURIComponent(q)}`);
  };

  return (
    <>
      <Tooltip title="Tìm từ vựng, bộ từ (Ctrl K)">
        <IconButton onClick={() => setOpen(true)} aria-label="Tìm kiếm" sx={roundIconSx}>
          <SearchIcon size={19} />
        </IconButton>
      </Tooltip>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        fullWidth
        maxWidth="sm"
        slotProps={{ transition: { onEntered: () => inputRef.current?.focus() } }}
        sx={{ '& .MuiDialog-container': { alignItems: 'flex-start', pt: { xs: 2, sm: 10 } } }}
      >
        <Box component="form" onSubmit={submit} sx={{ p: 2 }}>
          <TextField
            fullWidth
            placeholder="Gõ một từ hoặc tên bộ từ rồi Enter…"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            inputRef={inputRef}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon size={18} />
                  </InputAdornment>
                ),
                endAdornment: (
                  <InputAdornment position="end">
                    <Box component="kbd">Enter</Box>
                  </InputAdornment>
                ),
              },
            }}
          />
        </Box>
      </Dialog>
    </>
  );
}

/** Nút tròn trắng như hai nút chat/cài đặt góc phải ảnh mẫu. */
const roundIconSx = {
  width: 40,
  height: 40,
  bgcolor: SURFACE,
  color: INK,
  boxShadow: SOFT_SHADOW,
  '&:hover': { bgcolor: '#FAF5F0' },
} as const;

function useAccount() {
  const { data: profile } = useProfile();
  const name = profile?.display_name ?? '-';
  const initials = name.trim().split(/\s+/).slice(-2).map((w) => w[0]).join('').toUpperCase();
  const avatarSrc = profile?.avatar_url ? `${API_BASE_URL}${profile.avatar_url}` : undefined;
  return { profile, name, initials, avatarSrc };
}

/** Menu tài khoản sau avatar. Cấp độ/XP nằm ở đây. */
function AccountMenu({ showName = false }: { showName?: boolean }) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const auth = useAuth();
  const navigate = useNavigate();
  const { profile, name, initials, avatarSrc } = useAccount();
  const { data: summary } = useGamificationSummary();
  const { data: permissions } = useMyPermissions();

  const levelPct = summary && summary.xp_for_next_level > 0
    ? Math.min(100, Math.round((summary.xp_into_level / summary.xp_for_next_level) * 100))
    : 0;
  const go = (to: string) => {
    setAnchor(null);
    navigate(to);
  };
  const firstName = name.trim().split(/\s+/).slice(-1)[0];

  return (
    <>
      <Box
        component="button"
        type="button"
        onClick={(e: React.MouseEvent<HTMLElement>) => setAnchor(e.currentTarget)}
        aria-label="Mở menu tài khoản"
        sx={{
          display: 'flex', alignItems: 'center', gap: 1, p: 0, border: 0, bgcolor: 'transparent',
          cursor: 'pointer', font: 'inherit', color: INK, minWidth: 0,
          borderRadius: 999,
          '&:focus-visible': { outline: `3px solid ${PRIMARY}`, outlineOffset: 2 },
        }}
      >
        <Avatar
          src={avatarSrc}
          sx={{ width: 40, height: 40, fontSize: 15, fontWeight: 900, bgcolor: '#FDEFC4', color: INK, boxShadow: SOFT_SHADOW, border: '2px solid #FFFFFF' }}
        >
          {initials}
        </Avatar>
        {showName && (
          <Box sx={{ minWidth: 0, textAlign: 'left' }}>
            <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: MUTED, lineHeight: 1.1 }}>Chào bạn</Typography>
            <Typography sx={{ fontSize: 17, fontWeight: 900, lineHeight: 1.2 }} noWrap>{firstName}</Typography>
          </Box>
        )}
      </Box>

      <Menu
        anchorEl={anchor}
        open={Boolean(anchor)}
        onClose={() => setAnchor(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: showName ? 'left' : 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: showName ? 'left' : 'right' }}
        slotProps={{ paper: { sx: { minWidth: 260, mt: 1 } } }}
      >
        <Box sx={{ px: 2, py: 1.5 }}>
          <Typography sx={{ fontWeight: 900, fontSize: 15.5 }} noWrap>{name}</Typography>
          {profile?.email && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>
              {profile.email}
            </Typography>
          )}
          {summary && (
            <Box sx={{ mt: 1.25 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.75, gap: 1 }}>
                <Chip size="small" color="primary" label={`Cấp ${summary.level} · ${summary.level_title || 'Học viên'}`} sx={{ height: 24 }} />
                <Typography sx={{ fontWeight: 800, fontSize: 13, color: 'text.secondary', whiteSpace: 'nowrap' }}>
                  {summary.xp_into_level}/{summary.xp_for_next_level} XP
                </Typography>
              </Box>
              <LinearProgress variant="determinate" value={levelPct} />
            </Box>
          )}
        </Box>
        <Divider />
        <MenuItem onClick={() => go('/profile')} sx={{ gap: 1.25, fontSize: 14.5, py: 1 }}>
          <UserIcon size={18} /> Hồ sơ học tập
        </MenuItem>
        <MenuItem onClick={() => go('/settings')} sx={{ gap: 1.25, fontSize: 14.5, py: 1 }}>
          <GearIcon size={18} /> Cài đặt
        </MenuItem>
        {(permissions?.length ?? 0) > 0 && (
          <MenuItem onClick={() => go('/admin')} sx={{ gap: 1.25, fontSize: 14.5, py: 1, color: 'info.dark' }}>
            <ShieldIcon size={18} /> Quản trị hệ thống
          </MenuItem>
        )}
        <Divider />
        <MenuItem
          onClick={() => {
            setAnchor(null);
            auth.logout();
            navigate('/login');
          }}
          sx={{ gap: 1.25, fontSize: 14.5, py: 1, color: 'error.dark' }}
        >
          <LogoutIcon size={18} /> Đăng xuất
        </MenuItem>
      </Menu>
    </>
  );
}

/* ───────────────────────── THANH TAB ĐÁY (< lg) ──────────────────────────── */

function BottomTab({ item, onClick, active }: { item: NavLeaf; onClick?: () => void; active: boolean }) {
  const content = (
    <>
      <Box sx={{ position: 'relative', display: 'grid', placeItems: 'center', height: 26 }}>
        {item.icon}
        {item.badge != null && (
          <Box sx={{ position: 'absolute', top: -8, left: 14 }}>
            <CountBadge value={item.badge} />
          </Box>
        )}
      </Box>
      <Box component="span" sx={{ fontSize: 12.5, fontWeight: active ? 900 : 700, lineHeight: 1 }}>
        {item.label}
      </Box>
    </>
  );

  const sx = {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 0.6,
    border: 0,
    bgcolor: 'transparent',
    font: 'inherit',
    cursor: 'pointer',
    textDecoration: 'none',
    color: active ? PRIMARY_TEXT : '#9A8E83',
    '&:focus-visible': { outline: `3px solid ${PRIMARY}`, outlineOffset: -3, borderRadius: '12px' },
  } as const;

  return onClick ? (
    <Box component="button" type="button" onClick={onClick} aria-haspopup="dialog" sx={sx}>{content}</Box>
  ) : (
    <Box component={RouterLink} to={item.to} aria-current={active ? 'page' : undefined} sx={sx}>{content}</Box>
  );
}

/** Minh hoạ cho mục Hồ sơ: Bin trong vòng tròn vàng. */
function ProfileArt({ size = 52 }: FlatArtProps) {
  return (
    <Box sx={{ width: size, height: size, borderRadius: '50%', bgcolor: FLAT.yellow, overflow: 'hidden', display: 'grid', placeItems: 'end center' }}>
      <KidBin bust size={size} />
    </Box>
  );
}

/** Ô trong bảng Thêm: minh hoạ tròn + tên. */
function SheetTile({ item, onNavigate }: { item: NavLeaf; onNavigate: () => void }) {
  const Art = item.art ?? ProfileArt;
  return (
    <Box
      component={RouterLink}
      to={item.to}
      onClick={onNavigate}
      sx={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 0.75,
        p: 1,
        textAlign: 'center',
        textDecoration: 'none',
        color: INK,
        borderRadius: '16px',
        '&:hover': { bgcolor: '#F6EFE8' },
      }}
    >
      <Art size={52} />
      {item.badge != null && (
        <Box sx={{ position: 'absolute', top: 4, right: 'calc(50% - 34px)' }}><CountBadge value={item.badge} /></Box>
      )}
      <Typography sx={{ fontSize: 13, fontWeight: 800, lineHeight: 1.2 }}>{item.label}</Typography>
    </Box>
  );
}

function MoreSheet({ open, onClose, groups }: { open: boolean; onClose: () => void; groups: NavGroupDef[] }) {
  return (
    <Drawer
      anchor="bottom"
      open={open}
      onClose={onClose}
      slotProps={{
        paper: {
          sx: { borderRadius: '24px 24px 0 0', boxShadow: 'none', maxHeight: '82vh', bgcolor: SURFACE },
        },
      }}
    >
      <Box sx={{ width: 44, height: 5, borderRadius: 999, bgcolor: '#E2D7CC', mx: 'auto', mt: 1.25 }} />
      <Box sx={{ p: 2, pt: 1.5, pb: 'calc(16px + env(safe-area-inset-bottom))', overflowY: 'auto' }}>
        {groups.map((g) => (
          <Box key={g.label} sx={{ mb: 1.5 }}>
            <Typography sx={{ px: 1, mb: 0.5, fontSize: 12.5, fontWeight: 900, letterSpacing: '0.06em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', color: '#A69A8F' }}>
              {g.label}
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0.5 }}>
              {g.items.map((item) => <SheetTile key={item.to} item={item} onNavigate={onClose} />)}
            </Box>
          </Box>
        ))}
      </Box>
    </Drawer>
  );
}

/* ═══════════════════════════════════ KHUNG ═══════════════════════════════ */

function AppLayout() {
  const auth = useAuth();
  const theme = useTheme();
  const isDesktop = useMediaQuery(theme.breakpoints.up('lg'));
  const { pathname } = useLocation();
  const nav = useNavData();
  const [moreOpen, setMoreOpen] = useState(false);

  // Đổi trang thì đóng bảng Thêm (VD bấm thông báo dẫn sang trang khác).
  useEffect(() => setMoreOpen(false), [pathname]);

  if (!auth.token) {
    return <Navigate to="/login" replace />;
  }

  const account: NavGroupDef = {
    label: 'Tài khoản',
    items: [
      { to: '/profile', label: 'Hồ sơ', icon: <UserIcon size={21} />, art: ProfileArt },
      { to: '/settings', label: 'Cài đặt', icon: <GearIcon size={21} />, art: GearArt },
      ...(nav.isAdmin ? [{ to: '/admin', label: 'Quản trị', icon: <ShieldIcon size={21} />, art: GearArt }] : []),
    ],
  };
  const sheetGroups = [nav.practice, nav.progress, account];
  const moreActive = sheetGroups.some((g) => g.items.some((i) => matches(pathname, i.to)));

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', ...GRID_BACKGROUND }}>
      {isDesktop && <Sidebar nav={nav} />}

      <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {/* ─── HÀNG TRÊN ─── */}
        <Box
          component="header"
          sx={{
            position: 'sticky',
            top: 0,
            zIndex: 1100,
            bgcolor: PAPER,
          }}
        >
          <Box
            sx={{
              height: { xs: 64, lg: 72 },
              maxWidth: 1120,
              mx: 'auto',
              px: { xs: 2, sm: 3 },
              display: 'flex',
              alignItems: 'center',
              gap: { xs: 1, sm: 1.25 },
            }}
          >
            {isDesktop ? (
              <Box sx={{ flexGrow: 1 }} />
            ) : (
              <>
                <AccountMenu showName />
                <Box component={RouterLink} to="/" aria-label="Trang chủ" sx={{ display: { xs: 'none', sm: 'block' }, ml: 1 }}>
                  <BrandGlyph size={30} />
                </Box>
                <Box sx={{ flexGrow: 1 }} />
              </>
            )}
            <SearchLauncher />
            <StreakPill />
            <DailyGoalMeter compact={!isDesktop} />
            <Box sx={{ ...roundIconSx, borderRadius: '50%', display: 'grid', placeItems: 'center', '& .MuiIconButton-root': { color: INK } }}>
              <NotificationBell />
            </Box>
            {isDesktop && <AccountMenu />}
          </Box>
        </Box>

        {/* ─── NỘI DUNG ─── */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            width: '100%',
            maxWidth: 1120,
            mx: 'auto',
            boxSizing: 'border-box',
            px: { xs: 2, sm: 3 },
            pt: { xs: 1, lg: 1 },
            pb: { xs: `${BOTTOM_BAR_HEIGHT + 24}px`, lg: 5 },
          }}
        >
          <Outlet />
        </Box>
      </Box>

      {/* ─── THANH TAB ĐÁY (< lg) ─── */}
      {!isDesktop && (
        <Box
          component="nav"
          aria-label="Điều hướng chính"
          sx={{
            position: 'fixed',
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 1100,
            height: `calc(${BOTTOM_BAR_HEIGHT}px + env(safe-area-inset-bottom))`,
            pb: 'env(safe-area-inset-bottom)',
            bgcolor: SURFACE,
            boxShadow: '0 -4px 20px rgba(74,52,36,0.06)',
            display: 'flex',
            alignItems: 'stretch',
            px: 0.5,
          }}
        >
          {nav.primary.map((item) => (
            <BottomTab key={item.to} item={item} active={matches(pathname, item.to)} />
          ))}
          <BottomTab
            item={{ to: '#more', label: 'Thêm', icon: <MenuIcon size={21} /> }}
            active={moreActive || moreOpen}
            onClick={() => setMoreOpen(true)}
          />
        </Box>
      )}

      {!isDesktop && <MoreSheet open={moreOpen} onClose={() => setMoreOpen(false)} groups={sheetGroups} />}
    </Box>
  );
}

export default AppLayout;
