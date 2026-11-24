"""UC-13 — ảnh bìa bộ từ: tải lên, thay thế, gỡ bỏ."""

import io

from app.core.security import create_access_token
from app.schemas.auth import RegisterRequest
from app.services import word_set_service
from app.services.auth_service import register_user


def _make_user(db_session, email: str):
    user = register_user(
        db_session,
        RegisterRequest(
            email=email, password="Abcd1234", password_confirm="Abcd1234", display_name="U"
        ),
    )
    return user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


def _create_set(client, headers, **overrides) -> dict:
    resp = client.post("/api/v1/word-sets", json={"name": "Bo tu 1", **overrides}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _png(size: int = 64) -> tuple[str, io.BytesIO, str]:
    return ("bia.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"x" * size), "image/png")


def test_upload_cover_tra_ve_duong_dan_va_ghi_file(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers = _make_user(db_session, "cover1@example.com")
    ws = _create_set(client, headers)

    resp = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover", files={"file": _png()}, headers=headers
    )

    assert resp.status_code == 200, resp.text
    url = resp.json()["cover_image_url"]
    assert url.startswith("/uploads/word_set_covers/")
    assert url.endswith(".png")
    assert (tmp_path / "covers" / url.rsplit("/", 1)[1]).is_file()


def test_upload_cover_thay_anh_cu_thi_xoa_file_cu(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers = _make_user(db_session, "cover2@example.com")
    ws = _create_set(client, headers)

    first = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover", files={"file": _png()}, headers=headers
    ).json()["cover_image_url"]
    second = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover", files={"file": _png()}, headers=headers
    ).json()["cover_image_url"]

    assert first != second
    assert not (tmp_path / "covers" / first.rsplit("/", 1)[1]).exists()
    assert (tmp_path / "covers" / second.rsplit("/", 1)[1]).is_file()


def test_delete_cover_xoa_ca_ban_ghi_va_file(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers = _make_user(db_session, "cover3@example.com")
    ws = _create_set(client, headers)
    url = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover", files={"file": _png()}, headers=headers
    ).json()["cover_image_url"]

    resp = client.delete(f"/api/v1/word-sets/{ws['id']}/cover", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["cover_image_url"] is None
    assert not (tmp_path / "covers" / url.rsplit("/", 1)[1]).exists()


def test_upload_cover_tu_choi_dinh_dang_la(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers = _make_user(db_session, "cover4@example.com")
    ws = _create_set(client, headers)

    resp = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover",
        files={"file": ("bia.gif", io.BytesIO(b"GIF89a"), "image/gif")},
        headers=headers,
    )

    assert resp.status_code == 422
    assert "jpg/png/webp" in resp.json()["detail"]


def test_upload_cover_tu_choi_anh_qua_nang(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers = _make_user(db_session, "cover5@example.com")
    ws = _create_set(client, headers)

    resp = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover",
        files={"file": _png(size=word_set_service.MAX_COVER_SIZE_BYTES + 1)},
        headers=headers,
    )

    assert resp.status_code == 422
    assert "5MB" in resp.json()["detail"]


def test_khong_dat_duoc_bia_cho_bo_cua_nguoi_khac(client, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers_a = _make_user(db_session, "cover6a@example.com")
    _, headers_b = _make_user(db_session, "cover6b@example.com")
    ws = _create_set(client, headers_a)

    resp = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover", files={"file": _png()}, headers=headers_b
    )

    assert resp.status_code == 404


def test_sua_bo_tu_khong_lam_mat_anh_bia(client, db_session, tmp_path, monkeypatch):
    """PATCH không gửi `cover_image_url` thì bìa phải giữ nguyên.

    Form sửa bộ từ ở frontend chỉ gửi tên/mô tả/danh mục/độ khó; trước đây
    Pydantic điền None vào trường thiếu nên mỗi lần đổi tên là mất ảnh.
    """
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", tmp_path / "covers")
    _, headers = _make_user(db_session, "cover7@example.com")
    ws = _create_set(client, headers)
    url = client.post(
        f"/api/v1/word-sets/{ws['id']}/cover", files={"file": _png()}, headers=headers
    ).json()["cover_image_url"]

    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}", json={"name": "Ten moi"}, headers=headers
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Ten moi"
    assert resp.json()["cover_image_url"] == url


def test_gui_cover_image_url_rong_thi_van_xoa_duoc(client, db_session):
    """Client cố tình gửi `cover_image_url: null` thì vẫn phải gỡ được bìa."""
    _, headers = _make_user(db_session, "cover8@example.com")
    ws = _create_set(client, headers, cover_image_url="https://vidu.test/bia.png")

    resp = client.patch(
        f"/api/v1/word-sets/{ws['id']}",
        json={"name": "Bo tu 1", "cover_image_url": None},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["cover_image_url"] is None


def test_khong_xoa_file_ngoai_thu_muc_bia(tmp_path, monkeypatch):
    """`cover_image_url` là chuỗi client đặt tuỳ ý — không được dùng để unlink bừa."""
    covers = tmp_path / "covers"
    covers.mkdir()
    monkeypatch.setattr(word_set_service, "COVER_UPLOAD_DIR", covers)
    nan_nhan = tmp_path / "bi_mat.txt"
    nan_nhan.write_text("khong duoc xoa")

    word_set_service._remove_cover_file("/uploads/word_set_covers/../../bi_mat.txt")
    word_set_service._remove_cover_file("https://ngoai.test/anh.png")
    word_set_service._remove_cover_file("/uploads/avatars/abc.png")

    assert nan_nhan.is_file()
