import uuid
from datetime import datetime
from sentinel.logic.inventory import InventoryController

class SalesController:
    def __init__(self, db_manager, device_id):
        self.db = db_manager
        self.inv = InventoryController(db_manager, device_id)
        self.device_id = device_id

    def commit_sale(self, cashier_id, session_id, items, total_ghs, method, tendered):
        """
        Records the sale and deducts inventory via FEFO.
        """
        cursor = self.db.conn.cursor()
        sale_uuid = str(uuid.uuid4())
        total_minor = int(total_ghs * 100)
        tendered_minor = int(tendered * 100)
        change_minor = tendered_minor - total_minor
        now = datetime.now().isoformat()
        
        # Get next event seq
        cursor.execute("SELECT MAX(event_seq) FROM sales WHERE device_id = ?", (self.device_id,))
        res = cursor.fetchone()[0]
        event_seq = (res or 0) + 1

        try:
            # 1. Record Sale Header
            cursor.execute("""
                INSERT INTO sales (uuid, device_id, pos_session_id, sale_time, event_seq, 
                                 cashier_id, subtotal_minor, total_minor, amount_tendered_minor, 
                                 change_minor, payment_method, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETE')
            """, (sale_uuid, self.device_id, session_id, now, event_seq, 
                  cashier_id, total_minor, total_minor, tendered_minor, 
                  change_minor, method))
            
            sale_id = cursor.lastrowid

            # 2. Process Items (FEFO Allocation)
            for item in items:
                prod_id = item['id']
                qty_atomic = item['qty']
                unit_price_minor = int(item['price'] * 100)
                
                # Deduct from Inventory (This handles FEFO batch splitting)
                allocations = self.inv.sell_fefo(prod_id, qty_atomic, sale_id, cashier_id)
                
                # Record Sale Items
                for alloc in allocations:
                    cursor.execute("""
                        INSERT INTO sale_items (sale_id, product_id, product_version_id, batch_id, 
                                              uom, qty_atomic, unit_price_minor, line_total_minor)
                        VALUES (?, ?, (SELECT id FROM product_versions WHERE product_id = ? AND is_current=1), 
                                ?, 'UNIT', ?, ?, ?)
                    """, (sale_id, prod_id, prod_id, alloc['batch_id'], alloc['qty'], 
                          unit_price_minor, alloc['qty'] * unit_price_minor))

            self.db.conn.commit()
            return True
        except Exception as e:
            self.db.conn.rollback()
            print(f"CRITICAL_SALE_FAILURE: {e}")
            return False
