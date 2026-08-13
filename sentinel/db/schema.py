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
