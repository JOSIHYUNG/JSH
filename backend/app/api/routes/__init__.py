from fastapi import APIRouter

from app.api.routes.knowledge_v1 import router as knowledge_router
from app.api.routes.agent_v1 import router as agent_router

router = APIRouter()
router.include_router(knowledge_router)
router.include_router(agent_router)
