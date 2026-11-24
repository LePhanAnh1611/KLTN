import { useEffect, useRef } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';

import AuthLayout, { AuthStatus } from '../components/AuthLayout';
import { useVerifyEmail } from '../api/account';
import { AlertIcon, CheckIcon } from '../components/icons';

/** UC-03 bước 3 — người dùng bấm liên kết trong email và rơi vào đây. */
function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get('token');
  const verify = useVerifyEmail();
  const done = useRef(false);

  useEffect(() => {
    if (token && !done.current) {
      done.current = true;         // liên kết dùng một lần: tránh gọi 2 lần
      verify.mutate(token);
    }
  }, [token, verify]);

  return (
    <AuthLayout title="Xác thực email" centered>
      {!token && (
        <AuthStatus
          tone="error"
          icon={<AlertIcon size={26} />}
          title="Liên kết không hợp lệ"
          description="Liên kết thiếu mã xác thực - có thể bạn đã sao chép thiếu một phần."
        />
      )}

      {token && verify.isPending && (
        <Box sx={{ textAlign: 'center', py: 2 }}>
          <CircularProgress size={34} thickness={4} />
          <Typography sx={{ mt: 2, fontSize: 14, color: 'text.secondary' }}>
            Đang kiểm tra liên kết…
          </Typography>
        </Box>
      )}

      {verify.isSuccess && (
        <AuthStatus
          tone="success"
          icon={<CheckIcon size={26} />}
          title={verify.data.already_verified ? 'Email đã xác thực từ trước' : 'Đã xác thực email'}
          description={
            <>
              <Box component="strong" sx={{ color: 'text.primary', fontWeight: 650 }}>
                {verify.data.email}
              </Box>
              {verify.data.already_verified
                ? ' đã được xác thực trước đó. Bạn có thể đăng nhập ngay.'
                : ' đã được xác thực. Tài khoản của bạn đã kích hoạt đầy đủ.'}
            </>
          }
        />
      )}

      {verify.isError && (
        <AuthStatus
          tone="error"
          icon={<AlertIcon size={26} />}
          title="Liên kết không hợp lệ hoặc đã hết hạn"
          description={'Hãy đăng nhập rồi bấm "Gửi lại email xác thực" trong trang Cài đặt.'}
        />
      )}

      <Button
        component={RouterLink}
        to="/login"
        variant="contained"
        size="large"
        fullWidth
        sx={{ mt: 3 }}
      >
        Tới trang đăng nhập
      </Button>
    </AuthLayout>
  );
}

export default VerifyEmail;
