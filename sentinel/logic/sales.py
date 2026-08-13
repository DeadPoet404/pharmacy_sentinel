import uuid
from datetime import datetime
from sentinel.logic.inventory import InventoryController


class SalesController:
    def __init__(self, db_manager, device_id):
        self.db = db_manager
        self.inv = InventoryController(db_manager, device_id)
        self.device_id = device_id

    def commit_sale(self, cashier_id, session_id, items, total_ghs, method, tendered):
        cursor = self.db.conn.cursor()
        sale_uuid = str(uuid.uuid4())
        total_minor = int(round(float(total_ghs) * 100))
        tendered_minor = int(round(float(tendered) * 100))
        change_minor = tendered_minor - total_minor
        now = datetime.now().isoformat()

        cursor.execute(
            "SELECT MAX(event_seq) FROM sales WHERE device_id = ?",
            (self.device_id,),
        )
        res = cursor.fetchone()[0]
        event_seq = (res or 0) + 1

        try:
            cursor.execute(
                """
                INSERT INTO sales (uuid, device_id, pos_session_id, sale_time, event_seq,
                                 cashier_id, subtotal_minor, total_minor, amount_tendered_minor,
                                 change_minor, payment_method, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETE')
                """,
                (
                    sale_uuid,
                    self.device_id,
                    session_id,
                    now,
                    event_seq,
                    cashier_id,
                    total_minor,
                    total_minor,
                    tendered_minor,
                    change_minor,
                    method,
                ),
            )
            sale_id = cursor.lastrowid

            for item in items:
                prod_id = item["id"]
                qty_disp = int(item.get("qty", 1))
                qty_atomic = int(item.get("qty_atomic") or qty_disp)
                uom = item.get("uom", "UNIT")
                line_total_minor = int(round(float(item["price"]) * qty_disp * 100))

                allocations = self.inv.sell_fefo(prod_id, qty_atomic, sale_id, cashier_id)

                remaining_val = line_total_minor
                for i, alloc in enumerate(allocations):
                    if i == len(allocations) - 1:
                        part = remaining_val
                    elif qty_atomic:
                        part = int(round(line_total_minor * alloc["qty"] / qty_atomic))
                        remaining_val -= part
                    else:
                        part = 0
                    unit_price_minor = (part // alloc["qty"]) if alloc["qty"] else 0
                    cursor.execute(
                        """
                        INSERT INTO sale_items (
                            sale_id, product_id, product_version_id, batch_id,
                            uom, qty_atomic, unit_price_minor, line_total_minor
                        )
                        VALUES (
                            ?, ?,
                            COALESCE(
                                (SELECT id FROM product_versions WHERE product_id = ? AND is_current = 1),
                                (SELECT id FROM product_versions WHERE product_id = ? ORDER BY id DESC LIMIT 1)
                            ),
                            ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            sale_id,
                            prod_id,
                            prod_id,
                            prod_id,
                            alloc["batch_id"],
                            uom,
                            alloc["qty"],
                            unit_price_minor,
                            part,
                        ),
                    )

            self.db.conn.commit()
            return True
        except Exception as e:
            self.db.conn.rollback()
            print(f"CRITICAL_SALE_FAILURE: {e}")
            return False
import uuid
from datetime import datetime
from sentinel.logic.inventory import InventoryController


class SalesController:
    def __init__(self, db_manager, device_id):
        self.db = db_manager
        self.inv = InventoryController(db_manager, device_id)
        self.device_id = device_id

    def commit_sale(self, cashier_id, session_id, items, total_ghs, method, tendered):
        cursor = self.db.conn.cursor()
        sale_uuid = str(uuid.uuid4())
        total_minor = int(round(float(total_ghs) * 100))
        tendered_minor = int(round(float(tendered) * 100))
        change_minor = tendered_minor - total_minor
        now = datetime.now().isoformat()

        cursor.execute(
            "SELECT MAX(event_seq) FROM sales WHERE device_id = ?",
            (self.device_id,),
        )
        res = cursor.fetchone()[0]
        event_seq = (res or 0) + 1

        try:
            cursor.execute(
                """
                INSERT INTO sales (uuid, device_id, pos_session_id, sale_time, event_seq,
                                 cashier_id, subtotal_minor, total_minor, amount_tendered_minor,
                                 change_minor, payment_method, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETE')
                """,
                (
                    sale_uuid,
                    self.device_id,
                    session_id,
                    now,
                    event_seq,
                    cashier_id,
                    total_minor,
                    total_minor,
                    tendered_minor,
                    change_minor,
                    method,
                ),
            )
            sale_id = cursor.lastrowid

            for item in items:
                prod_id = item["id"]
                qty_disp = int(item.get("qty", 1))
                qty_atomic = int(item.get("qty_atomic") or qty_disp)
                uom = item.get("uom", "UNIT")
                line_total_minor = int(round(float(item["price"]) * qty_disp * 100))

                allocations = self.inv.sell_fefo(prod_id, qty_atomic, sale_id, cashier_id)

                remaining_val = line_total_minor
                for i, alloc in enumerate(allocations):
                    if i == len(allocations) - 1:
                        part = remaining_val
                    elif qty_atomic:
                        part = int(round(line_total_minor * alloc["qty"] / qty_atomic))
                        remaining_val -= part
                    else:
                        part = 0
                    unit_price_minor = (part // alloc["qty"]) if alloc["qty"] else 0
                    cursor.execute(
                        """
                        INSERT INTO sale_items (
                            sale_id, product_id, product_version_id, batch_id,
                            uom, qty_atomic, unit_price_minor, line_total_minor
                        )
                        VALUES (
                            ?, ?,
                            COALESCE(
                                (SELECT id FROM product_versions WHERE product_id = ? AND is_current = 1),
                                (SELECT id FROM product_versions WHERE product_id = ? ORDER BY id DESC LIMIT 1)
                            ),
                            ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            sale_id,
                            prod_id,
                            prod_id,
                            prod_id,
                            alloc["batch_id"],
                            uom,
                            alloc["qty"],
                            unit_price_minor,
                            part,
                        ),
                    )

            self.db.conn.commit()
            return True
        except Exception as e:
            self.db.conn.rollback()
            print(f"CRITICAL_SALE_FAILURE: {e}")
            return False
