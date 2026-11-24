import { useState } from 'react';
import type { ReactNode } from 'react';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import TextField from '@mui/material/TextField';
import type { TextFieldProps } from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';

import {
  FLOAT_SHADOW,
  GRID_BACKGROUND,
  INK,
  PRIMARY_TEXT,
  SURFACE,
  WARM_TEXT,
} from '../theme/theme';
import { EyeIcon, EyeOffIcon } from './icons';
import BrandMark from './BrandMark';
import { Bush, Cloud, Flower, Hills, KidBin, KidNa, SunFlat, TreeRound } from './FlatScene';

interface AuthLayoutProps {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  /**
   * Căn giữa tiêu đề — dùng cho màn chỉ báo một kết quả (xác thực email, đã gửi
   * liên kết, liên kết hỏng), nơi nội dung bên dưới cũng căn giữa. Biểu mẫu thì
   * luôn căn trái để mắt đọc nhãn theo một đường dọc.
   */
  centered?: boolean;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * KHUNG CÁC MÀN NGOÀI APP (đăng nhập, đăng ký, quên/đặt lại mật khẩu, xác thực)
 *
 * Bản flat (2026-10-26), cùng ngôn ngữ với AppLayout: nền be, một thẻ trắng
 * bo lớn. Cột trái là mảng phong cảnh (trời xanh, đồi, cây) với Bin & Na chào
 * người học; cột phải là biểu mẫu.
 * ═══════════════════════════════════════════════════════════════════════════ */

function AuthLayout({ title, subtitle, children, centered = false }: AuthLayoutProps) {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        px: { xs: 2, sm: 3 },
        py: { xs: 3, md: 5 },
        ...GRID_BACKGROUND,
      }}
    >
      <Box sx={{ width: '100%', maxWidth: 980 }}>
        <Box sx={{ borderRadius: '32px', overflow: 'hidden', bgcolor: SURFACE, boxShadow: FLOAT_SHADOW }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1.02fr 1fr' } }}>
            {/* ─── Cột giới thiệu — ẩn dưới md để biểu mẫu chiếm trọn chiều ngang ─── */}
            <Box
              sx={{
                display: { xs: 'none', md: 'flex' },
                flexDirection: 'column',
                p: 4,
                m: 1.25,
                mr: 0,
                borderRadius: '26px',
                bgcolor: '#DDF0F7',
                color: INK,
                position: 'relative',
                overflow: 'hidden',
              }}
            >
              <BrandMark size={36} fontSize={19} />

              <Typography component="p" sx={{ mt: 3, fontWeight: 900, fontSize: 30, lineHeight: 1.25, color: INK, position: 'relative', zIndex: 1 }}>
                Học đúng từ,
                <br />
                <Box component="span" sx={{ color: PRIMARY_TEXT }}>đúng lúc,</Box>{' '}
                <Box component="span" sx={{ color: WARM_TEXT }}>đúng sức.</Box>
              </Typography>
              <Typography sx={{ mt: 1.25, fontSize: 15, fontWeight: 700, lineHeight: 1.6, color: 'text.secondary', maxWidth: 340, position: 'relative', zIndex: 1 }}>
                Hệ thống theo dõi bạn nhớ từng từ tới đâu để chọn từ vừa sức và nhắc ôn đúng lúc.
              </Typography>

              {/* Phong cảnh + nhân vật — chỉ trang trí */}
              <Box aria-hidden sx={{ position: 'relative', mt: 'auto', height: 250, mx: -4, mb: -4 }}>
                <SunFlat size={54} sx={{ position: 'absolute', top: 6, right: 34 }} />
                <Cloud size={96} sx={{ position: 'absolute', top: 20, left: 30 }} />
                <Cloud size={60} sx={{ position: 'absolute', top: 64, right: 110 }} />
                <Hills width={520} sx={{ position: 'absolute', bottom: 0, left: -40 }} />
                <TreeRound size={70} sx={{ position: 'absolute', bottom: 30, left: 26 }} />
                <Bush size={80} sx={{ position: 'absolute', bottom: 4, right: 20 }} />
                <Flower size={20} sx={{ position: 'absolute', bottom: 14, left: '40%' }} />
                <Flower size={16} color="#F6C445" sx={{ position: 'absolute', bottom: 20, left: '62%' }} />
                <KidBin size={104} pose="wave" sx={{ position: 'absolute', bottom: 8, left: '30%' }} />
                <KidNa size={92} pose="book" sx={{ position: 'absolute', bottom: 8, left: '54%' }} />
              </Box>
            </Box>

            {/* ─── Cột biểu mẫu ─── */}
            <Box
              component="main"
              sx={{
                p: { xs: 3, sm: 4.5 },
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
              }}
            >
              <Box
                sx={{
                  display: { xs: 'flex', md: 'none' },
                  justifyContent: centered ? 'center' : 'flex-start',
                  mb: 3,
                }}
              >
                <BrandMark size={32} fontSize={17.5} />
              </Box>

              <Typography
                component="h1"
                sx={{
                  fontWeight: 900,
                  fontSize: { xs: 22, sm: 28 },
                  lineHeight: 1.25,
                  whiteSpace: 'nowrap',
                  textTransform: 'uppercase',
                  letterSpacing: '0.02em',
                  color: INK,
                  textAlign: centered ? 'center' : 'left',
                }}
              >
                {title}
              </Typography>
              {subtitle && (
                <Typography
                  sx={{
                    mt: 1,
                    fontSize: 15,
                    lineHeight: 1.55,
                    color: 'text.secondary',
                    textAlign: centered ? 'center' : 'left',
                  }}
                >
                  {subtitle}
                </Typography>
              )}

              <Box sx={{ mt: 3 }}>{children}</Box>
            </Box>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

/* ─────────────────────── Thành phần dùng chung cho 5 màn ─────────────────── */

/**
 * Ô mật khẩu có nút hiện/ẩn. Gõ sai thì phía sau chỉ trả về "email hoặc mật
 * khẩu không đúng" — không cho xem lại thì người dùng chỉ còn cách mò.
 */
export function AuthPasswordField(props: TextFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <TextField
      {...props}
      type={visible ? 'text' : 'password'}
      fullWidth
      slotProps={{
        ...props.slotProps,
        input: {
          endAdornment: (
            <InputAdornment position="end">
              <IconButton
                onClick={() => setVisible((v) => !v)}
                edge="end"
                size="small"
                aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                sx={{ color: 'text.secondary' }}
              >
                {visible ? <EyeOffIcon size={18} /> : <EyeIcon size={18} />}
              </IconButton>
            </InputAdornment>
          ),
        },
      }}
    />
  );
}

/**
 * Dải cuối biểu mẫu, ngăn bằng một viền mảnh: chỗ cho hành động thay thế
 * ("chưa có tài khoản?", "quay lại đăng nhập"). Thay cho việc xếp chồng vài
 * link căn giữa trông như danh sách bị bỏ quên.
 */
export function AuthAltAction({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        mt: 3,
        pt: 2.25,
        borderTop: '1px solid',
        borderColor: 'divider',
        textAlign: 'center',
        fontSize: 14,
        color: 'text.secondary',
      }}
    >
      {children}
    </Box>
  );
}

/**
 * Trạng thái kết quả chiếm trọn biểu mẫu (gửi mail xong, xác thực xong, liên
 * kết hỏng). Dùng thay `<Alert>` trải ngang: những màn này chỉ có đúng một
 * thông điệp, nên nó là nội dung chính chứ không phải một dải cảnh báo.
 */
export function AuthStatus({
  tone,
  icon,
  title,
  description,
}: {
  tone: 'success' | 'error' | 'info';
  icon: ReactNode;
  title: string;
  description?: ReactNode;
}) {
  const theme = useTheme();
  const palette =
    tone === 'success' ? theme.palette.success
      : tone === 'error' ? theme.palette.error
        : theme.palette.primary;

  return (
    <Box sx={{ textAlign: 'center' }}>
      <Box
        aria-hidden
        sx={{
          width: 56,
          height: 56,
          mx: 'auto',
          borderRadius: '50%',
          display: 'grid',
          placeItems: 'center',
          bgcolor: palette.main,
          color: '#FFFFFF',
        }}
      >
        {icon}
      </Box>
      <Typography
        sx={{
          mt: 2,
          fontWeight: 900,
          fontSize: 19,
          letterSpacing: '-0.015em',
        }}
      >
        {title}
      </Typography>
      {description && (
        <Typography sx={{ mt: 1, fontSize: 14, lineHeight: 1.6, color: 'text.secondary' }}>
          {description}
        </Typography>
      )}
    </Box>
  );
}

export default AuthLayout;
