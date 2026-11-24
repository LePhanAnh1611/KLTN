"""API luyện nói: nhận audio + đề bài, trả JSON chấm theo rubric.

Module độc lập với DKT: endpoint này không đọc/ghi KNOWLEDGE_STATE và không sinh
INTERACTION, nên điểm nói KHÔNG ảnh hưởng tới lộ trình học. Nối vào sau chỉ cần
thêm một adapter đọc `SpeakingAssessmentResponse`.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.speaking import (
    AudioMetrics,
    CriterionResult,
    SpeakingAppealCreate,
    SpeakingAppealRow,
    SpeakingAssessmentResponse,
    SpeakingAttemptRow,
    SpeakingHealth,
    SpeakingHistoryResponse,
    SpeakingScores,
)
from app.services import speaking_history_service
from app.speaking import pipeline
from app.speaking.asr.base import AsrUnavailable
from app.speaking.config import speaking_settings
from app.speaking.rubric import load_rubric
from app.speaking.rubric.thresholds import is_calibrated
from app.speaking.scoring import ollama_client
from app.speaking.types import SpeakingAssessment

logger = logging.getLogger(__name__)

router = APIRouter()

# Whisper đọc được nhiều định dạng, nhưng chặn sớm ở đây cho thông báo lỗi rõ ràng
ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}


def _to_response(
    result: SpeakingAssessment, rubric_version: str, attempt_id: int | None = None,
) -> SpeakingAssessmentResponse:
    return SpeakingAssessmentResponse(
        attempt_id=attempt_id,
        transcript=result.transcript,
        audio_metrics=AudioMetrics(**result.audio_metrics),
        scores=SpeakingScores(**{
            key: CriterionResult(
                level=score.level, label=score.label, evidence=score.evidence,
                suggestion=score.suggestion, scored_by=score.scored_by, reason=score.reason,
            )
            for key, score in result.scores.items()
        }),
        overall_level=result.overall_level,
        developmental_feedback=result.developmental_feedback,
        warnings=result.warnings,
        rubric_version=rubric_version,
    )


@router.post("/assess", response_model=SpeakingAssessmentResponse)
async def assess_speaking(
    audio: UploadFile = File(..., description="File ghi âm (wav/mp3/m4a/ogg/webm/flac)"),
    task_prompt: str = Form(..., min_length=1, max_length=1000),
    language: str | None = Form(default=None),
    weights: str | None = Form(
        default=None,
        description='JSON trọng số tùy chọn, VD {"coherence_task": 2}',
    ),
    save: bool = Form(default=True, description="Lưu vào lịch sử luyện nói"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakingAssessmentResponse:
    """Chấm một bài nói theo rubric 4 tiêu chí × 4 mức.

    Toàn bộ suy luận chạy cục bộ (faster-whisper + Ollama). File audio được ghi
    ra thư mục tạm rồi XÓA ngay sau khi chấm — không lưu lại giọng người học.
    """
    settings = speaking_settings()

    suffix = os.path.splitext(audio.filename or "")[1].lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Định dạng không hỗ trợ ({suffix or 'không rõ'}). "
                   f"Chấp nhận: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    payload = await audio.read()
    size_mb = len(payload) / (1024 * 1024)
    if size_mb > settings.max_audio_mb:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File {size_mb:.1f}MB vượt giới hạn {settings.max_audio_mb:.0f}MB",
        )
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File audio rỗng"
        )

    parsed_weights: dict[str, float] | None = None
    if weights:
        try:
            raw = json.loads(weights)
            if not isinstance(raw, dict):
                raise ValueError("weights phải là JSON object")
            parsed_weights = {str(k): float(v) for k, v in raw.items()}
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Trọng số không hợp lệ: {exc}",
            ) from exc

    # delete=False + xóa tay: trên Windows không mở lại được file đang giữ handle,
    # mà Whisper cần mở nó bằng đường dẫn.
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(payload)
        tmp.close()

        # Whisper + gọi LLM: chạy ngoài event loop (xem pronunciation.read_aloud_assess)
        result = await run_in_threadpool(
            pipeline.assess,
            tmp.name, task_prompt, language=language, weights=parsed_weights,
        )
    except AsrUnavailable as exc:
        # Không có transcript thì không có gì để chấm — báo lỗi thay vì bịa điểm
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Dịch vụ nhận dạng giọng nói chưa sẵn sàng: {exc}",
        ) from exc
    except (FileNotFoundError, ValueError) as exc:
        # Thiếu/hỏng file rubric là lỗi cấu hình máy chủ. Trả nguyên lý do thay
        # vì để 500 — người dùng chỉ thấy "không chấm được" mà không biết vì sao.
        logger.error("Không nạp được rubric: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Chưa nạp được rubric chấm điểm: {exc}",
        ) from exc
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            logger.warning("Không xóa được file tạm %s", tmp.name)

    rubric_version = load_rubric().version

    attempt_id = None
    if save:
        # Lưu KẾT QUẢ, không lưu audio — cam kết privacy của module giữ nguyên
        attempt_id = speaking_history_service.save_attempt(
            db, current_user, result, task_prompt, rubric_version,
        ).id

    return _to_response(result, rubric_version, attempt_id)


@router.get("/attempts", response_model=SpeakingHistoryResponse)
def list_attempts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakingHistoryResponse:
    """Lịch sử luyện nói + đường tiến bộ (chỉ trong cùng một phiên bản rubric)."""
    return speaking_history_service.list_history(
        db, current_user, page=page, page_size=page_size,
    )


@router.get("/attempts/{attempt_id}", response_model=SpeakingAttemptRow)
def get_attempt(
    attempt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakingAttemptRow:
    """Xem lại một lần chấm."""
    return speaking_history_service.get_attempt(db, current_user, attempt_id)


@router.post(
    "/attempts/{attempt_id}/appeals",
    response_model=SpeakingAppealRow,
    status_code=status.HTTP_201_CREATED,
)
def create_appeal(
    attempt_id: int,
    data: SpeakingAppealCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpeakingAppealRow:
    """Rubric mục 9 — báo kết quả chấm chưa đúng.

    KHÔNG sửa điểm; đây là dữ liệu để người làm rubric xem lại descriptor
    (mục 8 bước 4). E1 không phải bài của mình -> 404, E2 đã gửi rồi -> 409.
    """
    return speaking_history_service.create_appeal(db, current_user, attempt_id, data)


@router.get("/health", response_model=SpeakingHealth)
def speaking_health(_: User = Depends(get_current_user)) -> SpeakingHealth:
    """Kiểm tra Whisper (local) & LLM (Groq) đã sẵn sàng chưa — khi dựng môi trường."""
    settings = speaking_settings()

    try:
        import faster_whisper  # noqa: F401

        asr_ready, asr_detail = True, f"faster-whisper, model={settings.whisper_model}"
    except ImportError:
        asr_ready = False
        asr_detail = "Chưa cài faster-whisper (pip install -r requirements-speaking.txt)"

    # LLM nay là Groq Cloud, không còn Ollama local: "sẵn sàng" nghĩa là có key
    # VÀ key đó gọi được đúng model đang cấu hình. Thứ tự nhánh đi từ nguyên nhân
    # gần nhất (chưa đặt key) ra xa dần, để người dựng môi trường sửa đúng chỗ.
    models = ollama_client.installed_models()
    llm_ready = bool(settings.groq_api_key) and settings.groq_model in models
    if not settings.groq_api_key:
        llm_detail = "Chưa cấu hình GROQ_API_KEY - đặt key trong .env để bật chấm C3/C4"
    elif not models:
        llm_detail = f"Không kết nối được Groq tại {settings.groq_base_url}"
    elif not llm_ready:
        llm_detail = (
            f"Key hiện tại không dùng được model {settings.groq_model} "
            f"- đổi GROQ_MODEL sang một model Groq đang phục vụ"
        )
    else:
        llm_detail = "Sẵn sàng"

    # Health check mà tự sập thì vô dụng — báo cáo lỗi nạp rubric thay vì 500
    try:
        rubric = load_rubric()
        rubric_ready, rubric_detail = True, f"v{rubric.version}"
        rubric_version = rubric.version
    except (FileNotFoundError, ValueError) as exc:
        rubric_ready, rubric_detail, rubric_version = False, str(exc), ""

    return SpeakingHealth(
        asr_ready=asr_ready, asr_detail=asr_detail,
        llm_ready=llm_ready, llm_detail=llm_detail,
        # Tên trường giữ nguyên cho tương thích hợp đồng API; giá trị là model LLM thật.
        ollama_model=settings.groq_model, installed_models=models,
        rubric_ready=rubric_ready, rubric_detail=rubric_detail,
        rubric_version=rubric_version, rubric_calibrated=is_calibrated(),
    )
