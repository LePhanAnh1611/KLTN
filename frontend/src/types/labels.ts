/** Nhãn tiếng Việt cho các mã nội bộ hiện ra giao diện người học.
 *
 * Trước đây ba chỗ in thẳng mã ra màn hình — bảng số của đường cong học tập,
 * dòng mô tả khi rê chuột, và thẻ trò chơi — nên người học đọc được
 * `dkt_smart`, `srs_review`, `reverse_tap`. Mã nội bộ vẫn giữ nguyên trong dữ
 * liệu và trong API (đó là lõi khoa học), chỉ lớp hiển thị mới dịch.
 *
 * `SessionHistory` từng giữ một bản đồ riêng; gộp về đây để khỏi có hai bảng
 * nhãn lệch nhau.
 */

/** Chế độ một phiên học. */
export const SESSION_MODE_LABELS: Record<string, string> = {
  flashcard: 'Flashcard',
  quiz: 'Trắc nghiệm',
  cloze: 'Điền khuyết',
  matching: 'Ghép cặp',
  typing: 'Gõ từ',
  dictation: 'Nghe viết',
  mixed: 'Phiên trộn',
  dkt_smart: 'Học thông minh',
  srs_review: 'Ôn theo lịch',
  weak_review: 'Ôn điểm yếu',
  sm2: 'Ôn SM-2',
  game_rain: 'Mưa từ',
  game_spelling: 'Nghe đánh vần',
  game_match: 'Ghép cặp tốc độ',
};

/** Dạng bài của một lượt trả lời — mô tả HÀNH VI, không phải tên chế độ.
 *
 * Khác `SESSION_MODE_LABELS` ở chỗ: nhiều chế độ khác nhau cùng quy về một dạng
 * bài khi ghi lại (ví dụ ba trò chơi quy về gõ từ / nghe viết / ghép cặp).
 */
export const EXERCISE_FORMAT_LABELS: Record<string, string> = {
  flashcard: 'Lật thẻ',
  quiz: 'Trắc nghiệm',
  cloze: 'Điền khuyết',
  matching: 'Ghép cặp',
  typing: 'Gõ lại từ',
  dictation: 'Nghe rồi viết',
  dkt_smart: 'Học thông minh',
  srs_review: 'Ôn theo lịch',
  weak_review: 'Ôn điểm yếu',
  sm2: 'Ôn SM-2',
  mixed: 'Phiên trộn',
};

/** Trả nhãn tiếng Việt; không nhận ra mã thì trả chuỗi rỗng chứ KHÔNG trả lại
 * chính mã đó — để một mã lạ lọt ra màn hình là cách nó âm thầm sống mãi. */
export function formatLabel(code: string | null | undefined): string {
  if (!code) return '';
  return EXERCISE_FORMAT_LABELS[code] ?? '';
}

export function modeLabel(code: string | null | undefined): string {
  if (!code) return '';
  return SESSION_MODE_LABELS[code] ?? '';
}
