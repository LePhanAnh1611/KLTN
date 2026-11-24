import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';

interface StudyPromptProps {
  children: ReactNode;
  /** Bỏ khung thẻ — dùng khi bên trong đã có thẻ riêng, hoặc chỉ có vòng quay. */
  bare?: boolean;
  maxWidth?: number;
  /**
   * Lối thoát ở chân khung.
   *
   * Chỉ truyền khi màn đó CHƯA có nút nào dẫn ngược ra. Màn "bộ rỗng" hay
   * "tổng kết" đã lấy chính nút quay lại làm hành động chính rồi, thêm nữa
   * thành hai đường về giống hệt nhau nằm cạnh nhau.
   */
  back?: { to: string; label?: string };
}

/**
 * Khung cho các trạng thái TẠM của phiên học toàn màn hình: đang tải, lỗi,
 * chưa có từ, hỏi tiếp tục phiên dở, tổng kết.
 *
 * Vì sao cần: hai màn học không có thanh điều hướng, nên khi chỉ còn một câu
 * hỏi ngắn thì câu đó nằm chỏng chơ ở mép trên một trang trống cao 900px. Trước
 * đây mỗi trạng thái tự viết `<Box p={4} maxWidth mx="auto">` — căn giữa được
 * chiều ngang nhưng bỏ quên chiều dọc.
 *
 * `m: 'auto'` trên một flex item chứ không phải `placeItems: 'center'`: khi nội
 * dung CAO HƠN màn hình, `placeItems: center` đẩy phần đầu tràn lên trên và cắt
 * mất, còn `margin: auto` chỉ chia phần dư khi thực sự có phần dư. Bảng tổng kết
 * phiên có lúc dài hơn một màn, nên khác biệt này là thật.
 */
function StudyPrompt({ children, bare, maxWidth = 460, back }: StudyPromptProps) {
  const inner = { m: 'auto', width: '100%', maxWidth };

  const exit = back && (
    <Button
      component={RouterLink}
      to={back.to}
      size="small"
      sx={{ color: 'text.secondary' }}
    >
      ← {back.label ?? 'Quay lại'}
    </Button>
  );

  if (bare) {
    return (
      <Box sx={{ minHeight: '100vh', display: 'flex', p: { xs: 2, sm: 3 } }}>
        <Box sx={inner}>
          {children}
          {exit && <Box sx={{ mt: 3, textAlign: 'center' }}>{exit}</Box>}
        </Box>
      </Box>
    );
  }

  return (
    <Box sx={{ minHeight: '100vh', display: 'flex', p: { xs: 2, sm: 3 } }}>
      <Card sx={{ ...inner, p: { xs: 3, sm: 4 }, textAlign: 'center' }}>
        {children}
        {exit && (
          // Ngăn bằng đường kẻ: lối thoát không phải một lựa chọn ngang hàng với
          // hành động chính, nó là đường lui khi không muốn làm gì ở đây cả.
          <Box sx={{ mt: 3, pt: 2, borderTop: '2px solid', borderColor: 'divider' }}>
            {exit}
          </Box>
        )}
      </Card>
    </Box>
  );
}

export default StudyPrompt;
