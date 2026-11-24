import { useEffect, useState } from 'react';
import type { ChangeEvent, FormEvent, ReactNode } from 'react';
import Alert from '@mui/material/Alert';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import TextField from '@mui/material/TextField';

import PageHeader from '../components/PageHeader';
import { API_BASE_URL, ApiError, getFieldErrors, getGeneralErrors } from '../api/client';
import { useProfile, useUpdateProfile, useUploadAvatar } from '../api/user';

const MAX_AVATAR_SIZE_BYTES = 2 * 1024 * 1024;
const ALLOWED_AVATAR_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function Profile() {
  const profileQuery = useProfile();
  const updateMutation = useUpdateProfile();
  const uploadMutation = useUploadAvatar();

  const [displayName, setDisplayName] = useState('');
  const [bio, setBio] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalErrors, setGeneralErrors] = useState<string[]>([]);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    if (profileQuery.data) {
      setDisplayName(profileQuery.data.display_name);
      setBio(profileQuery.data.bio ?? '');
    }
  }, [profileQuery.data]);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFieldErrors({});
    setGeneralErrors([]);
    setSuccessMessage(null);

    updateMutation.mutate(
      { display_name: displayName, bio: bio.trim() === '' ? null : bio },
      {
        onSuccess: () => setSuccessMessage('Đã lưu hồ sơ.'),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 422) {
            setFieldErrors(getFieldErrors(error.detail));
            setGeneralErrors(getGeneralErrors(error.detail));
            return;
          }
          setGeneralErrors(['Đã xảy ra lỗi, vui lòng thử lại.']);
        },
      },
    );
  };

  const handleAvatarChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setAvatarError(null);

    if (!ALLOWED_AVATAR_TYPES.includes(file.type)) {
      setAvatarError('Định dạng ảnh không hỗ trợ (chỉ nhận jpg/png/webp)');
      return;
    }
    if (file.size > MAX_AVATAR_SIZE_BYTES) {
      setAvatarError('Ảnh vượt quá dung lượng cho phép (tối đa 2MB)');
      return;
    }

    uploadMutation.mutate(file, {
      onError: (error) => {
        setAvatarError(error instanceof ApiError ? error.message : 'Tải ảnh thất bại, vui lòng thử lại.');
      },
    });
  };

  // AppLayout đã cung cấp khung (sidebar + topbar); trang chỉ trả nội dung.
  const withSidebar = (inner: ReactNode) => inner;

  if (profileQuery.isLoading) {
    return withSidebar(
      <Box sx={{ maxWidth: 480, mx: 'auto', textAlign: 'center' }}>
        <CircularProgress />
      </Box>,
    );
  }

  if (profileQuery.isError || !profileQuery.data) {
    return withSidebar(
      <Box sx={{ maxWidth: 480, mx: 'auto' }}>
        <Alert severity="error">Không tải được hồ sơ. Vui lòng thử lại.</Alert>
      </Box>,
    );
  }

  const avatarSrc = profileQuery.data.avatar_url
    ? `${API_BASE_URL}${profileQuery.data.avatar_url}`
    : undefined;

  return withSidebar(
    <Box sx={{ maxWidth: 900, mx: 'auto' }}>
      <PageHeader
        title="Hồ sơ cá nhân"
        subtitle="Tên và ảnh người khác nhìn thấy."
      />

      {/* Trái: ảnh đại diện. Phải: thông tin (2026-11-04). */}
      <Box sx={{
        display: 'grid', gap: 2.5, alignItems: 'start',
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '280px minmax(0, 1fr)' },
      }}>
      <Card sx={{ p: 3, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
        <Avatar src={avatarSrc} sx={{ width: 120, height: 120 }}>
          {profileQuery.data.display_name.charAt(0).toUpperCase()}
        </Avatar>
        <Button component="label" size="small" disabled={uploadMutation.isPending}>
          {uploadMutation.isPending ? 'Đang tải lên...' : 'Đổi ảnh đại diện'}
          <input type="file" hidden accept="image/jpeg,image/png,image/webp" onChange={handleAvatarChange} />
        </Button>
        {avatarError && (
          <Alert severity="error" sx={{ width: '100%' }}>
            {avatarError}
          </Alert>
        )}
      </Card>

      <Card
        component="form"
        onSubmit={handleSubmit}
        noValidate
        sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 2 }}
      >
        {successMessage && <Alert severity="success">{successMessage}</Alert>}
        {generalErrors.map((message) => (
          <Alert severity="error" key={message}>
            {message}
          </Alert>
        ))}

        <TextField
          label="Tên hiển thị"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          error={Boolean(fieldErrors.display_name)}
          helperText={fieldErrors.display_name}
          required
          fullWidth
        />
        <TextField
          label="Giới thiệu"
          value={bio}
          onChange={(event) => setBio(event.target.value)}
          error={Boolean(fieldErrors.bio)}
          helperText={fieldErrors.bio}
          multiline
          minRows={3}
          fullWidth
        />

        <Button type="submit" variant="contained" size="large" loading={updateMutation.isPending}>
          Lưu
        </Button>
      </Card>
      </Box>

    </Box>,
  );
}

export default Profile;
