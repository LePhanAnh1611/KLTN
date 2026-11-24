"""Synchronize CEFR stages without resetting accounts or learning history.

Run: python -m app.scripts.sync_roadmap

Đồng bộ CẢ HAI phiên bản lộ trình. Mỗi hàm chỉ đụng chặng của phiên bản mình:
- v1 (cắt theo tần suất) — học viên pilot / tài khoản có trước migration rmv2
- v2 (track chủ đề + cốt lõi) — tài khoản mới
"""
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.user import User
from app.services.roadmap_seed import seed_stages, seed_stages_v2


def main() -> None:
    with SessionLocal() as db:
        owner = db.execute(select(User).where(User.role == "admin").order_by(User.id)).scalars().first()
        if owner is None:
            raise RuntimeError("Create a content administrator before synchronizing stages")
        print(f"Synchronized {seed_stages(db, owner)} CEFR stages (v1)")
        print(f"Synchronized {seed_stages_v2(db, owner)} CEFR stages (v2: chủ đề + cốt lõi)")


if __name__ == "__main__":
    main()
