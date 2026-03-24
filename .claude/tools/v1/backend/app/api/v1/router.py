"""API version 1 router aggregation."""
from fastapi import APIRouter

from app.api.v1.endpoints import loans, reports, config

api_router = APIRouter()

api_router.include_router(loans.router)
api_router.include_router(reports.router)
api_router.include_router(config.router)
