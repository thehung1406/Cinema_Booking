from cinema_platform.events import MessagingBase
from alembic import context
from sqlalchemy import create_engine
from review_service.config import Settings
from review_service.models import Base

with create_engine(Settings().database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=[Base.metadata, MessagingBase.metadata])
    with context.begin_transaction():
        context.run_migrations()
