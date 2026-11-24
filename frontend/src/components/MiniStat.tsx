import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';

import { INK, MUTED, PRIMARY, PRIMARY_LIGHT } from '../theme/theme';

/** Một chỉ số trên dải thống kê gọn (thay các thẻ lớn để trang vừa một màn hình). */
function MiniStat({ icon, value, label }: { icon: ReactNode; value: ReactNode; label: string }) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
      <Box sx={{ width: 36, height: 36, borderRadius: '50%', bgcolor: PRIMARY_LIGHT, color: PRIMARY, display: 'grid', placeItems: 'center', flexShrink: 0 }}>
        {icon}
      </Box>
      <Box>
        <Typography sx={{ fontWeight: 900, fontSize: 17, lineHeight: 1.2, color: INK }}>{value}</Typography>
        <Typography sx={{ fontWeight: 700, fontSize: 12.5, lineHeight: 1.3, color: MUTED, whiteSpace: 'nowrap' }}>{label}</Typography>
      </Box>
    </Box>
  );
}

export default MiniStat;
