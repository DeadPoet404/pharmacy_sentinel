import sys
import os
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sentinel.db.manager import DatabaseManager
from sentinel.logic.sessions import SessionManager
from sentinel.logic.backup import BackupEngine
from sentinel.security.crypto import generate_master_key
from sentinel.security.auth import hash_pin

def test_z_report_gate():
    db_path = "gov_test.db"
    if os.path.exists(db_path): os.remove(db_path)
    
    db = DatabaseManager(db_path)
    db.connect()
    db.initialize()
    
    master_key = generate_master_key()
    device_id = "DEV-001"
    sess_mgr = SessionManager(db, device_id)
    backup_eng = BackupEngine(db_path, master_key)
    
    # FIX: Insert a dummy user to satisfy Foreign Key constraint
    print("[0/4] Setting up dummy owner...")
    h, s = hash_pin("123456")
    db.conn.execute("""
        INSERT INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at)
        VALUES (?, 'admin', 'Admin User', 'owner', ?, ?, 'now')
    """, (str(uuid.uuid4()), h, s))
    db.conn.commit()
    user_id = 1
    
    # 1. Open Session
    sid = sess_mgr.open_session(user_id=user_id)
    print(f"[1/4] Session {sid} opened.")
    
    # 2. Try to close without Z-Report/Backup
    print("[2/4] Testing Z-Gate (Should block close)...")
    try:
        sess_mgr.close_session(sid, user_id=user_id)
        assert False, "Gate failed to block closure"
    except PermissionError as e:
        print(f"      -> Gate Blocked Close: {e}")

    # 3. Perform the Backup Ceremony
    print("[3/4] Performing USB Backup Ceremony...")
    db_hash, backup_path = backup_eng.create_encrypted_backup("mock_usb_drive")
    is_valid = backup_eng.verify_backup(backup_path, db_hash)
    assert is_valid, "Backup verification failed"
    
    # Record verified Z-Report in DB
    db.conn.execute("""
        INSERT INTO z_reports (uuid, pos_session_id, generated_by, generated_at, report_json, backup_verified)
        VALUES (?, ?, ?, 'now', '{}', 1)
    """, (str(uuid.uuid4()), sid, user_id))
    db.conn.commit()
    print("      -> Backup verified and Z-Report recorded.")

    # 4. Try to close again
    print("[4/4] Testing Z-Gate (Should allow close)...")
    sess_mgr.close_session(sid, user_id=user_id)
    
    cursor = db.conn.cursor()
    cursor.execute("SELECT status FROM pos_sessions WHERE id = ?", (sid,))
    assert cursor.fetchone()[0] == 'CLOSED'
    print("      -> Session successfully closed.")

    db.conn.close()
    # Cleanup
    for f in [db_path, f"{db_path}-wal", f"{db_path}-shm", "mock_usb_drive.sbk"]:
        if os.path.exists(f): os.remove(f)
    print("\n[SUCCESS] Governance Gate is operational.")

if __name__ == "__main__":
    test_z_report_gate()
