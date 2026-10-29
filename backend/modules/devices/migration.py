"""Add only Phase 1 tables, with no account/schema drops or secret generation."""
from sqlalchemy import inspect
from models import Base
from .models import DEVICE_TABLES


def upgrade_device_schema(engine):
    inspector = inspect(engine)
    for required in ("students", "auth_sessions"):
        if not inspector.has_table(required):
            raise RuntimeError("Initialize the existing application database first; missing " + required)
    before = set(inspector.get_table_names())
    Base.metadata.create_all(engine, tables=DEVICE_TABLES, checkfirst=True)
    return [table.name for table in DEVICE_TABLES if table.name not in before]
