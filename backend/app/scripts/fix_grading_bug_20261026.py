"""Sửa dữ liệu sau sự cố chấm sai trắc nghiệm (2026-10-26).

    python -m app.scripts.fix_grading_bug_20261026 --until 2026-10-27T08:00:20+07:00            # chạy thử
    python -m app.scripts.fix_grading_bug_20261026 --until 2026-10-27T08:00:20+07:00 --apply    # ghi thật

`--until` = lúc bản sửa lên pilot. BẮT BUỘC khai tường minh: lượt sau mốc đó được
chấm bằng code đã sửa, khai muộn là loại nhầm dữ liệu thật. Thiếu `--until` thì
script in mốc dò được từ dữ liệu để đối chiếu rồi dừng. Mốc thật trên pilot: bản
sao lưu trước khi cập nhật lúc 07:55 ngày 27/10; lượt trắc nghiệm sai cuối cùng
của đợt lỗi lúc 08:00:16, từ 08:00:21 chấm đúng trở lại -> 08:00:20+07:00.

Sự cố: commit 1ad9af0 đổi phương án trắc nghiệm/ghép cặp sang hiện NGHĨA CHÍNH
(`answer_label`), nhưng server vẫn chấm `answer == item.meaning` (nghĩa đầy đủ).

PHẠM VI THẬT RỘNG HƠN "từ nhiều nghĩa" (bản đầu của script chỉ xử lý nhóm đó).
Đo trên bản sao lưu 27/10 12:57, CÙNG một người học, trắc nghiệm của từ MỘT nghĩa:
user 12 95% -> 40%, user 9 89% -> 32%, user 11 76% -> 33% trong khoảng lỗi, rồi về
83-94% sau bản sửa; dạng gõ từ của chính họ không đổi. Lượt `quiz` lại KHÔNG có
`request_hash` (client trắc nghiệm không gửi `client_answer_id`), nên không có
cách nào biết người học đã chọn gì.

Script làm, trong MỘT giao dịch (chạy thử thì rollback), với MỌI lượt `quiz`/
`matching` trong khoảng lỗi chưa bị loại — đúng lẫn sai, một nghĩa lẫn nhiều nghĩa:

1. Lượt còn `request_hash`: khôi phục đáp án THẬT (thử mọi nghĩa trong bộ từ của
   từ đó cho tới khi băm khớp) và chấm lại. KHÔNG dò rộng ra nghĩa của mọi bộ từ:
   đã thử, và nó trả về đáp án vô lý cho lượt đang ghi đúng ("vải chéo" cho
   *say*) — chưa giải thích được nên không tin.
2. Lượt không khôi phục được -> `excluded_reason = 'grading_bug_2026-10-26'`, KỂ CẢ
   lượt đang ghi ĐÚNG. Lý do: lỗi chỉ sinh ra "sai giả", nên nếu chỉ loại lượt sai
   thì phần còn lại của khoảng lỗi gần như toàn đúng — lệch nhãn có hệ thống, làm
   hỏng cả đầu vào DKT lẫn số đo kiểm chứng. KHÔNG xóa (BR-05), KHÔNG đoán lại.
3. Tính lại số câu đúng của các phiên bị đụng.
4. Tính lại mastery bằng DKT trên lịch sử đã sạch cho mọi KnowledgeState của người
   học bị ảnh hưởng được cập nhật từ lúc lỗi (DKT là mô hình chuỗi: một lượt sai
   giả lệch trạng thái ẩn của MỌI từ sau nó).
5. Lịch ôn (chỉ lượt trong phiên không phải "luyện thường"): gỡ tác động của từng
   lượt bị loại/sửa lên nửa đời — lượt sai: chia lại `half_life_shrink`; lượt
   đúng bị loại: chia lại `half_life_growth * (0.5 + mastery)`. Mastery SAU lượt đó
   không được lưu nên dùng `predicted_mastery` (ngay TRƯỚC lượt đó) làm xấp xỉ.
   Nửa đời từng chạm sàn/trần thì phần bị cắt không còn biết. Sau đó đặt
   `next_review_at` tính từ lượt ôn cuối của cặp đó.

Chạy lại được, và chạy được SAU bản đầu của script: lượt đã loại thì bỏ qua; lượt
đã được bản đầu sửa thành đúng thì khôi phục lại ra cùng kết quả, không gỡ lịch
lần hai.
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
#: tiên 18:05. Lấy mốc tròn trước đó.
DEFAULT_SINCE = datetime(2026, 10, 26, 11, 0, tzinfo=timezone.utc)  # 18:00 giờ VN
FORMATS = ("quiz", "matching")


def is_multi_sense(meaning: str | None) -> bool:
    """Từ mà phương án hiển thị khác nghĩa đầy đủ. Chỉ còn dùng để gợi ý mốc
    `--until` và để thống kê — KHÔNG còn là điều kiện chọn lượt cần sửa."""
    return answer_label(meaning or "") != " ".join((meaning or "").split())


@dataclass
class FixResult:
    since: datetime
    until: datetime
    recovered_correct: list[int] = field(default_factory=list)   # sai giả -> đúng
    recovered_same: list[int] = field(default_factory=list)      # khôi phục, kết quả giữ nguyên
    excluded_wrong: list[int] = field(default_factory=list)
    excluded_correct: list[int] = field(default_factory=list)
    by_user: Counter = field(default_factory=Counter)
    sessions_fixed: int = 0
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


def _matches(it: Interaction, answer: str) -> bool:
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
                    return True
    return False


def _recover_answer(db: Session, it: Interaction, item: Item) -> str | None:
    """Đáp án người học đã gửi, suy ngược từ `request_hash`. None nếu không khớp."""
    if not it.request_hash or not it.client_answer_id:
        return None
    meanings = db.execute(select(Item.meaning).where(Item.word_set_id == item.word_set_id)).scalars()
    in_set = {c for m in meanings if m for c in (answer_label(m), m)}
    for answer in sorted(in_set):
        if _matches(it, answer):
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


def _fix_schedules(db: Session, factor: dict[tuple[int, int], float], result: FixResult) -> None:
    """Nhân nửa đời với hệ số gỡ tác động của các lượt bị loại/sửa, đặt lại lịch."""
    for (user_id, item_id), f in factor.items():
        rs = db.execute(select(ReviewSchedule).where(
            ReviewSchedule.user_id == user_id, ReviewSchedule.item_id == item_id)).scalar_one_or_none()
        if rs is None or rs.half_life_days is None:
            continue
        last_at = db.execute(
            select(func.max(Interaction.answered_at))
            .join(StudySession, StudySession.id == Interaction.session_id)
            .where(Interaction.user_id == user_id, Interaction.item_id == item_id,
                   Interaction.excluded_reason.is_(None),
                   StudySession.practice_only.is_(False))
        ).scalar_one()
        h = max(MIN_HALF_LIFE_DAYS, min(MAX_HALF_LIFE_DAYS, rs.half_life_days * f))
        interval = half_life_to_interval_days(h)
        rs.half_life_days, rs.interval_days = h, interval
        rs.next_review_at = (last_at or datetime.now(timezone.utc)) + timedelta(days=interval)
        result.schedules_fixed += 1


def fix(db: Session, until: datetime, since: datetime = DEFAULT_SINCE) -> FixResult:
    if until.tzinfo is None or since.tzinfo is None:
        raise ValueError("since/until phải kèm múi giờ, ví dụ 2026-10-27T08:00:20+07:00")
    result = FixResult(since=since, until=until)
    rows = db.execute(
        select(Interaction, Item, StudySession, User.display_name)
        .join(Item, Item.id == Interaction.item_id)
        .join(User, User.id == Interaction.user_id)
        .outerjoin(StudySession, StudySession.id == Interaction.session_id)
        .where(Interaction.answered_at >= since, Interaction.answered_at < until,
               Interaction.exercise_format.in_(FORMATS),
               Interaction.excluded_reason.is_(None))
        .order_by(Interaction.answered_at)
    ).all()

    shrink = config_service.get_float("half_life_shrink")
    growth = config_service.get_float("half_life_growth")
    factor: dict[tuple[int, int], float] = defaultdict(lambda: 1.0)  # (user, item) -> hệ số gỡ
    users: set[int] = set()
    touched_sessions: set[int] = set()
    for it, item, session, name in rows:
        affects_schedule = session is not None and not session.practice_only
        answer = _recover_answer(db, it, item)
        truth = _is_meaning_answer(answer, item.meaning) if answer is not None else None
        if truth is not None and truth == it.is_correct:
            result.recovered_same.append(it.id)  # chấm đúng từ đầu — giữ nguyên
            continue
        if truth is True:
            it.is_correct = True
            result.recovered_correct.append(it.id)
            if affects_schedule:
                factor[(it.user_id, it.item_id)] /= shrink
        else:
            # Không khôi phục được, HOẶC khôi phục ra "sai" cho lượt đang ghi đúng
            # (lỗi này không sinh ra ca đó -> dữ liệu mâu thuẫn): loại, không đoán.
            was_correct = it.is_correct
            it.excluded_reason = REASON
            (result.excluded_correct if was_correct else result.excluded_wrong).append(it.id)
            if affects_schedule:
                if was_correct:
                    m = it.predicted_mastery if it.predicted_mastery is not None else 0.5
                    factor[(it.user_id, it.item_id)] /= growth * (0.5 + m)
                else:
                    factor[(it.user_id, it.item_id)] /= shrink
        result.by_user[name] += 1
        users.add(it.user_id)
        if it.session_id is not None:
            touched_sessions.add(it.session_id)

    db.flush()
    # Số câu đúng của phiên (lịch sử học) theo dữ liệu đã sửa: chỉ đếm lượt hợp lệ.
    for sid in touched_sessions:
        s = db.get(StudySession, sid)
        s.correct_count = db.execute(select(func.count()).where(
            Interaction.session_id == sid, Interaction.is_correct.is_(True),
            Interaction.excluded_reason.is_(None))).scalar_one()
        result.sessions_fixed += 1
    db.flush()

    for user_id in users:
        _recompute_mastery(db, user_id, since, result)
    _fix_schedules(db, factor, result)
    return result


def _print(result: FixResult, apply: bool) -> None:
    vn = timezone(timedelta(hours=7))
    print("ĐÃ GHI" if apply else "CHẠY THỬ — chưa ghi gì (thêm --apply để ghi)")
    print(f"  Khoảng lỗi (giờ VN): {result.since.astimezone(vn):%Y-%m-%d %H:%M:%S} -> {result.until.astimezone(vn):%Y-%m-%d %H:%M:%S}")
    print(f"  Khôi phục từ request_hash : sửa sai giả -> đúng {len(result.recovered_correct)},"
          f" giữ nguyên {len(result.recovered_same)}")
    print(f"  Đánh dấu loại trừ         : {len(result.excluded_wrong) + len(result.excluded_correct)}"
          f" (đang ghi sai {len(result.excluded_wrong)}, đang ghi đúng {len(result.excluded_correct)})  [{REASON}]")
    print(f"  Phiên tính lại số câu đúng: {result.sessions_fixed}")
    print(f"  Mastery tính lại          : {result.mastery_updated} (DKT không chấm được, giữ nguyên: {result.mastery_unscored})")
    print(f"  Lịch ôn đã gỡ tác động    : {result.schedules_fixed}")
    print("  Theo người học (số lượt bị sửa/loại):")
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
                  + (f"{hint.astimezone(vn):%Y-%m-%dT%H:%M:%S}+07:00" if hint else "chưa có (bản sửa chưa lên hoặc chưa ai học)"))
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
