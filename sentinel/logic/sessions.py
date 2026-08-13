from datetime import datetime

class SessionManager:
    def __init__(self, db_manager, device_id):
        self.db = db_manager
        self.device_id = device_id

    def open_session(self, user_id):
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO pos_sessions (uuid, device_id, opened_by, opened_at, status)
            VALUES (lower(hex(randomblob(16))), ?, ?, ?, 'OPEN')
        """, (self.device_id, user_id, datetime.now().isoformat()))
        self.db.conn.commit()
        return cursor.lastrowid

    def can_close_session(self, session_id):
        """The Z-Gate: Check if a verified Z-Report/Backup exists."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT backup_verified FROM z_reports WHERE pos_session_id = ?", 
            (session_id,)
        )
        res = cursor.fetchone()
        return res is not None and res['backup_verified'] == 1

    def close_session(self, session_id, user_id):
        if not self.can_close_session(session_id):
            raise PermissionError("Z-Report Gate: Verified USB backup required before closing.")
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            UPDATE pos_sessions 
            SET status = 'CLOSED', closed_by = ?, closed_at = ?
            WHERE id = ?
        """, (user_id, datetime.now().isoformat(), session_id))
        self.db.conn.commit()
