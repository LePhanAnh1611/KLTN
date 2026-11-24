import { getToken } from './token';

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000';

export interface ValidationErrorItem {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export class ApiError extends Error {
  status: number;
  detail: string | ValidationErrorItem[] | undefined;

  constructor(status: number, detail: string | ValidationErrorItem[] | undefined, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<TResponse>(path: string, init: RequestInit): Promise<TResponse> {
  const token = getToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  const data = await response.json().catch(() => undefined);

  if (!response.ok) {
    const detail = data?.detail as string | ValidationErrorItem[] | undefined;
    throw new ApiError(response.status, detail, extractMessage(detail, response.statusText));
  }

  return data as TResponse;
}

export function apiGet<TResponse>(path: string): Promise<TResponse> {
  return request<TResponse>(path, { method: 'GET' });
}

export function apiPost<TResponse>(path: string, body: unknown): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function apiPut<TResponse>(path: string, body: unknown): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export function apiPatch<TResponse>(path: string, body: unknown): Promise<TResponse> {
  return request<TResponse>(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** `body` tùy chọn — UC-12 xóa tài khoản gửi kèm mật khẩu xác nhận. */
export function apiDelete(path: string, body?: unknown): Promise<unknown> {
  return request<unknown>(path, {
    method: 'DELETE',
    ...(body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  });
}

/** multipart/form-data với nhiều trường (file + text) — dùng cho endpoint chấm
 * nói. KHÔNG đặt Content-Type bằng tay: trình duyệt tự thêm boundary khi body là
 * FormData, đặt tay sẽ làm mất boundary và server không parse được. */
export function apiPostForm<TResponse>(path: string, form: FormData): Promise<TResponse> {
  return request<TResponse>(path, { method: 'POST', body: form });
}

/** multipart/form-data upload — do NOT set Content-Type manually, the browser
 * adds the multipart boundary automatically when the body is a FormData. */
export function apiUpload<TResponse>(path: string, file: File): Promise<TResponse> {
  const formData = new FormData();
  formData.append('file', file);
  return request<TResponse>(path, { method: 'POST', body: formData });
}

function extractMessage(detail: string | ValidationErrorItem[] | undefined, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((item) => item.msg).join('; ');
  }
  return fallback;
}

/** Maps FastAPI/Pydantic 422 detail into { fieldName: message }. Errors without a
 * specific field (e.g. cross-field validators, loc = ["body"]) are not included. */
export function getFieldErrors(detail: string | ValidationErrorItem[] | undefined): Record<string, string> {
  if (!Array.isArray(detail)) return {};
  const errors: Record<string, string> = {};
  for (const item of detail) {
    if (item.loc.length > 1) {
      const field = item.loc[item.loc.length - 1];
      if (typeof field === 'string') {
        errors[field] = item.msg;
      }
    }
  }
  return errors;
}

/** General (non-field-specific) error messages, e.g. password/password_confirm mismatch. */
export function getGeneralErrors(detail: string | ValidationErrorItem[] | undefined): string[] {
  if (typeof detail === 'string') return [detail];
  if (!Array.isArray(detail)) return [];
  return detail.filter((item) => item.loc.length <= 1).map((item) => item.msg);
}
