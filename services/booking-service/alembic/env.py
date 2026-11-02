from alembic import context
from sqlalchemy import create_engine
from booking_service.config import Settings
from booking_service.models import Model, SalesBase
from cinema_platform.events import MessagingBase
from booking_service.models.payment_saga import SagaBase

with create_engine(Settings().database_url).connect() as connection:
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
    connection.commit()
    context.configure(connection=connection, target_metadata=[Model.metadata,SalesBase.metadata,MessagingBase.metadata,SagaBase.metadata], version_table_schema=schema)
    with context.begin_transaction():
        context.run_migrations()
