from fastapi import APIRouter

from app.api.v1.endpoints import (
    achievements,
    admin,
    auth,
    challenges,
    community,
    conversations,
    dashboard,
    dictionary,
    discover,
    friends,
    games,
    home,
    item_flags,
    jobs,
    notifications,
    placement,
    progress,
    pronunciation,
    roadmap,
    reviews,
    sessions,
    shadowing,
    speaking,
    users,
    validation,
    word_sets,
    writing,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(word_sets.router, prefix="/word-sets", tags=["word-sets"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(achievements.router, prefix="/achievements", tags=["achievements"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(discover.router, prefix="/discover", tags=["discover"])
api_router.include_router(dictionary.router, prefix="/dictionary", tags=["dictionary"])
api_router.include_router(games.router, prefix="/games", tags=["games"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(community.router, prefix="/community", tags=["community"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(jobs.router, prefix="/admin/jobs", tags=["admin"])
api_router.include_router(shadowing.admin_router, prefix="/admin/shadowing", tags=["admin"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(home.router)   # trang chủ học viên (đường dẫn tự khai trong module)
api_router.include_router(placement.router, prefix="/placement", tags=["placement"])
api_router.include_router(roadmap.router, prefix="/me", tags=["roadmap"])
api_router.include_router(item_flags.router, prefix="/me", tags=["item-flags"])
api_router.include_router(challenges.router, tags=["challenges"])
api_router.include_router(friends.router, prefix="/community", tags=["community"])
api_router.include_router(pronunciation.router, prefix="/pronunciation", tags=["pronunciation"])
api_router.include_router(writing.router, tags=["writing"])
# Module luyen noi — doc lap voi DKT (xem app/speaking/__init__.py)
# Pilot kiểm chứng DKT — bài kiểm tra cuối
api_router.include_router(validation.router, prefix="/validation", tags=["validation"])
api_router.include_router(speaking.router, prefix="/speaking", tags=["speaking"])
# UC-97 — shadowing theo phụ đề video, cũng thuộc module luyện nói (độc lập DKT)
api_router.include_router(shadowing.router, prefix="/shadowing", tags=["shadowing"])
