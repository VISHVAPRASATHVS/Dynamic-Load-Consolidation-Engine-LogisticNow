"""
AI Agent Pipeline for the Dynamic Load Consolidation Engine.
Implements 4 sequential agents: Clustering → Capacity → SLA → Carbon
Each agent validates or enriches the route plan before passing to next stage.
"""
import time
import pandas as pd
from typing import List, Dict, Callable, Optional


class AgentResult:
    def __init__(self, agent: str, status: str, message: str, data: Optional[Dict] = None):
        self.agent   = agent
        self.status  = status   # pending | running | done | error
        self.message = message
        self.data    = data or {}

    def to_dict(self):
        return {"agent": self.agent, "status": self.status, "message": self.message, "result": self.data}


class ClusteringAgent:
    name = "Clustering Agent"

    def run(self, shipments: pd.DataFrame, clustered: pd.DataFrame) -> AgentResult:
        """Analyse clustering quality and consolidation opportunities."""
        time.sleep(0.1)
        n_clusters = clustered["cluster_id"].nunique()
        n_ships    = len(clustered)
        avg_size   = n_ships / max(n_clusters, 1)
        multi_ship_clusters = (clustered.groupby("cluster_id").size() > 1).sum()

        summary = {
            "total_shipments":        n_ships,
            "clusters_formed":        n_clusters,
            "avg_cluster_size":       round(avg_size, 1),
            "consolidation_clusters": int(multi_ship_clusters),
            "consolidation_rate_pct": round((multi_ship_clusters / n_clusters) * 100, 1) if n_clusters else 0,
        }

        msg = (
            f"Formed {n_clusters} clusters from {n_ships} shipments. "
            f"{multi_ship_clusters} clusters ({summary['consolidation_rate_pct']}%) have consolidation opportunities."
        )
        return AgentResult(self.name, "done", msg, summary)


class CapacityAgent:
    name = "Capacity Agent"

    def run(self, routes: List[Dict], fleet: pd.DataFrame) -> AgentResult:
        """Validate capacity constraints, flag overloaded routes."""
        time.sleep(0.1)
        overloaded = [r for r in routes if r["total_weight_kg"] > r["capacity_kg"]]
        ok         = len(routes) - len(overloaded)

        summary = {
            "total_routes":          len(routes),
            "valid_routes":          ok,
            "overloaded_routes":     len(overloaded),
            "avg_utilization_pct":   round(sum(r["utilization_pct"] for r in routes) / len(routes), 1) if routes else 0,
            "max_utilization_pct":   round(max((r["utilization_pct"] for r in routes), default=0), 1),
        }

        status  = "done" if not overloaded else "error"
        msg = (
            f"{ok}/{len(routes)} routes pass capacity check. "
            f"Avg utilization: {summary['avg_utilization_pct']}%."
        )
        if overloaded:
            msg += f" {len(overloaded)} overloaded routes detected — re-splitting recommended."
        return AgentResult(self.name, status, msg, summary)


class SLAAgent:
    name = "SLA Agent"

    def run(self, routes: List[Dict]) -> AgentResult:
        """Check SLA compliance — flag routes with deadline violations."""
        time.sleep(0.1)
        total_stops = sum(len(r["stops"]) for r in routes)
        violations  = sum(r["sla_violations"] for r in routes)
        compliant   = total_stops - violations
        comp_pct    = (compliant / total_stops * 100) if total_stops else 100

        # Priority breakdown of violations
        critical_violations = 0
        for r in routes:
            for stop in r["stops"]:
                if stop["priority"] in ("Critical", "High") and r["sla_violations"] > 0:
                    critical_violations += 1

        summary = {
            "total_stops":         total_stops,
            "sla_compliant":       compliant,
            "sla_violations":      violations,
            "compliance_pct":      round(comp_pct, 1),
            "critical_violations": critical_violations,
        }

        status = "done" if comp_pct >= 85 else "error"
        msg = (
            f"SLA compliance: {comp_pct:.1f}% ({compliant}/{total_stops} stops on time). "
            f"{critical_violations} critical/high priority violations."
        )
        return AgentResult(self.name, status, msg, summary)


class CarbonAgent:
    name = "Carbon Agent"

    def run(self, routes: List[Dict], before_co2: float) -> AgentResult:
        """Calculate total emissions and compare to pre-optimization baseline."""
        time.sleep(0.1)
        after_co2  = sum(r["total_co2_kg"] for r in routes)
        reduction  = before_co2 - after_co2
        reduc_pct  = (reduction / before_co2 * 100) if before_co2 else 0

        # Rank routes by CO2 per kg delivered (emission efficiency)
        ranked = sorted(routes, key=lambda r: r["total_co2_kg"] / max(r["total_weight_kg"], 1))
        most_efficient   = ranked[0]["vehicle_id"]  if ranked else "N/A"
        least_efficient  = ranked[-1]["vehicle_id"] if ranked else "N/A"

        summary = {
            "before_co2_kg":      round(before_co2, 2),
            "after_co2_kg":       round(after_co2, 2),
            "co2_saved_kg":       round(reduction, 2),
            "co2_reduction_pct":  round(reduc_pct, 1),
            "most_efficient_vehicle":  most_efficient,
            "least_efficient_vehicle": least_efficient,
            "avg_co2_per_route":  round(after_co2 / len(routes), 2) if routes else 0,
        }

        msg = (
            f"CO2 reduced by {summary['co2_saved_kg']:.1f} kg ({reduc_pct:.1f}%). "
            f"Most efficient vehicle: {most_efficient}."
        )
        return AgentResult(self.name, "done", msg, summary)


class AgentPipeline:
    """Orchestrates the 4 agents sequentially."""

    def __init__(self, progress_callback: Optional[Callable] = None):
        self.callback = progress_callback
        self.results: List[Dict] = []

    def _emit(self, result: AgentResult):
        self.results.append(result.to_dict())
        if self.callback:
            self.callback(result.to_dict())

    def run(
        self,
        shipments:   pd.DataFrame,
        clustered:   pd.DataFrame,
        routes:      List[Dict],
        fleet:       pd.DataFrame,
        before_co2:  float,
    ) -> List[Dict]:
        self.results = []

        # 1. Clustering Agent
        r1 = ClusteringAgent().run(shipments, clustered)
        self._emit(r1)

        # 2. Capacity Agent
        r2 = CapacityAgent().run(routes, fleet)
        self._emit(r2)

        # 3. SLA Agent
        r3 = SLAAgent().run(routes)
        self._emit(r3)

        # 4. Carbon Agent
        r4 = CarbonAgent().run(routes, before_co2)
        self._emit(r4)

        return self.results
