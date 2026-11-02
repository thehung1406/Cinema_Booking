from fastapi import APIRouter, Depends
from app.router.internal_auth import internal_service

router = APIRouter(prefix="/internal/v1/catalog-read", include_in_schema=False, dependencies=[Depends(internal_service)])


@router.get("/ownership")
def ownership():
    from app.utils.catalog_ownership import get_owner
    return {"owner": get_owner()}
