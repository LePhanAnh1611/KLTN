from datetime import datetime, timezone
import hashlib
import logging

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.session import StudySession
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.session import (
    OBJECTIVE_CHECK_MODES,
    OBJECTIVE_FORMATS,
    ActiveSessionResponse,
    AnswerRequest,
    ResumableSession,
    SessionCreateRequest,
    SessionHistoryResponse,
    SessionHistoryRow,
    SessionResponse,
    SessionSummary,
    WrongItem,
)
from app.services import (
    achievement_service,
    gamification_service,
    level_up_service,
    mastery_service,
    review_service,
    sm2_service,
    game_service,
)
from app.services.mastery_service import mastered_condition
from app.services.quiz_service import answer_label
from app.services.word_set_service import get_owned_word_set

logger = logging.getLogger(__name__)

#: Pilot — phiên bài kiểm tra cuối (do validation_service tạo, không mở qua API
#: tạo phiên thường).
VALIDATION_MODE = "validation"


def _get_owned_session(db: Session, user: User, session_id: int) -> StudySession:
    session = db.execute(
        select(StudySession).where(StudySession.id == session_id)
        .with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy phiên")
    return session


def _cross_library_scope(mode: str):
    """Phạm vi "cùng loại" của phiên xuyên thư viện (word_set_id = NULL).

    Ôn theo lịch / ôn từ yếu dùng chung một phạm vi như trước. "Học từ mới" mở
    từ trang chủ là phạm vi RIÊNG: mở nó không được bỏ dở phiên ôn đang làm, và
    ngược lại.
    """
    same_kind = (
        StudySession.mode == "dkt_smart" if mode == "dkt_smart"
        else StudySession.mode != "dkt_smart"
    )
    return and_(StudySession.word_set_id.is_(None), same_kind)


def create_session(db: Session, user: User, data: SessionCreateRequest) -> SessionResponse:
    if data.word_set_id is not None:
        get_owned_word_set(db, user, data.word_set_id)  # xác thực sở hữu bộ từ

    # phiên dở dang cũ cùng phạm vi (cùng bộ, hoặc cùng srs xuyên thư viện) → bỏ (alt 3a UC-31)
    stale_filter = (
        StudySession.word_set_id == data.word_set_id
        if data.word_set_id is not None
        else _cross_library_scope(data.mode)
    )
    stale = db.execute(
        select(StudySession).where(
            StudySession.user_id == user.id,
            stale_filter,
            StudySession.status == "in_progress",
            # bài kiểm tra cuối không bị phiên ôn xuyên thư viện "đè" mất
            StudySession.mode.is_distinct_from(VALIDATION_MODE),
        ).order_by(StudySession.id).with_for_update().execution_options(populate_existing=True)
    ).scalars().all()
    for s in stale:
        _abandon(db, s)

    session = StudySession(
        user_id=user.id,
        word_set_id=data.word_set_id,
        mode=data.mode,
        practice_only=data.practice_only,
        status="in_progress",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionResponse.model_validate(session)


def _has_answers():
    """Phiên chỉ tính là "đang dở" khi đã có ít nhất một câu trả lời.

    Màn học tạo phiên ngay khi mở (trước câu đầu tiên). Người học mở rồi thoát
    ra thì phiên vẫn `in_progress` với 0 Interaction — không có tiến độ gì để
    giữ, nên không hỏi "học tiếp" (hiện "Đã làm 0 từ" là sai). Lần mở sau,
    `create_session` sẽ tự bỏ phiên rỗng đó như mọi phiên cũ cùng phạm vi.
    """
    return select(Interaction.id).where(
        Interaction.session_id == StudySession.id
    ).exists()


def get_active_session(
    db: Session, user: User, word_set_id: int | None, mode: str | None = None
) -> ActiveSessionResponse:
    """Phiên dở của một bộ; hoặc, khi không có bộ, phiên dở xuyên thư viện của `mode`."""
    scope = (
        StudySession.word_set_id == word_set_id
        if word_set_id is not None
        else and_(StudySession.word_set_id.is_(None), StudySession.mode == mode)
    )
    session = db.execute(
        select(StudySession)
        .where(
            StudySession.user_id == user.id,
            scope,
            StudySession.status == "in_progress",
            _has_answers(),
        )
        .order_by(StudySession.started_at.desc())
    ).scalars().first()

    if session is None:
        return ActiveSessionResponse(session=None, answered_item_ids=[])

    answered = db.execute(
        select(Interaction.item_id).where(Interaction.session_id == session.id).distinct()
    ).scalars().all()
    return ActiveSessionResponse(
        session=SessionResponse.model_validate(session), answered_item_ids=list(answered)
    )


def _exercise_format(session: StudySession, data: AnswerRequest) -> str:
    """Dạng bài THẬT của lượt này, dùng làm đặc trưng cho DKT.

    Với phiên trò chơi (UC-94), dạng bài do SERVER quyết định chứ không lấy theo
    client. Lý do: mô hình chỉ được huấn luyện trên một tập mã dạng bài hữu hạn;
    gửi 'game_rain' vào thì `format_code` trả mã "other" — một mã chưa từng được
    huấn luyện. API vẫn 200, mastery vẫn có số, chỉ là sai, và không có lỗi nào
    hiện ra. Đây đúng kiểu lệch âm thầm đã hai lần làm hỏng số đo của đề tài.
    """
    game_format = game_service.exercise_format_for_mode(session.mode)
    if game_format:
        return game_format
    if session.mode == VALIDATION_MODE:
        return "typing"  # bài kiểm tra cuối luôn là gõ từ — không đoán mò được
    if session.mode in OBJECTIVE_CHECK_MODES and data.exercise_format in OBJECTIVE_FORMATS:
        # Thẻ lật có kèm câu hỏi chấm khách quan: dạng bài THẬT là câu hỏi đó.
        return data.exercise_format
    if session.mode == "mixed":
        if data.exercise_format not in {"quiz", "typing", "dictation", "cloze", "matching"}:
            raise HTTPException(status_code=422, detail="Phiên trộn cần dạng bài cụ thể của lượt trả lời")
        return data.exercise_format
    return session.mode or "flashcard"


def _selection_reason(session: StudySession, data: AnswerRequest) -> str | None:
    """Vì sao từ này được đưa ra — để tách lượt KHÔNG thiên lệch khi phân tích.

    Chỉ phiên 'Học thông minh' mới tin giá trị client gửi (client nhận nó từ
    /recommend); các chế độ khác lý do đã rõ theo chế độ nên server tự gán.
    """
    if session.mode == VALIDATION_MODE:
        return "validation"
    if session.mode in {"srs_review", "weak_review"}:
        return "review"
    if session.mode == "dkt_smart":
        return data.selection_reason
    return None


def _is_meaning_answer(answer: str, meaning: str) -> bool:
    """Đáp án chọn nghĩa có khớp nghĩa của từ không.

    Phương án trắc nghiệm/ghép cặp hiển thị `answer_label(meaning)` — chỉ nghĩa
    chính — nên client gửi lên đúng chuỗi đó chứ không phải nghĩa đầy đủ. So với
    `item.meaning` nguyên văn thì mọi từ có nhiều nghĩa ("số liệu, dữ liệu") đều
    bị chấm sai dù người học chọn đúng. Vẫn nhận nghĩa đầy đủ để client cũ không gãy.
    """
    given = " ".join(answer.split())
    if not given:
        return False
    return given in {" ".join((meaning or "").split()), answer_label(meaning)}


def _grade_answer(session: StudySession, item: Item, data: AnswerRequest, fmt: str) -> bool:
    if data.sm2_rating is not None and session.mode != "sm2":
        raise HTTPException(status_code=422, detail="Đánh giá SM-2 chỉ dùng trong phiên SM-2")
    if fmt in {"quiz", "matching", "typing", "dictation", "cloze"}:
        if data.answer is None:
            raise HTTPException(status_code=422, detail="Cần gửi đáp án để hệ thống chấm bài")
        if fmt in {"quiz", "matching"}:
            return _is_meaning_answer(data.answer, item.meaning)
        expected = item.word.strip().lower()
        return bool(expected) and data.answer.strip().lower() == expected
    if session.mode == "sm2" and data.sm2_rating is not None:
        return data.sm2_rating != "again"
    if data.is_correct is None:
        raise HTTPException(status_code=422, detail="Cần đánh giá kết quả của thẻ từ")
    return data.is_correct


def record_answer(db: Session, user: User, session_id: int, data: AnswerRequest) -> None:
    session = _get_owned_session(db, user, session_id)
    request_hash = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    answer_id = str(data.client_answer_id) if data.client_answer_id else None
    if answer_id:
        existing = db.execute(select(Interaction).where(
            Interaction.session_id == session_id, Interaction.client_answer_id == answer_id,
        )).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise HTTPException(status_code=409, detail="Mã lượt trả lời đã dùng cho nội dung khác")
            return  # A lost response can be retried even after the session ends.
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Phiên đã kết thúc"
        )

    item = db.execute(select(Item).where(Item.id == data.item_id).with_for_update()
                      .execution_options(populate_existing=True)).scalar_one_or_none()
    invalid = item is None or item.deleted_at is not None
    if not invalid:
        if session.word_set_id is not None:
            get_owned_word_set(db, user, session.word_set_id)
            invalid = item.word_set_id != session.word_set_id  # phiên gắn 1 bộ
        else:
            # phiên SRS xuyên thư viện: item chỉ cần thuộc bộ user sở hữu (chưa xóa)
            owner = db.execute(
                select(WordSet.owner_id).where(
                    WordSet.id == item.word_set_id, WordSet.deleted_at.is_(None)
                )
            ).scalar_one_or_none()
            invalid = owner != user.id
    if not invalid and session.mode == VALIDATION_MODE:
        planned = (session.completion_summary or {}).get("planned_item_ids", [])
        invalid = item.id not in planned  # chỉ được trả lời đúng các câu đã bốc
    if invalid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Từ không thuộc phiên này")

    fmt = _exercise_format(session, data)
    is_correct = _grade_answer(session, item, data, fmt)

    # UC-70: hỏi DKT NGAY TRƯỚC khi ghi lượt này — lịch sử chưa gồm lượt hiện tại,
    # dạng bài là dạng bài thật của lượt này. Không đọc lại KNOWLEDGE_STATE: giá
    # trị đó tính từ lần gặp trước của từ này nên đã cũ (xem predict_before_answer).
    predicted, prediction_source = mastery_service.predict_before_answer(
        db, user.id, item, exercise_format=fmt
    )

    # BR-05: ghi INTERACTION đầy đủ cho mỗi lần trả lời
    db.add(
        Interaction(
            user_id=user.id,
            item_id=data.item_id,
            session_id=session_id,
            is_correct=is_correct,
            response_time_ms=data.response_time_ms,
            exercise_format=fmt,
            client_answer_id=answer_id,
            request_hash=request_hash if answer_id else None,
            predicted_mastery=predicted,
            prediction_source=prediction_source,
            selection_reason=_selection_reason(session, data),
            answered_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    # UC-64: cập nhật mastery qua DKT (best-effort, đã gồm lịch sử vừa ghi).
    # AI lỗi/từ ngoài vocab -> bỏ qua, không ảnh hưởng interaction đã lưu.
    # Dạng bài của chính lượt vừa trả lời — mô hình dùng làm đặc trưng, và nó
    # biết trước nên không phải thông tin từ tương lai.
    mastery = mastery_service.update_mastery_for_item(
        db, user, item, exercise_format=fmt
    )

    # UC-35 — phiên "luyện thường": dừng ở đây, KHÔNG chạm vào lịch ôn.
    #
    # Lưu ý mastery VẪN đổi ở trên và đó là cố ý: DKT suy luận từ toàn bộ lịch sử
    # trả lời (BR-05 buộc ghi mọi lượt), nên nếu không cập nhật thì con số mastery
    # đang lưu sẽ lệch khỏi chính dữ liệu sinh ra nó. Thứ được giữ nguyên là
    # next_review_at — đúng nghĩa "luyện tự do không ảnh hưởng lịch".
    if session.practice_only:
        return

    # Lập lịch ôn:
    # - có sm2_rating (UC-34 baseline) -> SM-2 (cổ điển, không dùng DKT)
    # - ngược lại -> mastery-based (UC-66, DKT)
    try:
        if data.sm2_rating is not None:
            sm2_service.schedule_review_sm2(db, user.id, item.id, data.sm2_rating)
        elif mastery is not None:
            # Truyền kết quả THẬT của lượt này: luật mới giãn hay co nửa đời tùy
            # đúng/sai, và suy ngược từ mastery sẽ sai ở đúng ca đáng lo nhất —
            # một từ mastery còn cao mà người học vừa trả lời sai.
            review_service.schedule_review(
                db, user.id, item.id, mastery, is_correct=is_correct
            )
    except Exception:
        db.rollback()
        logger.exception("Could not schedule review for session %s item %s", session_id, item.id)


def complete_session(db: Session, user: User, session_id: int) -> SessionSummary:
    session = _get_owned_session(db, user, session_id)
    if session.status == "completed" and session.completion_summary:
        return SessionSummary.model_validate(session.completion_summary)
    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Phiên đã kết thúc"
        )

    interactions = db.execute(
        select(Interaction).where(Interaction.session_id == session_id)
    ).scalars().all()

    total = len(interactions)
    correct = sum(1 for i in interactions if i.is_correct)
    wrong = total - correct

    now = datetime.now(timezone.utc)
    session.status = "completed"
    session.ended_at = now
    session.item_count = total
    session.correct_count = correct

    wrong_item_ids = {i.item_id for i in interactions if not i.is_correct}
    wrong_items: list[WrongItem] = []
    if wrong_item_ids:
        items = db.execute(
            select(Item).where(Item.id.in_(wrong_item_ids))
        ).scalars().all()
        wrong_items = [
            WrongItem(item_id=it.id, word=it.word, meaning=it.meaning) for it in items
        ]

    # UC-30: số từ trong phiên đã đạt "thuộc" (mastery >= ngưỡng BR-01)
    session_item_ids = {i.item_id for i in interactions}
    mastered_count = 0
    if session_item_ids:
        mastered_count = db.execute(
            select(func.count())
            .select_from(KnowledgeState)
            .where(
                KnowledgeState.user_id == user.id,
                KnowledgeState.item_id.in_(session_item_ids),
                mastered_condition(),
            )
        ).scalar_one()

    duration = int((now - session.started_at).total_seconds())
    # UC-46/47: cấp XP + cập nhật streak (UC-30 E1: phiên rỗng -> bỏ qua XP)
    xp_earned = 0
    streak_count = 0
    streak_extended = False
    new_achievements: list[str] = []
    if total > 0:
        award = gamification_service.award_session(db, user, session, commit=False)
        xp_earned = award.xp_earned
        streak_count = award.streak_count
        streak_extended = award.streak_extended
        new_achievements = achievement_service.check_and_unlock(db, user, commit=False)
    summary = SessionSummary(
        session_id=session_id,
        total_answered=total,
        correct_count=correct,
        wrong_count=wrong,
        accuracy=(correct / total) if total > 0 else 0.0,
        duration_seconds=max(duration, 0),
        mastered_count=mastered_count,
        xp_earned=xp_earned,
        streak_count=streak_count,
        streak_extended=streak_extended,
        new_achievements=new_achievements,
        wrong_items=wrong_items,
    )
    # The receipt, completion and XP become durable together. Retrying must
    # return this receipt rather than award again or rebuild changing statistics.
    session.completion_summary = summary.model_dump(mode="json")
    db.commit()
    if total > 0:
        try:
            level_up_service.evaluate_after_session(db, user)
        except Exception:
            db.rollback()
            logger.exception("Could not evaluate level-up for session %s", session_id)
    return summary


def _abandon(db: Session, session: StudySession) -> None:
    total, correct = db.execute(select(
        func.count(Interaction.id),
        func.count(Interaction.id).filter(Interaction.is_correct.is_(True)),
    ).where(Interaction.session_id == session.id)).one()
    session.item_count = total
    session.correct_count = correct
    session.status = "abandoned"
    session.ended_at = datetime.now(timezone.utc)


def abandon_session(db: Session, user: User, session_id: int) -> None:
    session = _get_owned_session(db, user, session_id)
    if session.status == "in_progress":
        _abandon(db, session)
        db.commit()


def get_history(
    db: Session, user: User, *, page: int = 1, page_size: int = 20, mode: str | None = None
) -> SessionHistoryResponse:
    """UC-45 — nhật ký học tập, phiên mới nhất lên đầu.

    Chỉ liệt kê phiên ĐÃ KẾT THÚC (completed/abandoned): phiên đang mở chưa có
    số liệu chốt, và nó đã hiện ở chỗ khác dưới dạng "bài học đang dở".

    Tổng hợp (số phiên, số từ, XP) tính trên toàn bộ lịch sử chứ không phải trang
    hiện tại — người học muốn biết tổng công sức, không phải tổng của 20 dòng.
    """
    base = (
        select(StudySession)
        .where(StudySession.user_id == user.id, StudySession.status != "in_progress")
    )
    if mode:
        base = base.where(StudySession.mode == mode)

    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    historical_count = select(func.count(Interaction.id)).where(
        Interaction.session_id == StudySession.id,
    ).correlate(StudySession).scalar_subquery()
    agg = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(case(
                (StudySession.status == "abandoned", historical_count),
                else_=StudySession.item_count,
            )), 0),
            func.coalesce(func.sum(StudySession.xp_earned), 0),
        ).where(
            StudySession.user_id == user.id,
            StudySession.status != "in_progress",
            *([StudySession.mode == mode] if mode else []),
        )
    ).one()

    rows = db.execute(
        base.order_by(StudySession.started_at.desc(), StudySession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()

    # Include historical abandoned sessions created before counters were fixed.
    abandoned_ids = [s.id for s in rows if s.status == "abandoned"]
    abandoned_counts = {}
    if abandoned_ids:
        abandoned_counts = {
            sid: (total, correct) for sid, total, correct in db.execute(select(
                Interaction.session_id, func.count(Interaction.id),
                func.count(Interaction.id).filter(Interaction.is_correct.is_(True)),
            ).where(Interaction.session_id.in_(abandoned_ids)).group_by(Interaction.session_id)).all()
        }
    # Tên bộ từ cho các phiên gắn bộ (phiên xuyên thư viện để None)
    set_ids = {s.word_set_id for s in rows if s.word_set_id is not None}
    names: dict[int, str] = {}
    if set_ids:
        names = dict(db.execute(
            select(WordSet.id, WordSet.name).where(WordSet.id.in_(set_ids))
        ).all())

    items = []
    for s in rows:
        answered = s.item_count or 0
        correct = s.correct_count or 0
        if s.status == "abandoned":
            answered, correct = abandoned_counts.get(s.id, (0, 0))
        duration = (
            int((s.ended_at - s.started_at).total_seconds()) if s.ended_at else None
        )
        items.append(SessionHistoryRow(
            id=s.id, mode=s.mode, status=s.status,
            word_set_id=s.word_set_id,
            word_set_name=names.get(s.word_set_id) if s.word_set_id else None,
            started_at=s.started_at, ended_at=s.ended_at,
            item_count=answered, correct_count=correct,
            accuracy=(correct / answered) if answered else 0.0,
            xp_earned=s.xp_earned or 0,
            duration_seconds=max(duration, 0) if duration is not None else None,
        ))

    return SessionHistoryResponse(
        items=items, total=total, page=page, page_size=page_size,
        total_sessions=agg[0], total_items_answered=agg[1], total_xp=agg[2],
    )


def get_resumable(db: Session, user: User) -> ResumableSession | None:
    """UC-31 — phiên đang dở gần nhất, không cần biết trước là bộ nào.

    Khác `get_active_session`: hàm kia phải biết word_set_id (dùng khi đã mở màn
    học của một bộ). Trang chủ thì chưa biết gì cả, nên cần bản quét toàn bộ.
    """
    session = db.execute(
        select(StudySession)
        .where(
            StudySession.user_id == user.id, StudySession.status == "in_progress",
            # bài kiểm tra cuối có lối vào riêng, không hiện như "bài học đang dở"
            StudySession.mode.is_distinct_from(VALIDATION_MODE),
            _has_answers(),
        )
        .order_by(StudySession.started_at.desc(), StudySession.id.desc())
    ).scalars().first()
    if session is None:
        return None

    answered = db.execute(
        select(func.count(func.distinct(Interaction.item_id)))
        .where(Interaction.session_id == session.id)
    ).scalar_one()

    name = None
    if session.word_set_id is not None:
        name = db.execute(
            select(WordSet.name).where(WordSet.id == session.word_set_id)
        ).scalar_one_or_none()

    return ResumableSession(
        session_id=session.id, mode=session.mode,
        word_set_id=session.word_set_id, word_set_name=name,
        started_at=session.started_at, answered_count=answered,
    )
