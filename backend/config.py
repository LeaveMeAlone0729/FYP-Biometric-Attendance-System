import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime

ROOT = Path(__file__).resolve().parent

def load_env():
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

load_env()

@dataclass(frozen=True)
class Settings:
    db_host: str = os.getenv('DB_HOST', '127.0.0.1')
    db_port: int = int(os.getenv('DB_PORT', '3306'))
    db_user: str = os.getenv('DB_USER', 'root')
    db_password: str = os.getenv('DB_PASSWORD', '')
    db_name: str = os.getenv('DB_NAME', 'attendance_proposal_xampp')
    demo_mode: bool = os.getenv('DEMO_MODE', 'false').lower() == 'true'
    timezone: str = os.getenv('APP_TIMEZONE', 'Asia/Kuala_Lumpur')
    session_hours: int = int(os.getenv('SESSION_HOURS', '8'))
    challenge_seconds: int = int(os.getenv('CHALLENGE_SECONDS', '90'))
    face_threshold: float = float(os.getenv('FACE_DISTANCE_THRESHOLD', '0.45'))
    biometric_key: str = os.getenv('BIOMETRIC_KEY', '')

def local_now(settings):
    return datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)

def iso_time(value, settings):
    return value.replace(tzinfo=ZoneInfo(settings.timezone)).isoformat() if value else None
