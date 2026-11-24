import { useEffect, useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import InputAdornment from '@mui/material/InputAdornment';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { Link as RouterLink, useSearchParams } from 'react-router-dom';

import { useDictionary } from '../api/dictionary';
import { useSpeech } from '../hooks/useSpeech';
import type { DictionaryEntry } from '../api/dictionary';
import AddWordDialog from '../components/AddWordDialog';
import PageHeader from '../components/PageHeader';
import { SearchIcon, SpeakerIcon } from '../components/icons';

/** UC-95 — tra cứu từ.
 *
 * Trang này nói thẳng nó tra ở đâu. Người dùng quen với từ điển thật sẽ mong có
 * mọi từ; ở đây nghĩa đến từ bộ từ của chính họ và các bộ công khai, nên phải
 * ghi rõ để họ hiểu vì sao "supercalifragilistic" không có kết quả — đó là giới
 * hạn của nguồn dữ liệu, không phải lỗi.
 */

function EntryCard({ entry, onAdd }: { entry: DictionaryEntry; onAdd: () => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', mb: 0.5 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{entry.word}</Typography>
        {entry.phonetic && (
          <Typography variant="body2" color="text.secondary">{entry.phonetic}</Typography>
        )}
        {entry.part_of_speech && (
          <Chip size="small" variant="outlined" label={entry.part_of_speech} />
        )}
        {entry.in_my_library && (
          <Chip size="small" color="primary" variant="outlined" label="trong thư viện của bạn" />
        )}
      </Stack>

      <Typography variant="body1">{entry.meaning}</Typography>
      {entry.example && (
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontStyle: 'italic' }}>
          {entry.example}
        </Typography>
      )}

      <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
        <Button size="small" component={RouterLink} to={`/word-sets/${entry.word_set_id}`}>
          Mở bộ “{entry.word_set_name}”
        </Button>
        {!entry.in_my_library && (
          <Button size="small" variant="outlined" onClick={onAdd}>
            Thêm vào bộ từ của tôi
          </Button>
        )}
      </Stack>
    </Paper>
  );
}

function Dictionary() {
  // Nhận ?q= để link từ nơi khác (trang Khám phá) mở thẳng kết quả tra.
  const [params] = useSearchParams();
  const initial = params.get('q') ?? '';
  const [draft, setDraft] = useState(initial);
  const [query, setQuery] = useState(initial);
  const [adding, setAdding] = useState<DictionaryEntry | null>(null);
  const [addBlank, setAddBlank] = useState(false);
  const [snack, setSnack] = useState<string | null>(null);
  const result = useDictionary(query);
  // UC-29 — dùng hook chung: nó giữ tốc độ đọc người dùng đã chọn và tự chọn
  // giọng tiếng Anh. Tự viết lại ở đây sẽ bỏ qua cả hai.
  const speech = useSpeech();

  useEffect(() => {
    const q = params.get('q') ?? '';
    if (q) { setDraft(q); setQuery(q); }
  }, [params]);

  const own = useMemo(
    () => (result.data?.entries ?? []).filter((e) => e.in_my_library),
    [result.data],
  );
  const community = useMemo(
    () => (result.data?.entries ?? []).filter((e) => !e.in_my_library),
    [result.data],
  );

  const submit = (value?: string) => {
    const next = (value ?? draft).trim();
    if (value !== undefined) setDraft(value);
    setQuery(next);
  };

  return (
    <Box>
      <PageHeader
        title="Tra từ"
        subtitle="Tra từ trong bộ của bạn và bộ công khai."
      />

      <Box component="form" onSubmit={(e) => { e.preventDefault(); submit(); }} sx={{ mb: 3 }}>
        <TextField
          fullWidth autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
          placeholder="Nhập một từ tiếng Anh, ví dụ: habitat"
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start"><SearchIcon size={18} /></InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <Button type="submit" variant="contained" disabled={!draft.trim()}>Tra</Button>
                </InputAdornment>
              ),
            },
          }}
        />
      </Box>

      {query === '' && (
        <Alert severity="info">
          Đây là tra cứu <strong>trong kho dữ liệu của hệ thống</strong>, không phải một từ điển
          đầy đủ: nghĩa lấy từ bộ từ vựng của bạn và các bộ công khai. Không có thì hệ thống nói
          là không có, chứ không đoán nghĩa.
        </Alert>
      )}

      {result.isLoading && (
        <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>
      )}
      {result.isError && <Alert severity="error">Không tra được. Thử lại sau.</Alert>}

      {result.data && (
        <Box>
          <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center', mb: 2, flexWrap: 'wrap' }}>
            <Typography variant="h5" component="h2" sx={{ fontWeight: 700 }}>
              {result.data.query}
            </Typography>
            <IconButton
              size="small" aria-label={`Nghe phát âm ${result.data.query}`}
              onClick={() => speech.speak(result.data.query)}
            >
              <SpeakerIcon size={18} />
            </IconButton>
            {result.data.cefr_level ? (
              <Chip size="small" color="primary" label={`CEFR ${result.data.cefr_level}`} />
            ) : (
              <Chip size="small" variant="outlined" label="không có trong wordlist CEFR" />
            )}
          </Stack>

          {result.data.entries.length === 0 ? (
            <Alert severity="info">
              Chưa có bộ từ nào trong hệ thống ghi nghĩa cho “{result.data.query}”.
              <Box sx={{ mt: 1 }}>
                <Button size="small" variant="outlined" onClick={() => setAddBlank(true)}>
                  Tự thêm từ này vào bộ của tôi
                </Button>
              </Box>
              {result.data.suggestions.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  Có phải bạn tìm:{' '}
                  {result.data.suggestions.map((s) => (
                    <Chip
                      key={s} size="small" label={s} sx={{ mr: 0.5, mb: 0.5 }}
                      onClick={() => submit(s)}
                    />
                  ))}
                </Box>
              )}
            </Alert>
          ) : (
            // Có cả hai nguồn thì đặt cạnh nhau để so nghĩa không phải cuộn (2026-11-04)
            <Box sx={{
              display: 'grid', gap: 2.5, alignItems: 'start',
              gridTemplateColumns: own.length > 0 && community.length > 0
                ? { xs: 'minmax(0, 1fr)', md: 'repeat(2, minmax(0, 1fr))' } : 'minmax(0, 1fr)',
            }}>
              {own.length > 0 && (
                <Box>
                  <Typography variant="overline" color="text.secondary">
                    Trong thư viện của bạn
                  </Typography>
                  <Stack spacing={1.5} sx={{ mt: 0.5 }}>
                    {own.map((e, i) => (
                      <EntryCard key={`own-${i}`} entry={e} onAdd={() => setAdding(e)} />
                    ))}
                  </Stack>
                </Box>
              )}

              {community.length > 0 && (
                <Box>
                  <Typography variant="overline" color="text.secondary">
                    Từ các bộ công khai
                  </Typography>
                  <Stack spacing={1.5} sx={{ mt: 0.5 }}>
                    {community.map((e, i) => (
                      <EntryCard key={`pub-${i}`} entry={e} onAdd={() => setAdding(e)} />
                    ))}
                  </Stack>
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}
      <AddWordDialog
        open={adding !== null || addBlank}
        word={adding?.word ?? result.data?.query ?? ''}
        meaning={adding?.meaning ?? ''}
        phonetic={adding?.phonetic ?? null}
        partOfSpeech={adding?.part_of_speech ?? null}
        example={adding?.example ?? null}
        onClose={() => { setAdding(null); setAddBlank(false); }}
        onAdded={(name) => setSnack(`Đã thêm vào bộ “${name}”.`)}
      />

      <Snackbar
        open={snack !== null} autoHideDuration={4000}
        onClose={() => setSnack(null)} message={snack ?? ''}
      />
    </Box>
  );
}

export default Dictionary;
