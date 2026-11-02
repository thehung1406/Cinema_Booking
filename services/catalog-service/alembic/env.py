from alembic import context
from sqlalchemy import create_engine
from catalog_service.config import Settings
from catalog_service.models import Base

with create_engine(Settings().database_url).connect() as connection:
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
    connection.commit()
    context.configure(connection=connection, target_metadata=Base.metadata, version_table_schema=schema)
    with context.begin_transaction():
        context.run_migrations()
