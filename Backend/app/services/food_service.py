from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.food import BookingFoodItem, ComboItem, FoodItem
from app.schemas.food import FoodItemRead, FoodSelection


class FoodService:
    @staticmethod
    def get_catalog(db: Session) -> list[FoodItemRead]:
        items = db.exec(select(FoodItem).order_by(FoodItem.id)).all()
        by_id = {item.id: item for item in items}
        components = {}
        for part in db.exec(select(ComboItem).order_by(ComboItem.id)).all():
            components.setdefault(part.combo_id, []).append(part)
        result = []
        for item in items:
            if not item.is_active:
                continue
            parts = components.get(item.id, [])
            if item.category == "COMBO" and (not parts or any(
                part.food_item_id not in by_id
                or not by_id[part.food_item_id].is_active
                or by_id[part.food_item_id].category == "COMBO"
                for part in parts
            )):
                continue
            result.append(FoodItemRead(
                id=item.id, name=item.name, description=item.description,
                category=item.category, price=item.price,
                components=[dict(food_item_id=p.food_item_id,
                    name=by_id[p.food_item_id].name, quantity=p.quantity) for p in parts],
            ))
        return result

    @staticmethod
    def quote(db: Session, selections: list[FoodSelection]) -> tuple[list[dict], Decimal]:
        if not selections:
            return [], Decimal("0")
        ids = [s.food_item_id for s in selections]
        if len(ids) != len(set(ids)):
            raise HTTPException(400, "Danh sách bỏng, nước và combo bị trùng")
        catalog = {item.id: item for item in FoodService.get_catalog(db)}
        lines = []
        total = Decimal("0")
        for selection in selections:
            item = catalog.get(selection.food_item_id)
            if item is None:
                raise HTTPException(409, "Món hoặc combo đã ngừng bán. Vui lòng chọn lại.")
            lines.append(dict(food_item_id=item.id, name=item.name, category=item.category,
                quantity=selection.quantity, unit_price=item.price,
                components=[p.model_dump() for p in item.components]))
            total += item.price * selection.quantity
        return lines, total

    @staticmethod
    def save(db: Session, booking_id: int, lines: list[dict]) -> None:
        for line in lines:
            db.add(BookingFoodItem(booking_id=booking_id, **line))
        if lines:
            db.flush()

    @staticmethod
    def for_bookings(db: Session, booking_ids: list[int]) -> dict[int, list[dict]]:
        result = {}
        if not booking_ids:
            return result
        for line in db.exec(select(BookingFoodItem).where(
            BookingFoodItem.booking_id.in_(booking_ids)).order_by(BookingFoodItem.id)).all():
            result.setdefault(line.booking_id, []).append(dict(
                food_item_id=line.food_item_id, name=line.name, category=line.category,
                quantity=line.quantity, unit_price=line.unit_price,
                line_total=line.unit_price * line.quantity, components=line.components,
            ))
        return result
