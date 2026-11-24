"""Luyện phát âm: đọc TỪ (trình duyệt chấm) và đọc CÂU MẪU (máy chủ chấm).

Hai chế độ, một trang, một lịch sử — với người học đó là cùng một việc.
Đọc câu mẫu KHÔNG gọi mô hình ngôn ngữ: câu đã cho sẵn nên không có gì để chấm
về ngữ pháp hay bố cục ý, và bỏ LLM đưa thời gian từ ~106s xuống ~2s.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.pronunciation import (
    AspectOut,
    ItemBestScore,
    PronunciationAttemptCreate,
    PronunciationAttemptRow,
    PronunciationStats,
    ReadAloudHistoryRow,
    ReadAloudResponse,
    WordCheckOut,
)
from app.speaking import read_aloud
from app.speaking.asr.base import AsrUnavailable
from app.speaking.config import speaking_settings
from app.services import pronunciation_service
from app.services.word_set_service import get_owned_item

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}

router = APIRouter()


@router.post("/attempts", response_model=PronunciationAttemptRow,
             status_code=status.HTTP_201_CREATED)
def record(
    data: PronunciationAttemptCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PronunciationAttemptRow:
    """Ghi một lần chấm phát âm. KHÔNG ảnh hưởng mastery hay lịch ôn."""
    attempt = pronunciation_service.record_attempt(db, current_user, data)
    from app.models.item import Item

    item = db.get(Item, attempt.item_id)
    return PronunciationAttemptRow(
        id=attempt.id, item_id=attempt.item_id, word=item.word, meaning=item.meaning,
        score=attempt.score, transcript=attempt.transcript, created_at=attempt.created_at,
    )


@router.get("/stats", response_model=PronunciationStats)
def stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PronunciationStats:
    """Tổng hợp + các lần thử gần nhất."""
    return pronunciation_service.get_stats(db, current_user)


@router.get("/best-scores", response_model=list[ItemBestScore])
def best_scores(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ItemBestScore]:
    """Điểm cao nhất của từng từ đã luyện trong một bộ — cho thống kê đầu trang."""
    return pronunciation_service.best_scores(db, current_user, word_set_id)


@router.post("/read-aloud", response_model=ReadAloudResponse)
async def read_aloud_assess(
    audio: UploadFile = File(..., description="Bản ghi đọc câu mẫu"),
    item_id: int = Form(...),
    language: str | None = Form(default=None),
    save: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReadAloudResponse:
    """Chấm một lần đọc câu mẫu của từ.

    Câu mẫu lấy từ `item.example`. Không có ví dụ thì không tạo được bài — báo
    400 kèm lý do thay vì chấm với câu rỗng.
    """
    item = get_owned_item(db, current_user, item_id)
    if not (item.example or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Từ “{item.word}” chưa có câu ví dụ nên chưa luyện đọc câu được. "
                   "Thêm ví dụ cho từ này rồi thử lại.",
        )

    suffix = os.path.splitext(audio.filename or "")[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng không hỗ trợ ({suffix or 'không rõ'}).",
        )

    payload = await audio.read()
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File audio rỗng"
        )
    size_mb = len(payload) / (1024 * 1024)
    if size_mb > speaking_settings().max_audio_mb:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File {size_mb:.1f}MB vượt giới hạn",
        )

    from app.speaking.pipeline import _default_asr

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(payload)
        tmp.close()
        # Whisper chạy CPU vài giây: phải đẩy ra threadpool. Gọi thẳng trong
        # `async def` là khóa event loop — cả server đứng, mọi người dùng khác
        # (và chính trang này) đều treo theo.
        result = await run_in_threadpool(
            read_aloud.assess_sentence,
            tmp.name, item_id=item.id, word=item.word,
            expected_text=item.example, asr=_default_asr(), language=language,
        )
    except AsrUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dịch vụ nhận dạng giọng nói chưa sẵn sàng: {exc}",
        ) from exc
    finally:
        # Không giữ lại giọng người học trên máy chủ
        try:
            os.unlink(tmp.name)
        except OSError:
            logger.warning("Không xóa được file tạm %s", tmp.name)

    attempt_id = None
    if save:
        attempt_id = pronunciation_service.record_read_aloud(db, current_user, result).id

    return ReadAloudResponse(
        attempt_id=attempt_id,
        item_id=result.item_id, word=result.word,
        expected_text=result.expected_text, transcript=result.transcript,
        accuracy=result.accuracy, clarity=result.clarity,
        overall_level=result.overall_level,
        aspects=[AspectOut(**a.__dict__) for a in result.aspects],
        words=[WordCheckOut(**w) for w in result.words],
        missed_words=result.missed_words, extra_words=result.extra_words,
        audio_metrics=result.audio_metrics, feedback=result.feedback,
        warnings=result.warnings,
    )


@router.get("/items/{item_id}/attempts", response_model=list[ReadAloudHistoryRow])
def item_attempts(
    item_id: int,
    kind: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReadAloudHistoryRow]:
    """Lịch sử luyện của một từ (cả đọc từ lẫn đọc câu).

    Trang luyện đọc từ đây thay vì giữ trong state màn hình — chuyển tab rồi
    quay lại vẫn thấy kết quả vừa chấm.
    """
    get_owned_item(db, current_user, item_id)
    return [
        ReadAloudHistoryRow(
            id=a.id, item_id=a.item_id, word=item.word, kind=a.kind, score=a.score,
            transcript=a.transcript, target_text=a.target_text, detail=a.detail,
            created_at=a.created_at,
        )
        for a, item in pronunciation_service.list_attempts(db, current_user, item_id, kind)
    ]
