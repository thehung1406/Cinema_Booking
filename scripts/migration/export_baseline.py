"""Export source contracts without connecting to the application database.

Run from repository root in an environment with Backend requirements installed.
Output contains metadata only: no users, tokens, payment records or .env values.
"""

import ast
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Backend"))

# Explicit synthetic values prevent loading local application secrets from .env.
os.environ.update({
    "PAYMENT_DATABASE_URL":"sqlite:///./contract-payment-not-opened.db",
    "BOOKING_DATABASE_URL":"sqlite:///./contract-booking-not-opened.db",
    "PROJECT_NAME": "Cinema Booking contract export", "SECRET_KEY": "contract-export-not-for-auth",
    "ALGORITHM": "HS256", "ACCESS_TOKEN_EXPIRE_MINUTES": "15", "REFRESH_TOKEN_EXPIRE_DAYS": "7",
    "DATABASE_URL": "sqlite:///./contract-export-not-opened.db", "POSTGRES_USER": "contract",
    "POSTGRES_PASSWORD": "contract", "POSTGRES_DB": "contract_test", "FRONTEND_URL": "http://localhost:5173",
    "REDIS_HOST": "localhost", "REDIS_PORT": "6379", "REDIS_DB": "0", "REDIS_URL": "redis://localhost:6379/0",
    "TMN_CODE": "contract", "HASH_SECRET": "contract", "VNPAY_URL": "https://example.test/payment",
})

from main import app  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    write_json(ROOT / "contracts/openapi/monolith.v1.json", app.openapi())
    tables = []
    for name, table in sorted(SQLModel.metadata.tables.items()):
        tables.append({
            "table": name,
            "columns": [{"name": c.name, "type": str(c.type), "nullable": c.nullable, "primary_key": c.primary_key} for c in table.columns],
            "foreign_keys": sorted({f"{fk.parent.name} -> {fk.target_fullname}" for fk in table.foreign_keys}),
        })
    write_json(ROOT / "docs/migration/schema-baseline.json", tables)
    imports = {}
    for source in sorted((ROOT / "Backend/app").rglob("*.py")):
        parsed = ast.parse(source.read_text(encoding="utf-8-sig"))
        dependencies = sorted({
            node.module for node in ast.walk(parsed)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.")
        })
        if dependencies:
            imports[source.relative_to(ROOT).as_posix()] = dependencies
    write_json(ROOT / "docs/migration/import-baseline.json", imports)
    from cinema_platform.events import EventEnvelope
    from app.services.integration_events import ConfirmedData
    from notification_service.delivery import EmailData
    for name, model in [("envelope", EventEnvelope), ("BookingConfirmed", ConfirmedData), ("BookingConfirmationEmailRequested", EmailData)]:
        write_json(ROOT / f"contracts/events/v1/{name}.schema.json", model.model_json_schema())
    from review_service.main import create_app as review_app
    from review_service.config import Settings as ReviewSettings
    from review_service.models import Base as ReviewBase
    from review_service.events import ReviewFact
    write_json(ROOT / "contracts/openapi/review.v1.json", review_app(ReviewSettings(database_url="sqlite:///./contract-review-not-opened.db")).openapi())
    for event in ("ReviewChanged", "ReviewSentimentUpdated"):
        write_json(ROOT / f"contracts/events/v1/{event}.schema.json", ReviewFact.model_json_schema())
    write_json(ROOT / "docs/migration/review-owned-schema.json", [
        {"table": table.name, "columns": [column.name for column in table.columns],
         "foreign_keys": sorted(f"{fk.parent.name} -> {fk.target_fullname}" for fk in table.foreign_keys)}
        for table in ReviewBase.metadata.sorted_tables])
    from ai_service.main import create_app as ai_app
    from ai_service.config import Settings as AISettings
    from ai_service.models import Base as AIBase
    ai_config = AISettings(database_url="sqlite:///./contract-ai-not-opened.db", redis_url="redis://localhost:6379/0", writes_enabled=False)
    write_json(ROOT / "contracts/openapi/ai.v1.json", ai_app(ai_config).openapi())
    write_json(ROOT / "docs/migration/ai-owned-schema.json", [
        {"table": name, "columns": [column.name for column in table.columns],
         "foreign_keys": sorted(f"{key.parent.name} -> {key.target_fullname}" for key in table.foreign_keys)}
        for name, table in sorted(AIBase.metadata.tables.items())
    ])
    from identity_service.main import create_app as identity_app
    from identity_service.config import Settings as IdentitySettings
    from identity_service.models import Base as IdentityBase
    write_json(ROOT / "contracts/openapi/identity.v1.json", identity_app(IdentitySettings(database_url="sqlite:///./contract-identity-not-opened.db")).openapi())
    write_json(ROOT / "docs/migration/identity-owned-schema.json", [
        {"table": t.name, "columns": [c.name for c in t.columns],
         "foreign_keys": sorted(f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys)}
        for t in IdentityBase.metadata.sorted_tables])
    from catalog_service.main import create_app as catalog_app
    from catalog_service.config import Settings as CatalogSettings
    from catalog_service.models import Base as CatalogBase
    write_json(ROOT / "contracts/openapi/catalog.v1.json", catalog_app(CatalogSettings(database_url="sqlite:///./contract-catalog-not-opened.db")).openapi())
    write_json(ROOT / "docs/migration/catalog-owned-schema.json", [
        {"table": t.name, "columns": [c.name for c in t.columns],
         "foreign_keys": sorted(f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys)}
        for t in CatalogBase.metadata.sorted_tables])
    from cinema_service.main import create_app as cinema_app
    from cinema_service.config import Settings as CinemaSettings
    from cinema_service.models import Base as CinemaBase
    from app.models.sales import SalesBase
    from app.schemas.sales import ImportSales, OpenSales
    write_json(ROOT / "contracts/openapi/cinema.v1.json", cinema_app(CinemaSettings(database_url="sqlite:///./contract-cinema-not-opened.db")).openapi())
    for label,metadata in [("cinema",CinemaBase.metadata),("booking-sales",SalesBase.metadata)]:
        write_json(ROOT / f"docs/migration/{label}-owned-schema.json", [
            {"table":t.name,"columns":[c.name for c in t.columns],
             "foreign_keys":sorted(f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys)}
            for t in metadata.sorted_tables])
    for label,model in [("import",ImportSales),("open",OpenSales)]:
        write_json(ROOT / f"contracts/cinema-sales/v1/{label}.schema.json",model.model_json_schema())
    from booking_service.main import create_app as booking_app
    from booking_service.config import Settings as BookingSettings
    from booking_service.models import Model as BookingModel, SalesBase as BookingSalesBase
    write_json(ROOT / "contracts/openapi/booking.v1.json",booking_app(BookingSettings(database_url="sqlite:///./contract-booking-not-opened.db")).openapi())
    write_json(ROOT / "docs/migration/booking-owned-schema.json",[
        {"table":t.name,"columns":[c.name for c in t.columns],"foreign_keys":sorted(f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys)}
        for metadata in [BookingModel.metadata,BookingSalesBase.metadata] for t in metadata.sorted_tables])
    from payment_service.main import create_app as payment_app
    from payment_service.config import Settings as PaymentSettings
    from payment_service.models import Base as PaymentBase
    from booking_service.models.payment_saga import SagaBase
    from cinema_platform.payment_contracts import Captured,BookingResult,CheckoutFact
    write_json(ROOT / "contracts/openapi/payment.v1.json",payment_app(PaymentSettings(database_url="sqlite:///./contract-payment-not-opened.db")).openapi())
    for label,metadata in [("payment",PaymentBase.metadata),("booking-payment",SagaBase.metadata)]:
        write_json(ROOT / f"docs/migration/{label}-owned-schema.json",[{"table":t.name,"columns":[c.name for c in t.columns],"foreign_keys":sorted(f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys)} for t in metadata.sorted_tables])
    for label,model in [("PaymentCaptured",Captured),("PaymentBookingResult",BookingResult)]:
        write_json(ROOT / f"contracts/events/v1/{label}.schema.json",model.model_json_schema())
    write_json(ROOT / "contracts/payment/v1/checkout.schema.json",CheckoutFact.model_json_schema())
    operations = sum(method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}
                     for item in app.openapi()["paths"].values() for method in item)
    print(f"Exported {operations} HTTP operations, {len(tables)} tables and {len(imports)} import entries; no database connection.")


if __name__ == "__main__":
    main()
