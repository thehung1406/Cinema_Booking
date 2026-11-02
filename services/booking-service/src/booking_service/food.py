from datetime import datetime,timezone
from decimal import Decimal
from sqlmodel import select
from fastapi import HTTPException
from .models import Booking,BookingFoodItem
from .catalog import quote,QuotedLines

class FoodService:
    @staticmethod
    def quote(db,selections): return quote(selections) if selections else ([],Decimal('0'))
    @staticmethod
    def save(db,booking_id,lines):
        if isinstance(lines,QuotedLines):
            if lines.quote.expires_at<=datetime.now(timezone.utc): raise HTTPException(409,'Quote đã hết hạn')
            booking=db.get(Booking,booking_id)
            booking.food_quote_id=str(lines.quote.id); booking.food_quote_version=lines.quote.version; booking.food_quote_expires_at=lines.quote.expires_at
        for line in lines: db.add(BookingFoodItem(booking_id=booking_id,**line))
        db.flush()
    @staticmethod
    def for_bookings(db,booking_ids):
        result={}
        for line in db.exec(select(BookingFoodItem).where(BookingFoodItem.booking_id.in_(booking_ids)).order_by(BookingFoodItem.id)):
            result.setdefault(line.booking_id,[]).append(dict(food_item_id=line.food_item_id,name=line.name,category=line.category,quantity=line.quantity,unit_price=line.unit_price,line_total=line.unit_price*line.quantity,components=line.components))
        return result
