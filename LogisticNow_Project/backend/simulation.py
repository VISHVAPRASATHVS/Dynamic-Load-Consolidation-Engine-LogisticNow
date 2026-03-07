"""
What-If Simulation Engine
Reruns the cost/CO2 evaluation with modified parameters without full VRP re-solve.
Supports: fuel price, carbon tax rate, fleet size override, priority weight changes.
"""
import pandas as pd
from typing import List, Dict, Optional
from data_loader import haversine, estimate_travel_time

DIESEL_EMISSION_KG_PER_L = 2.68   # kg CO2 per litre


def run_whatif(
    base_routes: List[Dict],
    shipments: pd.DataFrame,
    fleet: pd.DataFrame,
    fuel_price: float = 92.0,
    carbon_tax: float = 0.0,
    fleet_override: Optional[int] = None,
    priority_weight: float = 1.0,
    scenario_name: str = "Scenario",
) -> Dict:
    """
    Given existing routes, recompute cost/CO2/CO2-tax with new parameters.
    If fleet_override reduces available vehicles, routes are trimmed/merged.
    Returns a full scenario result dict.
    """
    routes = base_routes
    if not routes:
        return {}

    # If fleet size is reduced, trim to that many routes
    if fleet_override and fleet_override < len(routes):
        routes = routes[:fleet_override]

    total_cost     = 0.0
    total_co2      = 0.0
    total_co2_tax  = 0.0
    total_dist     = 0.0
    trucks_used    = 0
    sla_violations = 0
    total_stops    = 0

    route_results = []
    for r in routes:
        dist     = r["total_distance_km"]
        v_cost   = _get_vehicle_cost(fleet, r["vehicle_id"])
        fuel_eff = _get_fuel_eff(fleet, r["vehicle_id"])
        emit_fac = _get_emission_factor(fleet, r["vehicle_id"])

        # Cost with new fuel price
        fuel_litres = dist / fuel_eff if fuel_eff else 0
        fuel_cost   = fuel_litres * fuel_price
        route_cost  = dist * v_cost + (fuel_cost - dist * v_cost * 0.3)  # blend

        # CO2 with carbon tax
        co2         = (dist / fuel_eff) * emit_fac * DIESEL_EMISSION_KG_PER_L if fuel_eff else r["total_co2_kg"]
        co2_tax_cost = co2 * carbon_tax

        # Priority weight affects SLA compliance scoring
        sla_viol = r["sla_violations"] * priority_weight

        total_cost     += route_cost
        total_co2      += co2
        total_co2_tax  += co2_tax_cost
        total_dist     += dist
        trucks_used    += 1
        sla_violations += sla_viol
        total_stops    += len(r["stops"])

        route_results.append({
            **r,
            "total_cost":    round(route_cost, 2),
            "total_co2_kg":  round(co2, 2),
            "co2_tax_cost":  round(co2_tax_cost, 2),
        })

    avg_util = sum(r["utilization_pct"] for r in route_results) / trucks_used if trucks_used else 0
    sla_comp = ((total_stops - sla_violations) / total_stops * 100) if total_stops else 0

    return {
        "scenario_name":      scenario_name,
        "fuel_price":         fuel_price,
        "carbon_tax":         carbon_tax,
        "fleet_override":     fleet_override or trucks_used,
        "priority_weight":    priority_weight,
        "trucks_used":        trucks_used,
        "total_cost":         round(total_cost + total_co2_tax, 2),
        "total_co2_kg":       round(total_co2, 2),
        "total_co2_tax":      round(total_co2_tax, 2),
        "total_distance_km":  round(total_dist, 2),
        "avg_utilization":    round(avg_util, 1),
        "sla_compliance_pct": round(max(0, sla_comp), 1),
        "routes":             route_results,
    }


def compare_scenarios(scenarios: List[Dict]) -> List[Dict]:
    """Build comparison rows across multiple scenarios."""
    if not scenarios:
        return []
    base = scenarios[0]
    result = []
    for sc in scenarios:
        cost_diff = ((sc["total_cost"] - base["total_cost"]) / base["total_cost"] * 100) if base["total_cost"] else 0
        co2_diff  = ((sc["total_co2_kg"] - base["total_co2_kg"]) / base["total_co2_kg"] * 100) if base["total_co2_kg"] else 0
        result.append({
            "scenario":          sc["scenario_name"],
            "fuel_price":        sc["fuel_price"],
            "carbon_tax":        sc["carbon_tax"],
            "trucks":            sc["trucks_used"],
            "total_cost":        sc["total_cost"],
            "cost_change_pct":   round(cost_diff, 1),
            "total_co2_kg":      sc["total_co2_kg"],
            "co2_change_pct":    round(co2_diff, 1),
            "avg_utilization":   sc["avg_utilization"],
            "sla_compliance_pct": sc["sla_compliance_pct"],
        })
    return result


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_vehicle_cost(fleet: pd.DataFrame, vehicle_id: str) -> float:
    rows = fleet[fleet["vehicle_id"] == vehicle_id]
    return float(rows["vehicle_cost_per_km"].iloc[0]) if len(rows) else 35.0


def _get_fuel_eff(fleet: pd.DataFrame, vehicle_id: str) -> float:
    rows = fleet[fleet["vehicle_id"] == vehicle_id]
    return float(rows["fuel_efficiency_km_per_l"].iloc[0]) if len(rows) else 10.0


def _get_emission_factor(fleet: pd.DataFrame, vehicle_id: str) -> float:
    rows = fleet[fleet["vehicle_id"] == vehicle_id]
    return float(rows["emission_factor"].iloc[0]) if len(rows) else 0.5
