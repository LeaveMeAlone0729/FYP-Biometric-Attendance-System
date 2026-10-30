"""Run from root with backend/venv/Scripts/python.exe backend/migrate_device_verification.py."""
from config import Settings
from database import make_engine
from modules.devices.verification_migration import upgrade_verification_schema

if __name__ == "__main__":
    engine = make_engine(Settings())
    try:
        created = upgrade_verification_schema(engine)
        print("Device verification migration: " + (", ".join(created) if created else "already current"))
    finally:
        engine.dispose()
