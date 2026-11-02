from alembic import context
from sqlalchemy import create_engine
from ai_service.config import Settings
from ai_service.models import Base

with create_engine(Settings().database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
