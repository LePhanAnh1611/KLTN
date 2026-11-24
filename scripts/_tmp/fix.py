"""Sửa dữ liệu sau sự cố chấm sai trắc nghiệm (2026-10-26).

    python -m app.scripts.fix_grading_bug_20261026 --until 2026-10-27T09:30+07:00            # chạy thử
    python -m app.scripts.fix_grading_bug_20261026 --until 2026-10-27T09:30+07:00 --apply    # ghi thật

`--until` = lúc bản sửa lên pilot (giờ chạy update-pilot). BẮT BUỘC khai tường
minh: lượt sai sau mốc đó là sai THẬT, khai muộn là loại nhầm dữ liệu thật.
Thiếu `--until` thì script in mốc dò được từ dữ liệu để đối chiếu rồi dừng.

Sự cố: commit 1ad9af0 đổi phương án trắc nghiệm/ghép cặp sang hiện NGHĨA CHÍNH
(`answer_label`), nhưng server vẫn chấm `answer == item.meaning` (nghĩa đầy đủ).
Mọi lượt chọn nghĩa của từ nhiều nghĩa bị ghi `is_correct = false` dù người học
chọn đúng. Trên pilot: tỉ lệ đúng của nhóm này từ 87,8% tụt về 0% kể từ 18:05.

Script làm, trong MỘT giao dịch (chạy thử thì rollback):

1. Tìm lượt bị ảnh hưởng: dạng `quiz`/`matching`, trong khoảng thời gian lỗi,
   của từ có `answer_label(meaning) != meaning`, đang ghi sai, chưa bị loại.
2. Khôi phục đáp án THẬT cho lượt còn `request_hash` (SHA-256 của chính request):
   thử mọi nghĩa trong bộ từ cho tới khi băm khớp, rồi chấm lại bằng luật mới.
3. Lượt không khôi phục được -> `excluded_reason = 'grading_bug_2026-10-26'`.
   KHÔNG xóa (BR-05), KHÔNG đoán lại đúng/sai (sẽ là bịa dữ liệu).
4. Tính lại mastery bằng DKT trên lịch sử đã sạch, cho mọi KnowledgeState của
   người học bị ảnh hưởng được cập nhật từ lúc lỗi (DKT là mô hình chuỗi: một
   lượt sai giả lệch trạng thái ẩn của MỌI từ sau nó, không riêng từ bị chấm sai).
5. Lịch ôn: mỗi lượt sai giả đã nhân nửa đời với `half_life_shrink`. Gỡ đúng phần
   đó (chia lại), rồi đặt `next_review_at` tính từ lượt ôn cuối của cặp đó. Gần
   đúng ở một chỗ: nếu nửa đời đã chạm sàn khi co thì giá trị trước khi co lớn
   hơn sàn bao nhiêu không còn biết — kết quả có thể giãn hơn thực tế một chút.
   Lượt khôi phục được là ĐÚNG cũng chỉ gỡ phần co, không cộng phần giãn
   (mastery lúc đó không lưu) — thiên về ôn sớm, an toàn.

Chạy lại được: lượt đã loại hoặc đã sửa thành đúng không bị đụng lần hai.
"""
from __future__ import annotations

import argparse
import hashlib
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.session import StudySession
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.session import AnswerRequest
from app.services import config_service, dkt_client
from app.services.mastery_service import build_history, cold_start_prior
from app.services.quiz_service import answer_label
from app.services.review_service import (
    MAX_HALF_LIFE_DAYS, MIN_HALF_LIFE_DAYS, half_life_to_interval_days,
)
from app.services.session_service import _is_meaning_answer

REASON = "grading_bug_2026-10-26"
#: Bản lỗi lên pilot lúc 18:02 (bản sao lưu ngay trước khi cập nhật); lượt lỗi đầu
#: tiên 18:05. Lấy mốc tròn trước đó — không có lượt nhiều nghĩa nào đúng sau 11:11.
DEFAULT_SINCE = datetime(2026, 10, 26, 11, 0, tzinfo=timezone.utc)  # 18:00 giờ VN
FORMATS = ("quiz", "matching")


def is_multi_sense(meaning: str | None) -> bool:
    """Từ mà phương án hiển thị khác nghĩa đầy đủ — đúng nhóm bị chấm sai."""
    return answer_label(meaning or "") != " ".join((meaning or "").split())


@dataclass
class FixResult:
    since: datetime
    until: datetime
    recovered_correct: list[int] = field(default_factory=list)
    recovered_wrong: list[int] = field(default_factory=list)
    excluded: list[int] = field(default_factory=list)
    by_user: Counter = field(default_factory=Counter)
    mastery_updated: int = 0
    mastery_unscored: int = 0
    schedules_fixed: int = 0


def find_fix_time(db: Session, since: datetime) -> datetime | None:
    """GỢI Ý lúc bản sửa lên: lượt chọn nghĩa ĐÚNG đầu tiên của từ nhiều nghĩa sau
    `since` (trong lúc lỗi, nhóm này không thể đúng). None = chưa thấy.

    Chỉ để đối chiếu, không dùng làm mốc: sau khi script đã chạy, lượt được khôi
    phục thành đúng cũng thỏa điều kiện này và kéo mốc về sớm."""
    rows = db.execute(
        select(Interaction.answered_at, Item.meaning)
        .join(Item, Item.id == Interaction.item_id)
        .where(Interaction.answered_at >= since, Interaction.is_correct.is_(True),
               Interaction.exercise_format.in_(FORMATS))
        .order_by(Interaction.answered_at)
    ).all()
    return next((at for at, meaning in rows if is_multi_sense(meaning)), None)


def _recover_answer(db: Session, it: Interaction, item: Item) -> str | None:
    """Đáp án người học đã gửi, suy ngược từ `request_hash`. None nếu không khớp."""
    if not it.request_hash or not it.client_answer_id:
        return None
    meanings = db.execute(select(Item.meaning).where(Item.word_set_id == item.word_set_id)).scalars()
    candidates = {c for m in meanings for c in (answer_label(m), m)}
    for answer in candidates:
        for is_correct in (True, False, None):
            for fmt in {None, it.exercise_format}:
                for reason in {None, it.selection_reason if it.selection_reason in ("band", "explore") else None}:
                    req = AnswerRequest(
                        item_id=it.item_id, is_correct=is_correct, answer=answer,
                        client_answer_id=uuid.UUID(it.client_answer_id),
                        response_time_ms=it.response_time_ms, exercise_format=fmt,
                        selection_reason=reason,
                    )
                    if hashlib.sha256(req.model_dump_json().encode()).hexdigest() == it.request_hash:
                        return answer
    return None


def _recompute_mastery(db: Session, user_id: int, since: datetime, result: FixResult) -> None:
    """Chấm lại mọi KnowledgeState của người này được ghi từ lúc lỗi, bằng lịch sử sạch."""
    states = db.execute(
        select(KnowledgeState, Item).join(Item, Item.id == KnowledgeState.item_id)
        .where(KnowledgeState.user_id == user_id, KnowledgeState.last_updated >= since)
    ).all()
    if not states:
        return
    history, formats, history_pos = build_history(db, user_id)
    # Dạng bài mục tiêu = dạng bài của lượt HỢP LỆ cuối cùng với từ đó — đúng cái
    # update_mastery_for_item đã dùng khi ghi giá trị cũ.
    last_fmt = dict(db.execute(
        select(Interaction.item_id, Interaction.exercise_format)
        .where(Interaction.user_id == user_id, Interaction.excluded_reason.is_(None))
        .order_by(Interaction.answered_at)
    ).all())
    groups: dict[str | None, list[tuple[KnowledgeState, Item]]] = defaultdict(list)
    for ks, item in states:
        groups[last_fmt.get(item.id, "quiz")].append((ks, item))
    now = datetime.now(timezone.utc)
    for fmt, pairs in groups.items():
        words = [item.word for _, item in pairs]
        pos = {**history_pos, **{item.word: item.part_of_speech or "" for _, item in pairs}}
        scores = dkt_client.predict_mastery(history, words, pos=pos,
                                            history_formats=formats, target_format=fmt)
        for ks, item in pairs:
            p = scores.get(item.word)
            if p is None and item.id not in last_fmt:
                # Mọi lượt của từ này đều bị loại: về lại prior cold-start.
                difficulty = db.execute(select(WordSet.difficulty).where(WordSet.id == item.word_set_id)).scalar_one_or_none()
                p = cold_start_prior(difficulty)
            if p is None:
                result.mastery_unscored += 1  # DKT không chấm được -> giữ nguyên
                continue
            ks.mastery, ks.last_updated = float(p), now
            result.mastery_updated += 1


def _fix_schedules(db: Session, undone: dict[tuple[int, int], int], result: FixResult) -> None:
    """Gỡ phần co nửa đời của các lượt sai giả, đặt lại lịch từ lượt ôn cuối."""
    shrink = config_service.get_float("half_life_shrink")
    for (user_id, item_id), k in undone.items():
        rs = db.execute(select(ReviewSchedule).where(
            ReviewSchedule.user_id == user_id, ReviewSchedule.item_id == item_id)).scalar_one_or_none()
        if rs is None or rs.half_life_days is None:
            continue
        last_at = db.execute(
            select(func.max(Interaction.answered_at))
            .join(StudySession, StudySession.id == Interaction.session_id)
            .where(Interaction.user_id == user_id, Interaction.item_id == item_id,
                   StudySession.practice_only.is_(False))
        ).scalar_one()
        h = max(MIN_HALF_LIFE_DAYS, min(MAX_HALF_LIFE_DAYS, rs.half_life_days / (shrink ** k)))
        interval = half_life_to_interval_days(h)
        rs.half_life_days, rs.interval_days = h, interval
        rs.next_review_at = (last_at or datetime.now(timezone.utc)) + timedelta(days=interval)
        result.schedules_fixed += 1


def fix(db: Session, until: datetime, since: datetime = DEFAULT_SINCE) -> FixResult:
    if until.tzinfo is None or since.tzinfo is None:
        raise ValueError("since/until phải kèm múi giờ, ví dụ 2026-10-27T09:30+07:00")
    result = FixResult(since=since, until=until)
    rows = db.execute(
        select(Interaction, Item, StudySession, User.display_name)
        .join(Item, Item.id == Interaction.item_id)
        .join(User, User.id == Interaction.user_id)
        .outerjoin(StudySession, StudySession.id == Interaction.session_id)
        .where(Interaction.answered_at >= since, Interaction.answered_at < until,
               Interaction.exercise_format.in_(FORMATS),
               Interaction.is_correct.is_(False),
               Interaction.excluded_reason.is_(None))
        .order_by(Interaction.answered_at)
    ).all()

    undone: dict[tuple[int, int], int] = Counter()   # (user, item) -> số lần co cần gỡ
    users: set[int] = set()
    for it, item, session, name in rows:
        if not is_multi_sense(item.meaning):
            continue  # từ một nghĩa vẫn được chấm đúng trong lúc lỗi
        answer = _recover_answer(db, it, item)
        if answer is not None and not _is_meaning_answer(answer, item.meaning):
            result.recovered_wrong.append(it.id)  # sai thật — giữ nguyên
            continue
        if answer is not None:
            it.is_correct = True
            result.recovered_correct.append(it.id)
        else:
            it.excluded_reason = REASON
            result.excluded.append(it.id)
        result.by_user[name] += 1
        users.add(it.user_id)
        if session is not None and not session.practice_only:
            undone[(it.user_id, it.item_id)] += 1

    db.flush()
    # Số câu đúng của phiên (lịch sử học) theo dữ liệu đã sửa.
    touched_sessions = {it.session_id for it, *_ in rows if it.id in set(result.recovered_correct)}
    for sid in touched_sessions:
        s = db.get(StudySession, sid)
        s.correct_count = db.execute(select(func.count()).where(
            Interaction.session_id == sid, Interaction.is_correct.is_(True))).scalar_one()
    db.flush()

    for user_id in users:
        _recompute_mastery(db, user_id, since, result)
    _fix_schedules(db, undone, result)
    return result


def _print(result: FixResult, apply: bool) -> None:
    vn = timezone(timedelta(hours=7))
    print("ĐÃ GHI" if apply else "CHẠY THỬ — chưa ghi gì (thêm --apply để ghi)")
    print(f"  Khoảng lỗi (giờ VN): {result.since.astimezone(vn):%Y-%m-%d %H:%M} -> {result.until.astimezone(vn):%Y-%m-%d %H:%M}")
    print(f"  Khôi phục từ request_hash : {len(result.recovered_correct) + len(result.recovered_wrong)}"
          f" (đúng {len(result.recovered_correct)}, sai thật {len(result.recovered_wrong)})")
    print(f"  Đánh dấu loại trừ         : {len(result.excluded)}  [{REASON}]")
    print(f"  Mastery tính lại          : {result.mastery_updated} (DKT không chấm được, giữ nguyên: {result.mastery_unscored})")
    print(f"  Lịch ôn đã gỡ phần co     : {result.schedules_fixed}")
    print("  Theo người học:")
    for name, n in result.by_user.most_common():
        print(f"    {name}: {n}")


def main() -> None:
    from app.core.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="ghi thật (mặc định chỉ chạy thử)")
    parser.add_argument("--since", type=datetime.fromisoformat, default=DEFAULT_SINCE,
                        help="mốc bắt đầu lỗi, ISO có múi giờ (mặc định 2026-10-26T18:00+07:00)")
    parser.add_argument("--until", type=datetime.fromisoformat, default=None,
                        help="lúc bản sửa lên pilot, ISO có múi giờ (bắt buộc)")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.until is None:
            hint = find_fix_time(db, args.since)
            vn = timezone(timedelta(hours=7))
            print("Thiếu --until (lúc bản sửa lên pilot).")
            print("  Gợi ý từ dữ liệu — lượt chọn nghĩa đúng đầu tiên của từ nhiều nghĩa: "
                  + (f"{hint.astimezone(vn):%Y-%m-%dT%H:%M}+07:00" if hint else "chưa có (bản sửa chưa lên hoặc chưa ai học)"))
            raise SystemExit(2)
        result = fix(db, until=args.until, since=args.since)
        if args.apply:
            db.commit()
        else:
            db.rollback()
    _print(result, args.apply)


if __name__ == "__main__":
    from app.scripts._console import use_utf8_console

    use_utf8_console()
    main()
