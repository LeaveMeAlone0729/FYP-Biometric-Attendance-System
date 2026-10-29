# Module owner: Chew Zhexuan
# Module: Facial Recognition and Liveness Detection
"""Encrypt stored face encodings; raw images and encodings are never API results."""

import json

from cryptography.fernet import Fernet


def encrypt_encoding(encoding, key):
    payload = json.dumps(list(map(float, encoding))).encode()
    return Fernet(key.encode()).encrypt(payload).decode()


def decrypt_encoding(value, key):
    return json.loads(Fernet(key.encode()).decrypt(value.encode()))
