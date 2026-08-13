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
