import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from cinema_platform.events import MessagingBase
from notification_service.config import Settings
from notification_service.models import Base


@pytest.fixture
def store():
    url = os.environ.get("NOTIFICATION_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated NOTIFICATION_DATABASE_URL with 'test' is required")
    root = create_engine(url)
    schema = "notification_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        MessagingBase.metadata.create_all(engine)
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.fixture
def notification_settings():
    return Settings(max_attempts=2)
