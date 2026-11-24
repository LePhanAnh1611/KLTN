import { useEffect, useState } from 'react';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';

import { useCreateItem, useWordSets } from '../api/wordSets';

/** UC-95 → UC-14 — thêm một từ vừa tra vào bộ từ vựng của mình.
 *
 * Không có nút này thì trang Tra từ là ngõ cụt: tra ra nghĩa rồi ngồi nhìn.
 * Điền sẵn những gì tra được (phiên âm, từ loại, ví dụ) nhưng vẫn cho sửa —
 * nghĩa của cộng đồng không phải lúc nào cũng là nghĩa người học muốn nhớ.
 */

interface Props {
  open: boolean;
  word: string;
  meaning?: string;
  phonetic?: string | null;
  partOfSpeech?: string | null;
  example?: string | null;
  onClose: () => void;
  onAdded: (wordSetName: string) => void;
}

function AddWordDialog({
  open, word, meaning = '', phonetic, partOfSpeech, example, onClose, onAdded,
}: Props) {
  const wordSets = useWordSets();
  const [wordSetId, setWordSetId] = useState<number | ''>('');
  const [form, setForm] = useState({ word, meaning, phonetic: '', pos: '', example: '' });
  const [error, setError] = useState<string | null>(null);

  const create = useCreateItem(typeof wordSetId === 'number' ? wordSetId : 0);

  useEffect(() => {
    if (!open) return;
    setForm({
      word,
      meaning,
      phonetic: phonetic ?? '',
      pos: partOfSpeech ?? '',
      example: example ?? '',
    });
    setError(null);
  }, [open, word, meaning, phonetic, partOfSpeech, example]);

  const mine = wordSets.data ?? [];

  const submit = () => {
    if (typeof wordSetId !== 'number') return;
    setError(null);
    create.mutate(
      {
        word: form.word.trim(),
        meaning: form.meaning.trim(),
        phonetic: form.phonetic.trim() || null,
        part_of_speech: form.pos.trim() || null,
        example: form.example.trim() || null,
      },
      {
        onSuccess: () => {
          onAdded(mine.find((ws) => ws.id === wordSetId)?.name ?? '');
          onClose();
        },
        onError: () => setError('Không thêm được. Từ này có thể đã có trong bộ.'),
      },
    );
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>Thêm “{word}” vào bộ từ vựng</DialogTitle>
      <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
        {error && <Alert severity="error">{error}</Alert>}

        {mine.length === 0 ? (
          <Alert severity="info">
            Bạn chưa có bộ từ vựng nào. Hãy tạo một bộ ở mục “Bộ từ vựng của tôi” trước.
          </Alert>
        ) : (
          <TextField
            select label="Thêm vào bộ" value={wordSetId}
            onChange={(e) => setWordSetId(Number(e.target.value))}
          >
            {mine.map((ws) => (
              <MenuItem key={ws.id} value={ws.id}>
                {ws.name} ({ws.item_count} từ)
              </MenuItem>
            ))}
          </TextField>
        )}

        <TextField
          label="Từ" value={form.word}
          onChange={(e) => setForm({ ...form, word: e.target.value })}
        />
        <TextField
          label="Nghĩa" value={form.meaning} multiline minRows={2}
          onChange={(e) => setForm({ ...form, meaning: e.target.value })}
          helperText="Sửa lại theo cách bạn muốn nhớ - nghĩa của cộng đồng chỉ là gợi ý."
        />
        <TextField
          label="Phiên âm" value={form.phonetic}
          onChange={(e) => setForm({ ...form, phonetic: e.target.value })}
        />
        <TextField
          label="Từ loại" value={form.pos}
          onChange={(e) => setForm({ ...form, pos: e.target.value })}
        />
        <TextField
          label="Câu ví dụ" value={form.example} multiline minRows={2}
          onChange={(e) => setForm({ ...form, example: e.target.value })}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Hủy</Button>
        <Button
          variant="contained" onClick={submit}
          disabled={
            create.isPending || typeof wordSetId !== 'number'
            || form.word.trim() === '' || form.meaning.trim() === ''
          }
        >
          Thêm
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default AddWordDialog;
