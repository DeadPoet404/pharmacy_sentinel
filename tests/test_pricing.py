import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sentinel.logic.pricing import calculate_wac, calculate_tier_prices

def test_wac_standard():
    print("[1/3] Testing Standard WAC...")
    new_wac = calculate_wac(100, 40, 100, 50)
    assert new_wac == 45
    print("      -> Standard WAC OK.")

def test_wac_debt_reset():
    print("[2/3] Testing WAC Debt Reset...")
    new_wac = calculate_wac(-50, 40, 200, 50)
    assert new_wac == 50
    print("      -> WAC Debt Reset OK.")

def test_tier_pricing_vector():
    print("[3/3] Testing Tier Pricing Vector (GHS)...")
    prices = calculate_tier_prices(
        wac_atomic_pesewas=40,
        units_per_strip=10,
        strips_per_box=10
    )
    
    # Spec §14.1 Validation:
    # Box: 4600
    # Strip: 500  (460/strip * 1.1 = 506 -> floor to 50)
    # Unit: 50   (50/unit * 1.1 = 55 -> floor to 10)
    
    assert prices['box'] == 4600, f"Box fail: {prices['box']}"
    assert prices['strip'] == 500, f"Strip fail: {prices['strip']}"
    assert prices['unit'] == 50, f"Unit fail: {prices['unit']}"
    print("      -> Tier Pricing Vector OK.")

if __name__ == "__main__":
    test_wac_standard()
    test_wac_debt_reset()
    test_tier_pricing_vector()
    print("\n[SUCCESS] Pricing Engine matches Spec Vector.")
