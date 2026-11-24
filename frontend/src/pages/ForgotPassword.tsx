import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Link from '@mui/material/Link';
import TextField from '@mui/material/TextField';

import AuthLayout, { AuthAltAction, AuthStatus } from '../components/AuthLayout';
import { useForgotPassword } from '../api/account';
import { ArrowLeftIcon, MailIcon } from '../components/icons';

/** UC-06 bước 1 — nhập email để nhận liên kết đặt lại mật khẩu. */
function ForgotPassword() {
  const [email, setEmail] = useState('');
  const forgot = useForgotPassword();

  if (forgot.isSuccess) {
    return (
      <AuthLayout title="Đã gửi yêu cầu" centered>
        {/* Luôn cùng một câu, dù email có tồn tại hay không (UC-06 1a) */}
        <AuthStatus
          tone="success"
          icon={<MailIcon size={26} />}
          title="Kiểm tra hộp thư của bạn"
          description={forgot.data.message}
        />
        <Button component={RouterLink} to="/login" fullWidth variant="contained" size="large" sx={{ mt: 3 }}>
          Về trang đăng nhập
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title="Quên mật khẩu"
      subtitle="Nhập email, chúng tôi gửi link đặt lại mật khẩu."
    >
      <Box
        component="form"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          forgot.mutate(email);
        }}
        sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}
      >
        {forgot.isError && <Alert severity="error">Gửi yêu cầu thất bại, thử lại sau.</Alert>}

        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          autoFocus
          value={email}
          required
          fullWidth
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button
          type="submit"
          variant="contained"
          size="large"
          loading={forgot.isPending}
          disabled={!email}
        >
          Gửi liên kết đặt lại
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

export default ForgotPassword;
