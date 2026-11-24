"""UC-39 — hội thoại roleplay với nhân vật AI (ASR + LLM + TTS).

Module luyện nói ĐỘC LẬP với lõi DKT (CLAUDE.md mục 7): không endpoint nào ở
đây đọc/ghi KNOWLEDGE_STATE hay sinh INTERACTION.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.conversation import (
    ConversationDetail,
    ConversationRow,
    ReplyRequest,
    ScenarioDefinition,
    StartConversationRequest,
)
from app.services import conversation_service
from app.speaking.asr.base import AsrUnavailable
from app.speaking.config import speaking_settings

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}


@router.get("/scenarios", response_model=list[ScenarioDefinition])
def list_scenarios(_: User = Depends(get_current_user)) -> list[ScenarioDefinition]:
    """Các tình huống roleplay có sẵn."""
    return conversation_service.list_scenarios()


@router.get("", response_model=list[ConversationRow])
def history(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConversationRow]:
    return conversation_service.history(db, current_user, limit)


@router.post("", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED)
def start(
    data: StartConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """Mở phiên hội thoại. Câu chào cố định nên mở được kể cả khi Ollama chưa chạy."""
    return conversation_service.start(db, current_user, data.scenario)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def detail(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    return conversation_service.get(db, current_user, conversation_id)


@router.post("/{conversation_id}/turns", response_model=ConversationDetail)
def reply_text(
    conversation_id: int,
    data: ReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """Trả lời bằng văn bản. Ollama không chạy được -> 503."""
    return conversation_service.reply(db, current_user, conversation_id, data.text)


@router.post("/{conversation_id}/turns/audio", response_model=ConversationDetail)
async def reply_audio(
    conversation_id: int,
    audio: UploadFile = File(..., description="File ghi âm (wav/mp3/m4a/ogg/webm/flac)"),
    language: str | None = Form(default="en"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    """Trả lời bằng giọng nói: Whisper chép lại rồi đi tiếp đúng luồng văn bản.

    File audio ghi ra thư mục tạm và **xóa ngay** sau khi chép — không lưu lại
    giọng người học, giống UC luyện nói.
    """
    settings = speaking_settings()

    suffix = os.path.splitext(audio.filename or "")[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Định dạng không hỗ trợ ({suffix or 'không rõ'}). "
            f"Chấp nhận: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    payload = await audio.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File audio rỗng")
    size_mb = len(payload) / (1024 * 1024)
    if size_mb > settings.max_audio_mb:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File {size_mb:.1f}MB vượt giới hạn {settings.max_audio_mb:.0f}MB",
        )

    path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(payload)
            path = handle.name

        from app.speaking.asr.whisper_engine import WhisperEngine

        transcript = await run_in_threadpool(
            WhisperEngine().transcribe, path, language=language,
        )
    except AsrUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Chưa nhận dạng được giọng nói: {exc}",
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Chưa cài faster-whisper (pip install -r requirements-speaking.txt)",
        ) from exc
    finally:
        if path and os.path.exists(path):
            os.unlink(path)

    text = (transcript.text or "").strip()
    if not text:
        # Whisper chép ra rỗng gần như luôn là "bản ghi không có tiếng nói"
        # (micro thu nhầm thiết bị / bị tắt tiếng), chứ không phải phòng ồn.
        # Log đủ số liệu để chẩn đoán mà KHÔNG giữ lại audio của người học.
        logger.warning(
            "UC-39 không nghe ra chữ nào: file %.0fKB (%s), %.1fs, "
            "no_speech_prob=%.2f, %d từ",
            len(payload) / 1024, suffix or "?", transcript.duration_sec,
            transcript.no_speech_prob, len(transcript.words),
        )
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Bản ghi không có tiếng nói. Kiểm tra trình duyệt đang thu đúng "
            "micro và micro không bị tắt tiếng, rồi ghi âm lại.",
        )
    # Gọi Groq (tối đa ~90 giây) — cũng không được chạy trên event loop.
    return await run_in_threadpool(
        conversation_service.reply,
        db, current_user, conversation_id, text,
        confidence=getattr(transcript, "confidence", None),
    )


@router.post("/{conversation_id}/end", response_model=ConversationDetail)
def end(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConversationDetail:
    return conversation_service.end(db, current_user, conversation_id)
