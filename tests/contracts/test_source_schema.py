"""Database fences remain verifiable without retaining the old Python application."""

import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


@pytest.mark.parametrize(
    "domain,statement",
    [
        ("identity", "INSERT INTO roles(code,name) VALUES ('FENCED','Fenced')"),
        ("catalog", "INSERT INTO genres(name) VALUES ('Fenced genre')"),
        (
            "cinema",
            "INSERT INTO theaters(name,city,address) VALUES ('Fenced','Test','Test')",
        ),
        ("booking", "INSERT INTO booking_sales_gates(showtime_id) VALUES (999999)"),
    ],
)
@pytest.mark.parametrize("owner", ["service", None])
def test_frozen_source_schema_rejects_raw_writes_without_an_app(
    domain, statement, owner
):
    url = os.environ.get("SOURCE_SCHEMA_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated source schema test database required")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            txn = conn.begin()
            if owner:
                conn.execute(
                    text(
                        "UPDATE domain_ownership SET owner=:owner WHERE domain=:domain"
                    ),
                    dict(owner=owner, domain=domain),
                )
            else:
                conn.execute(
                    text("DELETE FROM domain_ownership WHERE domain=:domain"),
                    dict(domain=domain),
                )
            with pytest.raises(DBAPIError, match="frozen or transferred"):
                with conn.begin_nested():
                    conn.execute(text(statement))
            txn.rollback()
    finally:
        engine.dispose()
