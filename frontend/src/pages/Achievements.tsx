import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import { useQuery } from '@tanstack/react-query';

import { getAchievements } from '../api/achievements';
import AchievementCard from '../components/AchievementCard';
import PageHeader from '../components/PageHeader';

function Achievements() {
  const query = useQuery({ queryKey: ['achievements'], queryFn: getAchievements });

  const unlocked = query.data?.filter((a) => a.unlocked).length ?? 0;

  return (
    <Box>
      <PageHeader
        title="Huy hiệu"
        subtitle={
          query.data
            ? `Đã mở ${unlocked}/${query.data.length} huy hiệu. Huy hiệu tự mở khi bạn đạt điều kiện, không cần thao tác gì thêm.`
            : 'Huy hiệu tự mở khi bạn đạt điều kiện, không cần thao tác gì thêm.'
        }
      />

      {query.data && query.data.length > 0 && (
        <LinearProgress
          variant="determinate"
          value={(unlocked / query.data.length) * 100}
          sx={{ mb: 3 }}
        />
      )}

      {query.isLoading && (
        <Box sx={{ textAlign: 'center', py: 8 }}>
          <CircularProgress />
        </Box>
      )}
      {query.isError && <Alert severity="error">Không tải được huy hiệu.</Alert>}

      {query.data && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, mt: 1 }}>
          {query.data.map((a) => (
            <AchievementCard
              key={a.code}
              name={a.name}
              description={a.description}
              unlocked={a.unlocked}
            />
          ))}
        </Box>
      )}
    </Box>
  );
}

export default Achievements;
