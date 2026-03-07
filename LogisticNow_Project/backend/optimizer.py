"""
OR-Tools VRP Solver — Vehicle Routing Problem with:
  - Capacity constraints (weight kg)
  - Time-window constraints (deadline hours)
  - Multiple depots
  - Distance minimization objective
"""
import math
import numpy as np
from typing import List, Dict, Tuple
import pandas as pd

try:
    from ortools.constraint_solver import routing_enums_pb2
    from ortools.constraint_solver import pywrapcp
    ORTOOLS_AVAILABLE = True
except ImportError:
    ORTOOLS_AVAILABLE = False
    print("[WARNING] OR-Tools not available — using greedy fallback optimizer")

from data_loader import haversine, estimate_travel_time


ROUTE_COLORS = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
    "#06b6d4", "#f97316", "#84cc16", "#ec4899", "#14b8a6",
    "#6366f1", "#d97706", "#059669", "#dc2626", "#7c3aed",
]


def _build_vrp_data(shipments: pd.DataFrame, fleet: pd.DataFrame):
    """Prepare data dict for OR-Tools."""
    # Nodes: depot(s) + deliveries
    # We use a single virtual depot at centroid of all depots for simplicity
    depot_lat = fleet["depot_lat"].mean()
    depot_lon = fleet["depot_lon"].mean()

    lats = [depot_lat] + list(shipments["delivery_lat"])
    lons = [depot_lon] + list(shipments["delivery_lon"])

    n = len(lats)
    dist_matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dist_matrix[i][j] = int(haversine(lats[i], lons[i], lats[j], lons[j]) * 100)  # m (scaled)

    demands    = [0] + [int(w) for w in shipments["weight_kg"]]            # depot demand = 0
    time_wins  = [(0, 9999)] + [(0, int(h * 60)) for h in shipments["deadline_hours"]]  # minutes
    capacities = [int(c) for c in fleet["capacity_kg"]]

    return {
        "distance_matrix": dist_matrix,
        "demands":         demands,
        "time_windows":    time_wins,
        "vehicle_capacities": capacities,
        "num_vehicles":    len(fleet),
        "depot":           0,
        "lats":            lats,
        "lons":            lons,
    }


def solve_vrp(shipments: pd.DataFrame, fleet: pd.DataFrame) -> Dict:
    """
    Solve the VRP and return route assignments.
    Returns dict: { vehicle_idx -> list of shipment indices (0-based in shipments df) }
    """
    if len(shipments) == 0 or len(fleet) == 0:
        return {}

    if not ORTOOLS_AVAILABLE:
        return _greedy_fallback(shipments, fleet)

    data = _build_vrp_data(shipments, fleet)
    manager = pywrapcp.RoutingIndexManager(
        len(data["distance_matrix"]),
        data["num_vehicles"],
        data["depot"],
    )
    routing = pywrapcp.RoutingModel(manager)

    # Distance callback
    def dist_callback(from_idx, to_idx):
        fi = manager.IndexToNode(from_idx)
        ti = manager.IndexToNode(to_idx)
        return data["distance_matrix"][fi][ti]

    transit_cb_idx = routing.RegisterTransitCallback(dist_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # Capacity constraint
    def demand_callback(idx):
        return data["demands"][manager.IndexToNode(idx)]

    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx, 0, data["vehicle_capacities"], True, "Capacity"
    )

    # Time window dimension
    def time_callback(from_idx, to_idx):
        fi = manager.IndexToNode(from_idx)
        ti = manager.IndexToNode(to_idx)
        dist_km = data["distance_matrix"][fi][ti] / 100.0
        travel_min = int(dist_km / 55.0 * 60)
        service_min = 0
        if ti > 0:
            srow = ti - 1
            if srow < len(shipments):
                service_min = int(shipments.iloc[srow]["service_time_minutes"])
        return travel_min + service_min

    time_cb_idx = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(time_cb_idx, 60, 9999, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    for loc_idx, (start, end) in enumerate(data["time_windows"]):
        if loc_idx == 0:
            continue
        idx = manager.NodeToIndex(loc_idx)
        time_dim.CumulVar(idx).SetRange(start, end)

    # Allow dropping nodes (with penalty) to handle infeasible cases
    penalty = 1_000_000
    for node in range(1, len(data["distance_matrix"])):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # Search parameters
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 10
    search_params.log_search = False

    solution = routing.SolveWithParameters(search_params)

    if not solution:
        print("[VRP] No solution found — using greedy fallback")
        return _greedy_fallback(shipments, fleet)

    routes = {}
    for v in range(data["num_vehicles"]):
        idx   = routing.Start(v)
        stops = []
        while not routing.IsEnd(idx):
            node = manager.IndexToNode(idx)
            if node != 0:
                stops.append(node - 1)  # 0-based shipment index
            idx = solution.Value(routing.NextVar(idx))
        if stops:
            routes[v] = stops

    return routes


def _greedy_fallback(shipments: pd.DataFrame, fleet: pd.DataFrame) -> Dict:
    """
    Simple greedy packing: sort shipments by deadline (ascending),
    assign to vehicles greedily respecting capacity.
    """
    df = shipments.copy().reset_index(drop=True)
    # Sort: Critical/High first, then by deadline
    priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    df["_pri"]  = df["priority_level"].map(priority_order).fillna(3)
    df["_dead"] = df["deadline_hours"]
    df = df.sort_values(["_pri", "_dead"]).reset_index(drop=True)

    routes    = {v: [] for v in range(len(fleet))}
    remaining = {v: float(fleet.iloc[v]["capacity_kg"]) for v in range(len(fleet))}

    assigned = set()
    for ship_idx, row in df.iterrows():
        original_idx = shipments.index.get_loc(ship_idx) if hasattr(shipments.index, 'get_loc') else ship_idx
        original_idx = int(ship_idx)
        if original_idx in assigned:
            continue
        for v in range(len(fleet)):
            if remaining[v] >= row["weight_kg"]:
                routes[v].append(original_idx)
                remaining[v] -= row["weight_kg"]
                assigned.add(original_idx)
                break

    return {v: stops for v, stops in routes.items() if stops}


def build_route_results(
    routes:    Dict,
    shipments: pd.DataFrame,
    fleet:     pd.DataFrame,
) -> List[Dict]:
    """Convert raw route assignments to full route result objects."""
    results = []

    for v_idx, stop_indices in routes.items():
        if not stop_indices:
            continue

        vrow    = fleet.iloc[v_idx]
        stops_df = shipments.iloc[stop_indices].copy()

        depot_lat = float(vrow["depot_lat"])
        depot_lon = float(vrow["depot_lon"])

        total_dist = 0.0
        prev_lat, prev_lon = depot_lat, depot_lon

        stop_list = []
        for _, srow in stops_df.iterrows():
            dlat, dlon = float(srow["delivery_lat"]), float(srow["delivery_lon"])
            seg_dist = haversine(prev_lat, prev_lon, dlat, dlon)
            total_dist += seg_dist
            prev_lat, prev_lon = dlat, dlon

        # Return to depot
        total_dist += haversine(prev_lat, prev_lon, depot_lat, depot_lon)

        total_weight  = float(stops_df["weight_kg"].sum())
        capacity      = float(vrow["capacity_kg"])
        utilization   = min(100.0, (total_weight / capacity) * 100)
        cost_per_km   = float(vrow["vehicle_cost_per_km"])
        emit_factor   = float(vrow["emission_factor"])
        fuel_eff      = float(vrow["fuel_efficiency_km_per_l"])
        route_cost    = total_dist * cost_per_km
        co2_kg        = (total_dist / fuel_eff) * emit_factor * 2.68  # diesel: 2.68 kg CO2/litre
        route_time    = estimate_travel_time(total_dist)

        sla_violations = 0
        for _, srow in stops_df.iterrows():
            if route_time > float(srow["deadline_hours"]):
                sla_violations += 1

        for _, srow in stops_df.iterrows():
            stop_list.append({
                "shipment_id":  srow["shipment_id"],
                "delivery_lat": float(srow["delivery_lat"]),
                "delivery_lon": float(srow["delivery_lon"]),
                "weight_kg":    float(srow["weight_kg"]),
                "service_time": int(srow["service_time_minutes"]),
                "deadline":     float(srow["deadline_hours"]),
                "priority":     str(srow["priority_level"]),
                "ship_type":    str(srow["shipment_type"]),
            })

        color = ROUTE_COLORS[v_idx % len(ROUTE_COLORS)]

        results.append({
            "vehicle_id":        str(vrow["vehicle_id"]),
            "vehicle_type":      str(vrow["vehicle_type"]),
            "depot_lat":         depot_lat,
            "depot_lon":         depot_lon,
            "stops":             stop_list,
            "total_weight_kg":   round(total_weight, 1),
            "capacity_kg":       round(capacity, 1),
            "utilization_pct":   round(utilization, 1),
            "total_distance_km": round(total_dist, 2),
            "total_cost":        round(route_cost, 2),
            "total_co2_kg":      round(co2_kg, 2),
            "route_time_hrs":    round(route_time, 2),
            "sla_violations":    sla_violations,
            "color":             color,
        })

    return results
