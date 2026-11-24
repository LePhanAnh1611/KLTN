import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import TextField from '@mui/material/TextField';

import { ApiError, getFieldErrors } from '../api/client';
import type { Item, ItemInput } from '../types/wordSet';

interface Props {
  open: boolean;
  initial?: Item;
  pending: boolean;
  onClose: () => void;
  onSubmit: (data: ItemInput, onError: (error: unknown) => void) => void;
}

function ItemFormDialog({ open, initial, pending, onClose, onSubmit }: Props) {
  const [word, setWord] = useState('');
  const [phonetic, setPhonetic] = useState('');
  const [partOfSpeech, setPartOfSpeech] = useState('');
  const [meaning, setMeaning] = useState('');
  const [example, setExample] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generalError, setGeneralError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setWord(initial?.word ?? '');
      setPhonetic(initial?.phonetic ?? '');
      setPartOfSpeech(initial?.part_of_speech ?? '');
      setMeaning(initial?.meaning ?? '');
      setExample(initial?.example ?? '');
      setFieldErrors({});
      setGeneralError(null);
    }
  }, [open, initial]);

  const handleSubmit = () => {
    setFieldErrors({});
    setGeneralError(null);
    onSubmit(
      {
        word,
        phonetic: phonetic.trim() === '' ? null : phonetic,
        part_of_speech: partOfSpeech.trim() === '' ? null : partOfSpeech,
        meaning,
        example: example.trim() === '' ? null : example,
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
      <DialogTitle>{initial ? 'Sửa từ' : 'Thêm từ mới'}</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
        {generalError && <Alert severity="error">{generalError}</Alert>}
        <TextField
          label="Từ"
          value={word}
          onChange={(e) => setWord(e.target.value)}
          error={Boolean(fieldErrors.word)}
          helperText={fieldErrors.word}
          required
          fullWidth
          autoFocus
        />
        <TextField label="Phiên âm" value={phonetic} onChange={(e) => setPhonetic(e.target.value)} fullWidth />
        <TextField
          label="Từ loại"
          value={partOfSpeech}
          onChange={(e) => setPartOfSpeech(e.target.value)}
          fullWidth
        />
        <TextField
          label="Nghĩa"
          value={meaning}
          onChange={(e) => setMeaning(e.target.value)}
          error={Boolean(fieldErrors.meaning)}
          helperText={fieldErrors.meaning}
          required
          fullWidth
        />
        <TextField
          label="Ví dụ"
          value={example}
          onChange={(e) => setExample(e.target.value)}
          multiline
          minRows={2}
          fullWidth
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

export default ItemFormDialog;
