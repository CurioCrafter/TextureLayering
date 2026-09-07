"""Polished View3D and Image Editor interface."""

from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from . import nodes
from .images import estimated_memory_mb
from .properties import active_layer
from .uv import active_uv_name
from .operators.common import shared_material_objects


def _active_mesh(context):
    obj = context.active_object
    return obj if obj is not None and obj.type == "MESH" else None


def _material(context):
    obj = _active_mesh(context)
    return obj.active_material if obj else None


def _managed_material(context):
    material = _material(context)
    return material if material is not None and hasattr(material, "sls") and material.sls.enabled else None


def _draw_setup(layout, context) -> None:
    obj = _active_mesh(context)
    box = layout.box()
    if obj is None:
        box.label(text="Select a mesh object to begin", icon="MESH_DATA")
        return
    box.operator("sls.desk_workspace", icon="WINDOW")
    box.label(text="Build a paintable PBR layer stack", icon="MATERIAL")
    box.label(text="Existing materials are copied by default.")
    if obj.mode == "EDIT":
        box.label(text="The new stack will be assigned to selected faces.", icon="INFO")
    column = box.column(align=True)
    column.scale_y = 1.25
    column.operator("sls.setup_material", icon="ADD")
    column.operator("sls.ship_starter", icon="MODIFIER")


class SLS_UL_layers(UIList):
    def draw_item(self, _context, layout, _data, item, _icon, _active_data, _active_propname, _index):
        layer = item
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            row = layout.row(align=True)
            row.prop(
                layer,
                "enabled",
                text="",
                icon="HIDE_OFF" if layer.enabled else "HIDE_ON",
                emboss=False,
            )
            row.prop(layer, "name", text="", emboss=False)
            if layer.mask_image is None:
                row.label(text="", icon="ERROR")
            elif layer.mask_image.is_dirty:
                row.label(text="", icon="IMAGE_DATA")
            row.prop(layer, "opacity", text="", slider=True)
            row.prop(
                layer,
                "locked",
                text="",
                icon="LOCKED" if layer.locked else "UNLOCKED",
                emboss=False,
            )
        else:
            layout.alignment = "CENTER"
            layout.label(text="", icon="IMAGE_DATA" if layer.mask_image else "ERROR")


class SLS_PT_layers(Panel):
    bl_label = "Surface Layer Studio"
    bl_idname = "SLS_PT_layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Surface Layers"

    def draw(self, context):
        layout = self.layout
        material = _managed_material(context)
        if material is None:
            _draw_setup(layout, context)
            return

        layout.operator("sls.desk_workspace", icon="WINDOW")
        settings = material.sls
        header = layout.row(align=True)
        header.label(text=material.name, icon="MATERIAL")
        healthy, message = nodes.graph_health(material)
        header.label(text="", icon="CHECKMARK" if healthy else "ERROR")
        if settings.last_error:
            error = layout.box()
            error.alert = True
            error.label(text="Stack error", icon="ERROR")
            error.label(text=settings.last_error[:90])
            error.operator("sls.repair_stack", icon="FILE_REFRESH")
        elif not healthy:
            warning = layout.box()
            warning.alert = True
            warning.label(text=message, icon="ERROR")
            warning.operator("sls.repair_stack", icon="FILE_REFRESH")

        object_users = shared_material_objects(material)
        if object_users > 1:
            shared = layout.box()
            shared.alert = True
            shared.label(text=f"Shared material ({object_users} objects)", icon="LINKED")
            shared.label(text="Painting may affect another object.")
            shared.operator("sls.make_single_user", icon="DUPLICATE")

        row = layout.row()
        row.template_list("SLS_UL_layers", "", settings, "layers", settings, "active_index", rows=6)
        controls = row.column(align=True)
        controls.operator("sls.add_layer", text="", icon="ADD")
        controls.operator("sls.remove_layer", text="", icon="REMOVE")
        controls.separator()
        controls.operator("sls.duplicate_layer", text="", icon="DUPLICATE")
        controls.separator()
        up = controls.operator("sls.move_layer", text="", icon="TRIA_UP")
        up.direction = "UP"
        down = controls.operator("sls.move_layer", text="", icon="TRIA_DOWN")
        down.direction = "DOWN"

        actions = layout.row(align=True)
        actions.operator("sls.import_pbr_set", text="Import PBR Set", icon="FILE_FOLDER")
        actions.operator("sls.ship_starter", text="Ship Starter", icon="MODIFIER")

        layer = active_layer(material)
        if layer is None:
            return
        box = layout.box()
        box.prop(layer, "name")
        row = box.row(align=True)
        row.prop(layer, "enabled", toggle=True)
        row.prop(layer, "solo", toggle=True)
        row.prop(layer, "locked", toggle=True)
        box.prop(layer, "opacity", slider=True)
        box.prop(layer, "blend_mode")
        if layer.pinned_base:
            box.label(text="Pinned base layer", icon="LOCKED")
        else:
            box.label(text="Mask paint: white reveals, black hides", icon="INFO")


class SLS_PT_textures(Panel):
    bl_label = "Layer Textures & PBR"
    bl_idname = "SLS_PT_textures"
    bl_parent_id = "SLS_PT_layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Surface Layers"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _managed_material(context) is not None

    def draw(self, context):
        layout = self.layout
        material = _managed_material(context)
        layer = active_layer(material)
        obj = _active_mesh(context)
        if layer is None or obj is None:
            return

        layout.label(text=f"Editing: {layer.name}", icon="IMAGE_DATA")
        base = layout.box()
        base.label(text="Base Color", icon="IMAGE_DATA")
        base.template_ID(layer, "base_color_image", open="image.open")
        base.prop(layer, "tint")
        if layer.base_color_image:
            base.prop(layer, "use_base_alpha")

        surface = layout.box()
        surface.label(text="Surface Response", icon="MATERIAL")
        surface.template_ID(layer, "roughness_image", open="image.open")
        surface.prop(layer, "roughness_multiplier" if layer.roughness_image else "roughness")
        surface.template_ID(layer, "metallic_image", open="image.open")
        surface.prop(layer, "metallic_multiplier" if layer.metallic_image else "metallic")

        detail = layout.box()
        detail.label(text="Normal & Height", icon="NORMALS_FACE")
        detail.template_ID(layer, "normal_image", open="image.open")
        if layer.normal_image:
            row = detail.row(align=True)
            row.prop(layer, "normal_strength")
            row.prop(layer, "normal_format", text="")
        detail.template_ID(layer, "height_image", open="image.open")
        if layer.height_image:
            detail.prop(layer, "height_strength")

        extra = layout.box()
        extra.label(text="AO & Emission", icon="LIGHT")
        extra.template_ID(layer, "ao_image", open="image.open")
        if layer.ao_image:
            extra.prop(layer, "ao_strength")
        extra.template_ID(layer, "emission_image", open="image.open")
        extra.prop(layer, "emission_tint")
        extra.prop(layer, "emission_strength")

        mapping = layout.box()
        mapping.label(text="UV Mapping", icon="UV")
        if obj.data.uv_layers:
            mapping.prop_search(layer, "uv_map", obj.data, "uv_layers", text="UV Map")
        else:
            mapping.label(text="No UV map on object", icon="ERROR")
        mapping.prop(layer, "mapping_offset")
        mapping.prop(layer, "mapping_scale")
        mapping.prop(layer, "mapping_rotation")


class SLS_PT_paint(Panel):
    bl_label = "Paint Layer Mask"
    bl_idname = "SLS_PT_paint"
    bl_parent_id = "SLS_PT_layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Surface Layers"

    @classmethod
    def poll(cls, context):
        return _managed_material(context) is not None

    def draw(self, context):
        layout = self.layout
        material = _managed_material(context)
        layer = active_layer(material)
        obj = _active_mesh(context)
        if layer is None or obj is None:
            return
        tools = context.scene.sls_tools

        status = layout.box()
        status.label(text=f"Painting mask: {layer.name}", icon="BRUSH_DATA")
        if layer.locked:
            status.alert = True
            status.label(text="Layer is locked", icon="LOCKED")
        elif layer.mask_image is None:
            status.alert = True
            status.label(text="No mask image", icon="ERROR")
        else:
            image = layer.mask_image
            status.label(text=f"{image.name}  •  {image.size[0]} × {image.size[1]}")
            status.label(text=f"Estimated mask memory: {estimated_memory_mb(image):.1f} MB")
            if image.is_dirty:
                status.label(text="Unsaved pixel changes", icon="IMAGE_DATA")

        brush = layout.box()
        brush.label(text="Brush", icon="BRUSH_DATA")
        row = brush.row(align=True)
        reveal = row.operator("sls.set_brush_mode", text="Reveal", depress=tools.brush_mode == "REVEAL")
        reveal.mode = "REVEAL"
        hide = row.operator("sls.set_brush_mode", text="Hide", depress=tools.brush_mode == "HIDE")
        hide.mode = "HIDE"
        row.operator("sls.select_soften_tool", text="Soften", depress=tools.brush_mode == "SOFTEN")
        brush.prop(tools, "brush_strength", slider=True)
        brush.prop(tools, "brush_size")
        brush.prop(tools, "brush_falloff")
        pressure = brush.row(align=True)
        pressure.prop(tools, "use_pressure_strength", toggle=True)
        pressure.prop(tools, "use_pressure_size", toggle=True)
        if tools.show_advanced:
            brush.prop(tools, "brush_spacing")
            brush.prop(tools, "use_airbrush")

        paint = layout.column(align=True)
        paint.scale_y = 1.3
        if obj.mode == "TEXTURE_PAINT":
            paint.operator("sls.finish_paint", icon="CHECKMARK")
        else:
            paint.operator("sls.start_paint", icon="BRUSH_DATA")
        secondary = layout.row(align=True)
        secondary.operator("sls.activate_mask", text="Target Mask", icon="IMAGE_DATA")
        secondary.operator("sls.paint_selected_faces", text="Selected Faces", icon="FACESEL")

        mask = layout.box()
        mask.label(text="Mask Image", icon="IMAGE_DATA")
        mask.template_ID(layer, "mask_image", open="image.open")
        mask.prop(layer, "invert_mask")
        row = mask.row(align=True)
        black = row.operator("sls.fill_mask", text="Black")
        black.fill = "BLACK"
        gray = row.operator("sls.fill_mask", text="Gray")
        gray.fill = "GRAY"
        white = row.operator("sls.fill_mask", text="White")
        white.fill = "WHITE"
        mask.prop(tools, "mask_resolution")
        row = mask.row(align=True)
        row.operator("sls.new_mask", text="New Mask", icon="ADD")
        row.operator("sls.resize_mask", text="Resize", icon="FULLSCREEN_ENTER")


class SLS_PT_surface_uv(Panel):
    bl_label = "Surface Scope & UV"
    bl_idname = "SLS_PT_surface_uv"
    bl_parent_id = "SLS_PT_layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Surface Layers"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _managed_material(context) is not None

    def draw(self, context):
        layout = self.layout
        obj = _active_mesh(context)
        if obj is None:
            return

        scope = layout.box()
        scope.label(text="1. Material assignment chooses surfaces", icon="MATERIAL")
        if obj.mode == "EDIT":
            scope.operator("sls.assign_selected_faces", icon="FACESEL")
        else:
            scope.label(text="Enter Edit Mode and select faces to assign.", icon="INFO")
        scope.operator("sls.select_assigned_faces", icon="RESTRICT_SELECT_OFF")

        guard = layout.box()
        guard.label(text="2. Each layer mask controls local coverage", icon="IMAGE_DATA")
        guard.label(text="3. Selected Faces prevents stray new strokes", icon="BRUSH_DATA")
        guard.operator("sls.paint_selected_faces", icon="FACESEL")

        uv_box = layout.box()
        uv_name = active_uv_name(obj)
        if uv_name:
            uv_box.label(text=f"Render UV: {uv_name}", icon="UV")
        else:
            uv_box.alert = True
            uv_box.label(text="No UV map — painting is unavailable", icon="ERROR")
        if "sls_uv_audit" in obj:
            uv_box.label(text=str(obj["sls_uv_audit"])[:100])
        row = uv_box.row(align=True)
        row.operator("sls.uv_audit", icon="CHECKMARK")
        row.operator("sls.open_uv_workspace", icon="UV")
        uv_box.operator("sls.smart_uv_project", icon="MOD_UVPROJECT")
        uv_box.label(text="Smart Project is explicit and changes UVs.", icon="INFO")
        uv_box.label(text="This release paints regular 0–1 masks; UDIM masks are not created.")


class SLS_PT_files_output(Panel):
    bl_label = "Files, Preview & Stack"
    bl_idname = "SLS_PT_files_output"
    bl_parent_id = "SLS_PT_layers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Surface Layers"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _managed_material(context) is not None

    def draw(self, context):
        layout = self.layout
        material = _managed_material(context)
        tools = context.scene.sls_tools
        assert material is not None

        preview = layout.box()
        preview.label(text="Channel Preview", icon="SHADING_TEXTURE")
        preview.prop(material.sls, "preview_mode", text="")
        if material.sls.preview_mode != "COMPOSITE":
            preview.alert = True
            preview.label(text="Preview mode is not the final material", icon="INFO")

        files = layout.box()
        files.label(text="Protect Painted Work", icon="FILE_TICK")
        files.prop(tools, "auto_pack_masks")
        files.operator("sls.pack_masks", icon="PACKAGE")
        files.prop(tools, "export_directory")
        files.operator("sls.export_masks", icon="FILE_TICK")
        files.operator("sls.pack_sources", icon="PACKAGE")

        advanced = layout.box()
        advanced.prop(tools, "show_advanced", toggle=True)
        if tools.show_advanced:
            advanced.prop(material.sls, "base_color")
            advanced.prop(material.sls, "base_roughness")
            advanced.prop(material.sls, "base_metallic")
            advanced.prop(material.sls, "bump_distance")
            advanced.operator("sls.repair_stack", icon="FILE_REFRESH")
            advanced.operator("sls.disable_stack", icon="X")


class SLS_PT_image_editor(Panel):
    bl_label = "Surface Layer Mask"
    bl_idname = "SLS_PT_image_editor"
    bl_space_type = "IMAGE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Surface Layers"

    @classmethod
    def poll(cls, context):
        return _managed_material(context) is not None

    def draw(self, context):
        layout = self.layout
        material = _managed_material(context)
        layer = active_layer(material)
        if material is None or layer is None:
            return
        tools = context.scene.sls_tools
        layout.label(text=f"Mask: {layer.name}", icon="IMAGE_DATA")
        row = layout.row(align=True)
        previous = row.operator("sls.cycle_layer", text="", icon="TRIA_UP")
        previous.direction = "PREVIOUS"
        following = row.operator("sls.cycle_layer", text="", icon="TRIA_DOWN")
        following.direction = "NEXT"
        row.operator("sls.activate_mask", text="Target")
        row = layout.row(align=True)
        reveal = row.operator("sls.set_brush_mode", text="Reveal", depress=tools.brush_mode == "REVEAL")
        reveal.mode = "REVEAL"
        hide = row.operator("sls.set_brush_mode", text="Hide", depress=tools.brush_mode == "HIDE")
        hide.mode = "HIDE"
        row.operator("sls.select_soften_tool", text="Soften", depress=tools.brush_mode == "SOFTEN")
        layout.prop(tools, "brush_strength", slider=True)
        layout.prop(tools, "brush_size")
        layout.prop(layer, "opacity", slider=True)


_CLASSES = (
    SLS_UL_layers,
    SLS_PT_layers,
    SLS_PT_textures,
    SLS_PT_paint,
    SLS_PT_surface_uv,
    SLS_PT_files_output,
    SLS_PT_image_editor,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
