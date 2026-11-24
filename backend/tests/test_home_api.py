"""API trang chủ học viên — tổng hợp UC-40/41/46/47/48, UC-65/69, UC-36/66."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.interaction import Interaction
from app.models.item import Item
from app.models.knowledge_state import KnowledgeState
from app.models.review_schedule import ReviewSchedule
from app.models.user_progress import UserProgress
from app.models.user_settings import UserSettings
from app.models.word_set import WordSet
from app.schemas.auth import RegisterRequest
from app.services import config_service, dkt_client, home_service
from app.services.auth_service import register_user

NOW = datetime.now(timezone.utc)


def _user(db_session, email):
    u = register_user(
        db_session,
        RegisterRequest(email=email, password="Abcd1234", password_confirm="Abcd1234",
                        display_name=email[:4]),
    )
    return u, {"Authorization": f"Bearer {create_access_token(u.id, u.role)}"}


def _word_set(db_session, owner_id, name, words, *, difficulty="beginner", category="Gen"):
    ws = WordSet(owner_id=owner_id, name=name, difficulty=difficulty, category=category)
    db_session.add(ws)
    db_session.flush()
    items = [Item(word_set_id=ws.id, word=w, meaning=f"nghĩa {w}") for w in words]
    db_session.add_all(items)
    db_session.commit()
    return ws, items


def _set_mastery(db_session, user, item, value):
    db_session.add(KnowledgeState(
        user_id=user.id, item_id=item.id, mastery=value,
        last_updated=NOW,
    ))
    db_session.commit()


def _answer(db_session, user, item, *, when=None):
    db_session.add(Interaction(
        user_id=user.id, item_id=item.id, is_correct=True,
        answered_at=when or NOW,
    ))
    db_session.commit()


def _schedule(db_session, user, item, when):
    db_session.add(ReviewSchedule(user_id=user.id, item_id=item.id, next_review_at=when))
    db_session.commit()


# --- /stats/overview ----------------------------------------------------------

def test_stats_overview_main_flow(client, db_session):
    """Luồng chính: 5 từ, 2 đã thuộc, 1 đang học, 2 chưa học."""
    user, headers = _user(db_session, "hm.a@example.com")
    _, items = _word_set(db_session, user.id, "Bộ A", ["a1", "a2", "a3", "a4", "a5"])

    _set_mastery(db_session, user, items[0], 0.95)
    _set_mastery(db_session, user, items[1], 0.91)
    _set_mastery(db_session, user, items[2], 0.30)
    for item in items[:2]:
        for _ in range(3):
            _answer(db_session, user, item)

    body = client.get("/api/v1/stats/overview", headers=headers).json()
    assert body["total_items"] == 5
    assert body["mastered"] == 2
    assert body["in_progress"] == 1
    assert body["not_started"] == 2
    assert body["mastery_percent"] == 40.0


def test_stats_overview_without_any_interaction(client, db_session):
    """Người học chưa học gì: đã thuộc = 0, chưa học = tổng."""
    user, headers = _user(db_session, "hm.b@example.com")
    _word_set(db_session, user.id, "Bộ B", ["b1", "b2", "b3"])

    body = client.get("/api/v1/stats/overview", headers=headers).json()
    assert body == {
        "total_items": 3, "mastered": 0, "in_progress": 0,
        "not_started": 3, "mastery_percent": 0.0,
    }


def test_stats_overview_empty_library(client, db_session):
    _, headers = _user(db_session, "hm.c@example.com")
    body = client.get("/api/v1/stats/overview", headers=headers).json()
    assert body["total_items"] == 0 and body["mastery_percent"] == 0.0


def test_stats_overview_uses_config_threshold(client, db_session):
    """BR-01 lấy ngưỡng từ system_configs, không hardcode."""
    user, headers = _user(db_session, "hm.d@example.com")
    _, items = _word_set(db_session, user.id, "Bộ D", ["d1", "d2"])
    _set_mastery(db_session, user, items[0], 0.87)
    for _ in range(3):
        _answer(db_session, user, items[0])

    assert client.get("/api/v1/stats/overview", headers=headers).json()["mastered"] == 0

    config_service.set_values(db_session, {"mastered_threshold": 0.85})
    assert client.get("/api/v1/stats/overview", headers=headers).json()["mastered"] == 1


def test_stats_ignores_other_users_and_deleted_sets(client, db_session):
    user, headers = _user(db_session, "hm.e1@example.com")
    other, _ = _user(db_session, "hm.e2@example.com")
    _word_set(db_session, other.id, "Bộ của người khác", ["x1", "x2"])
    ws, _ = _word_set(db_session, user.id, "Bộ đã xóa", ["y1"])
    ws.deleted_at = NOW
    db_session.commit()

    assert client.get("/api/v1/stats/overview", headers=headers).json()["total_items"] == 0


# --- /gamification/summary ----------------------------------------------------

def test_gamification_summary(client, db_session):
    user, headers = _user(db_session, "hm.f@example.com")
    progress = db_session.execute(
        select(UserProgress).where(UserProgress.user_id == user.id)
    ).scalar_one()
    progress.xp = 250
    progress.streak_count = 4
    db_session.commit()

    body = client.get("/api/v1/gamification/summary", headers=headers).json()
    assert body["xp"] == 250 and body["level"] == 3 and body["streak_count"] == 4
    assert body["level_title"] and body["xp_into_level"] == 50


def test_daily_goal_counts_distinct_items_today(client, db_session):
    """Mục tiêu ngày đếm TỪ riêng biệt: trả lời cùng một từ 3 lần vẫn là 1."""
    user, headers = _user(db_session, "hm.g@example.com")
    _, items = _word_set(db_session, user.id, "Bộ G", ["g1", "g2", "g3"])

    for _ in range(3):
        _answer(db_session, user, items[0])
    _answer(db_session, user, items[1])
    _answer(db_session, user, items[2], when=NOW - timedelta(days=2))   # hôm khác

    goal = client.get("/api/v1/gamification/summary", headers=headers).json()["daily_goal"]
    assert goal["done"] == 2
    assert goal["target"] == config_service.get_int("default_daily_item_goal")
    assert goal["reached"] is False


def test_daily_goal_uses_user_setting(client, db_session):
    user, headers = _user(db_session, "hm.h@example.com")
    _, items = _word_set(db_session, user.id, "Bộ H", ["h1", "h2"])
    _answer(db_session, user, items[0])
    _answer(db_session, user, items[1])

    row = db_session.execute(
        select(UserSettings).where(UserSettings.user_id == user.id)
    ).scalar_one()
    row.daily_item_goal = 2
    db_session.commit()

    goal = client.get("/api/v1/gamification/summary", headers=headers).json()["daily_goal"]
    assert goal == {"done": 2, "target": 2, "reached": True}


# --- /progress/courses --------------------------------------------------------

def test_course_progress(client, db_session):
    user, headers = _user(db_session, "hm.i@example.com")
    _, items_a = _word_set(db_session, user.id, "Bộ I1", ["i1", "i2", "i3", "i4"])
    _word_set(db_session, user.id, "Bộ I2", ["j1"])
    _set_mastery(db_session, user, items_a[0], 0.95)
    for _ in range(3):
        _answer(db_session, user, items_a[0])

    body = client.get("/api/v1/progress/courses", headers=headers).json()
    by_name = {c["name"]: c for c in body}
    assert by_name["Bộ I1"]["percent"] == 25.0
    assert by_name["Bộ I1"]["total_items"] == 4 and by_name["Bộ I1"]["mastered_items"] == 1
    assert by_name["Bộ I2"]["percent"] == 0.0
    assert by_name["Bộ I1"]["learning_items"] == 0 and by_name["Bộ I2"]["learning_items"] == 0


def test_course_progress_counts_learning_words(client, db_session):
    """Từ đã học nhưng chưa thuộc được tính riêng — không lẫn vào 'đã thuộc'."""
    user, headers = _user(db_session, "hm.learn@example.com")
    _, items = _word_set(db_session, user.id, "Bộ L", ["l1", "l2", "l3", "l4"])
    _set_mastery(db_session, user, items[0], 0.95)
    for _ in range(3):
        _answer(db_session, user, items[0])
    _set_mastery(db_session, user, items[1], 0.5)       # đang học
    _set_mastery(db_session, user, items[2], 0.95)      # mastery cao nhưng chưa đủ lượt đúng

    row = next(c for c in client.get("/api/v1/progress/courses", headers=headers).json()
               if c["name"] == "Bộ L")
    assert row["mastered_items"] == 1
    assert row["learning_items"] == 2
    assert row["total_items"] == 4


# --- /recommendations/today ---------------------------------------------------

def test_recommendations_only_in_band(client, db_session, monkeypatch):
    """BR-03: chỉ trả từ có P(đúng) trong [band_low, band_high]."""
    user, headers = _user(db_session, "hm.j@example.com")
    _, items = _word_set(db_session, user.id, "Bộ J", ["low", "mid", "high"])

    scores = {"low": 0.2, "mid": 0.7, "high": 0.95}
    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda history, targets, **kwargs: {t: scores[t] for t in targets})

    body = client.get("/api/v1/recommendations/today", headers=headers).json()
    assert body["count"] == 1
    assert [w["word"] for w in body["items"]] == ["mid"]
    assert body["items"][0]["predicted_p"] == 0.7
    assert body["band_low"] == 0.6 and body["band_high"] == 0.8
    assert body["degraded"] is False


def test_recommendations_dem_tu_moi_hoc_hom_nay(client, db_session):
    """Bước "Học từ mới" xong khi hôm nay có từ được học LẦN ĐẦU; ôn lại từ cũ
    (lần đầu từ hôm qua) không tính."""
    user, headers = _user(db_session, "hm.new@example.com")
    _, items = _word_set(db_session, user.id, "Bộ New", ["a", "b", "c"])
    url = "/api/v1/recommendations/today"
    assert client.get(url, headers=headers).json()["new_learned_today"] == 0

    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    _answer(db_session, user, items[0], when=yesterday)
    _answer(db_session, user, items[0])                  # ôn lại từ cũ hôm nay
    assert client.get(url, headers=headers).json()["new_learned_today"] == 0

    _answer(db_session, user, items[1])
    _answer(db_session, user, items[2])
    _answer(db_session, user, items[2])                  # trả lời 2 lần vẫn là 1 từ
    assert client.get(url, headers=headers).json()["new_learned_today"] == 2


def test_recommendations_bo_qua_tu_da_hoc(client, db_session, monkeypatch):
    """BR-03 gợi ý từ MỚI: từ đã có Interaction (học hôm trước) thuộc luồng ôn,
    không được hiện lại ở "Học từ mới" dù P(đúng) đang trong vùng vừa sức."""
    user, headers = _user(db_session, "hm.seen@example.com")
    _, items = _word_set(db_session, user.id, "Bộ Seen", ["old", "fresh"])
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kw: {x: 0.7 for x in t})
    _answer(db_session, user, items[0], when=datetime.now(timezone.utc) - timedelta(days=1))

    body = client.get("/api/v1/recommendations/today", headers=headers).json()
    assert [w["word"] for w in body["items"]] == ["fresh"]


def test_today_items_tham_do_khong_lay_tu_da_hoc(client, db_session, monkeypatch):
    """Từ thăm dò (pilot) cũng chỉ bốc trong từ chưa học."""
    config_service.set_values(db_session, {"explore_rate": 0.5})
    user, _ = _user(db_session, "hm.seen2@example.com")
    _, items = _word_set(db_session, user.id, "Bộ Seen2", [f"s{i}" for i in range(6)])
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kw: {x: 0.7 for x in t})
    learned = items[2:]
    for it in learned:
        _answer(db_session, user, it, when=datetime.now(timezone.utc) - timedelta(days=1))

    rows = home_service.get_today_study_items(db_session, user, [items[0].id])
    assert {r.id for r in rows} <= {items[0].id, items[1].id}


def test_recommendations_follow_config_band(client, db_session, monkeypatch):
    user, headers = _user(db_session, "hm.k@example.com")
    _word_set(db_session, user.id, "Bộ K", ["w1"])
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kwargs: {x: 0.5 for x in t})

    assert client.get("/api/v1/recommendations/today", headers=headers).json()["count"] == 0

    config_service.set_values(db_session, {"band_low": 0.4, "band_high": 0.6})
    body = client.get("/api/v1/recommendations/today", headers=headers).json()
    assert body["count"] == 1 and body["band_low"] == 0.4


def test_recommendations_degrade_when_ml_service_down(client, db_session, monkeypatch):
    """Service DKT tắt -> dkt_client trả None -> dùng cold-start prior, KHÔNG lỗi."""
    user, headers = _user(db_session, "hm.l@example.com")
    # prior của 'beginner' là 0.6 -> nằm trong vùng vừa sức mặc định
    _word_set(db_session, user.id, "Bộ L", ["m1", "m2"], difficulty="beginner")

    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda history, targets, **kwargs: {t: None for t in targets})

    response = client.get("/api/v1/recommendations/today", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is True
    assert body["count"] == 2
    assert all(w["predicted_p"] == 0.6 for w in body["items"])


def test_recommendations_empty_library(client, db_session):
    _, headers = _user(db_session, "hm.m@example.com")
    body = client.get("/api/v1/recommendations/today", headers=headers).json()
    assert body["count"] == 0 and body["items"] == []



# --- /recommendations/today/items (nút "Học N từ mới") -----------------------

def test_today_items_dung_cac_tu_da_goi_y(client, db_session, monkeypatch):
    """Trang chủ gợi ý N từ (có thể thuộc nhiều bộ) -> phiên học trả ĐÚNG N từ đó,
    giữ thứ tự, bỏ id không thuộc người học. Trước đây vào học 20 từ của 1 bộ."""
    config_service.set_values(db_session, {"explore_rate": 0})
    user, headers = _user(db_session, "hm.ti1@example.com")
    _, set_a = _word_set(db_session, user.id, "Bộ TA", [f"a{i}" for i in range(15)])
    _, set_b = _word_set(db_session, user.id, "Bộ TB", [f"b{i}" for i in range(15)])
    other, _ = _user(db_session, "hm.ti1x@example.com")
    _, foreign = _word_set(db_session, other.id, "Bộ X", ["x"])
    monkeypatch.setattr(dkt_client, "predict_mastery",
                        lambda h, t, **kw: {x: (0.7 if x in {"a1", "a2", "b3"} else 0.3) for x in t})

    today = client.get("/api/v1/recommendations/today", headers=headers).json()
    ids = [w["item_id"] for w in today["items"]]
    assert today["count"] == 3 and len({w["word_set_id"] for w in today["items"]}) == 2

    query = ",".join(str(i) for i in ids + [foreign[0].id])
    body = client.get(f"/api/v1/recommendations/today/items?ids={query}", headers=headers).json()
    assert [r["id"] for r in body] == ids                      # đúng 3 từ, đúng thứ tự
    assert all(r["in_band"] and r["selection"] == "band" for r in body)


def test_today_items_tham_do_giu_nguyen_so_tu(client, db_session, monkeypatch):
    """Pilot: vẫn trộn từ thăm dò ngẫu nhiên, nhưng bằng phép THAY nên số từ không đổi."""
    config_service.set_values(db_session, {"explore_rate": 0.15})
    user, headers = _user(db_session, "hm.ti2@example.com")
    _, items = _word_set(db_session, user.id, "Bộ TC", [f"c{i}" for i in range(20)])
    monkeypatch.setattr(dkt_client, "predict_mastery", lambda h, t, **kw: {x: 0.7 for x in t})

    picked = items[:6]
    rows = home_service.get_today_study_items(db_session, user, [it.id for it in picked])
    assert len(rows) == 6
    assert sum(r.selection == "explore" for r in rows) == 1
    picked_ids = {it.id for it in picked}
    for r in rows:
        assert (r.id in picked_ids) == (r.selection == "band")


def test_today_items_validate_ids(client, db_session):
    _, headers = _user(db_session, "hm.ti3@example.com")
    url = "/api/v1/recommendations/today/items"
    assert client.get(url, headers=headers).status_code == 422
    assert client.get(f"{url}?ids=1;2", headers=headers).status_code == 422
    assert client.get(f"{url}?ids=999999", headers=headers).json() == []


# --- /review-schedules --------------------------------------------------------

def test_review_days_in_month(client, db_session):
    """Chỉ trả các ngày có từ tới hạn TRONG tháng được hỏi."""
    user, headers = _user(db_session, "hm.n@example.com")
    _, items = _word_set(db_session, user.id, "Bộ N", ["n1", "n2", "n3", "n4"])

    _schedule(db_session, user, items[0], datetime(2026, 5, 4, 8, tzinfo=timezone.utc))
    _schedule(db_session, user, items[1], datetime(2026, 5, 4, 20, tzinfo=timezone.utc))
    _schedule(db_session, user, items[2], datetime(2026, 5, 19, 9, tzinfo=timezone.utc))
    _schedule(db_session, user, items[3], datetime(2026, 6, 2, 9, tzinfo=timezone.utc))  # tháng khác

    body = client.get("/api/v1/review-schedules?month=2026-05", headers=headers).json()
    assert body == [
        {"date": "2026-05-04", "due_count": 1},
        {"date": "2026-05-05", "due_count": 1},  # 20:00 UTC is next day in Vietnam
        {"date": "2026-05-19", "due_count": 1},
    ]


def test_review_days_empty_month(client, db_session):
    user, headers = _user(db_session, "hm.o@example.com")
    _, items = _word_set(db_session, user.id, "Bộ O", ["o1"])
    _schedule(db_session, user, items[0], datetime(2026, 5, 4, tzinfo=timezone.utc))

    assert client.get("/api/v1/review-schedules?month=2026-07", headers=headers).json() == []


def test_review_days_bad_month_format(client, db_session):
    _, headers = _user(db_session, "hm.p@example.com")
    assert client.get("/api/v1/review-schedules?month=2026-5", headers=headers).status_code == 422
    assert client.get("/api/v1/review-schedules?month=abcd-ef", headers=headers).status_code == 422
    assert client.get("/api/v1/review-schedules?month=2026-13", headers=headers).status_code == 422


# --- /review-schedules/upcoming -----------------------------------------------

def test_upcoming_grouped_by_word_set(client, db_session):
    user, headers = _user(db_session, "hm.q@example.com")
    ws_a, items_a = _word_set(db_session, user.id, "Sắp tới", ["q1", "q2"], category="Giao tiếp")
    _, items_b = _word_set(db_session, user.id, "Xa hơn", ["q3"])

    _schedule(db_session, user, items_a[0], NOW + timedelta(hours=2))
    _schedule(db_session, user, items_a[1], NOW + timedelta(hours=5))
    _schedule(db_session, user, items_b[0], NOW + timedelta(days=3))

    body = client.get("/api/v1/review-schedules/upcoming?limit=3", headers=headers).json()
    assert [x["title"] for x in body] == ["Sắp tới", "Xa hơn"]     # tăng dần theo thời gian
    assert body[0]["id"] == ws_a.id
    assert body[0]["due_count"] == 2 and body[0]["group"] == "Giao tiếp"


def test_upcoming_respects_limit(client, db_session):
    user, headers = _user(db_session, "hm.r@example.com")
    for i in range(4):
        _, items = _word_set(db_session, user.id, f"Bộ R{i}", [f"r{i}"])
        _schedule(db_session, user, items[0], NOW + timedelta(days=i + 1))

    assert len(client.get("/api/v1/review-schedules/upcoming?limit=2", headers=headers).json()) == 2


# --- Auth ---------------------------------------------------------------------

def test_all_home_endpoints_require_jwt(client):
    for path in (
        "/api/v1/gamification/summary",
        "/api/v1/stats/overview",
        "/api/v1/progress/courses",
        "/api/v1/recommendations/today",
        "/api/v1/review-schedules?month=2026-05",
        "/api/v1/review-schedules/upcoming",
    ):
        assert client.get(path).status_code == 401, path
