"""UC-72 tổng quan · UC-73 quản lý người dùng · UC-83 nhật ký hệ thống (Admin)."""
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_permission
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminOverview,
    AdminUserListResponse,
    AdminUserRow,
    AdminWordSetListResponse,
    AdminWordSetRow,
    AchievementCreate,
    AchievementDefinition,
    AchievementUpdate,
    AuditLogListResponse,
    BroadcastRequest,
    BroadcastResult,
    CategoryAdminRow,
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    EmailQueueListResponse,
    EmailQueueRow,
    ModerationDecision,
    ModerationPost,
    ModerationPostListResponse,
    ReportDecision,
    ReportListResponse,
    ReportRow,
    PermissionInfo,
    RolePermissionMatrix,
    RolePermissionUpdate,
    SystemConfigItem,
    SystemConfigUpdate,
    UserActiveUpdate,
    UserRoleUpdate,
    WordSetAdminUpdate,
)
from app.schemas.model_monitor import MetricPoint, ModelHealth
from app.schemas.pilot import PilotReport
from app.schemas.scheduler_experiment import SchedulerComparison
from app.schemas.speaking import SpeakingAppealAdminRow
from app.schemas.placement import (
    PlacementBankStats,
    PlacementQuestionAdminRow,
    PlacementQuestionCreate,
    PlacementQuestionUpdate,
)
from app.services import (
    achievement_service,
    admin_service,
    audit_service,
    broadcast_service,
    category_service,
    config_service,
    model_monitor_service,
    scheduler_experiment_service,
    moderation_service,
    permission_service,
    pilot_service,
    placement_service,
    speaking_history_service,
)

router = APIRouter()


@router.get("/overview", response_model=AdminOverview)
def get_overview(
    _: User = Depends(require_permission("admin.overview")),
    db: Session = Depends(get_db),
) -> AdminOverview:
    """UC-72 — chỉ số tổng quan toàn hệ thống."""
    return admin_service.get_overview(db)


@router.get("/pilot", response_model=PilotReport)
def get_pilot_report(
    _: User = Depends(require_permission("admin.overview")),
    db: Session = Depends(get_db),
) -> PilotReport:
    """Pilot — theo dõi đợt thử nghiệm: ai đang học, đã đủ dữ liệu calibrate chưa."""
    return pilot_service.build_report(db)


@router.post("/pilot/send-report", response_model=PilotReport)
def send_pilot_report(
    _: User = Depends(require_permission("admin.overview")),
    db: Session = Depends(get_db),
) -> PilotReport:
    """Gửi ngay email báo cáo pilot (bình thường scheduler gửi lúc 21h)."""
    return pilot_service.send_report(db)


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    q: str | None = Query(default=None, description="Tìm theo email hoặc tên"),
    role: str | None = None,
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_permission("admin.users")),
    db: Session = Depends(get_db),
) -> AdminUserListResponse:
    """UC-73 — tìm/lọc người dùng."""
    return admin_service.list_users(
        db, current_user, search=q, role=role, is_active=is_active,
        page=page, page_size=page_size,
    )


@router.patch("/users/{user_id}/role", response_model=AdminUserRow)
def set_user_role(
    user_id: int,
    data: UserRoleUpdate,
    current_user: User = Depends(require_permission("admin.users")),
    db: Session = Depends(get_db),
) -> AdminUserRow:
    """UC-73 — đổi vai trò (E1: không tự đổi quyền của mình)."""
    return admin_service.set_user_role(db, current_user, user_id, data)


@router.patch("/users/{user_id}/active", response_model=AdminUserRow)
def set_user_active(
    user_id: int,
    data: UserActiveUpdate,
    current_user: User = Depends(require_permission("admin.users")),
    db: Session = Depends(get_db),
) -> AdminUserRow:
    """UC-73 — khóa/mở khóa tài khoản (E1: không tự khóa mình)."""
    return admin_service.set_user_active(db, current_user, user_id, data)


@router.get("/word-sets", response_model=AdminWordSetListResponse)
def list_word_sets(
    q: str | None = Query(default=None, description="Tìm theo tên bộ từ vựng"),
    is_public: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("admin.word_sets")),
    db: Session = Depends(get_db),
) -> AdminWordSetListResponse:
    """UC-75 — kho bộ từ toàn hệ thống."""
    return admin_service.list_word_sets(
        db, search=q, is_public=is_public, page=page, page_size=page_size,
    )


@router.patch("/word-sets/{word_set_id}", response_model=AdminWordSetRow)
def update_word_set(
    word_set_id: int,
    data: WordSetAdminUpdate,
    current_user: User = Depends(require_permission("admin.word_sets")),
    db: Session = Depends(get_db),
) -> AdminWordSetRow:
    """UC-75 — gắn/bỏ nổi bật (khép UC-22) hoặc gỡ công khai."""
    return admin_service.update_word_set(db, current_user, word_set_id, data)


@router.delete("/word-sets/{word_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word_set(
    word_set_id: int,
    current_user: User = Depends(require_permission("admin.word_sets")),
    db: Session = Depends(get_db),
) -> Response:
    """UC-75 E1 — xóa mềm bộ từ (Q6)."""
    admin_service.delete_word_set(db, current_user, word_set_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/config", response_model=list[SystemConfigItem])
def list_config(
    _: User = Depends(require_permission("admin.config")),
) -> list[SystemConfigItem]:
    """UC-81 bước 1 — tham số vận hành hiện tại."""
    return [SystemConfigItem(**c) for c in config_service.list_configs()]


@router.put("/config", response_model=list[SystemConfigItem])
def update_config(
    data: SystemConfigUpdate,
    current_user: User = Depends(require_permission("admin.config")),
    db: Session = Depends(get_db),
) -> list[SystemConfigItem]:
    """UC-81 bước 2/3 — lưu tham số (E1 chặn giá trị ngoài khoảng) + ghi AUDIT_LOG."""
    changes = config_service.set_values(db, data.values)
    if changes:
        audit_service.log(
            db, current_user, action="config.update",
            target_type="config", detail="; ".join(changes),
        )
    return [SystemConfigItem(**c) for c in config_service.list_configs()]


@router.get("/posts", response_model=ModerationPostListResponse)
def list_posts_for_moderation(
    status_filter: str = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("admin.moderation")),
    db: Session = Depends(get_db),
) -> ModerationPostListResponse:
    """UC-77 — hàng đợi bài chờ duyệt (hoặc lọc theo trạng thái khác)."""
    return moderation_service.list_posts_for_moderation(
        db, post_status=status_filter, page=page, page_size=page_size,
    )


@router.patch("/posts/{post_id}", response_model=ModerationPost)
def moderate_post(
    post_id: int,
    data: ModerationDecision,
    current_user: User = Depends(require_permission("admin.moderation")),
    db: Session = Depends(get_db),
) -> ModerationPost:
    """UC-77 — duyệt / từ chối / gỡ bài."""
    return moderation_service.moderate_post(db, current_user, post_id, data)


@router.get("/reports", response_model=ReportListResponse)
def list_reports(
    status_filter: str = Query(default="pending", alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("admin.reports")),
    db: Session = Depends(get_db),
) -> ReportListResponse:
    """UC-78 — hàng đợi báo cáo từ UC-24/UC-53."""
    return moderation_service.list_reports(
        db, report_status=status_filter, page=page, page_size=page_size,
    )


@router.patch("/reports/{report_id}", response_model=ReportRow)
def resolve_report(
    report_id: int,
    data: ReportDecision,
    current_user: User = Depends(require_permission("admin.reports")),
    db: Session = Depends(get_db),
) -> ReportRow:
    """UC-78 — bỏ qua hoặc gỡ nội dung bị báo cáo."""
    return moderation_service.resolve_report(db, current_user, report_id, data)


@router.post("/broadcast", response_model=BroadcastResult)
def send_broadcast(
    data: BroadcastRequest,
    current_user: User = Depends(require_permission("admin.emails")),
    db: Session = Depends(get_db),
) -> BroadcastResult:
    """UC-82 — gửi thông báo (và tùy chọn email) tới toàn bộ/nhóm người dùng."""
    return broadcast_service.send_broadcast(db, current_user, data)


@router.get("/emails", response_model=EmailQueueListResponse)
def list_emails(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("admin.emails")),
    db: Session = Depends(get_db),
) -> EmailQueueListResponse:
    """UC-80 — hàng đợi email (lọc theo trạng thái)."""
    return broadcast_service.list_emails(
        db, email_status=status_filter, page=page, page_size=page_size,
    )


@router.post("/emails/{email_id}/retry", response_model=EmailQueueRow)
def retry_email(
    email_id: int,
    current_user: User = Depends(require_permission("admin.emails")),
    db: Session = Depends(get_db),
) -> EmailQueueRow:
    """UC-80 — thử gửi lại email thất bại."""
    return broadcast_service.retry_email(db, current_user, email_id)


@router.delete("/emails/{email_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_email(
    email_id: int,
    current_user: User = Depends(require_permission("admin.emails")),
    db: Session = Depends(get_db),
) -> Response:
    """UC-80 — xóa email khỏi hàng đợi."""
    broadcast_service.delete_email(db, current_user, email_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/categories", response_model=list[CategoryAdminRow])
def list_categories(
    _: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> list[CategoryAdminRow]:
    """UC-76 — mọi danh mục (kể cả đang tắt) kèm số bộ từ đang gắn."""
    counts = category_service.word_set_counts(db)
    return [
        CategoryAdminRow(
            **CategoryResponse.model_validate(c).model_dump(),
            word_set_count=counts.get(c.name, 0),
        )
        for c in category_service.list_categories(db, only_active=False)
    ]


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    """UC-76 — thêm danh mục."""
    category = category_service.create_category(db, data)
    audit_service.log(
        db, current_user, action="category.create", target_type="category",
        target_id=category.id, detail=category.name,
    )
    return CategoryResponse.model_validate(category)


@router.patch("/categories/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> CategoryResponse:
    """UC-76 — sửa danh mục (đổi tên thì đồng bộ các bộ từ đang gắn)."""
    category = category_service.update_category(db, category_id, data)
    audit_service.log(
        db, current_user, action="category.update", target_type="category",
        target_id=category.id, detail=category.name,
    )
    return CategoryResponse.model_validate(category)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> Response:
    """UC-76 E1 — còn bộ từ đang gắn thì chặn xóa."""
    name = category_service.get_category(db, category_id).name
    category_service.delete_category(db, category_id)
    audit_service.log(
        db, current_user, action="category.delete", target_type="category",
        target_id=category_id, detail=name,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/achievements", response_model=list[AchievementDefinition])
def list_achievement_definitions(
    _: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> list[AchievementDefinition]:
    """UC-79 — mọi định nghĩa huy hiệu, kể cả đang tắt."""
    return [
        AchievementDefinition.model_validate(a)
        for a in achievement_service.list_definitions(db)
    ]


@router.post("/achievements", response_model=AchievementDefinition, status_code=status.HTTP_201_CREATED)
def create_achievement(
    data: AchievementCreate,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> AchievementDefinition:
    """UC-79 — thêm định nghĩa huy hiệu."""
    achievement = achievement_service.create_definition(db, data)
    audit_service.log(
        db, current_user, action="achievement.create", target_type="achievement",
        target_id=achievement.id, detail=achievement.code,
    )
    return AchievementDefinition.model_validate(achievement)


@router.patch("/achievements/{achievement_id}", response_model=AchievementDefinition)
def update_achievement(
    achievement_id: int,
    data: AchievementUpdate,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> AchievementDefinition:
    """UC-79 — sửa định nghĩa (mã huy hiệu giữ nguyên)."""
    achievement = achievement_service.update_definition(db, achievement_id, data)
    audit_service.log(
        db, current_user, action="achievement.update", target_type="achievement",
        target_id=achievement.id, detail=achievement.code,
    )
    return AchievementDefinition.model_validate(achievement)


@router.delete("/achievements/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_achievement(
    achievement_id: int,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> Response:
    """UC-79 — xóa định nghĩa (huy hiệu đã cấp cho người dùng vẫn giữ)."""
    code = achievement_service.get_definition(db, achievement_id).code
    achievement_service.delete_definition(db, achievement_id)
    audit_service.log(
        db, current_user, action="achievement.delete", target_type="achievement",
        target_id=achievement_id, detail=code,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/my-permissions", response_model=list[str])
def get_my_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[str]:
    """UC-74 — quyền của chính người đang đăng nhập (rỗng nếu không có quyền
    quản trị nào). Frontend dùng để hiện đúng các mục vận hành."""
    return sorted(permission_service.get_matrix(db).get(current_user.role, set()))


@router.get("/permissions", response_model=RolePermissionMatrix)
def get_permission_matrix(
    _: User = Depends(require_permission("admin.roles")),
    db: Session = Depends(get_db),
) -> RolePermissionMatrix:
    """UC-74 bước 1 — danh mục quyền & ma trận vai trò ↔ quyền."""
    matrix = permission_service.get_matrix(db)
    return RolePermissionMatrix(
        permissions=[PermissionInfo(**p) for p in permission_service.list_catalog()],
        roles=list(permission_service.ROLES),
        matrix={role: sorted(keys) for role, keys in matrix.items()},
    )


@router.put("/permissions/{role}", response_model=RolePermissionMatrix)
def set_role_permissions(
    role: str,
    data: RolePermissionUpdate,
    current_user: User = Depends(require_permission("admin.roles")),
    db: Session = Depends(get_db),
) -> RolePermissionMatrix:
    """UC-74 bước 2/3 — gán/bỏ quyền cho vai trò + ghi AUDIT_LOG."""
    changes = permission_service.set_role_permissions(db, role, data.permissions)
    if changes:
        audit_service.log(
            db, current_user, action="role.permissions_change",
            target_type="role", detail=f"{role}: {' '.join(changes)}",
        )
    matrix = permission_service.get_matrix(db)
    return RolePermissionMatrix(
        permissions=[PermissionInfo(**p) for p in permission_service.list_catalog()],
        roles=list(permission_service.ROLES),
        matrix={r: sorted(keys) for r, keys in matrix.items()},
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def list_audit_logs(
    action: str | None = None,
    actor_id: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("admin.audit")),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """UC-83 — nhật ký thao tác quản trị."""
    return audit_service.list_logs(
        db, action=action, actor_id=actor_id, page=page, page_size=page_size,
    )


# ---- UC-11 · Ngân hàng câu hỏi kiểm tra đầu vào ----


@router.get("/placement-questions", response_model=list[PlacementQuestionAdminRow])
def list_placement_questions(
    cefr_level: str | None = None,
    _: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> list[PlacementQuestionAdminRow]:
    """UC-11 — toàn bộ ngân hàng câu hỏi (kể cả câu đang tắt), kèm đáp án đúng."""
    return [
        PlacementQuestionAdminRow.model_validate(q)
        for q in placement_service.list_questions(db, cefr_level=cefr_level)
    ]


@router.get("/placement-questions/stats", response_model=list[PlacementBankStats])
def placement_bank_stats(
    _: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> list[PlacementBankStats]:
    """UC-11 — số câu đang bật theo từng mức, để thấy mức nào còn mỏng."""
    return placement_service.bank_stats(db)


@router.post(
    "/placement-questions",
    response_model=PlacementQuestionAdminRow,
    status_code=status.HTTP_201_CREATED,
)
def create_placement_question(
    data: PlacementQuestionCreate,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> PlacementQuestionAdminRow:
    """UC-11 — thêm câu hỏi (E1: các lựa chọn trùng nhau -> 400)."""
    question = placement_service.create_question(db, data)
    audit_service.log(
        db, current_user, action="placement_question.create",
        target_type="placement_question", target_id=question.id,
        detail=f"[{question.cefr_level}] {question.word}",
    )
    return PlacementQuestionAdminRow.model_validate(question)


@router.patch("/placement-questions/{question_id}", response_model=PlacementQuestionAdminRow)
def update_placement_question(
    question_id: int,
    data: PlacementQuestionUpdate,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> PlacementQuestionAdminRow:
    """UC-11 — sửa câu hỏi, hoặc bật/tắt việc đưa câu đó ra đề."""
    question = placement_service.update_question(db, question_id, data)
    audit_service.log(
        db, current_user, action="placement_question.update",
        target_type="placement_question", target_id=question.id,
        detail=f"[{question.cefr_level}] {question.word}",
    )
    return PlacementQuestionAdminRow.model_validate(question)


@router.delete("/placement-questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_placement_question(
    question_id: int,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> None:
    """UC-11 — xóa hẳn câu hỏi (muốn giữ mà không ra đề thì tắt is_active)."""
    placement_service.delete_question(db, question_id)
    audit_service.log(
        db, current_user, action="placement_question.delete",
        target_type="placement_question", target_id=question_id,
    )


# ---- UC-70 · Giám sát hiệu năng mô hình ----


@router.get("/model-health", response_model=ModelHealth)
def model_health(
    days: int = Query(default=7, ge=1, le=90),
    _: User = Depends(require_permission("admin.overview")),
    db: Session = Depends(get_db),
) -> ModelHealth:
    """UC-70 — sức khỏe mô hình đo trên dữ liệu hệ thống (không phải AUC tập test)."""
    return model_monitor_service.compute_health(db, days=days)


@router.post("/model-health/snapshot", response_model=ModelHealth)
def snapshot_model_health(
    days: int = Query(default=7, ge=1, le=90),
    current_user: User = Depends(require_permission("admin.jobs")),
    db: Session = Depends(get_db),
) -> ModelHealth:
    """UC-70 — chốt số đo hiện tại để vẽ được đường theo thời gian."""
    health = model_monitor_service.record_snapshot(db, days=days)
    audit_service.log(
        db, current_user, action="model.snapshot", target_type="model",
        detail=f"{health.model_name}: coverage={health.coverage}",
    )
    return health


@router.get("/model-health/history", response_model=list[MetricPoint])
def model_health_history(
    metric: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_permission("admin.overview")),
    db: Session = Depends(get_db),
) -> list[MetricPoint]:
    """UC-70 — chuỗi thời gian đã chốt (cũ -> mới)."""
    return model_monitor_service.list_history(db, metric=metric, limit=limit)


# ---- UC-93 · So sánh định lượng lịch ôn DKT với SM-2 ----


@router.get("/scheduler-comparison", response_model=SchedulerComparison)
def scheduler_comparison(
    _: User = Depends(require_permission("admin.overview")),
) -> SchedulerComparison:
    """UC-93 — kết quả mô phỏng so lịch ôn DKT (UC-66) với SM-2 (UC-34).

    Chỉ đọc file `docs/experiments/scheduler_comparison.json` do
    `ml/src/schedule_sim.py` sinh ra. Đây là số liệu cho chương thực nghiệm nên
    KHÔNG hiện ở giao diện người học — nó không nói gì về việc học của họ, và
    một con số nội bộ đặt nhầm chỗ chỉ gây hiểu lầm.
    """
    return scheduler_experiment_service.get_comparison()


# ---- Hàng đợi phản hồi kết quả chấm nói (rubric mục 9) ----


@router.get("/speaking-appeals", response_model=list[SpeakingAppealAdminRow])
def list_speaking_appeals(
    only_open: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> list[SpeakingAppealAdminRow]:
    """Phản hồi của người học về kết quả chấm nói.

    Dùng để calibrate rubric (mục 8 bước 4): `gap` càng lớn thì descriptor ở mức
    đó càng mơ hồ, nên xem trước.
    """
    return [
        SpeakingAppealAdminRow(**row)
        for row in speaking_history_service.list_appeals(db, only_open=only_open, limit=limit)
    ]


@router.post("/speaking-appeals/{appeal_id}/reviewed", status_code=status.HTTP_204_NO_CONTENT)
def mark_speaking_appeal_reviewed(
    appeal_id: int,
    current_user: User = Depends(require_permission("admin.content")),
    db: Session = Depends(get_db),
) -> Response:
    """Đánh dấu đã xem xét (không sửa điểm của người học)."""
    speaking_history_service.mark_reviewed(db, appeal_id)
    audit_service.log(
        db, current_user, action="speaking_appeal.reviewed",
        target_type="speaking_appeal", target_id=appeal_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
