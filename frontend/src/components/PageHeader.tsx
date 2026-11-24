import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { INK, PRIMARY } from '../theme/theme';
import { flatArtForPath, ProfileArt } from './FlatArt';

interface PageHeaderProps {
  title: string;
  subtitle?: ReactNode;
  /** Nút hành động chính của trang, canh phải trên màn rộng. */
  actions?: ReactNode;
}

/**
 * Tiêu đề trang dùng chung cho MỌI màn: minh hoạ tròn của khu vực + tiêu đề
 * đậm + một câu ngắn. Nút hành động nằm cùng hàng để thấy ngay khi vào trang.
 */
function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  const { pathname } = useLocation();
  const Art = flatArtForPath(pathname);

  return (
    <Box
      sx={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', gap: 2, flexWrap: { xs: 'wrap', md: 'nowrap' }, mb: 3,
      }}
    >
      <Box sx={{ minWidth: 0, flex: { xs: '1 1 100%', md: 1 }, display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* Vòng navy + minh hoạ trắng, cùng kiểu 4 ô chức năng ở Trang chủ (2026-10-28) */}
        {Art && (
          <Box sx={{ display: { xs: 'none', sm: 'grid' }, placeItems: 'center', width: 64, height: 64, borderRadius: '50%', bgcolor: PRIMARY, flexShrink: 0, overflow: 'hidden' }}>
            <Art size={Art === ProfileArt ? 64 : 50} bg={null} />
          </Box>
        )}
        <Box sx={{ minWidth: 0 }}>
          <Typography
            variant="h4" component="h1"
            // Tiêu đề trang IN HOA, luôn một dòng (chủ dự án 2026-10-27)
            sx={{ fontWeight: 900, fontSize: { xs: 22, sm: 28 }, lineHeight: 1.5, color: INK, textTransform: 'uppercase', letterSpacing: '0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
          >
            {title}
          </Typography>
          {subtitle && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, maxWidth: 640, fontSize: 15 }}>
              {subtitle}
            </Typography>
          )}
        </Box>
      </Box>

      {actions && (
        // Điện thoại: hàng nút chiếm cả bề ngang, mỗi nút giãn đều; nút nào không
        // vừa thì cả nút xuống hàng (chữ trong nút không bao giờ gãy dòng).
        <Box sx={{
          display: 'flex', gap: 1.25, flexWrap: 'wrap', justifyContent: 'flex-end', flexShrink: 0,
          width: { xs: '100%', md: 'auto' },
          '& > .MuiButton-root': { flex: { xs: '1 1 auto', md: '0 0 auto' }, fontSize: { xs: 14, sm: undefined }, px: { xs: 2, sm: undefined } },
        }}>{actions}</Box>
      )}
    </Box>
  );
}

export default PageHeader;
