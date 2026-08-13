import sys
import os
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sentinel.db.manager import DatabaseManager
from sentinel.security.auth import hash_pin, verify_pin
from sentinel.security.crypto import generate_master_key, encrypt_backup, decrypt_backup

def test_database():
    print("[1/4] Testing Database Initialization & Pragmas...")
    db = DatabaseManager("test_sentinel.db")
    db.connect()
    db.initialize()
    
    cur = db.conn.cursor()
    cur.execute("PRAGMA journal_mode;")
    mode = cur.fetchone()[0]
    assert mode.lower() == "wal"
    
    cur.execute("PRAGMA synchronous;")
    sync = cur.fetchone()[0]
    assert sync == 2 # FULL
    
    db.conn.close()
    if os.path.exists("test_sentinel.db"): os.remove("test_sentinel.db")
    print("      -> Database OK.")

def test_security_auth():
    print("[2/4] Testing PIN Hashing (PBKDF2)...")
    pin = "123456"
    hashed, salt = hash_pin(pin)
    assert verify_pin(pin, hashed, salt)
    print("      -> Auth OK.")

def test_security_crypto():
    print("[3/4] Testing Master Key & AES-GCM...")
    master_key = generate_master_key()
    payload = b"Secret Data"
    encrypted = encrypt_backup(payload, master_key)
    decrypted = decrypt_backup(encrypted, master_key)
    assert decrypted == payload
    print(f"      -> Crypto OK. Key: {master_key}")

if __name__ == "__main__":
    test_database()
    test_security_auth()
    test_security_crypto()
    print("\n[SUCCESS] Step 1 Foundation verified.")
