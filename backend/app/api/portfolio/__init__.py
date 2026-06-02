from fastapi import APIRouter

from app.api.portfolio_legacy import router as legacy_router
from .routes import router as product_router

router = APIRouter()
router.include_router(legacy_router)
router.include_router(product_router)
