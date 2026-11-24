import pytest
from fastapi import HTTPException

from app.api.deps import require_role
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user


def _create_learner(db_session) -> User:
    return register_user(
        db_session,
        RegisterRequest(
            email="rbac.learner@example.com",
            password="Abcd1234",
            password_confirm="Abcd1234",
            display_name="RBAC Learner",
        ),
    )


def _create_admin(db_session) -> User:
    user = User(
        email="rbac.admin@example.com",
        password_hash="not-used-in-this-test",
        display_name="RBAC Admin",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_require_role_allows_matching_role(db_session):
    admin = _create_admin(db_session)
    dependency = require_role("admin")

    result = dependency(current_user=admin)

    assert result.id == admin.id


def test_require_role_rejects_other_role(db_session):
    learner = _create_learner(db_session)
    dependency = require_role("admin")

    with pytest.raises(HTTPException) as exc_info:
        dependency(current_user=learner)

    assert exc_info.value.status_code == 403


def test_require_role_accepts_multiple_allowed_roles(db_session):
    learner = _create_learner(db_session)
    admin = _create_admin(db_session)
    dependency = require_role("admin", "learner")

    assert dependency(current_user=learner).id == learner.id
    assert dependency(current_user=admin).id == admin.id
