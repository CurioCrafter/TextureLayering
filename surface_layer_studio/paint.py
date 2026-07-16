"""Blender Texture Paint integration for grayscale layer masks."""

from __future__ import annotations

import bpy

from . import nodes
from .properties import active_layer


def _texture_paint_brush(context) -> bpy.types.Brush | None:
    image_paint = context.scene.tool_settings.image_paint
    return getattr(image_paint, "brush", None)


def _view3d_override(context):
    window = context.window or next(iter(context.window_manager.windows), None)
    if window is None:
        return None
    area = context.area if context.area and context.area.type == "VIEW_3D" else next(
        (candidate for candidate in window.screen.areas if candidate.type == "VIEW_3D"), None
    )
    if area is None:
        return None
    region = next((candidate for candidate in area.regions if candidate.type == "WINDOW"), None)
    if region is None:
        return None
    return {"window": window, "screen": window.screen, "area": area, "region": region, "space_data": area.spaces.active}


def activate_default_brush(context) -> bpy.types.Brush | None:
    brush = _texture_paint_brush(context)
    if brush is not None:
        return brush
    override = _view3d_override(context)
    if override is None:
        return None
    try:
        with context.temp_override(**override):
            bpy.ops.wm.tool_set_by_id(name="builtin.brush", space_type="VIEW_3D")
    except (RuntimeError, TypeError):
        return None
    brush = _texture_paint_brush(context)
    if brush is not None:
        return brush
    if bpy.app.background:
        # Essentials indexing is not safe without a live interactive asset UI
        # in Blender 4.5. The generic tool normally loads Paint Hard even in
        # background; if it does not, fail cleanly instead of invoking the
        # asset browser operator headlessly.
        return None
    try:
        with context.temp_override(**override):
            bpy.ops.brush.asset_activate(
                asset_library_type="ESSENTIALS",
                asset_library_identifier="",
                relative_asset_identifier=(
                    "brushes/essentials_brushes-mesh_texture.blend/Brush/Paint Hard"
                ),
                use_toggle=False,
            )
    except (RuntimeError, TypeError):
        return None
    return _texture_paint_brush(context)


def apply_brush_settings(context, *, quiet: bool = False) -> bpy.types.Brush | None:
    if context is None or context.scene is None or not hasattr(context.scene, "sls_tools"):
        return None
    settings = context.scene.sls_tools
    brush = _texture_paint_brush(context)
    if brush is None:
        return None
    color = {
        "REVEAL": (1.0, 1.0, 1.0),
        "HIDE": (0.0, 0.0, 0.0),
        "SOFTEN": (0.5, 0.5, 0.5),
    }[settings.brush_mode]
    assignments = {
        "color": color,
        "strength": settings.brush_strength,
        "size": settings.brush_size,
        "use_pressure_strength": settings.use_pressure_strength,
        "use_pressure_size": settings.use_pressure_size,
        "spacing": settings.brush_spacing,
        "use_airbrush": settings.use_airbrush,
    }
    for name, value in assignments.items():
        if hasattr(brush, name):
            try:
                setattr(brush, name, value)
            except (AttributeError, TypeError):
                if not quiet:
                    raise
    if hasattr(brush, "curve_preset"):
        try:
            brush.curve_preset = settings.brush_falloff
        except (AttributeError, TypeError):
            pass
    if hasattr(brush, "image_tool"):
        brush.image_tool = "SOFTEN" if settings.brush_mode == "SOFTEN" else "DRAW"
    if hasattr(brush, "blend"):
        brush.blend = "MIX"
    if hasattr(brush, "stroke_method"):
        try:
            brush.stroke_method = "AIRBRUSH" if settings.use_airbrush else "SPACE"
        except TypeError:
            pass
    return brush


def _material_slot_index(obj: bpy.types.Object, material: bpy.types.Material) -> int | None:
    for index, slot in enumerate(obj.material_slots):
        if slot.material == material:
            return index
    return None


def set_active_paint_image(
    context,
    obj: bpy.types.Object,
    material: bpy.types.Material,
    layer,
) -> bpy.types.Image:
    if layer.mask_image is None:
        raise RuntimeError("The active layer has no paint mask")
    if layer.locked:
        raise RuntimeError(f"Layer '{layer.name}' is locked")
    if not obj.data.uv_layers:
        raise RuntimeError("The mesh has no UV map; use Smart UV Project or create UVs first")
    if layer.uv_map:
        uv_layer = obj.data.uv_layers.get(layer.uv_map)
        if uv_layer is None:
            raise RuntimeError(f"UV map '{layer.uv_map}' no longer exists on {obj.name}")
        obj.data.uv_layers.active = uv_layer
        uv_layer.active_render = True

    slot_index = _material_slot_index(obj, material)
    if slot_index is None:
        raise RuntimeError("The layered material is not assigned to the active object")
    obj.active_material_index = slot_index

    node = nodes.mask_node(material, layer.uuid)
    if node is None:
        nodes.rebuild_material(material)
        node = nodes.mask_node(material, layer.uuid)
    if node is None:
        raise RuntimeError("The mask node could not be created; use Repair Stack")
    for candidate in material.node_tree.nodes:
        candidate.select = False
    node.select = True
    material.node_tree.nodes.active = node

    image_paint = context.scene.tool_settings.image_paint
    if hasattr(image_paint, "mode"):
        try:
            image_paint.mode = "IMAGE"
        except (AttributeError, TypeError):
            pass
    if hasattr(image_paint, "canvas"):
        try:
            image_paint.canvas = layer.mask_image
        except (AttributeError, TypeError):
            pass

    for area in context.screen.areas if context.screen else ():
        if area.type == "IMAGE_EDITOR":
            area.spaces.active.image = layer.mask_image
    apply_brush_settings(context, quiet=True)
    return layer.mask_image


def enter_mask_paint(context, *, selected_faces_only: bool = False) -> bpy.types.Image:
    obj = context.active_object
    if obj is None or obj.type != "MESH":
        raise RuntimeError("Select a mesh object first")
    material = obj.active_material
    layer = active_layer(material)
    if layer is None:
        raise RuntimeError("The active material has no active Surface Layer Studio layer")

    context.view_layer.objects.active = obj
    obj.select_set(True)
    image = set_active_paint_image(context, obj, material, layer)
    obj.data.use_paint_mask = selected_faces_only
    if obj.mode != "TEXTURE_PAINT":
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        result = bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
        if "FINISHED" not in result:
            raise RuntimeError("Blender could not enter Texture Paint mode")
    if activate_default_brush(context) is None:
        raise RuntimeError("Blender has no active Texture Paint brush; activate a paint brush asset and retry")
    image_paint = context.scene.tool_settings.image_paint
    if hasattr(image_paint, "detect_data") and not image_paint.detect_data():
        missing = []
        for property_name, label in (
            ("missing_uvs", "UVs"),
            ("missing_materials", "material"),
            ("missing_texture", "paint texture"),
            ("missing_stencil", "stencil"),
        ):
            if bool(getattr(image_paint, property_name, False)):
                missing.append(label)
        details = ", ".join(missing) if missing else "unknown paint data"
        raise RuntimeError(f"Blender cannot start mask painting; missing {details}")
    apply_brush_settings(context, quiet=True)
    return image


def set_soften_brush(context) -> bpy.types.Brush | None:
    context.scene.sls_tools.brush_mode = "SOFTEN"
    brush = activate_default_brush(context)
    if brush is None:
        return None
    return apply_brush_settings(context, quiet=True)


def finish_mask_paint(context) -> None:
    obj = context.active_object
    if obj is not None and obj.type == "MESH" and obj.mode == "TEXTURE_PAINT":
        bpy.ops.object.mode_set(mode="OBJECT")
