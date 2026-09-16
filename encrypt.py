import base64
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# Default public key can be overridden by setting RSA_PUBLIC_KEY_PEM (paste the
# full PEM block as-is; newlines are optional, this parses either way).
_DEFAULT_PEM = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCRVvQPKvoRJobUMXz8jviEAxF2
TbOCxGQ+pWno1DNRy3Z6ZpZXKEmrUvURF+0X5kMSG2nZmS6GEPzgSvxj/6H6lBly
xlfsgjaesUV/9HVZjIjjVON2dLPnCWYu/4i1ydZAvk3Xa6CCTNeP/Qp8q968MRin
ObJlyZvrTPIzWKWEMwIDAQAB
-----END PUBLIC KEY-----"""

_pem = os.environ.get("RSA_PUBLIC_KEY_PEM", "").strip() or _DEFAULT_PEM
_public_key = serialization.load_pem_public_key(_pem.encode())

# Max plaintext for RSA-OAEP-SHA256 = key_size_bytes - 2*hash_len - 2.
# For a 1024-bit key that's 128 - 64 - 2 = 62 bytes — a hex ASCII string of a
# 256-bit private key (up to 64 chars) would NOT fit, so we encrypt the raw
# binary value (max 32 bytes) instead of its hex text representation.


def encrypt_priv_hex(priv_hex: str) -> str:
    """Encrypt a private-key hex string (with or without 0x) and return
    base64 ciphertext. Raises if it doesn't fit this key's OAEP capacity."""
    clean = priv_hex.strip().lower().replace("0x", "")
    if len(clean) % 2:
        clean = "0" + clean
    raw = bytes.fromhex(clean)

    ciphertext = _public_key.encrypt(
        raw,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(ciphertext).decode()
