import { useMutation } from '@tanstack/react-query';

import { apiPost } from './client';

/** UC-03 — xác thực email. */
export interface VerifyEmailResponse {
  email: string;
  already_verified: boolean;
}

export function useVerifyEmail() {
  return useMutation({
    mutationFn: (token: string) =>
      apiPost<VerifyEmailResponse>('/api/v1/auth/verify-email', { token }),
  });
}

/** UC-03 luồng 1a — gửi lại email xác thực (cần đăng nhập). */
export function useResendVerification() {
  return useMutation({
    mutationFn: () => apiPost<{ message: string }>('/api/v1/auth/resend-verification', {}),
  });
}

/** UC-06 — quên mật khẩu. */
export function useForgotPassword() {
  return useMutation({
    mutationFn: (email: string) =>
      apiPost<{ message: string }>('/api/v1/auth/forgot-password', { email }),
  });
}

/** UC-06 — đặt lại mật khẩu bằng token trong email. */
export function useResetPassword() {
  return useMutation({
    mutationFn: (body: {
      token: string; new_password: string; new_password_confirm: string;
    }) => apiPost<void>('/api/v1/auth/reset-password', body),
  });
}
