"""Translate validated filters to fixed owner APIs and build factual cards."""
from decimal import Decimal


def recommend(reader, context):
    if context.budget_amount and context.budget_scope == "unknown":
        return dict(answer="Ngân sách bạn nêu là cho mỗi vé hay tổng tiền vé của cả nhóm?",
                    status="needs_clarification", missing_fields=["budget_scope"], cards=[], sources=[])
    if not context.show_date:
        return dict(answer="Bạn muốn xem vào ngày nào? Mình sẽ tìm phim và suất đang mở bán phù hợp.",
                    status="needs_clarification", missing_fields=["show_date"], cards=[], sources=[])
    payload = context.model_dump(mode="json", exclude={"showtime_id", "budget_amount", "budget_scope", "knowledge_scope"})
    if context.budget_amount:
        payload["budget_total" if context.budget_scope == "total" else "budget_per_ticket"] = str(context.budget_amount)
    response = reader.call(reader.settings.booking_origin, "POST", "/internal/v1/booking-read/options", json=payload)
    # Validate the complete owner response, including links. Do not trust model-constructed cards.
    from datetime import date, time
    from pydantic import BaseModel, ConfigDict, Field, field_validator
    class Card(BaseModel):
        model_config = ConfigDict(extra="ignore")
        showtime_id: int = Field(gt=0)
        sales_version: int = Field(gt=0)
        film_id: int = Field(gt=0)
        film_title: str
        theater_id: int = Field(gt=0)
        theater_name: str
        room_name: str
        show_date: date
        start_time: time
        format: str | None
        available_seats: int = Field(ge=0)
        min_ticket_price: Decimal = Field(ge=0)
        minimum_total: Decimal = Field(ge=0)
        party_size: int = Field(ge=1, le=20)
        currency: str
        url: str

        @field_validator("currency")
        @classmethod
        def currency_vnd(cls, value):
            if value != "VND":
                raise ValueError("Unexpected currency")
            return value

    items = response.get("items")
    if not isinstance(items, list) or len(items) > 50:
        raise ValueError("Invalid booking options")
    cards, sources = [], []
    for row in items:
        card = Card.model_validate(row)
        if card.url != f"/seat-selection/{card.showtime_id}" or card.party_size != context.party_size:
            raise ValueError("Invalid booking action")
        data = card.model_dump(mode="json") | {"kind": "showtime"}
        cards.append(data)
        text = (f"{card.film_title} — {card.theater_name}, {card.show_date:%d/%m/%Y} {card.start_time:%H:%M}. "
                f"Giá vé còn bán từ {card.min_ticket_price:,.0f} VND; {card.party_size} vé từ {card.minimum_total:,.0f} VND. "
                f"Còn {card.available_seats} ghế tại thời điểm tra cứu; chưa giữ ghế, chưa bảo đảm ghế liền nhau.")
        sources.append(dict(id=f"showtime:{card.showtime_id}", title=card.film_title, text=text, url=card.url, kind="live"))
    return dict(answer="Mình tìm được các suất phù hợp dưới đây. Giá và ghế sẽ được kiểm tra lại khi bạn chọn."
                if cards else "Chưa có suất đáp ứng các điều kiện này. Bạn có thể đổi ngày, rạp hoặc ngân sách.",
                status="ok" if cards else "no_results", missing_fields=[], cards=cards, sources=sources,
                has_more=bool(response.get("has_more")))
