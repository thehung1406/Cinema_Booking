from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db
import uvicorn
import logging
from app.router.auth import router as auth_router
from app.router.cinema_room import router as cinema_room_router
from app.router.theater import router as theater_router
from app.router.film import router as film_router
from app.router.showtime import router as showtime_router
from app.router.seat import router as seat_router
from app.router.seat_type import router as seat_type_router
from app.router.booking import router as booking_router
from app.router.payment import router as payment_router
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: runs init_db on startup."""
    init_db()
    yield


app = FastAPI(
    title="BackendTTCS API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unhandled errors (500)."""
    logger.error(f"Unhandled error on {request.method} {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Lỗi hệ thống, vui lòng thử lại sau."}
    )


@app.get("/")
def root():
    return {"message": "FastAPI running with Docker 🚀"}

@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}



app.include_router(auth_router)
app.include_router(cinema_room_router)
app.include_router(theater_router)
app.include_router(film_router)
app.include_router(showtime_router)
app.include_router(seat_router)
app.include_router(seat_type_router)
app.include_router(booking_router)
app.include_router(payment_router)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
