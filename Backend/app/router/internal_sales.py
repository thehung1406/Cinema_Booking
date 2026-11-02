from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.router.internal_auth import internal_service
from app.schemas.sales import SalesCommand, ImportSales, OpenSales
from app.services import sales_service as service

from app.utils.booking_ownership import require_legacy_booking_owner

def legacy_booking(db: Session = Depends(get_session)):
    require_legacy_booking_owner(db)

router = APIRouter(prefix="/internal/v1/sales", include_in_schema=False, dependencies=[Depends(internal_service), Depends(legacy_booking)])


@router.post("/{showtime_id}/close")
def close(showtime_id: int, body: SalesCommand, db: Session = Depends(get_session)):
    return service.close(db, showtime_id, body.epoch)


@router.post("/{showtime_id}/import")
def install(showtime_id: int, body: ImportSales, db: Session = Depends(get_session)):
    from fastapi import HTTPException
    if body.snapshot.showtime_id != showtime_id: raise HTTPException(409, "Sai suất chiếu công bố")
    return service.install(db, body.snapshot, body.digest, body.epoch)


@router.post("/{showtime_id}/open")
def open_sales(showtime_id: int, body: OpenSales, db: Session = Depends(get_session)):
    return service.open_sales(db, showtime_id, body.sales_version, body.digest, body.epoch)


@router.get("/{showtime_id}/state")
def state(showtime_id: int, seat_id: int | None = None, db: Session = Depends(get_session)):
    row = service.gate(db, showtime_id, lock=True, create=True)
    result = {"epoch": row.epoch, "is_open": row.is_open, "sales_version": row.sales_version,
              **service.stats(db, showtime_id, seat_id=seat_id)}
    db.commit()
    return result


@router.get("/migration/ownership")
def ownership():
    from app.utils.cinema_ownership import get_owner
    return {"owner": get_owner()}
