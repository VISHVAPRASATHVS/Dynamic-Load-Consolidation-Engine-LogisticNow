"""
Live Control Tower — Real-time logistics KPIs computed from loaded data.
Simulates live operational status using the current shipment + route data.
"""
import random
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np


# Simulated "live" operational constants
SPEED_KMPH         = 55.0
MAINTENANCE_RATE   = 0.05   # 5% vehicles in maintenance at any time
DELAY_PROBABILITY  = 0.18   # 18% of routes have delays


def compute_live_stats(
    shipments: pd.DataFrame,
    fleet: pd.DataFrame,
    routes: Optional[List[Dict]] = None,
) -> Dict:
    """
    Build a control tower live stats snapshot.
    Combines real loaded data with realistic simulated live state.
    """
    rng = random.Random(42)
    np     = __import__('numpy')

    total_ships   = len(shipments)
    total_vehicles = len(fleet)

    # ── Active shipments ─────────────────────────────────────────
    # Simulate: some % are in-transit, some at depot, some delivered
    in_transit_pct  = rng.uniform(0.45, 0.65)
    at_depot_pct    = rng.uniform(0.15, 0.25)
    delivered_pct   = 1.0 - in_transit_pct - at_depot_pct
    active_ships    = int(total_ships * in_transit_pct)
    delivered_ships = int(total_ships * delivered_pct)
    at_depot_ships  = total_ships - active_ships - delivered_ships

    # ── Fleet ────────────────────────────────────────────────────
    on_road       = int(total_vehicles * (1 - MAINTENANCE_RATE) * in_transit_pct)
    in_maintenance = max(1, int(total_vehicles * MAINTENANCE_RATE))
    idle          = total_vehicles - on_road - in_maintenance

    # ── Utilization ──────────────────────────────────────────────
    if routes:
        avg_util = sum(r["utilization_pct"] for r in routes) / len(routes)
    else:
        avg_util = fleet["capacity_kg"].mean()  # placeholder
        total_w  = shipments["weight_kg"].sum() if "weight_kg" in shipments else 0
        avg_util = min(98, (total_w / (total_vehicles * fleet["capacity_kg"].mean())) * 100) if avg_util else 72

    # ── Delays ───────────────────────────────────────────────────
    delayed_routes  = max(0, int(on_road * DELAY_PROBABILITY))
    on_time_routes  = on_road - delayed_routes
    on_time_pct     = (on_time_routes / on_road * 100) if on_road else 100

    # ── CO2 today ────────────────────────────────────────────────
    avg_dist      = 420.0  # km avg route
    avg_fuel_eff  = float(fleet["fuel_efficiency_km_per_l"].mean()) if "fuel_efficiency_km_per_l" in fleet else 9.5
    avg_emit      = float(fleet["emission_factor"].mean()) if "emission_factor" in fleet else 0.5
    co2_today_kg  = on_road * avg_dist / avg_fuel_eff * avg_emit * 2.68
    co2_today_ton = co2_today_kg / 1000

    # ── Cost today ───────────────────────────────────────────────
    avg_cost_km    = float(fleet["vehicle_cost_per_km"].mean()) if "vehicle_cost_per_km" in fleet else 38.0
    cost_today     = on_road * avg_dist * avg_cost_km

    # ── Route status list (top 8 active routes) ──────────────────
    live_routes = []
    cities = ["Chennai", "Bangalore", "Hyderabad", "Mumbai", "Delhi",
              "Kolkata", "Pune", "Ahmedabad", "Coimbatore", "Madurai"]
    vehicle_ids = list(fleet["vehicle_id"].head(8)) if "vehicle_id" in fleet else [f"V{i:04d}" for i in range(8)]

    for i, vid in enumerate(vehicle_ids[:8]):
        origin = cities[i % len(cities)]
        dest   = cities[(i + 3) % len(cities)]
        progress = rng.uniform(0.15, 0.90)
        delayed  = rng.random() < DELAY_PROBABILITY
        eta_hrs  = round((1 - progress) * rng.uniform(2, 8), 1)
        live_routes.append({
            "vehicle_id":  vid,
            "origin":      origin,
            "destination": dest,
            "progress_pct": round(progress * 100, 1),
            "status":       "Delayed" if delayed else "On Time",
            "eta_hours":    eta_hrs,
            "load_kg":      int(rng.uniform(800, 2400)),
        })

    # ── Alert list ───────────────────────────────────────────────
    alerts = []
    if delayed_routes > 0:
        alerts.append({
            "level":   "warning",
            "message": f"{delayed_routes} vehicles experiencing route delays",
        })
    if in_maintenance >= 3:
        alerts.append({
            "level":   "info",
            "message": f"{in_maintenance} vehicles scheduled for maintenance",
        })
    if avg_util >= 95:
        alerts.append({
            "level":   "success",
            "message": f"Fleet utilization at {avg_util:.1f}% — optimal loading",
        })
    if co2_today_ton > 10:
        alerts.append({
            "level":   "warning",
            "message": f"CO2 output {co2_today_ton:.1f} t today — above threshold",
        })

    return {
        "timestamp":        datetime.now().isoformat(),
        "active_shipments": active_ships,
        "delivered_today":  delivered_ships,
        "at_depot":         at_depot_ships,
        "total_shipments":  total_ships,

        "vehicles_on_road":      on_road,
        "vehicles_idle":         idle,
        "vehicles_maintenance":  in_maintenance,
        "total_vehicles":        total_vehicles,

        "avg_utilization":   round(avg_util, 1),
        "delayed_routes":    delayed_routes,
        "on_time_routes":    on_time_routes,
        "on_time_pct":       round(on_time_pct, 1),

        "co2_today_kg":     round(co2_today_kg, 1),
        "co2_today_ton":    round(co2_today_ton, 2),
        "cost_today":       round(cost_today, 0),

        "live_routes":      live_routes,
        "alerts":           alerts,
    }
