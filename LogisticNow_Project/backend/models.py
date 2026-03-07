"""
Pydantic data models for the Dynamic Load Consolidation Engine.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum


class PriorityLevel(str, Enum):
    LOW      = "Low"
    MEDIUM   = "Medium"
    HIGH     = "High"
    CRITICAL = "Critical"


class ShipmentType(str, Enum):
    NORMAL     = "Normal"
    FRAGILE    = "Fragile"
    PERISHABLE = "Perishable"
    HAZARDOUS  = "Hazardous"


class Shipment(BaseModel):
    shipment_id:          str
    pickup_lat:           float
    pickup_lon:           float
    delivery_lat:         float
    delivery_lon:         float
    weight_kg:            float
    shipment_volume_m3:   float
    deadline_hours:       float
    priority_level:       PriorityLevel
    service_time_minutes: int
    shipment_type:        ShipmentType
    cluster_id:           Optional[int] = None


class Vehicle(BaseModel):
    vehicle_id:               str
    vehicle_type:             str
    capacity_kg:              float
    fuel_type:                str
    fuel_efficiency_km_per_l: float
    depot_lat:                float
    depot_lon:                float
    vehicle_cost_per_km:      float
    max_route_time:           float
    emission_factor:          float


class RouteStop(BaseModel):
    shipment_id:  str
    delivery_lat: float
    delivery_lon: float
    weight_kg:    float
    service_time: int
    deadline:     float
    priority:     str
    ship_type:    str


class VehicleRoute(BaseModel):
    vehicle_id:       str
    vehicle_type:     str
    depot_lat:        float
    depot_lon:        float
    stops:            List[RouteStop]
    total_weight_kg:  float
    capacity_kg:      float
    utilization_pct:  float
    total_distance_km: float
    total_cost:       float
    total_co2_kg:     float
    route_time_hrs:   float
    sla_violations:   int
    color:            str


class OptimizationResult(BaseModel):
    routes:             List[VehicleRoute]
    total_shipments:    int
    trucks_used:        int
    total_cost:         float
    total_co2_kg:       float
    avg_utilization:    float
    sla_compliance_pct: float
    total_distance_km:  float
    unassigned:         List[str] = []


class ComparisonMetrics(BaseModel):
    before_trucks:      int
    after_trucks:       int
    before_cost:        float
    after_cost:         float
    before_co2:         float
    after_co2:          float
    before_utilization: float
    after_utilization:  float
    cost_reduction_pct: float
    co2_reduction_pct:  float
    truck_reduction_pct: float


class AgentStatus(BaseModel):
    agent:   str
    status:  Literal["pending", "running", "done", "error"]
    message: str
    result:  Optional[dict] = None


class OptimizeRequest(BaseModel):
    num_shipments: int = Field(default=50, ge=5, le=200)
    num_vehicles:  int = Field(default=10, ge=2, le=25)
    use_sample:    bool = True
