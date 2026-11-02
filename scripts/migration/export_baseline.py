"""Export current owner contracts without connecting to databases or loading local secrets.
Historical monolith OpenAPI/schema/import baselines remain frozen migration evidence.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def main():
    from cinema_platform.events import EventEnvelope
    from booking_service.events import ConfirmedData
    from notification_service.delivery import EmailData

    for name, model in [
        ("envelope", EventEnvelope),
        ("BookingConfirmed", ConfirmedData),
        ("BookingConfirmationEmailRequested", EmailData),
    ]:
        write_json(
            ROOT / f"contracts/events/v1/{name}.schema.json", model.model_json_schema()
        )
    from review_service.main import create_app as review_app
    from review_service.config import Settings as ReviewSettings
    from review_service.models import Base as ReviewBase
    from review_service.events import ReviewFact

    write_json(
        ROOT / "contracts/openapi/review.v1.json",
        review_app(
            ReviewSettings(database_url="sqlite:///./contract-review-not-opened.db")
        ).openapi(),
    )
    for event in ("ReviewChanged", "ReviewSentimentUpdated"):
        write_json(
            ROOT / f"contracts/events/v1/{event}.schema.json",
            ReviewFact.model_json_schema(),
        )
    write_json(
        ROOT / "docs/migration/review-owned-schema.json",
        [
            {
                "table": table.name,
                "columns": [column.name for column in table.columns],
                "foreign_keys": sorted(
                    f"{fk.parent.name} -> {fk.target_fullname}"
                    for fk in table.foreign_keys
                ),
            }
            for table in ReviewBase.metadata.sorted_tables
        ],
    )
    from ai_service.main import create_app as ai_app
    from ai_service.config import Settings as AISettings
    from ai_service.models import Base as AIBase

    ai_config = AISettings(
        database_url="sqlite:///./contract-ai-not-opened.db",
        redis_url="redis://localhost:6379/0",
        writes_enabled=False,
    )
    write_json(ROOT / "contracts/openapi/ai.v1.json", ai_app(ai_config).openapi())
    write_json(
        ROOT / "docs/migration/ai-owned-schema.json",
        [
            {
                "table": name,
                "columns": [column.name for column in table.columns],
                "foreign_keys": sorted(
                    f"{key.parent.name} -> {key.target_fullname}"
                    for key in table.foreign_keys
                ),
            }
            for name, table in sorted(AIBase.metadata.tables.items())
        ],
    )
    from identity_service.main import create_app as identity_app
    from identity_service.config import Settings as IdentitySettings
    from identity_service.models import Base as IdentityBase

    write_json(
        ROOT / "contracts/openapi/identity.v1.json",
        identity_app(
            IdentitySettings(database_url="sqlite:///./contract-identity-not-opened.db")
        ).openapi(),
    )
    write_json(
        ROOT / "docs/migration/identity-owned-schema.json",
        [
            {
                "table": t.name,
                "columns": [c.name for c in t.columns],
                "foreign_keys": sorted(
                    f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys
                ),
            }
            for t in IdentityBase.metadata.sorted_tables
        ],
    )
    from catalog_service.main import create_app as catalog_app
    from catalog_service.config import Settings as CatalogSettings
    from catalog_service.models import Base as CatalogBase

    write_json(
        ROOT / "contracts/openapi/catalog.v1.json",
        catalog_app(
            CatalogSettings(database_url="sqlite:///./contract-catalog-not-opened.db")
        ).openapi(),
    )
    write_json(
        ROOT / "docs/migration/catalog-owned-schema.json",
        [
            {
                "table": t.name,
                "columns": [c.name for c in t.columns],
                "foreign_keys": sorted(
                    f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys
                ),
            }
            for t in CatalogBase.metadata.sorted_tables
        ],
    )
    from cinema_service.main import create_app as cinema_app
    from cinema_service.config import Settings as CinemaSettings
    from cinema_service.models import Base as CinemaBase
    from booking_service.models import SalesBase
    from booking_service.schemas.sales import ImportSales, OpenSales

    write_json(
        ROOT / "contracts/openapi/cinema.v1.json",
        cinema_app(
            CinemaSettings(database_url="sqlite:///./contract-cinema-not-opened.db")
        ).openapi(),
    )
    for label, metadata in [
        ("cinema", CinemaBase.metadata),
        ("booking-sales", SalesBase.metadata),
    ]:
        write_json(
            ROOT / f"docs/migration/{label}-owned-schema.json",
            [
                {
                    "table": t.name,
                    "columns": [c.name for c in t.columns],
                    "foreign_keys": sorted(
                        f"{fk.parent.name} -> {fk.target_fullname}"
                        for fk in t.foreign_keys
                    ),
                }
                for t in metadata.sorted_tables
            ],
        )
    for label, model in [("import", ImportSales), ("open", OpenSales)]:
        write_json(
            ROOT / f"contracts/cinema-sales/v1/{label}.schema.json",
            model.model_json_schema(),
        )
    from booking_service.main import create_app as booking_app
    from booking_service.config import Settings as BookingSettings
    from booking_service.models import (
        Model as BookingModel,
        SalesBase as BookingSalesBase,
    )

    write_json(
        ROOT / "contracts/openapi/booking.v1.json",
        booking_app(
            BookingSettings(database_url="sqlite:///./contract-booking-not-opened.db")
        ).openapi(),
    )
    write_json(
        ROOT / "docs/migration/booking-owned-schema.json",
        [
            {
                "table": t.name,
                "columns": [c.name for c in t.columns],
                "foreign_keys": sorted(
                    f"{fk.parent.name} -> {fk.target_fullname}" for fk in t.foreign_keys
                ),
            }
            for metadata in [BookingModel.metadata, BookingSalesBase.metadata]
            for t in metadata.sorted_tables
        ],
    )
    from payment_service.main import create_app as payment_app
    from payment_service.config import Settings as PaymentSettings
    from payment_service.models import Base as PaymentBase
    from booking_service.models.payment_saga import SagaBase
    from cinema_platform.payment_contracts import Captured, BookingResult, CheckoutFact

    write_json(
        ROOT / "contracts/openapi/payment.v1.json",
        payment_app(
            PaymentSettings(database_url="sqlite:///./contract-payment-not-opened.db")
        ).openapi(),
    )
    for label, metadata in [
        ("payment", PaymentBase.metadata),
        ("booking-payment", SagaBase.metadata),
    ]:
        write_json(
            ROOT / f"docs/migration/{label}-owned-schema.json",
            [
                {
                    "table": t.name,
                    "columns": [c.name for c in t.columns],
                    "foreign_keys": sorted(
                        f"{fk.parent.name} -> {fk.target_fullname}"
                        for fk in t.foreign_keys
                    ),
                }
                for t in metadata.sorted_tables
            ],
        )
    for label, model in [
        ("PaymentCaptured", Captured),
        ("PaymentBookingResult", BookingResult),
    ]:
        write_json(
            ROOT / f"contracts/events/v1/{label}.schema.json", model.model_json_schema()
        )
    write_json(
        ROOT / "contracts/payment/v1/checkout.schema.json",
        CheckoutFact.model_json_schema(),
    )
    from reporting_service.main import create_app as reporting_app
    from reporting_service.config import Settings as ReportingSettings
    from reporting_service.models import Base as ReportingBase
    from cinema_platform.reporting import Fact, Checkpoint

    write_json(
        ROOT / "contracts/openapi/reporting.v1.json",
        reporting_app(
            ReportingSettings(
                database_url="sqlite:///./contract-reporting-not-opened.db"
            )
        ).openapi(),
    )
    write_json(
        ROOT / "contracts/events/v1/ReportFactChanged.schema.json",
        Fact.model_json_schema(),
    )
    write_json(
        ROOT / "contracts/events/v1/ReportCheckpoint.schema.json",
        Checkpoint.model_json_schema(),
    )
    write_json(
        ROOT / "docs/migration/reporting-owned-schema.json",
        [
            {
                "table": t.name,
                "columns": [c.name for c in t.columns],
                "foreign_keys": [],
            }
            for t in ReportingBase.metadata.sorted_tables
        ],
    )
    print(
        "Exported current owner API/event/schema contracts; historical baselines unchanged; no database connection."
    )


if __name__ == "__main__":
    main()
