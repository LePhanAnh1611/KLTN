import { useNavigate, useParams } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';

import { usePublicProfile } from '../api/user';
import AchievementCard from '../components/AchievementCard';
import StatCard from '../components/StatCard';
import { ChartIcon, GraduationIcon, TrophyIcon } from '../components/icons';
import { ACCENT_FONT } from '../theme/theme';
import {
  useFriendshipState,
  useRespondFriendRequest,
  useSendFriendRequest,
  useUnfriend,
} from '../api/extras';

/** UC-55 — hồ sơ công khai: level, XP, streak, huy hiệu đã mở khóa.
 * E1: hồ sơ riêng tư -> backend đã ẩn chỉ số, trang chỉ hiện tên + avatar. */
/** UC-56 — nút kết bạn đổi chữ theo quan hệ hiện tại giữa hai người. */
function FriendButton({ userId }: { userId: number }) {
  const { data } = useFriendshipState(userId);
  const send = useSendFriendRequest();
  const respond = useRespondFriendRequest();
  const unfriend = useUnfriend();

  if (!data || data.status === 'self') return null;

  if (data.status === 'none') {
    return (
      <Button variant="contained" disabled={send.isPending}
              onClick={() => send.mutate(userId)}>
        Kết bạn
      </Button>
    );
  }

  if (data.status === 'accepted') {
    return (
      <Button variant="outlined" color="error" disabled={unfriend.isPending}
              onClick={() => unfriend.mutate(userId)}>
        Hủy kết bạn
      </Button>
    );
  }

  // pending: lời mời đến thì hiện hai nút, lời mời mình gửi thì cho rút lại
  return data.is_incoming ? (
    <Box sx={{ display: 'flex', gap: 1 }}>
      <Button variant="contained" disabled={respond.isPending}
              onClick={() => respond.mutate({ id: data.friendship_id!, accept: true })}>
        Đồng ý
      </Button>
      <Button disabled={respond.isPending}
              onClick={() => respond.mutate({ id: data.friendship_id!, accept: false })}>
        Từ chối
      </Button>
    </Box>
  ) : (
    <Button variant="outlined" disabled={unfriend.isPending}
            onClick={() => unfriend.mutate(userId)}>
      Hủy lời mời
    </Button>
  );
}

function PublicProfile() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const userId = id ? Number(id) : null;
  const { data, isLoading, isError } = usePublicProfile(userId);

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (isError || !data) return <Alert severity="error">Không tìm thấy người dùng.</Alert>;

  return (
    <Box sx={{ maxWidth: 900, mx: 'auto' }}>
      <Card sx={{ p: 3, mb: 3, display: 'flex', gap: 2.5, alignItems: 'center', flexWrap: 'wrap' }}>
        <Avatar src={data.avatar_url ?? undefined} sx={{ width: 72, height: 72 }}>
          {data.display_name.charAt(0).toUpperCase()}
        </Avatar>
        <Box sx={{ flexGrow: 1, minWidth: 200 }}>
          <Typography variant="h5" sx={{ fontFamily: ACCENT_FONT, fontWeight: 700 }}>{data.display_name}</Typography>
          {data.level != null && (
            <Chip size="small" color="primary" sx={{ mt: 0.5 }}
                  label={`Cấp ${data.level} · ${data.level_title}`} />
          )}
          {data.bio && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{data.bio}</Typography>
          )}
          {data.joined_at && (
            <Typography variant="caption" color="text.secondary">
              Tham gia {new Date(data.joined_at).toLocaleDateString('vi-VN')}
            </Typography>
          )}
        </Box>
        {!data.is_me && <FriendButton userId={data.user_id} />}
        {data.is_me && (
          <Button variant="outlined" onClick={() => navigate('/profile')}>Sửa hồ sơ</Button>
        )}
      </Card>

      {data.is_private ? (
        <Alert severity="info">Người dùng này đã đặt hồ sơ ở chế độ riêng tư.</Alert>
      ) : (
        <>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 3 }}>
            <StatCard label="Tổng XP" value={data.xp ?? 0} icon={<ChartIcon />} />
            <StatCard label="Chuỗi ngày" value={data.streak_count ?? 0} icon={<TrophyIcon />} />
            <StatCard label="Từ đã thuộc" value={data.items_mastered ?? 0} icon={<GraduationIcon />} />
          </Box>

          <Typography variant="h6" gutterBottom>Huy hiệu đã mở khóa</Typography>
          {data.achievements.length === 0 ? (
            <Typography variant="body2" color="text.secondary">Chưa mở khóa huy hiệu nào.</Typography>
          ) : (
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              {data.achievements.map((a) => (
                <AchievementCard key={a.code} name={a.name} description={a.description} unlocked />
              ))}
            </Box>
          )}
        </>
      )}
    </Box>
  );
}

export default PublicProfile;
