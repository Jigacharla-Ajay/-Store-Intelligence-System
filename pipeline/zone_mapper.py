"""
Zone mapper — determines which store zone a detected person's centroid is in.

Uses point-in-polygon (ray casting) to check if a (cx, cy) coordinate
falls within any defined zone polygon for the given camera.
"""

from pipeline.store_layout import STORE_LAYOUT


def point_in_polygon(x: float, y: float, polygon: list) -> bool:
    """
    Ray-casting algorithm to check if point (x,y) is inside a polygon.
    polygon: list of [x, y] vertices.
    """
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def get_zone(camera_id: str, cx: float, cy: float) -> str:
    """
    Determine which zone a centroid (cx, cy) falls in for the given camera.
    Returns zone_id string or None if not in any defined zone.
    """
    cam_config = STORE_LAYOUT["cameras"].get(camera_id)
    if cam_config is None:
        return None

    for zone_id, zone_data in cam_config["zones"].items():
        if point_in_polygon(cx, cy, zone_data["polygon"]):
            return zone_id

    return None


def get_camera_type(camera_id: str) -> str:
    """Get the camera type (entry_exit, main_floor, billing, overview)."""
    cam = STORE_LAYOUT["cameras"].get(camera_id)
    return cam["type"] if cam else "unknown"
