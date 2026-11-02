"""Frozen source schema for isolated migration tests only; no legacy app imports."""

import os
from logging.config import fileConfig
from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

config = context.config
url = os.environ["SOURCE_SCHEMA_DATABASE_URL"]
if "test" not in (make_url(url).database or "").lower():
    raise RuntimeError("Source schema fixture requires an isolated test database")
if config.config_file_name:
    fileConfig(config.config_file_name)
if context.is_offline_mode():
    context.configure(url=url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
