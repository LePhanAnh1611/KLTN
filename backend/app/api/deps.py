from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token không hợp lệ hoặc đã hết hạn",
    )

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise unauthorized from exc

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise unauthorized

    return user


def require_permission(permission: str) -> Callable[..., User]:
    """RBAC theo quyền (UC-74): `Depends(require_permission("admin.users"))`.

    Quyền của từng vai trò lấy từ ma trận ROLE_PERMISSIONS nên Admin đổi ma trận
    là đổi quyền truy cập thật, không cần sửa code.
    """

    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from app.services import permission_service

        if not permission_service.has_permission(db, current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập",
            )
        return current_user

    return dependency


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """RBAC guard: `Depends(require_role("admin"))` restricts a route to those roles.

    Chains onto get_current_user, so it also enforces a valid, active session.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không có quyền truy cập",
            )
        return current_user

    return dependency
