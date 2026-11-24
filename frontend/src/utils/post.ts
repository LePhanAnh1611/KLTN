import type { PostCard } from '../api/community';

/** Bug #10: bảng tin chỉ hiện tên tài khoản, không hiện cấp/XP/streak. Bài
 * "Tiến độ" cũ đã chốt các số đó vào nội dung (UC-57) — ẩn các dòng ấy khi
 * hiển thị, giữ lại câu người đăng tự viết. Dữ liệu trong DB không đổi. */
const PROGRESS_STAT_LINE = /^(🎯 Cấp \d+|⭐ \d+ XP|📚 Đã thuộc \d+ từ)/u;

export function visibleContent(post: Pick<PostCard, 'post_type' | 'content'>): string {
  if (post.post_type !== 'progress') return post.content;
  return post.content
    .split('\n')
    .filter((line) => !PROGRESS_STAT_LINE.test(line.trim()))
    .join('\n')
    .trim();
}
