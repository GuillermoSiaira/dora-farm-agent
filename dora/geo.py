"""Geographical operations: geodesic polygon area, bounding box region lookup, and field_from_map tool.

No external GIS dependencies: uses pure Python and spherical geometry on WGS84.
"""
from __future__ import annotations

import math
from typing import Any

from .scenario import ScenarioError

WGS84_RADIUS_METERS = 6_371_008.8

# Bounding boxes: (min_lon, max_lon, min_lat, max_lat)
REGION_BOUNDING_BOXES = {
    "southeast_buenos_aires": (-61.5, -56.5, -39.5, -36.0),
    "pampas_core": (-63.0, -59.0, -35.0, -32.5),
    "iowa": (-96.7, -90.1, 40.3, 43.6),
    "mato_grosso": (-61.0, -50.0, -18.0, -9.0),
}


def polygon_area_ha(coords: list[list[float]] | list[tuple[float, float]]) -> float:
    """Geodesic area of a lon/lat polygon in hectares using the spherical excess formula.

    WGS84 mean radius: 6,371,008.8 m.
    coords: sequence of [lon, lat] pairs.
    """
    if len(coords) < 3:
        return 0.0

    pts = coords[:-1] if coords[0] == coords[-1] else coords
    n = len(pts)
    if n < 3:
        return 0.0

    total = 0.0
    for i in range(n):
        lon1, lat1 = pts[i]
        lon2, lat2 = pts[(i + 1) % n]
        lam1, phi1 = math.radians(lon1), math.radians(lat1)
        lam2, phi2 = math.radians(lon2), math.radians(lat2)
        total += (lam2 - lam1) * (2.0 + math.sin(phi1) + math.sin(phi2))

    area_m2 = abs(total) * (WGS84_RADIUS_METERS ** 2) / 2.0
    return area_m2 / 10_000.0


def region_for_point(lon: float, lat: float) -> str | None:
    """Return region name ('southeast_buenos_aires' or 'iowa') for given lon/lat, or None."""
    for reg, (min_lon, max_lon, min_lat, max_lat) in REGION_BOUNDING_BOXES.items():
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            return reg
    return None


def _ccw(a: list[float], b: list[float], c: list[float]) -> float:
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a: list[float], b: list[float], c: list[float], d: list[float]) -> bool:
    ccw_c = _ccw(a, b, c)
    ccw_d = _ccw(a, b, d)
    ccw_a = _ccw(c, d, a)
    ccw_b = _ccw(c, d, b)
    return (ccw_c * ccw_d < -1e-12) and (ccw_a * ccw_b < -1e-12)


def validate_polygon_coords(coords: list[list[float]]) -> None:
    """Validate that coordinates form a valid, closed, non-self-intersecting polygon."""
    if not isinstance(coords, (list, tuple)) or len(coords) < 4:
        raise ScenarioError("A polygon must have at least 4 coordinates with matching start and end.")

    first = coords[0]
    last = coords[-1]
    if len(first) < 2 or len(last) < 2:
        raise ScenarioError("Each coordinate must be a [lon, lat] pair.")

    if abs(first[0] - last[0]) > 1e-9 or abs(first[1] - last[1]) > 1e-9:
        raise ScenarioError("The polygon is open: first and last coordinates must match.")

    # Check distinct vertices count
    pts = coords[:-1]
    if len(pts) < 3:
        raise ScenarioError("The polygon must have at least 3 distinct vertices.")

    # Check for self-intersection
    edges = [(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]
    m = len(edges)
    for i in range(m):
        for j in range(i + 1, m):
            if abs(i - j) <= 1 or (i == 0 and j == m - 1):
                continue
            if _segments_intersect(edges[i][0], edges[i][1], edges[j][0], edges[j][1]):
                raise ScenarioError("The polygon is self-intersecting.")


def parse_geojson_polygon(polygon: Any) -> list[list[float]]:
    """Extract coordinate ring from GeoJSON Polygon, Feature, or list of coordinates."""
    if isinstance(polygon, list):
        if polygon and isinstance(polygon[0], list) and isinstance(polygon[0][0], list):
            return polygon[0]
        return polygon

    if isinstance(polygon, dict):
        if polygon.get("type") == "Feature":
            geometry = polygon.get("geometry", {})
            return parse_geojson_polygon(geometry)
        if polygon.get("type") == "Polygon":
            coordinates = polygon.get("coordinates", [])
            if coordinates and isinstance(coordinates, list):
                return coordinates[0]

    raise ScenarioError("Invalid polygon input: expected GeoJSON Polygon or list of coordinates.")


def field_from_map(polygon: dict | list) -> dict:
    """Calculate area in hectares, region, and centroid from a drawn field polygon (GeoJSON)."""
    coords = parse_geojson_polygon(polygon)
    validate_polygon_coords(coords)

    pts = coords[:-1]
    centroid_lon = sum(p[0] for p in pts) / len(pts)
    centroid_lat = sum(p[1] for p in pts) / len(pts)
    centroid = [round(centroid_lon, 5), round(centroid_lat, 5)]

    area_ha = polygon_area_ha(coords)
    region = region_for_point(centroid_lon, centroid_lat)

    res = {
        "area_ha": round(area_ha, 1),
        "region": region,
        "centroid": centroid,
    }
    if region is None:
        res["message"] = (
            f"Point ({centroid_lon:.3f}, {centroid_lat:.3f}) is outside supported regions "
            "(Southeast Buenos Aires and Iowa)."
        )
    else:
        res["message"] = f"Field located in {region}."
    return res
