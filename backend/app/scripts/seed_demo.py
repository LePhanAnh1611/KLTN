"""Tạo dữ liệu mẫu để demo/bảo vệ: `python -m app.scripts.seed_demo`.

Đi qua ĐÚNG các service nghiệp vụ (không INSERT thẳng) nên mọi quy tắc vẫn chạy:
ghi INTERACTION (BR-05), cập nhật mastery qua DKT (UC-64), lập lịch ôn (UC-66),
cấp XP/streak/huy hiệu (UC-46/47/48), sinh thông báo (UC-61). Nhờ vậy dữ liệu mẫu
phản ánh đúng hành vi hệ thống chứ không phải số liệu bịa.

Không cần ml-serve: `dkt_client` degrade mềm về cold-start prior khi service tắt.
Chạy lại nhiều lần an toàn — script bỏ qua nếu tài khoản demo đã tồn tại (trừ khi
truyền --reset).

Nguồn bộ từ — MẶC ĐỊNH là bộ NỀN `data/vocab_seed_core.json` (3.748 từ / 76 bộ,
NGSL+NAWL, chia theo CEFR + tần suất). Bộ CHỦ ĐỀ cũ (320 từ / 8 bộ, nghĩa viết
tay) vẫn chạy được:

    python -m app.scripts.seed_demo --reset                              # bộ nền
    python -m app.scripts.seed_demo --reset --vocab data/vocab_seed.json # bộ chủ đề

`--study-sets N` giới hạn số bộ ĐẦU được sinh lịch sử học mô phỏng (mặc định 8).
Mô phỏng cả 76 bộ là 152 phiên, mỗi câu trả lời gọi DKT một lần — chạy hàng giờ
mà không thêm gì cho demo.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.scripts._console import use_utf8_console
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.item import Item
from app.models.learning_stage import LearningStage
from app.models.review_schedule import ReviewSchedule
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.admin import CategoryCreate
from app.schemas.auth import RegisterRequest
from app.schemas.community import CommentCreate, PostCreate
from app.schemas.item import ItemCreateRequest, ItemProvenance
from app.schemas.rating import RatingRequest
from app.schemas.report import ReportRequest
from app.schemas.session import AnswerRequest, SessionCreateRequest
from app.schemas.word_set import PublishRequest, WordSetCreateRequest
from app.services import (
    account_service,
    achievement_service,
    auth_service,
    category_service,
    community_service,
    discover_service,
    dkt_client,
    item_service,
    permission_service,
    placement_service,
    rating_service,
    report_service,
    roadmap_seed,
    session_service,
    word_set_service,
)

PASSWORD = "Demo1234"

CATEGORIES = [
    ("Công việc", "Từ vựng công sở, kinh doanh"),
    ("Công nghệ", "Thuật ngữ IT & phần mềm"),
    ("Du lịch", "Từ vựng đi lại, sân bay, khách sạn"),
    ("Đời sống", "Từ vựng sinh hoạt hằng ngày"),
    ("Học thuật", "Từ vựng bài đọc, nghiên cứu"),
    ("Sức khỏe", "Từ vựng y tế, chăm sóc sức khỏe"),
    ("Xã hội", "Từ vựng môi trường, chính sách, cộng đồng"),
]

# Hai nguồn bộ từ, KHÔNG gộp — xem CLAUDE.md mục 6:
#
#   data/vocab_seed_core.json  bộ NỀN (mặc định) — 3.748 từ / 76 bộ, NGSL+NAWL,
#                              chia theo CEFR + tần suất. Dựng bằng
#                              `python -m app.scripts.build_core_dataset`.
#   data/vocab_seed.json       bộ CHỦ ĐỀ — 320 từ / 8 bộ, nghĩa viết tay, chia
#                              theo tình huống. Dựng bằng
#                              `python -m app.scripts.build_vocab_dataset`.
#
# Trước đây khối này là 28 từ viết tay ngay trong file. Chuyển ra dữ liệu ngoài
# vì hai lý do: thêm từ không phải sửa code, và bộ dữ liệu dựng lại được từ
# nguồn gốc bất cứ lúc nào.
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

#: Mặc định từ 2026-09-20: bộ nền. Bộ chủ đề vẫn chạy được bằng
#: `--vocab data/vocab_seed.json`.
VOCAB_SEED_PATH = _DATA_DIR / "vocab_seed_core.json"
VOCAB_TOPICAL_PATH = _DATA_DIR / "vocab_seed.json"

CATEGORY_FALLBACK = "Chung"


def load_word_sets(path: Path | None = None) -> list[dict]:
    """Đọc bộ từ đã dựng sẵn. Thiếu file thì báo rõ cách tạo lại."""
    path = path or VOCAB_SEED_PATH
    if not path.is_file():
        raise SystemExit(
            f"Không thấy {path}. Chạy trước: python -m app.scripts.build_core_dataset "
            "(bộ nền, mặc định) hoặc python -m app.scripts.build_vocab_dataset (bộ chủ đề)."
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    word_sets = []
    for spec in payload["word_sets"]:
        # `seed=no` = danh sách chỉ để TRA CỨU (làm giàu IPA/ví dụ cho từ vựng
        # lộ trình), không phải bộ từ để công khai.
        if not spec.get("seed", True):
            continue
        # Giữ nguyên dict thay vì làm phẳng thành tuple: bộ nền còn mang
        # meaning_confidence / meaning_source / example_source, mà tuple 5 phần
        # tử thì rơi mất đúng những trường đó.
        items = [
            {
                "word": item["word"],
                "meaning": item["meaning"],
                "phonetic": item.get("phonetic") or "",
                "part_of_speech": item.get("part_of_speech") or "",
                "example": item.get("example") or "",
                "example_vi": item.get("example_vi") or None,
                "meaning_confidence": item.get("meaning_confidence"),
                "meaning_source": item.get("meaning_source"),
                "example_source": item.get("example_source"),
            }
            for item in spec["items"]
        ]
        word_sets.append({
            "name": spec["name"],
            "description": spec.get("description") or "",
            "category": spec.get("category") or CATEGORY_FALLBACK,
            "difficulty": spec.get("difficulty") or "intermediate",
            # Bộ chủ đề cũ không có khoá này -> None -> cột để NULL.
            "cefr_level": spec.get("cefr") or None,
            "items": items,
        })
    return word_sets


#: Nạp trong main() chứ không phải lúc import, để --vocab chọn được nguồn.
WORD_SETS: list[dict] = []

#: Số bộ đầu tiên được sinh lịch sử học mô phỏng. Bộ NỀN có tới 76 bộ; mô phỏng
#: hết là 152 phiên học, mỗi phiên gọi DKT cho từng câu trả lời — chạy hàng giờ
#: mà không thêm được gì cho phần demo. 8 bộ là đủ để mọi màn có dữ liệu.
STUDY_SETS_DEFAULT = 8
STUDY_SETS = STUDY_SETS_DEFAULT

POSTS = [
    ("tip", "Mẹo của mình: học 10 từ mới mỗi ngày rồi ôn lại đúng lịch hệ thống gợi ý, "
            "nhớ lâu hơn hẳn so với nhồi 50 từ một hôm."),
    ("question", "Mọi người thường học flashcard hay làm quiz trước? Mình thấy quiz khó hơn "
                 "nhưng nhớ kỹ hơn."),
    ("word", "Hôm nay gặp từ \"deadline\" — hạn chót. Câu ví dụ dễ nhớ: The deadline is next Friday."),
    ("resource", "Chia sẻ mấy bộ từ theo chủ đề mình vừa công khai (công sở, du lịch, sức khỏe...), "
                 "mọi người tải về học chung nhé."),
]

DEMO_EMAILS = {
    "admin": "admin@demo.example.com",
    # Vai trò 'content' có trong ma trận quyền nhưng trước đây KHÔNG có tài khoản
    # nào mang nó — nên UC-74 chỉ nói suông được, không chỉ ra được người thật bị
    # chặn ở đâu. Tài khoản này để demo: vào được kho bộ từ, bị chặn ở Cấu hình.
    "content": "bientap@demo.example.com",
    "learners": ["an@demo.example.com", "binh@demo.example.com", "chi@demo.example.com"],
}


def _register(db: Session, email: str, display_name: str, role: str = "learner") -> User:
    user = auth_service.register_user(
        db,
        RegisterRequest(
            email=email, password=PASSWORD, password_confirm=PASSWORD, display_name=display_name
        ),
    )
    # Tài khoản demo coi như đã xác thực email (UC-03) để khỏi vướng cảnh báo khi demo
    account_service.mark_verified_now(user)
    if role != "learner":
        user.role = role
    db.commit()
    db.refresh(user)
    return user


def _study_session(
    db: Session, user: User, word_set_id: int, items: list[Item], accuracy: float, rng: random.Random
) -> None:
    """Học một phiên qua service thật: ghi Interaction -> mastery -> lịch ôn -> XP."""
    session = session_service.create_session(
        db, user, SessionCreateRequest(word_set_id=word_set_id, mode="flashcard")
    )
    for item in items:
        session_service.record_answer(
            db, user, session.id,
            AnswerRequest(
                item_id=item.id,
                is_correct=rng.random() < accuracy,
                response_time_ms=rng.randint(1200, 6000),
                exercise_format="flashcard",
            ),
        )
    session_service.complete_session(db, user, session.id)


def _make_some_due(db: Session, user: User, *, due_now: int = 6, overdue: int = 2) -> None:
    """Kéo một phần lịch ôn về quá khứ.

    Sau khi seed, mọi lịch đều rơi vào 1-7 ngày TỚI nên hôm nay không có gì đến
    hạn và nút "Ôn ngay" bị khóa. Người học thật thì luôn có vài từ tới hạn, nên
    dời một ít về hôm nay/quá hạn cho đúng thực tế và demo được luồng ôn (UC-33).
    """
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(ReviewSchedule)
        .where(ReviewSchedule.user_id == user.id)
        .order_by(ReviewSchedule.id)
        .limit(due_now + overdue)
    ).scalars().all()

    for index, row in enumerate(rows):
        row.next_review_at = (
            now - timedelta(days=2, hours=index) if index < overdue
            else now - timedelta(hours=index + 1)
        )
    db.commit()


def _set_entry_level(db: Session, user: User, level: str) -> None:
    """UC-11 — gán trình độ đầu vào (thay cho việc bấm làm bài khi seed)."""
    settings_row = db.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    settings_row.entry_cefr_level = level
    db.commit()


def _backdate_activity(db: Session, user: User, streak_days: int) -> None:
    """Đặt streak/ngày hoạt động lùi lại để dashboard có chuỗi ngày đẹp khi demo."""
    progress = db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one()
    progress.streak_count = streak_days
    progress.last_activity_date = datetime.now(timezone.utc).date()   # streak tính theo UTC
    db.commit()


def _already_seeded(db: Session) -> bool:
    return db.execute(
        select(User.id).where(User.email == DEMO_EMAILS["admin"])
    ).scalar_one_or_none() is not None


def _reset(db: Session) -> None:
    """Xóa sạch tài khoản demo & dữ liệu gắn với chúng (chỉ dùng cho môi trường demo)."""
    emails = [DEMO_EMAILS["admin"], DEMO_EMAILS["content"], *DEMO_EMAILS["learners"]]
    users = db.execute(select(User).where(User.email.in_(emails))).scalars().all()
    if not users:
        return

    user_ids = [u.id for u in users]
    from app.models.audit_log import AuditLog
    from app.models.challenge_claim import ChallengeClaim
    from app.models.conversation import Conversation, ConversationTurn
    from app.models.email_queue import EmailQueue
    from app.models.auth_token import AuthToken
    from app.models.friendship import Friendship
    from app.models.game_score import GameScore
    from app.models.item_flag import ItemFlag
    from app.models.level_up import LevelUpSuggestion
    from app.models.pronunciation_attempt import PronunciationAttempt
    from app.models.speaking_attempt import SpeakingAppeal, SpeakingAttempt
    from app.models.writing import SentenceNote, WritingSubmission
    from app.models.placement import PlacementAttempt
    from app.models.interaction import Interaction
    from app.models.knowledge_state import KnowledgeState
    from app.models.notification import Notification
    from app.models.post import Post
    from app.models.post_comment import PostComment
    from app.models.post_reaction import PostReaction
    from app.models.report import Report
    from app.models.review_schedule import ReviewSchedule
    from app.models.session import StudySession
    from app.models.user_achievement import UserAchievement
    from app.models.user_settings import UserSettings
    from app.models.word_set_rating import WordSetRating

    word_set_ids = db.execute(
        select(WordSet.id).where(WordSet.owner_id.in_(user_ids))
    ).scalars().all()
    post_ids = db.execute(
        select(Post.id).where(Post.author_id.in_(user_ids))
    ).scalars().all()

    # Xóa theo đúng thứ tự phụ thuộc khóa ngoại; PHẢI flush sau mỗi bảng, nếu gộp
    # flush ở cuối thì SQLAlchemy tự xếp thứ tự và có thể xóa posts trước comments.
    # Bình luận/react lấy theo POST (người ngoài cũng có thể đã tương tác bài demo).
    deletions = [
        # Chặng lộ trình trỏ FK vào word_sets -> phải xóa trước bộ từ (UC-84)
        (LearningStage, LearningStage.word_set_id.in_(word_set_ids) if word_set_ids else None),
        (PlacementAttempt, PlacementAttempt.user_id.in_(user_ids)),
        (AuthToken, AuthToken.user_id.in_(user_ids)),
        (PostReaction, PostReaction.post_id.in_(post_ids) if post_ids else None),
        (PostReaction, PostReaction.user_id.in_(user_ids)),
        (PostComment, PostComment.post_id.in_(post_ids) if post_ids else None),
        (PostComment, PostComment.author_id.in_(user_ids)),
        (Post, Post.author_id.in_(user_ids)),
        (Report, Report.reporter_id.in_(user_ids)),
        (WordSetRating, WordSetRating.user_id.in_(user_ids)),
        (Notification, Notification.user_id.in_(user_ids)),
        (EmailQueue, EmailQueue.user_id.in_(user_ids)),
        (AuditLog, AuditLog.actor_id.in_(user_ids)),
        (Interaction, Interaction.user_id.in_(user_ids)),
        (KnowledgeState, KnowledgeState.user_id.in_(user_ids)),
        (ReviewSchedule, ReviewSchedule.user_id.in_(user_ids)),
        (StudySession, StudySession.user_id.in_(user_ids)),
        (UserAchievement, UserAchievement.user_id.in_(user_ids)),
        (UserProgress, UserProgress.user_id.in_(user_ids)),
        (UserSettings, UserSettings.user_id.in_(user_ids)),
        # Các module mở khóa SAU khi _reset() được viết. Đều trỏ FK vào users
        # (và item_flags/pronunciation_attempts còn trỏ vào items), nên bỏ sót
        # là `--reset` chết giữa chừng với ForeignKeyViolation — chỉ lộ ra khi
        # tài khoản demo đã thật sự dùng các màn đó.
        (ItemFlag, ItemFlag.user_id.in_(user_ids)),
        (PronunciationAttempt, PronunciationAttempt.user_id.in_(user_ids)),
        (SpeakingAppeal, SpeakingAppeal.user_id.in_(user_ids)),
        (SpeakingAttempt, SpeakingAttempt.user_id.in_(user_ids)),
        (SentenceNote, SentenceNote.user_id.in_(user_ids)),
        (WritingSubmission, WritingSubmission.user_id.in_(user_ids)),
        (ConversationTurn, ConversationTurn.conversation_id.in_(
            select(Conversation.id).where(Conversation.user_id.in_(user_ids))
        )),
        (Conversation, Conversation.user_id.in_(user_ids)),
        (GameScore, GameScore.user_id.in_(user_ids)),
        (ChallengeClaim, ChallengeClaim.user_id.in_(user_ids)),
        (LevelUpSuggestion, LevelUpSuggestion.user_id.in_(user_ids)),
        (Friendship, Friendship.requester_id.in_(user_ids)),
        (Friendship, Friendship.addressee_id.in_(user_ids)),
    ]
    for model, condition in deletions:
        if condition is None:
            continue
        for row in db.execute(select(model).where(condition)).scalars().all():
            db.delete(row)
        db.flush()

    if word_set_ids:
        for item in db.execute(
            select(Item).where(Item.word_set_id.in_(word_set_ids))
        ).scalars().all():
            db.delete(item)
        db.flush()

        # Gỡ tham chiếu origin_set_id trỏ vào bộ demo (kể cả bản sao của người
        # dùng THẬT đã tải bộ demo về) trước khi xóa bộ gốc
        for word_set in db.execute(
            select(WordSet).where(WordSet.origin_set_id.in_(word_set_ids))
        ).scalars().all():
            word_set.origin_set_id = None
        db.flush()

        for word_set in db.execute(
            select(WordSet).where(WordSet.id.in_(word_set_ids))
        ).scalars().all():
            db.delete(word_set)
        db.flush()

    for user in users:
        db.delete(user)
    db.commit()
    print("Đã xóa dữ liệu demo cũ.")


def _warn_if_dkt_down() -> None:
    """Mastery do DKT suy luận (UC-64). Nếu ml-serve tắt, mọi item rơi về cold-start
    prior (< ngưỡng "đã thuộc") nên demo sẽ không có từ nào đạt mastered."""
    dkt_client.reset_circuit()
    probe = dkt_client.predict_mastery([("apple", 1)], ["apple"])
    if probe.get("apple") is None:
        print(
            "! Chưa bật service DKT (ml-serve) — mastery sẽ dùng cold-start prior,\n"
            "  dữ liệu mẫu sẽ KHÔNG có từ nào đạt \"đã thuộc\".\n"
            f"  Muốn số liệu đầy đủ: bật ml-serve ở {settings.ml_serve_url} rồi chạy lại"
            " với --reset.\n"
        )


def seed(db: Session, *, rng: random.Random) -> None:
    _warn_if_dkt_down()
    permission_service.ensure_seeded(db)
    achievement_service.ensure_seeded(db)

    # --- Danh mục (UC-76) ---
    existing = {c.name for c in category_service.list_categories(db, only_active=False)}
    for order, (name, description) in enumerate(CATEGORIES, start=1):
        if name not in existing:
            category_service.create_category(
                db, CategoryCreate(name=name, description=description, sort_order=order)
            )
    print(f"Danh mục: {len(CATEGORIES)}")

    # --- Người dùng ---
    admin = _register(db, DEMO_EMAILS["admin"], "Quản trị viên", role="admin")
    _register(db, DEMO_EMAILS["content"], "Biên tập viên", role="content")
    an = _register(db, DEMO_EMAILS["learners"][0], "Nguyễn Văn An")
    binh = _register(db, DEMO_EMAILS["learners"][1], "Trần Thị Bình")
    chi = _register(db, DEMO_EMAILS["learners"][2], "Lê Minh Chi")
    print(f"Người dùng: 1 admin + 1 biên tập + 3 học viên (mật khẩu chung: {PASSWORD})")

    # --- Bộ từ của An (UC-13/14/17) ---
    created: list[tuple[WordSet, list[Item]]] = []
    for spec in WORD_SETS:
        response = word_set_service.create_word_set(
            db, an,
            WordSetCreateRequest(
                name=spec["name"], description=spec["description"],
                category=spec["category"], difficulty=spec["difficulty"],
                cefr_level=spec["cefr_level"], cover_image_url=None,
            ),
        )
        word_set = db.get(WordSet, response.id)
        for it in spec["items"]:
            item_service.create_item(
                db, an, word_set.id,
                ItemCreateRequest(
                    word=it["word"], meaning=it["meaning"], phonetic=it["phonetic"],
                    part_of_speech=it["part_of_speech"], example=it["example"],
                ),
                # Bộ chủ đề cũ không có ba trường này -> ItemProvenance toàn None
                # -> cột trong DB để NULL, đúng như item người học tự nhập.
                provenance=ItemProvenance(
                    meaning_confidence=it["meaning_confidence"],
                    meaning_source=it["meaning_source"],
                    example_source=it["example_source"],
                    example_vi=it["example_vi"],
                ),
            )
        word_set_service.set_publish(db, an, word_set.id, PublishRequest(is_public=True))
        items = db.execute(
            select(Item).where(Item.word_set_id == word_set.id, Item.deleted_at.is_(None))
        ).scalars().all()
        created.append((word_set, list(items)))
    print(f"Bộ từ công khai: {len(created)}")

    # --- An học nhiều phiên: sinh Interaction + mastery + lịch ôn + XP/huy hiệu ---
    for word_set, items in created[:STUDY_SETS]:
        for _ in range(2):
            _study_session(db, an, word_set.id, items, accuracy=0.75, rng=rng)
    _backdate_activity(db, an, streak_days=7)
    achievement_service.check_and_unlock(db, an)
    _make_some_due(db, an)

    # --- Bình & Chi tải bộ công khai về rồi học (UC-21 snapshot Q1) ---
    for learner, accuracy in ((binh, 0.6), (chi, 0.85)):
        for word_set, _ in created[:2]:
            clone = discover_service.clone_word_set(db, learner, word_set.id)
            clone_items = db.execute(
                select(Item).where(Item.word_set_id == clone.id, Item.deleted_at.is_(None))
            ).scalars().all()
            _study_session(db, learner, clone.id, list(clone_items), accuracy=accuracy, rng=rng)
        achievement_service.check_and_unlock(db, learner)
    _backdate_activity(db, binh, streak_days=3)
    _backdate_activity(db, chi, streak_days=12)
    print("Lịch sử học: 3 học viên (đã sinh Interaction / mastery / lịch ôn / XP)")

    # --- Đánh giá bộ từ (UC-23) ---
    rating_service.upsert_rating(db, binh, created[0][0].id,
                                 RatingRequest(stars=5, comment="Từ vựng sát với công việc thật, cảm ơn bạn!"))
    rating_service.upsert_rating(db, chi, created[0][0].id,
                                 RatingRequest(stars=4, comment="Hay, mong có thêm ví dụ."))
    rating_service.upsert_rating(db, binh, created[1][0].id, RatingRequest(stars=4))

    # --- Bộ nổi bật (UC-22 do Admin gắn ở UC-75) ---
    featured = created[0][0]
    featured.is_featured = True
    db.commit()

    # --- Cộng đồng: bài viết, bình luận, thích (UC-49/50/51) ---
    authors = [an, binh, chi, an]
    posts = []
    for (post_type, content), author in zip(POSTS, authors):
        card = community_service.create_post(
            db, author, PostCreate(post_type=post_type, content=content)
        )
        posts.append(card)

    community_service.add_comment(db, binh, posts[0].id,
                                  CommentCreate(content="Đúng rồi, ôn đúng lịch quan trọng hơn học nhiều."))
    community_service.add_comment(db, chi, posts[0].id,
                                  CommentCreate(content="Mình cũng thấy vậy, streak giúp mình kiên trì hơn."))
    community_service.add_comment(db, an, posts[1].id,
                                  CommentCreate(content="Mình học flashcard trước rồi mới quiz lại."))
    for post in posts[:3]:
        for liker in (an, binh, chi):
            if liker.id != post.author_id:
                community_service.toggle_reaction(db, liker, post.id)
    print(f"Cộng đồng: {len(posts)} bài viết + bình luận + lượt thích")

    # --- UC-11 ngân hàng câu hỏi + UC-84 chặng lộ trình (nội dung hệ thống) ---
    question_count = roadmap_seed.seed_placement_questions(db)
    stage_count = roadmap_seed.seed_stages(db, admin)
    stage_count_v2 = roadmap_seed.seed_stages_v2(db, admin)   # tài khoản mới dùng v2
    print(f"Lộ trình: {stage_count} chặng v1 + {stage_count_v2} chặng v2 · {question_count} câu hỏi đầu vào")

    # An đã làm placement ra A2 + học chặng A2 đầu tiên để bản đồ có tiến độ thật
    placement_service.skip(db, binh)                      # "Tôi mới bắt đầu" -> A1
    _set_entry_level(db, an, "A2")
    a2_stage = db.execute(
        select(LearningStage).where(
            LearningStage.cefr_level == "A2",
            LearningStage.roadmap_version == an.roadmap_version,
            LearningStage.is_active.is_(True),
        )
        .order_by(LearningStage.order_index)
    ).scalars().first()
    if a2_stage is not None:
        clone = discover_service.clone_word_set(db, an, a2_stage.word_set_id)
        clone_items = db.execute(
            select(Item).where(Item.word_set_id == clone.id, Item.deleted_at.is_(None))
        ).scalars().all()
        _study_session(db, an, clone.id, list(clone_items), accuracy=0.9, rng=rng)

    # --- Một báo cáo chờ xử lý để demo UC-78 ---
    report_service.create_report(
        db, chi,
        target_type=report_service.TARGET_POST, target_id=posts[2].id,
        data=ReportRequest(reason="spam", description="Mình thấy bài này giống quảng cáo."),
    )
    print("Báo cáo chờ xử lý: 1 (để demo UC-78)")

    print(
        "\nXong. Đăng nhập thử:\n"
        f"  Admin   : {DEMO_EMAILS['admin']} / {PASSWORD}\n"
        f"  Học viên: {DEMO_EMAILS['learners'][0]} / {PASSWORD}  (nhiều dữ liệu nhất)\n"
    )


def main() -> None:
    # Console Windows mặc định cp1252 -> không in được tiếng Việt
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Tạo dữ liệu mẫu cho demo")
    parser.add_argument("--reset", action="store_true",
                        help="Xóa dữ liệu demo cũ trước khi tạo lại")
    parser.add_argument("--seed", type=int, default=42, help="Seed ngẫu nhiên (mặc định 42)")
    parser.add_argument("--vocab", type=Path, default=None,
                        help="File bộ từ (mặc định data/vocab_seed_core.json — bộ nền "
                             "3.748 từ; dùng data/vocab_seed.json cho bộ chủ đề 320 từ)")
    parser.add_argument("--study-sets", type=int, default=STUDY_SETS_DEFAULT, dest="study_sets",
                        help=f"Số bộ đầu được sinh lịch sử học (mặc định {STUDY_SETS_DEFAULT})")
    args = parser.parse_args()

    global WORD_SETS, STUDY_SETS
    WORD_SETS = load_word_sets(args.vocab)
    STUDY_SETS = args.study_sets
    # Dấu phân cách hàng nghìn theo kiểu Việt Nam ("3.748"), không phải "3,748":
    # dòng này đi thẳng vào ảnh chụp màn hình trong tài liệu bảo vệ.
    total_items = f"{sum(len(w['items']) for w in WORD_SETS):,}".replace(",", ".")
    print(f"Nguồn bộ từ: {args.vocab or VOCAB_SEED_PATH} "
          f"({len(WORD_SETS)} bộ, {total_items} từ)")

    rng = random.Random(args.seed)

    with SessionLocal() as db:
        if args.reset:
            _reset(db)
        elif _already_seeded(db):
            print("Dữ liệu demo đã tồn tại. Dùng --reset nếu muốn tạo lại.")
            return
        seed(db, rng=rng)


if __name__ == "__main__":
    use_utf8_console()
    main()
