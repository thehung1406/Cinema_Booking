from fastapi import APIRouter,Depends
from app.router.internal_auth import internal_service
from app.utils.booking_ownership import get_owner
router=APIRouter(prefix="/internal/v1/booking-read",dependencies=[Depends(internal_service)],include_in_schema=False)
@router.get("/ownership")
def ownership(): return {"owner":get_owner()}
