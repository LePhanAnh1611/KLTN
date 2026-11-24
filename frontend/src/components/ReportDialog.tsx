import { useState } from 'react';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';

import { REPORT_REASONS, type ReportReason } from '../api/discover';

interface ReportDialogProps {
  title: string;
  open: boolean;
  pending?: boolean;
  onClose: () => void;
  onSubmit: (body: { reason: ReportReason; description: string | null }) => void;
}

/** Hộp thoại báo cáo vi phạm dùng chung: bộ từ (UC-24) và bài viết (UC-53). */
function ReportDialog({ title, open, pending, onClose, onSubmit }: ReportDialogProps) {
  const [reason, setReason] = useState<ReportReason>('wrong_content');
  const [description, setDescription] = useState('');

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <TextField
          select fullWidth size="small" label="Lý do" value={reason} sx={{ mt: 1 }}
          onChange={(e) => setReason(e.target.value as ReportReason)}
        >
          {REPORT_REASONS.map((r) => (
            <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>
          ))}
        </TextField>
        <TextField
          fullWidth multiline minRows={3} size="small" label="Mô tả (tùy chọn)" sx={{ mt: 2 }}
          value={description} onChange={(e) => setDescription(e.target.value)}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Hủy</Button>
        <Button
          variant="contained" color="error" disabled={pending}
          onClick={() => onSubmit({ reason, description: description || null })}
        >
          Gửi báo cáo
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default ReportDialog;
