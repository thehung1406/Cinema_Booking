"""Read-only business facade while Catalog/Cinema/Review/Booking remain legacy."""

import unicodedata

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.models import Film, Theater
from app.router.internal_auth import internal_service
from app.schemas.ai import ToolCall, ToolContext
from app.services.ai_tools import run_tool, validate_context

router = APIRouter(prefix="/internal/v1/ai-read", include_in_schema=False, dependencies=[Depends(internal_service)])


def folded(value):
    value = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(max_length=2000)


class Invocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: ToolCall
    evening: bool = False


@router.post("/matches")
def matches(body: MatchRequest, db: Session = Depends(get_session)):
    text = folded(body.message)
    result = {}
    from app.utils.catalog_ownership import get_owner
    from app.services.catalog_remote import call
    owner = get_owner(db)
    if owner == "maintenance":
        from fastapi import HTTPException
        raise HTTPException(503, "Catalog đang chuyển dữ liệu")
    from app.utils.cinema_ownership import get_owner as cinema_owner
    if cinema_owner(db)=="service":
        from app.services.cinema_remote import call as cinema_call
        result["theater_id"]=cinema_call("POST","/internal/v1/theaters/matches",json={"message":body.message})
        models=[]
    else: models = [("theater_id", Theater, Theater.name)]
    if owner == "service": result["film_id"] = call("POST", "/internal/v1/films/matches", json={"message": body.message})
    else: models.append(("film_id", Film, Film.title))
    for key, model, attribute in models:
        rows = db.exec(select(model.id, attribute).where(model.deleted_at.is_(None))).all()
        result[key] = [dict(id=id, name=name) for id, name in rows if len(folded(name)) > 2 and folded(name) in text]
    return result


@router.post("/context")
def context(body: ToolContext, db: Session = Depends(get_session)):
    validate_context(db, body)
    from app.services.catalog_remote import get_film
    film = get_film(db, body.film_id) if body.film_id else None
    from app.utils.cinema_ownership import get_owner as cinema_owner
    if body.theater_id and cinema_owner(db)=="service":
        from app.services.cinema_remote import object_at
        theater=object_at(f"/theaters/{body.theater_id}")
    else: theater = db.get(Theater, body.theater_id) if body.theater_id else None
    return dict(film_name=film.title if film else None, theater_name=theater.name if theater else None)


@router.post("/tool")
def tool(body: Invocation, db: Session = Depends(get_session)):
    return run_tool(db, body.call, body.evening)


@router.get("/ownership")
def ownership():
    from app.utils.ai_ownership import get_owner
    return {"owner": get_owner()}
