from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.violation_repository import ViolationRepository
from app.schemas.violation import (
    ViolationCreate,
    ViolationListResponse,
    ViolationResponse,
)
from app.services.violation_service import ViolationService

router = APIRouter(
    prefix="/api/v1/violations",
    tags=["Violations"],
)


def get_violation_service(
    db: Session = Depends(get_db),  # noqa: B008
) -> ViolationService:
    """Provide a violation service with its database repository."""
    repository = ViolationRepository(db)
    return ViolationService(repository)


@router.post(
    "",
    response_model=ViolationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_violation(
    data: ViolationCreate,
    service: ViolationService = Depends(get_violation_service),  # noqa: B008
):
    """Create a new vehicle speed violation."""
    return service.create_violation(data)


@router.get(
    "",
    response_model=ViolationListResponse,
)
def get_violations(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ViolationService = Depends(get_violation_service),  # noqa: B008
):
    """Return a paginated list of vehicle violations."""
    items = service.get_violations(limit=limit, offset=offset)
    total = service.count_violations()

    return ViolationListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{violation_id}",
    response_model=ViolationResponse,
)
def get_violation(
    violation_id: int,
    service: ViolationService = Depends(get_violation_service),  # noqa: B008
):
    """Return a single violation by its ID."""
    violation = service.get_violation(violation_id)

    if violation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Violation not found.",
        )

    return violation


