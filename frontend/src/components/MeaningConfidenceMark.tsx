import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import { alpha } from '@mui/material/styles';

import type { MeaningConfidence } from '../types/wordSet';

/**
 * Dấu độ tin cậy của NGHĨA, đặt cạnh nghĩa trong bảng từ.
 *
 * Vì sao cần: bộ từ nền lấy nghĩa từ một bản số hoá từ điển cũ, nên nghĩa đầu
 * tiên đôi khi là nghĩa cổ hoặc nghĩa chuyên ngành — `service` ra "cây thanh
 * lương trà", `main` ra "cuộc chọi gà". Bước dựng dữ liệu đã phát hiện được
 * những chỗ đó và gắn cờ; trước đây cờ dừng ở file JSON nên người học không có
 * cách nào biết nghĩa nào chưa được kiểm chứng và cứ thế học thuộc.
 *
 * CHỈ đánh dấu hai nhóm đáng ngờ. Nhóm `confirmed`/`single-source` không hiện gì:
 * gắn huy hiệu "đã đối chứng" lên 2/3 số từ chỉ làm bảng ồn lên mà không đổi
 * được quyết định nào của người học. Cảnh báo chỉ có giá trị khi nó hiếm.
 */

const MARKS: Partial<Record<MeaningConfidence, { label: string; hint: string }>> = {
  'needs-review': {
    label: 'chưa đối chứng',
    hint: 'Nghĩa này lấy từ từ điển nhưng chưa có nguồn thứ hai xác nhận. '
      + 'Từ điển gốc là bản số hoá một cuốn cũ nên đôi khi đưa nghĩa cổ hoặc '
      + 'nghĩa chuyên ngành. Gặp nghĩa trông lạ thì tra lại, và sửa được ngay '
      + 'bằng nút Sửa - sửa xong dấu này tự mất.',
  },
  llm: {
    label: 'máy đề xuất',
    hint: 'Nghĩa này do mô hình ngôn ngữ chạy cục bộ viết đè, vì nghĩa trong từ '
      + 'điển lệch hẳn. Chưa có người xác nhận. Đáng tin hơn nghĩa cổ của từ '
      + 'điển, nhưng vẫn nên tra lại nếu thấy lạ.',
  },
};

export default function MeaningConfidenceMark({
  confidence,
}: {
  confidence: MeaningConfidence | null;
}) {
  const mark = confidence ? MARKS[confidence] : undefined;
  if (!mark) return null;
  return (
    <Tooltip title={mark.hint} enterTouchDelay={0}>
      <Box
        component="span"
        sx={(t) => ({
          ml: 0.75,
          px: 0.75,
          py: 0.125,
          borderRadius: 1,
          fontSize: 11,
          lineHeight: 1.6,
          whiteSpace: 'nowrap',
          verticalAlign: 'middle',
          cursor: 'help',
          color: t.palette.warning.dark,
          bgcolor: alpha(t.palette.warning.main, t.palette.mode === 'dark' ? 0.22 : 0.14),
          border: `1px solid ${alpha(t.palette.warning.main, 0.35)}`,
          ...(t.palette.mode === 'dark' && { color: t.palette.warning.light }),
        })}
      >
        {mark.label}
      </Box>
    </Tooltip>
  );
}
