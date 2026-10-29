from app.routers.auth import router as auth_router
from app.routers.campaigns import router as campaigns_router
from app.routers.donations import router as donations_router
from app.routers.updates import router as updates_router
from app.routers.payouts import router as payouts_router
from app.routers.ai import router as ai_router
from app.routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "campaigns_router",
    "donations_router",
    "updates_router",
    "payouts_router",
    "ai_router",
    "admin_router"
]
