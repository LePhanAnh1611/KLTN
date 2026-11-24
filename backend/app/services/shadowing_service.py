"""UC-97 — nghiệp vụ Shadowing theo phụ đề video YouTube.

Ranh giới: KHÔNG đọc/ghi KNOWLEDGE_STATE, KHÔNG sinh INTERACTION (CLAUDE.md §7).
Có test canh `test_khong_sinh_interaction_nao`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.shadowing import ShadowingAttempt, ShadowingVideo
from app.models.user import User
from app.schemas.pronunciation import AspectOut, WordCheckOut
from app.schemas.shadowing import (
    SegmentOut,
    SegmentProgress,
    ShadowingAdminDetail,
    ShadowingAdminRow,
    ShadowingAttemptResult,
    ShadowingVideoCard,
    ShadowingVideoDetail,
    ShadowingVideoUpdate,
)
from app.services import audit_service, config_service
from app.services.shadowing import CaptionError, profile, segmenter, subtitles, youtube

# Trùng 8 bộ từ chủ đề (data/vocab_seed.json) để kho video khớp màn Khám phá.
TOPICS = [
    "Công sở & Kinh doanh",
    "Công nghệ thông tin",
    "Du lịch & Sân bay",
    "Sinh hoạt hằng ngày",
    "Học thuật & Nghiên cứu",
    "Sức khỏe & Y tế",
    "Ẩm thực & Nhà hàng",
    "Môi trường & Xã hội",
]
LICENSES = ["public-domain", "cc-by", "cc-by-sa", "youtube-standard"]
# Giấy phép Creative Commons bắt buộc ghi công
ATTRIBUTION_REQUIRED = {"cc-by", "cc-by-sa"}
MIN_SEGMENTS = 1


def pass_accuracy() -> float:
    return config_service.get_float("shadowing_pass_accuracy")


# ------------------------------------------------------------------ Dựng video

def _segments_payload(segments: list[segmenter.Segment]) -> tuple[list[dict], dict, float | None, float | None]:
    rows = [s.as_dict() for s in segments]
    vocab = profile.vocab_profile([r["text"] for r in rows])
    wpm = profile.words_per_minute(rows)
    duration = rows[-1]["end"] if rows else None
    return rows, vocab, wpm, duration


def build_video_data(url: str, caption_file: str | None = None) -> dict:
    """Lấy tiêu đề + phụ đề (hoặc đọc file), cắt câu, tính hồ sơ từ vựng.

    Không ghi DB — trả dict để service tạo bản ghi. Lỗi → HTTPException đúng mã.
    """
    try:
        video_id = youtube.parse_video_id(url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    try:
        meta = youtube.fetch_meta(video_id)
    except CaptionError as exc:
        # Có file phụ đề thì vẫn làm được khi chỉ là YouTube chặn oEmbed; còn
        # video tắt nhúng/không tồn tại thì có phụ đề cũng không phát được.
        if not (exc.blocked and caption_file is not None):
            raise _caption_http(exc) from exc
        meta = youtube.VideoMeta(title=f"Video {video_id}", channel=None)

    try:
        if caption_file is not None:
            snippets = subtitles.parse_subtitles(caption_file)
            kind, language = "upload", "en"
        else:
            track = youtube.fetch_captions(video_id)
            snippets, kind, language = track.snippets, track.kind, track.language
    except CaptionError as exc:
        raise _caption_http(exc) from exc

    segments = segmenter.segment(snippets)
    if len(segments) < MIN_SEGMENTS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Phụ đề không có câu nào dùng được để luyện.",
        )
    rows, vocab, wpm, duration = _segments_payload(segments)
    return {
        "youtube_id": video_id, "title": meta.title, "channel": meta.channel,
        "caption_kind": kind, "language": language, "segments": rows,
        "vocab_profile": vocab, "cefr_level": vocab["level"],
        "words_per_minute": wpm, "duration_sec": duration,
    }


def _caption_http(exc: CaptionError) -> HTTPException:
    code = status.HTTP_503_SERVICE_UNAVAILABLE if exc.blocked else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=str(exc))


# ------------------------------------------------------------------ Hiển thị

def _passed_counts(db: Session, user: User, video_ids: list[int]) -> dict[int, int]:
    if not video_ids:
        return {}
    rows = db.execute(
        select(ShadowingAttempt.video_id,
               func.count(func.distinct(ShadowingAttempt.segment_index)))
        .where(ShadowingAttempt.user_id == user.id,
               ShadowingAttempt.video_id.in_(video_ids),
               ShadowingAttempt.passed.is_(True))
        .group_by(ShadowingAttempt.video_id)
    ).all()
    return {vid: n for vid, n in rows}


def _card_fields(video: ShadowingVideo) -> dict:
    return {
        "id": video.id, "youtube_id": video.youtube_id, "title": video.title,
        "channel": video.channel, "topic": video.topic, "cefr_level": video.cefr_level,
        "words_per_minute": video.words_per_minute, "duration_sec": video.duration_sec,
        "segment_count": len(video.segments or []), "source": video.source,
        "license": video.license, "attribution": video.attribution,
    }


def _segment_out(seg: dict) -> SegmentOut:
    return SegmentOut(**seg, words_per_minute=profile.segment_wpm(seg))


def _visible_filter(user: User):
    return or_(
        (ShadowingVideo.source == "catalog") & (ShadowingVideo.status == "published"),
        (ShadowingVideo.source == "user") & (ShadowingVideo.owner_id == user.id),
    )


def list_videos(db: Session, user: User, topic: str | None = None,
                level: str | None = None) -> list[ShadowingVideoCard]:
    """Kho đã xuất bản + video riêng của chính người học."""
    stmt = select(ShadowingVideo).where(
        ShadowingVideo.deleted_at.is_(None), _visible_filter(user)
    )
    if topic:
        stmt = stmt.where(ShadowingVideo.topic == topic)
    if level:
        stmt = stmt.where(ShadowingVideo.cefr_level == level)
    videos = db.scalars(
        stmt.order_by(ShadowingVideo.source.desc(), ShadowingVideo.topic,
                      ShadowingVideo.cefr_level, ShadowingVideo.id)
    ).all()
    passed = _passed_counts(db, user, [v.id for v in videos])
    return [ShadowingVideoCard(**_card_fields(v), passed_count=passed.get(v.id, 0))
            for v in videos]


def get_visible_video(db: Session, user: User, video_id: int) -> ShadowingVideo:
    video = db.scalar(select(ShadowingVideo).where(
        ShadowingVideo.id == video_id, ShadowingVideo.deleted_at.is_(None),
        _visible_filter(user),
    ))
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy video")
    return video


def video_detail(db: Session, user: User, video: ShadowingVideo) -> ShadowingVideoDetail:
    stats: dict[int, dict] = defaultdict(lambda: {"attempts": 0, "best": None, "passed": False})
    for idx, acc, ok in db.execute(
        select(ShadowingAttempt.segment_index, ShadowingAttempt.accuracy,
               ShadowingAttempt.passed)
        .where(ShadowingAttempt.user_id == user.id, ShadowingAttempt.video_id == video.id)
    ).all():
        row = stats[idx]
        row["attempts"] += 1
        row["best"] = acc if row["best"] is None else max(row["best"], acc)
        row["passed"] = row["passed"] or ok

    segments = video.segments or []
    progress = [
        SegmentProgress(index=s["index"], attempts=stats[s["index"]]["attempts"],
                        best_accuracy=stats[s["index"]]["best"],
                        passed=stats[s["index"]]["passed"])
        for s in segments
    ]
    return ShadowingVideoDetail(
        **_card_fields(video),
        passed_count=sum(1 for p in progress if p.passed),
        caption_kind=video.caption_kind,
        segments=[_segment_out(s) for s in segments],
        vocab_profile=video.vocab_profile,
        progress=progress,
        pass_accuracy=pass_accuracy(),
    )


def list_topics() -> dict:
    return {"topics": TOPICS, "levels": list(profile.LEVELS), "licenses": LICENSES}


# ------------------------------------------------------------------ Người học

def add_user_video(db: Session, user: User, url: str,
                   caption_file: str | None = None) -> ShadowingVideo:
    """Người học dán link. E7: video đã có trong kho → trả luôn bản trong kho."""
    try:
        video_id = youtube.parse_video_id(url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    existing = db.scalar(select(ShadowingVideo).where(
        ShadowingVideo.youtube_id == video_id, ShadowingVideo.deleted_at.is_(None),
        _visible_filter(user),
    ).order_by(ShadowingVideo.source))  # 'catalog' < 'user'
    if existing is not None:
        return existing

    data = build_video_data(url, caption_file)
    video = ShadowingVideo(**data, source="user", owner_id=user.id, created_by=user.id,
                           status="published", published_at=datetime.now(timezone.utc))
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def delete_user_video(db: Session, user: User, video_id: int) -> None:
    video = get_visible_video(db, user, video_id)
    if video.source != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="Video trong kho chỉ admin mới gỡ được")
    video.deleted_at = datetime.now(timezone.utc)
    db.commit()


def _speed_feedback(ratio: float | None) -> str | None:
    if ratio is None:
        return None
    pct = abs(round((ratio - 1) * 100))
    if ratio < 0.8:
        return f"Bạn nói chậm hơn người trong video khoảng {pct}%. Nghe lại và bám nhịp sát hơn."
    if ratio > 1.25:
        return f"Bạn nói nhanh hơn người trong video khoảng {pct}%. Chậm lại để giữ rõ từng từ."
    return "Tốc độ của bạn gần với người nói trong video."


def score_attempt(db: Session, user: User, video: ShadowingVideo, segment_index: int,
                  result) -> ShadowingAttemptResult:
    """Lưu một lần nhại lại đã chấm (`result` là ReadAloudResult)."""
    seg = _segment(video, segment_index)
    original_wpm = profile.segment_wpm(seg)
    learner_wpm = result.audio_metrics.get("words_per_minute") or None
    ratio = round(learner_wpm / original_wpm, 2) if (learner_wpm and original_wpm) else None
    threshold = pass_accuracy()
    passed = result.accuracy >= threshold

    aspects = [
        {"key": a.key, "label": a.label, "level": a.level, "level_label": a.level_label,
         "detail": a.detail, "suggestion": a.suggestion}
        for a in result.aspects
    ]
    attempt = ShadowingAttempt(
        user_id=user.id, video_id=video.id, segment_index=segment_index,
        target_text=seg["text"], transcript=result.transcript,
        accuracy=result.accuracy, clarity=result.clarity, speed_ratio=ratio,
        overall_level=result.overall_level, passed=passed,
        detail={
            "words": result.words, "aspects": aspects,
            "missed_words": result.missed_words, "extra_words": result.extra_words,
            "audio_metrics": result.audio_metrics,
            "learner_wpm": learner_wpm, "original_wpm": original_wpm,
        },
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return ShadowingAttemptResult(
        attempt_id=attempt.id, video_id=video.id, segment_index=segment_index,
        expected_text=result.expected_text, transcript=result.transcript,
        accuracy=result.accuracy, clarity=result.clarity,
        overall_level=result.overall_level,
        aspects=[AspectOut(**a) for a in aspects],
        words=[WordCheckOut(**w) for w in result.words],
        missed_words=result.missed_words, extra_words=result.extra_words,
        audio_metrics=result.audio_metrics, feedback=result.feedback,
        warnings=result.warnings,
        learner_wpm=learner_wpm, original_wpm=original_wpm, speed_ratio=ratio,
        speed_feedback=_speed_feedback(ratio), passed=passed, pass_accuracy=threshold,
    )


def _segment(video: ShadowingVideo, index: int) -> dict:
    for seg in video.segments or []:
        if seg["index"] == index:
            return seg
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không có câu này trong video")


def get_segment(video: ShadowingVideo, index: int) -> dict:
    return _segment(video, index)


# ------------------------------------------------------------------ Admin

def _admin_row(video: ShadowingVideo) -> dict:
    return {**_card_fields(video), "status": video.status,
            "caption_kind": video.caption_kind, "created_at": video.created_at,
            "published_at": video.published_at}


def admin_list(db: Session, status_filter: str | None = None) -> list[ShadowingAdminRow]:
    stmt = select(ShadowingVideo).where(
        ShadowingVideo.source == "catalog", ShadowingVideo.deleted_at.is_(None)
    )
    if status_filter:
        stmt = stmt.where(ShadowingVideo.status == status_filter)
    videos = db.scalars(stmt.order_by(ShadowingVideo.topic, ShadowingVideo.id)).all()
    return [ShadowingAdminRow(**_admin_row(v)) for v in videos]


def _get_catalog(db: Session, video_id: int) -> ShadowingVideo:
    video = db.get(ShadowingVideo, video_id)
    if video is None or video.deleted_at is not None or video.source != "catalog":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy video")
    return video


def admin_detail(db: Session, video_id: int) -> ShadowingAdminDetail:
    video = _get_catalog(db, video_id)
    return ShadowingAdminDetail(
        **_admin_row(video),
        segments=[_segment_out(s) for s in video.segments or []],
        vocab_profile=video.vocab_profile,
    )


def _validate_topic(topic: str | None) -> None:
    if topic is not None and topic not in TOPICS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail=f"Chủ đề không hợp lệ. Chọn một trong: {', '.join(TOPICS)}")


def admin_create(db: Session, admin: User, *, url: str, topic: str | None,
                 license: str | None, attribution: str | None,
                 caption_file: str | None = None) -> ShadowingAdminDetail:
    _validate_topic(topic)
    if license is not None and license not in LICENSES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Giấy phép không hợp lệ")
    try:
        video_id = youtube.parse_video_id(url)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    duplicate = db.scalar(select(ShadowingVideo).where(
        ShadowingVideo.youtube_id == video_id, ShadowingVideo.source == "catalog",
        ShadowingVideo.deleted_at.is_(None),
    ))
    if duplicate is not None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"Video đã có trong kho (#{duplicate.id}: {duplicate.title}).")

    data = build_video_data(url, caption_file)
    video = ShadowingVideo(**data, topic=topic, license=license,
                           attribution=(attribution or None), source="catalog",
                           created_by=admin.id, status="draft")
    db.add(video)
    db.flush()
    audit_service.log(db, admin, action="shadowing.create", target_type="shadowing_video",
                      target_id=video.id, detail=f"{video.youtube_id} — {video.title}",
                      commit=False)
    db.commit()
    db.refresh(video)
    return admin_detail(db, video.id)


def admin_update(db: Session, admin: User, video_id: int,
                 data: ShadowingVideoUpdate) -> ShadowingAdminDetail:
    video = _get_catalog(db, video_id)
    fields = data.model_dump(exclude_unset=True)
    if "topic" in fields:
        _validate_topic(fields["topic"])
        video.topic = fields["topic"]
    if "title" in fields and fields["title"]:
        video.title = fields["title"].strip()
    if "license" in fields:
        video.license = fields["license"]
    if "attribution" in fields:
        video.attribution = (fields["attribution"] or "").strip() or None
    if data.segments is not None:
        try:
            segments = segmenter.normalize_edited([s.model_dump() for s in data.segments])
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        if not segments:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                                detail="Video phải còn ít nhất một câu.")
        rows, vocab, wpm, duration = _segments_payload(segments)
        video.segments = rows
        video.vocab_profile = vocab
        video.cefr_level = vocab["level"]
        video.words_per_minute = wpm
        video.duration_sec = duration

    if video.status == "published":
        _check_publishable(video)
    audit_service.log(db, admin, action="shadowing.update", target_type="shadowing_video",
                      target_id=video.id, detail=", ".join(sorted(fields)) or None,
                      commit=False)
    db.commit()
    return admin_detail(db, video.id)


def _check_publishable(video: ShadowingVideo) -> None:
    missing = []
    if not video.topic:
        missing.append("chủ đề")
    if not video.license:
        missing.append("giấy phép")
    elif video.license in ATTRIBUTION_REQUIRED and not video.attribution:
        missing.append("ghi công (bắt buộc với giấy phép Creative Commons)")
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="Chưa xuất bản được, còn thiếu: " + ", ".join(missing) + ".")


def admin_set_status(db: Session, admin: User, video_id: int,
                     new_status: str) -> ShadowingAdminDetail:
    video = _get_catalog(db, video_id)
    if new_status == "published":
        _check_publishable(video)
        video.published_at = video.published_at or datetime.now(timezone.utc)
    video.status = new_status
    audit_service.log(db, admin, action=f"shadowing.{'publish' if new_status == 'published' else 'unpublish'}",
                      target_type="shadowing_video", target_id=video.id,
                      detail=video.title, commit=False)
    db.commit()
    return admin_detail(db, video.id)


def admin_delete(db: Session, admin: User, video_id: int) -> None:
    video = _get_catalog(db, video_id)
    video.deleted_at = datetime.now(timezone.utc)
    audit_service.log(db, admin, action="shadowing.delete", target_type="shadowing_video",
                      target_id=video.id, detail=video.title, commit=False)
    db.commit()
