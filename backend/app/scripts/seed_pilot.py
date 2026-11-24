"""Nạp dữ liệu cho đợt PILOT với người dùng thật: `python -m app.scripts.seed_pilot`.

Khác `seed_demo` ở chỗ quan trọng nhất: KHÔNG tạo học viên giả, lịch sử học giả
lập, bài viết hay báo cáo mẫu. Dữ liệu pilot là đầu vào để kiểm chứng DKT — một
lượt trả lời giả lẫn vào là số đo sai. Script chỉ nạp NỘI DUNG HỆ THỐNG:

- quyền, huy hiệu, danh mục;
- một tài khoản admin (của người chạy pilot — vai trò admin bị loại khỏi báo cáo);
- bộ từ NỀN (NGSL + NAWL, chia theo CEFR) ở dạng công khai, do admin sở hữu;
- ngân hàng câu hỏi xếp lớp (UC-11) + các chặng lộ trình (UC-84).

Người học tự đăng ký, làm bài xếp lớp, rồi lấy bộ từ từ lộ trình/Khám phá.
Chạy lại an toàn: tài khoản admin đã có thì dùng lại; bộ từ đã nạp thì bỏ qua.

    python -m app.scripts.seed_pilot --admin-email ban@gmail.com --admin-password '...'
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.user import User
from app.models.word_set import WordSet
from app.schemas.admin import CategoryCreate
from app.schemas.item import ItemCreateRequest, ItemProvenance
from app.schemas.word_set import PublishRequest, WordSetCreateRequest
from app.scripts import seed_demo
from app.scripts._console import use_utf8_console
from app.services import (
    achievement_service,
    category_service,
    item_service,
    permission_service,
    roadmap_seed,
    word_set_service,
)


def seed(db, *, admin_email: str, admin_password: str, admin_name: str) -> None:
    permission_service.ensure_seeded(db)
    achievement_service.ensure_seeded(db)

    existing = {c.name for c in category_service.list_categories(db, only_active=False)}
    for order, (name, description) in enumerate(seed_demo.CATEGORIES, start=1):
        if name not in existing:
            category_service.create_category(
                db, CategoryCreate(name=name, description=description, sort_order=order)
            )

    admin = db.execute(select(User).where(User.email == admin_email.lower())).scalar_one_or_none()
    if admin is None:
        seed_demo.PASSWORD = admin_password
        admin = seed_demo._register(db, admin_email, admin_name, role="admin")
    elif admin.role != "admin":
        admin.role = "admin"
        db.commit()
    print(f"Admin: {admin.email}")

    owned = db.execute(
        select(func.count()).select_from(WordSet).where(WordSet.owner_id == admin.id)
    ).scalar_one()
    if owned:
        print(f"Bộ từ: đã có {owned} bộ của admin — bỏ qua")
    else:
        specs = seed_demo.load_word_sets(None)  # bộ NỀN
        for n, spec in enumerate(specs, start=1):
            created = word_set_service.create_word_set(
                db, admin,
                WordSetCreateRequest(
                    name=spec["name"], description=spec["description"],
                    category=spec["category"], difficulty=spec["difficulty"],
                    cefr_level=spec["cefr_level"], cover_image_url=None,
                ),
            )
            for it in spec["items"]:
                item_service.create_item(
                    db, admin, created.id,
                    ItemCreateRequest(
                        word=it["word"], meaning=it["meaning"], phonetic=it["phonetic"],
                        part_of_speech=it["part_of_speech"], example=it["example"],
                    ),
                    provenance=ItemProvenance(
                        meaning_confidence=it["meaning_confidence"],
                        meaning_source=it["meaning_source"],
                        example_source=it["example_source"],
                        example_vi=it["example_vi"],
                    ),
                )
            word_set_service.set_publish(db, admin, created.id, PublishRequest(is_public=True))
            print(f"\rBộ từ: {n}/{len(specs)}", end="", flush=True)
        print()

    questions = roadmap_seed.seed_placement_questions(db)
    stages = roadmap_seed.seed_stages(db, admin)
    stages_v2 = roadmap_seed.seed_stages_v2(db, admin)   # tài khoản mới dùng v2
    print(f"Lộ trình: {stages} chặng v1 + {stages_v2} chặng v2 · {questions} câu hỏi xếp lớp")
    print("\nXong. Không có học viên nào — người học tự đăng ký qua link pilot.")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Nạp dữ liệu hệ thống cho pilot")
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--admin-name", default="Quản trị viên")
    args = parser.parse_args()
    with SessionLocal() as db:
        seed(db, admin_email=args.admin_email, admin_password=args.admin_password,
             admin_name=args.admin_name)


if __name__ == "__main__":
    use_utf8_console()
    main()
