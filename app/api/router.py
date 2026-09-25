from fastapi import APIRouter

from app.api.routes import flags

api_router = APIRouter()
api_router.include_router(flags.router)
