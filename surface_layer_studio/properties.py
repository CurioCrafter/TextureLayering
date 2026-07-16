"""Persistent Blender data model for Surface Layer Studio."""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup

from .constants import BLEND_MODES, MASK_RESOLUTIONS, PREVIEW_MODES


def _request_rebuild(self, _context) -> None:
    material = getattr(self, "id_data", None)
    if isinstance(material, bpy.types.Material) and getattr(material, "sls", None):
        from . import nodes

        nodes.request_rebuild(material)


def _brush_settings_changed(_self, context) -> None:
    if context is None:
        return
    from .paint import apply_brush_settings

    apply_brush_settings(context, quiet=True)


class SLS_Layer(PropertyGroup):
    uuid: StringProperty(name="Layer ID", options={"HIDDEN"})
    name: StringProperty(name="Name", default="Surface Layer", update=_request_rebuild)
    enabled: BoolProperty(
        name="Visible",
        description="Include this layer in the material composite",
        default=True,
        update=_request_rebuild,
    )
    solo: BoolProperty(
        name="Solo",
        description="Temporarily show only soloed layers",
        default=False,
        update=_request_rebuild,
    )
    locked: BoolProperty(
        name="Lock",
        description="Prevent mask painting and destructive mask operations",
        default=False,
    )
    pinned_base: BoolProperty(
        name="Pinned Base",
        description="Keep this base layer at the bottom of the stack",
        default=False,
        options={"HIDDEN"},
    )
    opacity: FloatProperty(
        name="Layer Opacity",
        description="Overall influence of this layer; separate from brush stroke opacity",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_request_rebuild,
    )
    blend_mode: EnumProperty(
        name="Color Blend",
        description="How this layer's base color combines with layers below it",
        items=BLEND_MODES,
        default="MIX",
        update=_request_rebuild,
    )

    mask_image: PointerProperty(
        name="Paint Mask",
        description="Grayscale UV image: white reveals, black hides, gray blends",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    invert_mask: BoolProperty(
        name="Invert Mask",
        description="Non-destructively invert how the mask is interpreted",
        default=False,
        update=_request_rebuild,
    )

    base_color_image: PointerProperty(
        name="Base Color",
        description="sRGB color or albedo texture",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    tint: FloatVectorProperty(
        name="Tint",
        description="Multiply the base-color texture by this color",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=_request_rebuild,
    )
    use_base_alpha: BoolProperty(
        name="Use Texture Alpha",
        description="Multiply the paint mask by the base-color texture alpha",
        default=False,
        update=_request_rebuild,
    )

    roughness_image: PointerProperty(
        name="Roughness",
        description="Non-color roughness texture",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    roughness: FloatProperty(
        name="Roughness",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_request_rebuild,
    )
    roughness_multiplier: FloatProperty(
        name="Roughness Multiplier",
        default=1.0,
        min=0.0,
        max=2.0,
        update=_request_rebuild,
    )

    metallic_image: PointerProperty(
        name="Metallic",
        description="Non-color metallic texture",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    metallic: FloatProperty(
        name="Metallic",
        default=0.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_request_rebuild,
    )
    metallic_multiplier: FloatProperty(
        name="Metallic Multiplier",
        default=1.0,
        min=0.0,
        max=2.0,
        update=_request_rebuild,
    )

    normal_image: PointerProperty(
        name="Normal",
        description="Non-color tangent-space normal map",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    normal_strength: FloatProperty(
        name="Normal Strength",
        description="Influence of this layer's normal texture in the blended tangent-space normal",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_request_rebuild,
    )
    normal_format: EnumProperty(
        name="Normal Format",
        description="DirectX maps have their green channel inverted for Blender",
        items=(
            ("OPENGL", "OpenGL (+Y)", "Blender-native green-channel direction"),
            ("DIRECTX", "DirectX (-Y)", "Invert the green channel before decoding"),
        ),
        default="OPENGL",
        update=_request_rebuild,
    )

    height_image: PointerProperty(
        name="Height",
        description="Non-color height map used for bump detail",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    height_strength: FloatProperty(
        name="Height Influence",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_request_rebuild,
    )
    ao_image: PointerProperty(
        name="Ambient Occlusion",
        description="Non-color occlusion map multiplied into this layer's base color",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    ao_strength: FloatProperty(
        name="AO Strength",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_request_rebuild,
    )

    emission_image: PointerProperty(
        name="Emission",
        description="sRGB emission texture for lamps, panels, and indicators",
        type=bpy.types.Image,
        update=_request_rebuild,
    )
    emission_tint: FloatVectorProperty(
        name="Emission Tint",
        subtype="COLOR",
        size=4,
        default=(1.0, 1.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        update=_request_rebuild,
    )
    emission_strength: FloatProperty(
        name="Emission Strength",
        default=0.0,
        min=0.0,
        max=100.0,
        soft_max=10.0,
        update=_request_rebuild,
    )

    uv_map: StringProperty(
        name="UV Map",
        description="UV map used by this layer and its mask",
        default="",
        update=_request_rebuild,
    )
    mapping_offset: FloatVectorProperty(
        name="Offset",
        description="UV offset for this layer's source textures; the paint mask stays aligned to the UV map",
        size=2,
        default=(0.0, 0.0),
        subtype="TRANSLATION",
        update=_request_rebuild,
    )
    mapping_scale: FloatVectorProperty(
        name="Scale",
        description="UV tiling scale for source textures; the paint mask remains one-to-one with the UV map",
        size=2,
        default=(1.0, 1.0),
        min=0.0001,
        soft_max=20.0,
        update=_request_rebuild,
    )
    mapping_rotation: FloatProperty(
        name="Rotation",
        description="Rotate source textures while keeping the paint mask fixed to the UV map",
        default=0.0,
        subtype="ANGLE",
        update=_request_rebuild,
    )


class SLS_MaterialSettings(PropertyGroup):
    enabled: BoolProperty(name="Managed Layer Stack", default=False, options={"HIDDEN"})
    stack_id: StringProperty(name="Stack ID", options={"HIDDEN"})
    layers: CollectionProperty(type=SLS_Layer)
    active_index: IntProperty(name="Active Layer", default=0, min=0, update=_request_rebuild)
    base_color: FloatVectorProperty(
        name="Undercoat Color",
        subtype="COLOR",
        size=4,
        default=(0.08, 0.08, 0.08, 1.0),
        min=0.0,
        max=1.0,
        update=_request_rebuild,
    )
    base_roughness: FloatProperty(
        name="Undercoat Roughness",
        default=0.55,
        min=0.0,
        max=1.0,
        update=_request_rebuild,
    )
    base_metallic: FloatProperty(
        name="Undercoat Metallic",
        default=0.0,
        min=0.0,
        max=1.0,
        update=_request_rebuild,
    )
    bump_distance: FloatProperty(
        name="Bump Distance",
        description="Overall distance used by layered height maps",
        default=0.05,
        min=0.0,
        soft_max=1.0,
        subtype="DISTANCE",
        update=_request_rebuild,
    )
    preview_mode: EnumProperty(
        name="Channel Preview",
        items=PREVIEW_MODES,
        default="COMPOSITE",
        update=_request_rebuild,
    )
    graph_version: IntProperty(name="Graph Version", default=0, options={"HIDDEN"})
    last_error: StringProperty(name="Stack Error", default="", options={"HIDDEN"})


class SLS_ToolSettings(PropertyGroup):
    mask_resolution: EnumProperty(
        name="Mask Resolution",
        description="Resolution for newly created masks",
        items=MASK_RESOLUTIONS,
        default="2048",
    )
    new_layer_fill: EnumProperty(
        name="New Overlay Mask",
        description="New overlays normally start hidden so you reveal them with paint",
        items=(
            ("BLACK", "Hidden (Black)", "Start hidden and reveal with white paint"),
            ("GRAY", "Half (Gray)", "Start at 50% visibility"),
            ("WHITE", "Visible (White)", "Start fully visible and hide with black paint"),
        ),
        default="BLACK",
    )
    auto_pack_masks: BoolProperty(
        name="Pack New Masks",
        description="Pack newly generated masks into the blend file to prevent data loss",
        default=True,
    )
    brush_mode: EnumProperty(
        name="Brush Mode",
        items=(
            ("REVEAL", "Reveal", "Paint white to reveal the active layer"),
            ("HIDE", "Hide", "Paint black to hide the active layer"),
            ("SOFTEN", "Soften", "Use Blender's native soften image-paint mode"),
        ),
        default="REVEAL",
        update=_brush_settings_changed,
    )
    brush_strength: FloatProperty(
        name="Stroke Opacity",
        description="Opacity added or removed by each stroke; separate from layer opacity",
        default=0.5,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=_brush_settings_changed,
    )
    brush_size: IntProperty(
        name="Radius",
        default=80,
        min=1,
        max=5000,
        soft_max=500,
        subtype="PIXEL",
        update=_brush_settings_changed,
    )
    brush_falloff: EnumProperty(
        name="Falloff",
        items=(
            ("SMOOTH", "Soft", "Smooth feathered brush edge"),
            ("SHARP", "Firm", "Sharper brush edge"),
            ("CONSTANT", "Hard", "Hard-edged brush"),
        ),
        default="SMOOTH",
        update=_brush_settings_changed,
    )
    use_pressure_strength: BoolProperty(
        name="Pressure Opacity",
        default=True,
        update=_brush_settings_changed,
    )
    use_pressure_size: BoolProperty(
        name="Pressure Radius",
        default=True,
        update=_brush_settings_changed,
    )
    brush_spacing: IntProperty(
        name="Spacing",
        default=10,
        min=1,
        max=1000,
        subtype="PERCENTAGE",
        update=_brush_settings_changed,
    )
    use_airbrush: BoolProperty(
        name="Airbrush",
        default=False,
        update=_brush_settings_changed,
    )
    export_directory: StringProperty(
        name="Mask Folder",
        description="Folder used by Export All Masks",
        subtype="DIR_PATH",
        default="//textures/masks/",
    )
    show_advanced: BoolProperty(name="Advanced", default=False)
    previous_object_mode: StringProperty(name="Previous Mode", default="OBJECT", options={"HIDDEN"})
    previous_preview_mode: StringProperty(name="Previous Preview", default="COMPOSITE", options={"HIDDEN"})


def active_layer(material: bpy.types.Material | None) -> SLS_Layer | None:
    if material is None or not hasattr(material, "sls"):
        return None
    settings = material.sls
    if not settings.enabled or not settings.layers:
        return None
    index = min(max(settings.active_index, 0), len(settings.layers) - 1)
    return settings.layers[index]


@persistent
def _flush_before_save(_filepath) -> None:
    from . import nodes

    nodes.flush_pending_rebuilds()


_CLASSES = (SLS_Layer, SLS_MaterialSettings, SLS_ToolSettings)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Material.sls = PointerProperty(type=SLS_MaterialSettings)
    bpy.types.Scene.sls_tools = PointerProperty(type=SLS_ToolSettings)
    if _flush_before_save not in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.append(_flush_before_save)


def unregister() -> None:
    from . import nodes

    nodes.cancel_pending_rebuilds()
    if _flush_before_save in bpy.app.handlers.save_pre:
        bpy.app.handlers.save_pre.remove(_flush_before_save)
    if hasattr(bpy.types.Scene, "sls_tools"):
        del bpy.types.Scene.sls_tools
    if hasattr(bpy.types.Material, "sls"):
        del bpy.types.Material.sls
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
