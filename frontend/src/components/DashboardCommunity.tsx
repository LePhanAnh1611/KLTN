import { Link as RouterLink } from 'react-router-dom';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

import { POST_TYPE_LABELS, useFeed, useLeaderboard } from '../api/community';
import type { LeaderboardRow, PostCard } from '../api/community';
import { visibleContent } from '../utils/post';
import { useFriends } from '../api/extras';
import type { FriendRow } from '../api/extras';
import { Panel, PanelEmpty, PanelHead, PanelSkeleton } from './DashboardPanel';
import { ChatIcon, FlameIcon, TrophyIcon, UsersIcon } from './icons';

/** Ba thẻ cộng đồng của Trang chủ — mỗi thẻ đúng một mục đích.
 *
 * Toàn bộ số liệu lấy qua React Query hooks trong `src/api`, không viết cứng
 * dòng nào: bảng xếp hạng (UC-54), bài đăng nổi bật (UC-49), bạn bè (UC-56).
 *
 * Mỗi thẻ có ba trạng thái tách bạch — **đang tải**, **rỗng**, **có dữ liệu**.
 * Gộp "đang tải" vào "rỗng" là lỗi hay gặp và gây hiểu nhầm nặng: trong lúc chờ
 * mạng, người học đọc được câu "bạn chưa có bạn bè nào" rồi đi mất.
 */

const TOP_N = 5;
const POSTS_N = 2;
const FRIENDS_N = 5;

function initials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase();
}

/** Huy hiệu hạng: 3 hạng đầu có màu riêng, còn lại là số thứ tự trung tính. */
function RankBadge({ rank, highlight }: { rank: number; highlight: boolean }) {
  const theme = useTheme();
  const medal: Record<number, string> = {
    1: '#D4A017',
    2: '#9AA5AD',
    3: '#B87333',
  };
  const tint = medal[rank] ?? (highlight ? theme.palette.primary.main : theme.palette.text.disabled);
  return (
    <Box
      sx={{
        width: 28,
        height: 28,
        flexShrink: 0,
        borderRadius: '50%',
        display: 'grid',
        placeItems: 'center',
        fontSize: 12.5,
        fontWeight: 800,
        color: rank <= 3 || highlight ? '#fff' : 'text.secondary',
        bgcolor: rank <= 3 || highlight ? tint : alpha(theme.palette.text.primary, 0.07),
      }}
    >
      {rank}
    </Box>
  );
}

function LeaderRow({ row }: { row: LeaderboardRow }) {
  const theme = useTheme();
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        px: 1,
        py: 0.85,
        borderRadius: '12px',
        // Dòng của chính người xem được tô nền để tìm thấy ngay mà không phải dò
        bgcolor: row.is_me ? alpha(theme.palette.primary.main, 0.09) : 'transparent',
      }}
    >
      <RankBadge rank={row.rank} highlight={row.is_me} />
      <Avatar src={row.avatar_url ?? undefined} sx={{ width: 30, height: 30, fontSize: 12.5 }}>
        {initials(row.display_name)}
      </Avatar>
      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
        <Typography
          sx={{
            fontWeight: row.is_me ? 800 : 600,
            fontSize: 14,
            lineHeight: 1.3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {row.display_name}
          {row.is_me && ' (bạn)'}
        </Typography>
        <Typography sx={{ fontSize: 12, color: 'text.secondary' }}>
          Cấp {row.level} · {row.level_title}
        </Typography>
      </Box>
      <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
        <Typography sx={{ fontWeight: 800, fontSize: 13.5, lineHeight: 1.2 }}>
          {row.xp.toLocaleString('vi-VN')} XP
        </Typography>
        {row.streak_count > 0 && (
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.4,
              color: theme.palette.warning.dark,
            }}
          >
            <FlameIcon size={12} />
            <Typography component="span" sx={{ fontSize: 11.5, fontWeight: 700 }}>
              {row.streak_count}
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}

/** UC-54 — top người học theo XP, luôn kèm vị trí của chính người xem. */
export function LeaderboardCard() {
  const theme = useTheme();
  // Phạm vi 'week': bảng toàn thời gian gần như đứng yên nên không tạo được
  // động lực; XP bảy ngày thì tuần nào cũng có cửa leo hạng.
  const { data, isPending, isError } = useLeaderboard('week');

  const top = (data?.items ?? []).slice(0, TOP_N);
  // Ngoài top thì backend trả `my_row` riêng — nối vào cuối để người xem luôn
  // thấy mình đứng đâu, kể cả khi hạng 300.
  const outsideTop = data?.my_row && (data.my_rank ?? 0) > TOP_N ? data.my_row : null;

  return (
    <Panel>
      <PanelHead
        tint={theme.palette.warning.main}
        icon={<TrophyIcon size={19} />}
        title="Bảng xếp hạng tuần"
        hint="XP tích được trong 7 ngày gần nhất."
        action={
          <Button
            variant="text"
            component={RouterLink}
            to="/community"
            sx={{ flexShrink: 0, fontWeight: 700 }}
          >
            Xem tất cả
          </Button>
        }
      />

      {isPending ? (
        <PanelSkeleton rows={4} height={46} />
      ) : isError ? (
        <PanelEmpty message="Chưa tải được bảng xếp hạng. Thử lại sau ít phút." />
      ) : top.length === 0 ? (
        <PanelEmpty
          message="Tuần này chưa ai ghi được XP nào. Học một phiên là bạn đứng đầu bảng ngay."
          action={
            <Button variant="contained" component={RouterLink} to="/word-sets" sx={{ fontWeight: 700 }}>
              Bắt đầu học
            </Button>
          }
        />
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          {top.map((row) => (
            <LeaderRow key={row.user_id} row={row} />
          ))}

          {outsideTop && (
            <>
              <Typography
                sx={{ textAlign: 'center', color: 'text.disabled', fontSize: 13, lineHeight: 1 }}
              >
                ···
              </Typography>
              <LeaderRow row={outsideTop} />
            </>
          )}

          {data?.my_rank == null && (
            <Typography sx={{ fontSize: 12.5, color: 'text.secondary', mt: 0.75, px: 1 }}>
              Bạn chưa có XP trong tuần này nên chưa được xếp hạng.
            </Typography>
          )}
        </Box>
      )}
    </Panel>
  );
}

function PostRow({ post }: { post: PostCard }) {
  const theme = useTheme();
  return (
    <Box
      component={RouterLink}
      to="/community"
      sx={{
        display: 'block',
        textDecoration: 'none',
        color: 'inherit',
        p: 1.5,
        borderRadius: '14px',
        border: '1px solid',
        borderColor: 'divider',
        transition: 'border-color 0.15s ease',
        '&:hover': { borderColor: alpha(theme.palette.primary.main, 0.5) },
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.75 }}>
        <Avatar src={post.author_avatar_url ?? undefined} sx={{ width: 24, height: 24, fontSize: 11 }}>
          {initials(post.author_name)}
        </Avatar>
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 13,
            minWidth: 0,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {post.author_name}
        </Typography>
        <Chip
          size="small"
          label={POST_TYPE_LABELS[post.post_type] ?? post.post_type}
          sx={{
            height: 20,
            fontSize: 11,
            fontWeight: 700,
            flexShrink: 0,
            bgcolor: alpha(theme.palette.secondary.main, 0.13),
            color: theme.palette.secondary.dark,
          }}
        />
      </Box>

      <Typography
        sx={{
          fontSize: 13.5,
          lineHeight: 1.5,
          color: 'text.primary',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {visibleContent(post)}
      </Typography>

      <Typography sx={{ fontSize: 12, color: 'text.secondary', mt: 0.75 }}>
        {post.like_count} lượt thích · {post.comment_count} bình luận
      </Typography>
    </Box>
  );
}

/** UC-49 — vài bài mới nhất của cộng đồng, sắp theo mức tương tác. */
export function FeaturedPostsCard() {
  const theme = useTheme();
  // Lấy dư rồi mới xếp theo tương tác: backend trả theo thời gian, nên muốn
  // "nổi bật" phải có đủ bài để chọn, không thể lấy đúng 3 bài mới nhất.
  const { data, isPending, isError } = useFeed({ page: 1, page_size: 12 });

  const posts = [...(data?.items ?? [])]
    .filter((p) => visibleContent(p) !== '')   // bài khoe số liệu trống lời: bỏ (bug #10)
    .sort((a, b) => b.like_count + b.comment_count - (a.like_count + a.comment_count))
    .slice(0, POSTS_N);

  return (
    <Panel>
      <PanelHead
        tint={theme.palette.secondary.main}
        icon={<ChatIcon size={19} />}
        title="Bài nổi bật"
        hint="Bài được tương tác nhiều nhất trong những bài gần đây."
        action={
          <Button
            variant="text"
            component={RouterLink}
            to="/community"
            sx={{ flexShrink: 0, fontWeight: 700 }}
          >
            Vào cộng đồng
          </Button>
        }
      />

      {isPending ? (
        <PanelSkeleton rows={3} height={78} />
      ) : isError ? (
        <PanelEmpty message="Chưa tải được bảng tin cộng đồng. Thử lại sau ít phút." />
      ) : posts.length === 0 ? (
        <PanelEmpty
          message="Cộng đồng chưa có bài viết nào. Bạn có thể là người mở đầu - chia sẻ một mẹo học hoặc một từ hay."
          action={
            <Button variant="contained" component={RouterLink} to="/community" sx={{ fontWeight: 700 }}>
              Viết bài đầu tiên
            </Button>
          }
        />
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          {posts.map((post) => (
            <PostRow key={post.id} post={post} />
          ))}
        </Box>
      )}
    </Panel>
  );
}

function FriendRowItem({ friend }: { friend: FriendRow }) {
  const theme = useTheme();
  return (
    <Box
      component={RouterLink}
      to={`/users/${friend.user_id}`}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.25,
        px: 1,
        py: 0.85,
        borderRadius: '12px',
        textDecoration: 'none',
        color: 'inherit',
        transition: 'background-color 0.15s ease',
        '&:hover': { bgcolor: alpha(theme.palette.text.primary, 0.04) },
      }}
    >
      <Avatar src={friend.avatar_url ?? undefined} sx={{ width: 32, height: 32, fontSize: 13 }}>
        {initials(friend.display_name)}
      </Avatar>
      <Box sx={{ minWidth: 0, flexGrow: 1 }}>
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: 14,
            lineHeight: 1.3,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {friend.display_name}
        </Typography>
        <Typography sx={{ fontSize: 12, color: 'text.secondary' }}>
          Cấp {friend.level} · {friend.xp.toLocaleString('vi-VN')} XP
        </Typography>
      </Box>

      {friend.streak_count > 0 ? (
        <Box
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.4,
            flexShrink: 0,
            px: 0.9,
            py: 0.3,
            borderRadius: '9999px',
            bgcolor: alpha(theme.palette.warning.main, 0.14),
            color: theme.palette.warning.dark,
          }}
        >
          <FlameIcon size={13} />
          <Typography component="span" sx={{ fontSize: 12, fontWeight: 800 }}>
            {friend.streak_count}
          </Typography>
        </Box>
      ) : (
        // Streak 0 nói một điều thật: bạn này đang đứt chuỗi. Hiện chữ nhạt còn
        // hơn để trống, vì trống trông như thiếu dữ liệu.
        <Typography sx={{ fontSize: 12, color: 'text.disabled', flexShrink: 0 }}>
          chưa có chuỗi
        </Typography>
      )}
    </Box>
  );
}

/** UC-56 — bạn bè và mức độ hoạt động của họ (cấp, XP, chuỗi ngày học). */
export function FriendsActivityCard() {
  const theme = useTheme();
  const { data, isPending, isError } = useFriends();

  // Ai đang giữ chuỗi dài nhất lên trước: đó mới là "đang hoạt động", còn XP
  // tích lũy chỉ nói về quá khứ.
  const friends = [...(data ?? [])]
    .sort((a, b) => b.streak_count - a.streak_count || b.xp - a.xp)
    .slice(0, FRIENDS_N);

  return (
    <Panel>
      <PanelHead
        tint={theme.palette.primary.main}
        icon={<UsersIcon size={19} />}
        title="Bạn bè đang học"
        hint="Xếp theo chuỗi ngày học liên tiếp."
        action={
          <Button
            variant="text"
            component={RouterLink}
            to="/community"
            sx={{ flexShrink: 0, fontWeight: 700 }}
          >
            Quản lý
          </Button>
        }
      />

      {isPending ? (
        <PanelSkeleton rows={4} height={48} />
      ) : isError ? (
        <PanelEmpty message="Chưa tải được danh sách bạn bè. Thử lại sau ít phút." />
      ) : friends.length === 0 ? (
        <PanelEmpty
          message="Bạn chưa kết bạn với ai. Thấy một người học trên bảng xếp hạng hay trong cộng đồng thì mở hồ sơ của họ và gửi lời mời."
          action={
            <Button variant="contained" component={RouterLink} to="/community" sx={{ fontWeight: 700 }}>
              Tìm bạn học
            </Button>
          }
        />
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25 }}>
          {friends.map((friend) => (
            <FriendRowItem key={friend.user_id} friend={friend} />
          ))}
          {(data?.length ?? 0) > FRIENDS_N && (
            <Typography sx={{ fontSize: 12.5, color: 'text.secondary', mt: 0.75, px: 1 }}>
              và {(data?.length ?? 0) - FRIENDS_N} người bạn khác
            </Typography>
          )}
        </Box>
      )}
    </Panel>
  );
}

/** Dải ba thẻ cộng đồng — dùng ở Trang chủ. */
export default function DashboardCommunity() {
  return (
    <Box
      sx={{
        display: 'grid',
        // Cùng mốc với lưới học tập phía trên: hai cột từ 'lg', ba cột từ 'xl'.
        gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' },
        gap: 2,
        alignItems: 'start',
      }}
    >
      <LeaderboardCard />
      <FeaturedPostsCard />
      <FriendsActivityCard />
    </Box>
  );
}
