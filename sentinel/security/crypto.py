import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

def generate_master_key() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    key = ''.join(alphabet[b % len(alphabet)] for b in os.urandom(22))
    checksum = sum(ord(c) for c in key) % len(alphabet)
    key += alphabet[checksum]
    key += alphabet[(checksum * 2) % len(alphabet)]
    return key

def derive_key(master_key: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=500000)
    return kdf.derive(master_key.encode('utf-8'))

def encrypt_backup(data: bytes, master_key: str) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return salt + nonce + ciphertext

def decrypt_backup(encrypted_data: bytes, master_key: str) -> bytes:
    salt = encrypted_data[:16]
    nonce = encrypted_data[16:28]
    ciphertext = encrypted_data[28:]
    key = derive_key(master_key, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)
