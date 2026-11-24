import Box from '@mui/material/Box';
import { useTheme } from '@mui/material/styles';
import Typography from '@mui/material/Typography';

interface ProgressRingProps {
  value: number; // 0-100
  size?: number;
  thickness?: number;
  label?: string;
  color?: string; // CSS color; mặc định theo theme primary
}

/** Vòng tiến độ % (mục tiêu XP hôm nay...). Vẽ bằng conic-gradient, không cần lib. */
function ProgressRing({ value, size = 92, thickness = 10, label, color }: ProgressRingProps) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  const theme = useTheme();
  const ringColor = color ?? theme.palette.primary.main;

  return (
    <Box
      sx={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: '50%',
        background: `conic-gradient(${ringColor} ${pct * 3.6}deg, rgba(148,163,184,0.25) 0deg)`,
        display: 'grid',
        placeItems: 'center',
        flexShrink: 0,
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          inset: thickness,
          borderRadius: '50%',
          bgcolor: 'background.paper',
          display: 'grid',
          placeItems: 'center',
        }}
      >
        <Box sx={{ textAlign: 'center', lineHeight: 1 }}>
          <Typography component="span" sx={{ fontWeight: 800, fontSize: size * 0.24 }}>
            {pct}%
          </Typography>
          {label && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {label}
            </Typography>
          )}
        </Box>
      </Box>
    </Box>
  );
}

export default ProgressRing;
