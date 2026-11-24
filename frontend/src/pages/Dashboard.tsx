import { Link as RouterLink, useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';

import { useLeaderboard } from '../api/community';
import type { LeaderboardRow } from '../api/community';
import { useCourseProgress, useTodayRecommendation } from '../api/home';
import { useValidationStatus } from '../api/pilot';
import { getCalendar, useWeakItems } from '../api/reviews';
import { BookArt, ClockArt, GameArt, MicArt } from '../components/FlatArt';
import SetProgress from '../components/SetProgress';
import { Bush, Cloud, Flower, Hills, KidBin, KidNa, SunFlat, TreeRound } from '../components/FlatScene';
import type { Mood } from '../components/FlatScene';
import type { FlatArtProps } from '../components/FlatArt';
import { CARD_SX, FLAT, INK, MUTED, PRIMARY, PRIMARY_TEXT } from '../theme/theme';

/**
 * Trang chủ — "nhìn một phát biết cần học gì".
 *
 * Bản flat 2026-10-26 (ngôn ngữ ảnh mẫu Woofz): MỘT việc chính với MỘT nút
 * xanh to, bốn lối đi bằng minh hoạ tròn + số việc chờ (huy hiệu đỏ), hai danh
 * sách ngắn (học tiếp, hay quên). Mọi thứ nằm gọn trong màn đầu tiên.
 *
 * Mọi con số vẫn từ API: gợi ý hôm nay (DKT chọn theo BR-03), lịch ôn, tiến độ
 * bộ từ, lộ trình, từ yếu (UC-86) và số từ mới đã học hôm nay.
 */

const BOARD_TOP = 5;
const MEDAL: Record<number, string> = { 1: '#D4A017', 2: '#9AA5AD', 3: '#B87333' };

function BoardRow({ row }: { row: LeaderboardRow }) {
  return (
    <Box
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.25, px: 1, py: 0.75, borderRadius: '12px',
        // Dòng của chính người xem tô nền để thấy ngay mình đứng đâu
        bgcolor: row.is_me ? '#EFE4FB' : 'transparent',
      }}
    >
      <Box
        sx={{
          width: 28, height: 28, flexShrink: 0, borderRadius: '50%', display: 'grid', placeItems: 'center',
          fontWeight: 900, fontSize: 13,
          color: MEDAL[row.rank] || row.is_me ? '#FFFFFF' : MUTED,
          bgcolor: MEDAL[row.rank] ?? (row.is_me ? FLAT.purple : '#F3ECE4'),
        }}
      >
        {row.rank}
      </Box>
      <Typography noWrap sx={{ flexGrow: 1, minWidth: 0, fontWeight: row.is_me ? 900 : 700, fontSize: 15 }}>
        {row.display_name}{row.is_me && ' (bạn)'}
      </Typography>
      <Typography sx={{ flexShrink: 0, fontWeight: 900, fontSize: 14.5, color: FLAT.purple }}>
        {row.xp.toLocaleString('vi-VN')} XP
      </Typography>
    </Box>
  );
}

/** UC-54 — top người học theo XP 7 ngày, luôn kèm hạng của chính người xem. */
function HomeLeaderboard() {
  const { data, isPending, isError } = useLeaderboard('week');
  const top = (data?.items ?? []).slice(0, BOARD_TOP);
  // Ngoài top thì backend trả `my_row` riêng — nối vào cuối
  const me = data?.my_row && (data.my_rank ?? 0) > BOARD_TOP ? data.my_row : null;

  return (
    <Box sx={{ ...CARD_SX, p: { xs: 2.5, sm: 3 }, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
        <Typography sx={{ fontWeight: 900, fontSize: 16, flexGrow: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>Xếp hạng tuần</Typography>
        {/* Thẻ hẹp: tiêu đề + nút gọn chữ để cả hàng vừa một dòng, không phải cắt "…" */}
        <Button size="small" component={RouterLink} to="/community" sx={{ color: PRIMARY_TEXT, flexShrink: 0, ml: 1 }}>Tất cả</Button>
      </Box>
      {isPending ? (
        <Typography sx={{ fontWeight: 700, color: MUTED }}>Đang tải…</Typography>
      ) : isError ? (
        <Typography sx={{ fontWeight: 700, color: MUTED }}>Chưa tải được bảng xếp hạng. Thử lại sau ít phút.</Typography>
      ) : top.length === 0 ? (
        <Typography sx={{ fontWeight: 700, color: MUTED }}>
          Tuần này chưa ai có XP. Học một phiên là bạn đứng đầu bảng ngay!
        </Typography>
      ) : (
        // Danh sách giãn đều theo chiều cao thẻ (cao bằng ô "Việc hôm nay" bên cạnh)
        <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 0.25 }}>
          {top.map((row) => <BoardRow key={row.user_id} row={row} />)}
          {me && (
            <>
              <Typography sx={{ textAlign: 'center', color: MUTED, lineHeight: 1 }}>···</Typography>
              <BoardRow row={me} />
            </>
          )}
          {data?.my_rank == null && (
            <Typography sx={{ fontSize: 13.5, fontWeight: 700, color: MUTED, mt: 1, px: 1 }}>
              Học một phiên trong tuần để có tên trên bảng.
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}

/** Một lối đi: minh hoạ tròn + tên + số việc đang chờ. */
function Tile({ to, onClick, title, count, Art, tint, artBg, fg = INK }: {
  to?: string;
  onClick?: () => void;
  title: string;
  count?: number;
  Art: (p: FlatArtProps) => React.ReactNode;
  /** Màu nền ô. */
  tint: string;
  /** Màu vòng tròn sau minh hoạ; chuỗi rỗng = không vẽ vòng (ô navy). */
  artBg: string;
  /** Màu chữ — trắng khi nền ô đậm. */
  fg?: string;
}) {
  const link = to ? { component: RouterLink, to } : { component: 'button' as const, type: 'button' as const, onClick };
  return (
    <Box
      {...link}
      sx={{
        ...CARD_SX,
        bgcolor: tint,
        boxShadow: 'none',
        position: 'relative',
        p: { xs: 2, sm: 2.5 },
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 1.25,
        border: 0,
        textDecoration: 'none',
        color: fg,
        font: 'inherit',
        cursor: 'pointer',
        transition: 'transform 0.12s ease',
        '&:hover': { transform: 'translateY(-2px)' },
        '&:active': { transform: 'scale(0.98)' },
        '&:focus-visible': { outline: `3px solid ${PRIMARY}`, outlineOffset: 3 },
      }}
    >
      {count != null && count > 0 && (
        <Box
          aria-label={`${count} việc đang chờ`}
          sx={{
            position: 'absolute', top: 12, right: 12, minWidth: 28, height: 28, px: 1,
            display: 'grid', placeItems: 'center', bgcolor: FLAT.red, color: '#FFFFFF',
            borderRadius: 999, fontWeight: 900, fontSize: 14,
          }}
        >
          {count}
        </Box>
      )}
      <Art size={84} bg={artBg} />
      <Typography sx={{ fontWeight: 900, fontSize: 16, textTransform: 'uppercase', letterSpacing: '0.03em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, maxWidth: '100%' }}>{title}</Typography>
    </Box>
  );
}

/** Tâm trạng của cảnh theo tiến độ hôm nay. */
type SceneMood = 'done' | 'effort' | 'almost' | 'learn' | 'start';

/** Nét mặt, tư thế, bầu trời và lời nhắn của từng tâm trạng. */
const SCENE: Record<SceneMood, {
  bin: { mood: Mood; pose: 'book' | 'wave' };
  na: { mood: Mood; pose: 'book' | 'wave' };
  sky: string;
  hills: [string, string];
  sunny: boolean;
  bubble?: string;
}> = {
  // Xong bài: trời nắng, cả hai reo mừng
  done: { bin: { mood: 'cheer', pose: 'wave' }, na: { mood: 'cheer', pose: 'wave' }, sky: '#E2F1F8', hills: ['#BFE3B4', '#D5EDCB'], sunny: true },
  // Còn từ đến hạn mà hôm nay chưa học gì: trời âm u, Na buồn, Bin cầm sách giục
  effort: { bin: { mood: 'think', pose: 'book' }, na: { mood: 'sad', pose: 'book' }, sky: '#E6E9EE', hills: ['#C9D9C3', '#DCE6D6'], sunny: false, bubble: 'Từ sắp quên rồi…' },
  // Đã học một phần, còn ít nữa: mây đang tan
  almost: { bin: { mood: 'happy', pose: 'book' }, na: { mood: 'think', pose: 'book' }, sky: '#E3EEF4', hills: ['#C6DFBC', '#D8EACF'], sunny: false, bubble: 'Cố lên, sắp xong!' },
  // Có từ mới để học: vui vẻ, háo hức
  learn: { bin: { mood: 'happy', pose: 'wave' }, na: { mood: 'happy', pose: 'book' }, sky: '#E2F1F8', hills: ['#BFE3B4', '#D5EDCB'], sunny: true },
  start: { bin: { mood: 'think', pose: 'book' }, na: { mood: 'happy', pose: 'wave' }, sky: '#E2F1F8', hills: ['#BFE3B4', '#D5EDCB'], sunny: true },
};

/**
 * Mảng phong cảnh của thẻ việc chính: đồi, mây, cây, hoa và hai bạn Bin & Na
 * (theo mẫu "Your course"). Cảm xúc đổi theo tiến độ hôm nay (góp ý chủ dự án
 * 2026-10-26): chưa học thì trời âm u, hai bạn buồn/lo và nhắc "cố lên"; học
 * xong thì nắng lên và cả hai reo mừng.
 */
function HeroScene({ mood }: { mood: SceneMood }) {
  const s = SCENE[mood];
  return (
    <Box
      aria-hidden
      sx={{
        position: 'relative',
        flexShrink: 0,
        width: { xs: '100%', sm: 300, lg: 340 },
        height: { xs: 150, sm: 210 },
        borderRadius: '22px',
        overflow: 'hidden',
        bgcolor: s.sky,
        transition: 'background-color 0.3s ease',
      }}
    >
      <SunFlat size={46} sx={{ position: 'absolute', top: 14, right: 18, opacity: s.sunny ? 1 : 0.55 }} />
      {/* Trời chưa nắng: một đám mây xám che bớt mặt trời */}
      {!s.sunny && <Cloud size={84} color="#C9D0DA" sx={{ position: 'absolute', top: 26, right: -4 }} />}
      <Cloud size={78} color={s.sunny ? '#FFFFFF' : '#D3D9E1'} sx={{ position: 'absolute', top: 20, left: 16 }} />
      <Cloud size={54} color={s.sunny ? '#FFFFFF' : '#DCE1E8'} sx={{ position: 'absolute', top: 54, right: 74, opacity: 0.9 }} />
      <Hills width={420} front={s.hills[0]} back={s.hills[1]} sx={{ position: 'absolute', bottom: 0, left: -40 }} />
      <TreeRound size={52} leaf={s.sunny ? FLAT.green : '#5E9E6E'} sx={{ position: 'absolute', bottom: 22, left: 14 }} />
      <Bush size={60} sx={{ position: 'absolute', bottom: 6, right: 8 }} />
      {s.sunny && <Flower size={18} sx={{ position: 'absolute', bottom: 12, left: '44%' }} />}
      {s.sunny && <Flower size={15} color={FLAT.yellow} sx={{ position: 'absolute', bottom: 16, left: '30%' }} />}
      {/* Học xong: vài đốm sáng như pháo giấy */}
      {mood === 'done' && (
        <Box sx={{ position: 'absolute', inset: 0 }}>
          {[[18, 30, FLAT.yellow], [30, 64, FLAT.pink], [12, 78, FLAT.blue], [42, 22, FLAT.orange], [24, 50, FLAT.purple]].map(([t, l, c], i) => (
            <Box key={i} sx={{ position: 'absolute', top: `${t}%`, left: `${l}%`, width: 8, height: 8, borderRadius: i % 2 ? '50%' : '2px', bgcolor: c as string, transform: `rotate(${i * 30}deg)` }} />
          ))}
        </Box>
      )}
      <Box sx={{ position: 'absolute', bottom: 4, left: '50%', transform: 'translateX(-62%)', display: 'flex', alignItems: 'flex-end', gap: 0.5 }}>
        <KidBin size={96} pose={s.bin.pose} mood={s.bin.mood} sx={{ height: { xs: 118, sm: 150 }, width: 'auto' }} />
        <Box sx={{ position: 'relative' }}>
          {s.bubble && (
            <Box sx={{
              position: 'absolute', bottom: '100%', left: '50%', mb: 0.5, px: 1.25, py: 0.5, whiteSpace: 'nowrap',
              bgcolor: '#FFFFFF', borderRadius: '12px', fontSize: 12.5, fontWeight: 900, color: INK,
              boxShadow: '0 4px 12px rgba(74,52,36,0.12)',
              '&::after': { content: '""', position: 'absolute', top: '100%', left: 14, borderWidth: '6px 6px 0', borderStyle: 'solid', borderColor: '#FFFFFF transparent transparent' },
            }}>
              {s.bubble}
            </Box>
          )}
          <KidNa size={84} pose={s.na.pose} mood={s.na.mood} sx={{ height: { xs: 106, sm: 134 }, width: 'auto' }} />
        </Box>
      </Box>
    </Box>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  // /recommendations/today gọi DKT cho từng từ trong thư viện nên có thể mất vài
  // giây — phân biệt "đang tính" với "không có từ nào vừa sức".
  const { data: today, isPending } = useTodayRecommendation();
  const calendar = useQuery({ queryKey: ['reviews', 'calendar'], queryFn: getCalendar });
  const { data: courses } = useCourseProgress();
  const { data: weak } = useWeakItems();
  const { data: finalTest } = useValidationStatus();

  // `today` của lịch ôn đã bị chặn theo `review_daily_limit` ở backend — phần tồn
  // đọng được dàn sang ngày sau, nên đây là khối lượng THẬT của hôm nay.
  const due = calendar.data?.today.length ?? 0;
  const minutes = calendar.data?.estimated_minutes ?? 0;
  const fresh = today?.items.length ?? 0;
  const newLearnedToday = today?.new_learned_today ?? 0;

  // Gửi kèm ĐÚNG danh sách từ đang hiển thị, để "Học 6 từ mới" là học đúng 6 từ
  // đó. Trước đây chỉ mở bộ của từ đầu tiên, màn học tự chọn lại 20 từ.
  // Đặt id lên URL (không dùng router state) để F5 giữa chừng vẫn không mất.
  const startSmart = () => {
    const ids = today?.items.map((w) => w.item_id) ?? [];
    navigate(ids.length > 0 ? `/study/today?ids=${ids.join(',')}` : '/roadmap');
  };

  // MỘT việc chính: ôn từ đến hạn trước, rồi mới tới từ mới.
  const task = due > 0
    ? {
        kicker: 'Việc hôm nay',
        big: `Ôn ${due} từ`,
        meta: [minutes > 0 ? `khoảng ${minutes} phút` : '', newLearnedToday > 0
          ? `đã học ${newLearnedToday} từ mới hôm nay`
          : fresh > 0 ? `sau đó học ${fresh} từ mới` : ''].filter(Boolean).join(' · '),
        cta: 'Bắt đầu ôn',
        go: () => navigate('/reviews/study'),
        // Hôm nay đã học chút ít -> "sắp xong"; chưa học gì -> cần cố gắng
        mood: (newLearnedToday > 0 ? 'almost' : 'effort') as SceneMood,
      }
    : newLearnedToday > 0
      ? {
          kicker: 'Tuyệt vời',
          big: 'Xong bài hôm nay!',
          meta: `Bạn đã học ${newLearnedToday} từ mới. Chơi một ván ôn lại cho vui nhé.`,
          cta: 'Chơi trò ôn từ',
          go: () => navigate('/games'),
          mood: 'done' as SceneMood,
        }
      : fresh > 0
        ? {
            kicker: 'Việc hôm nay',
            big: `Học ${fresh} từ mới`,
            meta: 'Chọn sẵn những từ vừa sức bạn',
            cta: 'Bắt đầu học',
            go: startSmart,
            mood: 'learn' as SceneMood,
          }
        : {
            kicker: 'Bắt đầu',
            big: isPending ? 'Đang chuẩn bị…' : 'Chọn chặng để học',
            meta: '',
            cta: 'Mở lộ trình',
            go: () => navigate('/roadmap'),
            mood: 'start' as SceneMood,
          };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: { xs: 2, sm: 2.5 } }}>
      {/* Pilot — lối vào bài kiểm tra cuối, chỉ hiện khi admin đã mở và người học chưa làm */}
      {finalTest?.open && !finalTest.done && finalTest.eligible_items >= finalTest.min_items && (
        <Alert
          severity="warning"
          action={<Button color="inherit" size="small" onClick={() => navigate('/final-test')}>Làm ngay</Button>}
        >
          <b>Bài kiểm tra cuối đã mở</b> - khoảng 10 phút, giúp kiểm chứng hệ thống. Cảm ơn bạn!
        </Alert>
      )}

      {/* ===== VIỆC HÔM NAY — to nhất, một nút ===== */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: 'minmax(0, 1.75fr) minmax(0, 1fr)' }, gap: { xs: 2, sm: 2.5 } }}>
        <Box
          sx={{
            ...CARD_SX,
            position: 'relative',
            overflow: 'hidden',
            p: { xs: 2.5, sm: 3.5 },
            pr: { sm: 2 },
            display: 'flex',
            flexDirection: { xs: 'column-reverse', sm: 'row' },
            alignItems: { xs: 'stretch', sm: 'center' },
            gap: { xs: 2, sm: 2.5 },
          }}
        >
          <Box sx={{ flexGrow: 1, minWidth: 0, position: 'relative', zIndex: 1 }}>
            <Typography sx={{ fontWeight: 900, fontSize: 14, color: PRIMARY_TEXT, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {task.kicker}
            </Typography>
            <Typography component="h1" sx={{ fontWeight: 900, fontSize: { xs: 34, sm: 46 }, lineHeight: 1.1, mt: 0.75 }}>
              {task.big}
            </Typography>
            {task.meta && (
              <Typography sx={{ fontWeight: 700, fontSize: 16, color: MUTED, mt: 1 }}>{task.meta}</Typography>
            )}
            <Button
              variant="contained"
              size="large"
              onClick={task.go}
              disabled={isPending && due === 0}
              sx={{ mt: 2.5, px: 4, minHeight: 50, fontSize: 15, whiteSpace: 'nowrap', boxShadow: '0 4px 0 rgba(0,0,0,0.12)', width: { xs: '100%', sm: 'auto' } }}
            >
              {task.cta}
            </Button>
          </Box>
          <HeroScene mood={task.mood} />
        </Box>

        {/* Bảng xếp hạng tuần (UC-54) — thay cho "từ bạn đã thuộc": số đó có thể
            giảm khi ôn sai (mastery DKT tụt dưới ngưỡng BR-01), người học đọc thành
            "bị trừ điểm". XP chỉ tăng nên thứ hạng là động lực đúng chiều hơn. */}
        <HomeLeaderboard />
      </Box>

      {today?.degraded && (
        <Typography sx={{ fontSize: 14, color: 'warning.dark', fontWeight: 700, mt: -1 }}>
          Phần gợi ý từ đang tạm nghỉ - danh sách từ mới hôm nay có thể chưa sát với bạn.
        </Typography>
      )}

      {/* ===== 4 lối đi — minh hoạ + tên + số việc chờ ===== */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(4, 1fr)' }, gap: { xs: 2, sm: 2.5 } }}>
        <Tile to="/reviews" title="Ôn tập" count={due} Art={ClockArt} tint="#1E3A6E" artBg="" fg="#FFFFFF" />
        <Tile onClick={startSmart} title="Từ mới" count={fresh} Art={BookArt} tint="#1E3A6E" artBg="" fg="#FFFFFF" />
        <Tile to="/pronunciation" title="Luyện nói" Art={MicArt} tint="#1E3A6E" artBg="" fg="#FFFFFF" />
        <Tile to="/games" title="Trò chơi" Art={GameArt} tint="#1E3A6E" artBg="" fg="#FFFFFF" />
      </Box>

      {/* ===== Học tiếp + Hay quên ===== */}
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: { xs: 2, sm: 2.5 } }}>
        <Box sx={{ ...CARD_SX, p: { xs: 2.5, sm: 3 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Typography sx={{ fontWeight: 900, fontSize: 16, flexGrow: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>Học tiếp</Typography>
            <Button size="small" component={RouterLink} to="/word-sets" sx={{ color: PRIMARY_TEXT }}>Xem tất cả</Button>
          </Box>
          {(courses ?? []).length === 0 ? (
            <Typography sx={{ fontWeight: 700, color: MUTED }}>Chưa có bộ từ - mở Lộ trình để bắt đầu.</Typography>
          ) : (
            (courses ?? []).slice(0, 3).map((c) => (
              <Box
                key={c.id}
                component={RouterLink}
                to={`/word-sets/${c.id}`}
                aria-label={`${c.name}: ${c.mastered_items}/${c.total_items} từ đã thuộc, ${c.learning_items ?? 0} từ đang học`}
                sx={{ display: 'block', py: 1, color: INK, textDecoration: 'none', borderRadius: '12px' }}
              >
                <Typography sx={{ fontWeight: 800, fontSize: 15.5, mb: 0.5 }} noWrap>{c.name}</Typography>
                <SetProgress total={c.total_items} mastered={c.mastered_items} learning={c.learning_items ?? 0} />
              </Box>
            ))
          )}
        </Box>
        <Box sx={{ ...CARD_SX, p: { xs: 2.5, sm: 3 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
            <Typography sx={{ fontWeight: 900, fontSize: 16, flexGrow: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.03em' }}>Từ hay quên</Typography>
            {(weak ?? []).length > 0 && (
              <Button size="small" variant="contained" component={RouterLink} to="/reviews/study?source=weak">Ôn ngay</Button>
            )}
          </Box>
          {(weak ?? []).length === 0 ? (
            <Typography sx={{ fontWeight: 700, color: MUTED }}>Chưa có từ nào hay quên. Tốt lắm!</Typography>
          ) : (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {(weak ?? []).slice(0, 8).map((w) => (
                <Box
                  key={w.item_id}
                  title={w.meaning}
                  sx={{ px: 1.75, py: 0.75, borderRadius: 999, bgcolor: '#FCE0E1', color: '#8F2A30', fontWeight: 800, fontSize: 15.5 }}
                >
                  {w.word}
                </Box>
              ))}
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
}
