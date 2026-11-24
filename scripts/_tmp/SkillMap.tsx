import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Typography from '@mui/material/Typography';
import { useQueries } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { CourseProgress } from '../api/home';
import type { RoadmapStage } from '../api/roadmap';
import type { RecommendedItem } from '../types/wordSet';
import {
  ACCENT_FONT,
  INK,
  LABEL_FONT,
  MUTED,
  PRIMARY,
  PRIMARY_LIGHT,
  PRIMARY_TEXT,
  SURFACE,
  SOFT_SHADOW,
  LINE,
} from '../theme/theme';

/* Mặt bản đồ theo bảng màu navy + xanh pastel (2026-10-28): nền xanh rất nhạt,
 * nét nối navy mờ, node trắng viền navy — bỏ hẳn viền mực + bóng đổ cứng và
 * thanh tiêu đề vàng ".EXE" của bản retro cũ. */
const MAP_BG = '#F2F7FC';
const NAVY_SOFT = 'rgba(30, 58, 110, 0.10)';
const LOCKED_FILL = '#EEF1F5';
const LOCKED_INK = '#9AA6B8';
import { TrophyArt } from './FlatArt';
import { KidBin } from './FlatScene';
import { ExpandIcon } from './icons';

/**
 * Bản đồ học tập dạng tỏa tròn, kéo–thả và phóng to được.
 *
 * Hai tầng:
 *   - vòng trong  = "nhóm": 6 chặng lộ trình + các bộ từ khác trong thư viện,
 *   - vòng ngoài  = từng TỪ của nhóm đó, tô màu theo mastery do DKT tính.
 *
 * Vì sao phải gộp cả hai nguồn: lộ trình chỉ có 6 từ mỗi chặng và 5/6 chặng
 * chưa tải về thư viện (bộ gốc trả 404 theo Q1 — chỉ đọc được bộ mình sở hữu),
 * nên vẽ riêng lộ trình thì bản đồ chỉ có 12 node, thưa hơn cả bản đồ cũ.
 * Ghép thêm thư viện mới đủ mật độ để việc phóng to có ý nghĩa.
 *
 * Mastery đi theo THANG LIÊN TỤC (đỏ → cam → vàng → xanh), khác với chú thích trạng
 * thái chặng ở tab danh sách: ở đây mỗi chấm là một từ, không phải một chặng.
 */

const R_GROUP = 210;       // bán kính vòng node nhóm
const R_ITEM_BASE = 330;   // vành trong cùng của các từ, tính từ TÂM
const GROUP_R = 34;        // bán kính node nhóm
const ITEM_R = 7;          // bán kính node từ

type Group = {
  key: string;
  label: string;
  kind: 'stage' | 'set' | 'band';
  /** Bộ từ đọc được trong thư viện; null = chặng chưa tải, hoặc node cụm. */
  wordSetId: number | null;
  cefr?: string;
  state?: string;
  isCurrent?: boolean;
  mastered: number;
  total: number;
  /** Chỉ với kind='band': mức CEFR của cụm và số bộ bên trong. */
  bandKey?: string;
  setCount?: number;
};

/** Thứ tự hiển thị các cụm. 'NA' gom những bộ không khai mức CEFR. */
const BAND_ORDER = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'NA'];
const BAND_LABEL: Record<string, string> = {
  A1: 'A1', A2: 'A2', B1: 'B1', B2: 'B2', C1: 'C1', C2: 'C2', NA: 'Chưa xếp mức',
};

/** Thang màu poster: đỏ (quên) → cam → vàng (đang nhớ) → xanh (nắm vững). */
const MASTERY_STOPS: [number, [number, number, number]][] = [
  [0, [232, 51, 46]],
  [0.35, [255, 118, 82]],
  [0.6, [255, 225, 77]],
  [0.8, [123, 217, 87]],
  [1, [47, 158, 68]],
];

/** Năm ô màu cho chú thích (trùng các mốc của thang). */
const MASTERY_SWATCHES = MASTERY_STOPS.map(([, c]) => `rgb(${c[0]}, ${c[1]}, ${c[2]})`);

function masteryColor(m: number): string {
  const t = Math.max(0, Math.min(1, m));
  for (let i = 0; i < MASTERY_STOPS.length - 1; i++) {
    const [p0, c0] = MASTERY_STOPS[i];
    const [p1, c1] = MASTERY_STOPS[i + 1];
    if (t >= p0 && t <= p1) {
      const f = p1 === p0 ? 0 : (t - p0) / (p1 - p0);
      const c = c0.map((v, j) => Math.round(v + (c1[j] - v) * f));
      return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
    }
  }
  return MASTERY_SWATCHES[MASTERY_SWATCHES.length - 1];
}

export default function SkillMap({
  stages,
  sets,
  entryLevel,
  targetLevel,
  onOpenStage,
}: {
  stages: RoadmapStage[];
  sets: CourseProgress[];
  entryLevel: string;
  targetLevel: string | null;
  onOpenStage: (stage: RoadmapStage) => void;
}) {
  // Cụm CEFR đang được xoè ra; null = tất cả đang gom.
  const [openBand, setOpenBand] = useState<string | null>(null);

  // ── Gom nhóm: 6 chặng lộ trình + MỘT node cho mỗi mức CEFR ──
  //
  // Trước đây mỗi bộ trong thư viện là một node. Với bộ chủ đề cũ (8 bộ) thì ổn;
  // với bộ nền thì thư viện có 77 bộ -> 83 node chia nhau 360°, mỗi node được
  // hơn 4° nên nhãn chồng lên nhau thành một vệt chữ, và 83 truy vấn
  // /recommend bắn song song ngay khi mở tab.
  //
  // Gom theo mức CEFR vì đó ĐÚNG là cách bộ nền được chia (nguồn × mức × tần
  // suất), nên cụm trùng khít với cấu trúc dữ liệu chứ không phải một cách
  // nhóm áp từ ngoài vào. Bấm một cụm mới xoè ra các bộ của mức đó — và chỉ
  // lúc đó mới tải từ của chúng.
  const groups = useMemo<Group[]>(() => {
    const claimed = new Set(
      stages.map((s) => s.user_word_set_id).filter((v): v is number => v != null),
    );
    // One node per CEFR level; open the recommended/first unfinished stage.
    const representatives = BAND_ORDER.flatMap((level) => {
      const members = stages.filter((s) => s.cefr_level === level);
      if (!members.length) return [];
      return [members.find((s) => s.is_recommended)
        ?? members.find((s) => s.state !== 'mastered') ?? members[0]];
    });
    const fromStages: Group[] = representatives.map((s) => ({
      key: `stage-${s.id}`,
      label: `${s.cefr_level} · ${stages.filter((stage) => stage.cefr_level === s.cefr_level).length} chặng`,
      kind: 'stage',
      wordSetId: s.user_word_set_id,
      cefr: s.cefr_level,
      state: s.state,
      isCurrent: s.is_recommended,
      mastered: stages.filter((stage) => stage.cefr_level === s.cefr_level)
        .reduce((sum, stage) => sum + stage.items_mastered, 0),
      total: stages.filter((stage) => stage.cefr_level === s.cefr_level)
        .reduce((sum, stage) => sum + stage.items_total, 0),
    }));

    const loose = sets.filter((c) => !claimed.has(c.id));
    const byBand = new Map<string, CourseProgress[]>();
    for (const c of loose) {
      const band = c.cefr_level && BAND_ORDER.includes(c.cefr_level) ? c.cefr_level : 'NA';
      const bucket = byBand.get(band);
      if (bucket) bucket.push(c);
      else byBand.set(band, [c]);
    }

    const fromBands: Group[] = [];
    for (const band of BAND_ORDER) {
      const members = byBand.get(band);
      if (!members || members.length === 0) continue;
      if (openBand === band) {
        // Cụm đang mở: từng bộ thành một node riêng, có từ.
        for (const c of members) {
          fromBands.push({
            key: `set-${c.id}`,
            label: c.name,
            kind: 'set',
            wordSetId: c.id,
            cefr: c.cefr_level ?? undefined,
            mastered: c.mastered_items,
            total: c.total_items,
          });
        }
      } else {
        fromBands.push({
          key: `band-${band}`,
          label: `${BAND_LABEL[band]} · ${members.length} bộ`,
          kind: 'band',
          wordSetId: null,
          cefr: band === 'NA' ? undefined : band,
          bandKey: band,
          setCount: members.length,
          mastered: members.reduce((a, c) => a + c.mastered_items, 0),
          total: members.reduce((a, c) => a + c.total_items, 0),
        });
      }
    }
    return [...fromStages, ...fromBands];
  }, [stages, sets, openBand]);

  // ── Tải từ của từng nhóm đọc được; chạy song song, hiện dần khi có ──
  const itemQueries = useQueries({
    queries: groups.map((g) => ({
      queryKey: ['word-sets', g.wordSetId, 'map-items'],
      queryFn: () =>
        apiGet<RecommendedItem[]>(`/api/v1/word-sets/${g.wordSetId}/recommend?limit=200`),
      enabled: g.wordSetId != null,
      staleTime: 60_000,
    })),
  });

  // ── Toạ độ ──
  // Mỗi nhóm được một "múi" quạt rộng theo TỈ LỆ SỐ TỪ, không chia đều: bộ 40
  // từ cần chỗ gấp mấy lần chặng 6 từ, chia đều thì cụm lớn tràn sang cụm bên
  // cạnh còn cụm nhỏ để trống một mảng.
  // Trọng số lấy từ `total` (biết ngay từ đầu) chứ không phải số từ đã tải, để
  // bố cục không nhảy khi các truy vấn về rải rác.
  const layout = useMemo(() => {
    // Sàn 14: chặng chỉ có 6 từ, để đúng trọng số thật thì 6 múi chặng dồn sát
    // nhau và nhãn chồng lên nhau. Sàn này mua chỗ cho cái nhãn, không phải cho
    // số từ.
    // Node cụm KHÔNG vẽ chấm từ, nên trọng số của nó chỉ cần đủ chỗ cho cái
    // nhãn. Lấy theo `total` thật thì cụm A1 (17 bộ, ~850 từ) chiếm gần hết
    // vòng tròn trong khi không hiện chấm nào.
    const weights = groups.map((g) => (g.kind === 'band' ? 70 : Math.max(24, g.total)));
    const totalW = weights.reduce((a, b) => a + b, 0) || 1;
    let acc = 0;
    return groups.map((g, i) => {
      const a0 = (acc / totalW) * Math.PI * 2 - Math.PI / 2;
      acc += weights[i];
      const a1 = (acc / totalW) * Math.PI * 2 - Math.PI / 2;
      const mid = (a0 + a1) / 2;
      const gx = Math.cos(mid) * R_GROUP;
      const gy = Math.sin(mid) * R_GROUP;

      const items = (itemQueries[i]?.data ?? []) as RecommendedItem[];
      // Chừa hai mép múi để hai cụm cạnh nhau không dính vào nhau.
      const pad = (a1 - a0) * 0.08;
      const from = a0 + pad;
      const span = Math.max(0.06, a1 - a0 - pad * 2);
      // Số chỗ vừa trên một vành = độ dài cung / khoảng cách tối thiểu giữa 2 chấm.
      const perRing = Math.max(3, Math.round((span * R_ITEM_BASE) / 26));
      const pts = items.map((it, j) => {
        const ring = R_ITEM_BASE + Math.floor(j / perRing) * 34;
        const slot = j % perRing;
        const ia = from + ((slot + 0.5) / perRing) * span;
        // Toả từ TÂM ra chứ không từ node nhóm: giữ các chấm nằm gọn trong múi.
        return { item: it, x: Math.cos(ia) * ring, y: Math.sin(ia) * ring };
      });
      return { group: g, x: gx, y: gy, items: pts };
    });
  }, [groups, itemQueries]);

  // ── Khung nhìn: k = mức phóng, (tx,ty) = độ dời ──
  const wrapRef = useRef<HTMLDivElement | null>(null);
  // Màn hẹp (điện thoại): khung thấp và hẹp nên mức "toàn cảnh" 0.78 làm chấm
  // từ bé như hạt bụi — mở sẵn ở mức phóng lớn hơn.
  const fitK = typeof window !== 'undefined' && window.innerWidth < 600 ? 1.5 : 0.78;
  const [view, setView] = useState({ k: fitK, tx: 0, ty: 0 });
  // Mở trọn cửa sổ: bản đồ càng rộng càng dễ đọc, mà khung trong trang thì luôn
  // bị header + tab ăn mất một khoảng.
  const [full, setFull] = useState(false);
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);

  const clampK = (k: number) => Math.max(0.28, Math.min(2.8, k));

  const onWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const box = wrapRef.current?.getBoundingClientRect();
    if (!box) return;
    // Phóng quanh vị trí con trỏ, không phải quanh tâm khung: kéo tới đâu
    // phóng tới đó mới theo được thứ đang nhìn.
    const px = e.clientX - box.left - box.width / 2;
    const py = e.clientY - box.top - box.height / 2;
    setView((v) => {
      const k = clampK(v.k * (e.deltaY < 0 ? 1.12 : 1 / 1.12));
      const r = k / v.k;
      return { k, tx: px - (px - v.tx) * r, ty: py - (py - v.ty) * r };
    });
  }, []);

  const onPointerDown = (e: React.PointerEvent) => {
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    setView((v) => ({ ...v, tx: d.tx + (e.clientX - d.x), ty: d.ty + (e.clientY - d.y) }));
  };
  const endDrag = () => {
    drag.current = null;
  };

  // Khung to hơn thì mức vừa khít cũng lớn hơn bản cũ.
  const fitAll = () => setView({ k: fitK, tx: 0, ty: 0 });

  // Esc thoát chế độ mở rộng — lớp phủ toàn cửa sổ mà không có lối ra bằng bàn
  // phím thì rất dễ mắc kẹt.
  useEffect(() => {
    if (!full) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFull(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [full]);

  /** Đưa chặng đang được gợi ý vào giữa khung. */
  const goCurrent = () => {
    const idx = layout.findIndex((l) => l.group.isCurrent);
    const target = idx >= 0 ? layout[idx] : layout[0];
    if (!target) return fitAll();
    const k = 1.15;
    setView({ k, tx: -target.x * k, ty: -target.y * k });
  };

  const loadedItems = layout.reduce((sum, l) => sum + l.items.length, 0);
  // isLoading chứ không isPending: truy vấn bị tắt (chặng khoá, cụm CEFR) ở
  // trạng thái pending mãi, làm chú thích kẹt "đang tải…".
  const loading = itemQueries.some((q) => q.isLoading);

  /** Màu node nhóm: chặng hiện tại navy đặc, cụm CEFR xanh nhạt, còn lại trắng. */
  const nodeFill = (g: Group): string => {
    if (g.state === 'locked') return LOCKED_FILL;
    if (g.isCurrent) return PRIMARY;
    if (g.kind === 'band') return PRIMARY_LIGHT;
    return SURFACE;
  };
  const nodeStroke = (g: Group): string => (g.state === 'locked' ? LOCKED_INK : PRIMARY);
  const nodeText = (g: Group): string => {
    if (g.state === 'locked') return LOCKED_INK;
    return g.isCurrent ? '#FFFFFF' : PRIMARY_TEXT;
  };

  // Nhãn chữ trên bản đồ: viền trắng dày phía sau để đọc được trên mọi nền.
  const labelStyle = { fontFamily: ACCENT_FONT, fontWeight: 800, paintOrder: 'stroke' } as const;


  return (
    <Box
      sx={{
        position: full ? 'fixed' : 'relative',
        ...(full && { inset: 12, zIndex: 1400 }),
        display: 'flex',
        flexDirection: 'column',
        borderRadius: '20px',
        border: `1px solid ${LINE}`,
        boxShadow: SOFT_SHADOW,
        bgcolor: SURFACE,
        overflow: 'hidden',
      }}
    >
      {/* Thanh tiêu đề cửa sổ + điều khiển */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          flexWrap: 'wrap',
          px: 1.5,
          py: 1,
          bgcolor: SURFACE,
          borderBottom: `1px solid ${LINE}`,
        }}
      >
        <Box sx={{ mr: 'auto', minWidth: 0 }}>
          <Typography sx={{ fontWeight: 900, fontSize: 12, lineHeight: 1.4, color: PRIMARY_TEXT, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            Bản đồ từ
          </Typography>
          <Typography sx={{ fontSize: 12.5, fontWeight: 700, color: MUTED, lineHeight: 1.3, whiteSpace: 'nowrap' }}>
            Mỗi chấm là một từ, tô màu theo mức nắm vững
          </Typography>
        </Box>
        <Button size="small" variant="outlined" onClick={() => setFull((v) => !v)} startIcon={<ExpandIcon size={15} />}>
          {full ? 'Thu nhỏ' : 'Mở rộng'}
        </Button>
        <Button size="small" variant="outlined" onClick={fitAll}>
          Toàn cảnh
        </Button>
        {openBand && (
          <Button size="small" variant="outlined" onClick={() => setOpenBand(null)}>
            Thu gọn {BAND_LABEL[openBand]}
          </Button>
        )}
        <Button size="small" variant="contained" onClick={goCurrent}>
          Về chặng hiện tại
        </Button>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            bgcolor: SURFACE,
            border: `1px solid ${LINE}`,
            borderRadius: 999,
            overflow: 'hidden',
          }}
        >
          <Box
            component="button"
            aria-label="Thu nhỏ"
            onClick={() => setView((v) => ({ ...v, k: clampK(v.k / 1.25) }))}
            sx={{ border: 0, bgcolor: 'transparent', cursor: 'pointer', px: 1.25, py: 0.25, fontSize: 18, fontWeight: 900, color: PRIMARY }}
          >
            −
          </Box>
          <Typography sx={{ fontFamily: LABEL_FONT, fontWeight: 700, fontSize: 14, lineHeight: 1, minWidth: 44, textAlign: 'center', color: INK }}>
            {Math.round(view.k * 100)}%
          </Typography>
          <Box
            component="button"
            aria-label="Phóng to"
            onClick={() => setView((v) => ({ ...v, k: clampK(v.k * 1.25) }))}
            sx={{ border: 0, bgcolor: 'transparent', cursor: 'pointer', px: 1.25, py: 0.25, fontSize: 18, fontWeight: 900, color: PRIMARY }}
          >
            +
          </Box>
        </Box>
      </Box>

      {/* Mặt bản đồ */}
      <Box
        ref={wrapRef}
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerLeave={endDrag}
        sx={{
          position: 'relative',
          flexGrow: 1,
          height: full ? 'auto' : { xs: 440, md: 'min(76vh, 820px)' },
          minHeight: full ? 0 : 440,
          cursor: drag.current ? 'grabbing' : 'grab',
          touchAction: 'none',
          // Nền xanh rất nhạt + lưới chấm mờ: đủ để định hướng khi kéo mà không
          // tranh màu với các chấm mastery.
          bgcolor: MAP_BG,
          backgroundImage: 'radial-gradient(rgba(30,58,110,0.10) 1.2px, transparent 1.2px)',
          backgroundSize: '28px 28px',
        }}
      >
        {/* Chú thích thang mastery — nhãn dán góc trái */}
        <Box
          sx={{
            position: 'absolute',
            left: 12,
            top: 12,
            zIndex: 2,
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            px: 1.25,
            py: 0.6,
            borderRadius: '10px',
            bgcolor: SURFACE,
            border: `1px solid ${LINE}`,
            boxShadow: SOFT_SHADOW,
            pointerEvents: 'none',
          }}
        >
          <Typography sx={{ fontSize: 13, fontWeight: 800, color: INK }}>Mức nắm vững</Typography>
          <Typography sx={{ fontSize: 12, fontWeight: 700, color: MUTED }}>thấp</Typography>
          <Box sx={{ display: 'flex', border: `1px solid ${LINE}`, borderRadius: '6px', overflow: 'hidden' }}>
            {MASTERY_SWATCHES.map((c) => <Box key={c} sx={{ width: 18, height: 12, bgcolor: c }} />)}
          </Box>
          <Typography sx={{ fontSize: 12, fontWeight: 700, color: MUTED }}>cao ·</Typography>
          <Typography sx={{ fontFamily: LABEL_FONT, fontWeight: 800, fontSize: 13, lineHeight: 1, color: PRIMARY_TEXT }}>
            {loading ? 'đang tải…' : `${loadedItems} từ`}
          </Typography>
        </Box>

        {/* viewBox lấy gốc (0,0) làm tâm khung, nên mọi toạ độ tính quanh gốc là
            khớp sẵn — không phải đo lại kích thước khung mỗi lần đổi cỡ cửa sổ. */}
        <Box
          component="svg"
          viewBox="-600 -420 1200 840"
          preserveAspectRatio="xMidYMid meet"
          sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', userSelect: 'none' }}
        >
          <g transform={`translate(${view.tx}, ${view.ty}) scale(${view.k})`}>
            {/* đường nối tâm → nhóm: nét mực, chặng khoá thì nét đứt */}
            {layout.map((l) => (
              <line
                key={`spine-${l.group.key}`}
                x1={0}
                y1={0}
                x2={l.x}
                y2={l.y}
                stroke={PRIMARY}
                strokeWidth={l.group.isCurrent ? 5 : 3}
                strokeDasharray={l.group.state === 'locked' ? '8 8' : undefined}
                strokeLinecap="round"
                opacity={l.group.isCurrent ? 0.9 : l.group.state === 'locked' ? 0.2 : 0.35}
              />
            ))}

            {/* nét nhóm → từ */}
            {layout.map((l) =>
              l.items.map((p) => (
                <line
                  key={`edge-${l.group.key}-${p.item.id}`}
                  x1={l.x}
                  y1={l.y}
                  x2={p.x}
                  y2={p.y}
                  stroke={PRIMARY}
                  strokeOpacity={0.12}
                  strokeWidth={1.2}
                />
              )),
            )}

            {/* node từ */}
            {layout.map((l) =>
              l.items.map((p) => (
                <g key={`item-${p.item.id}`}>
                  <title>
                    {`${p.item.word} - ${p.item.meaning} · nắm vững ${Math.round(p.item.mastery * 100)}%`}
                  </title>
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={p.item.in_band ? ITEM_R + 2.5 : ITEM_R}
                    fill={masteryColor(p.item.mastery)}
                    stroke={p.item.in_band ? PRIMARY : '#FFFFFF'}
                    strokeWidth={p.item.in_band ? 2.5 : 1.5}
                  />
                </g>
              )),
            )}

            {/* node nhóm */}
            {layout.map((l) => {
              const locked = l.group.state === 'locked';
              const r = l.group.kind === 'band' ? GROUP_R + 6 : GROUP_R;
              return (
                <g
                  key={l.group.key}
                  transform={`translate(${l.x}, ${l.y})`}
                  style={{
                    cursor:
                      l.group.kind === 'band' || (l.group.kind === 'stage' && !locked)
                        ? 'pointer'
                        : 'default',
                  }}
                  onClick={() => {
                    if (l.group.kind === 'band') {
                      setOpenBand(l.group.bandKey ?? null);
                      return;
                    }
                    if (l.group.kind !== 'stage' || locked) return;
                    const st = stages.find((s) => `stage-${s.id}` === l.group.key);
                    if (st) onOpenStage(st);
                  }}
                >
                  <title>
                    {l.group.kind === 'band'
                      ? `${l.group.label} - bấm để xem từng bộ (${l.group.mastered}/${l.group.total} từ nắm vững)`
                      : `${l.group.label} · ${l.group.mastered}/${l.group.total} từ nắm vững`}
                  </title>
                  {/* Quầng sáng quanh chặng hiện tại */}
                  {l.group.isCurrent && (
                    <>
                      <circle r={r + 16} fill={NAVY_SOFT} />
                      <circle r={r + 8} fill={SURFACE} />
                    </>
                  )}
                  {/* Vành đứt nét = node gom, bấm được để xoè */}
                  {l.group.kind === 'band' && (
                    <circle r={r + 9} fill="none" stroke={PRIMARY} strokeOpacity={0.45} strokeWidth={2} strokeDasharray="5 6" />
                  )}
                  {/* bóng mờ thay cho bóng đổ cứng */}
                  <circle cy={3} r={r + 1} fill="rgba(30,58,110,0.12)" />
                  <circle r={r} fill={nodeFill(l.group)} stroke={nodeStroke(l.group)} strokeWidth={l.group.isCurrent ? 0 : 2.5} />
                  {l.group.kind === 'band' ? (
                    <>
                      <text textAnchor="middle" y={-1} fill={nodeText(l.group)} style={{ ...labelStyle, fontWeight: 900, fontSize: 18 }}>
                        {l.group.cefr ?? 'Chưa xếp'}
                      </text>
                      <text textAnchor="middle" y={16} fill={nodeText(l.group)} style={{ ...labelStyle, fontSize: 13 }}>
                        {`${l.group.setCount} bộ`}
                      </text>
                    </>
                  ) : locked ? (
                    <g transform="translate(-9 -12)" fill="none" stroke={LOCKED_INK} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
                      <rect x={0} y={9} width={18} height={14} rx={3} fill="#FFFFFF" />
                      <path d="M4 9 V5 a5 5 0 0 1 10 0 V9" />
                    </g>
                  ) : (
                    <text textAnchor="middle" y={6} fill={nodeText(l.group)} style={{ ...labelStyle, fontWeight: 900, fontSize: 17 }}>
                      {l.group.cefr ?? l.group.total}
                    </text>
                  )}
                  {/* Bin đứng vẫy cạnh chặng hiện tại */}
                  {l.group.isCurrent && (
                    <foreignObject x={GROUP_R - 4} y={-GROUP_R - 58} width={74} height={74} style={{ overflow: 'visible' }}>
                      <KidBin size={52} pose="wave" />
                    </foreignObject>
                  )}
                  {/* Ở mức thu nhỏ, các nhãn nằm sát nhau thành một vệt chữ khó
                      đọc. Giấu đi cho sạch — phóng to là hiện lại. */}
                  {view.k >= 0.78 && (
                    <text
                      textAnchor="middle"
                      y={r + 24}
                      fill={l.group.state === 'locked' ? LOCKED_INK : INK}
                      stroke={MAP_BG}
                      strokeWidth={5}
                      style={{ ...labelStyle, fontSize: 14.5 }}
                    >
                      {l.group.label.length > 22 ? `${l.group.label.slice(0, 21)}…` : l.group.label}
                    </text>
                  )}
                </g>
              );
            })}

            {/* tâm: mục tiêu của người học — một chiếc cúp */}
            <g>
              <circle cy={3} r={59} fill="rgba(30,58,110,0.10)" />
              <circle r={58} fill={SURFACE} stroke={PRIMARY_LIGHT} strokeWidth={4} />
              <foreignObject x={-36} y={-50} width={72} height={72} style={{ overflow: 'visible' }}>
                <TrophyArt size={70} />
              </foreignObject>
              <rect x={-60} y={22} width={120} height={26} rx={13} fill={PRIMARY} />
              <text textAnchor="middle" y={41} fill="#FFFFFF" style={{ fontFamily: LABEL_FONT, fontWeight: 700, fontSize: 14 }}>
                {targetLevel ? `MỤC TIÊU ${targetLevel}` : `HIỆN TẠI ${entryLevel}`}
              </text>
            </g>
          </g>
        </Box>
      </Box>

      <Box sx={{ px: 2, py: 1.25, borderTop: `1px solid ${LINE}`, bgcolor: SURFACE }}>
        <Typography sx={{ fontSize: 13, fontWeight: 600, color: MUTED }}>
          Lăn chuột để phóng to · kéo để di chuyển · rê chuột lên một chấm để xem từ và
          mức nắm vững. Chấm viền đậm là từ vừa sức để học tiếp.
          {' '}Vòng tròn nét đứt là một <b>mức CEFR</b> đang gom nhiều bộ - bấm vào để xoè
          ra từng bộ của mức đó.
        </Typography>
      </Box>
    </Box>
  );
}
