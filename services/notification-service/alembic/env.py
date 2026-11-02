from alembic import context
from sqlalchemy import create_engine
from cinema_platform.events import MessagingBase
from notification_service.config import Settings
from notification_service.models import Base

settings = Settings()
target_metadata = [MessagingBase.metadata, Base.metadata]
with create_engine(settings.database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
