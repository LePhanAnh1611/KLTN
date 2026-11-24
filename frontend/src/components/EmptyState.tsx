import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { Bush, Cloud, Flower, KidBin, KidNa } from './FlatScene';
import type { Mood } from './FlatScene';

interface EmptyStateProps {
  /** Không còn dùng (giữ cho các trang cũ khỏi phải sửa) — luôn vẽ cảnh nhân vật. */
  icon?: ReactNode;
  title: string;
  /** Nói rõ bước tiếp theo, đừng chỉ báo "không có dữ liệu". */
  description?: ReactNode;
  action?: ReactNode;
}

/** Chọn ổn định theo tiêu đề: bạn nào xuất hiện, nét mặt gì. */
function pick(seed: string): { kid: 'bin' | 'na'; mood: Mood } {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  const moods: Mood[] = ['think', 'happy', 'think', 'sad'];
  return { kid: h % 2 ? 'na' : 'bin', mood: moods[(h >>> 1) % moods.length] };
}

/**
 * Trạng thái rỗng dùng chung — một "cảnh nhỏ" phẳng: Bin hoặc Na đứng giữa
 * mây, bụi cây và hoa. Màn rỗng là chỗ người dùng dễ nản nhất, nên luôn có
 * nhân vật và một bước tiếp theo rõ ràng.
 */
function EmptyState({ title, description, action }: EmptyStateProps) {
  const { kid, mood } = pick(title);
  const Kid = kid === 'na' ? KidNa : KidBin;
  return (
    <Box sx={{ textAlign: 'center', py: 4, px: 2 }}>
      <Box aria-hidden sx={{ position: 'relative', width: 220, height: 150, mx: 'auto', mb: 2 }}>
        <Box sx={{ position: 'absolute', inset: '24px 10px 0', borderRadius: '50% 50% 24px 24px', bgcolor: '#EFE6DC' }} />
        <Cloud size={64} sx={{ position: 'absolute', top: 6, left: 4 }} />
        <Bush size={56} sx={{ position: 'absolute', bottom: 0, left: 18 }} />
        <Flower size={16} sx={{ position: 'absolute', bottom: 4, right: 40 }} />
        <Kid size={86} mood={mood} pose="book" sx={{ position: 'absolute', bottom: 0, left: '50%', transform: 'translateX(-50%)' }} />
      </Box>
      <Typography variant="h6" sx={{ mb: 0.5, fontWeight: 900 }}>{title}</Typography>
      {description && (
        <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420, mx: 'auto' }}>
          {description}
        </Typography>
      )}
      {action && <Box sx={{ mt: 2.5 }}>{action}</Box>}
    </Box>
  );
}

export default EmptyState;
