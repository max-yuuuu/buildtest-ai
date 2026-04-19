from fastapi import APIRouter

from app.api.v1.knowledge_bases.routes import router as knowledge_bases_router
from app.api.v1.models.routes import router as models_router
from app.api.v1.providers.routes import router as providers_router
from app.api.v1.users.routes import router as users_router
from app.api.v1.vector_dbs.routes import router as vector_dbs_router

api_router = APIRouter()
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])
api_router.include_router(models_router, prefix="/providers/{provider_id}/models", tags=["models"])
api_router.include_router(vector_dbs_router, prefix="/vector-dbs", tags=["vector-dbs"])
api_router.include_router(
    knowledge_bases_router, prefix="/knowledge-bases", tags=["knowledge-bases"]
)
