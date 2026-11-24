"""UC-32 — người học tự đánh dấu từ khó.

Khác "điểm yếu" (UC-40/86) do DKT suy ra từ mastery: đây là đánh giá chủ quan.
Giữ riêng hai nguồn vì chúng không thay thế nhau — một từ mastery 0.9 vẫn có thể
khiến người học thấy khó nhớ, và đó là thông tin đáng giữ.

Cờ này KHÔNG ảnh hưởng tới mastery hay lịch ôn: nó chỉ là bộ lọc để người học
tìm lại nhanh những từ mình quan tâm.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.item_flag import ItemFlag
from app.models.knowledge_state import KnowledgeState
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.item_flag import FlaggedItem, FlagRequest
from app.services.word_set_service import get_owned_item


def set_flag(db: Session, user: User, item_id: int, data: FlagRequest) -> ItemFlag:
    """Đánh dấu, hoặc cập nhật ghi chú nếu đã đánh dấu trước đó (idempotent)."""
    get_owned_item(db, user, item_id)

    flag = db.execute(
        select(ItemFlag).where(ItemFlag.user_id == user.id, ItemFlag.item_id == item_id)
    ).scalar_one_or_none()

    if flag is None:
        flag = ItemFlag(user_id=user.id, item_id=item_id, note=data.note)
        db.add(flag)
    else:
        flag.note = data.note

    db.commit()
    db.refresh(flag)
    return flag


def clear_flag(db: Session, user: User, item_id: int) -> None:
    """Bỏ đánh dấu. Chưa đánh dấu thì coi như xong — không báo lỗi cho một thao
    tác vốn không có gì để làm."""
    flag = db.execute(
        select(ItemFlag).where(ItemFlag.user_id == user.id, ItemFlag.item_id == item_id)
    ).scalar_one_or_none()
    if flag is not None:
        db.delete(flag)
        db.commit()


def list_flagged(db: Session, user: User) -> list[FlaggedItem]:
    """Danh sách từ đã đánh dấu, kèm mastery hiện tại để đối chiếu cảm nhận với
    số liệu — chỗ lệch giữa hai cái thường là chỗ đáng chú ý nhất."""
    rows = db.execute(
        select(ItemFlag, Item, WordSet, KnowledgeState.mastery)
        .join(Item, Item.id == ItemFlag.item_id)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .outerjoin(
            KnowledgeState,
            (KnowledgeState.item_id == Item.id) & (KnowledgeState.user_id == user.id),
        )
        .where(
            ItemFlag.user_id == user.id,
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
        )
        .order_by(ItemFlag.created_at.desc())
    ).all()

    return [
        FlaggedItem(
            item_id=item.id, word=item.word, meaning=item.meaning,
            word_set_id=ws.id, word_set_name=ws.name,
            note=flag.note,
            mastery=round(float(mastery), 4) if mastery is not None else None,
            flagged_at=flag.created_at,
        )
        for flag, item, ws, mastery in rows
    ]


def flagged_item_ids(db: Session, user: User) -> set[int]:
    """Dùng cho màn chi tiết bộ từ: đánh dấu icon trên từng dòng."""
    return set(db.execute(
        select(ItemFlag.item_id).where(ItemFlag.user_id == user.id)
    ).scalars().all())
