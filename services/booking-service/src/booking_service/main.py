from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI,Depends
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine,text
from sqlalchemy.exc import SQLAlchemyError,IntegrityError
from cinema_platform.auth import AuthClient
from .config import Settings,request_settings
from .dependencies import writes

def create_app(settings=None,*,engine=None,auth_transport=None):
    settings=settings or Settings(); owned=engine is None
    engine=engine or create_engine(settings.database_url,pool_pre_ping=True)
    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(trust_env=False,transport=auth_transport) as http:
            app.state.auth=AuthClient(http,settings.identity_origin,settings.service_key)
            yield
        if owned: engine.dispose()
    app=FastAPI(title='Booking and legacy Payment',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.engine=engine; app.state.settings=settings
    @app.middleware('http')
    async def context(request,call_next):
        token=request_settings.set(settings)
        try:
            response=await call_next(request); response.headers['X-Service-Name']='booking'; return response
        finally: request_settings.reset(token)
    @app.exception_handler(SQLAlchemyError)
    async def error(request,exc): return JSONResponse({'detail':'Dữ liệu thay đổi hoặc Booking store chưa sẵn sàng'},status_code=409 if isinstance(exc,IntegrityError) else 503)
    @app.get('/health/live')
    def live(): return dict(status='ok',service='booking')
    @app.get('/health/ready')
    def ready():
        try:
            with engine.connect() as conn: conn.execute(text('SELECT 1 FROM checkout_snapshots LIMIT 0'))
        except SQLAlchemyError: return JSONResponse(dict(status='not_ready',service='booking'),status_code=503)
        return dict(status='ready',service='booking')
    from .router import booking,seat,payment,ticket,internal
    for router in (booking.router,seat.router,payment.router,ticket.router): app.include_router(router,dependencies=[Depends(writes)])
    app.include_router(internal.router)
    from cinema_platform.reporting import source_router
    app.include_router(source_router(engine,settings.service_key,'booking'))
    return app

def application(): return create_app()
