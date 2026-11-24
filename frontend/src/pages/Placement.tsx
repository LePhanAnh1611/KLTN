import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

import { ApiError } from '../api/client';
import {
  usePlacementQuestions,
  usePlacementStatus,
  useSkipPlacement,
  useSubmitPlacement,
  type PlacementResult,
} from '../api/placement';
import { ACCENT_FONT } from '../theme/theme';
import { BookIcon, GraduationIcon, TrophyIcon } from '../components/icons';

/** UC-11 — bài kiểm tra trình độ đầu vào theo phong cách Hanpeak Diagnostic */
function Placement() {
  const navigate = useNavigate();
  const status = usePlacementStatus();
  const [started, setStarted] = useState(false);
  const questions = usePlacementQuestions(started);
  const submit = useSubmitPlacement();
  const skip = useSkipPlacement();

  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [result, setResult] = useState<PlacementResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const list = questions.data ?? [];
  const current = list[index];

  const finish = (picked: Record<number, string>) => {
    submit.mutate(
      Object.entries(picked).map(([id, answer]) => ({ question_id: Number(id), answer })),
      {
        onSuccess: setResult,
        onError: (e) => setError(e instanceof ApiError ? e.message : 'Không nộp được bài.'),
      },
    );
  };

  const choose = (option: string) => {
    const picked = { ...answers, [current.id]: option };
    setAnswers(picked);
    if (index + 1 < list.length) setIndex(index + 1);
    else finish(picked);
  };

  // ─── 1. MÀN BÁO CÁO KẾT QUẢ CHẨN ĐOÁN (Theo chuẩn Hanpeak Trang 2) ───
  if (result) {
    return (
      <Box sx={{ maxWidth: 760, mx: 'auto', py: 2 }}>
        <Box sx={{ textAlign: 'center', mb: 3 }}>
          <Chip
            label="✓ ĐÃ HOÀN TẤT BÀI ĐÁNH GIÁ"
            size="small"
            color="success"
            variant="outlined"
            sx={{ fontWeight: 800, mb: 1.5, letterSpacing: '0.04em' }}
          />
          <Typography sx={{ fontFamily: ACCENT_FONT, fontSize: { xs: 24, md: 30 }, fontWeight: 800 }}>
            Mình sẽ cùng bạn xây nền tảng thật vững
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75, maxWidth: 540, mx: 'auto' }}>
            Hệ thống đã phân tích kết quả bài chẩn đoán để cá nhân hóa lộ trình phù hợp nhất cho xuất phát điểm của bạn.
          </Typography>
        </Box>

        {/* Điểm xuất phát Banner */}
        <Paper
          sx={{
            p: 3,
            textAlign: 'center',
            mb: 3,
            bgcolor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: '16px',
          }}
        >
          <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary', letterSpacing: '0.08em' }}>
              ĐIỂM BẮT ĐẦU:
            </Typography>
            <Chip
              label={`Cấp độ ${result.estimated_level}`}
              color="primary"
              sx={{ fontWeight: 800, fontSize: '0.85rem' }}
            />
          </Box>
          <Typography variant="body2" color="text.secondary">
            Điểm bắt đầu được đề xuất dựa trên kết quả đánh giá năng lực hiện tại.
          </Typography>
        </Paper>

        {/* 3 Cột Phân tích năng lực (Kỹ năng nổi bật / Nền tảng ổn định / Ưu tiên củng cố) */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr 1fr' },
            gap: 2,
            mb: 3,
          }}
        >
          {/* Cột 1: Kỹ năng nổi bật */}
          <Card sx={{ p: 2.5, borderRadius: '12px', bgcolor: 'background.paper' }}>
            <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary', letterSpacing: '0.05em' }}>
              KỸ NĂNG NỔI BẬT
            </Typography>
            <Typography variant="body2" sx={{ mt: 1.5, color: 'text.primary', lineHeight: 1.5 }}>
              {result.correct_count > 0
                ? `Nhận diện tốt các từ vựng cốt lõi (${result.correct_count} câu đúng).`
                : 'Sẵn sàng bắt đầu từ những mẫu câu và từ vựng nền tảng nhất.'}
            </Typography>
          </Card>

          {/* Cột 2: Nền tảng đang ổn định */}
          <Card sx={{ p: 2.5, borderRadius: '12px', bgcolor: 'background.paper' }}>
            <Typography variant="caption" sx={{ fontWeight: 800, color: 'text.secondary', letterSpacing: '0.05em' }}>
              NỀN TẢNG ĐANG ỔN ĐỊNH
            </Typography>
            <Typography variant="body2" sx={{ mt: 1.5, color: 'text.primary', lineHeight: 1.5 }}>
              Đạt chuẩn xuất phát <strong>{result.entry_cefr_level || result.estimated_level}</strong>. Các chặng dưới mức này sẽ được tối ưu lướt qua.
            </Typography>
          </Card>

          {/* Cột 3: Ưu tiên củng cố */}
          <Card sx={{ p: 2.5, borderRadius: '12px', bgcolor: 'background.paper' }}>
            <Typography variant="caption" sx={{ fontWeight: 800, color: 'warning.main', letterSpacing: '0.05em' }}>
              ƯU TIÊN CỦNG CỐ
            </Typography>
            <Typography variant="body2" sx={{ mt: 1.5, color: 'text.primary', lineHeight: 1.5 }}>
              Ôn từ vựng theo lịch riêng: từ nào sắp quên sẽ được nhắc ôn đúng lúc.
            </Typography>
          </Card>
        </Box>

        {/* Phân rã theo cấp độ CEFR */}
        {result.per_level.length > 0 && (
          <Paper sx={{ p: 2.5, mb: 3, borderRadius: '12px' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 800, mb: 2 }}>
              Phân bổ độ chính xác theo cấp độ CEFR
            </Typography>
            <Stack spacing={1.5}>
              {result.per_level.map((lv) => (
                <Box key={lv.cefr_level} sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Chip size="small" label={lv.cefr_level} sx={{ minWidth: 46, fontWeight: 800 }} />
                  <LinearProgress
                    variant="determinate"
                    value={lv.answered ? (lv.correct / lv.answered) * 100 : 0}
                    sx={{ flexGrow: 1, height: 8 }}
                  />
                  <Typography variant="caption" sx={{ minWidth: 50, textAlign: 'right', fontWeight: 700 }}>
                    {lv.correct}/{lv.answered} ({Math.round(lv.answered ? (lv.correct / lv.answered) * 100 : 0)}%)
                  </Typography>
                </Box>
              ))}
            </Stack>
          </Paper>
        )}

        <Button
          variant="contained"
          color="primary"
          size="large"
          fullWidth
          onClick={() => navigate('/roadmap')}
          sx={{ py: 1.4, fontWeight: 800, fontSize: '1rem', borderRadius: '999px' }}
        >
          Bắt đầu với lộ trình của bạn →
        </Button>
      </Box>
    );
  }

  // ─── 2. MÀN KHẢO SÁT & BẮT ĐẦU (Theo chuẩn Hanpeak Trang 2) ───
  if (!started) {
    return (
      <Box sx={{ maxWidth: 740, mx: 'auto', py: 2 }}>
        <Box sx={{ textAlign: 'center', mb: 4 }}>
          <Typography sx={{ fontFamily: ACCENT_FONT, fontSize: { xs: 26, md: 32 }, fontWeight: 800, mb: 1 }}>
            Để LearningHub hiểu thêm về bạn nhé!
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 520, mx: 'auto' }}>
            Việc này giúp hệ thống tinh chỉnh lộ trình học tối ưu và chính xác nhất cho bạn.
          </Typography>
          <Typography sx={{ fontWeight: 750, color: 'primary.main', mt: 2 }}>
            Bạn đã từng học tiếng Anh chưa?
          </Typography>
        </Box>

        {/* 3 Thẻ Lựa chọn khảo sát (Clean Cards) */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: '1fr 1fr 1fr' },
            gap: 2,
            mb: 4,
          }}
        >
          {/* Card 1: Chưa từng học */}
          <Card
            onClick={() =>
              skip.mutate(undefined, {
                onSuccess: setResult,
                onError: (e) => setError(e instanceof ApiError ? e.message : 'Không lưu được.'),
              })
            }
            sx={{
              p: 3,
              textAlign: 'center',
              cursor: 'pointer',
              borderRadius: '16px',
              border: '1px solid',
              borderColor: 'divider',
              transition: 'all 0.15s ease',
              '&:hover': {
                borderColor: 'primary.main',
                transform: 'none',
              },
            }}
          >
            <Box
              sx={{
                width: 52,
                height: 52,
                borderRadius: '999px',
                display: 'grid',
                placeItems: 'center',
                mx: 'auto',
                mb: 2,
                bgcolor: 'background.muted',
                color: 'success.main',
              }}
            >
              <BookIcon size={26} />
            </Box>
            <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', mb: 0.75 }}>
              Chưa từng học
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.4 }}>
              Bắt đầu từ vựng và nền tảng căn bản nhất (A1).
            </Typography>
          </Card>

          {/* Card 2: Đã từng học */}
          <Card
            onClick={() => { setStarted(true); setIndex(0); setAnswers({}); }}
            sx={{
              p: 3,
              textAlign: 'center',
              cursor: 'pointer',
              borderRadius: '16px',
              border: '2px solid',
              borderColor: 'primary.main',
              bgcolor: 'background.paper',
              transition: 'all 0.15s ease',
              '&:hover': {
                transform: 'none',
              },
            }}
          >
            <Box
              sx={{
                width: 52,
                height: 52,
                borderRadius: '999px',
                display: 'grid',
                placeItems: 'center',
                mx: 'auto',
                mb: 2,
                bgcolor: 'primary.main',
                color: '#FFFFFF',
              }}
            >
              <GraduationIcon size={26} />
            </Box>
            <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', mb: 0.75, color: 'primary.main' }}>
              Đã từng học
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.4 }}>
              Kiểm tra nhanh để định vị chính xác trình độ.
            </Typography>
          </Card>

          {/* Card 3: Đã có chứng chỉ */}
          <Card
            onClick={() => { setStarted(true); setIndex(0); setAnswers({}); }}
            sx={{
              p: 3,
              textAlign: 'center',
              cursor: 'pointer',
              borderRadius: '16px',
              border: '1px solid',
              borderColor: 'divider',
              transition: 'all 0.15s ease',
              '&:hover': {
                borderColor: 'primary.main',
                transform: 'none',
              },
            }}
          >
            <Box
              sx={{
                width: 52,
                height: 52,
                borderRadius: '999px',
                display: 'grid',
                placeItems: 'center',
                mx: 'auto',
                mb: 2,
                bgcolor: 'background.muted',
                color: 'warning.main',
              }}
            >
              <TrophyIcon size={26} />
            </Box>
            <Typography sx={{ fontWeight: 800, fontSize: '0.95rem', mb: 0.75 }}>
              Đã có nền tảng
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', lineHeight: 1.4 }}>
              Xác định các lỗ hổng kiến thức nâng cao.
            </Typography>
          </Card>
        </Box>

        {status.data?.has_placement && status.data.entry_cefr_level && (
          <Alert severity="info" sx={{ mb: 2 }}>
            Bạn đã có trình độ đầu vào <strong>{status.data.entry_cefr_level}</strong>. Làm lại sẽ ghi đè kết quả cũ.
          </Alert>
        )}
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <Box sx={{ textAlign: 'center' }}>
          <Button
            variant="contained"
            color="primary"
            size="large"
            disabled={status.data?.question_count === 0}
            onClick={() => { setStarted(true); setIndex(0); setAnswers({}); }}
            sx={{ px: 4, py: 1.2, fontWeight: 800, borderRadius: '999px' }}
          >
            Bắt đầu đánh giá ngay →
          </Button>
        </Box>
      </Box>
    );
  }

  if (questions.isLoading || submit.isPending) {
    return <Box sx={{ textAlign: 'center', py: 8 }}><CircularProgress /></Box>;
  }
  if (questions.isError || !current) {
    return <Alert severity="error">Không tải được câu hỏi.</Alert>;
  }

  // ─── 3. MÀN LÀM BÀI CHẨN ĐOÁN (Assessment In Progress) ───
  return (
    <Box sx={{ maxWidth: 640, mx: 'auto', py: 2 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Button size="small" onClick={() => finish(answers)} sx={{ color: 'text.secondary' }}>
          ← Dừng & chấm điểm
        </Button>
        <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary' }}>
          Câu hỏi {index + 1} / {list.length}
        </Typography>
      </Box>

      <LinearProgress
        variant="determinate"
        value={(index / list.length) * 100}
        sx={{ mb: 3, height: 6, borderRadius: 999 }}
      />

      <Card sx={{ p: { xs: 3, md: 4 }, borderRadius: '16px' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Chip size="small" color="primary" variant="outlined" label={`Mức ${current.cefr_level}`} sx={{ fontWeight: 800 }} />
          <Typography variant="caption" color="text.secondary">Chọn 1 đáp án đúng</Typography>
        </Box>

        <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', lineHeight: 1.5, minWidth: 0, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Từ vựng này nghĩa là gì?
        </Typography>

        <Typography
          sx={{
            fontFamily: ACCENT_FONT,
            fontSize: { xs: 32, md: 40 },
            fontWeight: 800,
            color: 'text.primary',
            my: 2,
          }}
        >
          {current.word}
        </Typography>

        <Stack spacing={1.5} sx={{ mt: 3 }}>
          {current.options.map((option, optIdx) => (
            <Button
              key={option}
              variant="outlined"
              size="large"
              sx={{
                justifyContent: 'flex-start',
                textTransform: 'none',
                py: 1.25,
                px: 2,
                borderRadius: '10px',
                fontSize: '0.95rem',
                fontWeight: 600,
              }}
              onClick={() => choose(option)}
            >
              <Box
                component="span"
                sx={{
                  width: 24,
                  height: 24,
                  borderRadius: '6px',
                  display: 'grid',
                  placeItems: 'center',
                  mr: 1.5,
                  border: '1px solid',
                  borderColor: 'divider',
                  fontSize: '0.75rem',
                  fontWeight: 750,
                  bgcolor: 'background.muted',
                }}
              >
                {optIdx + 1}
              </Box>
              {option}
            </Button>
          ))}
        </Stack>
      </Card>
    </Box>
  );
}

export default Placement;
