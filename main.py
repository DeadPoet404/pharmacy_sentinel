import sys
import uuid
from PySide6.QtWidgets import QApplication
from sentinel.db.manager import DatabaseManager
from sentinel.ui.login import SaaSLogin
from sentinel.ui.pos import BrutalistPOS
from sentinel.security.auth import hash_pin
from sentinel.logic.sessions import SessionManager

def bootstrap_db(db):
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        h, s = hash_pin("1234")
        db.conn.execute("INSERT INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at) VALUES (?, 'admin', 'ADMIN', 'owner', ?, ?, 'now')", (str(uuid.uuid4()), h, s))
        db.conn.commit()

def run_app():
    app = QApplication(sys.argv)
    db = DatabaseManager("sentinel.db"); db.connect(); db.initialize(); bootstrap_db(db)
    session_mgr = SessionManager(db, "DEV-001")
    main_win = None

    def on_login(user_id, user_name):
        nonlocal main_win; login_win.close()
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM pos_sessions WHERE status = 'OPEN'")
        res = cursor.fetchone()
        s_id = res[0] if res else session_mgr.open_session(user_id)
        main_win = BrutalistPOS(db, user_id, user_name, s_id)
        main_win.show()

    login_win = SaaSLogin(db, on_login); login_win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
