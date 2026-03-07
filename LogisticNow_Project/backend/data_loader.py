"""
Data loader — reads shipment and fleet CSVs, validates, and computes distance matrices.
Falls back to auto-generating sample data if CSVs are not present.
"""
import os, sys, math
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SHIP_CSV  = DATA_DIR / "VRP_Shipment_Dataset_.csv"
FLEET_CSV = DATA_DIR / "VRP_Fleet_Dataset_.csv"


def _ensure_data() -> None:
    """Auto-generate sample data if CSVs are missing."""
    if not SHIP_CSV.exists() or not FLEET_CSV.exists():
        sys.path.insert(0, str(DATA_DIR))
        from sample_data import gen_shipments, gen_fleet
        gen_shipments(200).to_csv(SHIP_CSV,  index=False)
        gen_fleet(25).to_csv(FLEET_CSV, index=False)
        print("[DataLoader] Sample CSVs generated.")


def load_shipments(n: int = None) -> pd.DataFrame:
    _ensure_data()
    df = pd.read_csv(SHIP_CSV)
    # Coerce types
    df["weight_kg"]            = pd.to_numeric(df["weight_kg"], errors="coerce").fillna(500)
    df["deadline_hours"]       = pd.to_numeric(df["deadline_hours"], errors="coerce").fillna(24)
    df["service_time_minutes"] = pd.to_numeric(df["service_time_minutes"], errors="coerce").fillna(30)
    df["shipment_volume_m3"]   = pd.to_numeric(df["shipment_volume_m3"], errors="coerce").fillna(2.0)
    df.dropna(subset=["pickup_lat", "pickup_lon", "delivery_lat", "delivery_lon"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    if n:
        df = df.sample(min(n, len(df)), random_state=42).reset_index(drop=True)
    return df


def load_fleet(n: int = None) -> pd.DataFrame:
    _ensure_data()
    df = pd.read_csv(FLEET_CSV)
    df["capacity_kg"]              = pd.to_numeric(df["capacity_kg"], errors="coerce").fillna(2000)
    df["fuel_efficiency_km_per_l"] = pd.to_numeric(df["fuel_efficiency_km_per_l"], errors="coerce").fillna(10)
    df["vehicle_cost_per_km"]      = pd.to_numeric(df["vehicle_cost_per_km"], errors="coerce").fillna(30)
    df["emission_factor"]          = pd.to_numeric(df["emission_factor"], errors="coerce").fillna(0.5)
    df["max_route_time"]           = pd.to_numeric(df["max_route_time"], errors="coerce").fillna(10)
    df.dropna(subset=["depot_lat", "depot_lon"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    if n:
        df = df.sample(min(n, len(df)), random_state=42).reset_index(drop=True)
    return df


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_distance_matrix(lats: list, lons: list) -> list:
    """Build a full pairwise distance matrix (km)."""
    n = len(lats)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                mat[i][j] = haversine(lats[i], lons[i], lats[j], lons[j])
    return mat


def estimate_travel_time(distance_km: float, avg_speed_kmh: float = 55.0) -> float:
    """Return travel time in hours."""
    return distance_km / avg_speed_kmh
