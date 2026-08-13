import sys
import uuid
from PySide6.QtWidgets import QApplication
from sentinel.db.manager import DatabaseManager
from sentinel.ui.login import BrutalistLogin
from sentinel.ui.pos import BrutalistPOS
from sentinel.security.auth import hash_pin

def bootstrap_db(db):
    """Ensures at least one owner exists so the system can be accessed."""
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("First run detected. Creating industrial admin (PIN: 1234)...")
        h, s = hash_pin("1234")
        db.conn.execute("""
            INSERT INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at)
            VALUES (?, 'admin', 'SYSTEM_ADMIN', 'owner', ?, ?, 'now')
        """, (str(uuid.uuid4()), h, s))
        db.conn.commit()

def run_app():
    app = QApplication(sys.argv)
    
    # 1. Initialize Database
    db = DatabaseManager("sentinel.db")
    db.connect()
    db.initialize()
    
    # 2. Setup Default User
    bootstrap_db(db)

    main_win = None

    # 3. Define Logic to switch windows
    def on_login(user_id, user_name):
        nonlocal main_win
        login_win.close()
        # Create and show the new Industrial POS
        main_win = BrutalistPOS(db, user_id, user_name)
        main_win.show()

    # 4. Start with Brutalist Login
    login_win = BrutalistLogin(db, on_login)
    login_win.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    run_app()
