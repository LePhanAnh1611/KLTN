"""UC-96 — nhãn (tag) cho bộ từ vựng.

Khác `category` (UC-76): danh mục do Admin quản lý, mỗi bộ đúng một, dùng để
phân loại chủ đề. Nhãn do người tạo bộ tự đặt, một bộ nhiều nhãn, dùng để **lọc
chéo** — cùng lúc theo trình độ (`a1`), mục tiêu thi (`ielts`) và nguồn
(`oxford`). Hai thứ này không thay thế nhau được.

Chuẩn hóa là bắt buộc, không phải cho đẹp: "IELTS", "ielts", " Ielts " mà nằm
thành ba nhãn khác nhau thì bộ lọc đếm sai và người dùng không tìm thấy nhau.
"""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.word_set import WordSet
from app.models.word_set_tag import WordSetTag

#: Trần số nhãn mỗi bộ. Không có trần thì một bộ gắn 50 nhãn sẽ chiếm hết mọi
#: bộ lọc, và nhãn mất tác dụng phân biệt.
MAX_TAGS_PER_SET = 8
MAX_TAG_LENGTH = 40
_ALLOWED = re.compile(r"[^a-z0-9-]+")


def normalize(raw: str) -> str:
    """'  IELTS Writing ' -> 'ielts-writing'. Trả '' nếu không còn gì hợp lệ.

    Bỏ dấu tiếng Việt trước khi lọc ký tự: người dùng gõ "tiếng anh" thì thành
    'tieng-anh' chứ không phải 'ting-anh' (mất chữ có dấu).
    """
    text = unicodedata.normalize("NFD", raw.strip().lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("đ", "d").replace("_", "-").replace(" ", "-")
    text = _ALLOWED.sub("-", text).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:MAX_TAG_LENGTH]


def clean_tags(raw: list[str] | None) -> list[str]:
    """Chuẩn hóa + bỏ trùng + cắt theo trần.

    Trần cắt theo thứ tự NGƯỜI DÙNG NHẬP (8 nhãn đầu được giữ), nhưng khi đọc ra
    thì `tags_for` sắp theo bảng chữ cái. Không lưu thứ tự nhập vì làm vậy cần
    thêm một cột vị trí, mà thứ tự chip hiển thị không mang thông tin gì.
    """
    out: list[str] = []
    for item in raw or []:
        tag = normalize(item)
        if tag and tag not in out:
            out.append(tag)
    return out[:MAX_TAGS_PER_SET]


def set_tags(db: Session, word_set_id: int, raw: list[str] | None) -> list[str]:
    """Thay toàn bộ nhãn của một bộ. Không commit — để lớp gọi quyết định."""
    tags = clean_tags(raw)
    db.execute(delete(WordSetTag).where(WordSetTag.word_set_id == word_set_id))
    db.flush()
    for tag in tags:
        db.add(WordSetTag(word_set_id=word_set_id, tag=tag))
    db.flush()
    return tags


def tags_for(db: Session, word_set_ids: list[int]) -> dict[int, list[str]]:
    """Nhãn của nhiều bộ trong MỘT truy vấn.

    Danh sách bộ từ trả về 12–50 dòng; hỏi nhãn từng dòng là N+1 query, và đó là
    kiểu chậm chỉ lộ ra khi dữ liệu đã lớn.
    """
    if not word_set_ids:
        return {}
    rows = db.execute(
        select(WordSetTag.word_set_id, WordSetTag.tag)
        .where(WordSetTag.word_set_id.in_(word_set_ids))
        .order_by(WordSetTag.word_set_id, WordSetTag.tag)
    ).all()
    out: dict[int, list[str]] = {i: [] for i in word_set_ids}
    for ws_id, tag in rows:
        out[ws_id].append(tag)
    return out


def tags_of(db: Session, word_set_id: int) -> list[str]:
    return tags_for(db, [word_set_id]).get(word_set_id, [])


def popular_tags(db: Session, limit: int = 30) -> list[tuple[str, int]]:
    """[(nhãn, số bộ CÔNG KHAI mang nhãn đó)] — chỉ đếm bộ đang công khai.

    Đếm cả bộ riêng tư sẽ hiện ra những nhãn mà bấm vào không có kết quả nào.
    """
    rows = db.execute(
        select(WordSetTag.tag, func.count().label("n"))
        .join(WordSet, WordSet.id == WordSetTag.word_set_id)
        .where(WordSet.is_public.is_(True), WordSet.deleted_at.is_(None))
        .group_by(WordSetTag.tag)
        .order_by(func.count().desc(), WordSetTag.tag.asc())
        .limit(limit)
    ).all()
    return [(tag, int(n)) for tag, n in rows]
