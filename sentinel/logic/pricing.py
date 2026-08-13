def round_to_cash(pesewas: int, round_to: int) -> int:
    if round_to <= 1:
        return pesewas
    return (pesewas // round_to) * round_to


def calculate_wac(on_hand_atomic: int, old_wac_pesewas: int,
                  received_qty_atomic: int, received_cost_pesewas: int) -> int:
    on_hand = int(on_hand_atomic or 0)
    received_qty = int(received_qty_atomic or 0)
    received_cost = int(received_cost_pesewas or 0)
    old_wac = int(old_wac_pesewas) if old_wac_pesewas is not None else received_cost
    if on_hand <= 0:
        return received_cost
    if received_qty <= 0:
        return old_wac
    total_existing_value = on_hand * old_wac
    total_new_value = received_qty * received_cost
    total_qty = on_hand + received_qty
    return (total_existing_value + total_new_value) // total_qty


def calculate_tier_prices(wac_atomic_pesewas: int,
                          units_per_strip: int,
                          strips_per_box: int,
                          box_margin_pct: float = 0.15,
                          strip_breaking_fee_pct: float = 0.10,
                          unit_breaking_fee_pct: float = 0.10) -> dict:
    units_per_strip = max(int(units_per_strip or 1), 1)
    strips_per_box = max(int(strips_per_box or 1), 1)
    units_per_box = units_per_strip * strips_per_box

    box_cost = wac_atomic_pesewas * units_per_box
    box_price_raw = box_cost * (1 + box_margin_pct)
    box_final = round_to_cash(int(box_price_raw), 100)

    strip_price_raw = (box_final / strips_per_box) * (1 + strip_breaking_fee_pct)
    strip_final = round_to_cash(int(strip_price_raw), 50)

    unit_price_raw = (strip_final / units_per_strip) * (1 + unit_breaking_fee_pct)
    unit_final = round_to_cash(int(unit_price_raw), 10)

    return {
        "box": box_final,
        "strip": strip_final,
        "unit": unit_final,
        "atomic_cost": wac_atomic_pesewas,
    }
