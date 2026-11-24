"""UC-74 — vai trò & phân quyền (RBAC theo quyền, không chỉ theo vai trò).

Danh mục quyền khai báo trong code vì mỗi quyền gắn với một nhóm endpoint; ma
trận "vai trò nào có quyền nào" nằm ở bảng ROLE_PERMISSIONS để Admin sửa được.
`deps.require_permission()` là chỗ thực thi — đổi ma trận là đổi quyền truy cập thật.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.role_permission import RolePermission

ROLES = ("learner", "content", "admin")


@dataclass(frozen=True)
class Permission:
    key: str
    label: str
    description: str


PERMISSIONS: list[Permission] = [
    Permission("admin.overview", "Xem tổng quan", "Chỉ số toàn hệ thống (UC-72)"),
    Permission("admin.users", "Quản lý người dùng", "Khóa/mở, đổi vai trò (UC-73)"),
    Permission("admin.roles", "Quản lý phân quyền", "Sửa ma trận quyền (UC-74)"),
    Permission("admin.word_sets", "Quản lý kho bộ từ vựng", "Nổi bật, gỡ công khai, xóa (UC-75)"),
    Permission("admin.content", "Quản lý nội dung",
               "Danh mục, huy hiệu & ngân hàng câu hỏi đầu vào (UC-76, UC-79, UC-11)"),
    Permission("admin.moderation", "Kiểm duyệt bài viết", "Duyệt/từ chối/gỡ bài (UC-77)"),
    Permission("admin.reports", "Xử lý báo cáo", "Hàng đợi báo cáo vi phạm (UC-78)"),
    Permission("admin.emails", "Quản lý email", "Hàng đợi & broadcast (UC-80, UC-82)"),
    Permission("admin.config", "Cấu hình hệ thống", "Ngưỡng vận hành (UC-81)"),
    Permission("admin.audit", "Xem nhật ký", "Audit log (UC-83)"),
    Permission("admin.jobs", "Chạy tác vụ nền", "Nhắc ôn & đẩy email (UC-62, UC-63)"),
]
_KEYS = {p.key for p in PERMISSIONS}

# Quyền tối thiểu của 'admin' — không cho gỡ để tránh tự khóa mình ra ngoài.
PROTECTED_ADMIN_PERMISSIONS = {"admin.roles"}

DEFAULT_GRANTS: dict[str, set[str]] = {
    "admin": set(_KEYS),
    # Biên tập viên: lo nội dung & kiểm duyệt, không đụng người dùng/cấu hình
    "content": {"admin.overview", "admin.word_sets", "admin.content",
                "admin.moderation", "admin.reports"},
    "learner": set(),
}


def ensure_seeded(db: Session) -> None:
    """Nạp ma trận mặc định nếu bảng còn trống."""
    if db.execute(select(func.count()).select_from(RolePermission)).scalar_one():
        return
    db.add_all([
        RolePermission(role=role, permission=key)
        for role, keys in DEFAULT_GRANTS.items()
        for key in sorted(keys)
    ])
    db.commit()


def get_matrix(db: Session) -> dict[str, set[str]]:
    """{vai trò: tập quyền}."""
    ensure_seeded(db)
    matrix: dict[str, set[str]] = {role: set() for role in ROLES}
    for role, key in db.execute(select(RolePermission.role, RolePermission.permission)).all():
        matrix.setdefault(role, set()).add(key)
    return matrix


def has_permission(db: Session, role: str, key: str) -> bool:
    return key in get_matrix(db).get(role, set())


def set_role_permissions(db: Session, role: str, keys: list[str]) -> list[str]:
    """UC-74 bước 2 — đặt lại tập quyền của một vai trò. Trả mô tả thay đổi (cho audit)."""
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Vai trò không hợp lệ: {role}"
        )

    unknown = set(keys) - _KEYS
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quyền không hợp lệ: {', '.join(sorted(unknown))}",
        )

    new_keys = set(keys)
    if role == "admin" and not PROTECTED_ADMIN_PERMISSIONS <= new_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể gỡ quyền quản lý phân quyền của vai trò admin",
        )

    current = get_matrix(db).get(role, set())
    added = sorted(new_keys - current)
    removed = sorted(current - new_keys)

    for key in removed:
        row = db.execute(
            select(RolePermission).where(
                RolePermission.role == role, RolePermission.permission == key
            )
        ).scalar_one_or_none()
        if row is not None:
            db.delete(row)
    db.add_all([RolePermission(role=role, permission=key) for key in added])
    db.commit()

    changes = []
    if added:
        changes.append(f"+{', '.join(added)}")
    if removed:
        changes.append(f"-{', '.join(removed)}")
    return changes


def list_catalog() -> list[dict]:
    """UC-74 bước 1 — danh mục quyền kèm mô tả."""
    return [{"key": p.key, "label": p.label, "description": p.description} for p in PERMISSIONS]
