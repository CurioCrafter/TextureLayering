"""UV and material-surface diagnostics used by operators and UI."""

from __future__ import annotations

from collections import Counter


def active_uv_name(obj) -> str:
    layers = getattr(getattr(obj, "data", None), "uv_layers", None)
    if not layers:
        return ""
    for layer in layers:
        if getattr(layer, "active_render", False):
            return layer.name
    active = layers.active
    return active.name if active else layers[0].name


def _polygon_uv_area(mesh, uv_layer, polygon) -> float:
    coords = [uv_layer.data[index].uv for index in polygon.loop_indices]
    if len(coords) < 3:
        return 0.0
    doubled = 0.0
    for index, point in enumerate(coords):
        following = coords[(index + 1) % len(coords)]
        doubled += point.x * following.y - following.x * point.y
    return abs(doubled) * 0.5


def audit_uv(obj, uv_name: str = "") -> dict[str, object]:
    result: dict[str, object] = {
        "ok": False,
        "uv_name": "",
        "face_count": 0,
        "zero_area_faces": 0,
        "outside_tile_faces": 0,
        "exact_overlap_groups": 0,
        "message": "Select a mesh object",
    }
    if obj is None or obj.type != "MESH":
        return result
    mesh = obj.data
    result["face_count"] = len(mesh.polygons)
    if not mesh.uv_layers:
        result["message"] = "No UV map. Create or unwrap UVs before painting."
        return result
    uv_layer = mesh.uv_layers.get(uv_name) if uv_name else None
    uv_layer = uv_layer or mesh.uv_layers.active or mesh.uv_layers[0]
    result["uv_name"] = uv_layer.name

    signatures: list[tuple[tuple[float, float], ...]] = []
    zero_area = 0
    outside = 0
    for polygon in mesh.polygons:
        coords = [uv_layer.data[index].uv for index in polygon.loop_indices]
        if _polygon_uv_area(mesh, uv_layer, polygon) <= 1.0e-10:
            zero_area += 1
        if any(point.x < 0.0 or point.x > 1.0 or point.y < 0.0 or point.y > 1.0 for point in coords):
            outside += 1
        signatures.append(tuple(sorted((round(point.x, 6), round(point.y, 6)) for point in coords)))

    counts = Counter(signatures)
    overlap_groups = sum(1 for count in counts.values() if count > 1)
    result.update(
        {
            "zero_area_faces": zero_area,
            "outside_tile_faces": outside,
            "exact_overlap_groups": overlap_groups,
            "ok": len(mesh.polygons) > 0 and zero_area < len(mesh.polygons),
        }
    )
    warnings: list[str] = []
    if zero_area:
        warnings.append(f"{zero_area} zero-area UV face(s)")
    if outside:
        warnings.append(f"{outside} face(s) outside the 0-1 tile")
    if overlap_groups:
        warnings.append(f"{overlap_groups} exact overlap group(s)")
    result["message"] = ", ".join(warnings) if warnings else "UV map is ready for 0-1 texture painting"
    return result


def shared_material_users(material) -> list[str]:
    if material is None:
        return []
    users: list[str] = []
    import bpy

    for obj in bpy.data.objects:
        if obj.type == "MESH" and any(slot.material == material for slot in obj.material_slots):
            users.append(obj.name)
    return users
