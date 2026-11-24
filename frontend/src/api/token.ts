export interface JwtPayload {
  sub: string;
  role: string;
  exp: number;
}

const STORAGE_KEY = 'lh.access_token';

/**
 * Token giữ trong bộ nhớ VÀ localStorage, để tải lại trang / mở lại link hôm sau
 * không phải đăng nhập lại.
 *
 * Trước đây chỉ giữ trong bộ nhớ (tải lại trang là mất). Đổi cho đợt pilot: người
 * học mở app trên điện thoại mỗi ngày, bắt đăng nhập lại mỗi lần là lý do số một
 * khiến họ bỏ dở — mà dữ liệu nhiều ngày liên tiếp là thứ pilot cần nhất. Thời hạn
 * vẫn do backend quyết định (ACCESS_TOKEN_EXPIRE_MINUTES); token hết hạn bị bỏ ngay
 * khi nạp lại.
 */
let currentToken: string | null = loadStoredToken();

function loadStoredToken(): string | null {
  try {
    const token = window.localStorage.getItem(STORAGE_KEY);
    if (!token) return null;
    if (decodeJwtPayload(token).exp * 1000 <= Date.now()) {
      window.localStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return token;
  } catch {
    return null; // trình duyệt chặn bộ nhớ / token hỏng -> coi như chưa đăng nhập
  }
}

export function getToken(): string | null {
  return currentToken;
}

export function setToken(token: string | null): void {
  currentToken = token;
  try {
    if (token) window.localStorage.setItem(STORAGE_KEY, token);
    else window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // chế độ ẩn danh / chặn cookie: vẫn chạy được, chỉ không nhớ đăng nhập
  }
}

export function decodeJwtPayload(token: string): JwtPayload {
  const payload = token.split('.')[1];
  const json = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
  return JSON.parse(json) as JwtPayload;
}
