# Kế hoạch ôn hằng ngày

`review_daily_limit` trong Cấu hình hệ thống giới hạn số từ ôn theo lịch mỗi
ngày (mặc định 30). `review_seconds_per_word` dùng để ước tính thời gian
(mặc định 16 giây/từ, tương đương 8 phút cho 30 từ).

`GET /reviews/calendar` và `GET /reviews/due` dùng cùng một kế hoạch:

- Mỗi ngày tính theo múi giờ của tài khoản.
- Từ đến hạn ưu tiên xác suất trả lời đúng thấp nhất do DKT dự đoán. Khi mô
  hình không có tín hiệu, dùng mastery đã lưu, rồi mới đến prior theo độ khó.
- Mỗi từ đã trả lời trong phiên SRS hôm nay chiếm một suất, kể cả trả lời sai.
  Mở lại trang hay bắt đầu phiên khác không cấp thêm toàn bộ hạn mức.
- Tồn đọng và lịch tương lai được đưa vào ngày còn chỗ, không trước ngày đến
  hạn. `scheduled_for` là ngày dự kiến trong kế hoạch; `next_review_at` vẫn là
  ngày đến hạn do thuật toán half-life/SM-2 tạo. Không sửa ngày đến hạn để che
  tồn đọng. Kế hoạch tính lại theo tình hình học và cấu hình hiện tại.
- `backlog_count` đếm từ đến hạn chưa được xếp vào hôm nay, kể cả phần ngoài
  tuần đang hiển thị. Nhãn đỏ cần tín hiệu DKT/mastery dưới ngưỡng điểm yếu;
  không dùng số ngày quá hạn hoặc cold-start prior đơn thuần.

`POST /reviews/pause-lower-level` tạm ngưng các lịch ôn của người gọi có mức
CEFR của bộ từ thấp hơn mức đầu vào. Không xóa bộ từ, mastery hay lịch sử;
không suy đoán mức cho bộ chưa có CEFR. Các từ này cũng được loại khỏi ôn điểm
yếu và truy vấn nhắc ôn. Khi người học chủ động học lại từ trong bộ từ, lần
trả lời tạo lịch mới và bỏ trạng thái tạm ngưng.

Migration: `python -m alembic upgrade head` thêm `review_schedules.is_paused`.
Frontend mặc định xem hôm nay, gom theo bộ từ, thu gọn và phân trang từng bộ.
