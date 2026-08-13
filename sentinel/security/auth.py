import hashlib
import hmac
import os

def hash_pin(pin: str, salt: bytes = None, iterations: int = 250000) -> tuple:
    if salt is None:
        salt = os.urandom(32)
    pin_bytes = pin.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', pin_bytes, salt, iterations)
    return hashed, salt

def verify_pin(pin: str, hashed: bytes, salt: bytes, iterations: int = 250000) -> bool:
    check_hashed, _ = hash_pin(pin, salt, iterations)
    # compare_digest is in the hmac module, provides constant-time comparison
    return hmac.compare_digest(check_hashed, hashed)
