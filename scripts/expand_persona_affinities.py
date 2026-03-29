"""Expand persona category affinities to cover 18 B2C categories.

Each persona gets affinities based on their archetype's behavioral profile.
Existing affinities are preserved; new ones are added with appropriate
interest levels and Indian brand preferences.

Run once: python scripts/expand_persona_affinities.py
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "personas"

# New affinities to add per archetype.
# Format: category -> (interest_level, preferred_brands, purchase_frequency)
# Only adds categories the persona doesn't already have.

ARCHETYPE_EXPANSIONS: dict[str, dict[str, tuple[float, list[str], str]]] = {
    "aspirational_buyer": {
        "automobile": (0.6, ["Hyundai", "Kia", "Tata Nexon"], "rarely"),
        "two_wheeler": (0.4, ["Ather", "Ola Electric"], "rarely"),
        "home_services": (0.5, ["Urban Company"], "monthly"),
        "fintech": (0.7, ["CRED", "PhonePe", "Groww"], "weekly"),
        "edtech": (0.3, ["Skillshare", "Coursera"], "quarterly"),
        "health_and_wellness": (0.6, ["Cult.fit", "Nykaa Wellness"], "monthly"),
        "travel": (0.7, ["MakeMyTrip", "Airbnb"], "quarterly"),
        "telecom": (0.4, ["Jio", "Airtel"], "monthly"),
        "jewelry_and_luxury": (0.7, ["Tanishq", "CaratLane"], "quarterly"),
        "baby_and_kids": (0.2, ["FirstCry"], "rarely"),
        "quick_commerce": (0.6, ["Zepto", "Blinkit"], "weekly"),
        "food_delivery": (0.6, ["Zomato", "Swiggy"], "weekly"),
        "personal_care": (0.7, ["Bath & Body Works", "Forest Essentials"], "monthly"),
    },
    "brand_loyalist": {
        "automobile": (0.5, ["Maruti", "Toyota"], "rarely"),
        "two_wheeler": (0.3, ["Honda", "Hero"], "rarely"),
        "home_services": (0.4, ["Urban Company"], "quarterly"),
        "fintech": (0.5, ["Paytm", "Google Pay"], "weekly"),
        "edtech": (0.2, ["Byju's"], "rarely"),
        "health_and_wellness": (0.5, ["Himalaya", "Dabur"], "monthly"),
        "travel": (0.4, ["IRCTC", "MakeMyTrip"], "quarterly"),
        "telecom": (0.6, ["Airtel", "Jio"], "monthly"),
        "jewelry_and_luxury": (0.5, ["Tanishq", "Malabar Gold"], "quarterly"),
        "baby_and_kids": (0.4, ["Johnson & Johnson", "FirstCry"], "monthly"),
        "quick_commerce": (0.5, ["BigBasket", "Blinkit"], "weekly"),
        "food_delivery": (0.5, ["Swiggy", "Zomato"], "weekly"),
        "personal_care": (0.6, ["Dove", "Nivea", "Colgate"], "monthly"),
        "food_and_beverage": (0.5, ["Amul", "Cadbury", "Haldiram"], "weekly"),
        "electronics": (0.4, ["Samsung", "LG"], "quarterly"),
    },
    "impulse_buyer": {
        "automobile": (0.4, ["Tata Punch", "Hyundai i20"], "rarely"),
        "two_wheeler": (0.5, ["Royal Enfield", "Ather"], "rarely"),
        "home_services": (0.3, ["Urban Company"], "quarterly"),
        "fintech": (0.6, ["CRED", "Slice", "PhonePe"], "weekly"),
        "edtech": (0.2, ["Unacademy"], "rarely"),
        "health_and_wellness": (0.4, ["HealthifyMe", "Cult.fit"], "monthly"),
        "travel": (0.6, ["Cleartrip", "ixigo", "Yatra"], "quarterly"),
        "telecom": (0.3, ["Jio"], "monthly"),
        "jewelry_and_luxury": (0.5, ["CaratLane", "BlueStone"], "quarterly"),
        "baby_and_kids": (0.2, ["FirstCry"], "rarely"),
        "quick_commerce": (0.7, ["Zepto", "Blinkit", "Swiggy Instamart"], "weekly"),
        "food_delivery": (0.7, ["Zomato", "Swiggy"], "weekly"),
        "personal_care": (0.5, ["Beardo", "Man Matters", "Plum"], "monthly"),
        "grocery_and_household": (0.4, ["D-Mart", "BigBasket"], "weekly"),
    },
    "pragmatist": {
        "automobile": (0.6, ["Maruti", "Tata", "Honda"], "rarely"),
        "two_wheeler": (0.5, ["Honda Activa", "TVS Jupiter"], "rarely"),
        "home_services": (0.5, ["Urban Company", "Housejoy"], "quarterly"),
        "fintech": (0.6, ["Google Pay", "PhonePe", "Zerodha"], "weekly"),
        "edtech": (0.4, ["Coursera", "NPTEL"], "quarterly"),
        "health_and_wellness": (0.6, ["Pharmeasy", "1mg", "Himalaya"], "monthly"),
        "travel": (0.4, ["IRCTC", "RedBus"], "quarterly"),
        "telecom": (0.5, ["Airtel", "Jio"], "monthly"),
        "jewelry_and_luxury": (0.3, ["Tanishq"], "rarely"),
        "baby_and_kids": (0.4, ["FirstCry", "Pampers"], "monthly"),
        "quick_commerce": (0.5, ["Blinkit", "BigBasket"], "weekly"),
        "food_delivery": (0.4, ["Swiggy", "Zomato"], "weekly"),
        "personal_care": (0.5, ["Nivea", "Colgate", "Dove"], "monthly"),
        "fashion": (0.3, ["Decathlon", "Westside"], "quarterly"),
        "food_and_beverage": (0.5, ["Amul", "Tata Tea", "Britannia"], "weekly"),
    },
    "price_anchor": {
        "automobile": (0.3, ["Maruti Alto", "Tata Nano"], "rarely"),
        "two_wheeler": (0.5, ["Hero Splendor", "Honda Shine"], "rarely"),
        "home_services": (0.3, ["local service"], "rarely"),
        "fintech": (0.4, ["Google Pay", "PhonePe"], "weekly"),
        "edtech": (0.2, ["YouTube free courses"], "rarely"),
        "health_and_wellness": (0.4, ["generic pharmacy", "Patanjali"], "monthly"),
        "travel": (0.3, ["IRCTC", "RedBus"], "quarterly"),
        "telecom": (0.7, ["Jio", "BSNL"], "monthly"),
        "jewelry_and_luxury": (0.2, ["local jeweller"], "rarely"),
        "baby_and_kids": (0.5, ["local brands", "FirstCry sale"], "monthly"),
        "quick_commerce": (0.4, ["BigBasket", "D-Mart Ready"], "weekly"),
        "food_delivery": (0.3, ["Swiggy", "Zomato"], "rarely"),
        "personal_care": (0.6, ["Medimix", "Colgate", "Clinic Plus"], "monthly"),
        "fashion": (0.3, ["V-Mart", "Reliance Trends"], "quarterly"),
        "electronics": (0.4, ["Xiaomi", "Realme"], "quarterly"),
        "food_and_beverage": (0.6, ["Amul", "Parle", "local brands"], "weekly"),
    },
    "researcher": {
        "automobile": (0.6, ["Toyota", "Honda", "Hyundai"], "rarely"),
        "two_wheeler": (0.4, ["Ather", "Bajaj"], "rarely"),
        "home_services": (0.4, ["Urban Company"], "quarterly"),
        "fintech": (0.7, ["Zerodha", "Groww", "CRED"], "weekly"),
        "edtech": (0.7, ["Coursera", "NPTEL", "MIT OCW"], "monthly"),
        "health_and_wellness": (0.6, ["1mg", "Pharmeasy"], "monthly"),
        "travel": (0.5, ["MakeMyTrip", "Booking.com"], "quarterly"),
        "telecom": (0.5, ["Airtel", "Jio"], "monthly"),
        "jewelry_and_luxury": (0.3, ["Tanishq"], "rarely"),
        "baby_and_kids": (0.3, ["FirstCry"], "rarely"),
        "quick_commerce": (0.5, ["Blinkit", "Zepto"], "weekly"),
        "food_delivery": (0.4, ["Zomato", "Swiggy"], "weekly"),
        "personal_care": (0.5, ["Cetaphil", "The Ordinary", "CeraVe"], "monthly"),
        "fashion": (0.4, ["Uniqlo", "Decathlon"], "quarterly"),
        "food_and_beverage": (0.5, ["Amul", "organic brands"], "weekly"),
    },
    "skeptic": {
        "automobile": (0.4, ["Maruti", "Tata"], "rarely"),
        "two_wheeler": (0.3, ["Honda", "TVS"], "rarely"),
        "home_services": (0.3, ["Word of mouth only"], "rarely"),
        "fintech": (0.4, ["Google Pay"], "weekly"),
        "edtech": (0.2, ["free resources only"], "rarely"),
        "health_and_wellness": (0.5, ["Himalaya", "generic pharmacy"], "monthly"),
        "travel": (0.3, ["IRCTC"], "quarterly"),
        "telecom": (0.5, ["Airtel", "Jio"], "monthly"),
        "jewelry_and_luxury": (0.2, ["family jeweller"], "rarely"),
        "baby_and_kids": (0.3, ["Johnson & Johnson"], "rarely"),
        "quick_commerce": (0.4, ["BigBasket"], "weekly"),
        "food_delivery": (0.3, ["Swiggy", "Zomato"], "rarely"),
        "personal_care": (0.5, ["Medimix", "Pears", "Hamam"], "monthly"),
        "fashion": (0.3, ["local brands", "Westside"], "quarterly"),
        "food_and_beverage": (0.6, ["Amul", "Tata", "local brands"], "weekly"),
    },
    "trend_follower": {
        "automobile": (0.5, ["Tata Nexon EV", "Kia Seltos"], "rarely"),
        "two_wheeler": (0.6, ["Ather 450X", "Ola S1 Pro"], "rarely"),
        "home_services": (0.5, ["Urban Company"], "monthly"),
        "fintech": (0.8, ["CRED", "Jupiter", "Fi Money"], "weekly"),
        "edtech": (0.4, ["Masterclass", "Skillshare"], "quarterly"),
        "health_and_wellness": (0.7, ["Cult.fit", "Nykaa Wellness", "WOW"], "monthly"),
        "travel": (0.6, ["Airbnb", "MakeMyTrip"], "quarterly"),
        "telecom": (0.4, ["Jio", "Airtel"], "monthly"),
        "jewelry_and_luxury": (0.5, ["CaratLane", "Swarovski"], "quarterly"),
        "baby_and_kids": (0.2, ["FirstCry"], "rarely"),
        "quick_commerce": (0.8, ["Zepto", "Blinkit"], "weekly"),
        "food_delivery": (0.7, ["Zomato", "Swiggy"], "weekly"),
        "personal_care": (0.6, ["Man Matters", "Plum", "mCaffeine"], "monthly"),
        "grocery_and_household": (0.4, ["BigBasket", "Zepto"], "weekly"),
    },
}


def expand_persona_file(file_path: Path) -> bool:
    """Add missing category affinities to a persona JSON file.

    Returns True if the file was modified.
    """
    data = json.loads(file_path.read_text())
    archetype = data.get("archetype", "")
    expansions = ARCHETYPE_EXPANSIONS.get(archetype, {})

    if not expansions:
        return False

    existing_cats = {aff["category"] for aff in data.get("category_affinities", [])}
    added = False

    for category, (interest, brands, frequency) in expansions.items():
        if category not in existing_cats:
            data["category_affinities"].append({
                "category": category,
                "interest_level": interest,
                "preferred_brands": brands,
                "purchase_frequency": frequency,
                "brand_relationships": [],
            })
            added = True

    if added:
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    return added


def main():
    """Expand all persona files."""
    files = sorted(DATA_DIR.glob("*.json"))
    updated = 0
    for f in files:
        if expand_persona_file(f):
            data = json.loads(f.read_text())
            n = len(data["category_affinities"])
            print(f"  Updated {f.name}: {data['name']} — now {n} affinities")
            updated += 1
        else:
            print(f"  Skipped {f.name}")
    print(f"\nDone. Updated {updated}/{len(files)} files.")


if __name__ == "__main__":
    main()
