from pathlib import Path
from types import SimpleNamespace
from decimal import Decimal
import re,sys
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text,event,select
from sqlmodel import Session

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Backend/tests'))
sys.path.insert(0,str(ROOT/'services/booking-service/tests'))
from test_normalized_schema import pg
from booking_support import booking_store
from test_booking import ready,request,params
from booking_service.config import Settings
from booking_service.main import create_app
from booking_service.models import Booking
from booking_service import reservations,bookings
from booking_service.payment_repo import PaymentRepository
from booking_service.payments import PaymentService
from app.core.config import settings


def test_source_ai_review_report_use_booking_owner_without_reading_frozen_tables(pg,ready,monkeypatch):
    from app.services import booking_remote,catalog_remote,identity_remote,review_remote
    from app.services.ai_tools import run_tool
    from app.schemas.ai import ToolCall,ToolContext
    from app.router.internal_review_read import authors,Authors,candidates
    from app.repositories.admin_repo import report
    from app.schemas.admin import ReportFilters
    from datetime import date,timedelta
    pg.execute(text("UPDATE domain_ownership SET owner='service' WHERE domain='booking'")); pg.commit()
    for key in ('BOOKING_STORAGE_OWNER','CATALOG_STORAGE_OWNER','IDENTITY_STORAGE_OWNER','CINEMA_STORAGE_OWNER','REVIEW_STORAGE_OWNER'): monkeypatch.setattr(settings,key,'service')
    cfg=Settings(writes_enabled=True)
    app=create_app(cfg,engine=ready,auth_transport=httpx.MockTransport(lambda r:httpx.Response(200,json=dict(user_id=999999,role='USER',permissions=[],is_active=True))))
    with Session(ready) as db:
        rid=reservations.hold(db,1,[1,2],999999)[0]['reservation_id']
        created=bookings.create(db,request(user=999999,reservation=rid),999999,'owner-boundary')
        booking=db.get(Booking,created['bookingId']); payment=PaymentRepository.create_attempt(db,booking)
        assert PaymentService.confirm_vnpay_payment(db,booking.id,'00',params(payment))['status']=='success'
    with TestClient(app) as client:
        def call(method,path,**kwargs):
            response=client.request(method,path,headers={'X-Service-Key':cfg.service_key},**kwargs)
            if response.status_code!=200: raise HTTPException(response.status_code,response.text)
            return response.json()
        monkeypatch.setattr(booking_remote,'call',call)
        monkeypatch.setattr(catalog_remote,'film_batch',lambda ids,**kw:{i:SimpleNamespace(id=i,title='Current Catalog label',image=None) for i in ids})
        monkeypatch.setattr(identity_remote,'profiles',lambda ids:{i:SimpleNamespace(username='Independent Identity') for i in ids})
        monkeypatch.setattr(review_remote,'report',lambda *a:dict(positive=0,negative=0,neutral=0,total=0,pending=0,coverage=0))
        queries=[]
        def watch(conn,cursor,statement,*args): queries.append(statement.lower())
        event.listen(pg.bind,'before_cursor_execute',watch)
        try:
            evidence=run_tool(pg,ToolCall(name='get_ticket_prices',context=ToolContext(showtime_id=1)))
            assert evidence and '75,000' in evidence[0]['text']
            verified=authors(Authors(items=[dict(user_id=999999,film_id=2000001)]),pg)
            assert verified[0]['verified_purchase'] and verified[0]['author']=='Independent Identity'
            assert candidates(db=pg)[0]['id']==2000001
            result=report(pg,ReportFilters(start_date=date.today(),end_date=date.today()+timedelta(days=10)))
            assert Decimal(result['revenue'])==150000 and result['ticket_count']==2 and result['occupied_seats']==2
            assert result['by_film'][0]['title']=='Current Catalog label'
        finally: event.remove(pg.bind,'before_cursor_execute',watch)
    assert not any(re.search(r'(?:from|join)\s+(?:bookings|booking_details|booking_food_items|payments|tickets|seat_status|booking_sales_configurations|booking_sales_gates)\b',q) for q in queries)
