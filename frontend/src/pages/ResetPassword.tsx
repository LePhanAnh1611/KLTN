import { useState } from 'react';
import { Link as RouterLink, useNavigate, useSearchParams } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';

import AuthLayout, { AuthAltAction, AuthPasswordField, AuthStatus } from '../components/AuthLayout';
import { useResetPassword } from '../api/account';
import { ApiError, getFieldErrors } from '../api/client';
import { AlertIcon, ArrowLeftIcon } from '../components/icons';

/** UC-06 bước 3 — đặt mật khẩu mới bằng token trong liên kết email. */
function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') ?? '';
  const reset = useResetPassword();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    reset.mutate(
      { token, new_password: password, new_password_confirm: confirm },
      {
        onSuccess: () => navigate('/login', { replace: true }),
        onError: (err) => {
          if (err instanceof ApiError) {
            setFieldErrors(getFieldErrors(err.detail));
            setError(err.status === 422 ? null : err.message);
          } else {
            setError('Đặt lại mật khẩu thất bại.');
          }
        },
      },
    );
  };

  if (!token) {
    return (
      <AuthLayout title="Liên kết không hợp lệ" centered>
        <AuthStatus
          tone="error"
          icon={<AlertIcon size={26} />}
          title="Thiếu mã đặt lại"
          description="Link có thể bị thiếu. Hãy yêu cầu link mới."
        />
        <Button
          component={RouterLink}
          to="/forgot-password"
          fullWidth
          variant="contained"
          size="large"
          sx={{ mt: 3 }}
        >
          Yêu cầu liên kết mới
        </Button>

        <AuthAltAction>
          <Link
            component={RouterLink}
            to="/login"
            sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}
          >
            <ArrowLeftIcon size={16} />
            Quay lại đăng nhập
          </Link>
        </AuthAltAction>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Đặt lại mật khẩu" subtitle="Chọn mật khẩu mới cho tài khoản của bạn.">
      <Box component="form" onSubmit={submit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {error && (
          <Alert
            severity="error"
            action={
              <Button size="small" color="inherit" component={RouterLink} to="/forgot-password">
                Gửi lại
              </Button>
            }
          >
            {error}
          </Alert>
        )}

        <AuthPasswordField
          label="Mật khẩu mới"
          autoComplete="new-password"
          autoFocus
          value={password}
          required
          onChange={(e) => setPassword(e.target.value)}
          error={Boolean(fieldErrors.new_password)}
          helperText={fieldErrors.new_password || 'Tối thiểu 8 ký tự, có cả chữ và số'}
        />
        <AuthPasswordField
          label="Xác nhận mật khẩu mới"
          autoComplete="new-password"
          value={confirm}
          required
          onChange={(e) => setConfirm(e.target.value)}
          error={Boolean(fieldErrors.new_password_confirm)}
          helperText={fieldErrors.new_password_confirm}
        />

        <Button type="submit" variant="contained" size="large" loading={reset.isPending}>
          Đổi mật khẩu
        </Button>
      </Box>

      <AuthAltAction>
        <Link
          component={RouterLink}
          to="/login"
          sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}
        >
          <ArrowLeftIcon size={16} />
          Quay lại đăng nhập
        </Link>
      </AuthAltAction>
    </AuthLayout>
  );
}

export default ResetPassword;
