import sys
import uuid
from PySide6.QtWidgets import QApplication
from sentinel.db.manager import DatabaseManager
from sentinel.ui.login import BrutalistLogin
from sentinel.ui.pos import BrutalistPOS
from sentinel.security.auth import hash_pin
from sentinel.logic.sessions import SessionManager

def bootstrap_db(db, device_id):
    """Ensures at least one owner exists."""
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        h, s = hash_pin("1234")
        db.conn.execute("""
            INSERT INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at)
            VALUES (?, 'admin', 'SYSTEM_ADMIN', 'owner', ?, ?, 'now')
        """, (str(uuid.uuid4()), h, s))
        db.conn.commit()

def run_app():
    app = QApplication(sys.argv)
    device_id = "DEV-001"
    
    db = DatabaseManager("sentinel.db")
    db.connect()
    db.initialize()
    bootstrap_db(db, device_id)

    main_win = None
    session_mgr = SessionManager(db, device_id)

    def on_login(user_id, user_name):
        nonlocal main_win
        login_win.close()
        
        # 1. OPEN A SESSION (Satisfies Foreign Key)
        # In a real app, we check if one is already open, but for now we create one.
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM pos_sessions WHERE status = 'OPEN' AND device_id = ?", (device_id,))
        res = cursor.fetchone()
        
        if res:
            session_id = res[0]
        else:
            session_id = session_mgr.open_session(user_id)
        
        # 2. Start POS with the active session_id
        main_win = BrutalistPOS(db, user_id, user_name, session_id)
        main_win.show()

    login_win = BrutalistLogin(db, on_login)
    login_win.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
