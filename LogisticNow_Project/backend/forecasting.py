"""
Demand Forecasting Module
Uses moving average + geographic zone aggregation to predict tomorrow's shipment demand.
No external ML library required — pure numpy/pandas for hackathon speed.
"""
import numpy as np
import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta


# Tamil Nadu / major Indian cities with coordinates
DEMAND_ZONES = {
    "Chennai":        (13.0827, 80.2707),
    "Coimbatore":     (11.0168, 76.9558),
    "Bangalore":      (12.9716, 77.5946),
    "Hyderabad":      (17.3850, 78.4867),
    "Mumbai":         (19.0760, 72.8777),
    "Delhi":          (28.6139, 77.2090),
    "Kolkata":        (22.5726, 88.3639),
    "Madurai":        (9.9252,  78.1198),
    "Salem":          (11.6643, 78.1460),
    "Pune":           (18.5204, 73.8567),
    "Ahmedabad":      (23.0225, 72.5714),
    "Visakhapatnam":  (17.6868, 83.2185),
}

ZONE_RADIUS_DEG = 3.0   # degree radius to assign shipment to a zone


def _assign_zone(lat: float, lon: float) -> str:
    """Assign a lat/lon to the nearest demand zone."""
    best_zone, best_dist = "Other", float("inf")
    for zone, (zlat, zlon) in DEMAND_ZONES.items():
        dist = ((lat - zlat) ** 2 + (lon - zlon) ** 2) ** 0.5
        if dist < best_dist:
            best_dist, best_zone = dist, zone
    return best_zone if best_dist < ZONE_RADIUS_DEG else "Other"


def _moving_average(values: List[float], window: int = 7) -> float:
    """Simple moving average forecast."""
    if not values:
        return 0.0
    tail = values[-window:]
    return sum(tail) / len(tail)


def _weighted_moving_average(values: List[float], window: int = 7) -> float:
    """Linearly weighted moving average — more weight to recent values."""
    if not values:
        return 0.0
    tail   = values[-window:]
    n      = len(tail)
    weights = list(range(1, n + 1))
    return sum(v * w for v, w in zip(tail, weights)) / sum(weights)


def _trend_adjustment(values: List[float]) -> float:
    """Compute trend (slope) from last N values using linear regression."""
    if len(values) < 3:
        return 0.0
    x = np.arange(len(values))
    y = np.array(values, dtype=float)
    if y.std() == 0:
        return 0.0
    slope = np.polyfit(x, y, 1)[0]
    return slope


def generate_synthetic_history(shipments: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """
    Since we don't have time-series history, simulate 30 days of historical demand
    by adding Gaussian noise and weekly seasonality to the current dataset distribution.
    This lets us demo a real forecast.
    """
    np.random.seed(42)
    base_total = len(shipments)

    # Zone distribution from current dataset
    shipments = shipments.copy()
    shipments["zone"] = shipments.apply(
        lambda r: _assign_zone(r["delivery_lat"], r["delivery_lon"]), axis=1
    )
    zone_dist = shipments["zone"].value_counts(normalize=True).to_dict()

    rows = []
    today = datetime.now().date()
    for d in range(days, 0, -1):
        date = today - timedelta(days=d)
        dow  = date.weekday()  # 0=Mon, 6=Sun
        # Weekly seasonality: Mon-Fri peak, Sat lower, Sun lowest
        seasonal = [1.10, 1.05, 1.00, 1.08, 1.15, 0.80, 0.55][dow]
        daily_total = int(base_total * seasonal * np.random.uniform(0.85, 1.15) / 7)

        for zone, frac in zone_dist.items():
            zone_count = max(1, int(daily_total * frac * np.random.uniform(0.8, 1.2)))
            # Priority distribution
            rows.append({
                "date":             date.isoformat(),
                "zone":             zone,
                "shipment_count":   zone_count,
                "high_priority_pct": round(np.random.uniform(0.10, 0.35), 2),
                "avg_weight_kg":    round(np.random.uniform(300, 900), 0),
            })

    return pd.DataFrame(rows)


def forecast_demand(shipments: pd.DataFrame, horizon_days: int = 3) -> Dict:
    """
    Generate demand forecast for the next N days across zones.
    Returns per-zone forecasts + suggested fleet sizes.
    """
    hist = generate_synthetic_history(shipments, days=30)
    today = datetime.now().date()

    # Per-zone forecast
    zone_forecasts = {}
    all_zone_shipments = []

    for zone in DEMAND_ZONES:
        zone_hist = hist[hist["zone"] == zone].sort_values("date")
        counts    = list(zone_hist["shipment_count"])

        wma       = _weighted_moving_average(counts, window=7)
        trend     = _trend_adjustment(counts)
        forecasts = []
        for d in range(1, horizon_days + 1):
            predicted = max(0, round(wma + trend * d))
            forecasts.append({
                "date":             (today + timedelta(days=d)).isoformat(),
                "predicted_count":  predicted,
                "confidence":       round(max(0.55, 0.90 - d * 0.05), 2),
            })

        zone_forecasts[zone] = {
            "zone":              zone,
            "lat":               DEMAND_ZONES[zone][0],
            "lon":               DEMAND_ZONES[zone][1],
            "recent_avg_daily":  round(wma, 1),
            "trend_per_day":     round(trend, 2),
            "forecasts":         forecasts,
            "tomorrow":          forecasts[0]["predicted_count"] if forecasts else 0,
        }
        all_zone_shipments.append(forecasts[0]["predicted_count"] if forecasts else 0)

    # Overall totals
    total_tomorrow   = sum(z["tomorrow"] for z in zone_forecasts.values())
    top_zones        = sorted(zone_forecasts.values(), key=lambda z: z["tomorrow"], reverse=True)[:5]

    # Suggest fleet size (avg 12 shipments per truck at ~65% capacity)
    suggested_fleet  = max(5, round(total_tomorrow / 12))

    # High demand zone alerts
    alerts = []
    avg_zone = total_tomorrow / max(1, len(zone_forecasts))
    for zone, data in zone_forecasts.items():
        if data["tomorrow"] > avg_zone * 1.4:
            alerts.append(f"High demand in {zone}: {data['tomorrow']} shipments predicted")

    return {
        "generated_at":    datetime.now().isoformat(),
        "horizon_days":    horizon_days,
        "total_tomorrow":  total_tomorrow,
        "suggested_fleet": suggested_fleet,
        "top_zones":       top_zones,
        "all_zones":       list(zone_forecasts.values()),
        "alerts":          alerts,
        "method":          "Weighted Moving Average + Linear Trend",
        "history_days":    30,
    }
