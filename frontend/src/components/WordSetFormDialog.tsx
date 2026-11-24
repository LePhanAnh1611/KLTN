import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';

import { ApiError, getFieldErrors } from '../api/client';
import type { WordSet, WordSetInput } from '../types/wordSet';

const DIFFICULTIES = ['beginner', 'intermediate', 'advanced'];

interface Props {
  open: boolean;
  initial?: WordSet;
  pending: boolean;
  onClose: () => void;
  onSubmit: (data: WordSetInput, onError: (error: unknown) => void) => void;
}

function WordSetFormDialog({ open, initial, pending, onClose, onSubmit }: Props) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [tags, setTags] = useState('');   // UC-96 — nhập tự do, ngăn cách bằng dấu phẩy
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setName(initial?.name ?? '');
      setDescription(initial?.description ?? '');
      setCategory(initial?.category ?? '');
      setDifficulty(initial?.difficulty ?? '');
      setTags((initial?.tags ?? []).join(', '));
      setFieldErrors({});
      setGeneralError(null);
    }
  }, [open, initial]);

  const handleSubmit = () => {
    setFieldErrors({});
    setGeneralError(null);
    onSubmit(
      {
        name,
        description: description.trim() === '' ? null : description,
        category: category.trim() === '' ? null : category,
        difficulty: difficulty === '' ? null : difficulty,
        // Server chuẩn hóa (bỏ dấu, gạch nối, cắt trần) — client chỉ tách chuỗi,
        // không tự sửa chữ của người dùng để tránh hai bên chuẩn hóa lệch nhau.
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
      },
      (error) => {
        if (error instanceof ApiError && error.status === 422) {
          setFieldErrors(getFieldErrors(error.detail));
        } else {
          setGeneralError('Không lưu được, vui lòng thử lại.');
        }
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{initial ? 'Sửa bộ từ vựng' : 'Tạo bộ từ vựng mới'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
        {generalError && <Alert severity="error">{generalError}</Alert>}
        <TextField
          label="Tên bộ từ vựng"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={Boolean(fieldErrors.name)}
          helperText={fieldErrors.name}
          required
          fullWidth
          autoFocus
        />
        <TextField
          label="Mô tả"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          multiline
          minRows={2}
          fullWidth
        />
        <TextField
          label="Danh mục"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          fullWidth
        />
        <TextField
          label="Độ khó"
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
          select
          fullWidth
        >
          <MenuItem value="">(Chưa chọn)</MenuItem>
          {DIFFICULTIES.map((d) => (
            <MenuItem key={d} value={d}>
              {d}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="Nhãn"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
          placeholder="ielts, oxford, b1"
          helperText="Ngăn cách bằng dấu phẩy, tối đa 8 nhãn. Dùng để lọc ở trang Khám phá."
          error={Boolean(fieldErrors.tags)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Hủy</Button>
        <Button onClick={handleSubmit} variant="contained" loading={pending}>
          Lưu
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default WordSetFormDialog;
