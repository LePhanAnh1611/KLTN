import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import { TrophyArt } from './FlatArt';
import { KidBin, KidNa } from './FlatScene';
import SpeakButton from './SpeakButton';
import StreakBanner from './StreakBanner';
import { CloseIcon } from './icons';
import { useAnswerSound } from '../hooks/useAnswerSound';
import type { SessionSummary } from '../types/session';
import {
  FLAT,
  GO_GREEN_TEXT,
  INK,
  MUTED,
  PAPER,
  PRIMARY,
  PRIMARY_DARK,
  SOFT_SHADOW,
  SURFACE,
  WRONG_RED,
} from '../theme/theme';

/* ═══════════════════════════════════════════════════════════════════════════
 * PHÒNG HỌC — khung dùng chung cho Study (học bộ từ) và ReviewStudy (ôn tập).
 *
 * Bản flat 2026-10-26 — góp ý người dùng thử: "mỗi lần sang câu phải cuộn
 * xuống". Khung giờ cao ĐÚNG một màn hình (100dvh) và chia ba tầng cố định:
 *   1. thanh trên: thoát · thanh tiến độ · số câu · bật/tắt âm;
 *   2. vùng câu hỏi: thẻ từ + lựa chọn (trắc nghiệm xếp 2×2 cho gọn);
 *   3. đáy: nút trả lời hoặc dải kết quả đúng/sai — luôn trong tầm ngón cái,
 *      không bao giờ bị đẩy xuống dưới mép màn.
 * Hộp "máy bán nước" có mặt hông 3D đã bỏ: nó chiếm gần một nửa chiều cao.
 *
 * Mọi component ở đây chỉ hiển thị; ghi câu trả lời vẫn do trang cha làm.
 * ═══════════════════════════════════════════════════════════════════════════ */

/** Bề rộng cột học. */
const COLUMN = 720;

/** Giới hạn số ô: quá số này mỗi ô quá mảnh, chuyển sang thanh liền. */
const MAX_SEGMENTS = 40;

/** Màu chữ đọc được trên một nền màu (trắng trên nền đậm, mực trên nền nhạt). */
function onColor(hex: string): string {
  const h = hex.replace('#', '');
  if (h.length !== 6) return INK;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return lum < 0.62 ? '#FFFFFF' : INK;
}

/** Thanh tiến độ chia ô. `results[i]` = đúng/sai của từ thứ i đã làm. */
export function SegmentedProgress({ total, done, results }: { total: number; done: number; results: boolean[] }) {
  if (total <= 0) return null;
  const label = `Đã làm ${done} trên ${total}`;

  if (total > MAX_SEGMENTS) {
    const pct = Math.min(100, (done / total) * 100);
    return (
      <Box role="progressbar" aria-label={label} aria-valuenow={done} aria-valuemax={total}
        sx={{ height: 14, borderRadius: 999, bgcolor: '#E8DED4', overflow: 'hidden' }}>
        <Box sx={{ width: `${pct}%`, height: '100%', bgcolor: PRIMARY, borderRadius: 999, transition: 'width 0.25s ease' }} />
      </Box>
    );
  }

  return (
    <Box role="progressbar" aria-label={label} aria-valuenow={done} aria-valuemax={total}
      sx={{ display: 'flex', gap: '4px' }}>
      {Array.from({ length: total }, (_, i) => {
        const state = i < done ? (results[i] === false ? 'wrong' : 'right') : i === done ? 'current' : 'todo';
        return (
          <Box
            key={i}
            sx={{
              flex: 1,
              height: 14,
              borderRadius: 999,
              bgcolor: state === 'right' ? PRIMARY
                : state === 'wrong' ? WRONG_RED
                  : state === 'current' ? FLAT.yellow
                    : '#E8DED4',
              transition: 'background-color 0.2s ease',
            }}
          />
        );
      })}
    </Box>
  );
}

interface StudyShellProps {
  /** Tên bộ từ hoặc tên phiên ôn. */
  title: string;
  /** Nhãn chế độ (Thẻ lật, Trắc nghiệm…). */
  modeLabel: string;
  /** Dòng ghi chú nhỏ cạnh nhãn chế độ (VD luyện thường). */
  note?: string;
  done: number;
  total: number;
  results: boolean[];
  onExit: () => void;
  /** Gợi ý phím tắt ở chân màn (chỉ desktop). */
  hints?: ReactNode;
  children: ReactNode;
}

export function StudyShell({ title, modeLabel, note, done, total, results, onExit, hints, children }: StudyShellProps) {
  const sound = useAnswerSound();
  return (
    <Box sx={{ height: '100dvh', display: 'flex', flexDirection: 'column', bgcolor: PAPER, overflow: 'hidden' }}>
      <Box component="header" sx={{ flexShrink: 0, width: '100%', maxWidth: COLUMN, mx: 'auto', boxSizing: 'border-box', px: { xs: 2, sm: 3 }, pt: { xs: 1.5, sm: 2.5 }, pb: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: { xs: 1.25, sm: 2 } }}>
          <Tooltip title="Thoát (tiến độ đã làm được giữ lại)">
            <IconButton onClick={onExit} aria-label="Thoát phiên học" sx={{ color: MUTED, ml: -1 }}>
              <CloseIcon size={24} />
            </IconButton>
          </Tooltip>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <SegmentedProgress total={total} done={done} results={results} />
          </Box>
          <Typography aria-hidden sx={{ fontWeight: 900, fontSize: 16, color: MUTED, whiteSpace: 'nowrap' }}>
            {Math.min(done + 1, total)}/{total}
          </Typography>
          <Tooltip title={sound.enabled ? 'Tắt âm báo đúng/sai' : 'Bật âm báo đúng/sai'}>
            <IconButton onClick={sound.toggle} aria-label={sound.enabled ? 'Tắt âm báo' : 'Bật âm báo'} aria-pressed={sound.enabled}
              sx={{ color: sound.enabled ? INK : '#B0A69C', mr: -1 }}>
              <SoundIcon on={sound.enabled} />
            </IconButton>
          </Tooltip>
        </Box>
        <Typography sx={{ mt: 0.75, fontSize: 13.5, fontWeight: 700, color: MUTED, textAlign: 'center' }} noWrap>
          {title} · {modeLabel}{note ? ` · ${note}` : ''}
        </Typography>
      </Box>

      <Box
        component="main"
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          width: '100%',
          maxWidth: COLUMN,
          mx: 'auto',
          boxSizing: 'border-box',
          px: { xs: 2, sm: 3 },
          pt: { xs: 1, sm: 2 },
          pb: { xs: 2, sm: 2.5 },
          display: 'flex',
          flexDirection: 'column',
          // Màn rộng: gom cả cụm (thẻ + lựa chọn + nút) vào giữa theo chiều dọc.
          // Dùng margin auto thay vì justify-content để nội dung dài vẫn cuộn được.
          '& > :first-child': { mt: { sm: 'auto' } },
          '& > :last-child': { mb: { sm: 'auto' } },
        }}
      >
        {children}
      </Box>

      {hints && (
        <Box
          sx={{
            flexShrink: 0,
            display: { xs: 'none', md: 'flex' },
            justifyContent: 'center',
            gap: 2.5,
            pb: 1.5,
            fontSize: 13.5,
            fontWeight: 700,
            color: MUTED,
            '& kbd': { mr: 0.5 },
          }}
        >
          {hints}
        </Box>
      )}
    </Box>
  );
}

function SoundIcon({ on }: { on: boolean }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor" stroke="none" />
      {on ? <path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" /> : <path d="M17 9l5 6M22 9l-5 6" />}
    </svg>
  );
}

/** Thẻ trắng cho các dạng bài không có thẻ từ (điền từ, gõ từ, ghép cặp…). */
export function StudyCard({
  label,
  tone = 'default',
  children,
  onClick,
}: {
  label: ReactNode;
  tone?: 'default' | 'right' | 'wrong';
  children: ReactNode;
  /** Bấm vào thân thẻ (dùng để lật thẻ). */
  onClick?: () => void;
}) {
  const chip = tone === 'right' ? { bg: '#DDF2E1', fg: GO_GREEN_TEXT } : tone === 'wrong' ? { bg: '#FCE0E1', fg: '#B8333A' } : { bg: '#F3EAE1', fg: MUTED };
  return (
    <Box
      onClick={onClick}
      sx={{
        width: '100%',
        boxSizing: 'border-box',
        bgcolor: SURFACE,
        borderRadius: '24px',
        boxShadow: SOFT_SHADOW,
        p: { xs: 2.5, sm: 3.5 },
        textAlign: 'center',
        cursor: onClick ? 'pointer' : 'default',
      }}
    >
      <Box component="span" sx={{ display: 'inline-block', mb: 1.75, px: 1.5, py: 0.5, borderRadius: 999, bgcolor: chip.bg, color: chip.fg, fontSize: 13, fontWeight: 900 }}>
        {label}
      </Box>
      {children}
    </Box>
  );
}

/** Hiệu ứng nội dung mới hiện ra. */
export const revealSx = {
  animation: 'cardReveal 0.22s ease-out',
  '@keyframes cardReveal': {
    from: { opacity: 0, transform: 'translateY(8px)' },
    to: { opacity: 1, transform: 'none' },
  },
  '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
} as const;

/** Lưới lựa chọn 2×2 (góp ý người dùng thử: bốn ô xếp dọc làm phải cuộn). */
export function OptionGrid({ children }: { children: ReactNode }) {
  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: { xs: 1.25, sm: 1.5 } }}>
      {children}
    </Box>
  );
}

/**
 * Một ô lựa chọn trong lưới 2×2. Số phím tắt ở góc (chỉ desktop).
 * `state`: idle · right (đáp án đúng) · wrong (đã chọn sai) · muted (đã trả lời, ô khác).
 */
export function OptionTile({
  index,
  label,
  state = 'idle',
  disabled,
  onClick,
}: {
  index: number;
  label: ReactNode;
  state?: 'idle' | 'right' | 'wrong' | 'muted';
  disabled?: boolean;
  onClick: () => void;
}) {
  const look = {
    idle: { bg: SURFACE, border: 'transparent', fg: INK },
    right: { bg: '#DDF2E1', border: PRIMARY, fg: GO_GREEN_TEXT },
    wrong: { bg: '#FCE0E1', border: WRONG_RED, fg: '#B8333A' },
    muted: { bg: SURFACE, border: 'transparent', fg: INK },
  }[state];
  return (
    <Box
      component="button"
      type="button"
      onClick={onClick}
      disabled={disabled}
      sx={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: { xs: 72, sm: 84 },
        width: '100%',
        boxSizing: 'border-box',
        textAlign: 'center',
        px: { xs: 1.5, sm: 2.5 },
        py: 1.25,
        font: 'inherit',
        fontSize: { xs: 15, sm: 16.5 },
        fontWeight: 800,
        lineHeight: 1.3,
        color: look.fg,
        bgcolor: look.bg,
        border: `2.5px solid ${look.border}`,
        borderRadius: '20px',
        boxShadow: state === 'idle' || state === 'muted' ? SOFT_SHADOW : 'none',
        opacity: state === 'muted' ? 0.5 : 1,
        cursor: disabled ? 'default' : 'pointer',
        transition: 'border-color 0.12s ease, background-color 0.15s ease, transform 0.08s ease',
        ...(state === 'idle' && !disabled && {
          '&:hover': { borderColor: '#E2D7CC' },
          '&:active': { transform: 'scale(0.98)' },
        }),
        ...(state === 'wrong' && {
          animation: 'optShake 0.32s ease',
          '@keyframes optShake': {
            '0%, 100%': { transform: 'none' },
            '25%': { transform: 'translateX(-5px)' },
            '75%': { transform: 'translateX(5px)' },
          },
        }),
        '&:focus-visible': { outline: `3px solid ${PRIMARY}`, outlineOffset: 2 },
        '@media (prefers-reduced-motion: reduce)': { animation: 'none' },
      }}
    >
      <Box
        component="span"
        aria-hidden
        sx={{
          display: { xs: 'none', md: 'grid' },
          position: 'absolute', top: 8, left: 10,
          minWidth: 20, height: 20, placeItems: 'center',
          borderRadius: 999, bgcolor: '#F3EAE1', color: MUTED,
          fontSize: 12, fontWeight: 900, lineHeight: 1,
        }}
      >
        {index}
      </Box>
      <Box component="span" sx={{ minWidth: 0, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
        {label}
      </Box>
    </Box>
  );
}

/** Hàng nút trả lời — luôn nằm ở đáy vùng học (mt: auto). */
export function AnswerBar({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        mt: { xs: 'auto', sm: 0 },
        pt: { xs: 2, sm: 3 },
        display: 'grid',
        gap: { xs: 1, sm: 1.5 },
        gridAutoFlow: 'column',
        gridAutoColumns: '1fr',
        flexShrink: 0,
      }}
    >
      {children}
    </Box>
  );
}

/** Nút trả lời lớn hình viên thuốc; số phím tắt hiện dưới nhãn trên desktop. */
export function AnswerButton({
  shortcut,
  label,
  color,
  onClick,
  disabled,
  autoFocus,
}: {
  shortcut: string;
  label: string;
  color: string;
  onClick: () => void;
  disabled?: boolean;
  /** Nhận focus ngay khi hiện — để phím Enter bấm được "Tiếp theo". */
  autoFocus?: boolean;
}) {
  const fg = onColor(color);
  return (
    <Box
      component="button"
      type="button"
      onClick={onClick}
      disabled={disabled}
      autoFocus={autoFocus}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 0.25,
        minHeight: { xs: 54, sm: 60 },
        px: 1,
        font: 'inherit',
        fontSize: { xs: 16, sm: 17 },
        fontWeight: 900,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        whiteSpace: 'nowrap',
        color: fg,
        bgcolor: color,
        border: color === SURFACE ? '2px solid #E2D7CC' : 0,
        borderRadius: 999,
        boxShadow: `0 4px 0 rgba(0,0,0,0.10)`,
        cursor: 'pointer',
        transition: 'transform 0.08s ease, filter 0.12s ease, box-shadow 0.08s ease',
        '&:hover': { filter: 'brightness(0.96)' },
        '&:active': { transform: 'translateY(3px)', boxShadow: '0 1px 0 rgba(0,0,0,0.10)' },
        '&:disabled': { bgcolor: '#E8DED4', color: '#ADA299', boxShadow: 'none', cursor: 'default' },
        '&:focus-visible': { outline: `3px solid ${INK}`, outlineOffset: 2 },
      }}
    >
      {label}
      <Box component="span" sx={{ display: { xs: 'none', md: 'block' }, fontWeight: 800, fontSize: 12, lineHeight: 1, opacity: 0.75 }}>
        phím {shortcut}
      </Box>
    </Box>
  );
}

/**
 * Dải kết quả sau khi trả lời — nằm ở đáy như bảng kết quả trong ảnh mẫu:
 * mèo vui/buồn + câu ngắn + đáp án + nút Tiếp tục to. Thay cho sticker
 * "CHUẨN!/ÔI!" và chữ nhỏ dưới các lựa chọn của bản cũ.
 */
export function FeedbackBar({
  tone,
  title,
  detail,
  nextLabel = 'Tiếp tục',
  onNext,
  busy,
}: {
  tone: 'right' | 'wrong';
  title: string;
  detail?: ReactNode;
  nextLabel?: string;
  onNext: () => void;
  busy?: boolean;
}) {
  const right = tone === 'right';
  return (
    <Box
      role="status"
      sx={{
        mt: { xs: 'auto', sm: 0 },
        pt: { xs: 2, sm: 3 },
        flexShrink: 0,
        ...revealSx,
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          alignItems: { xs: 'stretch', sm: 'center' },
          gap: { xs: 1.25, sm: 2.5 },
          p: { xs: 1.75, sm: 2.25 },
          borderRadius: '24px',
          bgcolor: right ? '#DDF2E1' : '#FCE0E1',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flex: 1, minWidth: 0 }}>
          <Box sx={{ width: 56, height: 56, borderRadius: '50%', bgcolor: SURFACE, overflow: 'hidden', flexShrink: 0, display: 'grid', placeItems: 'end center' }}>
            <KidBin bust size={56} mood={right ? 'cheer' : 'sad'} />
          </Box>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontWeight: 900, fontSize: { xs: 18, sm: 20 }, color: right ? GO_GREEN_TEXT : '#B8333A', lineHeight: 1.25 }}>
              {title}
            </Typography>
            {detail && (
              <Box sx={{ mt: 0.25, fontSize: 14.5, fontWeight: 700, color: INK, lineHeight: 1.4 }}>
                {detail}
              </Box>
            )}
          </Box>
        </Box>
        <Button
          variant="contained"
          size="large"
          autoFocus
          disabled={busy}
          onClick={onNext}
          sx={{
            flexShrink: 0,
            minWidth: { sm: 180 },
            minHeight: 52,
            fontSize: 17,
            bgcolor: right ? PRIMARY : WRONG_RED,
            boxShadow: '0 4px 0 rgba(0,0,0,0.12)',
            '&:hover': { bgcolor: right ? PRIMARY_DARK : '#CF3A40' },
          }}
        >
          {nextLabel}
          <Box component="span" sx={{ ml: 1, display: { xs: 'none', md: 'inline' } }}><kbd>Enter</kbd></Box>
        </Button>
      </Box>
    </Box>
  );
}

/** Khung cho trạng thái tạm (tải, lỗi, rỗng, hỏi tiếp tục) của phòng học. */
export function StudyMessage({
  title,
  children,
  mood = 'vui',
  actions,
}: {
  title: string;
  children?: ReactNode;
  mood?: 'vui' | 'nghi' | 'ngu' | 'mung';
  actions?: ReactNode;
}) {
  return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', p: { xs: 2, sm: 3 }, bgcolor: PAPER }}>
      <Box sx={{ m: 'auto', width: '100%', maxWidth: 460, textAlign: 'center', bgcolor: SURFACE, borderRadius: '28px', boxShadow: SOFT_SHADOW, p: { xs: 3, sm: 4 } }}>
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          <KidBin size={92} pose={mood === 'mung' ? 'wave' : 'book'} mood={mood === 'nghi' ? 'think' : mood === 'ngu' ? 'sad' : mood === 'mung' ? 'cheer' : 'happy'} />
        </Box>
        <Typography sx={{ mt: 2, fontWeight: 900, fontSize: 21 }}>{title}</Typography>
        {children && (
          <Typography component="div" sx={{ mt: 0.75, color: 'text.secondary', fontSize: 15 }}>
            {children}
          </Typography>
        )}
        {actions && (
          <Box sx={{ mt: 3, display: 'flex', gap: 1.5, justifyContent: 'center', flexWrap: 'wrap' }}>
            {actions}
          </Box>
        )}
      </Box>
    </Box>
  );
}

function formatDuration(seconds: number): string {
  // Phiên dài quá một ngày là phiên bỏ dở — số giờ khi đó không nói gì về việc học.
  if (!Number.isFinite(seconds) || seconds < 0) return '-';
  if (seconds >= 86400) return 'để dở';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.round(seconds % 60);
  if (h > 0) return `${h}g ${m}p`;
  if (m > 0) return `${m}p ${s}s`;
  return `${s}s`;
}

/** Câu khen theo độ chính xác — để người học biết phiên này "tốt" hay "cần ôn". */
function verdict(accuracy: number): string {
  if (accuracy >= 0.9) return 'Xuất sắc! Gần như không sai từ nào.';
  if (accuracy >= 0.7) return 'Tốt lắm! Từ nào sai sẽ được nhắc ôn lại.';
  if (accuracy >= 0.5) return 'Ổn rồi - những từ sai sẽ được ôn lại sớm.';
  return 'Phiên khó đây. Đừng lo, các từ này sẽ quay lại sớm để bạn ôn.';
}

/** Màn tổng kết phiên — dùng chung cho học bộ từ và ôn tập. */
export function SessionSummaryView({
  summary,
  primary,
  secondary,
}: {
  summary: SessionSummary;
  primary: { label: string; onClick: () => void };
  secondary?: { label: string; onClick: () => void };
}) {
  const pct = Math.round(summary.accuracy * 100);
  const tiles: { label: string; value: string; color: string }[] = [
    { label: 'Câu đúng', value: `${summary.correct_count}/${summary.total_answered}`, color: FLAT.green },
    { label: 'Từ đã thuộc', value: `${summary.mastered_count}`, color: FLAT.purple },
    { label: 'Điểm XP', value: `+${summary.xp_earned}`, color: FLAT.orange },
    { label: 'Thời gian', value: formatDuration(summary.duration_seconds), color: FLAT.blue },
  ];

  return (
    <Box sx={{ height: '100dvh', display: 'flex', p: { xs: 2, sm: 3 }, bgcolor: PAPER, boxSizing: 'border-box' }}>
      <Box
        sx={{
          m: 'auto', width: '100%', maxWidth: 620, maxHeight: '100%', overflowY: 'auto', boxSizing: 'border-box',
          bgcolor: SURFACE, borderRadius: '28px', boxShadow: SOFT_SHADOW, p: { xs: 2.5, sm: 4 }, textAlign: 'center',
        }}
      >
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          {pct >= 50 ? (
            <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1 }}>
              <KidBin size={84} pose="wave" mood="cheer" />
              <TrophyArt size={72} />
              <KidNa size={76} pose="wave" mood="cheer" />
            </Box>
          ) : <KidBin size={88} mood="think" />}
        </Box>
        <Typography component="h1" sx={{ fontWeight: 900, fontSize: { xs: 26, sm: 30 }, mt: 1.5, lineHeight: 1.2 }}>
          Hoàn thành! {pct}% đúng
        </Typography>
        <Typography sx={{ color: 'text.secondary', fontWeight: 700, mt: 0.5, mb: 2.5 }}>{verdict(summary.accuracy)}</Typography>

        <Box sx={{ textAlign: 'left' }}>
          <StreakBanner streakCount={summary.streak_count} extended={summary.streak_extended} />
        </Box>

        <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(4, 1fr)' }, mb: 2.5 }}>
          {tiles.map((t) => (
            <Box key={t.label} sx={{ p: 1.5, bgcolor: '#FAF5F0', borderRadius: '18px' }}>
              <Typography sx={{ fontWeight: 900, fontSize: 22, lineHeight: 1.1, color: t.color }}>{t.value}</Typography>
              <Typography sx={{ fontSize: 13, fontWeight: 800, color: MUTED, mt: 0.25 }}>{t.label}</Typography>
            </Box>
          ))}
        </Box>

        {summary.new_achievements.length > 0 && (
          <Box sx={{ mb: 2.5, p: 1.5, bgcolor: '#FDEFC4', borderRadius: '16px', fontWeight: 800 }}>
            🏆 Mở khóa huy hiệu: {summary.new_achievements.join(', ')}
          </Box>
        )}

        {summary.wrong_items.length > 0 && (
          <Box sx={{ textAlign: 'left', mb: 1 }}>
            <Typography sx={{ fontWeight: 900, fontSize: 15, mb: 1 }}>
              Từ cần chú ý ({summary.wrong_items.length})
            </Typography>
            <Box sx={{ display: 'grid', gap: 1, gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' } }}>
              {summary.wrong_items.map((w) => (
                <Box key={w.item_id} sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 1, borderRadius: '16px', bgcolor: '#FCE0E1' }}>
                  <Box sx={{ minWidth: 0, flexGrow: 1 }}>
                    <Typography sx={{ fontWeight: 900, fontSize: 15 }} noWrap>{w.word}</Typography>
                    <Typography sx={{ fontSize: 14, color: 'text.secondary' }} noWrap>{w.meaning}</Typography>
                  </Box>
                  <SpeakButton text={w.word} />
                </Box>
              ))}
            </Box>
          </Box>
        )}

        <Box sx={{ mt: 3, display: 'flex', gap: 1.5, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Button variant="contained" size="large" onClick={primary.onClick} sx={{ minWidth: 180 }}>{primary.label}</Button>
          {secondary && (
            <Button variant="outlined" size="large" onClick={secondary.onClick}>{secondary.label}</Button>
          )}
        </Box>
      </Box>
    </Box>
  );
}
