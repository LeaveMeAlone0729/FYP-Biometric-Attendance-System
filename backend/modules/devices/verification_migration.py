"""Phase 2 is additive: preserve Phase 1 keys, audit, sessions and academic data."""
from sqlalchemy import inspect
from models import Base
from .verification_models import VERIFICATION_TABLES


def upgrade_verification_schema(engine):
    inspector = inspect(engine)
    for required in ("students", "auth_sessions", "registered_devices"):
        if not inspector.has_table(required):
            raise RuntimeError("Apply the existing app and Phase 1 migrations first; missing " + required)
    before = set(inspector.get_table_names())
    Base.metadata.create_all(engine, tables=VERIFICATION_TABLES, checkfirst=True)
    return [table.name for table in VERIFICATION_TABLES if table.name not in before]
