"""UC-76 — danh mục bộ từ (Admin CRUD; người học dùng để lọc ở UC-19).

`word_sets.category` vẫn lưu TÊN danh mục dạng chuỗi, nên khi đổi tên danh mục
thì cập nhật luôn các bộ từ đang gắn để không lệch bộ lọc.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.word_set import WordSet


def list_categories(db: Session, *, only_active: bool = True) -> list[Category]:
    query = select(Category)
    if only_active:
        query = query.where(Category.is_active.is_(True))
    return list(db.execute(query.order_by(Category.sort_order, Category.name)).scalars().all())


def _count_word_sets(db: Session, name: str) -> int:
    return db.execute(
        select(func.count()).select_from(WordSet)
        .where(WordSet.category == name, WordSet.deleted_at.is_(None))
    ).scalar_one()


def word_set_counts(db: Session) -> dict[str, int]:
    """{tên danh mục: số bộ từ đang gắn} — hiện ở màn quản trị."""
    rows = db.execute(
        select(WordSet.category, func.count(WordSet.id))
        .where(WordSet.deleted_at.is_(None), WordSet.category.is_not(None))
        .group_by(WordSet.category)
    ).all()
    return {name: count for name, count in rows}


def get_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy danh mục"
        )
    return category


def _ensure_name_free(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    query = select(Category.id).where(Category.name == name)
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if db.execute(query).scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Tên danh mục đã tồn tại"
        )


def create_category(db: Session, data) -> Category:
    _ensure_name_free(db, data.name)
    category = Category(
        name=data.name, description=data.description,
        is_active=data.is_active, sort_order=data.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: int, data) -> Category:
    """Đổi tên danh mục thì đồng bộ luôn `word_sets.category` của các bộ đang gắn."""
    category = get_category(db, category_id)

    if data.name is not None and data.name != category.name:
        _ensure_name_free(db, data.name, exclude_id=category.id)
        db.execute(
            update(WordSet)
            .where(WordSet.category == category.name)
            .values(category=data.name)
        )
        category.name = data.name

    for field in ("description", "is_active", "sort_order"):
        value = getattr(data, field)
        if value is not None:
            setattr(category, field, value)

    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: int) -> None:
    """E1 — còn bộ từ đang gắn thì không cho xóa (yêu cầu chuyển/hủy gắn trước)."""
    category = get_category(db, category_id)
    in_use = _count_word_sets(db, category.name)
    if in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Còn {in_use} bộ từ vựng đang dùng danh mục này - hãy chuyển sang danh mục khác trước",
        )
    db.delete(category)
    db.commit()
