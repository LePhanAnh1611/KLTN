import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import TextField from '@mui/material/TextField';

import AuthLayout, { AuthAltAction, AuthPasswordField, AuthStatus } from '../components/AuthLayout';
import { ApiError, getFieldErrors, getGeneralErrors } from '../api/client';
import { useRegister } from '../api/auth';
import { MailIcon } from '../components/icons';
import type { RegisterRequest } from '../types/auth';

const EMPTY_FORM: RegisterRequest = {
  email: '',
  password: '',
  password_confirm: '',
  display_name: '',
};

function Register() {
  const [form, setForm] = useState<RegisterRequest>(EMPTY_FORM);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalErrors, setGeneralErrors] = useState<string[]>([]);
  const registerMutation = useRegister();

  const handleChange =
    (field: keyof RegisterRequest) => (event: React.ChangeEvent<HTMLInputElement>) => {
      setForm((prev) => ({ ...prev, [field]: event.target.value }));
    };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFieldErrors({});
    setGeneralErrors([]);

    registerMutation.mutate(form, {
      onError: (error) => {
        if (error instanceof ApiError) {
          if (error.status === 409) {
            setFieldErrors({ email: error.message });
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

  if (registerMutation.isSuccess) {
    return (
      <AuthLayout title="Đã tạo tài khoản" centered>
        <AuthStatus
          tone="success"
          icon={<MailIcon size={26} />}
          title={`Chào ${registerMutation.data.display_name}!`}
          description={
            <>
              Chúng tôi vừa gửi một liên kết xác thực tới{' '}
              <Box component="strong" sx={{ color: 'text.primary', fontWeight: 650 }}>
                {registerMutation.data.email}
              </Box>
              . Mở hộp thư và bấm vào liên kết để kích hoạt đầy đủ tài khoản.
            </>
          }
        />
        <Button component={RouterLink} to="/login" variant="contained" fullWidth size="large" sx={{ mt: 3 }}>
          Tới trang đăng nhập
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Tạo tài khoản" subtitle="Mất chưa tới một phút, và miễn phí.">
      <Box component="form" onSubmit={handleSubmit} noValidate sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {generalErrors.map((message) => (
          <Alert severity="error" key={message}>
            {message}
          </Alert>
        ))}

        <TextField
          label="Tên hiển thị"
          autoComplete="nickname"
          autoFocus
          value={form.display_name}
          onChange={handleChange('display_name')}
          error={Boolean(fieldErrors.display_name)}
          helperText={fieldErrors.display_name}
          required
          fullWidth
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={handleChange('email')}
          error={Boolean(fieldErrors.email)}
          helperText={fieldErrors.email}
          required
          fullWidth
        />
        <AuthPasswordField
          label="Mật khẩu"
          autoComplete="new-password"
          value={form.password}
          onChange={handleChange('password')}
          error={Boolean(fieldErrors.password)}
          helperText={fieldErrors.password || 'Tối thiểu 8 ký tự, có cả chữ và số'}
          required
        />
        <AuthPasswordField
          label="Xác nhận mật khẩu"
          autoComplete="new-password"
          value={form.password_confirm}
          onChange={handleChange('password_confirm')}
          error={Boolean(fieldErrors.password_confirm)}
          helperText={fieldErrors.password_confirm}
          required
        />

        <Button type="submit" variant="contained" size="large" loading={registerMutation.isPending}>
          Đăng ký
        </Button>
      </Box>

      <AuthAltAction>
        Đã có tài khoản?{' '}
        <Link component={RouterLink} to="/login">
          Đăng nhập
        </Link>
      </AuthAltAction>
    </AuthLayout>
  );
}

export default Register;
