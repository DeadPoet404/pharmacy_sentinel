import uuid
import json
from datetime import datetime

class SessionManager:
    def __init__(self, db_manager, device_id):
        self.db = db_manager
        self.device_id = device_id

    def open_session(self, user_id):
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO pos_sessions (uuid, device_id, opened_by, opened_at, status)
            VALUES (?, ?, ?, ?, 'OPEN')
        """, (str(uuid.uuid4()), self.device_id, user_id, datetime.now().isoformat()))
        self.db.conn.commit()
        return cursor.lastrowid

    def generate_z_report(self, session_id, user_id, backup_file, backup_hash):
        """
        Creates the Z-Report record. 
        backup_verified=1 is what unlocks the session close.
        """
        cursor = self.db.conn.cursor()
        
        # 1. Gather session stats for the JSON report
        cursor.execute("SELECT COUNT(*) as count, SUM(total_minor) as total FROM sales WHERE pos_session_id = ?", (session_id,))
        stats = cursor.fetchone()
        report_data = {
            "sales_count": stats[0],
            "total_ghs": (stats[1] or 0) / 100,
            "timestamp": datetime.now().isoformat()
        }

        # 2. Record Z-Report
        cursor.execute("""
            INSERT INTO z_reports (uuid, pos_session_id, generated_by, generated_at, report_json, 
                                 backup_verified, backup_file, backup_sha256)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """, (str(uuid.uuid4()), session_id, user_id, datetime.now().isoformat(), 
              json.dumps(report_data), backup_file, backup_hash))
        
        z_id = cursor.lastrowid
        
        # 3. Update session with the Z-Report link
        cursor.execute("UPDATE pos_sessions SET z_report_id = ? WHERE id = ?", (z_id, session_id))
        self.db.conn.commit()
        return z_id

    def close_session(self, session_id, user_id):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT z_report_id FROM pos_sessions WHERE id = ?", (session_id,))
        if not cursor.fetchone()[0]:
            raise PermissionError("Z_REPORT_GATE: BACKUP_REQUIRED_BEFORE_CLOSURE")
        
        cursor.execute("""
            UPDATE pos_sessions 
            SET status = 'CLOSED', closed_by = ?, closed_at = ?
            WHERE id = ?
        """, (user_id, datetime.now().isoformat(), session_id))
        self.db.conn.commit()
