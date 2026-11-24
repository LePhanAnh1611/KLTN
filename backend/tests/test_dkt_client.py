"""UC-64 E2 — degrade mềm khi service DKT (UC-68) không sẵn sàng."""
import httpx
import pytest

from app.services import dkt_client

# conftest có fixture autouse thay predict_mastery bằng stub cho mọi test khác;
# ở đây ta cần chính hàm thật nên giữ tham chiếu từ lúc import.
_REAL_PREDICT = dkt_client.predict_mastery


@pytest.fixture(autouse=True)
def _use_real_client(monkeypatch):
    monkeypatch.setattr(dkt_client, "predict_mastery", _REAL_PREDICT)
    dkt_client.reset_circuit()
    yield
    dkt_client.reset_circuit()


def test_empty_targets_skips_call(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("không được gọi HTTP khi không có target")

    monkeypatch.setattr(dkt_client._http, "post", _boom)
    assert dkt_client.predict_mastery([], []) == {}


def test_service_down_returns_none_for_all(monkeypatch):
    def _refused(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(dkt_client._http, "post", _refused)
    assert dkt_client.predict_mastery([], ["apple", "book"]) == {"apple": None, "book": None}


def test_circuit_breaker_stops_repeated_calls(monkeypatch):
    """Sau lần lỗi đầu, các lần sau trả ngay — không gọi HTTP nữa (không tốn timeout)."""
    calls = {"n": 0}

    def _refused(*args, **kwargs):
        calls["n"] += 1
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(dkt_client._http, "post", _refused)

    for _ in range(5):
        assert dkt_client.predict_mastery([], ["apple"]) == {"apple": None}

    assert calls["n"] == 1


def test_circuit_reopens_after_cooldown(monkeypatch):
    """Hết thời gian nghỉ thì thử lại, và khi service sống thì trả kết quả thật."""
    # đồng hồ giả phải áp dụng từ TRƯỚC lần lỗi đầu, để mốc nghỉ tính theo nó
    now = [1000.0]
    monkeypatch.setattr(dkt_client.time, "monotonic", lambda: now[0])

    monkeypatch.setattr(dkt_client._http, "post",
                        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))
    dkt_client.predict_mastery([], ["apple"])

    now[0] += dkt_client.COOLDOWN_SECONDS + 1

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"mastery": {"apple": 0.72}}

    monkeypatch.setattr(dkt_client._http, "post", lambda *a, **k: _Resp())
    assert dkt_client.predict_mastery([], ["apple"]) == {"apple": 0.72}


def test_bad_payload_treated_as_unavailable(monkeypatch):
    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"khong_co_mastery": {}}

    monkeypatch.setattr(dkt_client._http, "post", lambda *a, **k: _Resp())
    assert dkt_client.predict_mastery([], ["apple"]) == {"apple": None}
