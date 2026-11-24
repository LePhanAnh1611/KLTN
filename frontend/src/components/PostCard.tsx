import { useState } from 'react';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  POST_TYPE_LABELS,
  useAddComment,
  useComments,
  useDeletePost,
  useReportPost,
  useToggleLike,
  type PostCard as PostCardData,
} from '../api/community';
import ReportDialog from './ReportDialog';
import { visibleContent } from '../utils/post';
import { HeartIcon } from './icons';

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
  });
}

/** UC-50 — khu vực bình luận, chỉ tải khi người dùng mở. */
function CommentSection({ postId, onResult }: { postId: number; onResult: (msg: string) => void }) {
  const { data } = useComments(postId);
  const addComment = useAddComment(postId);
  const [draft, setDraft] = useState('');

  const submit = () => {
    if (!draft.trim()) return;
    addComment.mutate(draft.trim(), {
      onSuccess: () => setDraft(''),
      onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không gửi được bình luận.'),
    });
  };

  return (
    <Box sx={{ px: 2, pb: 2 }}>
      <Divider sx={{ mb: 1.5 }} />
      {data?.map((c) => (
        <Box key={c.id} sx={{ mb: 1 }}>
          <Typography variant="body2">
            <strong>{c.author_name}</strong>{' '}
            <Typography component="span" variant="caption" color="text.secondary">
              {formatTime(c.created_at)}
            </Typography>
          </Typography>
          <Typography variant="body2" color="text.secondary">{c.content}</Typography>
        </Box>
      ))}
      {data?.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          Chưa có bình luận.
        </Typography>
      )}
      <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
        <TextField
          size="small" fullWidth placeholder="Viết bình luận..."
          value={draft} onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
        />
        <Button variant="contained" disabled={!draft.trim() || addComment.isPending} onClick={submit}>
          Gửi
        </Button>
      </Box>
    </Box>
  );
}

interface PostCardProps {
  post: PostCardData;
  onResult: (msg: string) => void;
  onOpenAuthor?: (userId: number) => void;
}

/** Thẻ bài viết cộng đồng: nội dung + ảnh + thích (UC-51) + bình luận (UC-50)
 * + menu xóa bài của mình (UC-52) / báo cáo (UC-53). */
function PostCard({ post, onResult, onOpenAuthor }: PostCardProps) {
  const [showComments, setShowComments] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const toggleLike = useToggleLike();
  const deletePost = useDeletePost();
  const report = useReportPost(post.id);
  const content = visibleContent(post);

  // Bài khoe tiến độ không kèm lời nào: bỏ số liệu đi thì không còn gì để đọc.
  if (!content && !post.image_url) return null;

  return (
    <Card sx={{ mb: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, p: 2, pb: 1 }}>
        <Avatar src={post.author_avatar_url ?? undefined} sx={{ width: 40, height: 40 }}>
          {post.author_name.charAt(0).toUpperCase()}
        </Avatar>
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 700, cursor: onOpenAuthor ? 'pointer' : 'default' }}
            onClick={() => onOpenAuthor?.(post.author_id)}
          >
            {post.author_name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {formatTime(post.created_at)}
          </Typography>
        </Box>
        <Chip size="small" label={POST_TYPE_LABELS[post.post_type] ?? post.post_type} />
        <IconButton size="small" aria-label="Tùy chọn bài viết"
                    onClick={(e) => setMenuAnchor(e.currentTarget)}>
          ⋯
        </IconButton>
        <Menu anchorEl={menuAnchor} open={menuAnchor != null} onClose={() => setMenuAnchor(null)}>
          {post.is_mine ? (
            <MenuItem
              onClick={() => {
                setMenuAnchor(null);
                deletePost.mutate(post.id, {
                  onSuccess: () => onResult('Đã gỡ bài viết.'),
                  onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không gỡ được bài.'),
                });
              }}
            >
              Xóa bài
            </MenuItem>
          ) : (
            <MenuItem onClick={() => { setMenuAnchor(null); setReportOpen(true); }}>
              Báo cáo
            </MenuItem>
          )}
        </Menu>
      </Box>

      <Box sx={{ px: 2, pb: 1.5 }}>
        <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>{content}</Typography>
        {post.image_url && (
          <Box
            component="img" src={post.image_url} alt=""
            sx={{ mt: 1.5, maxWidth: '100%', borderRadius: 1, display: 'block' }}
          />
        )}
      </Box>

      <Box sx={{ display: 'flex', gap: 1, px: 1.5, pb: 1.5 }}>
        <Button
          size="small"
          color={post.liked_by_me ? 'primary' : 'inherit'}
          startIcon={<HeartIcon size={16} filled={post.liked_by_me} />}
          disabled={toggleLike.isPending}
          onClick={() =>
            toggleLike.mutate(post.id, {
              onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không thực hiện được.'),
            })
          }
        >
          Thích ({post.like_count})
        </Button>
        <Button size="small" color="inherit" onClick={() => setShowComments((v) => !v)}>
          Bình luận ({post.comment_count})
        </Button>
      </Box>

      {showComments && <CommentSection postId={post.id} onResult={onResult} />}

      <ReportDialog
        title="Báo cáo bài viết"
        open={reportOpen}
        pending={report.isPending}
        onClose={() => setReportOpen(false)}
        onSubmit={(body) =>
          report.mutate(body, {
            onSuccess: (res) => {
              onResult(res.merged
                ? 'Bạn đã báo cáo bài này rồi - báo cáo được gộp.'
                : 'Đã gửi báo cáo tới quản trị viên.');
              setReportOpen(false);
            },
            onError: (e) => onResult(e instanceof ApiError ? e.message : 'Không gửi được báo cáo.'),
          })
        }
      />
    </Card>
  );
}

export default PostCard;
