import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Badge from '@mui/material/Badge';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ListItemButton from '@mui/material/ListItemButton';
import Menu from '@mui/material/Menu';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import { useMarkAllRead, useMarkRead, useNotifications } from '../api/notifications';
import { BellIcon } from './icons';

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

/** UC-58 — chuông + badge số chưa đọc; bấm một thông báo thì đánh dấu đã đọc
 * (UC-59) và điều hướng theo `link` của thông báo. */
function NotificationBell() {
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const { data } = useNotifications();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();

  const unread = data?.unread_count ?? 0;

  return (
    <>
      <Tooltip title="Thông báo">
        <IconButton aria-label="Thông báo" color="inherit" onClick={(e) => setAnchor(e.currentTarget)}>
          <Badge badgeContent={unread} color="error">
            <BellIcon />
          </Badge>
        </IconButton>
      </Tooltip>

      <Menu
        anchorEl={anchor} open={anchor != null} onClose={() => setAnchor(null)}
        slotProps={{ paper: { sx: { width: 360, maxHeight: 460 } } }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', px: 2, py: 1 }}>
          <Typography variant="subtitle2" sx={{ flexGrow: 1, fontWeight: 900, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Thông báo</Typography>
          {unread > 0 && (
            <Button size="small" onClick={() => markAllRead.mutate()}>Đọc tất cả</Button>
          )}
        </Box>
        <Divider />

        {(data?.items.length ?? 0) === 0 && (
          <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>
            Chưa có thông báo nào.
          </Typography>
        )}

        {data?.items.map((n) => (
          <ListItemButton
            key={n.id}
            // Chưa đọc: nền cam nhạt + vạch cam bên trái + chấm cam, đọc lướt là
            // thấy ngay; đã đọc: nền trắng, chữ nhạt (chủ dự án 2026-10-27).
            sx={{
              alignItems: 'flex-start', gap: 1.25, mx: 1, my: 0.5, borderRadius: '14px',
              borderLeft: '4px solid', borderColor: n.is_read ? 'transparent' : '#F39A3D',
              bgcolor: n.is_read ? 'transparent' : '#FFF1E2',
              '&:hover': { bgcolor: n.is_read ? '#F6EFE8' : '#FFE7CF' },
            }}
            onClick={() => {
              if (!n.is_read) markRead.mutate(n.id);
              setAnchor(null);
              if (n.link) navigate(n.link);
            }}
          >
            <Box sx={{ mt: 0.75, width: 9, height: 9, borderRadius: '50%', flexShrink: 0, bgcolor: n.is_read ? '#E2D7CC' : '#F39A3D' }} />
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="body2" sx={{ fontWeight: n.is_read ? 600 : 900, color: n.is_read ? 'text.secondary' : 'text.primary' }}>
                {n.title}
              </Typography>
              {n.body && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }} noWrap>
                  {n.body}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary">
                {formatTime(n.created_at)}
              </Typography>
            </Box>
          </ListItemButton>
        ))}
      </Menu>
    </>
  );
}

export default NotificationBell;
