"""
FastAPI Backend — Dynamic Load Consolidation Engine
Team Sypnatix
"""
import os, sys, json
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import io

# Add backend dir to path
sys.path.insert(0, str(Path(__file__).parent))

from data_loader    import load_shipments, load_fleet
from clustering     import cluster_shipments, get_cluster_summary
from optimizer      import solve_vrp, build_route_results
from evaluator      import compute_before_metrics, compute_after_metrics, build_comparison, score_routes
from agents         import AgentPipeline
from simulation     import run_whatif, compare_scenarios
from forecasting    import forecast_demand
from control_tower  import compute_live_stats

app = FastAPI(
    title="Dynamic Load Consolidation Engine",
    description="Autonomous logistics optimization — Team Sypnatix",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory state ──────────────────────────────────────────────────────────
_state = {
    "shipments":    None,
    "fleet":        None,
    "routes":       None,
    "before":       None,
    "after":        None,
    "comparison":   None,
    "agents":       None,
    "clustered":    None,
    "cluster_summary": None,
}

# ── Static frontend ──────────────────────────────────────────────────────────
FRONTEND = Path(__file__).parent.parent / "frontend"
if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    idx = FRONTEND / "index.html"
    if idx.exists():
        return FileResponse(str(idx))
    return JSONResponse({"message": "LogisticNow API running. UI not found."})


# ── Shipment & Fleet endpoints ───────────────────────────────────────────────

@app.get("/api/shipments")
async def get_shipments(n: int = 50):
    df = load_shipments(n)
    return {"count": len(df), "data": df.to_dict(orient="records")}


@app.get("/api/fleet")
async def get_fleet(n: int = 10):
    df = load_fleet(n)
    return {"count": len(df), "data": df.to_dict(orient="records")}


# ── Upload endpoints ─────────────────────────────────────────────────────────

@app.post("/api/upload/shipments")
async def upload_shipments(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df      = pd.read_csv(io.StringIO(content.decode("utf-8")))
        required = ["pickup_lat", "pickup_lon", "delivery_lat", "delivery_lon", "weight_kg"]
        missing  = [c for c in required if c not in df.columns]
        if missing:
            raise HTTPException(400, f"Missing columns: {missing}")
        _state["shipments"] = df
        return {"status": "ok", "rows": len(df), "columns": list(df.columns)}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/upload/fleet")
async def upload_fleet(file: UploadFile = File(...)):
    try:
        content = await file.read()
        df      = pd.read_csv(io.StringIO(content.decode("utf-8")))
        required = ["capacity_kg", "depot_lat", "depot_lon"]
        missing  = [c for c in required if c not in df.columns]
        if missing:
            raise HTTPException(400, f"Missing columns: {missing}")
        _state["fleet"] = df
        return {"status": "ok", "rows": len(df), "columns": list(df.columns)}
    except Exception as e:
        raise HTTPException(400, str(e))


# ── Main optimization endpoint ───────────────────────────────────────────────

@app.post("/api/optimize")
async def optimize(num_shipments: int = 200, num_vehicles: int = 30):
    """
    Run the full optimization pipeline:
    1. Load data
    2. Cluster shipments (DBSCAN)
    3. Solve VRP (OR-Tools)
    4. Evaluate (cost, CO2, SLA)
    5. Run AI agent pipeline
    """
    # 1. Load data
    try:
        ships = _state["shipments"] if _state["shipments"] is not None else load_shipments(num_shipments)
        fleet = _state["fleet"]     if _state["fleet"]     is not None else load_fleet(num_vehicles)
    except Exception as e:
        raise HTTPException(500, f"Data load error: {e}")

    # Apply user-selected limits (max 5000 ships, 300 vehicles)
    num_shipments = min(num_shipments, 5000)
    num_vehicles  = min(num_vehicles, 300)
    ships = ships.head(num_shipments).reset_index(drop=True)
    fleet = fleet.head(num_vehicles).reset_index(drop=True)

    # 2. Cluster
    try:
        clustered = cluster_shipments(ships, eps_km=200.0, min_samples=2)
        cluster_summary = get_cluster_summary(clustered)
    except Exception as e:
        clustered = ships.copy()
        clustered["cluster_id"] = 0
        cluster_summary = {}
        print(f"[Cluster] Error: {e}")

    # 3. Before metrics (naive baseline)
    try:
        before = compute_before_metrics(ships, fleet)
    except Exception as e:
        before = {"trucks_used": len(ships), "total_cost": 0, "total_co2_kg": 0,
                  "total_distance_km": 0, "avg_utilization": 0, "sla_compliance_pct": 0}
        print(f"[Before] Error: {e}")

    # 4. VRP solve
    try:
        raw_routes = solve_vrp(clustered, fleet)
    except Exception as e:
        raise HTTPException(500, f"VRP solver error: {e}")

    # 5. Build route results
    try:
        routes = build_route_results(raw_routes, clustered, fleet)
        routes = score_routes(routes)
    except Exception as e:
        raise HTTPException(500, f"Route build error: {e}")

    # 6. After metrics
    try:
        after = compute_after_metrics(routes, len(ships))
    except Exception as e:
        after = {}
        print(f"[After] Error: {e}")

    # 7. Comparison
    comparison = build_comparison(before, after) if before and after else {}

    # 8. Agent pipeline
    try:
        pipeline = AgentPipeline()
        agent_results = pipeline.run(
            shipments  = ships,
            clustered  = clustered,
            routes     = routes,
            fleet      = fleet,
            before_co2 = before.get("total_co2_kg", 0),
        )
    except Exception as e:
        agent_results = []
        print(f"[Agents] Error: {e}")

    # Store state
    _state.update({
        "shipments": ships, "fleet": fleet,
        "routes": routes, "before": before, "after": after,
        "comparison": comparison, "agents": agent_results,
        "clustered": clustered, "cluster_summary": cluster_summary,
    })

    # Compute unassigned
    assigned_ids = {s["shipment_id"] for r in routes for s in r["stops"]}
    unassigned   = [sid for sid in ships["shipment_id"] if sid not in assigned_ids]

    return {
        "status":           "ok",
        "routes":           routes,
        "before":           before,
        "after":            after,
        "comparison":       comparison,
        "agents":           agent_results,
        "cluster_summary":  cluster_summary,
        "total_shipments":  len(ships),
        "trucks_used":      len(routes),
        "unassigned":       unassigned,
    }


# ── Result endpoints ─────────────────────────────────────────────────────────

@app.get("/api/results")
async def get_results():
    if _state["routes"] is None:
        raise HTTPException(404, "No optimization results. Run /api/optimize first.")
    return {
        "routes":          _state["routes"],
        "after":           _state["after"],
        "agents":          _state["agents"],
        "cluster_summary": _state["cluster_summary"],
        "unassigned":      [],
    }


@app.get("/api/comparison")
async def get_comparison():
    if _state["comparison"] is None:
        raise HTTPException(404, "No comparison data. Run /api/optimize first.")
    return {"before": _state["before"], "after": _state["after"], "comparison": _state["comparison"]}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "team": "Sypnatix"}


@app.get("/api/dataset_info")
async def dataset_info():
    """Return actual row counts from the real CSV files."""
    try:
        ships_df = load_shipments()
        fleet_df = load_fleet()
        return {
            "shipments": len(ships_df),
            "fleet":     len(fleet_df),
            "ship_columns": list(ships_df.columns),
            "fleet_columns": list(fleet_df.columns),
            "source": "VRP_Shipment_Dataset_.csv + VRP_Fleet_Dataset_.csv",
        }
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Upgrade 1: What-If Simulation ────────────────────────────────────────────

@app.post("/api/simulate")
async def simulate(
    fuel_price_1:    float = 92.0,
    carbon_tax_1:    float = 0.0,
    fleet_size_1:    int   = None,
    priority_w_1:    float = 1.0,
    fuel_price_2:    float = 110.0,
    carbon_tax_2:    float = 5.0,
    fleet_size_2:    int   = None,
    priority_w_2:    float = 1.2,
    fuel_price_3:    float = 92.0,
    carbon_tax_3:    float = 0.0,
    fleet_size_3:    int   = None,
    priority_w_3:    float = 1.0,
    include_third:   bool  = False,
):
    """
    Run What-If scenarios against the last optimized routes.
    Scenarios: Base, High Fuel / Carbon Tax, Smaller Fleet.
    """
    if _state["routes"] is None:
        raise HTTPException(404, "Run /api/optimize first to generate base routes.")

    routes = _state["routes"]
    fleet  = _state["fleet"] if _state["fleet"] is not None else load_fleet()

    # Scenario 1: Base (with possibly updated fuel/tax)
    s1 = run_whatif(
        routes, fleet, fleet,
        fuel_price=fuel_price_1, carbon_tax=carbon_tax_1,
        fleet_override=fleet_size_1, priority_weight=priority_w_1,
        scenario_name="Base Scenario",
    )

    # Scenario 2: High fuel price + carbon tax
    s2 = run_whatif(
        routes, fleet, fleet,
        fuel_price=fuel_price_2, carbon_tax=carbon_tax_2,
        fleet_override=fleet_size_2, priority_weight=priority_w_2,
        scenario_name="High Fuel + Carbon Tax",
    )

    # Scenario 3: Smaller fleet
    s3 = run_whatif(
        routes, fleet, fleet,
        fuel_price=fuel_price_3, carbon_tax=carbon_tax_3,
        fleet_override=fleet_size_3 or max(2, len(routes) - 2),
        priority_weight=priority_w_3,
        scenario_name="Smaller Fleet",
    ) if include_third or True else None

    scenarios = [s1, s2, s3]
    comparison = compare_scenarios(scenarios)

    return {
        "scenarios":  scenarios,
        "comparison": comparison,
    }


# ── Upgrade 2: Demand Forecasting ────────────────────────────────────────────

@app.get("/api/forecast")
async def demand_forecast(horizon_days: int = 3):
    """
    Predict shipment demand for the next N days across geographic zones.
    """
    try:
        ships = _state["shipments"] if _state["shipments"] is not None else load_shipments()
        result = forecast_demand(ships, horizon_days=horizon_days)
        return result
    except Exception as e:
        raise HTTPException(500, f"Forecast error: {e}")


# ── Upgrade 3: Live Control Tower ────────────────────────────────────────────

@app.get("/api/live")
async def live_stats():
    """
    Real-time logistics control tower KPIs.
    Computes live stats from loaded data + simulated operational state.
    """
    try:
        ships  = _state["shipments"] if _state["shipments"] is not None else load_shipments()
        fleet  = _state["fleet"]     if _state["fleet"]     is not None else load_fleet()
        routes = _state["routes"]
        result = compute_live_stats(ships, fleet, routes)
        return result
    except Exception as e:
        raise HTTPException(500, f"Live stats error: {e}")
