interface MascotProps {
  size?: number;
  /** Tâm trạng — đổi mắt và mỏ, phần thân giữ nguyên. */
  mood?: 'vui' | 'nghi' | 'ngu' | 'mung';
  /** Màu thân. Để trống thì dùng xanh mặc định. */
  tone?: string;
}

/**
 * VẸT — linh vật của LearningHub.
 *
 * Vì sao là vẹt: con vật gắn với việc "nhắc lại lời người khác", tức là đúng
 * việc người học đang làm khi luyện phát âm và đọc câu mẫu.
 *
 * Vì sao vẽ kiểu này: toàn bộ hình ghép từ đa giác cạnh thẳng, tô màu ĐẶC, không
 * gradient, không bo góc, không đổ bóng mờ. Vẽ tròn trịa mềm mại sẽ chỏi với hệ
 * góc vuông của giao diện, và đó chính là kiểu hình minh họa bị dùng đến mòn.
 *
 * Chỉ 4 màu phẳng: thân, cánh (thân tối hơn), mỏ, mắt.
 */
function Mascot({ size = 96, mood = 'vui', tone = '#1CB0F6' }: MascotProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="Vẹt - linh vật LearningHub"
      shapeRendering="crispEdges"
    >
      {/* cành đậu */}
      <rect x="8" y="54" width="48" height="4" fill="#1B2430" />

      {/* chân */}
      <rect x="26" y="48" width="3" height="6" fill="#1B2430" />
      <rect x="35" y="48" width="3" height="6" fill="#1B2430" />

      {/* đuôi — ba dải lệch nhau, dải giữa dài nhất */}
      <polygon points="44,30 58,22 58,28 46,36" fill={tone} opacity="0.55" />
      <polygon points="44,34 60,32 58,38 45,39" fill={tone} opacity="0.75" />

      {/* thân */}
      <polygon points="18,20 40,16 46,34 40,48 24,48 16,34" fill={tone} />

      {/* cánh — cùng màu thân, tối hơn bằng lớp phủ đen phẳng */}
      <polygon points="24,26 40,24 38,42 26,40" fill="#000000" opacity="0.22" />

      {/* mào — ba gai nhọn */}
      <polygon points="22,20 25,10 28,19" fill={tone} />
      <polygon points="28,19 32,8 36,18" fill={tone} />

      {/* mỏ */}
      {mood === 'mung' ? (
        <polygon points="16,28 6,32 16,37 18,32" fill="#F59E0B" />
      ) : (
        <polygon points="16,28 8,33 16,36" fill="#F59E0B" />
      )}

      {/* mắt */}
      {mood === 'ngu' ? (
        <rect x="21" y="27" width="7" height="2" fill="#1B2430" />
      ) : mood === 'nghi' ? (
        <>
          <rect x="21" y="24" width="7" height="7" fill="#FFFFFF" />
          <rect x="25" y="27" width="3" height="3" fill="#1B2430" />
        </>
      ) : (
        <>
          <rect x="21" y="24" width="7" height="7" fill="#FFFFFF" />
          <rect x="23" y="26" width="3" height="3" fill="#1B2430" />
        </>
      )}

      {/* dấu hỏi khi đang nghĩ */}
      {mood === 'nghi' && (
        <>
          <rect x="46" y="8" width="8" height="3" fill="#1B2430" />
          <rect x="51" y="11" width="3" height="4" fill="#1B2430" />
          <rect x="48" y="15" width="6" height="3" fill="#1B2430" />
          <rect x="48" y="18" width="3" height="3" fill="#1B2430" />
          <rect x="48" y="24" width="3" height="3" fill="#1B2430" />
        </>
      )}

      {/* tia mừng */}
      {mood === 'mung' && (
        <>
          <rect x="48" y="12" width="9" height="3" fill="#F59E0B" />
          <rect x="47" y="4" width="3" height="8" fill="#F59E0B" />
          <rect x="54" y="18" width="6" height="3" fill="#F59E0B" />
        </>
      )}
    </svg>
  );
}

export default Mascot;
