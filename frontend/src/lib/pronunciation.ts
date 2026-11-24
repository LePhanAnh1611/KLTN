/** Chấm phát âm một từ: so bản ghi nhận dạng được với từ đích.
 *
 * Lưu ý về giới hạn: đây là so khớp ở mức TỪ do bộ nhận dạng của trình duyệt trả
 * về, không phải phân tích âm vị. Điểm cao nghĩa là "máy nghe ra đúng từ", chưa
 * đảm bảo trọng âm/ngữ điệu chuẩn.
 */

export type PronunciationBand = 'good' | 'fair' | 'poor';

export interface PronunciationResult {
  score: number;              // 0..100
  band: PronunciationBand;
  heard: string;              // phương án gần đúng nhất mà máy nghe được
  exact: boolean;
}

/** Bỏ dấu câu, hạ chữ thường, gộp khoảng trắng. */
export function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s']/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** Khoảng cách Levenshtein (số phép sửa tối thiểu giữa hai chuỗi). */
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;

  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const curr = [i];
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    prev = curr;
  }
  return prev[b.length];
}

/** Độ giống nhau 0..1 theo tỉ lệ ký tự khớp. */
export function similarity(a: string, b: string): number {
  const longest = Math.max(a.length, b.length);
  if (longest === 0) return 1;
  return 1 - levenshtein(a, b) / longest;
}

/** Bỏ luôn khoảng trắng — bộ nhận dạng hay tách từ ghép ("deadline" -> "dead
 * line"). Đó là cách máy phân tách, không phải lỗi phát âm, nên không trừ điểm. */
function compact(text: string): string {
  return normalize(text).replace(/[\s']/g, '');
}

/** Điểm cao nhất giữa so khớp có và không có khoảng trắng. */
function bestSimilarity(target: string, candidate: string): number {
  return Math.max(
    similarity(normalize(target), normalize(candidate)),
    similarity(compact(target), compact(candidate)),
  );
}

// Đặt 90 (không phải 85) để lệch một chữ cái ở từ ngắn — tức NGHE RA TỪ KHÁC,
// ví dụ "contract" -> "contact" — không được coi là phát âm tốt.
export const GOOD_THRESHOLD = 90;
export const FAIR_THRESHOLD = 60;

function bandOf(score: number): PronunciationBand {
  if (score >= GOOD_THRESHOLD) return 'good';
  if (score >= FAIR_THRESHOLD) return 'fair';
  return 'poor';
}

/**
 * Chấm điểm với danh sách phương án mà bộ nhận dạng trả về.
 *
 * Lấy phương án GIỐNG NHẤT chứ không chỉ phương án đầu: bộ nhận dạng hay ưu tiên
 * từ phổ biến hơn (VD nói "bug" ra "bag"), nên xét cả các phương án sau sẽ công
 * bằng hơn với người học.
 */
export function scorePronunciation(target: string, alternatives: string[]): PronunciationResult {
  const wanted = normalize(target);
  const candidates = alternatives.map(normalize).filter(Boolean);

  if (candidates.length === 0) {
    return { score: 0, band: 'poor', heard: '', exact: false };
  }

  let best = candidates[0];
  let bestScore = -1;
  for (const candidate of candidates) {
    const value = Math.round(bestSimilarity(wanted, candidate) * 100);
    if (value > bestScore) {
      bestScore = value;
      best = candidate;
    }
  }

  return {
    score: bestScore,
    band: bandOf(bestScore),
    heard: best,
    // coi là khớp hoàn toàn kể cả khi máy tách từ ghép thành hai chữ
    exact: compact(best) === compact(wanted),
  };
}

export const BAND_TEXT: Record<PronunciationBand, string> = {
  good: 'Phát âm tốt',
  fair: 'Gần đúng, thử lại nhé',
  poor: 'Chưa khớp, nghe mẫu rồi đọc lại',
};
