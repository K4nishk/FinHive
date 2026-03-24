"""Loan management API endpoints."""
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional

from app.schemas.loan import (
    LoanCreate,
    LoanUpdate,
    LoanResponse,
    LoanFilters,
)
from app.services.storage_service import storage_service
from app.core.exceptions import LoanNotFoundException, StorageException, ValidationException
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/loans", tags=["loans"])


@router.post("/", response_model=LoanResponse, status_code=status.HTTP_201_CREATED)
async def create_loan(loan: LoanCreate) -> LoanResponse:
    """
    Create a new loan record.

    Args:
        loan: Loan data including borrower, amount, dates

    Returns:
        Created loan record with generated ID

    Raises:
        HTTPException: If loan creation fails
    """
    try:
        return storage_service.create_loan(loan)
    except ValidationException as e:
        logger.warning("loan_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except StorageException as e:
        logger.error("loan_create_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[LoanResponse])
async def get_loans(
    borrower_name: Optional[str] = None,
    depositor_name: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[LoanResponse]:
    """
    Get all loans with optional filters.

    Args:
        borrower_name: Filter by borrower name (partial match)
        depositor_name: Filter by depositor name (partial match)
        status: Filter by loan status
        date_from: Filter by giving date from (YYYY-MM-DD)
        date_to: Filter by giving date to (YYYY-MM-DD)

    Returns:
        List of loan records matching the filters
    """
    try:
        filters = LoanFilters(
            borrower_name=borrower_name,
            depositor_name=depositor_name,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
        return storage_service.get_all_loans(filters)
    except Exception as e:
        logger.error("loans_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{loan_id}", response_model=LoanResponse)
async def get_loan(loan_id: str) -> LoanResponse:
    """
    Get a specific loan by ID.

    Args:
        loan_id: Unique loan identifier

    Returns:
        Loan record

    Raises:
        HTTPException: If loan not found
    """
    try:
        return storage_service.get_loan_by_id(loan_id)
    except LoanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("loan_fetch_failed", loan_id=loan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{loan_id}", response_model=LoanResponse)
async def update_loan(loan_id: str, loan_update: LoanUpdate) -> LoanResponse:
    """
    Update an existing loan.

    Args:
        loan_id: Unique loan identifier
        loan_update: Updated loan data

    Returns:
        Updated loan record

    Raises:
        HTTPException: If loan not found or update fails
    """
    try:
        return storage_service.update_loan(loan_id, loan_update)
    except LoanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        logger.warning("loan_update_validation_error", loan_id=loan_id, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("loan_update_failed", loan_id=loan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_loan(loan_id: str):
    """
    Delete a loan record.

    Args:
        loan_id: Unique loan identifier

    Raises:
        HTTPException: If loan not found or deletion fails
    """
    try:
        storage_service.delete_loan(loan_id)
    except LoanNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("loan_delete_failed", loan_id=loan_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
