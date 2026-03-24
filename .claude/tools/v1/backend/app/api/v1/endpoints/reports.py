"""Reporting API endpoints."""
from fastapi import APIRouter, HTTPException
from typing import Dict

from app.services.storage_service import storage_service
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/statistics")
async def get_statistics() -> Dict:
    """
    Get loan statistics and summaries.

    Returns:
        Dictionary containing various loan statistics
    """
    try:
        return storage_service.get_statistics()
    except Exception as e:
        logger.error("statistics_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
