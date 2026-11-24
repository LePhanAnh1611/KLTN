from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    test_database_url: str | None = None

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Nguồn được phép gọi API (ngăn cách bằng dấu phẩy) — khác nhau giữa chạy
    # tay (vite dev :5173) và chạy docker (nginx publish ở cổng khác).
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # service DKT (UC-68) — backend gọi qua HTTP nội bộ
    # 127.0.0.1 chứ không phải localhost: trên Windows "localhost" thử IPv6 (::1)
    # trước rồi mới lùi về IPv4, mỗi lần gọi mất thêm ~2 giây với httpx.
    ml_serve_url: str = "http://127.0.0.1:8001"

    # UC-37 luyện viết: KHÔNG bắt buộc. Không có key thì hệ thống dùng bộ chấm
    # heuristic và nói rõ với người học là ai đang chấm.
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.anthropic.com"
    llm_model: str = "claude-sonnet-5"

    # UC-03/UC-06: gốc URL của frontend để dựng liên kết trong email
    frontend_base_url: str = "http://localhost:5173"

    # UC-62 gửi email. Mặc định 'log' (ghi ra log, không gửi thật) để chạy được
    # trong môi trường khóa luận; đặt 'smtp' + cấu hình bên dưới để gửi thật.
    email_backend: str = "log"
    email_from: str = "no-reply@dktvocab.local"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    # Khi EMAIL_BACKEND=smtp: CHỈ các loại email (cột template) liệt kê ở đây được
    # gửi thật; loại khác (nhắc ôn, thông báo hàng loạt, báo cáo pilot) vẫn chỉ ghi
    # log và hiện trong app — để email không thành biến số mới giữa đợt pilot DKT.
    # Đặt "*" để gửi thật mọi loại.
    email_real_templates: str = "password_reset,email_verify"

    @property
    def email_real_template_set(self) -> set[str]:
        return {t.strip() for t in self.email_real_templates.split(",") if t.strip()}

    # UC-62/UC-63 tác vụ nền (APScheduler). Tắt trong test.
    scheduler_enabled: bool = True
    email_worker_interval_seconds: int = 60
    # Giữ lại cho tương thích cấu hình cũ. Job nhắc nay chạy MỖI GIỜ và lấy
    # giờ nhắc của từng người học (UC-09 + UC-88), không dùng giá trị này nữa.
    reminder_job_hour: int = 8

    # ---- Pilot kiểm chứng DKT trên người dùng thật ----
    # Ngày bắt đầu pilot (YYYY-MM-DD, theo giờ pilot_timezone). Trước ngày này
    # là dữ liệu chạy thử -> không tính. Để trống = tính từ lượt trả lời đầu tiên.
    pilot_start_date: str | None = None
    pilot_timezone: str = "Asia/Ho_Chi_Minh"
    # Email nhận báo cáo hằng tối. Để trống = không gửi (vẫn xem được ở trang Admin).
    pilot_report_email: str | None = None
    pilot_report_hour: int = 21
    # Thư mục ghi báo cáo hằng tối ra file (latest.txt/latest.json + bản theo ngày).
    # Thư mục này được mount ra máy host để tác vụ hẹn giờ của Claude đọc và báo
    # cho người chạy pilot — thay cho email. Để trống = không ghi file.
    pilot_report_dir: str | None = None


settings = Settings()
