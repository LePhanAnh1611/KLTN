from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.config import settings
from app.core.scheduler import shutdown_scheduler, start_scheduler


def _warm_up_whisper() -> None:
    """Nạp sẵn Whisper ở luồng nền khi khởi động (nếu có cài module luyện nói).

    Không làm vậy thì người ĐẦU TIÊN bấm "Chấm" sau mỗi lần dựng lại phải chờ
    tải model (~145MB) + nạp vào RAM ngay trong request — nhìn như treo.
    Lỗi ở đây chỉ ghi log; request thật sẽ thử nạp lại và báo lỗi rõ ràng.
    """
    import importlib.util
    import logging
    import threading

    if importlib.util.find_spec("faster_whisper") is None:
        return

    def _load() -> None:
        try:
            from app.speaking.asr.whisper_engine import _load_model

            _load_model()
            logging.getLogger(__name__).info("Whisper đã nạp sẵn")
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning("Nạp sẵn Whisper thất bại: %s", exc)

    threading.Thread(target=_load, name="whisper-warmup", daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bật tác vụ nền UC-62 (đẩy hàng đợi email) + UC-63 (nhắc ôn)."""
    start_scheduler()
    _warm_up_whisper()
    yield
    shutdown_scheduler()


app = FastAPI(title="LearningHub API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path("uploads/avatars").mkdir(parents=True, exist_ok=True)
Path("uploads/word_set_covers").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(health.router, tags=["health"])
app.include_router(api_router, prefix="/api/v1")
