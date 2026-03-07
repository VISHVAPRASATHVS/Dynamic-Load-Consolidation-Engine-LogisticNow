"""
Clustering module — groups nearby delivery locations using DBSCAN (geographic)
with K-Means fallback. Outputs cluster_id per shipment.
"""
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.preprocessing import StandardScaler


EARTH_RADIUS_KM = 6371.0


def cluster_shipments(
    df: pd.DataFrame,
    eps_km: float = 150.0,
    min_samples: int = 2,
    n_clusters: int = None
) -> pd.DataFrame:
    """
    Cluster shipments by DELIVERY location using DBSCAN (geo-aware).
    Falls back to K-Means if DBSCAN produces poor clusters.

    Args:
        df: Shipment DataFrame with delivery_lat, delivery_lon columns
        eps_km: DBSCAN neighbourhood radius in km
        min_samples: Minimum shipments per cluster
        n_clusters: If set, forces K-Means with this many clusters

    Returns:
        df with added 'cluster_id' column (noise = -1 reassigned to nearest)
    """
    df = df.copy()
    coords = df[["delivery_lat", "delivery_lon"]].values

    if n_clusters:
        # Force K-Means
        km = KMeans(n_clusters=min(n_clusters, len(df)), random_state=42, n_init=10)
        df["cluster_id"] = km.fit_predict(coords)
        return df

    # DBSCAN with haversine distance (expects radians)
    coords_rad = np.radians(coords)
    eps_rad    = eps_km / EARTH_RADIUS_KM

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine", algorithm="ball_tree")
    labels = db.fit_predict(coords_rad)

    n_clusters_found = len(set(labels)) - (1 if -1 in labels else 0)

    # If DBSCAN found too few clusters (< 2), fall back to KMeans
    if n_clusters_found < 2:
        k = max(2, len(df) // 8)
        km = KMeans(n_clusters=min(k, len(df)), random_state=42, n_init=10)
        labels = km.fit_predict(coords)
        df["cluster_id"] = labels
        return df

    # Handle noise points (-1) — assign to nearest cluster centroid
    if -1 in labels:
        valid_mask    = labels != -1
        valid_coords  = coords[valid_mask]
        valid_labels  = labels[valid_mask]

        for idx in np.where(labels == -1)[0]:
            pt = coords[idx]
            # find nearest labelled point
            dists  = np.linalg.norm(valid_coords - pt, axis=1)
            labels[idx] = valid_labels[np.argmin(dists)]

    df["cluster_id"] = labels
    return df


def get_cluster_summary(df: pd.DataFrame) -> dict:
    """Return per-cluster statistics."""
    summary = {}
    for cid, grp in df.groupby("cluster_id"):
        summary[int(cid)] = {
            "count":           len(grp),
            "total_weight_kg": float(grp["weight_kg"].sum()),
            "avg_deadline_h":  float(grp["deadline_hours"].mean()),
            "center_lat":      float(grp["delivery_lat"].mean()),
            "center_lon":      float(grp["delivery_lon"].mean()),
            "priorities":      grp["priority_level"].value_counts().to_dict(),
        }
    return summary
