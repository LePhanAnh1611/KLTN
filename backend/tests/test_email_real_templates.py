"""EMAIL_REAL_TEMPLATES — ở chế độ smtp chỉ email tài khoản đi ra ngoài.

Test thuần (không cần DB): thay smtplib.SMTP bằng bản giả để đếm email gửi thật.
"""
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import email_service


class _FakeSMTP:
    sent: list = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, message):
        _FakeSMTP.sent.append(message)


def _email(template):
    return SimpleNamespace(
        to_email="hoc-vien@example.com", subject="Tiêu đề", body="Nội dung", template=template,
    )


@pytest.fixture
def smtp_mode(monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(settings, "email_backend", "smtp")
    monkeypatch.setattr(settings, "email_from", "learninghub@gmail.com")
    monkeypatch.setattr(settings, "email_real_templates", "password_reset,email_verify")
    return monkeypatch


@pytest.mark.parametrize("template", ["password_reset", "email_verify"])
def test_email_tai_khoan_gui_that(smtp_mode, template):
    email_service._send_now(_email(template))
    assert len(_FakeSMTP.sent) == 1
    assert "LearningHub" in _FakeSMTP.sent[0]["From"]


@pytest.mark.parametrize("template", ["review_due", "broadcast", "pilot_report", None])
def test_email_khac_chi_ghi_log(smtp_mode, template):
    email_service._send_now(_email(template))
    assert _FakeSMTP.sent == []


def test_dau_sao_gui_tat_ca(smtp_mode):
    smtp_mode.setattr(settings, "email_real_templates", "*")
    email_service._send_now(_email("review_due"))
    assert len(_FakeSMTP.sent) == 1


def test_che_do_log_khong_gui_gi(smtp_mode):
    smtp_mode.setattr(settings, "email_backend", "log")
    email_service._send_now(_email("password_reset"))
    assert _FakeSMTP.sent == []
