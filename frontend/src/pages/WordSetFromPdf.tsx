import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Snackbar from '@mui/material/Snackbar';
import Stack from '@mui/material/Stack';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  CEFR_LEVELS,
  useCreateWordSetFromPdf,
  useExtractPdf,
  usePdfImportHealth,
  type PdfCandidateWord,
  type PdfExtractResponse,
} from '../api/pdfImport';
import EmptyState from '../components/EmptyState';
import PageHeader from '../components/PageHeader';
import SectionCard from '../components/SectionCard';
import { BookIcon } from '../components/icons';

/** Trạng thái phụ thuộc — nói trước khi người học mất công chọn file. */
function DependencyBanner() {
  const { data, isLoading } = usePdfImportHealth();
  if (isLoading || !data) return null;

  // Ollama chỉ ảnh hưởng phần chủ đề, không chặn luồng -> tách riêng khỏi lỗi nặng.
  const blocking = data.dependencies.filter((d) => !d.ready && d.name !== 'ollama');
  const topicOff = data.dependencies.some((d) => d.name === 'ollama' && !d.ready);

  if (blocking.length > 0) {
    return (
      <Alert severity="warning" sx={{ mb: 3 }}>
        <AlertTitle>Máy chủ chưa cài đủ thư viện để đọc PDF</AlertTitle>
        {blocking.map((d) => (
          <Typography key={d.name} variant="body2">• {d.detail}</Typography>
        ))}
      </Alert>
    );
  }

  return (
    <Alert severity={topicOff ? 'info' : 'success'} sx={{ mb: 3 }}>
      Sẵn sàng - tối đa {data.max_file_mb}MB / {data.max_pages} trang, mức CEFR tra từ{' '}
      nguồn chuẩn {data.cefr_source} ({data.cefr_word_count.toLocaleString('vi-VN')} từ).
      {topicOff && ' Ollama chưa chạy nên bộ từ vựng sẽ không có chủ đề - các phần khác vẫn đầy đủ.'}
    </Alert>
  );
}

function LevelChip({ level }: { level: string | null }) {
  if (!level) {
    // Không tô màu và nói rõ "chưa rõ": hệ thống KHÔNG đoán mức CEFR.
    return (
      <Tooltip title="Từ này không có trong wordlist chuẩn - hệ thống không đoán mức">
        <Chip label="-" size="small" variant="outlined" />
      </Tooltip>
    );
  }
  return <Chip label={level} size="small" color="primary" variant="outlined" />;
}

function WordSetFromPdf() {
  const navigate = useNavigate();
  const extract = useExtractPdf();
  const create = useCreateWordSetFromPdf();

  const [file, setFile] = useState<File | null>(null);
  const [levelFilter, setLevelFilter] = useState<string[]>([]);
  const [result, setResult] = useState<PdfExtractResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [meanings, setMeanings] = useState<Record<string, string>>({});
  const [name, setName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [snack, setSnack] = useState<string | null>(null);

  // useMemo để mảng giữ nguyên định danh giữa các lần render (bộ lọc bên dưới phụ thuộc nó)
  const candidates = useMemo(() => result?.candidates ?? [], [result]);
  const visible = useMemo(
    () =>
      levelFilter.length === 0
        ? candidates
        : candidates.filter((c) => c.cefr_level && levelFilter.includes(c.cefr_level)),
    [candidates, levelFilter],
  );

  const toggleLevel = (level: string) =>
    setLevelFilter((prev) =>
      prev.includes(level) ? prev.filter((l) => l !== level) : [...prev, level],
    );

  const toggleWord = (lemma: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(lemma)) next.delete(lemma);
      else next.add(lemma);
      return next;
    });

  const toggleAllVisible = () => {
    const allChosen = visible.length > 0 && visible.every((c) => selected.has(c.lemma));
    setSelected((prev) => {
      const next = new Set(prev);
      visible.forEach((c) => (allChosen ? next.delete(c.lemma) : next.add(c.lemma)));
      return next;
    });
  };

  const handleExtract = () => {
    if (!file) return;
    setError(null);
    extract.mutate(
      { file, cefrLevels: levelFilter },
      {
        onSuccess: (data) => {
          setResult(data);
          // Mặc định chọn hết: người học bỏ vài từ rác nhanh hơn tick lại cả trăm từ.
          setSelected(new Set(data.candidates.map((c) => c.lemma)));
          setMeanings({});
          setName((current) => current || data.filename.replace(/\.pdf$/i, ''));
        },
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : 'Không đọc được tài liệu.'),
      },
    );
  };

  const chosen: PdfCandidateWord[] = candidates.filter((c) => selected.has(c.lemma));
  const missingMeaning = chosen.filter((c) => !(meanings[c.lemma] ?? '').trim()).length;

  const handleCreate = () => {
    setError(null);
    create.mutate(
      {
        name: name.trim(),
        source_filename: result?.filename ?? null,
        words: chosen.map((c) => ({
          word: c.word,
          lemma: c.lemma,
          part_of_speech: c.part_of_speech,
          meaning: (meanings[c.lemma] ?? '').trim(),
          example: c.example_sentence,
          cefr_level: c.cefr_level,
          topic: c.topic,
        })),
      },
      {
        onSuccess: (wordSet) => {
          setSnack('Đã tạo bộ từ vựng.');
          navigate(`/word-sets/${wordSet.id}`);
        },
        onError: (err) =>
          setError(err instanceof ApiError ? err.message : 'Không tạo được bộ từ vựng.'),
      },
    );
  };

  return (
    <>
      <PageHeader
        title="Tạo bộ từ từ PDF"
        subtitle="Tải PDF lên, hệ thống trích từ vựng để bạn chọn lưu."
        actions={
          <Button variant="text" onClick={() => navigate('/word-sets')}>
            Về thư viện
          </Button>
        }
      />

      <DependencyBanner />

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <SectionCard
        title="1. Chọn tài liệu"
        caption="Chỉ nhận PDF có chữ (không nhận bản scan)."
        sx={{ mb: 3 }}
      >
        <Stack spacing={2}>
          <Box>
            <Button variant="outlined" component="label">
              {file ? 'Đổi file' : 'Chọn file PDF'}
              <input
                hidden
                type="file"
                accept="application/pdf,.pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </Button>
            {file && (
              <Typography variant="body2" sx={{ display: 'inline', ml: 1.5 }}>
                {file.name}
              </Typography>
            )}
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.75 }}>
              Lọc theo trình độ (bỏ trống = lấy tất cả). Từ không có trong wordlist chuẩn
              sẽ bị loại khi bật bộ lọc.
            </Typography>
            <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap' }} useFlexGap>
              {CEFR_LEVELS.map((level) => (
                <Chip
                  key={level}
                  label={level}
                  onClick={() => toggleLevel(level)}
                  color={levelFilter.includes(level) ? 'primary' : 'default'}
                  variant={levelFilter.includes(level) ? 'filled' : 'outlined'}
                />
              ))}
            </Stack>
          </Box>

          <Box>
            <Button
              variant="contained"
              disabled={!file || extract.isPending}
              onClick={handleExtract}
            >
              {extract.isPending ? 'Đang đọc tài liệu…' : 'Trích từ vựng'}
            </Button>
          </Box>

          {extract.isPending && <LinearProgress />}
        </Stack>
      </SectionCard>

      {result && (
        <SectionCard
          title="2. Duyệt từ trích được"
          caption={`${result.page_count} trang · ${result.total_words} từ duy nhất · đang chọn ${chosen.length}/${candidates.length}`}
          action={
            <Button size="small" onClick={toggleAllVisible} disabled={visible.length === 0}>
              Chọn/bỏ tất cả
            </Button>
          }
          sx={{ mb: 3 }}
        >
          {result.warnings.map((warning) => (
            <Alert key={warning} severity="info" sx={{ mb: 2 }}>
              {warning}
            </Alert>
          ))}

          {visible.length === 0 ? (
            <EmptyState
              icon={<BookIcon />}
              title="Không còn từ nào"
              description="Thử bỏ bộ lọc trình độ, hoặc dùng một tài liệu khác."
            />
          ) : (
            <TableContainer sx={{ maxHeight: 560 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell padding="checkbox" />
                    <TableCell>Từ</TableCell>
                    <TableCell>Từ loại</TableCell>
                    <TableCell>CEFR</TableCell>
                    <TableCell>Chủ đề</TableCell>
                    <TableCell align="right">Lần</TableCell>
                    <TableCell sx={{ minWidth: 200 }}>Nghĩa tiếng Việt</TableCell>
                    <TableCell sx={{ minWidth: 260 }}>Câu gốc trong tài liệu</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {visible.map((candidate) => (
                    <TableRow key={candidate.lemma} hover>
                      <TableCell padding="checkbox">
                        <Checkbox
                          checked={selected.has(candidate.lemma)}
                          onChange={() => toggleWord(candidate.lemma)}
                        />
                      </TableCell>
                      <TableCell sx={{ fontWeight: 700 }}>
                        {candidate.word}
                        {/* Tài liệu viết "absorbs" nhưng từ đáng học là "absorb" —
                            hiện cả hai để người học đối chiếu được. */}
                        {candidate.surface_form !== candidate.word && (
                          <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                            gặp: {candidate.surface_form}
                          </Typography>
                        )}
                      </TableCell>
                      <TableCell>{candidate.part_of_speech ?? '-'}</TableCell>
                      <TableCell><LevelChip level={candidate.cefr_level} /></TableCell>
                      <TableCell>{candidate.topic ?? '-'}</TableCell>
                      <TableCell align="right">{candidate.occurrences}</TableCell>
                      <TableCell>
                        <TextField
                          size="small"
                          fullWidth
                          placeholder="Nhập nghĩa…"
                          value={meanings[candidate.lemma] ?? ''}
                          onChange={(e) =>
                            setMeanings((prev) => ({ ...prev, [candidate.lemma]: e.target.value }))
                          }
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {candidate.example_sentence ?? '-'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </SectionCard>
      )}

      {result && (
        <SectionCard title="3. Đặt tên và tạo bộ từ vựng">
          <Stack spacing={2}>
            <TextField
              label="Tên bộ từ vựng"
              value={name}
              onChange={(e) => setName(e.target.value)}
              slotProps={{ htmlInput: { maxLength: 200 } }}
              fullWidth
            />

            {missingMeaning > 0 && (
              <Alert severity="warning">
                {missingMeaning} từ chưa có nghĩa tiếng Việt. Vẫn tạo được - bạn bổ sung
                sau ở màn chi tiết bộ từ vựng.
              </Alert>
            )}

            <Box>
              <Button
                variant="contained"
                disabled={chosen.length === 0 || !name.trim() || create.isPending}
                onClick={handleCreate}
              >
                {create.isPending ? 'Đang tạo…' : `Tạo bộ từ vựng (${chosen.length} từ)`}
              </Button>
            </Box>
          </Stack>
        </SectionCard>
      )}

      <Snackbar
        open={snack !== null}
        autoHideDuration={3000}
        onClose={() => setSnack(null)}
        message={snack ?? ''}
      />
    </>
  );
}

export default WordSetFromPdf;
