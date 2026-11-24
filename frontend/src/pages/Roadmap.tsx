import { useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import Snackbar from '@mui/material/Snackbar';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import { useCourseProgress } from '../api/home';
import { usePlacementStatus } from '../api/placement';
import SkillMap from '../components/SkillMap';
import {
  useDecideLevelUp,
  useDownloadStageSet,
  useLevelUpStatus,
  useRoadmap,
  type RoadmapStage,
} from '../api/roadmap';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import StageSummaryDialog from '../components/StageSummaryDialog';
import {
  BookArt, BulbArt, CardsArt, ChartArt, ChatArt, CheckBadge, GameArt, MicArt, PeopleArt, TrophyArt,
} from '../components/FlatArt';
import {
  Bench, Bush, Cloud, Flower, House, Mountains, Mushroom, Pine, Pond, Snowman, SunFlat, TreeRound, TreeTall,
} from '../components/FlatScene';
import { LockIcon } from '../components/icons';
import type { FlatArtProps } from '../components/FlatArt';
import { CARD_SX, FLAT, INK, MUTED, PRIMARY, PRIMARY_TEXT, SOFT_SHADOW, SURFACE } from '../theme/theme';
import { splitRoadmapStages } from '../utils/roadmap';

/* ═══════════════════════════════════════════════════════════════════════════
 * LỘ TRÌNH — bản đồ phong cảnh (2026-10-26, theo mẫu "Your course").
 *
 * Mỗi trình độ là một tab/"tầng" với cảnh một mùa; mỗi chặng là một cuốn sách
 * đặt dọc con đường. Trạng thái đọc được bằng hình chứ không cần chú thích:
 *  - xong: dấu tích xanh ở góc;
 *  - đang học: thanh tiến độ nhỏ dưới tên;
 *  - gợi ý tiếp theo: viền xanh + nhãn "Bạn ở đây" + nút "Vào học";
 *  - chưa mở: bìa xám + ổ khoá đỏ.
 * ═══════════════════════════════════════════════════════════════════════════ */

/** Minh hoạ bìa cho từng chặng — xoay vòng theo thứ tự để con đường có nhịp màu. */
const STAGE_ART: ((p: FlatArtProps) => ReactNode)[] = [ChatArt, CardsArt, BookArt, MicArt, BulbArt, GameArt, PeopleArt, ChartArt];
const STAGE_TINT = ['#FDE3D6', '#FDF0C4', '#EFE4FB', '#EEF2CC', '#E8E6FB', '#DDEFF8', '#D9F1EC', '#E6E7FC'];

interface LevelTheme {
  /** Tên mùa — mỗi trình độ một "mùa" như mẫu Your course. */
  season: string;
  bg: string;
  road: string;
  /** Cảnh vật lấp chỗ trống, xếp lần lượt bên đối diện mỗi chặng. */
  decor: ReactNode[];
}

const LEVEL_THEMES: Record<string, LevelTheme> = {
  A1: {
    season: 'Mùa xuân', bg: '#DCF0DA', road: '#8FD1AE',
    decor: [<Pond key="p" size={150} />, <TreeRound key="t" size={70} />, <House key="h" size={120} />, <Flower key="f" size={34} />, <Mushroom key="m" size={44} />],
  },
  A2: {
    season: 'Mùa hè', bg: '#FCEFC2', road: '#F4CF74',
    decor: [<SunFlat key="s" size={70} />, <TreeTall key="t" size={48} leaf="#F0866A" />, <Mushroom key="m" size={48} />, <Bench key="b" size={80} />, <TreeRound key="r" size={66} leaf="#7CB342" />],
  },
  B1: {
    season: 'Mùa thu', bg: '#FBE2D3', road: '#F2B68E',
    decor: [<TreeTall key="t" size={50} leaf="#E8823A" />, <House key="h" size={118} wall="#C9563C" />, <Bench key="b" size={78} />, <TreeRound key="r" size={66} leaf="#E9A23B" />, <Mushroom key="m" size={44} />],
  },
  B2: {
    season: 'Mùa đông', bg: '#DCEEF8', road: '#FFFFFF',
    decor: [<Mountains key="mo" size={170} snow />, <Pine key="p" size={56} snow />, <Snowman key="s" size={52} />, <House key="h" size={112} wall="#C94A40" />, <Pine key="p2" size={46} snow />],
  },
  C1: {
    season: 'Núi cao', bg: '#E8E1FA', road: '#C8B6F2',
    decor: [<Mountains key="mo" size={170} />, <Pine key="p" size={54} />, <Cloud key="c" size={110} />, <TreeRound key="t" size={62} leaf="#5E9E6E" />],
  },
  C2: {
    season: 'Đỉnh núi', bg: '#EFE8DF', road: '#DDCBB8',
    decor: [<Mountains key="mo" size={170} snow />, <Pine key="p" size={54} snow />, <Cloud key="c" size={110} />],
  },
};
const FALLBACK_THEME = LEVEL_THEMES.A1;

const LANES = [27, 73];
const ROW_H = 196;
const CARD_W = 140;

/** Một chặng = một "cuốn sách" trên bản đồ: bìa minh hoạ + tên + huy hiệu trạng thái. */
function StageBook({ stage, onOpen }: { stage: RoadmapStage; onOpen: (s: RoadmapStage) => void }) {
  const locked = stage.state === 'locked';
  const done = stage.state === 'mastered' && !stage.is_skipped;
  const i = (stage.order_index - 1 + STAGE_ART.length) % STAGE_ART.length;
  const Art = STAGE_ART[i];
  // Bug #1: % cũ đo trên CẢ chặng trong khi chặng xong ở ~80%, nên "32/50" và
  // thanh không khớp nhau. Giờ thanh đo tới ĐÍCH qua chặng, chữ ghi số từ.
  const needed = stage.items_needed || stage.items_total;
  const goalPct = needed > 0 ? Math.min(100, (stage.items_mastered / needed) * 100) : 0;
  const learningPct = needed > 0
    ? Math.min(100 - goalPct, ((stage.items_learning ?? 0) / needed) * 100) : 0;
  const left = Math.max(needed - stage.items_mastered, 0);
  const label = locked
    ? `${stage.title}: chưa mở - học xong chặng trước nhé`
    : done ? `${stage.title}: đã xong, xem tổng kết`
      : `${stage.title}: đạt ${stage.items_mastered}/${needed} từ để qua chặng, còn ${left} từ - bấm để học`;
  return (
    <Box
      component="button"
      type="button"
      disabled={locked}
      onClick={() => onOpen(stage)}
      aria-label={label}
      sx={{
        position: 'relative', width: CARD_W, p: 0.75, pb: 1, border: 0, font: 'inherit', textAlign: 'left',
        bgcolor: SURFACE, borderRadius: '18px', cursor: locked ? 'default' : 'pointer',
        boxShadow: stage.is_recommended ? `0 0 0 4px ${PRIMARY}, 0 8px 20px rgba(74,52,36,0.16)` : '0 6px 16px rgba(74,52,36,0.12)',
        transition: 'transform 0.12s ease',
        '&:hover': { transform: locked ? 'none' : 'translateY(-3px)' },
        '&:focus-visible': { outline: `3px solid ${INK}`, outlineOffset: 3 },
      }}
    >
      <Box sx={{ height: 86, borderRadius: '13px', bgcolor: locked ? '#EAE3DB' : STAGE_TINT[i], display: 'grid', placeItems: 'center', filter: locked ? 'grayscale(1)' : 'none', opacity: locked ? 0.7 : 1 }}>
        <Art size={64} />
      </Box>
      <Typography sx={{ mt: 0.75, px: 0.5, fontWeight: 900, fontSize: 13.5, lineHeight: 1.25, color: locked ? '#A69A8F' : INK, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', minHeight: 34 }}>
        {stage.title}
      </Typography>
      <Box sx={{ px: 0.5, mt: 0.5, display: 'flex', alignItems: 'center', gap: 0.75 }}>
        {!locked && !done ? (
          <>
            <Box sx={{ flexGrow: 1, height: 6, borderRadius: 999, bgcolor: '#EDE3D9', overflow: 'hidden', display: 'flex' }}>
              <Box sx={{ width: `${Math.max(3, goalPct)}%`, height: '100%', bgcolor: PRIMARY }} />
              <Box sx={{ width: `${learningPct}%`, height: '100%', bgcolor: '#A8DDB5' }} />
            </Box>
            <Typography sx={{ fontSize: 11.5, fontWeight: 900, color: MUTED, whiteSpace: 'nowrap' }}
                        title={`Thuộc ${needed} từ là qua chặng`}>
              {stage.items_mastered}/{needed}
            </Typography>
          </>
        ) : (
          <Typography sx={{ fontSize: 12, fontWeight: 800, color: done ? PRIMARY_TEXT : '#A69A8F' }}>
            {done ? 'Đã xong' : `${stage.items_total} từ`}
          </Typography>
        )}
      </Box>
      {done && <CheckBadge size={32} sx={{ position: 'absolute', top: -10, right: -10 }} />}
      {locked && (
        <Box sx={{ position: 'absolute', top: -10, right: -10, width: 32, height: 32, borderRadius: '50%', bgcolor: FLAT.red, border: '3px solid #FFFFFF', display: 'grid', placeItems: 'center', color: '#FFFFFF' }}>
          <LockIcon size={15} />
        </Box>
      )}
    </Box>
  );
}

/**
 * Bản đồ phong cảnh theo trình độ — như mẫu "Your course" chủ dự án gửi: tab
 * mỗi trình độ (A1, A2…) là một "tầng", mỗi tầng một mùa với cảnh riêng; con
 * đường có vạch kẻ giữa uốn qua các chặng (cuốn sách), cảnh vật lấp chỗ trống.
 */
function ScenicMap({ stages, onOpen }: { stages: RoadmapStage[]; onOpen: (s: RoadmapStage) => void }) {
  const levels = [...new Set(stages.map((s) => s.cefr_level))];
  const preferred = stages.find((s) => s.is_recommended)?.cefr_level
    ?? stages.find((s) => s.state !== 'mastered')?.cefr_level ?? levels[0];
  const [picked, setPicked] = useState<string | null>(null);
  const level = picked && levels.includes(picked) ? picked : preferred;
  const theme = LEVEL_THEMES[level] ?? FALLBACK_THEME;
  const rows = stages.filter((s) => s.cefr_level === level);

  const top = 64;
  const height = top + rows.length * ROW_H + 24;
  const pts = rows.map((_, i) => ({ x: LANES[i % 2], y: top + i * ROW_H + 70 }));
  // Đường vào từ mép trên và đi ra mép dưới — như con đường chạy tiếp sang tầng sau.
  const all = [{ x: LANES[0] - 22, y: 0 }, ...pts, { x: LANES[(rows.length) % 2], y: height }];
  const d = all.reduce((acc, p, i) => {
    if (i === 0) return `M ${p.x} ${p.y}`;
    const prev = all[i - 1];
    const k = (p.y - prev.y) * 0.55;
    return `${acc} C ${prev.x} ${prev.y + k}, ${p.x} ${p.y - k}, ${p.x} ${p.y}`;
  }, '');

  return (
    <Box sx={{ maxWidth: 640, mx: 'auto', mb: 2 }}>
      {/* Tab trình độ ("tầng") */}
      <Box role="tablist" aria-label="Trình độ" sx={{ display: 'flex', gap: 0.75, px: 1, overflowX: 'auto' }}>
        {levels.map((lv) => {
          const on = lv === level;
          const th = LEVEL_THEMES[lv] ?? FALLBACK_THEME;
          const list = stages.filter((s) => s.cefr_level === lv);
          const doneCount = list.filter((s) => s.state === 'mastered').length;
          return (
            <Box
              key={lv}
              component="button"
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setPicked(lv)}
              sx={{
                flex: '1 0 auto', minWidth: 92, px: 1.5, pt: 1.25, pb: on ? 1.5 : 1.25, mt: on ? 0 : 0.75,
                border: 0, font: 'inherit', cursor: 'pointer', textAlign: 'center',
                borderRadius: '18px 18px 0 0', bgcolor: on ? th.bg : SURFACE, color: on ? INK : '#A69A8F',
                boxShadow: on ? 'none' : SOFT_SHADOW,
              }}
            >
              <Typography sx={{ fontWeight: 900, fontSize: 15.5, lineHeight: 1.1, color: 'inherit' }}>{lv}</Typography>
              <Typography sx={{ fontWeight: 800, fontSize: 12, color: on ? MUTED : '#B8ADA2', whiteSpace: 'nowrap' }}>
                {th.season} · {doneCount}/{list.length}
              </Typography>
            </Box>
          );
        })}
      </Box>

      <Box sx={{ position: 'relative', height, borderRadius: '28px', bgcolor: theme.bg, overflow: 'hidden' }}>
        {/* Cảnh nền: mây, bụi cây, hoa rải rác — cho bản đồ đỡ trống như mẫu */}
        <Cloud size={96} color="rgba(255,255,255,0.75)" sx={{ position: 'absolute', top: 18, right: 24 }} />
        <Cloud size={64} color="rgba(255,255,255,0.6)" sx={{ position: 'absolute', top: ROW_H + 40, left: 12 }} />
        <Bush size={74} color="rgba(62,158,98,0.55)" sx={{ position: 'absolute', bottom: -4, left: 14 }} />
        <Bush size={56} color="rgba(62,158,98,0.45)" sx={{ position: 'absolute', bottom: -4, right: 18 }} />
        {rows.map((_, i) => (
          <Flower key={`f${i}`} size={18} color={i % 2 ? FLAT.yellow : FLAT.pink}
            sx={{ position: 'absolute', top: top + i * ROW_H + 150, left: `${50 + (i % 2 ? -6 : 6)}%` }} />
        ))}
        <Box component="svg" viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" aria-hidden
          sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
          <path d={d} fill="none" stroke={theme.road} strokeWidth="40" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
          <path d={d} fill="none" stroke={theme.road === '#FFFFFF' ? '#C9DCE8' : '#FFFFFF'} strokeWidth="3" strokeDasharray="12 12" strokeLinecap="round" vectorEffect="non-scaling-stroke" opacity="0.85" />
        </Box>

        {rows.map((stage, i) => {
          const p = pts[i];
          const other = LANES[(i + 1) % 2];
          const decor = theme.decor[i % theme.decor.length];
          return (
            <Box key={stage.id}>
              {/* cảnh vật bên đối diện */}
              <Box aria-hidden sx={{ position: 'absolute', left: `${other}%`, top: p.y - 10, transform: 'translate(-50%, -50%)', opacity: 0.95 }}>
                {decor}
              </Box>
              <Box sx={{ position: 'absolute', left: `${p.x}%`, top: p.y, transform: 'translate(-50%, -50%)', display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 1 }}>
                {stage.is_recommended && (
                  <Box sx={{ mb: 0.75, px: 1.25, py: 0.25, borderRadius: 999, bgcolor: INK, color: '#FFFFFF', fontSize: 12.5, fontWeight: 900, whiteSpace: 'nowrap' }}>
                    Bạn ở đây
                  </Box>
                )}
                <StageBook stage={stage} onOpen={onOpen} />
                {stage.is_recommended && (
                  <Button variant="contained" size="small" onClick={() => onOpen(stage)} sx={{ mt: 1, px: 2.5, boxShadow: '0 3px 0 rgba(0,0,0,0.12)' }}>
                    {stage.user_word_set_id ? 'Học tiếp' : 'Vào học'}
                  </Button>
                )}
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
}

/** UC-85 — thẻ đề xuất nâng trình độ, chỉ hiện khi có đề xuất đang chờ.
 *
 * Cố tình nêu rõ bằng chứng (số chặng, số từ) thay vì chỉ hỏi "có nâng không"
 * — quyết định là của người học nên họ phải thấy căn cứ. */
function LevelUpCard() {
  const { data } = useLevelUpStatus();
  const decide = useDecideLevelUp();

  const suggestion = data?.suggestion;
  if (!suggestion) return null;

  return (
    <Box sx={{ ...CARD_SX, p: { xs: 2.5, sm: 3 }, mb: 2.5, display: 'flex', gap: 2.5, alignItems: 'center' }}>
      <Box sx={{ display: { xs: 'none', sm: 'block' } }}><TrophyArt size={88} /></Box>
      <Box sx={{ minWidth: 0 }}>
        <Typography sx={{ fontWeight: 900, fontSize: 13, color: PRIMARY_TEXT, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Đủ điều kiện lên trình
        </Typography>
        <Typography variant="h6" sx={{ fontWeight: 900 }}>
          Bạn đã sẵn sàng lên {suggestion.to_level}
        </Typography>
        <Typography variant="body2" sx={{ color: MUTED, mt: 0.5, maxWidth: 560 }}>
          Bạn đã học xong cả {data.stages_total} chặng mức {suggestion.from_level}, trung bình nhớ khoảng{' '}
          {Math.round(suggestion.avg_mastery * 100)}% trong {suggestion.items_considered} từ. Lên {suggestion.to_level} thì
          lộ trình sẽ làm lại từ mức mới; giữ mức hiện tại thì mọi thứ không đổi.
        </Typography>
        <Box sx={{ display: 'flex', gap: 1.25, mt: 2, flexWrap: 'wrap' }}>
          <Button
            variant="contained" disabled={decide.isPending}
            onClick={() => decide.mutate({ id: suggestion.id, decision: 'accept' })}
          >
            Lên {suggestion.to_level}
          </Button>
          <Button
            variant="outlined" disabled={decide.isPending}
            onClick={() => decide.mutate({ id: suggestion.id, decision: 'decline' })}
          >
            Giữ mức hiện tại
          </Button>
        </Box>
      </Box>
    </Box>
  );
}

function Roadmap() {
  const navigate = useNavigate();
  const { data, isLoading, isError } = useRoadmap();
  // Bản đồ cần cả thư viện: lộ trình chỉ có 6 từ mỗi chặng và hầu hết chặng
  // chưa tải về, vẽ riêng nó thì bản đồ quá thưa.
  const courses = useCourseProgress();
  const placement = usePlacementStatus();
  const download = useDownloadStageSet();
  const [snack, setSnack] = useState<string | null>(null);
  const [summaryStageId, setSummaryStageId] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'stepper' | 'map'>('stepper');

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (isError || !data) return <Alert severity="error">Không tải được lộ trình.</Alert>;

  const openStage = (stage: RoadmapStage) => {
    if (stage.state === 'locked') return;

    // Chặng đã có bản sao trong thư viện -> vào thẳng
    if (stage.user_word_set_id) {
      const done = stage.state === 'mastered' && !stage.is_skipped;
      // Chặng đã xong thì mở bảng tổng kết thay vì đá sang trang khác — người
      // học vừa hoàn thành cần biết mình nắm được gì, còn hổng chỗ nào.
      if (done) {
        setSummaryStageId(stage.id);
        return;
      }
      navigate(`/word-sets/${stage.user_word_set_id}/study/dkt_smart`);
      return;
    }

    // Chưa tải: tải bộ từ về thư viện (UC-21) rồi vào học ngay
    download.mutate(stage.word_set_id, {
      onSuccess: (ws) => navigate(`/word-sets/${ws.id}/study/dkt_smart`),
      onError: (e) => setSnack(e instanceof ApiError ? e.message : 'Không tải được bộ từ vựng của chặng.'),
    });
  };


  // Đi tới đâu trên đường: mốc cuối cùng đã hoàn thành (hoặc đang được gợi ý)

  const { skippedStages, personalStages } = splitRoadmapStages(data.stages, data.entry_level);
  const totalMastered = personalStages.filter((s) => s.state === 'mastered').length;
  const overallPct = personalStages.length
    ? Math.round((totalMastered / personalStages.length) * 100) : 0;

  return (
    <Box>
      <PageHeader
        title="Lộ trình học"
        subtitle="Học lần lượt từng chặng, bắt đầu từ “Bạn ở đây”."
      />

      <LevelUpCard />

      {/* Trái: tiến độ luôn trong tầm mắt. Phải: con đường cuộn theo trang (2026-11-04). */}
      <Box sx={{
        display: 'grid', gap: 2.5, alignItems: 'start',
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '300px minmax(0, 1fr)' },
      }}>
      {/* Trình độ + tiến độ + chế độ xem — một thẻ gọn */}
      <Box sx={{ ...CARD_SX, p: { xs: 2, sm: 2.5 }, display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'stretch', position: { md: 'sticky' }, top: { md: 16 } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}>
          <Box sx={{ px: 1.5, py: 0.5, bgcolor: FLAT.green, color: '#FFFFFF', borderRadius: 999, fontWeight: 900, fontSize: 18 }}>
            {data.entry_level}
          </Box>
          {data.target_level && (
            <>
              <Box sx={{ width: 28, height: 6, borderRadius: 999, bgcolor: FLAT.path, opacity: 0.6 }} />
              <Box sx={{ px: 1.5, py: 0.5, bgcolor: '#FDEFC4', borderRadius: 999, fontWeight: 900, fontSize: 18 }}>
                {data.target_level}
              </Box>
            </>
          )}
        </Box>
        <Box>
          <Typography sx={{ fontWeight: 900, mb: 0.75 }}>
            Đã xong {totalMastered}/{personalStages.length} chặng
          </Typography>
          <LinearProgress variant="determinate" value={overallPct} sx={{ height: 12 }} />
          <Typography sx={{ fontSize: 13, fontWeight: 700, color: MUTED, mt: 0.75 }}>
            {placement.data?.has_placement
              ? `Trình độ ${data.entry_level} lấy từ bài kiểm tra đầu vào - các chặng thấp hơn đã được bỏ qua.`
              : 'Bạn chưa làm bài kiểm tra đầu vào nên đang bắt đầu từ A1.'}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Button variant={placement.data?.has_placement ? 'outlined' : 'contained'} size="small"
                  onClick={() => navigate('/placement')}>
            {placement.data?.has_placement ? 'Kiểm tra lại trình độ' : 'Làm bài kiểm tra đầu vào'}
          </Button>
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            size="small"
            onChange={(_, next) => { if (next) setViewMode(next); }}
            aria-label="Chế độ xem lộ trình"
          >
            <ToggleButton value="stepper" sx={{ py: 0.5, fontSize: 14 }}>Con đường</ToggleButton>
            <ToggleButton value="map" sx={{ py: 0.5, fontSize: 14 }}>Bản đồ từ</ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      <Box sx={{ minWidth: 0 }}>
      {skippedStages.length > 0 && (
        <Box component="details" sx={{ mb: 2 }}>
          <Typography component="summary" sx={{ cursor: 'pointer', mb: 2, fontWeight: 800, color: MUTED }}>
            Các chặng đã bỏ qua theo bài kiểm tra ({skippedStages[0].cefr_level}-{skippedStages[skippedStages.length - 1].cefr_level})
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>Phần này không tính vào tiến độ lộ trình.</Typography>
          <ScenicMap stages={skippedStages} onOpen={openStage} />
        </Box>
      )}
      {data.stages.length === 0 ? (
        <EmptyState
          title="Chưa có chặng nào trong lộ trình"
          description="Làm bài kiểm tra đầu vào hoặc chọn bộ từ ở Khám phá."
          action={
            <Button variant="contained" onClick={() => navigate('/discover')}>
              Khám phá bộ từ vựng
            </Button>
          }
        />
      ) : viewMode === 'stepper' ? (
        <ScenicMap stages={personalStages} onOpen={openStage} />
      ) : (
        <SkillMap
          stages={personalStages}
          sets={(courses.data ?? []).filter((set) =>
            !skippedStages.some((stage) => stage.user_word_set_id === set.id))}
          entryLevel={data.entry_level}
          targetLevel={data.target_level}
          onOpenStage={openStage}
        />
      )}
      {personalStages.length > 0 && viewMode === 'stepper' && (
        <Box sx={{ textAlign: 'center' }}>
          <Button onClick={() => openStage({ ...personalStages[0], state: 'current' })} sx={{ color: MUTED }}>
            Học lại từ chặng đầu mức {data.entry_level}
          </Button>
        </Box>
      )}
      </Box>
      </Box>

      <StageSummaryDialog
        stageId={summaryStageId}
        onClose={() => setSummaryStageId(null)}
        onReviewWeak={() => navigate('/reviews/study?source=weak')}
      />

      <Snackbar open={snack !== null} autoHideDuration={4000}
                onClose={() => setSnack(null)} message={snack ?? ''} />
    </Box>
  );
}

export default Roadmap;
