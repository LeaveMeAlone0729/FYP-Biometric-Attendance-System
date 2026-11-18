"""Local test-only SHA256/ECDSA signer. Never imported by the production app."""
import argparse,base64
from pathlib import Path
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import ec
parser=argparse.ArgumentParser()
parser.add_argument('--key',type=Path,required=True)
parser.add_argument('--payload',required=True)
args=parser.parse_args()
if 'slot2-e2e-' not in str(args.key.resolve()):raise RuntimeError('Not a disposable test key')
key=serialization.load_pem_private_key(args.key.read_bytes(),password=None)
if not isinstance(key,ec.EllipticCurvePrivateKey) or not isinstance(key.curve,ec.SECP256R1):raise RuntimeError('Expected test P256 key')
print(base64.b64encode(key.sign(base64.b64decode(args.payload,validate=True),ec.ECDSA(hashes.SHA256()))).decode())
