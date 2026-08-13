import uuid
from datetime import datetime


class InventoryController:
    def __init__(self, db_manager, device_id):
        self.db = db_manager
        self.device_id = device_id

    def get_on_hand(self, product_id: int) -> int:
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT SUM(qty_delta_atomic) FROM stock_ledger WHERE product_id = ?",
            (product_id,),
        )
        res = cursor.fetchone()[0]
        return res if res is not None else 0

    def last_wac(self, product_id: int):
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT cost_minor_per_unit FROM stock_ledger "
            "WHERE product_id = ? AND cost_minor_per_unit IS NOT NULL "
            "ORDER BY event_seq DESC LIMIT 1",
            (product_id,),
        )
        row = cursor.fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def get_batch_balances(self, product_id: int):
        """Active batches, earliest expiry first (FEFO). Always returns dicts."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT b.id, b.batch_code, b.expiry_date, SUM(l.qty_delta_atomic) as balance
            FROM batches b
            JOIN stock_ledger l ON b.id = l.batch_id
            WHERE b.product_version_id IN (
                SELECT id FROM product_versions WHERE product_id = ?
            )
            AND b.is_archived = 0
            GROUP BY b.id
            HAVING balance > 0
            ORDER BY b.expiry_date ASC
            """,
            (product_id,),
        )
        out = []
        for r in cursor.fetchall():
            out.append(
                {
                    "id": r[0],
                    "batch_code": r[1],
                    "expiry_date": r[2],
                    "balance": r[3],
                }
            )
        return out

    def record_movement(
        self,
        product_id,
        qty_delta,
        movement_type,
        ref_type,
        ref_id,
        batch_id=None,
        cost_per_unit=None,
        user_id=None,
        is_debt=0,
        debt_auth_by=None,
        commit=True,
    ):
        event_seq = self.db.get_next_event_seq(self.device_id)
        row_uuid = str(uuid.uuid4())
        now = datetime.now().isoformat()

        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            INSERT INTO stock_ledger (
                uuid, device_id, batch_id, product_id, qty_delta_atomic,
                cost_minor_per_unit, movement_type, ref_type, ref_id,
                event_time, event_seq, user_id, is_debt, debt_authorized_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_uuid,
                self.device_id,
                batch_id,
                product_id,
                qty_delta,
                cost_per_unit,
                movement_type,
                ref_type,
                ref_id,
                now,
                event_seq,
                user_id,
                is_debt,
                debt_auth_by,
            ),
        )

        if batch_id:
            cursor.execute(
                "UPDATE batches SET qty_atomic = qty_atomic + ? WHERE id = ?",
                (qty_delta, batch_id),
            )

        if commit:
            self.db.conn.commit()
        return row_uuid

    def sell_fefo(self, product_id, total_qty_needed, ref_id, user_id):
        batches = self.get_batch_balances(product_id)
        remaining = total_qty_needed
        allocations = []
        wac = self.last_wac(product_id)

        for b in batches:
            if remaining <= 0:
                break
            take = min(remaining, b["balance"])
            self.record_movement(
                product_id=product_id,
                batch_id=b["id"],
                qty_delta=-take,
                movement_type="SALE_OUT",
                ref_type="sale",
                ref_id=ref_id,
                user_id=user_id,
                cost_per_unit=wac,
                commit=False,
            )
            allocations.append({"batch_id": b["id"], "qty": take})
            remaining -= take

        if remaining > 0:
            self.record_movement(
                product_id=product_id,
                batch_id=None,
                qty_delta=-remaining,
                movement_type="SALE_OUT",
                ref_type="sale",
                ref_id=ref_id,
                user_id=user_id,
                is_debt=1,
                cost_per_unit=wac,
                commit=False,
            )
            allocations.append({"batch_id": None, "qty": remaining, "is_debt": True})

        return allocations
