import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from ai_service.config import Settings
from ai_service.models import Base


@pytest.fixture
def ai_store():
    url = os.environ.get("AI_DATABASE_URL", "")
    if "test" not in url:
        pytest.skip("Dedicated AI test database required")
    root = create_engine(url)
    schema = "ai_test_" + uuid4().hex
    with root.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with root.begin() as conn:
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


@pytest.fixture
def ai_settings():
    return Settings(writes_enabled=True)


class FakeCache:
    def __init__(self):
        self.values, self.counts = {}, {}
    def ping(self):
        return True
    def eval(self, script, count, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]
    def setex(self, key, ttl, value):
        assert ttl > 0
        self.values[key] = value
    def delete(self, key):
        self.values.pop(key, None)
