"""UC-97 — Shadowing theo phụ đề video YouTube.

Người học: duyệt kho video, thêm video riêng, nhại từng câu và nhận chấm.
Admin (`admin.content`): thêm video vào kho, sửa câu, xuất bản/gỡ.

Chấm dùng lại `read_aloud.assess_sentence` (không gọi LLM, ~2s). Câu gốc do
máy chủ lấy từ DB theo `segment_index` — KHÔNG nhận câu từ client.
"""
import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_current_user, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.shadowing import (
    ShadowingAdminDetail,
    ShadowingAdminRow,
    ShadowingAttemptResult,
    ShadowingStatusUpdate,
    ShadowingTopics,
    ShadowingVideoCard,
    ShadowingVideoDetail,
    ShadowingVideoUpdate,
)
from app.services import shadowing_service
from app.speaking import read_aloud
from app.speaking.asr.base import AsrUnavailable
from app.speaking.config import speaking_settings

logger = logging.getLogger(__name__)

AUDIO_SUFFIXES = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
CAPTION_SUFFIXES = {".srt", ".vtt"}
MAX_CAPTION_BYTES = 2 * 1024 * 1024

router = APIRouter()
admin_router = APIRouter()


async def _read_caption_file(captions: UploadFile | None) -> str | None:
    """File phụ đề tùy chọn → chuỗi. E5: sai đuôi / quá lớn / không phải UTF-8."""
    if captions is None or not captions.filename:
        return None
    suffix = os.path.splitext(captions.filename)[1].lower()
    if suffix not in CAPTION_SUFFIXES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="File phụ đề phải là .srt hoặc .vtt")
    payload = await captions.read()
    if len(payload) > MAX_CAPTION_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, detail="File phụ đề quá lớn (tối đa 2MB)")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="File phụ đề phải lưu dạng UTF-8") from exc


# ------------------------------------------------------------------ Người học

@router.get("/topics", response_model=ShadowingTopics)
def topics(_: User = Depends(get_current_user)) -> ShadowingTopics:
    """Danh sách chủ đề / cấp độ / giấy phép — frontend không tự hardcode."""
    return ShadowingTopics(**shadowing_service.list_topics())


@router.get("/videos", response_model=list[ShadowingVideoCard])
def list_videos(
    topic: str | None = None,
    level: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ShadowingVideoCard]:
    """Kho video đã xuất bản + video riêng của người học, kèm số câu đã đạt."""
    return shadowing_service.list_videos(db, current_user, topic, level)


@router.post("/videos", response_model=ShadowingVideoDetail, status_code=status.HTTP_201_CREATED)
async def add_video(
    url: str = Form(..., max_length=500),
    captions: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShadowingVideoDetail:
    """Người học thêm video của mình. Video đã có trong kho → trả luôn bản trong kho."""
    caption_text = await _read_caption_file(captions)
    video = await run_in_threadpool(
        shadowing_service.add_user_video, db, current_user, url, caption_text
    )
    return shadowing_service.video_detail(db, current_user, video)


@router.get("/videos/{video_id}", response_model=ShadowingVideoDetail)
def get_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShadowingVideoDetail:
    video = shadowing_service.get_visible_video(db, current_user, video_id)
    return shadowing_service.video_detail(db, current_user, video)


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Gỡ video riêng (xóa mềm — lịch sử luyện vẫn giữ)."""
    shadowing_service.delete_user_video(db, current_user, video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/videos/{video_id}/segments/{segment_index}/attempts",
             response_model=ShadowingAttemptResult)
async def attempt(
    video_id: int,
    segment_index: int,
    audio: UploadFile = File(..., description="Bản ghi nhại lại câu"),
    language: str | None = Form(default="en"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ShadowingAttemptResult:
    """Chấm một lần nhại lại câu `segment_index` của video."""
    video = shadowing_service.get_visible_video(db, current_user, video_id)
    segment = shadowing_service.get_segment(video, segment_index)

    suffix = os.path.splitext(audio.filename or "")[1].lower()
    if suffix not in AUDIO_SUFFIXES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail=f"Định dạng không hỗ trợ ({suffix or 'không rõ'}).")
    payload = await audio.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="File audio rỗng")
    size_mb = len(payload) / (1024 * 1024)
    if size_mb > speaking_settings().max_audio_mb:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=f"File {size_mb:.1f}MB vượt giới hạn")

    from app.speaking.pipeline import _default_asr

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(payload)
        tmp.close()
        # Whisper chạy CPU vài giây — đẩy ra threadpool để không khóa event loop
        result = await run_in_threadpool(
            read_aloud.assess_sentence,
            tmp.name, item_id=segment_index, word="",
            expected_text=segment["text"], asr=_default_asr(), language=language,
        )
    except AsrUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"Dịch vụ nhận dạng giọng nói chưa sẵn sàng: {exc}") from exc
    finally:
        # Không giữ lại giọng người học trên máy chủ
        try:
            os.unlink(tmp.name)
        except OSError:
            logger.warning("Không xóa được file tạm %s", tmp.name)

    return shadowing_service.score_attempt(db, current_user, video, segment_index, result)


# ------------------------------------------------------------------ Admin

_content = require_permission("admin.content")


@admin_router.get("/videos", response_model=list[ShadowingAdminRow])
def admin_list(
    status_filter: str | None = None,
    _: User = Depends(_content),
    db: Session = Depends(get_db),
) -> list[ShadowingAdminRow]:
    return shadowing_service.admin_list(db, status_filter)


@admin_router.post("/videos", response_model=ShadowingAdminDetail,
                   status_code=status.HTTP_201_CREATED)
async def admin_create(
    url: str = Form(..., max_length=500),
    topic: str | None = Form(default=None),
    license: str | None = Form(default=None),
    attribution: str | None = Form(default=None, max_length=1000),
    captions: UploadFile | None = File(default=None),
    admin: User = Depends(_content),
    db: Session = Depends(get_db),
) -> ShadowingAdminDetail:
    """Thêm video vào kho dưới dạng NHÁP: lấy phụ đề (hoặc đọc file), cắt câu, tính cấp độ."""
    caption_text = await _read_caption_file(captions)
    return await run_in_threadpool(
        lambda: shadowing_service.admin_create(
            db, admin, url=url, topic=topic or None, license=license or None,
            attribution=attribution, caption_file=caption_text,
        )
    )


@admin_router.get("/videos/{video_id}", response_model=ShadowingAdminDetail)
def admin_get(
    video_id: int,
    _: User = Depends(_content),
    db: Session = Depends(get_db),
) -> ShadowingAdminDetail:
    return shadowing_service.admin_detail(db, video_id)


@admin_router.patch("/videos/{video_id}", response_model=ShadowingAdminDetail)
def admin_update(
    video_id: int,
    data: ShadowingVideoUpdate,
    admin: User = Depends(_content),
    db: Session = Depends(get_db),
) -> ShadowingAdminDetail:
    """Sửa thông tin hoặc danh sách câu (hồ sơ từ vựng tính lại khi sửa câu)."""
    return shadowing_service.admin_update(db, admin, video_id, data)


@admin_router.put("/videos/{video_id}/status", response_model=ShadowingAdminDetail)
def admin_status(
    video_id: int,
    data: ShadowingStatusUpdate,
    admin: User = Depends(_content),
    db: Session = Depends(get_db),
) -> ShadowingAdminDetail:
    """Xuất bản / gỡ xuất bản. E9: thiếu chủ đề, giấy phép hoặc ghi công → 422."""
    return shadowing_service.admin_set_status(db, admin, video_id, data.status)


@admin_router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete(
    video_id: int,
    admin: User = Depends(_content),
    db: Session = Depends(get_db),
) -> Response:
    shadowing_service.admin_delete(db, admin, video_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
