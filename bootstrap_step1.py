import os

files = {
    "sentinel/db/schema.py": '''
# The absolute source of truth. Append-only design.
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY, uuid TEXT UNIQUE NOT NULL, username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','manager','pharmacist','cashier')),
  pin_hash BLOB NOT NULL, pin_salt BLOB NOT NULL, pin_iterations INTEGER NOT NULL DEFAULT 250000,
  pin_expires_at TEXT, pin_failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
  is_active INTEGER NOT NULL DEFAULT 1, must_change_pin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY, uuid TEXT UNIQUE NOT NULL, generic_molecule TEXT NOT NULL,
  brand TEXT NOT NULL, strength TEXT NOT NULL, form TEXT NOT NULL,
  regulatory_class TEXT NOT NULL CHECK(regulatory_class IN ('POM','OTC','OTHER')),
  is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(generic_molecule, brand, strength, form)
);

CREATE TABLE IF NOT EXISTS product_versions (
  id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id),
  version_label TEXT NOT NULL, units_per_strip INTEGER NOT NULL CHECK(units_per_strip > 0),
  strips_per_box INTEGER NOT NULL CHECK(strips_per_box > 0), units_per_box INTEGER NOT NULL,
  effective_date TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1, notes TEXT, created_at TEXT NOT NULL,
  UNIQUE(product_id, version_label)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_versions_current ON product_versions(product_id) WHERE is_current = 1;

CREATE TABLE IF NOT EXISTS batches (
  id INTEGER PRIMARY KEY, uuid TEXT UNIQUE NOT NULL, product_version_id INTEGER NOT NULL REFERENCES product_versions(id),
  batch_code TEXT NOT NULL, expiry_date TEXT NOT NULL, qty_atomic INTEGER NOT NULL DEFAULT 0,
  supplier TEXT, received_at TEXT NOT NULL, is_archived INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_batches_expiry ON batches(expiry_date) WHERE is_archived = 0;

CREATE TABLE IF NOT EXISTS stock_ledger (
  id INTEGER PRIMARY KEY, uuid TEXT UNIQUE NOT NULL, device_id TEXT NOT NULL,
  batch_id INTEGER REFERENCES batches(id), product_id INTEGER NOT NULL REFERENCES products(id),
  qty_delta_atomic INTEGER NOT NULL, cost_minor_per_unit INTEGER,
  movement_type TEXT NOT NULL CHECK(movement_type IN ('PURCHASE_IN','SALE_OUT','RETURN_IN','RETURN_OUT','STOCKTAKE_ADJ','BACK_ENTRY','ADJUSTMENT','DEBT_RESOLUTION')),
  ref_type TEXT NOT NULL, ref_id INTEGER NOT NULL, event_time TEXT NOT NULL, event_seq INTEGER NOT NULL,
  user_id INTEGER REFERENCES users(id), is_debt INTEGER NOT NULL DEFAULT 0,
  debt_authorized_by INTEGER REFERENCES users(id), notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_ledger_product ON stock_ledger(product_id, event_seq);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_seq ON stock_ledger(device_id, event_seq);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY, uuid TEXT UNIQUE NOT NULL, event_time TEXT NOT NULL, event_seq INTEGER NOT NULL,
  user_id INTEGER REFERENCES users(id), action TEXT NOT NULL, entity_type TEXT, entity_id INTEGER,
  detail_json TEXT, pin_gated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(event_time);
"""
''',

    "sentinel/db/manager.py": '''
import sqlite3
import os
from .schema import SCHEMA_DDL

class DatabaseManager:
    def __init__(self, db_path="sentinel.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._apply_pragmas()
        return self.conn

    def _apply_pragmas(self):
        c = self.conn.cursor()
        c.execute("PRAGMA journal_mode = WAL;")
        c.execute("PRAGMA synchronous = FULL;")
        c.execute("PRAGMA foreign_keys = ON;")
        c.execute("PRAGMA busy_timeout = 5000;")
        c.execute("PRAGMA wal_autocheckpoint = 1000;")
        c.execute("PRAGMA cache_size = -8000;")

    def initialize(self):
        if self.conn is None: self.connect()
        c = self.conn.cursor()
        c.executescript(SCHEMA_DDL)
        self.conn.commit()
        
    def get_next_event_seq(self, device_id: str) -> int:
        c = self.conn.cursor()
        c.execute("SELECT MAX(event_seq) FROM stock_ledger WHERE device_id = ?", (device_id,))
        res = c.fetchone()
        max_seq = res[0] if res else 0
        return (max_seq or 0) + 1
''',

    "sentinel/security/auth.py": '''
import hashlib
import os

def hash_pin(pin: str, salt: bytes = None, iterations: int = 250000) -> tuple:
    if salt is None:
        salt = os.urandom(32)
    pin_bytes = pin.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', pin_bytes, salt, iterations)
    return hashed, salt

def verify_pin(pin: str, hashed: bytes, salt: bytes, iterations: int = 250000) -> bool:
    check_hashed, _ = hash_pin(pin, salt, iterations)
    return hashlib.compare_digest(check_hashed, hashed)
''',

    "sentinel/security/crypto.py": '''
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
''',

    "tests/test_step1.py": '''
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
    print("\\n[SUCCESS] Step 1 Foundation verified.")
'''
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
