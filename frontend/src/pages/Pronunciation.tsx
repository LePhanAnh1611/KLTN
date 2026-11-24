import { useEffect, useMemo, useState } from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Snackbar from '@mui/material/Snackbar';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

import { useItems, useWordSets } from '../api/wordSets';
import PronunciationCheck from '../components/PronunciationCheck';
import SpeakButton from '../components/SpeakButton';
import EmptyState from '../components/EmptyState';
import MiniStat from '../components/MiniStat';
import PageHeader from '../components/PageHeader';
import SectionCard from '../components/SectionCard';
import SentencePractice from '../components/SentencePractice';
import { CheckIcon, MicIcon, StarIcon } from '../components/icons';
import { useSpeechRecognition } from '../hooks/useSpeechRecognition';
import { GOOD_THRESHOLD, type PronunciationResult } from '../lib/pronunciation';
import {
  usePronunciationBestScores, usePronunciationStats, useRecordPronunciation,
} from '../api/extras';

/** Điểm cao nhất đạt được cho mỗi từ (item_id → điểm). */
type Scores = Record<number, number>;

function Practice({ wordSetId, onResult }: {
  wordSetId: number; onResult: (msg: string) => void;
}) {
  const { data: items, isLoading } = useItems(wordSetId);
  const [index, setIndex] = useState(0);
  // Điểm vừa chấm ở trình duyệt, hiện ngay trong lúc chờ server lưu xong.
  const [localScores, setLocalScores] = useState<Scores>({});
  const { data: savedScores } = usePronunciationBestScores(wordSetId);

  // Đổi bộ từ thì quay về từ đầu tiên (tiến độ đã lưu trên server vẫn giữ)
  useEffect(() => { setIndex(0); setLocalScores({}); }, [wordSetId]);

  const list = useMemo(() => items ?? [], [items]);
  const current = list[index];

  // Nguồn chính là server (bền qua F5/chuyển trang, gồm cả đọc câu); gộp với
  // điểm vừa chấm bằng max để ô thống kê nhảy ngay, không phải đợi refetch.
  const scores = useMemo<Scores>(() => {
    const merged: Scores = {};
    for (const row of savedScores ?? []) merged[row.item_id] = row.best_score;
    for (const [id, s] of Object.entries(localScores)) {
      merged[Number(id)] = Math.max(merged[Number(id)] ?? 0, s);
    }
    // chỉ đếm từ còn trong bộ đang hiển thị
    const ids = new Set(list.map((it) => it.id));
    return Object.fromEntries(
      Object.entries(merged).filter(([id]) => ids.has(Number(id))),
    );
  }, [savedScores, localScores, list]);

  const saveAttempt = useRecordPronunciation();
  const practiced = Object.keys(scores).length;
  const goodCount = Object.values(scores).filter((s) => s >= GOOD_THRESHOLD).length;
  const average = practiced
    ? Math.round(Object.values(scores).reduce((a, b) => a + b, 0) / practiced) : 0;

  if (isLoading) return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  if (list.length === 0) {
    return <Alert severity="info">Bộ từ vựng này chưa có từ nào để luyện.</Alert>;
  }

  const record = (result: PronunciationResult) => {
    if (!current) return;
    setLocalScores((prev) => ({
      ...prev,
      // giữ điểm CAO NHẤT: đọc lại nhiều lần thì lấy lần tốt nhất
      [current.id]: Math.max(prev[current.id] ?? 0, result.score),
    }));
    // Lưu lại để có lịch sử; điểm này KHÔNG vào mastery hay lịch ôn.
    // Lỗi mạng thì bỏ qua — không được chặn người đang luyện.
    saveAttempt.mutate({
      item_id: current.id,
      score: Math.round(result.score),
      transcript: result.heard ?? null,
    });
  };

  const best = current ? scores[current.id] : undefined;

  return (
    <>
      <Card sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: { xs: 1.5, sm: 3 }, px: 2.5, py: 1.5, mb: 2.5 }}>
        <MiniStat icon={<MicIcon size={18} />} value={`${practiced}/${list.length}`} label="Từ đã luyện" />
        <MiniStat icon={<CheckIcon size={18} />} value={goodCount} label="Đạt phát âm tốt" />
        <MiniStat icon={<StarIcon size={18} />} value={practiced ? average : '-'} label="Điểm trung bình" />
        <LinearProgress
          variant="determinate" value={(practiced / list.length) * 100}
          sx={{ flex: '1 1 160px' }}
        />
      </Card>

      {/* Hai cột: trái luyện TỪ, phải luyện CÂU. Màn rộng giữ cả trang trong một
          màn hình, kết quả dài thì cuộn trong cột phải (2026-11-04). */}
      <Box sx={{
        display: 'grid', gap: 2.5,
        gridTemplateColumns: { xs: 'minmax(0, 1fr)', md: 'minmax(0, 5fr) minmax(0, 7fr)' },
        height: { md: 'calc(100vh - 294px)' }, minHeight: { md: 430 },
      }}>
        <Card sx={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          <CardContent sx={{ flexGrow: 1, minHeight: 0, overflowY: 'auto', textAlign: 'center', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Từ {index + 1} / {list.length}
            </Typography>

            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
              <Typography variant="h3" sx={{ overflowWrap: 'anywhere' }}>{current.word}</Typography>
              <SpeakButton text={current.word} size={28} label="Nghe mẫu" />
            </Box>
            {current.phonetic && (
              <Typography color="text.secondary">{current.phonetic}</Typography>
            )}
            <Typography variant="h6" sx={{ mt: 1 }}>{current.meaning}</Typography>

            {best !== undefined && (
              <Box>
                <Chip
                  size="small" sx={{ mt: 1.5 }}
                  color={best >= GOOD_THRESHOLD ? 'success' : 'warning'}
                  label={`Điểm tốt nhất: ${best}/100`}
                />
              </Box>
            )}

            <Typography variant="body2" color="text.secondary" sx={{ mt: 2.5 }}>
              Bấm nghe mẫu, rồi bấm micro và đọc lại từ này
            </Typography>
            {/* key theo từ: đổi từ thì xóa kết quả cũ trên thẻ. */}
            <PronunciationCheck key={`word-${current.id}`} word={current.word} onResult={record} prominent />
          </CardContent>

          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1, px: 2, pb: 2 }}>
            <Button disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
              ← Từ trước
            </Button>
            <Button variant="contained" disabled={index >= list.length - 1}
                    onClick={() => setIndex((i) => i + 1)}>
              Từ tiếp →
            </Button>
          </Box>
        </Card>

        <Card sx={{ minHeight: 0, overflowY: { md: 'auto' } }}>
          <CardContent>
            {/* Luyện đọc CẢ CÂU chứa từ này — máy chủ chấm, chỉ ra từng từ sai.
                key theo item để đổi từ là làm lại từ đầu. */}
            <SentencePractice
              key={`sentence-${current.id}`}
              itemId={current.id}
              word={current.word}
              example={current.example}
              onResult={onResult}
            />
          </CardContent>
        </Card>
      </Box>
    </>
  );
}

/** Luyện phát âm — chấm bằng bộ nhận dạng giọng nói của trình duyệt.
 *
 * Tách riêng khỏi màn Học để phiên học giữ được sự tập trung, và để người dùng
 * luyện phát âm độc lập mà không phải mở một phiên học. */
/** Lịch sử chấm phát âm — có được nhờ việc lưu lại từng lần thử.
 *
 * Nói rõ điểm này không tính vào tiến độ học: Web Speech API phụ thuộc micro và
 * môi trường, không đủ tin cậy để làm đầu vào cho mô hình. */
function PronunciationHistory() {
  const { data } = usePronunciationStats();
  if (!data || data.total_attempts === 0) return null;

  return (
    <SectionCard
      title="Lịch sử luyện phát âm"
      caption="Chỉ để tự theo dõi, không ảnh hưởng lịch ôn."
      sx={{ mt: 4 }}
    >
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <Chip label={`${data.total_attempts} lượt`} />
        <Chip label={`${data.words_practiced} từ`} />
        <Chip color="primary" label={`Trung bình ${data.average_score}`} />
        <Chip color="success" label={`Cao nhất ${data.best_score}`} />
      </Box>

      {data.recent.map((row) => (
        <Box key={row.id} sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 1,
                                borderTop: 1, borderColor: 'divider',
                                '&:first-of-type': { borderTop: 0 } }}>
          <Typography variant="body2" sx={{ fontWeight: 700, minWidth: 110 }}>
            {row.word}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1, minWidth: 0 }}
                      noWrap>
            {row.transcript ? `nghe được: “${row.transcript}”` : '-'}
          </Typography>
          <Chip
            size="small"
            color={row.score >= GOOD_THRESHOLD ? 'success' : row.score >= 60 ? 'warning' : 'error'}
            label={Math.round(row.score)}
          />
        </Box>
      ))}
    </SectionCard>
  );
}

function Pronunciation() {
  const { data: wordSets, isLoading } = useWordSets();
  const { supported } = useSpeechRecognition();
  const [wordSetId, setWordSetId] = useState<number | ''>('');
  const [snack, setSnack] = useState<string | null>(null);

  // Tự chọn bộ đầu tiên có từ
  useEffect(() => {
    if (wordSetId === '' && wordSets?.length) {
      const first = wordSets.find((ws) => ws.item_count > 0) ?? wordSets[0];
      setWordSetId(first.id);
    }
  }, [wordSets, wordSetId]);

  return (
    <Box sx={{ maxWidth: 1120, mx: 'auto' }}>
      <PageHeader
        title="Luyện phát âm"
        subtitle="Nghe mẫu rồi đọc lại từng từ và câu ví dụ."
        actions={wordSets && wordSets.length > 0 ? (
          <TextField
            select size="small" label="Chọn bộ từ vựng" value={wordSetId}
            sx={{ width: { xs: '100%', md: 340 } }}
            onChange={(e) => setWordSetId(Number(e.target.value))}
          >
            {wordSets.map((ws) => (
              <MenuItem key={ws.id} value={ws.id} disabled={ws.item_count === 0}>
                {ws.name} ({ws.item_count} từ)
              </MenuItem>
            ))}
          </TextField>
        ) : undefined}
      />

      {!supported && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Trình duyệt này không hỗ trợ nhận dạng giọng nói nên phần <strong>đọc
          từng từ</strong> sẽ không chấm được - hãy dùng Chrome hoặc Edge.
          Phần <strong>đọc câu mẫu</strong> vẫn chạy bình thường vì nó chấm trên
          máy chủ, không phụ thuộc trình duyệt.
        </Alert>
      )}

      {isLoading && <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>}

      {wordSets && wordSets.length === 0 && (
        <EmptyState
          icon={<MicIcon size={24} />}
          title="Chưa có từ nào để luyện"
          description="Tạo hoặc tải một bộ từ rồi quay lại đây."
        />
      )}

      {wordSetId !== '' && <Practice wordSetId={wordSetId} onResult={setSnack} />}

      <PronunciationHistory />

      <Snackbar open={snack !== null} autoHideDuration={4000}
                onClose={() => setSnack(null)} message={snack ?? ''} />
    </Box>
  );
}

export default Pronunciation;
