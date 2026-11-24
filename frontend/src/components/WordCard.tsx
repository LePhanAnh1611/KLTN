import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import SpeakButton from './SpeakButton';
import { revealSx } from './StudyShell';
import { FLAT, INK, SOFT_SHADOW, SURFACE } from '../theme/theme';

/**
 * THẺ TỪ phẳng (2026-10-26). Một thẻ trắng duy nhất: tên từ to, phiên âm, nút
 * nghe; lật thẻ thì nghĩa hiện NGAY BÊN DƯỚI trong cùng thẻ — không đổi chỗ,
 * không đẩy nút trả lời ra khỏi màn hình như hộp "máy bán nước" cũ.
 *
 * Vòng tròn chữ cái ở góc có màu ỔN ĐỊNH theo id từ: gặp lại từ cũ là gặp lại
 * đúng màu đó — một mốc nhận diện nhỏ giúp nhớ.
 *
 * Chỉ hiển thị: lật thẻ / trả lời do trang cha xử lý.
 */

/** Màu vòng tròn theo id từ (lấy từ bảng minh hoạ phẳng). */
const WORD_COLORS = [FLAT.purple, FLAT.green, FLAT.orange, FLAT.blue, FLAT.red, FLAT.teal, FLAT.lime];

/**
 * [màu nhấn, nền nhạt, chữ] theo id — giữ chữ ký cũ vì bìa bộ từ (WordSetCard)
 * cũng dùng để tô màu ổn định.
 */
export function cardTone(seed: number): [string, string, string] {
  const c = WORD_COLORS[Math.abs(Math.trunc(seed)) % WORD_COLORS.length];
  return [c, `${c}1F`, INK];
}

/** 0–4 sao theo mức nắm vững. null = chưa có ước lượng → không vẽ sao. */
export function Stars({ mastery, size = 20, onDark = false }: { mastery: number | null | undefined; size?: number; /** Trên nền xanh đậm: sao trống màu trắng mờ. */ onDark?: boolean }) {
  if (mastery == null) return null;
  const filled = Math.max(0, Math.min(4, Math.round(mastery * 4)));
  return (
    <Box aria-label={`Mức nhớ từ này: ${filled}/4 sao`} sx={{ display: 'inline-flex', gap: '2px', fontSize: size, lineHeight: 1 }}>
      {Array.from({ length: 4 }, (_, i) => (
        <Box key={i} component="span" sx={{ color: i < filled ? FLAT.yellow : onDark ? 'rgba(255,255,255,0.3)' : '#E8DED4' }}>★</Box>
      ))}
    </Box>
  );
}

interface WordCardProps {
  seed: number;
  /** Số thứ tự trong phiên (bắt đầu từ 1). */
  no: number;
  word: string;
  phonetic?: string | null;
  partOfSpeech?: string | null;
  /** Mức nắm vững — chỉ truyền SAU khi trả lời để không gợi ý đáp án. */
  mastery?: number | null;
  /** Tên bộ từ (giữ cho tương thích, không còn hiển thị trên thẻ). */
  footer?: string;
  flipped: boolean;
  /** Nội dung mặt sau (nghĩa, ví dụ). */
  back?: ReactNode;
  /** Bấm vào thẻ để lật (bỏ trống nếu thẻ đang chờ câu chọn nghĩa). */
  onFlip?: () => void;
}

/** Nền phần câu hỏi: xanh lá đậm, chữ trắng — tách hẳn khỏi các ô đáp án trắng bên dưới. */
export const QUESTION_BG = '#1F7A39';

export default function WordCard({
  seed, word, phonetic, partOfSpeech, mastery, flipped, back, onFlip,
}: WordCardProps) {
  const [color] = cardTone(seed);
  const canFlip = Boolean(onFlip) && !flipped;

  return (
    <Box
      onClick={canFlip ? onFlip : undefined}
      role={canFlip ? 'button' : undefined}
      tabIndex={canFlip ? 0 : undefined}
      aria-label={canFlip ? 'Lật thẻ để xem nghĩa' : undefined}
      onKeyDown={canFlip ? (e: React.KeyboardEvent) => { if (e.key === 'Enter') onFlip?.(); } : undefined}
      sx={{
        flexShrink: 0,
        boxSizing: 'border-box',
        width: '100%',
        bgcolor: SURFACE,
        borderRadius: '28px',
        boxShadow: SOFT_SHADOW,
        overflow: 'hidden',
        textAlign: 'center',
        cursor: canFlip ? 'pointer' : 'default',
        animation: 'cardIn 0.25s ease-out',
        '@keyframes cardIn': {
          from: { opacity: 0, transform: 'translateY(10px)' },
          to: { opacity: 1, transform: 'none' },
        },
        '&:focus-visible': { outline: `3px solid ${color}`, outlineOffset: 3 },
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
    >
      {/* Phần câu hỏi — nền xanh đậm (chủ dự án 2026-10-27: câu hỏi phải khác màu đáp án) */}
      <Box
        sx={{
          position: 'relative',
          bgcolor: QUESTION_BG,
          color: '#FFFFFF',
          px: { xs: 2.5, sm: 4 },
          pt: { xs: 3, sm: 4 },
          pb: { xs: 2.5, sm: 3.25 },
        }}
      >
        {/* Vòng tròn chữ cái — mốc màu riêng của từ */}
        <Box
          aria-hidden
          sx={{
            position: 'absolute', top: { xs: 14, sm: 18 }, left: { xs: 14, sm: 18 },
            width: { xs: 36, sm: 44 }, height: { xs: 36, sm: 44 }, borderRadius: '50%',
            bgcolor: '#FFFFFF', color, display: 'grid', placeItems: 'center',
            fontWeight: 900, fontSize: { xs: 17, sm: 20 }, textTransform: 'uppercase',
          }}
        >
          {word.trim().charAt(0)}
        </Box>
        <Box sx={{ position: 'absolute', top: { xs: 10, sm: 14 }, right: { xs: 10, sm: 14 }, '& span span': { textShadow: 'none' } }}>
          <Stars mastery={mastery} size={18} onDark />
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, px: { xs: 4, sm: 5 } }}>
          <Typography
            component="h2"
            sx={{ fontWeight: 900, fontSize: { xs: 32, sm: 42 }, letterSpacing: '-0.015em', lineHeight: 1.15, color: '#FFFFFF', wordBreak: 'break-word' }}
          >
            {word}
          </Typography>
          <Box sx={{ bgcolor: 'rgba(255,255,255,0.18)', borderRadius: '50%', ml: 0.5, '& .MuiIconButton-root': { color: '#FFFFFF' } }}>
            <SpeakButton text={word} size={22} />
          </Box>
        </Box>
        {(partOfSpeech || phonetic) && (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mt: 0.75, flexWrap: 'wrap' }}>
            {partOfSpeech && (
              <Box component="span" sx={{ px: 1.25, py: 0.25, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.18)', color: '#FFFFFF', fontWeight: 800, fontSize: 13.5 }}>
                {partOfSpeech}
              </Box>
            )}
            {phonetic && (
              <Typography component="span" sx={{ fontSize: 15, fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>{phonetic}</Typography>
            )}
          </Box>
        )}

        {canFlip && (
          <Box component="span" sx={{ display: 'inline-block', mt: 2, px: 2, py: 0.75, borderRadius: 999, bgcolor: 'rgba(255,255,255,0.18)', color: '#FFFFFF', fontWeight: 800, fontSize: 14 }}>
            Chạm để xem nghĩa
          </Box>
        )}
      </Box>

      {/* Mặt sau (nghĩa, ví dụ) — phần trắng bên dưới, cùng màu với đáp án */}
      {flipped && back && (
        <Box sx={{ px: { xs: 2.5, sm: 4 }, py: { xs: 2, sm: 2.5 }, color: INK, ...revealSx }}>
          {back}
        </Box>
      )}
    </Box>
  );
}
