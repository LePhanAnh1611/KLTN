"""UC-72 tổng quan · UC-73 người dùng · UC-83 nhật ký hệ thống."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UserRole = Literal["learner", "content", "admin"]


class AdminOverview(BaseModel):
    """UC-72 — chỉ số tổng quan toàn hệ thống."""

    total_users: int
    active_users: int
    dau: int                 # người học có phiên hoàn thành hôm nay
    mau: int                 # ... trong 30 ngày
    total_sessions: int
    total_interactions: int
    total_word_sets: int
    public_word_sets: int
    total_items: int
    total_posts: int
    pending_reports: int


class AdminUserRow(BaseModel):
    """UC-73 — một dòng trong danh sách người dùng."""

    id: int
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    xp: int
    is_me: bool


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserActiveUpdate(BaseModel):
    is_active: bool
    reason: str | None = Field(default=None, max_length=200)


class AdminWordSetRow(BaseModel):
    """UC-75 — một dòng trong kho bộ từ."""

    id: int
    name: str
    owner_id: int
    owner_name: str
    category: str | None
    difficulty: str | None
    is_public: bool
    is_featured: bool
    download_count: int
    item_count: int
    created_at: datetime


class AdminWordSetListResponse(BaseModel):
    items: list[AdminWordSetRow]
    total: int
    page: int
    page_size: int


class WordSetAdminUpdate(BaseModel):
    """UC-75 — gắn/bỏ nổi bật (UC-22) và gỡ công khai."""

    is_featured: bool | None = None
    is_public: bool | None = None


class SystemConfigItem(BaseModel):
    """UC-81 — một tham số vận hành."""

    key: str
    value: float | int | bool
    value_type: str
    label: str
    description: str
    minimum: float | None
    maximum: float | None
    default: float | int | bool


class SystemConfigUpdate(BaseModel):
    """UC-81 — {key: value} các tham số cần đổi."""

    values: dict[str, float | int | bool]


class ModerationPost(BaseModel):
    """UC-77 — bài viết trong hàng đợi kiểm duyệt."""

    id: int
    post_type: str
    content: str
    image_url: str | None
    status: str
    created_at: datetime
    author_id: int
    author_name: str


class ModerationPostListResponse(BaseModel):
    items: list[ModerationPost]
    total: int
    page: int
    page_size: int


class ModerationDecision(BaseModel):
    """UC-77 — duyệt / từ chối / gỡ bài."""

    decision: Literal["approve", "reject", "remove"]
    reason: str | None = Field(default=None, max_length=200)


class ReportRow(BaseModel):
    """UC-78 — một báo cáo trong hàng đợi."""

    id: int
    target_type: str
    target_id: int
    reason: str
    description: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None
    reporter_id: int
    reporter_name: str
    target_preview: str | None       # tên bộ từ / trích nội dung bài
    target_exists: bool              # đối tượng còn hiển thị công khai không


class ReportListResponse(BaseModel):
    items: list[ReportRow]
    total: int
    page: int
    page_size: int


class ReportDecision(BaseModel):
    """UC-78 — bỏ qua hoặc gỡ nội dung bị báo cáo."""

    decision: Literal["dismiss", "remove_content"]
    note: str | None = Field(default=None, max_length=200)


class EmailQueueRow(BaseModel):
    """UC-80 — một email trong hàng đợi."""

    id: int
    to_email: str
    subject: str
    template: str | None
    status: str
    attempts: int
    last_error: str | None
    scheduled_at: datetime | None
    sent_at: datetime | None
    created_at: datetime


class EmailQueueListResponse(BaseModel):
    items: list[EmailQueueRow]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]   # {pending: n, sent: n, failed: n}


class BroadcastRequest(BaseModel):
    """UC-82 — thông báo tới toàn bộ / một nhóm người dùng."""

    title: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=1000)
    link: str | None = Field(default=None, max_length=200)
    audience: Literal["all", "role"] = "all"
    role: UserRole | None = None       # bắt buộc khi audience='role'
    send_email: bool = False


class BroadcastResult(BaseModel):
    recipients: int
    notifications_created: int
    emails_queued: int


class CategoryResponse(BaseModel):
    """UC-76 — danh mục bộ từ."""

    model_config = {"from_attributes": True}

    id: int
    name: str
    description: str | None
    is_active: bool
    sort_order: int


class CategoryAdminRow(CategoryResponse):
    word_set_count: int = 0     # số bộ từ đang gắn (chặn xóa khi > 0)


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    sort_order: int | None = None


class AchievementDefinition(BaseModel):
    """UC-79 — định nghĩa huy hiệu."""

    model_config = {"from_attributes": True}

    id: int
    code: str
    name: str
    description: str
    condition_key: str
    threshold: int
    icon: str | None
    is_active: bool
    sort_order: int


class AchievementCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    condition_key: str
    threshold: int = Field(ge=1)
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool = True
    sort_order: int = 0


class AchievementUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    condition_key: str | None = None
    threshold: int | None = Field(default=None, ge=1)
    icon: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None
    sort_order: int | None = None


class PermissionInfo(BaseModel):
    """UC-74 — một quyền trong danh mục."""

    key: str
    label: str
    description: str


class RolePermissionMatrix(BaseModel):
    """UC-74 bước 1 — danh mục quyền + vai trò nào đang có quyền nào."""

    permissions: list[PermissionInfo]
    roles: list[str]
    matrix: dict[str, list[str]]


class RolePermissionUpdate(BaseModel):
    """UC-74 bước 2 — đặt lại tập quyền của một vai trò."""

    permissions: list[str]


class AuditLogEntry(BaseModel):
    """UC-83 — một mục nhật ký."""

    id: int
    action: str
    target_type: str | None
    target_id: int | None
    detail: str | None
    actor_id: int | None
    actor_name: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int
    page: int
    page_size: int
