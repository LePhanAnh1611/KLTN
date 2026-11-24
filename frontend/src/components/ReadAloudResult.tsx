import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { alpha } from '@mui/material/styles';

import type { ReadAloudResult as Result } from '../api/extras';
import SectionCard from './SectionCard';

const LEVEL_COLOR: Record<number, 'error' | 'warning' | 'info' | 'success'> = {
  1: 'error', 2: 'warning', 3: 'info', 4: 'success',
};

/** Câu mẫu tô màu theo từng từ — thứ người học nhìn đầu tiên.
 *
 * Đây là cái mà chế độ nói tự do không làm được: vì biết trước câu cần đọc nên
 * chỉ được đúng từ nào sai, thay vì chỉ đưa một điểm chung. */
function ColoredSentence({ words }: { words: Result['words'] }) {
  return (
    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, lineHeight: 2 }}>
      {words.map((word, index) => {
        const unclear = word.ok && word.confidence !== null && word.confidence < 0.7;
        const tone = !word.ok ? 'error' : unclear ? 'warning' : 'success';

        return (
          <Tooltip
            key={`${word.expected}-${index}`}
            title={
              !word.ok
                ? word.heard
                  ? `Máy nghe thành “${word.heard}”`
                  : 'Chưa nghe thấy từ này'
                : unclear
                  ? `Đúng từ nhưng chưa rõ (${Math.round((word.confidence ?? 0) * 100)}%)`
                  : 'Đọc đúng và rõ'
            }
          >
            <Box
              component="span"
              sx={{
                px: 1, py: 0.25, borderRadius: 1.5, fontSize: 20, fontWeight: 600,
                bgcolor: (t) => alpha(t.palette[tone].main, 0.16),
                color: `${tone}.main`,
                textDecoration: word.ok ? 'none' : 'line-through',
              }}
            >
              {word.expected}
            </Box>
          </Tooltip>
        );
      })}
    </Box>
  );
}

function ReadAloudResultView({ result }: { result: Result }) {
  return (
    <Box>
      {result.warnings.map((warning) => (
        <Alert key={warning} severity="warning" sx={{ mb: 1.5 }}>{warning}</Alert>
      ))}

      <SectionCard
        title="Kết quả đọc"
        action={
          <Chip color={LEVEL_COLOR[result.overall_level]}
                label={`Mức ${result.overall_level}`} />
        }
        sx={{ mb: 2 }}
      >
        <ColoredSentence words={result.words} />

        <Box sx={{ display: 'flex', gap: 3, mt: 2.5, flexWrap: 'wrap' }}>
          <Box>
            <Typography variant="caption" color="text.secondary">Đọc đúng</Typography>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              {Math.round(result.accuracy * 100)}%
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Độ rõ</Typography>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              {Math.round(result.clarity * 100)}%
            </Typography>
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">Tốc độ</Typography>
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              {Math.round(result.audio_metrics.words_per_minute ?? 0)}
              <Box component="span" sx={{ fontSize: 14, fontWeight: 400 }}> từ/phút</Box>
            </Typography>
          </Box>
        </Box>

        <Alert severity="info" sx={{ mt: 2 }}>{result.feedback}</Alert>
      </SectionCard>

      {result.aspects.map((aspect) => (
        <SectionCard key={aspect.key} sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 700, flexGrow: 1 }}>
              {aspect.label}
            </Typography>
            <Chip size="small" color={LEVEL_COLOR[aspect.level]}
                  label={`${aspect.level} · ${aspect.level_label}`} />
          </Box>
          <Typography variant="body2" color="text.secondary">{aspect.detail}</Typography>
          <Typography variant="body2" sx={{ mt: 0.75 }}>
            <strong>Nên làm:</strong> {aspect.suggestion}
          </Typography>
        </SectionCard>
      ))}

      {result.transcript && (
        <Typography variant="caption" color="text.secondary">
          Máy nghe được: “{result.transcript}”
          {result.extra_words.length > 0
            && ` · nói thêm: ${result.extra_words.join(', ')}`}
        </Typography>
      )}
    </Box>
  );
}

export default ReadAloudResultView;
export { LEVEL_COLOR as READ_ALOUD_LEVEL_COLOR };
