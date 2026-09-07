"""Shared operator helpers."""

from __future__ import annotations

from uuid import uuid4
from time import monotonic

import bpy

from .. import images, nodes
from ..properties import active_layer
from ..uv import active_uv_name


def active_mesh(context) -> bpy.types.Object | None:
    obj = context.active_object
    return obj if obj is not None and obj.type == "MESH" else None


def managed_material(context) -> bpy.types.Material | None:
    obj = active_mesh(context)
    material = obj.active_material if obj else None
    if material is None or not hasattr(material, "sls") or not material.sls.enabled:
        return None
    return material


def mask_size(context) -> int:
    return int(context.scene.sls_tools.mask_resolution)


def add_layer(
    context,
    material: bpy.types.Material,
    name: str,
    *,
    fill: str = "BLACK",
    pinned: bool = False,
    to_top: bool = True,
):
    settings = material.sls
    layer = settings.layers.add()
    layer.uuid = str(uuid4())
    layer.name = name
    layer.pinned_base = pinned
    layer.uv_map = active_uv_name(context.active_object)
    layer.mask_image = images.create_mask(
        material,
        name,
        layer.uuid,
        mask_size(context),
        fill,
        pack=context.scene.sls_tools.auto_pack_masks,
    )
    source_index = len(settings.layers) - 1
    if to_top and not pinned and source_index > 0:
        settings.layers.move(source_index, 0)
        settings.active_index = 0
        layer = settings.layers[0]
    else:
        settings.active_index = source_index
    return layer


def copy_layer_properties(source, target) -> None:
    excluded = {"rna_type", "uuid", "mask_image", "pinned_base", "desk"}
    for prop in source.bl_rna.properties:
        name = prop.identifier
        if name in excluded or prop.is_readonly:
            continue
        try:
            value = getattr(source, name)
            setattr(target, name, value[:]) if getattr(prop, "is_array", False) else setattr(target, name, value)
        except (AttributeError, TypeError, ValueError):
            continue

    if hasattr(source, "desk") and hasattr(target, "desk"):
        for prop in source.desk.bl_rna.properties:
            if prop.identifier in {"rna_type", "previous_image", "previous_slot", "previous_normal_format"} or prop.is_readonly:
                continue
            value = getattr(source.desk, prop.identifier)
            setattr(target.desk, prop.identifier, value[:] if getattr(prop, "is_array", False) else value)


def material_slot_index(obj: bpy.types.Object, material: bpy.types.Material) -> int | None:
    for index, slot in enumerate(obj.material_slots):
        if slot.material == material:
            return index
    return None


def ensure_material_slot(obj: bpy.types.Object, material: bpy.types.Material) -> int:
    index = material_slot_index(obj, material)
    if index is not None:
        return index
    obj.data.materials.append(material)
    return len(obj.material_slots) - 1


def rebuild(material: bpy.types.Material) -> None:
    nodes.rebuild_material(material)


def require_active_layer(context):
    material = managed_material(context)
    layer = active_layer(material)
    if material is None or layer is None:
        return None, None
    return material, layer


_USER_CACHE = {}


def shared_material_objects(material):
    """Count objects, not orphan mesh datablocks; briefly cache for heavy scenes."""
    if material is None:
        return 0
    if material.users <= 1:
        return material.users
    key = material.as_pointer()
    now = monotonic()
    previous = _USER_CACHE.get(key)
    if previous and now - previous[0] < .5:
        return previous[1]
    count = sum(any(slot.material == material for slot in obj.material_slots) for obj in bpy.data.objects)
    if len(_USER_CACHE) > 256:
        _USER_CACHE.clear()
    _USER_CACHE[key] = (now, count)
    return count
