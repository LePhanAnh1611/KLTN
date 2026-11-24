"""UC-97 — API shadowing: kho video, video riêng, chấm câu, admin duyệt.

Không gọi YouTube thật và không chạy Whisper: lấy phụ đề/tiêu đề và ASR đều
được thay bằng đồ giả. Câu mẫu do nhóm tự viết.
"""
import io

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.audit_log import AuditLog
from app.models.interaction import Interaction
from app.models.knowledge_state import KnowledgeState
from app.models.shadowing import ShadowingAttempt
from app.schemas.auth import RegisterRequest
from app.services.auth_service import register_user
from app.services.shadowing import CaptionError, Snippet, youtube
from app.services.shadowing.youtube import CaptionTrack, VideoMeta

from tests.speaking.conftest import FakeAsr, make_transcript

VID_A = "AAAAAAAAAA1"
VID_B = "BBBBBBBBBB2"
LINES = [
    ("Good morning, I am calling about the meeting.", 0.0, 3.0),
    ("Can we move it to Friday afternoon?", 3.2, 2.8),
    ("That works well for our whole team.", 6.2, 2.8),
]


def _user(db_session, email, role="learner"):
    u = register_user(db_session, RegisterRequest(
        email=email, password="Abcd1234", password_confirm="Abcd1234", display_name=email[:4]))
    if role != "learner":
        u.role = role
        db_session.commit()
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


@pytest.fixture
def fake_youtube(monkeypatch):
    calls = {"captions": 0}

    def meta(video_id, timeout=8.0):
        return VideoMeta(title=f"Bài {video_id}", channel="Kênh thử")

    def captions(video_id):
        calls["captions"] += 1
        return CaptionTrack(kind="manual", language="en",
                            snippets=[Snippet(t, s, d) for t, s, d in LINES])

    monkeypatch.setattr(youtube, "fetch_meta", meta)
    monkeypatch.setattr(youtube, "fetch_captions", captions)
    return calls


@pytest.fixture
def fake_asr(monkeypatch):
    from app.speaking import pipeline

    def install(words, duration=2.4):
        step = duration / max(1, len(words))
        spec = [(w, i * step, (i + 1) * step, 0.95) for i, w in enumerate(words)]
        monkeypatch.setattr(pipeline, "_default_asr",
                            lambda: FakeAsr(make_transcript(spec, duration=duration)))
    return install


def _audio():
    return {"audio": ("a.webm", io.BytesIO(b"fake-audio"), "audio/webm")}


def _admin_create(client, headers, vid=VID_A, **form):
    data = {"url": f"https://youtu.be/{vid}", **form}
    return client.post("/api/v1/admin/shadowing/videos", headers=headers, data=data)


def _published(client, headers, vid=VID_A):
    r = _admin_create(client, headers, vid, topic="Công sở & Kinh doanh",
                      license="public-domain", attribution="VOA Learning English")
    assert r.status_code == 201, r.text
    vid_id = r.json()["id"]
    r = client.put(f"/api/v1/admin/shadowing/videos/{vid_id}/status", headers=headers,
                   json={"status": "published"})
    assert r.status_code == 200, r.text
    return vid_id


# ------------------------------------------------------------ Admin

def test_admin_creates_draft_with_segments_and_profile(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad1@example.com", role="admin")
    r = _admin_create(client, admin, topic="Công sở & Kinh doanh")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["title"] == f"Bài {VID_A}"
    assert body["caption_kind"] == "manual"
    assert [s["text"] for s in body["segments"]] == [t for t, _, _ in LINES]
    assert body["vocab_profile"]["total_words"] > 0
    assert body["words_per_minute"] > 0
    log = db_session.scalar(select(AuditLog).where(AuditLog.action == "shadowing.create"))
    assert log is not None and log.target_id == body["id"]


def test_admin_duplicate_video_conflicts(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad2@example.com", role="admin")
    assert _admin_create(client, admin).status_code == 201
    assert _admin_create(client, admin).status_code == 409


def test_publish_requires_topic_license_and_attribution(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad3@example.com", role="admin")
    vid_id = _admin_create(client, admin).json()["id"]
    url = f"/api/v1/admin/shadowing/videos/{vid_id}"

    r = client.put(f"{url}/status", headers=admin, json={"status": "published"})
    assert r.status_code == 422 and "chủ đề" in r.json()["detail"]

    client.patch(url, headers=admin, json={"topic": "Du lịch & Sân bay", "license": "cc-by"})
    r = client.put(f"{url}/status", headers=admin, json={"status": "published"})
    assert r.status_code == 422 and "ghi công" in r.json()["detail"]

    client.patch(url, headers=admin, json={"attribution": "Tác giả X, CC BY 4.0"})
    r = client.put(f"{url}/status", headers=admin, json={"status": "published"})
    assert r.status_code == 200 and r.json()["status"] == "published"


def test_invalid_topic_rejected(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad4@example.com", role="admin")
    assert _admin_create(client, admin, topic="Chủ đề bịa").status_code == 422


def test_admin_edits_segments_and_profile_recomputed(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad5@example.com", role="admin")
    vid_id = _admin_create(client, admin).json()["id"]
    r = client.patch(f"/api/v1/admin/shadowing/videos/{vid_id}", headers=admin, json={
        "segments": [{"start": 0, "end": 6, "text": "Good morning. Can we move the meeting?"}],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["segment_count"] == 1
    assert body["vocab_profile"]["total_words"] == 7

    r = client.patch(f"/api/v1/admin/shadowing/videos/{vid_id}", headers=admin, json={
        "segments": [{"start": 5, "end": 2, "text": "bad"}],
    })
    assert r.status_code == 422


def test_learner_cannot_use_admin_endpoints(client, db_session, fake_youtube):
    _, learner = _user(db_session, "sh.le0@example.com")
    assert _admin_create(client, learner).status_code == 403
    assert client.get("/api/v1/admin/shadowing/videos", headers=learner).status_code == 403


def test_blocked_youtube_returns_503_and_upload_fallback_works(client, db_session, monkeypatch):
    _, admin = _user(db_session, "sh.ad6@example.com", role="admin")

    def blocked(*args, **kwargs):
        raise CaptionError("YouTube đang chặn", blocked=True)

    monkeypatch.setattr(youtube, "fetch_meta", blocked)
    monkeypatch.setattr(youtube, "fetch_captions", blocked)
    assert _admin_create(client, admin).status_code == 503

    srt = "1\n00:00:00,000 --> 00:00:03,000\nWe need a new plan for the launch.\n"
    r = client.post("/api/v1/admin/shadowing/videos", headers=admin,
                    data={"url": f"https://youtu.be/{VID_A}"},
                    files={"captions": ("sub.srt", io.BytesIO(srt.encode()), "text/plain")})
    assert r.status_code == 201, r.text
    assert r.json()["caption_kind"] == "upload"
    assert r.json()["segments"][0]["text"] == "We need a new plan for the launch."


def test_video_without_english_captions_is_422(client, db_session, monkeypatch):
    _, admin = _user(db_session, "sh.ad7@example.com", role="admin")
    monkeypatch.setattr(youtube, "fetch_meta", lambda v, timeout=8.0: VideoMeta("x", None))

    def none(video_id):
        raise CaptionError("Video không có phụ đề tiếng Anh.")

    monkeypatch.setattr(youtube, "fetch_captions", none)
    r = _admin_create(client, admin)
    assert r.status_code == 422 and "phụ đề" in r.json()["detail"]


def test_wrong_caption_file_extension_rejected(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad8@example.com", role="admin")
    r = client.post("/api/v1/admin/shadowing/videos", headers=admin,
                    data={"url": f"https://youtu.be/{VID_A}"},
                    files={"captions": ("sub.txt", io.BytesIO(b"x"), "text/plain")})
    assert r.status_code == 422


# ------------------------------------------------------------ Người học

def test_learner_sees_only_published_catalog_and_own_videos(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad9@example.com", role="admin")
    _, alice = _user(db_session, "sh.le1@example.com")
    _, bob = _user(db_session, "sh.le2@example.com")

    published = _published(client, admin, VID_A)
    _admin_create(client, admin, "CCCCCCCCCC3")                 # bản nháp — không ai thấy
    r = client.post("/api/v1/shadowing/videos", headers=bob,
                    data={"url": f"https://www.youtube.com/watch?v={VID_B}"})
    assert r.status_code == 201 and r.json()["source"] == "user"
    bob_video = r.json()["id"]

    alice_ids = {v["id"] for v in client.get("/api/v1/shadowing/videos", headers=alice).json()}
    bob_ids = {v["id"] for v in client.get("/api/v1/shadowing/videos", headers=bob).json()}
    assert alice_ids == {published}
    assert bob_ids == {published, bob_video}
    assert client.get(f"/api/v1/shadowing/videos/{bob_video}", headers=alice).status_code == 404

    filtered = client.get("/api/v1/shadowing/videos", headers=alice,
                          params={"topic": "Du lịch & Sân bay"}).json()
    assert filtered == []


def test_learner_link_to_catalog_video_returns_catalog_copy(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad10@example.com", role="admin")
    _, alice = _user(db_session, "sh.le3@example.com")
    published = _published(client, admin, VID_A)
    before = fake_youtube["captions"]

    r = client.post("/api/v1/shadowing/videos", headers=alice,
                    data={"url": f"https://youtu.be/{VID_A}"})
    assert r.status_code == 201
    assert r.json()["id"] == published and r.json()["source"] == "catalog"
    assert fake_youtube["captions"] == before      # không gọi YouTube lần nữa


def test_attempt_scores_saves_and_tracks_progress(client, db_session, fake_youtube, fake_asr):
    _, admin = _user(db_session, "sh.ad11@example.com", role="admin")
    user, alice = _user(db_session, "sh.le4@example.com")
    vid_id = _published(client, admin)

    fake_asr("can we move it to friday afternoon".split(), duration=2.8)
    r = client.post(f"/api/v1/shadowing/videos/{vid_id}/segments/1/attempts",
                    headers=alice, files=_audio())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["expected_text"] == LINES[1][0]
    assert body["accuracy"] == 1.0
    assert body["passed"] is True
    assert body["original_wpm"] > 0 and body["speed_ratio"] is not None
    assert body["speed_feedback"]

    fake_asr("that works".split(), duration=1.0)
    r = client.post(f"/api/v1/shadowing/videos/{vid_id}/segments/2/attempts",
                    headers=alice, files=_audio())
    assert r.status_code == 200 and r.json()["passed"] is False

    detail = client.get(f"/api/v1/shadowing/videos/{vid_id}", headers=alice).json()
    assert detail["passed_count"] == 1
    assert [p["passed"] for p in detail["progress"]] == [False, True, False]
    assert detail["progress"][2]["attempts"] == 1
    cards = client.get("/api/v1/shadowing/videos", headers=alice).json()
    assert cards[0]["passed_count"] == 1

    saved = db_session.scalars(select(ShadowingAttempt).where(
        ShadowingAttempt.user_id == user.id)).all()
    assert len(saved) == 2
    assert saved[0].target_text == LINES[1][0]


def test_khong_sinh_interaction_nao(client, db_session, fake_youtube, fake_asr):
    """Ranh giới CLAUDE.md §7: shadowing không chạm tới dữ liệu đầu vào của DKT."""
    _, admin = _user(db_session, "sh.ad12@example.com", role="admin")
    _, alice = _user(db_session, "sh.le5@example.com")
    vid_id = _published(client, admin)
    before_i = db_session.scalar(select(func.count()).select_from(Interaction))
    before_k = db_session.scalar(select(func.count()).select_from(KnowledgeState))

    fake_asr("good morning i am calling about the meeting".split())
    client.post(f"/api/v1/shadowing/videos/{vid_id}/segments/0/attempts",
                headers=alice, files=_audio())

    assert db_session.scalar(select(func.count()).select_from(Interaction)) == before_i
    assert db_session.scalar(select(func.count()).select_from(KnowledgeState)) == before_k


def test_unknown_segment_is_404(client, db_session, fake_youtube, fake_asr):
    _, admin = _user(db_session, "sh.ad13@example.com", role="admin")
    _, alice = _user(db_session, "sh.le6@example.com")
    vid_id = _published(client, admin)
    fake_asr(["hello"])
    r = client.post(f"/api/v1/shadowing/videos/{vid_id}/segments/99/attempts",
                    headers=alice, files=_audio())
    assert r.status_code == 404


def test_asr_down_returns_503(client, db_session, fake_youtube, monkeypatch):
    from app.speaking import pipeline
    from app.speaking.asr.base import AsrUnavailable

    _, admin = _user(db_session, "sh.ad14@example.com", role="admin")
    _, alice = _user(db_session, "sh.le7@example.com")
    vid_id = _published(client, admin)

    class Broken:
        name = "broken"

        def transcribe(self, *a, **k):
            raise AsrUnavailable("chưa cài faster-whisper")

    monkeypatch.setattr(pipeline, "_default_asr", lambda: Broken())
    r = client.post(f"/api/v1/shadowing/videos/{vid_id}/segments/0/attempts",
                    headers=alice, files=_audio())
    assert r.status_code == 503
    assert db_session.scalar(select(func.count()).select_from(ShadowingAttempt)) == 0


def test_learner_deletes_own_video_but_not_catalog(client, db_session, fake_youtube):
    _, admin = _user(db_session, "sh.ad15@example.com", role="admin")
    _, alice = _user(db_session, "sh.le8@example.com")
    catalog = _published(client, admin, VID_A)
    own = client.post("/api/v1/shadowing/videos", headers=alice,
                      data={"url": f"https://youtu.be/{VID_B}"}).json()["id"]

    assert client.delete(f"/api/v1/shadowing/videos/{catalog}", headers=alice).status_code == 403
    assert client.delete(f"/api/v1/shadowing/videos/{own}", headers=alice).status_code == 204
    ids = {v["id"] for v in client.get("/api/v1/shadowing/videos", headers=alice).json()}
    assert ids == {catalog}


def test_topics_endpoint(client, db_session):
    _, alice = _user(db_session, "sh.le9@example.com")
    body = client.get("/api/v1/shadowing/topics", headers=alice).json()
    assert len(body["topics"]) == 8 and "Công nghệ thông tin" in body["topics"]
    assert body["levels"] == ["A1", "A2", "B1", "B2", "C1", "C2"]
