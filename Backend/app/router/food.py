from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.schemas.food import FoodItemRead
from app.services.food_service import FoodService

router = APIRouter(prefix="/food-items", tags=["Bỏng, nước và combo"])


@router.get("", response_model=list[FoodItemRead])
def get_food_catalog(db: Session = Depends(get_session)):
    return FoodService.get_catalog(db)
