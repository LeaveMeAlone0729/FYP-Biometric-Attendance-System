"""Initialize configuration, a separate MySQL schema, and the official MediaPipe model."""
import argparse
import getpass
import hashlib
import re
import sys
import warnings
from pathlib import Path
from urllib.request import urlopen
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent
MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
MODEL_SHA256 = 'fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1'

def install_hand_model():
    target = ROOT / 'models' / 'hand_landmarker.task'
    if not target.exists():
        target.parent.mkdir(exist_ok=True)
        with urlopen(MODEL_URL, timeout=60) as response:
            data = response.read(20 * 1024 * 1024)
        if len(data) < 1_000_000:
            raise SystemExit('Unexpected hand model download; model was not saved.')
        if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
            raise SystemExit('Hand model checksum did not match; model was not saved.')
        target.write_bytes(data)
    return target


def new_demo_password():
    if not sys.stdin.isatty():
        raise SystemExit('Create a new demo account from an interactive terminal.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            password = getpass.getpass('Choose a unique DEMO001 password (12-128 characters): ')
            confirmed = getpass.getpass('Confirm the DEMO001 password: ')
        except getpass.GetPassWarning:
            raise SystemExit('The terminal cannot securely read a password.') from None
    if not 12 <= len(password) <= 128 or password != confirmed:
        raise SystemExit('The demo password must be 12-128 characters and match its confirmation.')
    return password


def main():
    parser = argparse.ArgumentParser()
    model = parser.add_mutually_exclusive_group()
    model.add_argument('--skip-model', action='store_true')
    model.add_argument('--model-only', action='store_true', help='Install the liveness model without configuring or connecting to a database.')
    args = parser.parse_args()
    if args.model_only:
        print(f'Hand model ready: {install_hand_model()}')
        return
    env = ROOT / '.env'
    if not env.exists():
        text = (ROOT / '.env.example').read_text()
        env.write_text(text.replace('BIOMETRIC_KEY=\n', 'BIOMETRIC_KEY=' + Fernet.generate_key().decode() + '\n'))
    from config import Settings, local_now
    from database import make_engine, make_sessions
    from models import Base, Student
    from modules.devices.migration import upgrade_device_schema
    from modules.devices.verification_migration import upgrade_verification_schema
    from migrate import upgrade_schema
    from security import hash_password
    from demo import seed_demo
    import mysql.connector
    settings = Settings()
    if settings.db_user == 'replace_with_local_database_user':
        raise SystemExit('Set the intended database account in backend/.env before initializing the schema.')
    if not re.fullmatch(r'[A-Za-z0-9_]+', settings.db_name):
        raise SystemExit('DB_NAME may contain only letters, digits, and underscores.')
    if not settings.biometric_key:
        raise SystemExit('Set BIOMETRIC_KEY in .env before initializing the database.')
    Fernet(settings.biometric_key.encode())
    connection = mysql.connector.connect(host=settings.db_host, port=settings.db_port,
        user=settings.db_user, password=settings.db_password)
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{settings.db_name}` CHARACTER SET utf8mb4')
    connection.close()
    engine = make_engine(settings)
    Base.metadata.create_all(engine)
    upgrade_schema(engine)
    upgrade_device_schema(engine)
    upgrade_verification_schema(engine)
    if settings.demo_mode:
        with make_sessions(engine).begin() as db:
            seed_demo(db, local_now(settings))
            if db.get(Student, 'DEMO001') is None:
                db.add(Student(student_id='DEMO001', group_id=1, name='Demo Student', email='demo001@example.test',
                    password_hash=hash_password(new_demo_password()), created_at=local_now(settings)))
    engine.dispose()
    if not args.skip_model:
        install_hand_model()
    print(f'Database ready: {settings.db_name}.')
    if settings.demo_mode:
        print('Demo group: DEMO-A. Today\'s attendance PINs: 123456 and 654321.')
        print('Demo account: DEMO001 (use the assigned password).')

if __name__ == '__main__':
    main()
