import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import TextField from '@mui/material/TextField';

import AuthLayout, { AuthAltAction, AuthPasswordField } from '../components/AuthLayout';
import { ApiError, getFieldErrors, getGeneralErrors } from '../api/client';
import { useLogin } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import type { LoginRequest } from '../types/auth';

const EMPTY_FORM: LoginRequest = { email: '', password: '' };

function Login() {
  const [form, setForm] = useState<LoginRequest>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalErrors, setGeneralErrors] = useState<string[]>([]);
  const loginMutation = useLogin();
  const auth = useAuth();
  const navigate = useNavigate();

  const handleChange =
    (field: keyof LoginRequest) => (event: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: event.target.value }));
    };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFieldErrors({});
    setGeneralErrors([]);

    loginMutation.mutate(form, {
      onSuccess: (data) => {
        const role = auth.login(data.access_token);
        // Chỉ có trang chủ ("/") ở M0 — chưa có màn vận hành Admin (UC-73+),
        // nên admin cũng tạm điều hướng về đây.
        navigate(role === 'learner' ? '/' : '/');
      },
      onError: (error) => {
        if (error instanceof ApiError) {
          if (error.status === 401 || error.status === 403) {
            setGeneralErrors([error.message]);
            return;
          }
          if (error.status === 422) {
            setFieldErrors(getFieldErrors(error.detail));
            setGeneralErrors(getGeneralErrors(error.detail));
            return;
          }
        }
        setGeneralErrors(['Đã xảy ra lỗi, vui lòng thử lại.']);
      },
    });
  };

  return (
    <AuthLayout title="Đăng nhập" subtitle="Tiếp tục lộ trình đang dở của bạn.">
      <Box component="form" onSubmit={handleSubmit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {generalErrors.map((message) => (
          <Alert severity="error" key={message}>
            {message}
          </Alert>
        ))}

        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          value={form.email}
          onChange={handleChange('email')}
          error={Boolean(fieldErrors.email)}
          helperText={fieldErrors.email}
          required
          fullWidth
        />

        <Box>
          <AuthPasswordField
            label="Mật khẩu"
            autoComplete="current-password"
            value={form.password}
            onChange={handleChange('password')}
            error={Boolean(fieldErrors.password)}
            helperText={fieldErrors.password}
            required
          />
          {/* UC-06 — đặt cạnh ô mật khẩu, đúng chỗ người dùng nhận ra mình quên. */}
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
            <Link component={RouterLink} to="/forgot-password" sx={{ fontSize: 13.5 }}>
              Quên mật khẩu?
            </Link>
          </Box>
        </Box>

        <Button type="submit" variant="contained" size="large" loading={loginMutation.isPending}>
          Đăng nhập
        </Button>
      </Box>

      <AuthAltAction>
        Chưa có tài khoản?{' '}
        <Link component={RouterLink} to="/register">
          Đăng ký
        </Link>
      </AuthAltAction>
    </AuthLayout>
  );
}

export default Login;
