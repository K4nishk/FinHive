"""System configuration endpoints."""
from fastapi import APIRouter

from app.schemas.loan import SystemConfig
from app.config import settings

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/", response_model=SystemConfig)
async def get_system_config() -> SystemConfig:
    """
    Get current system configuration.

    Returns:
        System configuration details
    """
    return SystemConfig(
        storage_type=settings.storage_type,
        encryption_enabled=settings.is_encryption_enabled,
        csv_output_dir=settings.csv_output_dir,
        app_version=settings.app_version,
    )
