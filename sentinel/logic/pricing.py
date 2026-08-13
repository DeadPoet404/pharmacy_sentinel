import math

def round_to_cash(pesewas: int, round_to: int) -> int:
    """
    Rounds pesewas down to the nearest denomination (Floor).
    In Ghana retail, rounding to the nearest coin often favors 
    the customer to ensure exact change availability.
    """
    if round_to <= 1:
        return pesewas
    # Use floor to match spec vector: 55p -> 50p, 506p -> 500p
    return (pesewas // round_to) * round_to

def calculate_wac(on_hand_atomic: int, old_wac_pesewas: int, 
                  received_qty_atomic: int, received_cost_pesewas: int) -> int:
    if on_hand_atomic <= 0:
        return received_cost_pesewas
    
    total_existing_value = on_hand_atomic * old_wac_pesewas
    total_new_value = received_qty_atomic * received_cost_pesewas
    total_qty = on_hand_atomic + received_qty_atomic
    
    return (total_existing_value + total_new_value) // total_qty

def calculate_tier_prices(wac_atomic_pesewas: int, 
                          units_per_strip: int, 
                          strips_per_box: int,
                          box_margin_pct: float = 0.15,
                          strip_breaking_fee_pct: float = 0.10,
                          unit_breaking_fee_pct: float = 0.10) -> dict:
    units_per_box = units_per_strip * strips_per_box
    
    # 1. BOX: WAC * units * 1.15
    box_cost = wac_atomic_pesewas * units_per_box
    box_price_raw = box_cost * (1 + box_margin_pct)
    box_final = round_to_cash(int(box_price_raw), 100)
    
    # 2. STRIP: (BoxPrice / strips) * 1.10
    strip_price_raw = (box_final / strips_per_box) * (1 + strip_breaking_fee_pct)
    strip_final = round_to_cash(int(strip_price_raw), 50)
    
    # 3. UNIT: (StripPrice / units) * 1.10
    unit_price_raw = (strip_final / units_per_strip) * (1 + unit_breaking_fee_pct)
    unit_final = round_to_cash(int(unit_price_raw), 10)
    
    return {
        "box": box_final,
        "strip": strip_final,
        "unit": unit_final,
        "atomic_cost": wac_atomic_pesewas
    }
