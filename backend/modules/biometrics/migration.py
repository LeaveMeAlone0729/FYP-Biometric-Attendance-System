"""Add persisted passive anti-spoof evidence without changing existing biometric data."""

from sqlalchemy import inspect, text


def upgrade_liveness_schema(engine):
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("verification_challenges"):
            return []
        columns = {column["name"] for column in inspector.get_columns("verification_challenges")}
        if "face_liveness_state" in columns:
            return []
        connection.execute(text(
            "ALTER TABLE verification_challenges ADD COLUMN face_liveness_state TEXT NULL"
        ))
        return ["verification_challenges.face_liveness_state"]


if __name__ == "__main__":
    from config import Settings
    from database import make_engine

    engine = make_engine(Settings())
    try:
        print("Liveness schema:", upgrade_liveness_schema(engine) or "already current")
    finally:
        engine.dispose()
