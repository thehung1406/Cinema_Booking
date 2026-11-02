from pathlib import Path
import sys
from sqlmodel import Session
from sqlalchemy import select
from fastapi import HTTPException

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'services/booking-service/tests'))
sys.path.insert(0,str(ROOT/'services/catalog-service/tests'))
from booking_support import booking_store
from test_booking import ready,request,params
from catalog_support import catalog_store,catalog_settings,catalog_client,HEADERS
from booking_service.models import Booking,Checkout
from booking_service import reservations,bookings,catalog
from booking_service.schemas.food import FoodSelection
from booking_service.payment_repo import PaymentRepository
from booking_service.payments import PaymentService
from booking_service.booking_repo import BookingRepository


def test_booking_uses_real_catalog_quote_and_keeps_combo_snapshot_after_menu_edit(ready,catalog_client,catalog_settings,monkeypatch):
    def call(method,path,**kwargs):
        response=catalog_client.request(method,path,headers={'X-Service-Key':catalog_settings.service_key},**kwargs)
        if response.status_code!=200: raise HTTPException(response.status_code,response.text)
        return response.json()
    monkeypatch.setattr(catalog,'call',call)
    with Session(ready) as db:
        rid=reservations.hold(db,1,[1,2],1)[0]['reservation_id']
        body=request(reservation=rid,total=200000)
        body.foodItems=[FoodSelection(food_item_id=3,quantity=2)]
        created=bookings.create(db,body,1,'real-quote')
        booking=db.get(Booking,created['bookingId'])
        assert booking.food_quote_id and booking.food_quote_version==1
        snapshot=db.get(Checkout,booking.id).snapshot
        assert snapshot['food_items'][0]['unit_price']=='25000.00'
        assert len(snapshot['food_items'][0]['components'])==2
        changed=catalog_client.put('/admin/food-items/3',headers=HEADERS,json=dict(name='Renamed combo',category='COMBO',price='99000.00',components=[dict(food_item_id=1,quantity=1),dict(food_item_id=2,quantity=2)]))
        assert changed.status_code==200,changed.text
        payment=PaymentRepository.create_attempt(db,booking)
        monkeypatch.setattr(catalog,'call',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('Callback/history cannot call Catalog')))
        assert PaymentService.confirm_vnpay_payment(db,booking.id,'00',params(payment))['status']=='success'
        history=BookingRepository.get_booking_with_details(db,booking.id)
        assert history['foodItems'][0]['unit_price']==25000 and history['totalAmount']==200000
        assert history['foodItems'][0]['name']=='Combo'
