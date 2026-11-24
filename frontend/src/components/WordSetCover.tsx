import { useState } from 'react';
import Box from '@mui/material/Box';

import { API_BASE_URL } from '../api/client';
import { accentById } from '../theme/accents';
import { ACCENT_FONT } from '../theme/theme';

interface WordSetCoverProps {
  /** Id bộ từ — nguồn duy nhất sinh màu, để hai bộ cùng danh mục vẫn khác nhau. */
  id: number;
  name: string;
  /** Ảnh người tạo tải lên. Chưa có (đa số hiện nay) thì sinh bìa từ id + tên. */
  coverUrl?: string | null;
  /** 'card' = bìa 16:9 trên thẻ lưới, 'thumb' = ô vuông nhỏ trong danh sách. */
  variant?: 'card' | 'thumb';
  /** Cạnh ô vuông khi variant='thumb'. */
  thumbSize?: number;
}

/**
 * Chữ cái đầu có nghĩa của tên bộ từ.
 *
 * Nhiều bộ đặt tên kiểu '[A2] Du lịch & Di chuyển' — lấy thẳng ký tự đầu sẽ ra
 * dấu '[' vô nghĩa. Bỏ nhãn trình độ trong ngoặc vuông ở đầu, rồi lấy chữ/số
 * đầu tiên (\p{L} nhận cả chữ có dấu tiếng Việt).
 */
function coverInitial(name: string): string {
  const stripped = name.replace(/^\s*\[[^\]]*\]\s*/, '');
  const match = (stripped || name).match(/[\p{L}\p{N}]/u);
  return (match?.[0] ?? '?').toUpperCase();
}

/**
 * Ảnh bìa bộ từ, khung khoá tỉ lệ cứng.
 *
 * Khung luôn có kích thước cố định dù ảnh nguồn tỉ lệ nào (`object-fit: cover`),
 * nên các thẻ trong lưới không bị cao thấp lệch nhau vì ảnh. Ảnh hỏng/404 thì
 * rơi về bìa sinh, không để lại ô vỡ.
 */
function WordSetCover({
  id,
  name,
  coverUrl,
  variant = 'card',
  thumbSize = 48,
}: WordSetCoverProps) {
  const [failed, setFailed] = useState(false);

  const accent = accentById(id);
  const initial = coverInitial(name);
  const isThumb = variant === 'thumb';

  const frame = isThumb
    ? { width: thumbSize, height: thumbSize, borderRadius: '14px', flexShrink: 0, boxSizing: 'border-box' as const }
    // Bug #3: trên điện thoại thẻ chiếm full chiều ngang nên 16:9 cao ~190px —
    // mỗi màn chỉ thấy đúng một bộ. Dưới sm dẹt lại còn ~1/3 chiều ngang.
    : { width: '100%', aspectRatio: { xs: '3 / 1', sm: '16 / 9' }, borderRadius: 0 };

  const showImage = Boolean(coverUrl) && !failed;
  // Ảnh lưu dạng đường dẫn tương đối ('/uploads/...'); URL ngoài thì giữ nguyên.
  const src = coverUrl?.startsWith('http') ? coverUrl : `${API_BASE_URL}${coverUrl ?? ''}`;

  return (
    <Box
      sx={{
        ...frame,
        position: 'relative',
        overflow: 'hidden',
        display: 'grid',
        placeItems: 'center',
        bgcolor: accent.solid,
      }}
    >
      {showImage ? (
        <Box
          component="img"
          src={src}
          alt=""
          loading="lazy"
          onError={() => setFailed(true)}
          sx={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      ) : (
        <>
          {/* Bìa sinh: khối màu đặc + chữ cái trắng, đúng phong cách khối màu của app. */}
          <Box
            aria-hidden
            sx={{
              position: 'relative',
              fontFamily: ACCENT_FONT,
              fontWeight: 900,
              lineHeight: 1,
              color: '#FFFFFF',
              fontSize: isThumb ? thumbSize * 0.45 : 52,
              letterSpacing: '-0.02em',
              textShadow: 'none',
            }}
          >
            {initial}
          </Box>
        </>
      )}
    </Box>
  );
}

export default WordSetCover;
