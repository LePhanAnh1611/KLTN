/** Mã lượt trả lời (UUID v4) gửi kèm mỗi lượt chấm khách quan.
 *
 * Server lưu SHA-256 của request khi có mã này (`request_hash`): nếu sau này
 * phát hiện lượt bị chấm sai, đáp án thật vẫn suy ngược lại được thay vì mất
 * hẳn — sự cố 2026-10-26 chỉ cứu được 34/316 lượt vì lượt chọn nghĩa thiếu mã.
 *
 * `crypto.randomUUID` chỉ có ở ngữ cảnh an toàn (https/localhost); mở qua địa
 * chỉ LAN bằng http thì dựng từ `getRandomValues` (có ở mọi ngữ cảnh).
 */
export function newAnswerId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
