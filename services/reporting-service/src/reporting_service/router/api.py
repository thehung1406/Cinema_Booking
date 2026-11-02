"""HTTP routes and request dependencies for this owner. App lifecycle stays in main."""

from datetime import date

import csv, io

from fastapi import Request, Depends, HTTPException, Query

from fastapi.responses import JSONResponse, Response

from pydantic import BaseModel, Field, model_validator

from sqlalchemy.orm import Session

from cinema_platform.auth import AuthError

from .. import reports

from fastapi import APIRouter


class Filters(BaseModel):
    start_date: date
    end_date: date
    film_id: int | None = Field(default=None, gt=0)
    theater_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def dates(self):
        if (
            self.end_date < self.start_date
            or (self.end_date - self.start_date).days > 366
        ):
            raise ValueError("Khoảng báo cáo không quá 367 ngày")
        return self


def create_router(app, engine, cfg):
    router = APIRouter()

    def session():
        with Session(engine) as db:
            yield db

    async def authorized(request: Request):
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Bearer token required")
        try:
            return await app.state.auth.introspect(token, "reports.view")
        except AuthError as exc:
            raise HTTPException(
                exc.status_code, "Không thể xác thực quyền báo cáo"
            ) from exc

    @router.get("/health/live")
    def live():
        return dict(status="ok", service="reporting")

    @router.get("/health/ready")
    def ready(db=Depends(session)):
        return (
            dict(status="ready", service="reporting")
            if reports.readiness(db)
            else JSONResponse(
                dict(status="not_ready", service="reporting"), status_code=503
            )
        )

    @router.get("/admin/reports", dependencies=[Depends(authorized)])
    def report(filters: Filters = Query(), db=Depends(session)):
        return reports.report(db, filters, cfg.stale_seconds)

    @router.get("/admin/reports.csv", dependencies=[Depends(authorized)])
    def export(filters: Filters = Query(), db=Depends(session)):
        data = reports.report(db, filters, cfg.stale_seconds)
        out = io.StringIO(newline="")
        writer = csv.writer(out)
        writer.writerow(
            ["film_id", "title", "revenue_vnd", "bookings", "tickets", "as_of", "stale"]
        )
        for row in data["by_film"]:
            title = row["title"]
            title = (
                "'" + title
                if title[:1] in {"=", "+", "-", "@", "\t", "\r", "\n"}
                else title
            )
            writer.writerow(
                [
                    row["film_id"],
                    title,
                    row["revenue"],
                    row["bookings"],
                    row["tickets"],
                    data["as_of"].isoformat(),
                    str(data["stale"]).lower(),
                ]
            )
        return Response(
            "\ufeff" + out.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="cinema-report.csv"'},
        )

    return router
