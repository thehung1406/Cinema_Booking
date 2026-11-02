"""Temporary reporting adapter: no SQL against transferred Booking tables."""
from datetime import datetime,timezone
from fastapi import HTTPException
from app.services.booking_remote import call
from app.services.catalog_remote import film_batch
from app.services.review_remote import report as review_report

def report(db,filters):
    params={k:(v.isoformat() if hasattr(v,"isoformat") else v) for k,v in filters.model_dump().items() if v is not None}
    result=call("GET","/internal/v1/booking-read/report",params=params)
    labels=film_batch([row["film_id"] for row in result["by_film"]],include_retired=True)
    for row in result["by_film"]:
        if row["film_id"] not in labels: raise HTTPException(503,"Thiếu nhãn phim báo cáo")
        row["title"]=labels[row["film_id"]].title
    ids=[filters.film_id] if filters.film_id else None
    if filters.theater_id: ids=result["screened_film_ids"]
    db.rollback()
    result["sentiments"]=review_report(filters.start_date,filters.end_date,ids)
    result.pop("screened_film_ids",None)
    result.update(as_of=datetime.now(timezone.utc),filters=filters.model_dump())
    return result
