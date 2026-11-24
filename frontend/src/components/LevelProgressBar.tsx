import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';

interface LevelProgressBarProps {
  level: number;
  xpInto: number;
  xpForNext: number;
  title?: string;
}

/** Thanh tiến độ tới cấp kế (gamification). */
function LevelProgressBar({ level, xpInto, xpForNext, title }: LevelProgressBarProps) {
  const pct = xpForNext > 0 ? Math.round((xpInto / xpForNext) * 100) : 0;
  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.75 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
          Cấp {level}{title ? ` · ${title}` : ''}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {xpInto}/{xpForNext} XP
        </Typography>
      </Box>
      <LinearProgress variant="determinate" value={pct} />
    </Box>
  );
}

export default LevelProgressBar;
