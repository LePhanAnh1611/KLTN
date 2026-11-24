#!/bin/sh
# Chờ Postgres sẵn sàng rồi nâng schema lên head trước khi chạy API.
set -e

echo "[entrypoint] Đang nâng schema (alembic upgrade head)..."
until alembic upgrade head; do
  echo "[entrypoint] DB chưa sẵn sàng, thử lại sau 2s..."
  sleep 2
done

echo "[entrypoint] Schema đã sẵn sàng, khởi động API."
exec "$@"
