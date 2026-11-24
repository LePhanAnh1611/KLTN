"""UC-95 — tra cứu một từ bất kỳ.

**Đây là tra cứu trong KHO DỮ LIỆU CỦA HỆ THỐNG, không phải một từ điển đầy đủ.**
Nói rõ ngay từ đầu vì đó là giới hạn thật: nếu không bộ từ công khai nào chứa từ
đó thì hệ thống không có nghĩa để trả, và nó sẽ nói vậy thay vì bịa.

Ba nguồn, không gọi dịch vụ ngoài nào:

1. **Bộ từ của chính người tra** — nghĩa họ (hoặc người họ tải bộ về) đã viết.
   Ưu tiên cao nhất: đây là cách họ đang hiểu từ đó.
2. **Bộ từ công khai** — nghĩa cộng đồng đã viết, xếp theo bộ được tải nhiều.
3. **Wordlist CEFR chuẩn** (CEFR-J + Octanove) cho mức trình độ.

Vì sao không dùng LLM sinh nghĩa: cùng lý do UC-87 cấm LLM gán CEFR — hai lần
chạy ra hai kết quả khác nhau, và người học không có cách nào biết cái nào đúng.
Thà trả rỗng kèm gợi ý còn hơn trả một nghĩa không kiểm chứng được.
"""
from __future__ import annotations

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.dictionary import DictionaryEntry, DictionaryResult
from app.services.pdf_import.cefr import get_cefr_source

#: Trần số nghĩa trả về. "book" có mặt trong hàng chục bộ công khai; đổ hết ra
#: thì người học phải cuộn qua mười nghĩa giống nhau để thấy cái khác biệt.
MAX_ENTRIES = 12
MAX_SUGGESTIONS = 8
MIN_QUERY_LENGTH = 1

_WORD_RE = re.compile(r"[^a-zA-Z\-' ]+")


def normalize_query(raw: str) -> str:
    """Chuẩn hóa chuỗi tra: bỏ ký tự lạ, gộp khoảng trắng, về chữ thường."""
    text = _WORD_RE.sub(" ", raw or "").strip().lower()
    return re.sub(r"\s{2,}", " ", text)


def _cefr_level(word: str) -> str | None:
    """Mức CEFR từ wordlist chuẩn. Lỗi nạp file KHÔNG được làm hỏng tra cứu."""
    try:
        return get_cefr_source().lookup(word)
    except Exception:  # thiếu/hỏng file wordlist — phần còn lại vẫn dùng được
        return None


def _entries(db: Session, user: User, word: str) -> list[DictionaryEntry]:
    """Các nghĩa khớp CHÍNH XÁC mặt chữ, thư viện của người tra lên trước."""
    rows = db.execute(
        select(Item, WordSet.id, WordSet.name, WordSet.owner_id, WordSet.download_count)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            func.lower(Item.word) == word,
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
            # Chỉ thấy bộ của mình hoặc bộ công khai — không rò nội dung bộ riêng
            # tư của người khác qua đường tra từ.
            (WordSet.owner_id == user.id) | (WordSet.is_public.is_(True)),
        )
        .order_by(
            (WordSet.owner_id == user.id).desc(),
            WordSet.download_count.desc(),
            Item.id.asc(),
        )
        .limit(MAX_ENTRIES * 3)
    ).all()

    out: list[DictionaryEntry] = []
    seen: set[tuple[str, str]] = set()
    for item, ws_id, ws_name, owner_id, _dl in rows:
        # Khử trùng: cùng một nghĩa lặp lại ở nhiều bộ (bộ tải về là bản sao)
        # thì chỉ giữ lần đầu — bản của thư viện người tra, do thứ tự ở trên.
        key = ((item.meaning or "").strip().lower(), (item.part_of_speech or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(DictionaryEntry(
            word=item.word,
            phonetic=item.phonetic,
            part_of_speech=item.part_of_speech,
            meaning=item.meaning,
            example=item.example,
            word_set_id=ws_id,
            word_set_name=ws_name,
            in_my_library=owner_id == user.id,
        ))
        if len(out) >= MAX_ENTRIES:
            break
    return out


def _suggestions(db: Session, user: User, word: str) -> list[str]:
    """Từ gần đúng (khớp tiền tố) — cứu các ca gõ thiếu hoặc nhập dạng chia."""
    if len(word) < 2:
        return []
    rows = db.execute(
        select(Item.word)
        .join(WordSet, WordSet.id == Item.word_set_id)
        .where(
            func.lower(Item.word).like(f"{word}%"),
            func.lower(Item.word) != word,
            Item.deleted_at.is_(None),
            WordSet.deleted_at.is_(None),
            (WordSet.owner_id == user.id) | (WordSet.is_public.is_(True)),
        )
        .group_by(Item.word)
        .order_by(func.count().desc(), Item.word.asc())
        .limit(MAX_SUGGESTIONS)
    ).all()
    return [w for (w,) in rows]


def lookup(db: Session, user: User, raw_query: str) -> DictionaryResult:
    """UC-95 — tra một từ. Không tìm thấy vẫn trả 200 kèm gợi ý, không 404.

    404 ở đây sẽ sai về nghĩa: bản thân phép tra ĐÃ chạy thành công, chỉ là kết
    quả rỗng. Giao diện cần phân biệt "tra hỏng" với "tra xong, không có gì".
    """
    query = normalize_query(raw_query)
    if len(query) < MIN_QUERY_LENGTH:
        return DictionaryResult(query=query, cefr_level=None, in_my_library=False,
                                entries=[], suggestions=[])

    entries = _entries(db, user, query)
    return DictionaryResult(
        query=query,
        cefr_level=_cefr_level(query),
        in_my_library=any(e.in_my_library for e in entries),
        entries=entries,
        suggestions=[] if entries else _suggestions(db, user, query),
    )
