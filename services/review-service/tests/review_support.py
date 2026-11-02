import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from review_service.config import Settings
from review_service.models import Base
from cinema_platform.events import MessagingBase


@pytest.fixture
def review_store():
    url = os.environ.get("REVIEW_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated Review test database required")
    root = create_engine(url)
    schema = "review_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        MessagingBase.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.fixture
def review_settings():
    return Settings(writes_enabled=True)
