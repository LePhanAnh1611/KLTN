"""UC-93 — so sánh định lượng lịch ôn DKT với SM-2.

Hai nhóm test khác hẳn nhau về mục đích:

1. **Hợp đồng với bộ mô phỏng.** `ml/src/schedule_sim.py` phải chép lại luật
   SM-2 và bảng ánh xạ mastery→ngày của backend, vì nó không import được qua
   biên (module backend kéo theo cả SQLAlchemy). Chép là sẽ trôi. Nên bộ mô
   phỏng ghi lại quỹ đạo của chính nó vào file kết quả, còn ở đây tính lại quỹ
   đạo ấy bằng hàm THẬT của backend rồi so từng bước. Sửa một bên là đỏ ngay.

2. **Lớp đọc file.** Thiếu file, file hỏng, và phân quyền.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.security import create_access_token
from app.schemas.auth import RegisterRequest
from app.services import scheduler_experiment_service as svc
from app.services.auth_service import register_user
from app.services.review_service import mastery_to_interval_days
from app.services.sm2_service import sm2_step

RESULT_FILE = (Path(__file__).resolve().parents[2]
               / "docs" / "experiments" / "scheduler_comparison.json")


def _user(db_session, email, role="learner"):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    if role != "learner":
        u.role = role
        db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _payload() -> dict:
    if not RESULT_FILE.exists():
        pytest.skip("Chưa chạy ml/src/schedule_sim.py")
    return json.loads(RESULT_FILE.read_text(encoding="utf-8"))


# --- 1. Hợp đồng với bộ mô phỏng ---------------------------------------------

def test_quy_dao_sm2_cua_bo_mo_phong_khop_ham_that_cua_backend():
    """Bộ mô phỏng chép luật SM-2; chép mà trôi thì số đo không còn nói về SM-2."""
    trajectory = _payload()["contract"]["sm2_trajectory"]
    interval, ease, reps = 1, 2.5, 0
    for quality, sim_interval, sim_ease, sim_reps in trajectory:
        interval, ease, reps = sm2_step(quality, interval, ease, reps)
        assert (interval, ease, reps) == (sim_interval, sim_ease, sim_reps), (
            f"Lệch ở mức {quality}: backend {(interval, ease, reps)} "
            f"vs mô phỏng {(sim_interval, sim_ease, sim_reps)}"
        )


def test_bang_anh_xa_mastery_sang_ngay_khop_uc66(monkeypatch):
    """Mô phỏng phải dùng ĐÚNG ngưỡng của `review_service`, kể cả θ_review."""
    monkeypatch.setattr("app.services.review_service.review_threshold", lambda: 0.6)
    for mastery, sim_days in _payload()["contract"]["dkt_intervals"]:
        assert mastery_to_interval_days(mastery) == sim_days, (
            f"mastery={mastery}: backend {mastery_to_interval_days(mastery)} "
            f"ngày vs mô phỏng {sim_days} ngày"
        )


# --- 2. Lớp đọc file ----------------------------------------------------------

def test_doc_duoc_file_ket_qua_that():
    data = svc.load(RESULT_FILE) if RESULT_FILE.exists() else pytest.skip("chưa chạy")
    names = {a.scheduler for a in data.arms}
    assert {"sm2", "dkt", "fixed"} <= names
    assert data.setup.learners > 0 and data.setup.horizon_days > 0
    # Chương trình học phải giống nhau ở mọi nhánh trong cùng một kịch bản — nếu
    # khác thì đang so hai chương trình học chứ không phải hai lịch ôn.
    for pool in data.setup.pools:
        for budget in data.setup.budgets:
            introduced = {a.introduced for a in data.arms
                          if a.budget == budget and a.pool == pool}
            assert len(introduced) == 1, (
                f"kho={pool} ngân sách={budget}: số từ đã học lệch {introduced}"
            )


def test_thieu_file_thi_404_kem_cach_chay(tmp_path):
    with pytest.raises(HTTPException) as exc:
        svc.load(tmp_path / "khong-co.json")
    assert exc.value.status_code == 404
    assert "schedule_sim" in exc.value.detail


def test_file_hong_thi_500_chu_khong_tra_so_bia(tmp_path):
    bad = tmp_path / "hong.json"
    bad.write_text('{"runs": {"dkt@20": {}}}', encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        svc.load(bad)
    assert exc.value.status_code == 500


def test_khoang_tin_cay_khong_chua_0_moi_goi_la_co_y_nghia():
    data = svc.load(RESULT_FILE) if RESULT_FILE.exists() else pytest.skip("chưa chạy")
    for gap in data.gaps:
        assert gap.ci_low <= gap.mean_diff <= gap.ci_high
        assert gap.significant == (gap.ci_low > 0 or gap.ci_high < 0)


# --- 3. Phân quyền ------------------------------------------------------------

def test_nguoi_hoc_thuong_khong_xem_duoc(client, db_session):
    _, headers = _user(db_session, "se.a@example.com")
    assert client.get("/api/v1/admin/scheduler-comparison", headers=headers).status_code == 403


def test_chua_dang_nhap_thi_401(client):
    assert client.get("/api/v1/admin/scheduler-comparison").status_code == 401


def test_admin_xem_duoc(client, db_session):
    _, headers = _user(db_session, "se.b@example.com", role="admin")
    resp = client.get("/api/v1/admin/scheduler-comparison", headers=headers)
    assert resp.status_code in (200, 404)     # 404 khi máy chưa chạy thí nghiệm
    if resp.status_code == 200:
        assert resp.json()["arms"]
