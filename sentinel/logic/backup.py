import os
import sqlite3
import hashlib
from sentinel.security.crypto import encrypt_backup, decrypt_backup

class BackupEngine:
    def __init__(self, db_path, master_key):
        self.db_path = db_path
        self.master_key = master_key

    def _get_bytes_hash(self, data_bytes):
        return hashlib.sha256(data_bytes).hexdigest()

    def create_encrypted_backup(self, destination_path):
        """
        1. Uses SQLite Backup API to create a consistent snapshot in memory.
        2. Hashes that consistent snapshot.
        3. Encrypts and writes to disk.
        """
        # Connect to live DB and a destination 'in-memory' or temp file
        src = sqlite3.connect(self.db_path)
        
        # We backup to a temporary file to ensure we don't blow up RAM 
        # for large databases, then read it to encrypt.
        temp_snapshot = destination_path + ".tmp"
        dst = sqlite3.connect(temp_snapshot)
        
        with dst:
            src.backup(dst)
        dst.close()
        src.close()

        # Read the consistent snapshot
        with open(temp_snapshot, "rb") as f:
            snapshot_data = f.read()
        
        # Calculate hash of the consistent snapshot
        snapshot_hash = self._get_bytes_hash(snapshot_data)
        
        # Encrypt the consistent snapshot
        encrypted_data = encrypt_backup(snapshot_data, self.master_key)
        
        final_path = destination_path + ".sbk"
        with open(final_path, "wb") as f:
            f.write(encrypted_data)
        
        # Clean up temp
        os.remove(temp_snapshot)
        
        return snapshot_hash, final_path

    def verify_backup(self, backup_file, expected_hash):
        """Decrypts and checks if the hash matches the snapshot hash."""
        with open(backup_file, "rb") as f:
            decrypted_data = decrypt_backup(f.read(), self.master_key)
        
        actual_hash = self._get_bytes_hash(decrypted_data)
        return actual_hash == expected_hash
