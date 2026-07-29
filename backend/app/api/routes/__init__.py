from fastapi import APIRouter

from app.api.routes.knowledge_v1 import router as knowledge_router

router = APIRouter()
router.include_router(knowledge_router)
