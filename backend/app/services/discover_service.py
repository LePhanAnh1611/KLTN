"""UC-19/20/21 — Khám phá, xem chi tiết & tải (snapshot) bộ từ công khai; UC-22 bộ nổi bật.

Q1: tải = SAO CHÉP (snapshot) bộ + từ vào thư viện người dùng, gắn origin_set_id.
Q2: knowledge state gắn theo item bản sao (tạo lazy khi học — cold-start UC-69).
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.learning_stage import LearningStage
from app.models.user import User
from app.models.word_set import WordSet
from app.models.word_set_tag import WordSetTag
from app.services import tag_service
from app.models.word_set_rating import WordSetRating
from app.schemas.discover import (
    ItemPreview,
    PublicListResponse,
    PublicWordSetCard,
    PublicWordSetDetail,
    SortOption,
)
from app.schemas.word_set import WordSetResponse
from app.services.rating_service import rating_map
from app.services.word_set_service import _to_response, get_public_word_set

PREVIEW_LIMIT = 8
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 50
FEATURED_LIMIT = 8


def _downloaded_origin_ids(db: Session, user: User) -> set[int]:
    """Tập origin_set_id mà user đã tải (bản sao còn sống)."""
    rows = db.execute(
        select(WordSet.origin_set_id).where(
            WordSet.owner_id == user.id,
            WordSet.origin_set_id.is_not(None),
            WordSet.deleted_at.is_(None),
        )
    ).scalars().all()
    return {oid for oid in rows if oid is not None}


def _not_other_roadmap(user: User):
    """Ẩn bộ từ của chặng thuộc lộ trình KHÁC phiên bản người học (UC-84 v1/v2).

    Học viên pilot (v1) không thấy ~120 bộ v2 mới xuất hiện trong Khám phá —
    giữ nguyên điều kiện thực nghiệm; người dùng v2 không thấy bộ v1 trùng từ
    với bộ v2 (tránh tải hai bộ chứa cùng một từ -> DKT thấy hai item).
    """
    return WordSet.id.not_in(
        select(LearningStage.word_set_id).where(
            LearningStage.roadmap_version != user.roadmap_version
        )
    )


def _item_count(db: Session, word_set_id: int) -> int:
    return db.execute(
        select(func.count()).select_from(Item)
        .where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalar_one()


def _rating_subquery():
    """(word_set_id, điểm TB, số lượt) — outer join để sắp xếp theo đánh giá (UC-23)."""
    return (
        select(
            WordSetRating.word_set_id.label("ws_id"),
            func.avg(WordSetRating.stars).label("avg_stars"),
            func.count(WordSetRating.id).label("rating_count"),
        )
        .group_by(WordSetRating.word_set_id)
        .subquery()
    )


def _to_card(
    ws: WordSet, owner_name: str, item_count: int, is_downloaded: bool,
    avg_stars: float | None, rating_count: int, tags: list[str] | None = None,
) -> PublicWordSetCard:
    return PublicWordSetCard(
        id=ws.id, name=ws.name, description=ws.description, category=ws.category,
        difficulty=ws.difficulty, cover_image_url=ws.cover_image_url,
        download_count=ws.download_count, is_featured=ws.is_featured,
        owner_name=owner_name, item_count=item_count, is_downloaded=is_downloaded,
        rating_avg=round(float(avg_stars), 2) if avg_stars is not None else None,
        rating_count=rating_count or 0,
        tags=tags or [],
    )


def list_public(
    db: Session,
    user: User,
    *,
    search: str | None = None,
    category: str | None = None,
    difficulty: str | None = None,
    tag: str | None = None,
    sort: SortOption = "popular",
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> PublicListResponse:
    """UC-19: duyệt/tìm/lọc/sắp xếp bộ từ công khai (phân trang). UC-96: lọc nhãn."""
    page = max(1, page)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    filters = [WordSet.is_public.is_(True), WordSet.deleted_at.is_(None), _not_other_roadmap(user)]
    if search:
        filters.append(WordSet.name.ilike(f"%{search}%"))
    if category:
        filters.append(WordSet.category == category)
    if difficulty:
        filters.append(WordSet.difficulty == difficulty)
    if tag:
        # Chuẩn hóa nhãn nhận từ URL: '?tag=IELTS' và '?tag=ielts' phải ra cùng
        # một kết quả, nếu không link chia sẻ sẽ ra danh sách rỗng.
        wanted = tag_service.normalize(tag)
        filters.append(
            WordSet.id.in_(
                select(WordSetTag.word_set_id).where(WordSetTag.tag == wanted)
            )
        )

    total = db.execute(select(func.count()).select_from(WordSet).where(*filters)).scalar_one()

    ratings = _rating_subquery()
    if sort == "new":
        order = WordSet.created_at.desc()
    elif sort == "rating":
        order = func.coalesce(ratings.c.avg_stars, 0).desc()
    else:
        order = WordSet.download_count.desc()

    rows = db.execute(
        select(WordSet, User.display_name, ratings.c.avg_stars, ratings.c.rating_count)
        .join(User, User.id == WordSet.owner_id)
        .outerjoin(ratings, ratings.c.ws_id == WordSet.id)
        .where(*filters)
        .order_by(order, WordSet.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    downloaded = _downloaded_origin_ids(db, user)
    tags = tag_service.tags_for(db, [ws.id for ws, *_ in rows])   # UC-96, một truy vấn
    items = [
        _to_card(ws, owner_name, _item_count(db, ws.id), ws.id in downloaded, avg, cnt,
                 tags.get(ws.id, []))
        for ws, owner_name, avg, cnt in rows
    ]
    return PublicListResponse(items=items, total=total, page=page, page_size=page_size)


def list_featured(db: Session, user: User) -> list[PublicWordSetCard]:
    """UC-22: bộ từ được Admin gắn nổi bật (E1: chưa có bộ nào -> danh sách rỗng)."""
    ratings = _rating_subquery()
    rows = db.execute(
        select(WordSet, User.display_name, ratings.c.avg_stars, ratings.c.rating_count)
        .join(User, User.id == WordSet.owner_id)
        .outerjoin(ratings, ratings.c.ws_id == WordSet.id)
        .where(
            WordSet.is_featured.is_(True),
            WordSet.is_public.is_(True),
            WordSet.deleted_at.is_(None),
            _not_other_roadmap(user),
        )
        .order_by(WordSet.download_count.desc(), WordSet.id.desc())
        .limit(FEATURED_LIMIT)
    ).all()

    downloaded = _downloaded_origin_ids(db, user)
    tags = tag_service.tags_for(db, [ws.id for ws, *_ in rows])   # UC-96
    return [
        _to_card(ws, owner_name, _item_count(db, ws.id), ws.id in downloaded, avg, cnt,
                 tags.get(ws.id, []))
        for ws, owner_name, avg, cnt in rows
    ]


def get_public_detail(db: Session, user: User, word_set_id: int) -> PublicWordSetDetail:
    """UC-20: chi tiết + preview một số từ mẫu."""
    ws = get_public_word_set(db, word_set_id)
    owner_name = db.execute(
        select(User.display_name).where(User.id == ws.owner_id)
    ).scalar_one()
    preview = db.execute(
        select(Item).where(Item.word_set_id == ws.id, Item.deleted_at.is_(None))
        .order_by(Item.id).limit(PREVIEW_LIMIT)
    ).scalars().all()
    downloaded = _downloaded_origin_ids(db, user)
    avg, count = rating_map(db, [ws.id]).get(ws.id, (None, 0))

    return PublicWordSetDetail(
        id=ws.id, name=ws.name, description=ws.description, category=ws.category,
        difficulty=ws.difficulty, cover_image_url=ws.cover_image_url,
        download_count=ws.download_count, is_featured=ws.is_featured,
        owner_name=owner_name, item_count=_item_count(db, ws.id),
        is_downloaded=ws.id in downloaded, created_at=ws.created_at,
        rating_avg=avg, rating_count=count,
        tags=tag_service.tags_of(db, ws.id),                       # UC-96
        preview_items=[ItemPreview.model_validate(it) for it in preview],
    )


def clone_word_set(db: Session, user: User, source_id: int) -> WordSetResponse:
    """UC-21: tải = snapshot bộ gốc vào thư viện; tăng download_count; chống trùng.

    UC-96: nhãn cũng được chép theo. Q1 nói bản tải là một SNAPSHOT — chép từ mà
    bỏ nhãn thì bản sao mất luôn khả năng lọc, dù nội dung y hệt bản gốc.
    """
    source = get_public_word_set(db, source_id)

    existing = db.execute(
        select(WordSet.id).where(
            WordSet.owner_id == user.id,
            WordSet.origin_set_id == source_id,
            WordSet.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bộ từ vựng đã có trong thư viện của bạn",
        )

    clone = WordSet(
        owner_id=user.id,
        name=source.name,
        description=source.description,
        category=source.category,
        difficulty=source.difficulty,
        cefr_level=source.cefr_level,
        cover_image_url=source.cover_image_url,
        is_public=False,
        origin_set_id=source.id,
    )
    db.add(clone)
    db.flush()

    source_items = db.execute(
        select(Item).where(Item.word_set_id == source.id, Item.deleted_at.is_(None))
    ).scalars().all()
    db.add_all([
        Item(
            word_set_id=clone.id, word=it.word, meaning=it.meaning,
            phonetic=it.phonetic, part_of_speech=it.part_of_speech, example=it.example,
            example_vi=it.example_vi,
            # Snapshot (Q1) phải mang theo cả nguồn gốc: bản sao có đúng nội
            # dung của bản gốc thì phải có đúng mức tin cậy của bản gốc. Bỏ ba
            # trường này là tải bộ từ về xong cảnh báo "chưa kiểm chứng" biến
            # mất, trong khi nghĩa vẫn y nguyên.
            meaning_confidence=it.meaning_confidence,
            meaning_source=it.meaning_source,
            example_source=it.example_source,
        )
        for it in source_items
    ])

    source.download_count += 1
    tag_service.set_tags(db, clone.id, tag_service.tags_of(db, source.id))   # UC-96
    db.commit()
    db.refresh(clone)
    return _to_response(db, clone, user.id)
