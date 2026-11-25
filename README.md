# LearningHub - Hệ thống học ngoại ngữ cá nhân hóa ứng dụng Deep Knowledge Tracing

Khóa luận tốt nghiệp của Lê Phan Anh - 11236049, web app học từ vựng tiếng Anh cho người Việt, dùng mô hình
Deep Knowledge Tracing (DKT) để ước lượng mức độ nắm vững từng từ của người
học, từ đó **gợi ý từ vừa sức** và **lập lịch ôn tập** thay cho công thức giãn
cách cố định.

> Điểm khác biệt so với Anki/Quizlet: lịch ôn và thứ tự từ do mô hình học sâu suy
> ra từ toàn bộ lịch sử trả lời, không phải từ một công thức tĩnh. SM-2 được cài
> song song làm baseline để so sánh.

---

## 1. Kết quả khoa học (Chương 4)

Ba mô hình Knowledge Tracing huấn luyện trên bộ Duolingo SLAM 2018 (track en_es),
2.593 người học · 386.604 lượt trả lời, đánh giá bằng AUC/Accuracy:

| Mô hình | AUC | Accuracy | Ghi chú |
|---|---|---|---|
| BKT | 0.7228 | 0.8525 | Baseline xác suất cổ điển |
| **DKT** | **0.8088** | **0.8713** | **Tốt nhất — dùng để phục vụ** |
| SAKT | 0.7884 | 0.8643 | Self-attention |

Số liệu đầy đủ: [`ml/models/results.json`](ml/models/results.json).
Bảng + biểu đồ so sánh: [`ml/notebooks/02_results.ipynb`](ml/notebooks/02_results.ipynb).
Khảo sát dữ liệu: [`ml/notebooks/01_eda.ipynb`](ml/notebooks/01_eda.ipynb).

---

## 2. Kiến trúc

```
Trình duyệt ──HTTP──> frontend (React + Vite, nginx)
                          │
                          └──REST /api/v1──> backend (FastAPI)
                                                │
                                   ┌────────────┼────────────┐
                                   ▼            ▼            ▼
                              PostgreSQL   ml-serve      APScheduler
                                           (DKT, :8001)  (nhắc ôn, gửi email)
```

- **backend** theo lớp `api (router) → services (nghiệp vụ) → models (ORM)`.
  Router không chứa business logic.
- **ml-serve** là tiến trình riêng nạp trọng số DKT; backend gọi qua HTTP nội bộ
  và **degrade mềm** — service tắt thì hệ thống quay về cold-start prior chứ
  không chặn luồng học.
- Mọi lần trả lời đều ghi `INTERACTION` — đây là đầu vào của DKT.

| Thư mục | Nội dung |
|---|---|
| `backend/` | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| `frontend/` | React 18 + TypeScript + MUI + React Query |
| `ml/` | PyTorch: tiền xử lý, train BKT/DKT/SAKT, service phục vụ |
| `docs/` | Đặc tả 83 use case, ERD, pipeline, đề cương |

---

## 3. Chạy bằng Docker (khuyến nghị)

```bash
cp .env.example .env          # sửa JWT_SECRET_KEY trước khi chạy thật
docker compose up -d
```

Xong là có:

| Thành phần | Địa chỉ |
|---|---|
| Giao diện | http://localhost:5173 |
| API + Swagger | http://localhost:8000/docs |
| Service DKT | http://localhost:8001 |
| PostgreSQL | localhost:5433 |

Backend tự chạy `alembic upgrade head` lúc khởi động nên không cần bước migration
thủ công.

> **ml-serve** cần trọng số `ml/models/dkt_best.pt` và `ml/data/processed/` (nạp
> qua volume, không nằm trong repo vì dung lượng lớn). Chưa có thì hệ thống vẫn
> chạy bình thường, chỉ là mastery dùng cold-start prior thay vì DKT.

### Tạo dữ liệu mẫu để demo

```bash
docker compose exec backend python -m app.scripts.seed_demo
```

Sinh sẵn 1 quản trị viên + 3 học viên có lịch sử học thật (Interaction → mastery →
lịch ôn → XP/huy hiệu), 4 bộ từ công khai, đánh giá, bài viết cộng đồng và 1 báo
cáo chờ xử lý.

| Tài khoản | Mật khẩu | Vai trò |
|---|---|---|
| `admin@demo.example.com` | `Demo1234` | Quản trị viên |
| `an@demo.example.com` | `Demo1234` | Học viên (nhiều dữ liệu nhất) |
| `binh@demo.example.com` · `chi@demo.example.com` | `Demo1234` | Học viên |

Chạy lại với `--reset` để xóa dữ liệu demo cũ và tạo mới.

---

## 4. Chạy tay khi phát triển

Bốn tiến trình, mỗi cái một terminal (backend/frontend/ml đều có `.venv` riêng,
Python 3.13):

```bash
# 1) Cơ sở dữ liệu
docker compose up -d postgres

# 2) Backend  (http://localhost:8000)
cd backend
alembic upgrade head
uvicorn app.main:app --reload

# 3) Service DKT  (http://localhost:8001)
cd ml
uvicorn serve_app:app --port 8001

# 4) Frontend  (http://localhost:5173)
cd frontend
npm install
npm run dev
```

### Kiểm thử

```bash
cd backend && pytest              # 235 test
cd frontend && npm run build && npm run lint
```

### Huấn luyện lại mô hình

```bash
cd ml
python -m src.preprocess                 # tiền xử lý SLAM en_es
python -m src.bkt  --full                # baseline
python -m src.dkt  --full                # DKT  (mô hình chính)
python -m src.sakt --full                # SAKT
```

`--subset` chạy trên tập nhỏ để thử nhanh. Kết quả ghi vào `ml/models/results.json`.

---

## 5. Tính năng theo nhóm use case

| Nhóm | Use case |
|---|---|
| Tài khoản & hồ sơ | UC-01, 02, 04, 05, 08 |
| Bộ từ & nội dung | UC-13, 14, 15, 16, 17 |
| Học & ghi nhận | UC-25 flashcard, UC-26 quiz, UC-30, UC-31 |
| **Lõi AI** | **UC-64 mastery (DKT), UC-65 gợi ý vừa sức, UC-66 lịch ôn, UC-67 huấn luyện, UC-68 phục vụ, UC-69 cold-start** |
| Ôn tập | UC-27 học thông minh, UC-33 SRS, UC-34 SM-2 (baseline), UC-36 lịch tuần |
| Tiến độ & gamification | UC-40, 41, 42, 43, 46, 47, 48 |
| Khám phá & chia sẻ | UC-19, 20, 21, 22, 23, 24 |
| Cộng đồng | UC-49, 50, 51, 52, 53, 54, 55 |
| Thông báo & email | UC-58, 59, 60, 61, 62, 63 |
| Quản trị | UC-72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83 |

Đặc tả chi tiết từng use case ở [`docs/`](docs/).

### Quy tắc nghiệp vụ then chốt

- **BR-01** — "đã thuộc" khi mastery ≥ 0.9 (ngưỡng chỉnh được ở UC-81).
- **BR-02** — vào hàng đợi ôn khi P(nhớ) < θ_review (mặc định 0.6).
- **BR-03** — chỉ gợi ý từ mới có P(đúng) dự đoán trong khoảng [0.6, 0.8].
- **BR-05** — mọi lần trả lời đều ghi `INTERACTION` (đầu vào của DKT).
- **Q1** — tải bộ từ công khai là **sao chép (snapshot)**, giữ `origin_set_id`.
- **Q6** — xóa bộ từ/bài viết đang được dùng là **xóa mềm**, giữ toàn vẹn lịch sử.

Toàn bộ ngưỡng vận hành nằm trong bảng `system_configs`, sửa được ở màn Quản trị
→ Cấu hình (UC-81); phân quyền theo từng quyền cụ thể ở màn Phân quyền (UC-74).
