"""
Generate realistic sample data matching the exact VRP dataset schema from Google Drive.
Run this script to create sample CSVs for testing and demo purposes.
"""
import pandas as pd
import numpy as np
import os
import random

random.seed(42)
np.random.seed(42)

# Major Indian city coordinates (lat, lon)
CITIES = {
    "Chennai":     (13.0827,  80.2707),
    "Coimbatore":  (11.0168,  76.9558),
    "Salem":       (11.6643,  78.1460),
    "Erode":       (11.3410,  77.7172),
    "Madurai":     (9.9252,   78.1198),
    "Tiruchirappalli": (10.7905, 78.7047),
    "Vellore":     (12.9165,  79.1325),
    "Bangalore":   (12.9716,  77.5946),
    "Hyderabad":   (17.3850,  78.4867),
    "Mumbai":      (19.0760,  72.8777),
    "Pune":        (18.5204,  73.8567),
    "Nagpur":      (21.1458,  79.0882),
    "Delhi":       (28.6139,  77.2090),
    "Ahmedabad":   (23.0225,  72.5714),
    "Kolkata":     (22.5726,  88.3639),
    "Jaipur":      (26.9124,  75.7873),
    "Surat":       (21.1702,  72.8311),
    "Lucknow":     (26.8467,  80.9462),
    "Kochi":       (9.9312,   76.2673),
    "Visakhapatnam": (17.6868, 83.2185),
}

city_names = list(CITIES.keys())

def gen_shipments(n=200):
    rows = []
    types = ["Normal", "Fragile", "Perishable", "Hazardous"]
    priorities = ["Low", "Medium", "High", "Critical"]
    weights_dist = [0.5, 0.3, 0.15, 0.05]  # Low, Med, High, Critical

    for i in range(1, n + 1):
        pickup_city  = random.choice(city_names)
        delivery_city = random.choice([c for c in city_names if c != pickup_city])
        plat, plon = CITIES[pickup_city]
        dlat, dlon = CITIES[delivery_city]

        # Add small noise to lat/lon for realism
        plat += np.random.normal(0, 0.05)
        plon += np.random.normal(0, 0.05)
        dlat += np.random.normal(0, 0.05)
        dlon += np.random.normal(0, 0.05)

        weight    = round(np.random.uniform(100, 2500), 0)
        volume    = round(weight / np.random.uniform(150, 400), 2)
        deadline  = round(np.random.uniform(4, 72), 1)
        priority  = np.random.choice(priorities, p=weights_dist)
        svc_time  = random.randint(10, 90)
        ship_type = np.random.choice(types, p=[0.55, 0.20, 0.15, 0.10])

        rows.append({
            "shipment_id":          f"S{i:04d}",
            "pickup_lat":           round(plat, 4),
            "pickup_lon":           round(plon, 4),
            "delivery_lat":         round(dlat, 4),
            "delivery_lon":         round(dlon, 4),
            "weight_kg":            int(weight),
            "shipment_volume_m3":   volume,
            "deadline_hours":       deadline,
            "priority_level":       priority,
            "service_time_minutes": svc_time,
            "shipment_type":        ship_type,
        })
    return pd.DataFrame(rows)


def gen_fleet(n=25):
    rows = []
    vehicle_types = {
        "Mini Truck":   {"cap": (800,  2500),  "eff": (10, 14), "cost": (15, 35), "ef": (0.2,  0.45)},
        "Medium Truck": {"cap": (2500, 8000),  "eff": (7,  11), "cost": (30, 55), "ef": (0.45, 0.75)},
        "Heavy Truck":  {"cap": (8000, 25000), "eff": (4,  7),  "cost": (50, 90), "ef": (0.75, 1.50)},
    }
    depot_cities = random.choices(city_names, k=n)

    for i in range(1, n + 1):
        vtype = np.random.choice(list(vehicle_types.keys()), p=[0.45, 0.35, 0.20])
        cfg   = vehicle_types[vtype]
        depot = depot_cities[i - 1]
        dlat, dlon = CITIES[depot]
        dlat += np.random.normal(0, 0.03)
        dlon += np.random.normal(0, 0.03)

        rows.append({
            "vehicle_id":               f"V{i:04d}",
            "vehicle_type":             vtype,
            "capacity_kg":              random.randint(*cfg["cap"]),
            "fuel_type":                "Diesel",
            "fuel_efficiency_km_per_l": round(np.random.uniform(*cfg["eff"]), 2),
            "depot_lat":                round(dlat, 4),
            "depot_lon":                round(dlon, 4),
            "vehicle_cost_per_km":      round(np.random.uniform(*cfg["cost"]), 2),
            "max_route_time":           round(np.random.uniform(6, 14), 1),
            "emission_factor":          round(np.random.uniform(*cfg["ef"]), 3),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    out_dir = os.path.dirname(os.path.abspath(__file__))
    ships = gen_shipments(200)
    fleet = gen_fleet(25)

    ship_path  = os.path.join(out_dir, "VRP_Shipment_Dataset_.csv")
    fleet_path = os.path.join(out_dir, "VRP_Fleet_Dataset_.csv")

    ships.to_csv(ship_path,  index=False)
    fleet.to_csv(fleet_path, index=False)

    print(f"[OK] Shipments ({len(ships)} rows) -> {ship_path}")
    print(f"[OK] Fleet     ({len(fleet)} rows) -> {fleet_path}")
    print("\nShipment columns:", list(ships.columns))
    print("Fleet columns:   ", list(fleet.columns))
