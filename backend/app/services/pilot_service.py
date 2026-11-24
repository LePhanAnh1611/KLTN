"""Pilot — theo dõi đợt thử nghiệm và báo khi đã đủ dữ liệu để calibrate DKT.

Trả lời ba câu hỏi người làm khóa luận cần biết mỗi ngày:
1. Hôm nay có bao nhiêu người học, ai đang bỏ dở (để nhắn nhắc)?
2. Dữ liệu có "sạch" không — tỉ lệ lượt có dự đoán thật của DKT
   (thấp bất thường nghĩa là ml-serve đang tắt và dữ liệu đang hỏng)?
3. Đã đủ dữ liệu để kiểm chứng/hiệu chuẩn chưa (4 điều kiện bên dưới)?

Chỉ tính người dùng vai trò `learner` (bỏ admin/tài khoản quản trị) và chỉ tính
từ `PILOT_START_DATE` nếu có đặt — dữ liệu chạy thử trước đó không lẫn vào.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.interaction import Interaction, counted_interaction
from app.models.placement import PlacementAttempt
from app.models.session import StudySession
from app.models.user import User
from app.schemas.pilot import PilotBin, PilotCriterion, PilotParticipant, PilotReport

logger = logging.getLogger(__name__)

# ---- Điều kiện "đủ dữ liệu" (giải thích chi tiết trong `_criteria`) ----
TARGET_ACTIVE_USERS = 12        # số người học đủ ...
MIN_ACTIVE_DAYS = 5             # ... ít nhất bấy nhiêu ngày
TARGET_MODEL_ANSWERS = 4000     # số lượt có dự đoán thật của DKT
N_BINS = 10                     # số khoảng mastery khi kiểm tra độ phủ
TARGET_PER_BIN = 100            # số lượt tối thiểu mỗi khoảng
TARGET_GAP_ANSWERS = 1000       # số lượt ôn lại một từ sau một khoảng nghỉ ...
GAP_HOURS = 20                  # ... ít nhất bấy nhiêu giờ (≈ "hôm sau")
NUDGE_AFTER_DAYS = 2            # bỏ học bấy nhiêu ngày thì đánh dấu cần nhắc


def _zone() -> ZoneInfo:
    return ZoneInfo(settings.pilot_timezone)


def pilot_start() -> date | None:
    if not settings.pilot_start_date:
        return None
    return date.fromisoformat(settings.pilot_start_date)


def _start_utc() -> datetime | None:
    start = pilot_start()
    if start is None:
        return None
    return datetime.combine(start, datetime.min.time(), tzinfo=_zone()).astimezone(timezone.utc)


def _local_day(column):
    """Ngày theo giờ pilot của một cột timestamptz (Postgres `timezone()`)."""
    return cast(func.timezone(settings.pilot_timezone, column), Date)


def _interaction_filter() -> list:
    learners = select(User.id).where(User.role == "learner", User.deleted_at.is_(None))
    # Lượt bị loại (dữ liệu ghi sai) không được tính vào bất kỳ chỉ số pilot nào.
    conds = [Interaction.user_id.in_(learners), counted_interaction()]
    start = _start_utc()
    if start is not None:
        conds.append(Interaction.answered_at >= start)
    return conds


def _gap_answer_count(db: Session) -> int:
    """Lượt trả lời một từ mà lần gặp TRƯỚC của chính người đó cách ≥ GAP_HOURS.

    Đây là lượt đo được hiện tượng QUÊN — thứ khiến DKT khác một bảng đếm
    đúng/sai đơn thuần. Học dồn một buổi thì không có lượt nào loại này.
    """
    prev = func.lag(Interaction.answered_at).over(
        partition_by=(Interaction.user_id, Interaction.item_id),
        order_by=Interaction.answered_at,
    )
    seq = select(
        Interaction.answered_at.label("at"),
        prev.label("prev_at"),
        Interaction.prediction_source.label("src"),
    ).where(*_interaction_filter()).subquery()
    return db.execute(
        select(func.count()).select_from(seq).where(
            seq.c.prev_at.is_not(None),
            seq.c.at - seq.c.prev_at >= timedelta(hours=GAP_HOURS),
            seq.c.src == "model",
        )
    ).scalar_one()


def _bins(db: Session) -> list[PilotBin]:
    bucket = func.least(func.floor(Interaction.predicted_mastery * N_BINS), N_BINS - 1)
    rows = db.execute(
        select(
            bucket.label("b"), func.count(),
            func.avg(case((Interaction.is_correct.is_(True), 1.0), else_=0.0)),
        ).where(
            *_interaction_filter(),
            Interaction.prediction_source == "model",
            Interaction.predicted_mastery.is_not(None),
        ).group_by("b")
    ).all()
    by_bin = {int(b): (n, acc) for b, n, acc in rows}
    return [
        PilotBin(
            low=i / N_BINS, high=(i + 1) / N_BINS,
            count=by_bin.get(i, (0, None))[0],
            accuracy=None if i not in by_bin else round(float(by_bin[i][1]), 4),
        )
        for i in range(N_BINS)
    ]


def _criteria(
    active_users: int, model_answers: int, bins: list[PilotBin], gap_answers: int
) -> list[PilotCriterion]:
    bins_ok = sum(1 for b in bins if b.count >= TARGET_PER_BIN)
    return [
        PilotCriterion(
            key="active_users", target=TARGET_ACTIVE_USERS, current=active_users,
            met=active_users >= TARGET_ACTIVE_USERS,
            label=f"Số người học đủ ≥ {MIN_ACTIVE_DAYS} ngày",
            why="Ít người quá thì kết quả chỉ phản ánh vài cá nhân, không đáng tin.",
        ),
        PilotCriterion(
            key="model_answers", target=TARGET_MODEL_ANSWERS, current=model_answers,
            met=model_answers >= TARGET_MODEL_ANSWERS,
            label="Số câu trả lời có dự đoán của DKT",
            why="Mỗi câu là một cặp (DKT đoán, thực tế) - đủ nhiều mới so được.",
        ),
        PilotCriterion(
            key="bins", target=N_BINS, current=bins_ok, met=bins_ok >= N_BINS,
            label=f"Số khoảng mastery (0-10%, …, 90-100%) có ≥ {TARGET_PER_BIN} câu",
            why="Để kiểm chứng được cả từ DKT cho là khó lẫn từ cho là dễ.",
        ),
        PilotCriterion(
            key="gap_answers", target=TARGET_GAP_ANSWERS, current=gap_answers,
            met=gap_answers >= TARGET_GAP_ANSWERS,
            label=f"Số câu ôn lại một từ sau ≥ {GAP_HOURS} giờ",
            why="Để đo được hiện tượng quên - cần người học quay lại vào hôm sau.",
        ),
    ]


def build_report(db: Session, *, now: datetime | None = None) -> PilotReport:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(_zone()).date()
    start = pilot_start()
    conds = _interaction_filter()
    day = _local_day(Interaction.answered_at)

    learners = db.execute(
        select(User).where(User.role == "learner", User.deleted_at.is_(None)).order_by(User.id)
    ).scalars().all()

    per_user = {
        uid: (total, days, last, today_n)
        for uid, total, days, last, today_n in db.execute(
            select(
                Interaction.user_id,
                func.count(),
                func.count(func.distinct(day)),
                func.max(Interaction.answered_at),
                func.count().filter(day == today),
            ).where(*conds).group_by(Interaction.user_id)
        ).all()
    }
    placed = set(db.execute(select(PlacementAttempt.user_id).distinct()).scalars().all())
    validated = set(db.execute(
        select(StudySession.user_id).where(
            StudySession.mode == "validation", StudySession.status == "completed",
        ).distinct()
    ).scalars().all())

    people: list[PilotParticipant] = []
    for u in learners:
        total, days, last, today_n = per_user.get(u.id, (0, 0, None, 0))
        if last is not None:
            inactive = (today - last.astimezone(_zone()).date()).days
        else:
            inactive = None
        registered_day = u.created_at.astimezone(_zone()).date()
        nudge = (
            (inactive is not None and inactive >= NUDGE_AFTER_DAYS)
            or (inactive is None and (today - registered_day).days >= 1)
        )
        people.append(PilotParticipant(
            user_id=u.id, display_name=u.display_name, email=u.email,
            registered_at=u.created_at, placement_done=u.id in placed,
            active_days=days, answers_total=total, answers_today=today_n,
            last_active_at=last, days_inactive=inactive, needs_nudge=nudge,
            validation_done=u.id in validated,
        ))
    people.sort(key=lambda p: (-p.active_days, -p.answers_total))

    totals = db.execute(
        select(
            func.count(),
            func.count().filter(Interaction.prediction_source == "model"),
            func.count().filter(Interaction.selection_reason == "explore"),
            func.count().filter(day == today),
        ).where(*conds)
    ).one()
    answers_total, model_answers, explore_answers, answers_today = totals

    bins = _bins(db)
    criteria = _criteria(
        active_users=sum(1 for p in people if p.active_days >= MIN_ACTIVE_DAYS),
        model_answers=model_answers,
        bins=bins,
        gap_answers=_gap_answer_count(db),
    )
    return PilotReport(
        generated_at=now,
        pilot_start=start,
        pilot_day=(today - start).days + 1 if start else None,
        registered=len(learners),
        participants=sum(1 for p in people if p.answers_total > 0),
        active_today=sum(1 for p in people if p.answers_today > 0),
        answers_today=answers_today,
        answers_total=answers_total,
        model_share=round(model_answers / answers_total, 4) if answers_total else None,
        explore_answers=explore_answers,
        validation_done=len(validated & {u.id for u in learners}),
        criteria=criteria,
        ready=all(c.met for c in criteria),
        bins=bins,
        people=people,
    )


def _bar(current: int, target: int, width: int = 10) -> str:
    filled = min(width, round(width * current / target)) if target else width
    return "█" * filled + "░" * (width - filled)


def render_email(report: PilotReport) -> tuple[str, str]:
    """(tiêu đề, nội dung) email báo cáo hằng tối — văn bản thuần, đọc được trên điện thoại."""
    day_label = f"Ngày {report.pilot_day}" if report.pilot_day else report.generated_at.date().isoformat()
    met = sum(1 for c in report.criteria if c.met)
    if report.ready:
        subject = f"[LearningHub] ✅ ĐÃ ĐỦ DỮ LIỆU để calibrate — {day_label}"
    else:
        subject = (f"[LearningHub] {day_label}: {report.active_today} người học, "
                   f"{report.answers_today} câu — đạt {met}/{len(report.criteria)} điều kiện")

    lines = [
        f"BÁO CÁO PILOT — {day_label}",
        "",
        f"Hôm nay: {report.active_today} người học · {report.answers_today} câu trả lời",
        f"Tổng: {report.participants}/{report.registered} người đã học · {report.answers_total} câu",
    ]
    if report.model_share is not None:
        lines.append(f"Câu có dự đoán của DKT: {report.model_share:.0%}"
                     + ("  ⚠ THẤP — kiểm tra ml-serve!" if report.model_share < 0.8 else ""))
    lines += ["", "ĐIỀU KIỆN ĐỦ DỮ LIỆU:"]
    for c in report.criteria:
        mark = "✅" if c.met else "⬜"
        lines.append(f"{mark} {c.label}: {c.current}/{c.target}  {_bar(c.current, c.target)}")
    short = [f"{b.low:.0%}–{b.high:.0%} ({b.count})" for b in report.bins if b.count < TARGET_PER_BIN]
    if short:
        lines.append("   Khoảng mastery còn thiếu: " + ", ".join(short))

    if report.ready:
        lines += ["", "→ Đã đủ dữ liệu. Nhắn Claude: \"làm phân tích đi\"."]

    nudge = [p for p in report.people if p.needs_nudge]
    if nudge:
        lines += ["", "CẦN NHẮC:"]
        for p in nudge:
            why = ("chưa học lần nào" if p.days_inactive is None
                   else f"{p.days_inactive} ngày chưa vào")
            lines.append(f"- {p.display_name} ({p.email}): {why}")

    lines += ["", "TỪNG NGƯỜI (số ngày đã học · tổng câu · hôm nay):"]
    for p in report.people:
        lines.append(f"- {p.display_name}: {p.active_days} ngày · {p.answers_total} câu · "
                     f"{p.answers_today} hôm nay" + (" · đã làm bài cuối" if p.validation_done else ""))
    return subject, "\n".join(lines)


def write_report_files(report: PilotReport, directory: str | Path) -> Path:
    """Ghi báo cáo ra `latest.txt` + `latest.json` và một bản lưu theo ngày.

    Đây là kênh báo cáo chính của pilot: thư mục được mount ra máy host, một tác
    vụ hẹn giờ của Claude đọc `latest.*` mỗi tối và thông báo cho người chạy
    pilot. `generated_at` trong JSON cho phép bên đọc phát hiện báo cáo CŨ — tức
    là backend/scheduler đã ngừng chạy — thay vì im lặng.
    """
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    subject, body = render_email(report)
    text = f"{subject}\n\n{body}\n"
    day = report.generated_at.astimezone(_zone()).date().isoformat()
    for name in ("latest.txt", f"{day}.txt"):
        (out / name).write_text(text, encoding="utf-8")
    (out / "latest.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out / "latest.txt"


def send_report(db: Session) -> PilotReport:
    """Báo cáo hằng tối: ghi ra file (nếu có PILOT_REPORT_DIR) và/hoặc xếp email."""
    from app.services import email_service

    report = build_report(db)
    if settings.pilot_report_dir:
        try:
            write_report_files(report, settings.pilot_report_dir)
        except OSError:
            logger.exception("Pilot: không ghi được file báo cáo")
    if settings.pilot_report_email:
        subject, body = render_email(report)
        email_service.enqueue(
            db, None, to_email=settings.pilot_report_email, subject=subject, body=body,
            template="pilot_report",
        )
    return report
