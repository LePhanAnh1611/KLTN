"""Sinh đề bài từ item của một bộ từ: trắc nghiệm (UC-26), điền khuyết & ghép
cặp (UC-28).

Đề sinh ngẫu nhiên mỗi lần gọi và KHÔNG lưu lại — kết quả trả lời mới là thứ
được ghi (Interaction, BR-05). Đáp án gửi kèm để hiển thị phản hồi luyện tập;
backend chấm lại đáp án người học gửi trước khi ghi Interaction và cấp XP.
"""
import random
import re

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.item import Item
from app.models.user import User
from app.schemas.quiz import (
    ClozeQuestion,
    MatchingRound,
    MatchPair,
    QuizQuestion,
    TypingQuestion,
)
from app.services import config_service
from app.services.word_set_service import get_owned_word_set


# --- Chọn câu hỏi & đáp án nhiễu (bug #9) -----------------------------------------
#
# Người học phản ánh "4 đáp án không sát với từ". Có ba nguyên nhân, xử lý ở đây:
#   1. Đáp án ĐÚNG là nghĩa từ điển bị gắn cờ sai (needs-review) hoặc rác ("xem X")
#      -> từ đó không ra câu trắc nghiệm; thẻ lật vẫn học bình thường.
#   2. Đáp án nhiễu trùng/gần nghĩa đáp án đúng (ethical & ethics cùng "đạo đức")
#      -> câu có 2 đáp án đúng. Loại nhiễu có cụm nghĩa trùng hoặc lồng nhau.
#   3. Nhiễu là nghĩa cổ quái hoặc khác từ loại -> đoán được bằng cách loại trừ.
#      Ưu tiên nhiễu đáng tin, cùng từ loại.
#   4. Một đáp án chứa nhiều nghĩa ngăn bằng dấu phẩy ("lợi, lợi ích, bổ ích")
#      -> mỗi đáp án chỉ hiện NGHĨA CHÍNH (`answer_label`). Việc loại nhiễu trùng
#      nghĩa vẫn so trên nghĩa ĐẦY ĐỦ, nên rút gọn không làm lọt nhiễu gần nghĩa.

#: Mức tin cậy nghĩa KHÔNG dùng làm đáp án trắc nghiệm. NULL (người học tự nhập)
#: vẫn dùng: chữ của chính họ thì không cần hệ thống xác nhận.
UNRELIABLE_CONFIDENCE = frozenset({"needs-review"})
_JUNK_MEANING = re.compile(r"^\s*(xem\s|<|cách viết khác)", re.IGNORECASE)
_SENSE_SPLIT = re.compile(r"[,;/]")
_PARENS = re.compile(r"\([^)]*\)")
#: Dấu còn sót ở mép một cụm nghĩa sau khi bỏ phần trong ngoặc:
#: "(Mạo từ): một + danh từ" -> ": một + danh từ". Cắt ở hai mép, giữ "->" ở giữa.
_EDGE_PUNCT = " \t:-–—>"


def meaning_is_quizzable(meaning: str | None, confidence: str | None) -> bool:
    """Nghĩa đủ tin để làm đáp án đúng / đáp án nhiễu của câu trắc nghiệm."""
    text = (meaning or "").strip()
    return bool(text) and confidence not in UNRELIABLE_CONFIDENCE and not _JUNK_MEANING.match(text)


def _senses(meaning: str) -> set[str]:
    text = _PARENS.sub(" ", meaning.lower())
    return {" ".join(part.strip(_EDGE_PUNCT).split()) for part in _SENSE_SPLIT.split(text)
            if part.strip(_EDGE_PUNCT)}


def answer_label(meaning: str) -> str:
    """Nghĩa chính dùng làm chữ của MỘT đáp án: cụm đầu tiên trước `, ; /`, bỏ
    phần trong ngoặc. "Số liệu, dữ liệu" -> "số liệu".

    Hạ chữ hoa đầu (nghĩa từ điển đôi khi viết hoa, đôi khi không): để nguyên thì
    đáp án đúng viết hoa giữa ba nhiễu viết thường là lộ đáp án. Từ viết tắt toàn
    chữ hoa ("AI", "GDP") giữ nguyên. Không còn gì sau khi cắt -> trả nguyên văn.
    """
    text = _PARENS.sub(" ", meaning or "")
    head = next((h for h in (p.strip(_EDGE_PUNCT) for p in _SENSE_SPLIT.split(text)) if h), "")
    head = " ".join(head.split()) or (meaning or "").strip()
    first = head.split(" ", 1)[0]
    if first[:1].isupper() and not first.isupper():
        head = head[:1].lower() + head[1:]
    return head


def meanings_overlap(a: str, b: str) -> bool:
    """Hai nghĩa có cụm trùng hoặc lồng nhau ("đạo đức" ⊂ "đạo đức học") — đặt
    cạnh nhau thì người học không phân biệt được đâu là đáp án đúng."""
    for x in _senses(a):
        for y in _senses(b):
            if x == y or f" {x} " in f" {y} " or f" {y} " in f" {x} ":
                return True
    return False


def pick_distractors(
    correct: str,
    part_of_speech: str | None,
    pool: list[tuple[str, str | None, bool]],
    k: int = 3,
) -> list[str] | None:
    """Chọn k đáp án nhiễu từ `pool` = [(nghĩa, từ loại, đáng tin)].

    Thứ tự ưu tiên: đáng tin + cùng từ loại > đáng tin > còn lại; trong cùng một
    nhóm thì ngẫu nhiên. Không đủ k nhiễu hợp lệ -> None (nơi gọi bỏ câu đó).
    """
    seen = {correct.strip().lower()}
    seen_labels = {answer_label(correct).lower()}
    candidates: list[tuple[str, str | None, bool]] = []
    for meaning, pos, reliable in pool:
        key = (meaning or "").strip().lower()
        if not key or key in seen or meanings_overlap(meaning, correct):
            continue
        label = answer_label(meaning).lower()
        if label in seen_labels:
            continue  # hai nhiễu khác nhau nhưng cùng nghĩa chính -> 2 đáp án y hệt
        seen.add(key)
        seen_labels.add(label)
        candidates.append((meaning, pos, reliable))
    if len(candidates) < k:
        return None
    random.shuffle(candidates)
    candidates.sort(key=lambda c: (not c[2], not part_of_speech or c[1] != part_of_speech))
    return [c[0] for c in candidates[:k]]


def _options(correct: str, distractors: list[str]) -> tuple[list[str], int]:
    """Xáo đáp án, mỗi đáp án đúng một nghĩa (`answer_label`). Trả (options, index đúng)."""
    labels = [answer_label(correct), *(answer_label(d) for d in distractors)]
    right = labels[0]
    random.shuffle(labels)
    return labels, labels.index(right)


def _quizzable(item: Item) -> bool:
    return meaning_is_quizzable(item.meaning, item.meaning_confidence)


def generate_quiz(db: Session, user: User, word_set_id: int, limit: int) -> list[QuizQuestion]:
    get_owned_word_set(db, user, word_set_id)

    items = db.execute(
        select(Item).where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalars().all()

    # cần đủ 1 đáp án đúng + các đáp án nhiễu (ngưỡng ở UC-81)
    min_items = config_service.get_int("min_items_for_quiz")
    if len(items) < min_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bộ từ vựng cần tối thiểu {min_items} từ để tạo trắc nghiệm",
        )

    # Bộ toàn nghĩa chưa xác nhận (hiếm) thì vẫn ra đề như cũ thay vì trả 0 câu.
    chosen = [it for it in items if _quizzable(it)] or list(items)
    random.shuffle(chosen)
    chosen = chosen[:limit]
    pool = [(it.id, it.meaning, it.part_of_speech, _quizzable(it)) for it in items]

    questions: list[QuizQuestion] = []
    for item in chosen:
        distractors = pick_distractors(
            item.meaning, item.part_of_speech,
            [(m, pos, ok) for iid, m, pos, ok in pool if iid != item.id],
        )
        if distractors is None:
            continue
        options, correct_index = _options(item.meaning, distractors)
        questions.append(
            QuizQuestion(
                item_id=item.id,
                word=item.word,
                options=options,
                correct_index=correct_index,
            )
        )
    return questions


BLANK = "____"


def _live_items(db: Session, user: User, word_set_id: int) -> list[Item]:
    get_owned_word_set(db, user, word_set_id)
    return list(db.execute(
        select(Item).where(Item.word_set_id == word_set_id, Item.deleted_at.is_(None))
    ).scalars().all())


def _blank_out(example: str, word: str) -> str | None:
    """Thay từ cần học trong câu ví dụ bằng chỗ trống.

    Khớp theo ranh giới từ và không phân biệt hoa thường, nên "Book a ticket"
    với từ "book" vẫn khoét đúng. Trả None nếu câu không chứa từ — khi đó item
    không dùng được cho dạng điền khuyết.
    """
    pattern = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
    blanked, count = pattern.subn(BLANK, example, count=1)
    return blanked if count else None


def generate_cloze(db: Session, user: User, word_set_id: int, limit: int) -> list[ClozeQuestion]:
    """UC-28 — điền khuyết, dựng từ câu ví dụ của item.

    E1: bộ từ không có item nào vừa có ví dụ vừa chứa chính từ đó -> 400 kèm lý do,
    vì đây là thiếu dữ liệu chứ không phải lỗi hệ thống; người học cần biết phải
    bổ sung ví dụ.
    """
    items = _live_items(db, user, word_set_id)

    usable: list[tuple[Item, str]] = []
    for item in items:
        if not item.example:
            continue
        blanked = _blank_out(item.example, item.word)
        if blanked:
            usable.append((item, blanked))

    if not usable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bộ từ vựng chưa có câu ví dụ nào chứa chính từ cần học, "
                   "nên chưa tạo được bài điền khuyết",
        )

    random.shuffle(usable)
    return [
        ClozeQuestion(item_id=item.id, sentence=sentence, answer=item.word, hint=item.meaning)
        for item, sentence in usable[:limit]
    ]


def generate_typing(db: Session, user: User, word_set_id: int, limit: int) -> list[TypingQuestion]:
    """UC-89 gõ từ · UC-90 nghe viết — dùng CHUNG một nguồn dữ liệu.

    Chỉ cần `word` và `meaning` nên KHÔNG có nhánh "thiếu dữ liệu" như điền
    khuyết (vốn đòi câu ví dụ chứa chính từ đó). E1 duy nhất: bộ từ rỗng.

    Hai UC dùng chung endpoint vì payload y hệt nhau — khác biệt nằm hoàn toàn ở
    cách TRÌNH BÀY: gõ từ hiện nghĩa tiếng Việt làm đề, nghe viết cho trình duyệt
    đọc từ đó lên (UC-29). Tách thành hai endpoint chỉ để tên đường dẫn đẹp là
    nhân đôi một truy vấn giống hệt nhau. Chế độ phiên vẫn tách
    (`typing`/`dictation`) nên `INTERACTION.exercise_format` vẫn phân biệt được.
    """
    items = [it for it in _live_items(db, user, word_set_id) if it.meaning.strip()]
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bộ từ vựng chưa có từ nào có nghĩa để tạo bài gõ từ",
        )

    random.shuffle(items)
    return [
        TypingQuestion(
            item_id=item.id,
            meaning=item.meaning,
            answer=item.word,
            part_of_speech=item.part_of_speech,
            first_letter=item.word[:1],
            length=len(item.word),
        )
        for item in items[:limit]
    ]


def generate_matching(db: Session, user: User, word_set_id: int, size: int | None = None) -> MatchingRound:
    """UC-28 — ghép cặp từ ↔ nghĩa. Số cặp mỗi lượt lấy từ cấu hình (UC-81)."""
    items = _live_items(db, user, word_set_id)

    round_size = size or config_service.get_int("matching_round_size")
    if len(items) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bộ từ vựng cần tối thiểu 2 từ để tạo bài ghép cặp",
        )

    # Cột nghĩa hiện NGHĨA CHÍNH (bug #9). Client khớp cặp theo chữ nghĩa, nên hai
    # từ cùng nghĩa chính không được vào cùng một lượt — chọn lần lượt, bỏ trùng.
    pairs: list[MatchPair] = []
    used: set[str] = set()
    for item in random.sample(items, len(items)):
        label = answer_label(item.meaning)
        if label.lower() in used:
            continue
        used.add(label.lower())
        pairs.append(MatchPair(item_id=item.id, word=item.word, meaning=label))
        if len(pairs) == round_size:
            break

    meanings = [p.meaning for p in pairs]
    # Xáo cột nghĩa để không khớp theo hàng. Với >=2 cặp, quay vòng cho tới khi
    # khác thứ tự gốc — nếu không, ngẫu nhiên có thể trả về đúng thứ tự và lộ đáp án.
    for _ in range(10):
        random.shuffle(meanings)
        if meanings != [p.meaning for p in pairs]:
            break
    else:
        meanings.reverse()

    return MatchingRound(pairs=pairs, shuffled_meanings=meanings)


def generate_quiz_for_items(db: Session, user: User, item_ids: list[int]) -> list[QuizQuestion]:
    """Pilot — câu trắc nghiệm (chọn nghĩa đúng trong 4) cho đúng các từ đã cho.

    Dùng cho thẻ lật của 'Học thông minh' và 'Ôn tập': người học chọn nghĩa
    TRƯỚC khi lật thẻ, hệ thống chấm. Khác `generate_quiz` ở chỗ danh sách từ do
    người gọi quyết định (đã chọn theo DKT / theo lịch ôn) và có thể trải nhiều
    bộ, nên đáp án nhiễu lấy trong cùng bộ trước, thiếu thì lấy cả thư viện.

    Luân phiên dạng bài (cấu hình `alternate_card_quiz`): từ mà lượt trả lời
    gần nhất là trắc nghiệm thì lần này KHÔNG ra câu hỏi -> client hiện thẻ lật;
    lần sau đó (lượt gần nhất là thẻ lật) lại ra trắc nghiệm. Từ chưa học lần
    nào ra trắc nghiệm. Từ có nghĩa chưa đáng tin vẫn luôn là thẻ lật (bug #9).

    Từ không thuộc người học / đã xóa bị bỏ qua (không lộ là có tồn tại).
    Giữ đúng thứ tự `item_ids`.
    """
    from app.models.word_set import WordSet  # tránh vòng import ở đầu module

    if not item_ids:
        return []
    owned = select(WordSet.id).where(WordSet.owner_id == user.id, WordSet.deleted_at.is_(None))
    items = {
        it.id: it for it in db.execute(
            select(Item).where(
                Item.id.in_(item_ids), Item.deleted_at.is_(None), Item.word_set_id.in_(owned)
            )
        ).scalars().all()
    }
    if not items:
        return []

    Pool = list[tuple[str, str | None, bool]]
    columns = (Item.meaning, Item.part_of_speech, Item.meaning_confidence)

    def _rows(stmt) -> Pool:
        return [(m, pos, meaning_is_quizzable(m, conf)) for _sid, m, pos, conf in db.execute(stmt).all()]

    set_ids = {it.word_set_id for it in items.values()}
    by_set: dict[int, Pool] = {}
    for set_id, meaning, pos, conf in db.execute(
        select(Item.word_set_id, *columns).where(
            Item.word_set_id.in_(set_ids), Item.deleted_at.is_(None)
        )
    ).all():
        by_set.setdefault(set_id, []).append((meaning, pos, meaning_is_quizzable(meaning, conf)))
    library: Pool | None = None  # chỉ nạp khi một bộ quá ít từ

    last_was_quiz = (
        _items_last_answered_by_quiz(db, user.id, list(items))
        if config_service.get_bool("alternate_card_quiz") else set()
    )

    questions: list[QuizQuestion] = []
    for item_id in item_ids:
        item = items.get(item_id)
        if item is None or not _quizzable(item):
            continue  # nghĩa chưa đáng tin -> client dùng thẻ lật thường (bug #9)
        if item_id in last_was_quiz:
            continue  # lần trước đã trắc nghiệm -> lần này thẻ lật (luân phiên)
        distractors = pick_distractors(item.meaning, item.part_of_speech,
                                       by_set.get(item.word_set_id, []))
        if distractors is None:
            if library is None:
                library = _rows(
                    select(Item.word_set_id, *columns).where(
                        Item.word_set_id.in_(owned), Item.deleted_at.is_(None)
                    ).limit(2000)
                )
            distractors = pick_distractors(item.meaning, item.part_of_speech,
                                           by_set.get(item.word_set_id, []) + library)
        if distractors is None:
            continue  # không đủ đáp án nhiễu -> client dùng thẻ lật thường
        options, correct_index = _options(item.meaning, distractors)
        questions.append(QuizQuestion(
            item_id=item.id, word=item.word, options=options,
            correct_index=correct_index,
        ))
    return questions


def _items_last_answered_by_quiz(db: Session, user_id: int, item_ids: list[int]) -> set[int]:
    """Các từ mà lượt trả lời GẦN NHẤT (được tính) của người học là trắc nghiệm.

    Lượt bị loại (`excluded_reason`) coi như chưa xảy ra, giống mọi chỗ khác.
    Lấy hết lượt của các từ này rồi giữ lượt mới nhất mỗi từ trong Python — số từ
    mỗi phiên nhỏ nên rẻ, và chạy được trên cả PostgreSQL lẫn SQLite của test.
    """
    from app.models.interaction import Interaction, counted_interaction

    if not item_ids:
        return set()
    latest: dict[int, str | None] = {}
    for item_id, fmt in db.execute(
        select(Interaction.item_id, Interaction.exercise_format)
        .where(Interaction.user_id == user_id, Interaction.item_id.in_(item_ids),
               counted_interaction())
        .order_by(Interaction.answered_at.desc(), Interaction.id.desc())
    ).all():
        latest.setdefault(item_id, fmt)
    return {item_id for item_id, fmt in latest.items() if fmt == "quiz"}
