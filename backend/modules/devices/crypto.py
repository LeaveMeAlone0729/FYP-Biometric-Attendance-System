"""Android SHA256withECDSA interoperability: SPKI keys and DER signatures."""
import base64
import hashlib
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec


def decode_base64(value):
    return base64.b64decode(value, validate=True)


def canonical_public_key(value):
    try:
        raw = decode_base64(value)
        key = serialization.load_der_public_key(raw)
        if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(key.curve, ec.SECP256R1):
            raise ValueError("Use an ECDSA P-256 public key.")
        canonical = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        return base64.b64encode(canonical).decode("ascii"), hashlib.sha256(canonical).hexdigest()
    except (ValueError, TypeError, UnsupportedAlgorithm) as exc:
        raise ValueError("Use a base64 DER SubjectPublicKeyInfo ECDSA P-256 public key.") from exc


def verify_signature(public_key, payload, signature):
    try:
        key = serialization.load_der_public_key(decode_base64(public_key))
        key.verify(decode_base64(signature), payload.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, ValueError, TypeError, UnsupportedAlgorithm):
        return False
