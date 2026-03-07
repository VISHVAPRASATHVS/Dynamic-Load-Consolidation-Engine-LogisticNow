"""
Evaluation layer — calculates cost, CO2, SLA compliance, and before/after comparisons.
"""
import math
import pandas as pd
from typing import List, Dict
from data_loader import haversine, estimate_travel_time


DIESEL_PRICE_PER_LITRE = 92.0   # INR — Tamil Nadu avg 2024
CO2_PER_LITRE_DIESEL   = 2.68   # kg CO2 per litre of diesel


def compute_before_metrics(shipments: pd.DataFrame, fleet: pd.DataFrame) -> Dict:
    """
    Simulate naive (un-optimized) scenario: 1 vehicle per shipment,
    smallest available vehicle for each.
    """
    total_shipments = len(shipments)
    avg_vehicle_cost = float(fleet["vehicle_cost_per_km"].mean())
    avg_fuel_eff     = float(fleet["fuel_efficiency_km_per_l"].mean())
    avg_emit         = float(fleet["emission_factor"].mean())
    avg_capacity     = float(fleet["capacity_kg"].mean())

    total_dist  = 0.0
    total_cost  = 0.0
    total_co2   = 0.0
    trucks_used = 0
    sla_meets   = 0

    # Central depot (centroid of all depots)
    depot_lat = fleet["depot_lat"].mean()
    depot_lon = fleet["depot_lon"].mean()

    for _, row in shipments.iterrows():
        # Round-trip: depot → pickup → delivery → depot
        dist  = haversine(depot_lat, depot_lon, float(row["pickup_lat"]), float(row["pickup_lon"]))
        dist += haversine(float(row["pickup_lat"]), float(row["pickup_lon"]),
                          float(row["delivery_lat"]), float(row["delivery_lon"]))
        dist += haversine(float(row["delivery_lat"]), float(row["delivery_lon"]),
                          depot_lat, depot_lon)

        cost = dist * avg_vehicle_cost
        co2  = (dist / avg_fuel_eff) * avg_emit * CO2_PER_LITRE_DIESEL
        travel_h = estimate_travel_time(dist)

        total_dist += dist
        total_cost += cost
        total_co2  += co2
        trucks_used += 1
        if travel_h <= float(row["deadline_hours"]):
            sla_meets += 1

    utilization = (shipments["weight_kg"].sum() / (trucks_used * avg_capacity)) * 100 if trucks_used else 0

    return {
        "trucks_used":        trucks_used,
        "total_cost":         round(total_cost, 2),
        "total_co2_kg":       round(total_co2, 2),
        "total_distance_km":  round(total_dist, 2),
        "avg_utilization":    round(min(100.0, utilization), 1),
        "sla_compliance_pct": round((sla_meets / total_shipments) * 100, 1) if total_shipments else 0,
    }


def compute_after_metrics(route_results: List[Dict], total_shipments: int) -> Dict:
    """Aggregate optimized route metrics."""
    if not route_results:
        return {}

    trucks_used       = len(route_results)
    total_cost        = sum(r["total_cost"] for r in route_results)
    total_co2         = sum(r["total_co2_kg"] for r in route_results)
    total_dist        = sum(r["total_distance_km"] for r in route_results)
    avg_util          = sum(r["utilization_pct"] for r in route_results) / trucks_used
    sla_violations    = sum(r["sla_violations"] for r in route_results)
    assigned_count    = sum(len(r["stops"]) for r in route_results)
    sla_comp = ((assigned_count - sla_violations) / assigned_count * 100) if assigned_count else 0

    return {
        "trucks_used":        trucks_used,
        "total_cost":         round(total_cost, 2),
        "total_co2_kg":       round(total_co2, 2),
        "total_distance_km":  round(total_dist, 2),
        "avg_utilization":    round(avg_util, 1),
        "sla_compliance_pct": round(sla_comp, 1),
    }


def build_comparison(before: Dict, after: Dict) -> Dict:
    """Build before/after comparison object with reduction percentages."""
    def pct_change(b, a):
        if b == 0:
            return 0.0
        return round(((b - a) / b) * 100, 1)

    return {
        "before_trucks":       before["trucks_used"],
        "after_trucks":        after["trucks_used"],
        "before_cost":         before["total_cost"],
        "after_cost":          after["total_cost"],
        "before_co2":          before["total_co2_kg"],
        "after_co2":           after["total_co2_kg"],
        "before_distance":     before["total_distance_km"],
        "after_distance":      after["total_distance_km"],
        "before_utilization":  before["avg_utilization"],
        "after_utilization":   after["avg_utilization"],
        "before_sla":          before["sla_compliance_pct"],
        "after_sla":           after["sla_compliance_pct"],
        "cost_reduction_pct":  pct_change(before["total_cost"],  after["total_cost"]),
        "co2_reduction_pct":   pct_change(before["total_co2_kg"], after["total_co2_kg"]),
        "truck_reduction_pct": pct_change(before["trucks_used"], after["trucks_used"]),
        "dist_reduction_pct":  pct_change(before["total_distance_km"], after["total_distance_km"]),
    }


def score_routes(route_results: List[Dict]) -> List[Dict]:
    """Add efficiency score (0-100) to each route."""
    for r in route_results:
        # Score: weighted average of utilization (60%) + SLA (30%) + CO2 efficiency (10%)
        util_score = min(100, r["utilization_pct"])
        sla_score  = max(0, 100 - r["sla_violations"] * 20)
        # CO2 per kg delivered
        stops_weight = r["total_weight_kg"] or 1
        co2_per_kg   = r["total_co2_kg"] / stops_weight
        co2_score    = max(0, 100 - co2_per_kg * 50)
        r["efficiency_score"] = round(0.6 * util_score + 0.3 * sla_score + 0.1 * co2_score, 1)
    return route_results
