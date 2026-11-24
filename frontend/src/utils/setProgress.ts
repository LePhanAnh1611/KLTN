/**
 * Tiến độ một bộ từ / một chặng — 3 nấc thay cho một con số % duy nhất.
 *
 * Vì sao bỏ "%": "đã thuộc" theo BR-01 rất khắt khe (mastery >= 0.9 VÀ đủ lượt
 * đúng), nên người vừa học 20/50 từ vẫn thấy 0% — công sức không hiện ra, còn
 * con số % thì không nói được "phải làm gì tiếp". Ở đây tách:
 *  - đã thuộc  : đạt BR-01 (chặng lộ trình: đạt ngưỡng của chặng)
 *  - đang học  : đã gặp ít nhất một lần nhưng chưa thuộc
 *  - chưa học  : phần còn lại
 * và luôn kèm MỘT câu gợi bước tiếp theo bằng số từ cụ thể.
 *
 * Hàm thuần (không React) để test bằng `node --test`.
 */

export interface SetProgressInput {
  total: number;
  mastered: number;
  learning: number;
  /** Số từ cần thuộc để "xong" (chặng lộ trình xong ở 80%). Bỏ trống = cả bộ. */
  goal?: number;
}

export interface SetProgressView {
  mastered: number;
  learning: number;
  fresh: number;
  /** Bề rộng (%) từng đoạn của thanh, cộng lại <= 100. */
  masteredPct: number;
  learningPct: number;
  /** Mốc mục tiêu trên thanh (%), null khi mục tiêu = cả bộ. */
  goalPct: number | null;
  goal: number;
  done: boolean;
  /** Câu gợi bước tiếp theo — luôn là việc làm được ngay. */
  hint: string;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

export function describeSetProgress({ total, mastered, learning, goal }: SetProgressInput): SetProgressView {
  const t = Math.max(0, Math.floor(total));
  const m = clamp(Math.floor(mastered), 0, t);
  const l = clamp(Math.floor(learning), 0, t - m);
  const fresh = t - m - l;
  const g = goal != null && goal > 0 ? clamp(Math.floor(goal), 1, t || 1) : t;
  const done = t > 0 && m >= g;
  const left = Math.max(g - m, 0);

  let hint: string;
  // Câu ngắn (vừa thẻ 230px): luôn nêu số từ còn thiếu + việc nên làm.
  if (t === 0) hint = 'Bộ chưa có từ nào';
  else if (done) hint = g < t ? 'Đã qua chặng · thuộc nốt cả bộ nhé' : 'Thuộc cả bộ · nhớ ôn đều nhé';
  else if (m === 0 && l === 0) hint = 'Chưa học · bắt đầu vài từ thôi';
  else {
    // "Còn N từ chưa thuộc" khi mục tiêu là cả bộ; với chặng lộ trình, N là số từ
    // cần thuộc thêm để qua chặng (tiêu đề đã ghi "để qua chặng") nên không thêm chữ.
    // Không dùng "sắp thuộc": nhóm `learning` chỉ cần gặp 1 lần, chưa chắc gần thuộc.
    const head = `Còn ${left} từ${g < t ? '' : ' chưa thuộc'}`;
    if (l >= left) hint = `${head} · ôn tiếp là thuộc`;
    else if (l > 0) hint = `${head} · ôn ${l} từ đang học trước`;
    else hint = `${head} · học tiếp từ mới`;
  }

  return {
    mastered: m,
    learning: l,
    fresh,
    masteredPct: t ? (m / t) * 100 : 0,
    learningPct: t ? (l / t) * 100 : 0,
    goalPct: t && g < t ? (g / t) * 100 : null,
    goal: g,
    done,
    hint,
  };
}
