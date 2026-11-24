import { useState } from 'react';
import type { KeyboardEvent, ReactNode } from 'react';
import Box from '@mui/material/Box';
import Rating from '@mui/material/Rating';
import Typography from '@mui/material/Typography';

import { API_BASE_URL } from '../api/client';
import { BookArt, BulbArt, CardsArt, ChatArt, GameArt, MicArt, PeopleArt } from './FlatArt';
import SetProgress from './SetProgress';
import { cardTone } from './WordCard';
import { CARD_SX, INK, MUTED, PRIMARY } from '../theme/theme';

interface WordSetCardProps {
  id: number;
  name: string;
  coverImageUrl?: string | null;
  description?: string | null;
  itemCount: number;
  masteredCount?: number;
  /** Đã học nhưng chưa thuộc — đoạn giữa của thanh tiến độ. */
  learningCount?: number;
  category?: string | null;
  difficulty?: string | null;
  isPublic?: boolean;
  ratingAvg?: number | null;
  ratingCount?: number;
  onOpen?: () => void;
  actions?: ReactNode;
}

/** Minh hoạ phẳng làm "bìa" khi bộ từ chưa có ảnh — chọn ổn định theo id. */
const COVER_ART = [CardsArt, BookArt, ChatArt, BulbArt, MicArt, GameArt, PeopleArt] as const;

const DIFFICULTY_LABEL: Record<string, string> = {
  beginner: 'Cơ bản',
  intermediate: 'Trung cấp',
  advanced: 'Nâng cao',
};

/**
 * Thẻ bộ từ phẳng (2026-10-26): khung bìa màu nhạt ổn định theo id với minh hoạ
 * tròn (hoặc ảnh bìa), tên, mô tả, thanh tiến độ 3 nấc (thuộc / đang học / chưa học). Mọi phần chữ khoá số
 * dòng để các thẻ trong lưới cao bằng nhau.
 */
function WordSetCard({
  id, name, coverImageUrl, description, itemCount, masteredCount, learningCount, category, difficulty, isPublic,
  ratingAvg, ratingCount, onOpen, actions,
}: WordSetCardProps) {
  const [, tint] = cardTone(id);
  const Art = COVER_ART[Math.abs(Math.trunc(id)) % COVER_ART.length];
  const [imgFailed, setImgFailed] = useState(false);
  const showImage = Boolean(coverImageUrl) && !imgFailed;
  const src = coverImageUrl?.startsWith('http') ? coverImageUrl : `${API_BASE_URL}${coverImageUrl ?? ''}`;
  const showProgress = masteredCount != null && itemCount > 0;

  const open = onOpen
    ? {
        role: 'button',
        tabIndex: 0,
        onClick: onOpen,
        onKeyDown: (e: KeyboardEvent) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(); } },
      }
    : {};

  return (
    <Box
      sx={{
        ...CARD_SX,
        p: 1.25,
        height: '100%',
        boxSizing: 'border-box',
        display: 'flex',
        flexDirection: 'column',
        transition: 'transform 0.12s ease',
        '&:hover': { transform: onOpen ? 'translateY(-2px)' : 'none' },
      }}
    >
      <Box
        {...open}
        aria-label={onOpen ? `Mở bộ từ ${name}` : undefined}
        sx={{
          cursor: onOpen ? 'pointer' : 'default',
          borderRadius: '16px',
          '&:focus-visible': { outline: `3px solid ${PRIMARY}`, outlineOffset: 3 },
        }}
      >
        {/* Bìa: ảnh hoặc minh hoạ tròn trên nền nhạt */}
        <Box sx={{ position: 'relative', height: { xs: 100, sm: 112 }, borderRadius: '16px', bgcolor: tint, display: 'grid', placeItems: 'center', overflow: 'hidden' }}>
          {showImage ? (
            <Box
              component="img"
              src={src}
              alt=""
              loading="lazy"
              onError={() => setImgFailed(true)}
              sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
            />
          ) : (
            <Art size={78} />
          )}
          <Box sx={{ position: 'absolute', left: 10, bottom: 10, px: 1.25, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.92)', fontWeight: 900, fontSize: 13, lineHeight: 1.8, color: INK }}>
            {itemCount} từ
          </Box>
        </Box>

        <Box sx={{ px: 0.75, pt: 1.5 }}>
          <Typography sx={{ fontWeight: 900, fontSize: 17, lineHeight: 1.25, color: INK }} noWrap>
            {name}
          </Typography>
          {/* Rút gọn (chủ dự án 2026-10-27): độ khó + công khai gộp một dòng chữ
              nhạt; mô tả chỉ hiện ở thẻ chưa học (bộ công khai ở Khám phá). */}
          <Typography sx={{ mt: 0.25, fontSize: 13, fontWeight: 800, color: MUTED }} noWrap>
            {[difficulty ? (DIFFICULTY_LABEL[difficulty.toLowerCase()] ?? difficulty) : null,
              category,
              isPublic == null ? null : isPublic ? 'Công khai' : 'Riêng tư'].filter(Boolean).join(' · ')}
          </Typography>
          {!showProgress && description && (
            <Typography
              sx={{
                mt: 0.75, fontSize: 14, fontWeight: 600, color: MUTED,
                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
              }}
            >
              {description}
            </Typography>
          )}
        </Box>
      </Box>

      {/* Tiến độ + đánh giá */}
      <Box sx={{ mt: 'auto', pt: 1.25, px: 0.75 }}>
        {showProgress && (
          <Box sx={{ mb: 0.75 }}>
            <SetProgress total={itemCount} mastered={masteredCount ?? 0} learning={learningCount ?? 0} hideHint />
          </Box>
        )}
        {/* UC-23: chỉ hiện khi bộ đã có người đánh giá */}
        {ratingAvg != null && (ratingCount ?? 0) > 0 && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.25 }}>
            <Rating value={ratingAvg} precision={0.5} size="small" readOnly />
            <Typography sx={{ fontSize: 13, fontWeight: 700, color: MUTED }}>({ratingCount})</Typography>
          </Box>
        )}
        {actions && (
          <Box sx={{ mt: 0.75, pt: 0.75, borderTop: '1px solid #EDE3D9', '& .MuiButton-root': { whiteSpace: 'nowrap', minWidth: 0, px: 1.25 }, '& .MuiButton-root:not(.MuiButton-colorError)': { color: INK } }}>
            {actions}
          </Box>
        )}
      </Box>
    </Box>
  );
}

/** Lưới chứa WordSetCard: số cột tự co theo bề ngang, mỗi cột tối thiểu 230px. */
export const wordSetGridSx = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(230px, 1fr))',
  gap: 2.5,
} as const;

export default WordSetCard;
