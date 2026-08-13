import sys
import os
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sentinel.db.manager import DatabaseManager
from sentinel.logic.inventory import InventoryController

def test_inventory_flow():
    db = DatabaseManager("test_inv.db")
    db.connect()
    db.initialize()
    ctrl = InventoryController(db, "DEV-001")
    
    # 1. Setup Product & Batches
    cur = db.conn.cursor()
    cur.execute("INSERT INTO products (uuid, generic_molecule, brand, strength, form, regulatory_class, created_at, updated_at) VALUES (?, 'Paracetamol', 'Adcock', '500mg', 'Tab', 'OTC', 'now', 'now')", (str(uuid.uuid4()),))
    prod_id = cur.lastrowid
    
    cur.execute("INSERT INTO product_versions (product_id, version_label, units_per_strip, strips_per_box, units_per_box, effective_date, created_at) VALUES (?, 'V1', 10, 10, 100, 'now', 'now')", (prod_id,))
    ver_id = cur.lastrowid
    
    # Batch A: Expiring SOON (10 units)
    cur.execute("INSERT INTO batches (uuid, product_version_id, batch_code, expiry_date, received_at) VALUES (?, ?, 'A', '2025-01-01', 'now')", (str(uuid.uuid4()), ver_id))
    batch_a = cur.lastrowid
    
    # Batch B: Expiring LATER (50 units)
    cur.execute("INSERT INTO batches (uuid, product_version_id, batch_code, expiry_date, received_at) VALUES (?, ?, 'B', '2025-12-31', 'now')", (str(uuid.uuid4()), ver_id))
    batch_b = cur.lastrowid
    
    # 2. Add Initial Stock via Ledger
    ctrl.record_movement(prod_id, 10, 'PURCHASE_IN', 'po', 1, batch_id=batch_a)
    ctrl.record_movement(prod_id, 50, 'PURCHASE_IN', 'po', 1, batch_id=batch_b)
    
    assert ctrl.get_on_hand(prod_id) == 60
    print("[1/3] Initial Stock Setup OK.")

    # 3. Perform FEFO Sale (Sell 15)
    # Should take 10 from A (emptying it) and 5 from B
    print("[2/3] Testing FEFO Split (Sell 15)...")
    allocs = ctrl.sell_fefo(prod_id, 15, ref_id=101, user_id=1)
    
    assert len(allocs) == 2
    assert allocs[0]['batch_id'] == batch_a and allocs[0]['qty'] == 10
    assert allocs[1]['batch_id'] == batch_b and allocs[1]['qty'] == 5
    assert ctrl.get_on_hand(prod_id) == 45
    print("      -> FEFO Split OK.")

    # 4. Perform Debt Sale (Sell 50)
    # Should take remaining 45 from B and 5 as DEBT
    print("[3/3] Testing Stock Debt (Sell 50)...")
    allocs_debt = ctrl.sell_fefo(prod_id, 50, ref_id=102, user_id=1)
    
    assert ctrl.get_on_hand(prod_id) == -5
    debt_row = next(a for a in allocs_debt if a.get('is_debt'))
    assert debt_row['qty'] == 5
    print("      -> Stock Debt OK.")

    db.conn.close()
    os.remove("test_inv.db")
    print("\n[SUCCESS] Inventory Engine handles FEFO and Debt correctly.")

if __name__ == "__main__":
    test_inventory_flow()
