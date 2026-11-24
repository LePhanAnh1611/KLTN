"""UC-97 — nạp kho video Shadowing từ `data/shadowing_catalog.json`.

    python -m app.scripts.seed_shadowing              # tạo bản NHÁP, admin duyệt rồi xuất bản
    python -m app.scripts.seed_shadowing --publish    # xuất bản luôn (đủ chủ đề + giấy phép)
    python -m app.scripts.seed_shadowing --dry-run    # chỉ liệt kê, không gọi YouTube

Chạy lại được nhiều lần: video đã có trong kho (cùng youtube_id) thì bỏ qua,
không đụng tới câu admin đã sửa hay lịch sử luyện. Mục có `youtube_id: null`
(chưa tìm được link) cũng bỏ qua — điền link vào file rồi chạy lại.

Phụ đề lấy từ YouTube lúc chạy và CHỈ lưu trong DB, không ghi ra file nào.
Cần mạng tới YouTube; video nào lỗi thì in lý do và chạy tiếp video sau.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.shadowing import ShadowingVideo
from app.models.user import User
from app.services import audit_service, shadowing_service

DEFAULT_CATALOG = Path(__file__).resolve().parents[2] / "data" / "shadowing_catalog.json"


def _find_admin(db, email: str | None) -> User | None:
    stmt = select(User).where(User.role == "admin")
    if email:
        stmt = select(User).where(User.email == email)
    return db.scalars(stmt.order_by(User.id)).first()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--publish", action="store_true", help="Xuất bản ngay sau khi nạp")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ liệt kê, không ghi DB")
    parser.add_argument("--admin-email", help="Tài khoản ghi vào nhật ký (mặc định: admin đầu tiên)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Giây nghỉ giữa hai video để YouTube không chặn")
    args = parser.parse_args()

    entries = json.loads(args.catalog.read_text(encoding="utf-8"))["videos"]
    created = skipped = missing = failed = 0

    with SessionLocal() as db:
        admin = _find_admin(db, args.admin_email)
        for entry in entries:
            label = f"[{entry['topic']}] {entry['title']}"
            youtube_id = entry.get("youtube_id")
            if not youtube_id:
                missing += 1
                print(f"  -  chưa có link YouTube: {label}")
                continue

            exists = db.scalar(select(ShadowingVideo).where(
                ShadowingVideo.youtube_id == youtube_id,
                ShadowingVideo.source == "catalog",
                ShadowingVideo.deleted_at.is_(None),
            ))
            if exists is not None:
                skipped += 1
                print(f"  =  đã có (#{exists.id}): {label}")
                continue
            if args.dry_run:
                print(f"  ?  sẽ nạp: {label}")
                continue

            try:
                data = shadowing_service.build_video_data(youtube_id)
            except HTTPException as exc:
                failed += 1
                print(f"  !  LỖI ({exc.status_code}) {label}: {exc.detail}")
                time.sleep(args.delay)
                continue

            data["title"] = entry.get("title") or data["title"]
            video = ShadowingVideo(
                **data, topic=entry["topic"], license=entry["license"],
                attribution=entry.get("attribution"), source="catalog",
                created_by=admin.id if admin else None,
                status="published" if args.publish else "draft",
                published_at=datetime.now(timezone.utc) if args.publish else None,
            )
            db.add(video)
            db.flush()
            if admin is not None:
                audit_service.log(db, admin, action="shadowing.seed",
                                  target_type="shadowing_video", target_id=video.id,
                                  detail=f"{youtube_id} — {video.title}", commit=False)
            db.commit()
            created += 1
            print(f"  +  #{video.id} {label} — {len(video.segments)} câu, "
                  f"cấp độ {video.cefr_level or '?'}, phụ đề {video.caption_kind}")
            time.sleep(args.delay)

    state = "đã xuất bản" if args.publish else "bản nháp (vào Vận hành → Shadowing để duyệt)"
    print(f"\nNạp mới {created} ({state}) · đã có {skipped} · chưa có link {missing} · lỗi {failed}")


if __name__ == "__main__":
    main()
