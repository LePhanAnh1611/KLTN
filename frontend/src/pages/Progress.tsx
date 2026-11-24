import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CircularProgress from '@mui/material/CircularProgress';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Typography from '@mui/material/Typography';
import { useState } from 'react';
import { useTheme } from '@mui/material/styles';
import { useNavigate } from 'react-router-dom';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import { useQuery } from '@tanstack/react-query';

import { getProgress } from '../api/progress';
import LevelProgressBar from '../components/LevelProgressBar';
import MiniStat from '../components/MiniStat';
import ProgressRing from '../components/ProgressRing';
import PageHeader from '../components/PageHeader';
import SessionHistory from '../components/SessionHistory';
import SectionCard from '../components/SectionCard';
import { ChartIcon, FlameIcon, GraduationIcon, StarIcon, TrophyIcon } from '../components/icons';
import type { MasteryBand } from '../api/progress';

/** Bốn dải từ Chưa học → Nắm vững theo bảng Kem & Vàng: xám → vàng nhạt → vàng
 * → mực. Đậm dần = nắm vững hơn, không cần thêm màu thứ ba. */
/** Chưa học → Nắm vững: be → vàng → cam → xanh lá (màu hành động = đích đến). */
const BAND_RAMP = ['#D9CCC0', '#F6C445', '#F39A3D', '#2FA84F'] as const;

function XpGoal({ today, goal, reached }: { today: number; goal: number; reached: boolean }) {
  const theme = useTheme();
  const remaining = Math.max(0, goal - today);
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <ProgressRing
        value={(today / goal) * 100}
        size={64}
        color={reached ? theme.palette.success.main : undefined}
      />
      <Box>
        <Typography variant="body2" color="text.secondary">Mục tiêu hôm nay</Typography>
        <Typography variant="h6" component="p" sx={{ fontWeight: 800 }}>{today}/{goal} XP</Typography>
        <Typography variant="caption" color={reached ? 'success.main' : 'text.secondary'}>
          {reached ? 'Đã hoàn thành' : `Còn ${remaining} XP nữa`}
        </Typography>
      </Box>
    </Box>
  );
}

function DistributionChart({ bands }: { bands: MasteryBand[] }) {
  const ramp = BAND_RAMP;
  const max = Math.max(1, ...bands.map((b) => b.count));
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      {bands.map((b, i) => (
        <Box key={b.label} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="body2" sx={{ width: 90, flexShrink: 0, fontWeight: 700 }}>{b.label}</Typography>
          <Box sx={{ flexGrow: 1, height: 18, bgcolor: '#F3EAE1', borderRadius: 999, overflow: 'hidden' }}>
            <Box sx={{ width: `${(b.count / max) * 100}%`, minWidth: b.count > 0 ? 18 : 0, height: '100%',
                       bgcolor: ramp[i], borderRadius: 999 }} />
          </Box>
          <Typography sx={{ width: 44, textAlign: 'right', flexShrink: 0, fontWeight: 900, fontSize: 17, lineHeight: 1 }}>{b.count}</Typography>
        </Box>
      ))}
    </Box>
  );
}

function Progress() {
  const navigate = useNavigate();
  const [tab, setTab] = useState(0);
  const query = useQuery({ queryKey: ['progress'], queryFn: getProgress });
  const data = query.data;

  return (
    <Box>
      <PageHeader
        title="Tiến độ học tập"
        subtitle="Cập nhật sau mỗi lần học."
      />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Tổng quan" />
        <Tab label="Lịch sử học tập" />
      </Tabs>

      {tab === 1 && <SessionHistory />}

      {tab === 0 && query.isLoading && (
        <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>
      )}
      {tab === 0 && query.isError && <Alert severity="error">Không tải được tiến độ.</Alert>}

      {tab === 0 && data && (
        <>
          {/* Một thẻ tổng hợp thay 5 thẻ rời, phần chi tiết chia 2 cột để cả trang
              nằm gọn trong một màn hình (2026-11-04). */}
          <Card sx={{ p: { xs: 2, sm: 2.5 }, mb: 2.5 }}>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: { xs: 1.5, sm: 2.5 }, mb: 2 }}>
              <XpGoal today={data.today_xp} goal={data.daily_xp_goal} reached={data.daily_goal_reached} />
              <MiniStat icon={<GraduationIcon size={18} />} value={data.level} label={data.level_title} />
              <MiniStat icon={<StarIcon size={18} />} value={data.xp} label="Tổng XP" />
              <MiniStat icon={<FlameIcon size={18} />} value={data.streak_count} label="Ngày học liên tiếp" />
              <MiniStat icon={<TrophyIcon size={18} />} value={`${data.mastered_items}/${data.total_items}`} label="Đã thuộc" />
            </Box>
            <LevelProgressBar
              level={data.level}
              xpInto={data.xp_into_level}
              xpForNext={data.xp_for_next_level}
              title={data.level_title}
            />
          </Card>

          <Box sx={{
            display: 'grid', gap: 2.5,
            gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: data.weak_items.length > 0 ? 'repeat(2, minmax(0, 1fr))' : 'minmax(0, 1fr)' },
          }}>
            <SectionCard
              title="Phân bố mức độ nắm vững"
              icon={<ChartIcon size={18} />}
              caption="Số từ theo 4 mức, từ Chưa học đến Nắm vững."
            >
              {data.learned_items === 0 ? (
                <Alert severity="info">Chưa có dữ liệu. Hãy học một bộ từ vựng để theo dõi tiến độ.</Alert>
              ) : (
                <DistributionChart bands={data.mastery_distribution} />
              )}
            </SectionCard>

            {data.weak_items.length > 0 && (
              <SectionCard
                title="Từ cần chú ý"
                icon={<TrophyIcon size={18} />}
                caption="Từ nhớ kém nhất, nên ôn trước."
                action={
                  // UC-86: mở thẳng phiên ôn đúng nhóm từ đang hiển thị
                  <Button size="small" variant="contained"
                          onClick={() => navigate('/reviews/study?source=weak')}>
                    Ôn ngay
                  </Button>
                }
                sx={{ maxHeight: { md: 'calc(100vh - 500px)' }, minHeight: { md: 300 }, overflowY: { md: 'auto' } }}
              >
                <List dense disablePadding>
                  {data.weak_items.map((w) => (
                    <ListItem key={w.item_id} secondaryAction={
                      <Typography variant="body2" color="error">{Math.round(w.mastery * 100)}%</Typography>
                    }>
                      <ListItemText primary={`${w.word} - ${w.meaning}`} secondary={w.word_set_name} />
                    </ListItem>
                  ))}
                </List>
              </SectionCard>
            )}
          </Box>
        </>
      )}
    </Box>
  );
}

export default Progress;
