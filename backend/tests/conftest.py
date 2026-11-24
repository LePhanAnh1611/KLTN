import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.base import Base

engine = create_engine(settings.test_database_url)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def _disable_scheduler():
    """Test không chạy tác vụ nền (UC-62/UC-63) — job được gọi trực tiếp khi cần."""
    settings.scheduler_enabled = False


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _reset_system_config():
    """UC-81: mỗi test bắt đầu với cache cấu hình rỗng -> dùng giá trị mặc định
    (và không đụng tới DB dev khi nạp lazy)."""
    from app.services import config_service

    config_service._cache = {}
    yield
    config_service._cache = {}


@pytest.fixture(autouse=True)
def _stub_dkt(monkeypatch):
    """Mặc định KHÔNG gọi service DKT thật trong test (hermetic + nhanh).
    Test cần mastery cụ thể sẽ tự monkeypatch đè lại."""
    from app.services import dkt_client

    monkeypatch.setattr(dkt_client, "predict_mastery", lambda history, targets, **kwargs: {t: None for t in targets})


@pytest.fixture
def db_session():
    # service code calls db.commit(); use a SAVEPOINT that auto-restarts after
    # each commit so the outer transaction can still be rolled back at the end.
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
