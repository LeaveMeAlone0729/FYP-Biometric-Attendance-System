import base64
import hashlib
import hmac
import json
import secrets
from cryptography.fernet import Fernet

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def hash_password(password):
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600_000)
    return 'pbkdf2_sha256$600000$' + base64.b64encode(salt).decode() + '$' + base64.b64encode(derived).decode()

def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, expected = encoded.split('$')
        if algorithm != 'pbkdf2_sha256' or int(rounds) != 600_000:
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt), int(rounds))
        return hmac.compare_digest(actual, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False

def encrypt_encoding(encoding, key):
    return Fernet(key.encode()).encrypt(json.dumps(list(map(float, encoding))).encode()).decode()

def decrypt_encoding(value, key):
    return json.loads(Fernet(key.encode()).decrypt(value.encode()))
