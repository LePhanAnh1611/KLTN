import { useState } from 'react';
import type { FormEvent } from 'react';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { API_BASE_URL } from '../api/client';
import {
  useFriendRequests,
  useFriends,
  useRespondFriendRequest,
  useSendFriendRequest,
  useUnfriend,
  useUserSearch,
  type FriendRequestRow,
  type FriendRow,
  type UserSearchRow,
} from '../api/extras';
import { useAuth } from '../context/AuthContext';
import EmptyState from './EmptyState';
import SectionCard from './SectionCard';
import { UsersIcon } from './icons';

/* Bug #10 — tab Bạn bè chỉ làm hai việc: TÌM người để kết bạn (theo tên hoặc ID)
 * và xem DANH SÁCH bạn hiện có. Thẻ "Chia sẻ tiến độ" cũ (đăng XP/streak lên
 * bảng tin) đã bỏ khỏi đây. Mỗi người chỉ hiện tên + ID, không hiện XP/streak. */

function PersonAvatar({ name, url }: { name: string; url: string | null }) {
  return (
    <Avatar src={url ? `${API_BASE_URL}${url}` : undefined} sx={{ width: 40, height: 40 }}>
      {name.charAt(0).toUpperCase()}
    </Avatar>
  );
}

/** Tên + ID, bấm vào mở hồ sơ. Dùng chung cho cả 3 danh sách. */
function PersonName({ id, name, onOpen }: { id: number; name: string; onOpen?: () => void }) {
  return (
    <Box
      sx={{ flexGrow: 1, minWidth: 0, cursor: onOpen ? 'pointer' : 'default' }}
      onClick={onOpen}
    >
      <Typography variant="body2" sx={{ fontWeight: 700, overflow: 'hidden',
                                        textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {name}
      </Typography>
      <Typography variant="caption" color="text.secondary">ID #{id}</Typography>
    </Box>
  );
}

const rowSx = {
  display: 'flex', alignItems: 'center', gap: 1.5, py: 1.25, flexWrap: 'wrap',
  borderTop: 1, borderColor: 'divider', '&:first-of-type': { borderTop: 0 },
} as const;

/** Nút hành động của một kết quả tìm kiếm — chữ đi theo trạng thái quan hệ. */
function SearchAction({ row, onResult }: { row: UserSearchRow; onResult: (msg: string) => void }) {
  const send = useSendFriendRequest();
  const respond = useRespondFriendRequest();
  const { status, is_incoming, friendship_id } = row.friendship;

  if (status === 'accepted') return <Chip size="small" color="success" label="Bạn bè" />;
  if (status === 'pending' && !is_incoming) return <Chip size="small" label="Đã gửi lời mời" />;
  if (status === 'pending' && is_incoming && friendship_id !== null) {
    return (
      <Button size="small" variant="contained" disabled={respond.isPending}
              onClick={() => respond.mutate({ id: friendship_id, accept: true },
                { onSuccess: () => onResult('Đã thêm bạn.') })}>
        Đồng ý
      </Button>
    );
  }
  return (
    <Button size="small" variant="contained" disabled={send.isPending}
            onClick={() => send.mutate(row.user_id, {
              onSuccess: () => onResult(`Đã gửi lời mời tới ${row.display_name}.`),
              onError: () => onResult('Không gửi được lời mời.'),
            })}>
      Kết bạn
    </Button>
  );
}

function FindFriendsCard({ onOpenUser, onResult }: {
  onOpenUser: (id: number) => void; onResult: (msg: string) => void;
}) {
  const { userId } = useAuth();
  const [draft, setDraft] = useState('');
  const [term, setTerm] = useState('');
  const search = useUserSearch(term);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setTerm(draft.trim());
  };
  const isNameTooShort = term.length > 0 && !/^#?\d+$/.test(term) && term.length < 2;

  return (
    <SectionCard
      title="Tìm bạn"
      caption={userId ? `Nhập tên hoặc ID. ID của bạn là #${userId} - gửi cho bạn bè để họ tìm bạn.`
                      : 'Nhập tên hoặc ID.'}
      sx={{ mb: 3 }}
    >
      <Box component="form" onSubmit={submit} sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        <TextField
          size="small" sx={{ flex: '1 1 200px' }}
          placeholder="Ví dụ: Trang hoặc #12"
          value={draft} onChange={(e) => setDraft(e.target.value)}
          slotProps={{ htmlInput: { maxLength: 100, 'aria-label': 'Tìm theo tên hoặc ID' } }}
        />
        <Button type="submit" variant="contained" disabled={!draft.trim()}>Tìm</Button>
      </Box>

      {search.isFetching && <LinearProgress sx={{ mt: 1.5 }} />}
      {isNameTooShort && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
          Nhập ít nhất 2 ký tự để tìm theo tên.
        </Typography>
      )}
      {search.isError && (
        <Typography variant="body2" color="error" sx={{ mt: 1.5 }}>
          Không tìm được, thử lại nhé.
        </Typography>
      )}
      {search.data && term && !isNameTooShort && (
        search.data.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
            Không thấy ai khớp “{term}”.
          </Typography>
        ) : (
          <Box sx={{ mt: 1 }}>
            {search.data.map((row) => (
              <Box key={row.user_id} sx={rowSx}>
                <PersonAvatar name={row.display_name} url={row.avatar_url} />
                <PersonName id={row.user_id} name={row.display_name}
                            onOpen={() => onOpenUser(row.user_id)} />
                <SearchAction row={row} onResult={onResult} />
              </Box>
            ))}
          </Box>
        )
      )}
    </SectionCard>
  );
}

function RequestRow({ row, onOpenUser, onResult }: {
  row: FriendRequestRow; onOpenUser: (id: number) => void; onResult: (msg: string) => void;
}) {
  const respond = useRespondFriendRequest();

  return (
    <Box sx={rowSx}>
      <PersonAvatar name={row.display_name} url={row.avatar_url} />
      <PersonName id={row.user_id} name={row.display_name} onOpen={() => onOpenUser(row.user_id)} />
      <Box sx={{ display: 'flex', gap: 1 }}>
        <Button
          size="small" variant="contained" disabled={respond.isPending}
          onClick={() => respond.mutate({ id: row.friendship_id, accept: true },
            { onSuccess: () => onResult('Đã thêm bạn.') })}
        >
          Đồng ý
        </Button>
        <Button
          size="small" disabled={respond.isPending}
          onClick={() => respond.mutate({ id: row.friendship_id, accept: false },
            { onSuccess: () => onResult('Đã từ chối lời mời.') })}
        >
          Từ chối
        </Button>
      </Box>
    </Box>
  );
}

function FriendListRow({ row, onOpenUser, onResult }: {
  row: FriendRow; onOpenUser: (id: number) => void; onResult: (msg: string) => void;
}) {
  const unfriend = useUnfriend();

  return (
    <Box sx={rowSx}>
      <PersonAvatar name={row.display_name} url={row.avatar_url} />
      <PersonName id={row.user_id} name={row.display_name} onOpen={() => onOpenUser(row.user_id)} />
      <Button size="small" color="error" disabled={unfriend.isPending}
              onClick={() => unfriend.mutate(row.user_id,
                { onSuccess: () => onResult('Đã hủy kết bạn.') })}>
        Hủy kết bạn
      </Button>
    </Box>
  );
}

/** UC-56 — tìm bạn + lời mời đến + danh sách bạn. */
function FriendsTab({ onOpenUser, onResult }: {
  onOpenUser: (id: number) => void; onResult: (msg: string) => void;
}) {
  const friends = useFriends();
  const requests = useFriendRequests();
  // Danh sách bạn chỉ hiện tên nên xếp theo tên cho dễ dò (API xếp theo XP).
  const sorted = [...(friends.data ?? [])].sort((a, b) =>
    a.display_name.localeCompare(b.display_name, 'vi'));

  return (
    <Box>
      <FindFriendsCard onOpenUser={onOpenUser} onResult={onResult} />

      {(requests.data?.length ?? 0) > 0 && (
        <SectionCard
          title="Lời mời kết bạn"
          action={<Chip size="small" color="primary" label={requests.data!.length} />}
          sx={{ mb: 3 }}
        >
          {requests.data!.map((row) => (
            <RequestRow key={row.friendship_id} row={row}
                        onOpenUser={onOpenUser} onResult={onResult} />
          ))}
        </SectionCard>
      )}

      {friends.isLoading && <LinearProgress />}

      {friends.data && friends.data.length === 0 ? (
        <EmptyState
          icon={<UsersIcon size={24} />}
          title="Chưa có bạn nào"
          description="Tìm theo tên hoặc ID rồi bấm Kết bạn."
        />
      ) : friends.data && (
        <SectionCard title={`Bạn bè (${sorted.length})`}>
          {sorted.map((row) => (
            <FriendListRow key={row.user_id} row={row}
                           onOpenUser={onOpenUser} onResult={onResult} />
          ))}
        </SectionCard>
      )}
    </Box>
  );
}

export default FriendsTab;
