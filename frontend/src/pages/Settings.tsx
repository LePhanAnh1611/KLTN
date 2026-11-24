import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Card from '@mui/material/Card';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Snackbar from '@mui/material/Snackbar';
import Switch from '@mui/material/Switch';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import useMediaQuery from '@mui/material/useMediaQuery';
import { useTheme } from '@mui/material/styles';

import PageHeader from '../components/PageHeader';
import { useDeleteAccount } from '../api/extras';
import { useAuth } from '../context/AuthContext';
import { ApiError, getFieldErrors, getGeneralErrors } from '../api/client';
import {
  useChangePassword,
  useSettings,
  useUpdateGoals,
  useUpdateSettings,
} from '../api/settings';
import {
  useNotificationPreferences,
  useUpdateNotificationPreferences,
} from '../api/notifications';
import { useResendVerification } from '../api/account';
import { useProfile } from '../api/user';

const CEFR_LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

/** UC-09 — giao diện, giờ nhắc, quyền riêng tư. */
/** Múi giờ hay dùng. Danh sách IANA đầy đủ có hơn 500 mục — liệt kê hết chỉ
 *  làm người học phải cuộn, mà 99% dùng đúng dòng đầu tiên. */
const TIMEZONES = [
  { value: 'Asia/Ho_Chi_Minh', label: 'Việt Nam (GMT+7)' },
  { value: 'Asia/Bangkok', label: 'Bangkok (GMT+7)' },
  { value: 'Asia/Singapore', label: 'Singapore (GMT+8)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (GMT+9)' },
  { value: 'Asia/Seoul', label: 'Seoul (GMT+9)' },
  { value: 'Australia/Sydney', label: 'Sydney (GMT+10/11)' },
  { value: 'Europe/London', label: 'London (GMT+0/1)' },
  { value: 'Europe/Paris', label: 'Paris (GMT+1/2)' },
  { value: 'America/New_York', label: 'New York (GMT-5/-4)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (GMT-8/-7)' },
  { value: 'UTC', label: 'UTC' },
];

function AppearanceSection({ onResult }: { onResult: (msg: string) => void }) {
  const { data } = useSettings();
  const update = useUpdateSettings();
  if (!data) return null;

  const onError = (e: unknown) =>
    onResult(e instanceof ApiError ? e.message : 'Lưu thất bại, giữ nguyên giá trị cũ.');

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>Giao diện & quyền riêng tư</Typography>


      <Box sx={{ display: 'flex', gap: 2, mt: 2, flexWrap: 'wrap' }}>
        <Tooltip title="Giao diện hiện chỉ có tiếng Việt - bản đa ngữ chưa bật">
          <TextField
            select size="small" label="Ngôn ngữ giao diện" value={data.ui_language}
            disabled sx={{ minWidth: 190 }}
            helperText="Chưa có hiệu lực"
          >
            <MenuItem value="vi">Tiếng Việt</MenuItem>
            <MenuItem value="en">English</MenuItem>
          </TextField>
        </Tooltip>

        <TextField
          size="small" type="time" label="Giờ nhắc ôn tập" sx={{ minWidth: 190 }}
          value={data.reminder_time ? data.reminder_time.slice(0, 5) : ''}
          slotProps={{ inputLabel: { shrink: true } }}
          helperText="Nhắc ôn theo đúng giờ này, tính theo múi giờ bên cạnh"
          onChange={(e) =>
            update.mutate(
              { reminder_time: e.target.value ? `${e.target.value}:00` : null },
              { onSuccess: () => onResult('Đã lưu giờ nhắc.'), onError },
            )
          }
        />

        <TextField
          select size="small" label="Múi giờ" sx={{ minWidth: 220 }}
          value={data.timezone}
          helperText="Quyết định mốc sang ngày mới của streak & mục tiêu"
          onChange={(e) =>
            update.mutate({ timezone: e.target.value }, {
              onSuccess: () => onResult('Đã lưu múi giờ.'), onError,
            })
          }
        >
          {TIMEZONES.map((tz) => (
            <MenuItem key={tz.value} value={tz.value}>{tz.label}</MenuItem>
          ))}
        </TextField>

        <TextField
          select size="small" label="Hồ sơ công khai" sx={{ minWidth: 190 }}
          value={data.profile_visibility}
          helperText="Riêng tư thì người khác không thấy chỉ số"
          onChange={(e) =>
            update.mutate(
              { profile_visibility: e.target.value as 'public' | 'private' },
              { onSuccess: () => onResult('Đã lưu quyền riêng tư.'), onError },
            )
          }
        >
          <MenuItem value="public">Công khai</MenuItem>
          <MenuItem value="private">Riêng tư</MenuItem>
        </TextField>
      </Box>
    </Paper>
  );
}

/** UC-10 — mục tiêu học. */
function GoalsSection({ onResult }: { onResult: (msg: string) => void }) {
  const { data } = useSettings();
  const update = useUpdateGoals();
  const [draft, setDraft] =
    useState<{ items: string; xp: string; cefr: string; entry: string } | null>(null);

  useEffect(() => {
    if (data && draft === null) {
      setDraft({
        items: data.daily_item_goal ? String(data.daily_item_goal) : '',
        xp: data.daily_xp_goal ? String(data.daily_xp_goal) : '',
        cefr: data.target_cefr_level ?? '',
        entry: data.entry_cefr_level ?? '',
      });
    }
  }, [data, draft]);

  if (!data || !draft) return null;

  const save = () =>
    update.mutate(
      {
        daily_item_goal: draft.items ? Number(draft.items) : null,
        daily_xp_goal: draft.xp ? Number(draft.xp) : null,
        target_cefr_level: (draft.cefr || null) as never,
        entry_cefr_level: (draft.entry || null) as never,
      },
      {
        onSuccess: () => onResult('Đã lưu mục tiêu học.'),
        onError: (e) => onResult(
          e instanceof ApiError && e.status === 422
            ? 'Giá trị ngoài khoảng cho phép (từ/ngày 1-200, XP/ngày 10-1000).'
            : 'Lưu mục tiêu thất bại.',
        ),
      },
    );

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>Mục tiêu học</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Ngôn ngữ học: Tiếng Anh. Bỏ trống số từ/ngày thì hệ thống dùng mặc định 10 từ.
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'flex-start' }}>
        <TextField
          size="small" type="number" label="Số từ / ngày" sx={{ width: 160 }}
          value={draft.items} onChange={(e) => setDraft({ ...draft, items: e.target.value })}
          slotProps={{ htmlInput: { min: 1, max: 200 } }} helperText="1-200"
        />
        <TextField
          size="small" type="number" label="XP mục tiêu / ngày" sx={{ width: 180 }}
          value={draft.xp} onChange={(e) => setDraft({ ...draft, xp: e.target.value })}
          slotProps={{ htmlInput: { min: 10, max: 1000 } }} helperText="10-1000"
        />
        <TextField
          select size="small" label="Mục tiêu CEFR" sx={{ width: 160 }}
          value={draft.cefr} onChange={(e) => setDraft({ ...draft, cefr: e.target.value })}
          helperText="Trình độ hướng tới"
        >
          <MenuItem value="">Chưa đặt</MenuItem>
          {CEFR_LEVELS.map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
        </TextField>
        {/* Mức do bài kiểm tra đầu vào ước lượng, nhưng người học tự chỉnh được:
            thấy quá dễ/quá khó thì đổi ngay, khỏi làm lại cả bài test (UC-11). */}
        <TextField
          select size="small" label="Trình độ đầu vào" sx={{ width: 180 }}
          value={draft.entry} onChange={(e) => setDraft({ ...draft, entry: e.target.value })}
          helperText="Điểm xuất phát của lộ trình"
        >
          <MenuItem value="">Chưa xác định</MenuItem>
          {CEFR_LEVELS.map((lv) => <MenuItem key={lv} value={lv}>{lv}</MenuItem>)}
        </TextField>
        <Button variant="contained" disabled={update.isPending} onClick={save} sx={{ mt: 0.5 }}>
          Lưu mục tiêu
        </Button>
      </Box>
    </Paper>
  );
}

/** UC-60 — bật/tắt từng loại thông báo (trước ở trang Hồ sơ, gom về đây). */
function NotificationSection() {
  const { data } = useNotificationPreferences();
  const update = useUpdateNotificationPreferences();
  if (!data) return null;

  const rows: { key: keyof typeof data; label: string }[] = [
    { key: 'notify_review', label: 'Nhắc ôn tập & streak' },
    { key: 'notify_achievement', label: 'Huy hiệu mở khóa' },
    { key: 'notify_community', label: 'Tương tác cộng đồng' },
  ];

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>Thông báo</Typography>
      {rows.map((r) => (
        <FormControlLabel
          key={r.key}
          sx={{ display: 'flex' }}
          control={
            <Switch
              checked={data[r.key]} disabled={update.isPending}
              onChange={() => update.mutate({ ...data, [r.key]: !data[r.key] })}
            />
          }
          label={r.label}
        />
      ))}
    </Paper>
  );
}

/** UC-03 luồng 1a — nhắc & gửi lại email xác thực khi tài khoản chưa xác thực. */
function EmailVerificationSection({ onResult }: { onResult: (msg: string) => void }) {
  const { data: profile } = useProfile();
  const resend = useResendVerification();
  if (!profile || profile.is_email_verified) return null;

  return (
    <Alert
      severity="warning"
      sx={{ mb: 3 }}
      action={
        <Button
          size="small" disabled={resend.isPending}
          onClick={() => resend.mutate(undefined, {
            onSuccess: (res) => onResult(res.message),
            onError: (e) => onResult(
              e instanceof ApiError && e.status === 429
                ? 'Bạn đã yêu cầu gửi lại quá nhiều lần, thử lại sau.'
                : 'Không gửi lại được email.',
            ),
          })}
        >
          Gửi lại
        </Button>
      }
    >
      Email <strong>{profile.email}</strong> chưa được xác thực.
    </Alert>
  );
}

/** UC-07 — đổi mật khẩu. */
function PasswordSection({ onResult }: { onResult: (msg: string) => void }) {
  const change = useChangePassword();
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldErrors({});
    change.mutate(
      {
        current_password: form.current,
        new_password: form.next,
        new_password_confirm: form.confirm,
      },
      {
        onSuccess: () => {
          setForm({ current: '', next: '', confirm: '' });
          onResult('Đã đổi mật khẩu.');
        },
        onError: (err) => {
          if (err instanceof ApiError) {
            setFieldErrors(getFieldErrors(err.detail));
            const general = getGeneralErrors(err.detail);
            setError(general[0] ?? err.message);
          } else {
            setError('Đổi mật khẩu thất bại.');
          }
        },
      },
    );
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>Đổi mật khẩu</Typography>
      <Box component="form" onSubmit={submit} noValidate
           sx={{ display: 'flex', flexDirection: 'column', gap: 2, maxWidth: 380 }}>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          type="password" label="Mật khẩu hiện tại" value={form.current} required
          onChange={(e) => setForm({ ...form, current: e.target.value })}
          error={Boolean(fieldErrors.current_password)}
          helperText={fieldErrors.current_password}
        />
        <Divider />
        <TextField
          type="password" label="Mật khẩu mới" value={form.next} required
          onChange={(e) => setForm({ ...form, next: e.target.value })}
          error={Boolean(fieldErrors.new_password)}
          helperText={fieldErrors.new_password || 'Tối thiểu 8 ký tự, có cả chữ và số'}
        />
        <TextField
          type="password" label="Xác nhận mật khẩu mới" value={form.confirm} required
          onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          error={Boolean(fieldErrors.new_password_confirm)}
          helperText={fieldErrors.new_password_confirm}
        />
        <Button type="submit" variant="contained" loading={change.isPending}>
          Đổi mật khẩu
        </Button>
      </Box>
    </Paper>
  );
}

/** UC-12 — xóa tài khoản.
 *
 * Đặt cuối trang và bắt nhập mật khẩu: thao tác không hoàn tác được, không nên
 * chỉ cách một cú bấm. Nói rõ cái gì bị xóa và cái gì được giữ lại. */
function DangerZone({ onResult }: { onResult: (msg: string) => void }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const remove = useDeleteAccount();

  return (
    <Paper sx={{ p: 3, mb: 3, borderColor: 'error.main' }} variant="outlined">
      <Typography variant="h6" gutterBottom color="error">Xóa tài khoản</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Tài khoản sẽ bị vô hiệu hóa ngay, email và tên hiển thị được xóa khỏi hệ thống,
        bộ từ vựng riêng và bài viết của bạn bị gỡ. Lịch sử trả lời được giữ lại ở dạng ẩn danh
        để không phá vỡ dữ liệu thống kê. <strong>Thao tác này không hoàn tác được.</strong>
      </Typography>

      {!open ? (
        <Button color="error" variant="outlined" onClick={() => setOpen(true)}>
          Tôi muốn xóa tài khoản
        </Button>
      ) : (
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', alignItems: 'center' }}>
          <TextField
            size="small" type="password" label="Nhập mật khẩu để xác nhận"
            sx={{ minWidth: 260 }}
            value={password} onChange={(e) => setPassword(e.target.value)}
          />
          <Button
            color="error" variant="contained"
            disabled={!password || remove.isPending}
            onClick={() => remove.mutate(password, {
              onSuccess: () => { auth.logout(); navigate('/login', { replace: true }); },
              onError: (e) => onResult(
                e instanceof ApiError ? e.message : 'Xóa tài khoản thất bại.',
              ),
            })}
          >
            Xóa vĩnh viễn
          </Button>
          <Button onClick={() => { setOpen(false); setPassword(''); }}>Hủy</Button>
        </Box>
      )}
    </Paper>
  );
}

/** UC-07 + UC-09 + UC-10 — trang Cài đặt. */
const SECTIONS = [
  { id: 'appearance', label: 'Giao diện & riêng tư' },
  { id: 'goals', label: 'Mục tiêu học' },
  { id: 'notifications', label: 'Thông báo' },
  { id: 'password', label: 'Đổi mật khẩu' },
  { id: 'danger', label: 'Xóa tài khoản' },
] as const;

function Settings() {
  const { isLoading, isError } = useSettings();
  const [snack, setSnack] = useState<string | null>(null);
  const [section, setSection] = useState<(typeof SECTIONS)[number]['id']>('appearance');
  const wide = useMediaQuery(useTheme().breakpoints.up('md'));

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (isError) return <Alert severity="error">Không tải được cài đặt.</Alert>;

  // Ẩn bằng CSS chứ không gỡ khỏi cây: đang gõ dở ở mục này, sang mục khác rồi
  // quay lại vẫn còn nguyên.
  const shown = (id: typeof section) => ({ display: section === id ? 'block' : 'none' });

  return (
    <Box sx={{ maxWidth: 1120, mx: 'auto' }}>
      <PageHeader
        title="Cài đặt"
        subtitle="Mục tiêu, nhắc ôn và mật khẩu."
      />

      <EmailVerificationSection onResult={setSnack} />

      {/* Menu mục bên trái, nội dung một mục bên phải: không phải cuộn qua cả
          5 khối để tìm một ô (2026-11-04). */}
      <Box sx={{
        display: 'grid', gap: 2.5, alignItems: 'start',
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '250px minmax(0, 1fr)' },
      }}>
        <Card sx={{ p: 1 }}>
          <Tabs
            orientation={wide ? 'vertical' : 'horizontal'} variant="scrollable" scrollButtons={false}
            value={section} onChange={(_, v) => setSection(v)}
            aria-label="Các mục cài đặt"
            sx={{ '& .MuiTab-root': { alignItems: { md: 'flex-start' }, textAlign: 'left' } }}
          >
            {SECTIONS.map((s) => (
              <Tab key={s.id} value={s.id} label={s.label}
                   sx={s.id === 'danger' ? { color: 'error.main' } : undefined} />
            ))}
          </Tabs>
        </Card>

        <Box sx={{ minWidth: 0, '& > div > .MuiPaper-root': { mb: 0 } }}>
          <Box sx={shown('appearance')}><AppearanceSection onResult={setSnack} /></Box>
          <Box sx={shown('goals')}><GoalsSection onResult={setSnack} /></Box>
          <Box sx={shown('notifications')}><NotificationSection /></Box>
          <Box sx={shown('password')}><PasswordSection onResult={setSnack} /></Box>
          <Box sx={shown('danger')}><DangerZone onResult={setSnack} /></Box>
        </Box>
      </Box>

      <Snackbar open={snack !== null} autoHideDuration={3000}
                onClose={() => setSnack(null)} message={snack ?? ''} />
    </Box>
  );
}

export default Settings;
