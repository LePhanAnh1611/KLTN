# API FastAPI. Migration chạy lúc khởi động (entrypoint) để container mới lên là
# schema đã đúng — không cần bước thủ công khi demo.
FROM python:3.13-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Module luyện nói (app/speaking) cần faster-whisper — kéo theo ctranslate2 +
# onnxruntime (~200MB) nên MẶC ĐỊNH TẮT để image gọn. Bật bằng:
#   docker compose build --build-arg INSTALL_SPEAKING=true backend
# hoặc đặt INSTALL_SPEAKING=true trong .env.
# Không bật thì /api/v1/speaking/assess trả 503 kèm hướng dẫn, phần còn lại của
# app chạy bình thường.
ARG INSTALL_SPEAKING=false
COPY requirements-speaking.txt .
RUN if [ "$INSTALL_SPEAKING" = "true" ]; then \
        pip install --no-cache-dir -r requirements-speaking.txt \
        && apt-get update \
        && apt-get install -y --no-install-recommends ffmpeg \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# Luồng tạo bộ từ từ PDF (UC-87) cần pdfplumber + spaCy + model ngôn ngữ. Cùng
# lý do như trên: MẶC ĐỊNH TẮT. Bật bằng:
#   docker compose build --build-arg INSTALL_PDF_IMPORT=true backend
# Không bật thì /api/v1/word-sets/extract-pdf trả 503 kèm hướng dẫn.
ARG INSTALL_PDF_IMPORT=false
COPY requirements-import.txt .
RUN if [ "$INSTALL_PDF_IMPORT" = "true" ]; then \
        pip install --no-cache-dir -r requirements-import.txt \
        && python -m spacy download en_core_web_sm; \
    fi

COPY alembic.ini .
COPY alembic/ ./alembic/
COPY app/ ./app/
# Wordlist CEFR (UC-87) + dữ liệu seed từ vựng — vài chục KB, luôn có trong image
# vì tra CEFR là nguồn chuẩn của luồng import, không phải phụ thuộc tùy chọn.
COPY data/ ./data/

# Ảnh đại diện người dùng (UC-08) — mount volume lúc chạy để không mất khi rebuild
RUN mkdir -p uploads/avatars

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
