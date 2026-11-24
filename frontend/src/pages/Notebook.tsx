import { useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Snackbar from '@mui/material/Snackbar';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import {
  useCreateNote,
  useDeleteNote,
  useFlaggedItems,
  useNotes,
  useSubmitWriting,
  useWritingPrompts,
  useWritingSubmissions,
  type WritingResult,
} from '../api/extras';
import { useClearItemFlag } from '../api/extras';
import { useWordSets } from '../api/wordSets';
import { ApiError } from '../api/client';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import SectionCard from '../components/SectionCard';
import { BookIcon, CloseIcon, SearchIcon, StarIcon } from '../components/icons';

/** UC-37 — luyện dịch Việt→Anh trên chính vốn từ đang học. */
function WritingTab({ onResult }: { onResult: (msg: string) => void }) {
  const { data: wordSets } = useWordSets();
  const [wordSetId, setWordSetId] = useState<number | ''>('');
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<WritingResult | null>(null);

  const prompts = useWritingPrompts(wordSetId === '' ? null : wordSetId);
  const submit = useSubmitWriting();
  const createNote = useCreateNote();

  const current = prompts.data?.[index];

  const doSubmit = () => {
    if (!current) return;
    submit.mutate(
      { prompt_vi: current.prompt_vi, answer_en: answer.trim() },
      {
        onSuccess: setResult,
        onError: (e) => onResult(e instanceof ApiError ? e.message : 'Nộp bài thất bại.'),
      },
    );
  };

  const next = () => {
    setResult(null);
    setAnswer('');
    setIndex((i) => i + 1);
  };

  return (
    <Box>
      <TextField
        select size="small" label="Chọn bộ từ vựng" sx={{ minWidth: { xs: 0, sm: 260 }, width: { xs: '100%', sm: 'auto' }, mb: 3 }}
        value={wordSetId}
        onChange={(e) => {
          setWordSetId(Number(e.target.value));
          setIndex(0); setAnswer(''); setResult(null);
        }}
      >
        {(wordSets ?? []).map((ws) => (
          <MenuItem key={ws.id} value={ws.id} disabled={ws.item_count === 0}>
            {ws.name} ({ws.item_count} từ)
          </MenuItem>
        ))}
      </TextField>

      {prompts.isLoading && <LinearProgress />}
      {prompts.isError && (
        <Alert severity="info">
          Bộ từ vựng này chưa có câu ví dụ nào nên chưa tạo được đề luyện viết.
          Thêm ví dụ cho các từ rồi quay lại.
        </Alert>
      )}

      {current && (
        <SectionCard title={`Đề ${index + 1}/${prompts.data?.length ?? 0}`}>
          {/* Trái: đề và bài làm. Phải: nhận xét (2026-11-04). */}
          <Box sx={{ display: 'grid', gap: 3, gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' } }}>
            <Box sx={{ minWidth: 0 }}>
          <Typography variant="h6" sx={{ mb: 2 }}>{current.prompt_vi}</Typography>

          <TextField
            fullWidth multiline minRows={3} label="Câu tiếng Anh của bạn"
            value={answer} onChange={(e) => setAnswer(e.target.value)}
            disabled={result !== null}
          />

          <Box sx={{ display: 'flex', gap: 1.5, mt: 2.5, flexWrap: 'wrap' }}>
            {!result ? (
              <Button variant="contained" disabled={!answer.trim() || submit.isPending}
                      onClick={doSubmit}>
                Nộp bài
              </Button>
            ) : (
              <>
                <Button
                  variant="contained"
                  disabled={index + 1 >= (prompts.data?.length ?? 0)}
                  onClick={next}
                >
                  Đề tiếp theo
                </Button>
                <Button
                  onClick={() => createNote.mutate(
                    {
                      text_en: result.suggestion || result.answer_en,
                      note: result.feedback, submission_id: result.id,
                    },
                    { onSuccess: () => onResult('Đã lưu vào sổ tay.') },
                  )}
                >
                  Lưu vào sổ tay
                </Button>
              </>
            )}
          </Box>
            </Box>

            <Box sx={{ minWidth: 0 }}>
              {result ? (
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Chip
                      color={(result.score ?? 0) >= 70 ? 'success' : 'warning'}
                      label={`${Math.round(result.score ?? 0)}/100`}
                    />
                    {/* Nói thật ai chấm — không trình bày heuristic như thể là AI */}
                    <Tooltip title={result.grader === 'llm'
                      ? 'Nhận xét do mô hình ngôn ngữ sinh ra'
                      : 'Chưa cấu hình mô hình ngôn ngữ - đây là bộ kiểm tra máy móc (độ dài, dùng đúng từ, dấu câu)'}>
                      <Chip size="small" variant="outlined"
                            label={result.grader === 'llm' ? 'AI chấm' : 'Kiểm tra tự động'} />
                    </Tooltip>
                  </Box>

                  <Alert severity={(result.score ?? 0) >= 70 ? 'success' : 'warning'}>
                    {result.feedback}
                  </Alert>

                  {result.suggestion && (
                    <Alert severity="info" sx={{ mt: 1 }}>
                      Gợi ý: <strong>{result.suggestion}</strong>
                    </Alert>
                  )}
                  {current.reference_en && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                      Câu ví dụ gốc: <em>{current.reference_en}</em>
                    </Typography>
                  )}
                </Box>
              ) : (
                <Typography variant="body2" color="text.secondary"
                            sx={{ p: 2.5, borderRadius: '16px', bgcolor: '#F4F8FD', textAlign: 'center' }}>
                  Nộp bài xong, nhận xét sẽ hiện ở đây.
                </Typography>
              )}
            </Box>
          </Box>
        </SectionCard>
      )}
    </Box>
  );
}

/** UC-38 — sổ tay câu. */
function NotesTab({ onResult }: { onResult: (msg: string) => void }) {
  const [q, setQ] = useState('');
  const [draft, setDraft] = useState({ text_en: '', text_vi: '', note: '' });

  const { data, isLoading } = useNotes(q);
  const create = useCreateNote();
  const remove = useDeleteNote();

  return (
    <Box sx={{
      display: 'grid', gap: 2.5, alignItems: 'start',
      gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: '340px minmax(0, 1fr)' },
    }}>
      <SectionCard title="Thêm câu mới" sx={{ position: { md: 'sticky' }, top: { md: 16 } }}>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
          <TextField size="small" label="Câu tiếng Anh" sx={{ flex: '1 1 260px' }}
                     value={draft.text_en}
                     onChange={(e) => setDraft({ ...draft, text_en: e.target.value })} />
          <TextField size="small" label="Nghĩa tiếng Việt" sx={{ flex: '1 1 220px' }}
                     value={draft.text_vi}
                     onChange={(e) => setDraft({ ...draft, text_vi: e.target.value })} />
          <TextField size="small" label="Ghi chú" sx={{ flex: '1 1 180px' }}
                     value={draft.note}
                     onChange={(e) => setDraft({ ...draft, note: e.target.value })} />
          <Button
            variant="contained" disabled={!draft.text_en.trim() || create.isPending}
            onClick={() => create.mutate(
              {
                text_en: draft.text_en.trim(),
                text_vi: draft.text_vi.trim() || null,
                note: draft.note.trim() || null,
              },
              {
                onSuccess: () => {
                  setDraft({ text_en: '', text_vi: '', note: '' });
                  onResult('Đã lưu câu.');
                },
              },
            )}
          >
            Lưu
          </Button>
        </Box>
      </SectionCard>

      <Box sx={{ minWidth: 0 }}>
      <TextField
        size="small" placeholder="Tìm trong sổ tay..." sx={{ mb: 2, minWidth: { xs: 0, sm: 260 }, width: { xs: '100%', sm: 'auto' } }}
        value={q} onChange={(e) => setQ(e.target.value)}
        slotProps={{ input: { startAdornment: (
          <InputAdornment position="start"><SearchIcon size={18} /></InputAdornment>
        ) } }}
      />

      {isLoading && <LinearProgress />}
      {data && data.length === 0 && (
        <EmptyState
          icon={<BookIcon size={24} />}
          title={q ? 'Không tìm thấy câu nào' : 'Sổ tay còn trống'}
          description="Lưu câu hay để ôn lại sau."
        />
      )}

      {data?.map((note) => (
        <SectionCard key={note.id} sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <Typography variant="body1" sx={{ fontWeight: 600 }}>{note.text_en}</Typography>
              {note.text_vi && (
                <Typography variant="body2" color="text.secondary">{note.text_vi}</Typography>
              )}
              {note.note && (
                <Typography variant="caption" color="text.secondary"
                            sx={{ display: 'block', mt: 0.5, fontStyle: 'italic' }}>
                  {note.note}
                </Typography>
              )}
            </Box>
            <Button size="small" color="error"
                    onClick={() => remove.mutate(note.id, {
                      onSuccess: () => onResult('Đã xóa khỏi sổ tay.'),
                    })}>
              Xóa
            </Button>
          </Box>
        </SectionCard>
      ))}
      </Box>
    </Box>
  );
}

/** UC-32 — các từ tự đánh dấu là khó. */
function FlaggedTab({ onResult }: { onResult: (msg: string) => void }) {
  const { data, isLoading } = useFlaggedItems();
  const clear = useClearItemFlag();

  if (isLoading) return <LinearProgress />;
  if (!data || data.length === 0) {
    return (
      <EmptyState
        icon={<StarIcon size={24} />}
        title="Chưa đánh dấu từ nào"
        description="Bấm ngôi sao ở từ khó nhớ trong bộ từ."
      />
    );
  }

  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Đây là đánh giá của riêng bạn, tách biệt với danh sách &quot;điểm yếu&quot; do mô
        hình tính. Chỗ hai bên lệch nhau thường là chỗ đáng chú ý nhất.
      </Typography>

      <Box sx={{ display: 'grid', columnGap: 2, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' } }}>
      {data.map((row) => (
        <SectionCard key={row.item_id} sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
            <Box sx={{ flexGrow: 1, minWidth: 160 }}>
              <Typography variant="body1" sx={{ fontWeight: 700 }}>
                {row.word} <Box component="span" sx={{ fontWeight: 400 }}>- {row.meaning}</Box>
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {row.word_set_name}{row.note ? ` · ${row.note}` : ''}
              </Typography>
            </Box>
            <Chip
              size="small"
              color={row.mastery == null ? 'default'
                : row.mastery >= 0.85 ? 'success' : row.mastery >= 0.6 ? 'warning' : 'error'}
              label={row.mastery == null ? 'Chưa học'
                : `Nắm vững ${Math.round(row.mastery * 100)}%`}
            />
            <Tooltip title="Bỏ đánh dấu">
              <IconButton size="small" onClick={() => clear.mutate(row.item_id, {
                onSuccess: () => onResult('Đã bỏ đánh dấu.'),
              })} aria-label="Bỏ đánh dấu">
                <CloseIcon size={16} />
              </IconButton>
            </Tooltip>
          </Box>
        </SectionCard>
      ))}
      </Box>
    </Box>
  );
}

/** Gom ba thứ liên quan tới "câu chữ & ghi chú cá nhân" vào một trang thay vì ba
 * mục nav rời rạc: luyện viết (UC-37), sổ tay câu (UC-38), từ khó (UC-32). */
function Notebook() {
  const [tab, setTab] = useState(0);
  const [snack, setSnack] = useState<string | null>(null);
  const submissions = useWritingSubmissions();

  return (
    <Box>
      <PageHeader
        title="Luyện viết & Sổ tay"
        subtitle="Luyện dịch câu, lưu câu hay và từ khó nhớ."
      />

      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 3 }}>
        <Tab label="Luyện viết" />
        <Tab label={`Sổ tay câu`} />
        <Tab label="Từ khó" />
        <Tab label={`Bài đã nộp (${submissions.data?.length ?? 0})`} />
      </Tabs>

      {tab === 0 && <WritingTab onResult={setSnack} />}
      {tab === 1 && <NotesTab onResult={setSnack} />}
      {tab === 2 && <FlaggedTab onResult={setSnack} />}
      {tab === 3 && (
        submissions.data && submissions.data.length > 0 ? (
          <Box sx={{ display: 'grid', columnGap: 2, alignItems: 'start', gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' } }}>
            {submissions.data.map((s) => (
              <SectionCard key={s.id} sx={{ mb: 1.5 }}>
                <Typography variant="body2" color="text.secondary">{s.prompt_vi}</Typography>
                <Typography variant="body1" sx={{ my: 1 }}>{s.answer_en}</Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Chip size="small" label={`${Math.round(s.score ?? 0)}/100`} />
                  <Chip size="small" variant="outlined"
                        label={s.grader === 'llm' ? 'AI chấm' : 'Kiểm tra tự động'} />
                  <Typography variant="caption" color="text.secondary">{s.feedback}</Typography>
                </Box>
              </SectionCard>
            ))}
          </Box>
        ) : (
          <EmptyState
            icon={<BookIcon size={24} />}
            title="Chưa nộp bài nào"
            description="Sang tab Luyện viết để làm đề đầu tiên."
          />
        )
      )}

      <Snackbar open={snack !== null} autoHideDuration={3000}
                onClose={() => setSnack(null)} message={snack ?? ''} />
    </Box>
  );
}

export default Notebook;
