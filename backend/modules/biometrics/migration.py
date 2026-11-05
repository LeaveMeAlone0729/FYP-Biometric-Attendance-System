"""Retire the extra PAD column; temporary evidence now stays in server memory."""

from sqlalchemy import inspect, text


def retire_liveness_column(engine):
    with engine.begin() as connection:
        inspector = inspect(connection)
        if not inspector.has_table("verification_challenges"):
            return []
        columns = {column["name"] for column in inspector.get_columns("verification_challenges")}
        if "face_liveness_state" not in columns:
            return []
        connection.execute(text(
            "ALTER TABLE verification_challenges DROP COLUMN face_liveness_state"
        ))
        return ["verification_challenges.face_liveness_state"]


if __name__ == "__main__":
    from config import Settings
    from database import make_engine

    engine = make_engine(Settings())
    try:
        print("Retired PAD columns:", retire_liveness_column(engine) or "none; runtime checks need no extra column")
    finally:
        engine.dispose()
