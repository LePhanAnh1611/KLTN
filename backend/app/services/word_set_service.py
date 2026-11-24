import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.pdf_import import WordSetFromPdfRequest
from app.schemas.word_set import (
    PublishRequest,
    WordSetCreateRequest,
    WordSetResponse,
    WordSetUpdateRequest,
)
from app.services import config_service, tag_service
from app.services.mastery_service import mastered_condition

# UC-13 — ảnh bìa bộ từ. Giữ cùng khuôn với ảnh đại diện (user_service) nhưng
# trần dung lượng rộng hơn vì bìa là ảnh ngang, không phải avatar vuông nhỏ.
COVER_UPLOAD_DIR = Path("uploads/word_set_covers")
COVER_URL_PREFIX = "/uploads/word_set_covers/"
MAX_COVER_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ALLOWED_COVER_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def get_owned_word_set(db: Session, user: User, word_set_id: int) -> WordSet:
    """Lấy bộ từ thuộc sở hữu user và chưa xóa mềm; 404 nếu không tìm thấy/không phải của mình."""
    word_set = db.get(WordSet, word_set_id)
    if word_set is None or word_set.deleted_at is not None or word_set.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy bộ từ vựng")
    return word_set


def get_public_word_set(db: Session, word_set_id: int) -> WordSet:
    """Lấy bộ từ công khai còn khả dụng; 404 nếu ẩn/đã xóa (UC-20/23/24)."""
    word_set = db.get(WordSet, word_set_id)
    if word_set is None or word_set.deleted_at is not None or not word_set.is_public:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bộ từ vựng không còn khả dụng"
        )
    return word_set


def _count_items(db: Session, word_set_id: int) -> int:
    return db.execute(
        select(func.count())
        .select_from(Item)
        .where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalar_one()


def _count_mastered(db: Session, word_set_id: int, user_id: int) -> int:
    """UC-16: số từ "đã thuộc" (mastery >= ngưỡng BR-01) của user trong bộ."""
    return db.execute(
        select(func.count())
        .select_from(KnowledgeState)
        .join(Item, Item.id == KnowledgeState.item_id)
        .where(
            Item.word_set_id == word_set_id,
            Item.deleted_at.is_(None),
            KnowledgeState.user_id == user_id,
            mastered_condition(),
        )
    ).scalar_one()


def _count_started(db: Session, word_set_id: int, user_id: int) -> int:
    """Số từ người học đã gặp ít nhất một lần (đã có KNOWLEDGE_STATE), gồm cả từ đã thuộc."""
    return db.execute(
        select(func.count())
        .select_from(KnowledgeState)
        .join(Item, Item.id == KnowledgeState.item_id)
        .where(
            Item.word_set_id == word_set_id,
            Item.deleted_at.is_(None),
            KnowledgeState.user_id == user_id,
        )
    ).scalar_one()


def _to_response(db: Session, word_set: WordSet, user_id: int) -> WordSetResponse:
    response = WordSetResponse.model_validate(word_set)
    response.item_count = _count_items(db, word_set.id)
    response.mastered_count = _count_mastered(db, word_set.id, user_id)
    # Thanh tiến độ 3 nấc: thuộc / đang học / chưa học. Chỉ đếm "đã thuộc" thì
    # người học vừa học 20 từ vẫn thấy 0% vì BR-01 cần mastery >= 0.9 và đủ lượt đúng.
    response.learning_count = max(
        _count_started(db, word_set.id, user_id) - response.mastered_count, 0
    )
    response.tags = tag_service.tags_of(db, word_set.id)      # UC-96
    return response


def create_word_set(db: Session, user: User, data: WordSetCreateRequest) -> WordSetResponse:
    word_set = WordSet(
        owner_id=user.id,
        name=data.name,
        description=data.description,
        category=data.category,
        difficulty=data.difficulty,
        cefr_level=data.cefr_level,
        cover_image_url=data.cover_image_url,
    )
    db.add(word_set)
    db.flush()
    tag_service.set_tags(db, word_set.id, data.tags)          # UC-96
    db.commit()
    db.refresh(word_set)
    return _to_response(db, word_set, user.id)


def create_word_set_from_pdf(
    db: Session, user: User, data: WordSetFromPdfRequest
) -> WordSetResponse:
    """UC-87 bước 2 — ghi bộ từ người học đã duyệt vào thư viện.

    Chỉ đến đây mới chạm DB (BR-PDF-01): bước trích chỉ trả danh sách ứng viên.
    Khử trùng lặp theo mặt chữ vì cùng một lemma có thể được người học sửa thành
    hai dòng giống nhau khi duyệt bảng.
    """
    seen: set[str] = set()
    items: list[Item] = []
    for selection in data.words:
        word = selection.word.strip()
        key = word.lower()
        if not word or key in seen:
            continue
        seen.add(key)
        items.append(
            Item(
                word=word,
                part_of_speech=(selection.part_of_speech or "").strip() or None,
                # BR-PDF-06: hệ thống không tự dịch; để trống thì người học bổ sung ở UC-14
                meaning=selection.meaning.strip(),
                example=(selection.example or "").strip() or None,
            )
        )

    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chưa chọn từ nào để tạo bộ từ vựng",
        )

    word_set = WordSet(
        owner_id=user.id,
        name=data.name,
        description=data.description,
        category=data.category,
        difficulty=data.difficulty,
        cefr_level=data.cefr_level,
        cover_image_url=data.cover_image_url,
        source="pdf",                      # BR-PDF-05 — truy nguyên nguồn gốc
        source_filename=data.source_filename,
    )
    db.add(word_set)
    db.flush()                             # cần id để gắn item, chưa commit

    for item in items:
        item.word_set_id = word_set.id
    db.add_all(items)
    db.commit()
    db.refresh(word_set)
    return _to_response(db, word_set, user.id)


def list_word_sets(db: Session, user: User) -> list[WordSetResponse]:
    word_sets = (
        db.execute(
            select(WordSet)
            .where(WordSet.owner_id == user.id, WordSet.deleted_at.is_(None))
            .order_by(WordSet.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_to_response(db, ws, user.id) for ws in word_sets]


def get_word_set(db: Session, user: User, word_set_id: int) -> WordSetResponse:
    word_set = get_owned_word_set(db, user, word_set_id)
    return _to_response(db, word_set, user.id)


def update_word_set(
    db: Session, user: User, word_set_id: int, data: WordSetUpdateRequest
) -> WordSetResponse:
    word_set = get_owned_word_set(db, user, word_set_id)
    word_set.name = data.name
    word_set.description = data.description
    word_set.category = data.category
    word_set.difficulty = data.difficulty
    word_set.cefr_level = data.cefr_level
    # Chỉ đụng tới bìa khi client gửi hẳn trường này. Form sửa bộ từ không gửi
    # `cover_image_url`, mà Pydantic mặc định None — gán thẳng là mỗi lần đổi tên
    # bộ lại xoá mất ảnh vừa tải lên.
    if "cover_image_url" in data.model_fields_set:
        word_set.cover_image_url = data.cover_image_url
    tag_service.set_tags(db, word_set.id, data.tags)          # UC-96
    db.commit()
    db.refresh(word_set)
    return _to_response(db, word_set, user.id)


def _remove_cover_file(url: str | None) -> None:
    """Xoá file bìa cũ, và CHỈ file nằm trong thư mục bìa của hệ thống.

    `cover_image_url` là chuỗi client đặt được qua PATCH (kể cả '../../..' hay
    một URL ngoài), nên không được unlink thẳng theo giá trị đó. Lấy mỗi phần
    tên file rồi ghép lại vào thư mục bìa là đường dẫn không thể thoát ra ngoài.
    """
    if not url or not url.startswith(COVER_URL_PREFIX):
        return
    path = COVER_UPLOAD_DIR / Path(url).name
    if path.is_file():
        path.unlink(missing_ok=True)


def update_cover(
    db: Session, user: User, word_set_id: int, file: UploadFile
) -> WordSetResponse:
    """UC-13 — đặt ảnh bìa cho bộ từ mình sở hữu."""
    word_set = get_owned_word_set(db, user, word_set_id)

    extension = ALLOWED_COVER_CONTENT_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Định dạng ảnh không hỗ trợ (chỉ nhận jpg/png/webp)",
        )

    contents = file.file.read()
    if len(contents) > MAX_COVER_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Ảnh vượt quá dung lượng cho phép (tối đa 5MB)",
        )
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File ảnh rỗng",
        )

    COVER_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{word_set.id}_{uuid.uuid4().hex}{extension}"
    (COVER_UPLOAD_DIR / filename).write_bytes(contents)

    old_url = word_set.cover_image_url
    word_set.cover_image_url = f"{COVER_URL_PREFIX}{filename}"
    db.commit()
    db.refresh(word_set)

    _remove_cover_file(old_url)      # dọn file cũ SAU khi đã ghi DB thành công
    return _to_response(db, word_set, user.id)


def delete_cover(db: Session, user: User, word_set_id: int) -> WordSetResponse:
    """UC-13 — gỡ ảnh bìa, thẻ quay về bìa sinh tự động ở frontend."""
    word_set = get_owned_word_set(db, user, word_set_id)
    old_url = word_set.cover_image_url
    word_set.cover_image_url = None
    db.commit()
    db.refresh(word_set)

    _remove_cover_file(old_url)
    return _to_response(db, word_set, user.id)


def delete_word_set(db: Session, user: User, word_set_id: int) -> None:
    word_set = get_owned_word_set(db, user, word_set_id)
    word_set.deleted_at = datetime.now(timezone.utc)  # xóa mềm (Q6) giữ toàn vẹn INTERACTION
    db.commit()


def set_publish(
    db: Session, user: User, word_set_id: int, data: PublishRequest
) -> WordSetResponse:
    word_set = get_owned_word_set(db, user, word_set_id)

    if data.is_public:
        min_items = config_service.get_int("min_items_to_publish")  # UC-81
        if _count_items(db, word_set.id) < min_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bộ từ vựng cần tối thiểu {min_items} từ để công khai",
            )
        if not word_set.category or not word_set.difficulty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bộ từ vựng cần có danh mục và độ khó để công khai",
            )

    word_set.is_public = data.is_public
    db.commit()
    db.refresh(word_set)
    return _to_response(db, word_set, user.id)


def get_owned_item(db: Session, user: User, item_id: int) -> Item:
    """Item thuộc thư viện của chính người học (Q2 — mastery gắn theo bản sao).

    Dùng chung cho các tính năng thao tác trên MỘT từ (đánh dấu từ khó UC-32,
    lưu kết quả phát âm) thay vì mỗi service tự viết lại một truy vấn giống nhau.
    """
    row = db.execute(
        select(Item)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            Item.id == item_id,
            Item.deleted_at.is_(None),
            WordSet.owner_id == user.id,
            WordSet.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy từ trong thư viện của bạn",
        )
    return row
