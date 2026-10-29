"""Run from root: backend/venv/Scripts/python.exe backend/migrate_devices.py."""
from config import Settings
from database import make_engine
from modules.devices.migration import upgrade_device_schema

if __name__ == "__main__":
    engine = make_engine(Settings())
    try:
        created = upgrade_device_schema(engine)
        print("Device registration migration: " + (", ".join(created) if created else "already current"))
    finally:
        engine.dispose()
