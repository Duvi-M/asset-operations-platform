from fastapi import APIRouter
from app.api.routes.parts import router as parts_router
from app.api.routes.assets import router as assets_router
from app.api.routes.interventions import router as interventions_router
from app.api.routes.import_excel import router as import_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(parts_router)
api_router.include_router(assets_router)
api_router.include_router(interventions_router)
api_router.include_router(import_router)
