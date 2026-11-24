import csv
import io
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.session import StudySession
from app.models.user import User
from app.schemas.item import (
    ImportReport,
    ImportRowError,
    ItemCreateRequest,
    ItemProvenance,
    ItemResponse,
    ItemUpdateRequest,
)
from app.services.word_set_service import get_owned_word_set

CSV_COLUMNS = ["word", "phonetic", "part_of_speech", "meaning", "example"]


def _get_owned_item(db: Session, word_set_id: int, item_id: int) -> Item:
    item = db.execute(
        select(Item).where(Item.id == item_id).with_for_update()
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if item is None or item.deleted_at is not None or item.word_set_id != word_set_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy từ")
    return item


def list_items(db: Session, user: User, word_set_id: int) -> list[ItemResponse]:
    get_owned_word_set(db, user, word_set_id)
    items = (
        db.execute(
            select(Item)
            .where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
            .order_by(Item.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [ItemResponse.model_validate(item) for item in items]


def create_item(
    db: Session, user: User, word_set_id: int, data: ItemCreateRequest,
    provenance: ItemProvenance | None = None,
) -> ItemResponse:
    """Thêm một từ vào bộ.

    `provenance` chỉ do luồng seed nội bộ truyền (xem `ItemProvenance`); router
    công khai gọi không truyền, nên item người học tự tạo để NULL.
    """
    get_owned_word_set(db, user, word_set_id)
    item = Item(
        word_set_id=word_set_id,
        word=data.word,
        phonetic=data.phonetic,
        part_of_speech=data.part_of_speech,
        meaning=data.meaning,
        example=data.example,
        meaning_confidence=provenance.meaning_confidence if provenance else None,
        meaning_source=provenance.meaning_source if provenance else None,
        example_source=provenance.example_source if provenance else None,
        example_vi=provenance.example_vi if provenance else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


def update_item(
    db: Session, user: User, word_set_id: int, item_id: int, data: ItemUpdateRequest
) -> ItemResponse:
    get_owned_word_set(db, user, word_set_id)
    item = _get_owned_item(db, word_set_id, item_id)
    identity_changed = any(
        getattr(item, field) != getattr(data, field)
        for field in ("word", "meaning", "part_of_speech")
    )
    has_learning_data = identity_changed and any(
        db.execute(select(model.item_id).where(model.item_id == item.id).limit(1))
        .scalar_one_or_none() is not None
        for model in (Interaction, KnowledgeState, ReviewSchedule)
    )
    active_session = identity_changed and db.execute(select(StudySession.id).where(
        StudySession.user_id == user.id, StudySession.status == "in_progress",
        or_(StudySession.word_set_id == word_set_id, StudySession.word_set_id.is_(None)),
    ).limit(1)).scalar_one_or_none() is not None
    if has_learning_data or active_session:
        # Q6: historical interactions continue to refer to the original content.
        # The replacement is a new knowledge unit, with no inherited mastery/SRS.
        item.deleted_at = datetime.now(timezone.utc)
        item = Item(word_set_id=word_set_id)
        db.add(item)
    if data.meaning != item.meaning:
        # Người học vừa tự viết lại nghĩa -> cờ độ tin cậy của TỪ ĐIỂN không còn
        # nói về nội dung này nữa. Giữ lại cờ cũ sẽ hiện "chưa kiểm chứng" trên
        # chính chữ họ vừa sửa, hoặc tệ hơn là dán "đã đối chứng" lên nội dung
        # chưa ai đối chứng.
        item.meaning_confidence = None
        item.meaning_source = "user"
    if data.example != item.example:
        item.example_source = None if data.example is None else "user"
        item.example_vi = None   # bản dịch của câu cũ, không còn khớp câu mới
    item.word = data.word
    item.phonetic = data.phonetic
    item.part_of_speech = data.part_of_speech
    item.meaning = data.meaning
    item.example = data.example
    db.commit()
    db.refresh(item)
    return ItemResponse.model_validate(item)


def delete_item(db: Session, user: User, word_set_id: int, item_id: int) -> None:
    get_owned_word_set(db, user, word_set_id)
    item = _get_owned_item(db, word_set_id, item_id)
    item.deleted_at = datetime.now(timezone.utc)  # xóa mềm giữ lịch sử học
    db.commit()


def import_items_csv(
    db: Session, user: User, word_set_id: int, file: UploadFile
) -> ImportReport:
    get_owned_word_set(db, user, word_set_id)

    raw = file.file.read()
    try:
        text = raw.decode("utf-8-sig")  # bỏ BOM nếu có
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File CSV phải mã hóa UTF-8",
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or "word" not in reader.fieldnames or "meaning" not in reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="CSV cần có cột 'word' và 'meaning'",
        )

    errors: list[ImportRowError] = []
    to_add: list[Item] = []
    for index, row in enumerate(reader, start=1):
        word = (row.get("word") or "").strip()
        meaning = (row.get("meaning") or "").strip()
        if not word or not meaning:
            errors.append(ImportRowError(row=index, message="Thiếu 'word' hoặc 'meaning'"))
            continue
        to_add.append(
            Item(
                word_set_id=word_set_id,
                word=word,
                phonetic=(row.get("phonetic") or "").strip() or None,
                part_of_speech=(row.get("part_of_speech") or "").strip() or None,
                meaning=meaning,
                example=(row.get("example") or "").strip() or None,
            )
        )

    db.add_all(to_add)
    db.commit()

    return ImportReport(imported=len(to_add), errors=errors)
