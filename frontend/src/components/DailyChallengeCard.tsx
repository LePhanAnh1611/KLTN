import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';

import { useClaimChallenge, useDailyChallenges } from '../api/extras';
import SectionCard from './SectionCard';
import { TrophyIcon } from './icons';

/** UC-44 — thử thách hôm nay. Tiến độ do backend đọc từ dữ liệu học thật, ở đây
 * chỉ hiển thị và bấm nhận thưởng. */
function DailyChallengeCard() {
  const { data, isLoading } = useDailyChallenges();
  const claim = useClaimChallenge();

  if (isLoading || !data) return null;

  return (
    <SectionCard
      title="Thử thách hôm nay"
      icon={<TrophyIcon size={18} />}
      caption="Xong thì bấm nhận thưởng, XP cộng vào mục tiêu ngày."
      action={
        data.claimable_count > 0
          ? <Chip size="small" color="primary" label={`${data.claimable_count} phần thưởng`} />
          : undefined
      }
    >
      {data.items.map((item) => (
        <Box key={item.code} sx={{ mb: 2, '&:last-child': { mb: 0 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography variant="body2" sx={{ fontWeight: 700, flexGrow: 1, minWidth: 0 }}>
              {item.title}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {item.progress}/{item.target}
            </Typography>
            {item.claimed ? (
              <Chip size="small" color="success" label={`+${item.xp_reward} XP`} />
            ) : (
              <Button
                size="small" variant="contained"
                disabled={!item.completed || claim.isPending}
                onClick={() => claim.mutate(item.code)}
                // Cột hẹp, để tự xuống dòng thì "Nhận 30 XP" vỡ làm hai dòng
                sx={{ whiteSpace: 'nowrap', flexShrink: 0 }}
              >
                Nhận {item.xp_reward} XP
              </Button>
            )}
          </Box>
          <LinearProgress
            variant="determinate"
            value={(item.progress / item.target) * 100}
            color={item.completed ? 'success' : 'primary'}
            sx={{ height: 6, borderRadius: 0 }}
          />
        </Box>
      ))}
    </SectionCard>
  );
}

export default DailyChallengeCard;
