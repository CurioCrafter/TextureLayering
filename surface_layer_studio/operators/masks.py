"""Mask painting, brush, persistence, and export operators."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator

from .. import images, nodes
from ..core import safe_filename
from ..paint import apply_brush_settings, enter_mask_paint, finish_mask_paint, set_active_paint_image, set_soften_brush
from ..properties import active_layer
from .common import active_mesh, managed_material, require_active_layer


class SLS_OT_new_mask(Operator):
    bl_idname = "sls.new_mask"
    bl_label = "Create New Mask"
    bl_description = "Replace the active layer's mask with a new image; the old image datablock is preserved"
    bl_options = {"REGISTER", "UNDO"}

    fill: EnumProperty(
        items=(("BLACK", "Black", "Hidden"), ("GRAY", "Gray", "Half visible"), ("WHITE", "White", "Visible")),
        default="BLACK",
    )

    @classmethod
    def poll(cls, context):
        material, layer = require_active_layer(context)
        return material is not None and layer is not None

    def execute(self, context):
        material, layer = require_active_layer(context)
        assert material is not None and layer is not None
        if layer.locked:
            self.report({"ERROR"}, "Unlock the layer before replacing its mask")
            return {"CANCELLED"}
        if layer.mask_image is not None:
            layer.mask_image.use_fake_user = True
        layer.mask_image = images.create_mask(
            material,
            layer.name,
            layer.uuid,
            int(context.scene.sls_tools.mask_resolution),
            self.fill,
            pack=context.scene.sls_tools.auto_pack_masks,
        )
        nodes.rebuild_material(material)
        return {"FINISHED"}


class SLS_OT_fill_mask(Operator):
    bl_idname = "sls.fill_mask"
    bl_label = "Fill Mask"
    bl_description = "Destructively fill the active paint mask"
    bl_options = {"REGISTER", "UNDO"}

    fill: EnumProperty(
        items=(("BLACK", "Black", "Hide layer"), ("GRAY", "Gray", "Half visibility"), ("WHITE", "White", "Reveal layer")),
        default="BLACK",
    )

    @classmethod
    def poll(cls, context):
        _material, layer = require_active_layer(context)
        return layer is not None and layer.mask_image is not None

    def execute(self, context):
        _material, layer = require_active_layer(context)
        assert layer is not None and layer.mask_image is not None
        if layer.locked:
            self.report({"ERROR"}, "Unlock the layer before filling its mask")
            return {"CANCELLED"}
        value = {"BLACK": 0.0, "GRAY": 0.5, "WHITE": 1.0}[self.fill]
        try:
            images.fill_image(layer.mask_image, value)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Filled '{layer.name}' mask {self.fill.lower()}")
        return {"FINISHED"}


class SLS_OT_resize_mask(Operator):
    bl_idname = "sls.resize_mask"
    bl_label = "Resize Mask"
    bl_description = "Resize the active mask to the current New Mask Resolution; resampling may soften detail"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        _material, layer = require_active_layer(context)
        return layer is not None and layer.mask_image is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        _material, layer = require_active_layer(context)
        assert layer is not None and layer.mask_image is not None
        if layer.locked:
            self.report({"ERROR"}, "Unlock the layer before resizing its mask")
            return {"CANCELLED"}
        if layer.mask_image.source == "TILED":
            self.report({"ERROR"}, "UDIM mask resizing is not available in this release")
            return {"CANCELLED"}
        size = int(context.scene.sls_tools.mask_resolution)
        layer.mask_image.scale(size, size)
        layer.mask_image.update()
        self.report({"INFO"}, f"Mask resized to {size} x {size}")
        return {"FINISHED"}


class SLS_OT_start_paint(Operator):
    bl_idname = "sls.start_paint"
    bl_label = "Start Mask Painting"
    bl_description = "Target the active grayscale mask and enter Blender Texture Paint mode"
    bl_options = {"REGISTER"}

    selected_faces_only: bpy.props.BoolProperty(
        name="Selected Faces Only",
        description="Enable Blender's face-selection paint guard",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        material, layer = require_active_layer(context)
        return material is not None and layer is not None and layer.mask_image is not None

    def execute(self, context):
        obj = active_mesh(context)
        material, layer = require_active_layer(context)
        assert obj is not None and material is not None and layer is not None
        if layer.locked:
            self.report({"ERROR"}, "Unlock the active layer before painting")
            return {"CANCELLED"}
        tools = context.scene.sls_tools
        tools.previous_object_mode = obj.mode
        tools.previous_preview_mode = material.sls.preview_mode
        try:
            image = enter_mask_paint(context, selected_faces_only=self.selected_faces_only)
        except (RuntimeError, TypeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Painting mask: {layer.name} ({image.name})")
        return {"FINISHED"}


class SLS_OT_finish_paint(Operator):
    bl_idname = "sls.finish_paint"
    bl_label = "Finish Mask Painting"
    bl_description = "Leave Texture Paint and restore the prior object mode when possible"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        assert obj is not None
        tools = context.scene.sls_tools
        finish_mask_paint(context)
        if tools.previous_object_mode == "EDIT" and obj.mode == "OBJECT":
            try:
                bpy.ops.object.mode_set(mode="EDIT")
            except RuntimeError:
                pass
        material = obj.active_material
        if material is not None and hasattr(material, "sls") and material.sls.enabled:
            try:
                material.sls.preview_mode = tools.previous_preview_mode
            except TypeError:
                material.sls.preview_mode = "COMPOSITE"
        return {"FINISHED"}


class SLS_OT_set_brush_mode(Operator):
    bl_idname = "sls.set_brush_mode"
    bl_label = "Set Mask Brush"
    bl_description = "Choose whether the native Blender brush reveals or hides the active layer"
    bl_options = {"REGISTER"}

    mode: EnumProperty(items=(("REVEAL", "Reveal", "Paint white"), ("HIDE", "Hide", "Paint black")))

    def execute(self, context):
        context.scene.sls_tools.brush_mode = self.mode
        apply_brush_settings(context)
        return {"FINISHED"}


class SLS_OT_swap_brush_mode(Operator):
    bl_idname = "sls.swap_brush_mode"
    bl_label = "Swap Reveal / Hide"
    bl_description = "Swap between white Reveal paint and black Hide paint"
    bl_options = {"REGISTER"}

    def execute(self, context):
        tools = context.scene.sls_tools
        tools.brush_mode = "HIDE" if tools.brush_mode == "REVEAL" else "REVEAL"
        apply_brush_settings(context)
        return {"FINISHED"}


class SLS_OT_select_soften_tool(Operator):
    bl_idname = "sls.select_soften_tool"
    bl_label = "Soften Tool"
    bl_description = "Select Blender's native Soften texture-paint tool for smoothing mask transitions"
    bl_options = {"REGISTER"}

    def execute(self, context):
        if set_soften_brush(context) is None:
            self.report({"ERROR"}, "Enter Texture Paint mode and activate a brush before using Soften")
            return {"CANCELLED"}
        return {"FINISHED"}


class SLS_OT_activate_mask(Operator):
    bl_idname = "sls.activate_mask"
    bl_label = "Target Active Mask"
    bl_description = "Make the active layer mask Blender's paint canvas without changing mode"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        material, layer = require_active_layer(context)
        return material is not None and layer is not None and layer.mask_image is not None

    def execute(self, context):
        obj = active_mesh(context)
        material, layer = require_active_layer(context)
        assert obj is not None and material is not None and layer is not None
        try:
            set_active_paint_image(context, obj, material, layer)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Paint canvas: {layer.name} mask")
        return {"FINISHED"}


class SLS_OT_cycle_layer(Operator):
    bl_idname = "sls.cycle_layer"
    bl_label = "Cycle Layer"
    bl_description = "Select the next layer and retarget its mask if currently painting"
    bl_options = {"REGISTER"}

    direction: EnumProperty(items=(("PREVIOUS", "Previous", "Previous row"), ("NEXT", "Next", "Next row")))

    @classmethod
    def poll(cls, context):
        material = managed_material(context)
        return material is not None and len(material.sls.layers) > 1

    def execute(self, context):
        material = managed_material(context)
        obj = active_mesh(context)
        assert material is not None and obj is not None
        count = len(material.sls.layers)
        delta = -1 if self.direction == "PREVIOUS" else 1
        material.sls.active_index = (material.sls.active_index + delta) % count
        nodes.flush_pending_rebuilds()
        layer = active_layer(material)
        if obj.mode == "TEXTURE_PAINT" and layer is not None:
            try:
                set_active_paint_image(context, obj, material, layer)
            except RuntimeError as exc:
                self.report({"WARNING"}, str(exc))
        return {"FINISHED"}


class SLS_OT_pack_masks(Operator):
    bl_idname = "sls.pack_masks"
    bl_label = "Pack All Masks"
    bl_description = "Pack every layer mask into the blend file"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        packed = 0
        embedded = 0
        failed: list[str] = []
        for layer in material.sls.layers:
            image = layer.mask_image
            if image is None:
                continue
            if image.source == "GENERATED":
                image.update()
                embedded += 1
                continue
            try:
                image.pack()
                packed += 1
            except RuntimeError:
                failed.append(layer.name)
        if failed:
            self.report(
                {"WARNING"},
                f"Protected {embedded} embedded and {packed} packed masks; could not pack: {', '.join(failed[:3])}",
            )
        else:
            self.report({"INFO"}, f"Protected {embedded} embedded and {packed} packed mask(s)")
        return {"FINISHED"}


class SLS_OT_pack_sources(Operator):
    bl_idname = "sls.pack_sources"
    bl_label = "Pack Source Textures"
    bl_description = "Pack all source PBR textures referenced by this stack"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        unique = set()
        for layer in material.sls.layers:
            for field in (
                "base_color_image",
                "roughness_image",
                "metallic_image",
                "normal_image",
                "height_image",
                "ao_image",
                "emission_image",
            ):
                image = getattr(layer, field)
                if image:
                    unique.add(image)
        packed = 0
        for image in unique:
            try:
                image.pack()
                packed += 1
            except RuntimeError:
                pass
        self.report({"INFO"}, f"Packed {packed} of {len(unique)} source texture(s)")
        return {"FINISHED"}


class SLS_OT_export_masks(Operator):
    bl_idname = "sls.export_masks"
    bl_label = "Export All Masks"
    bl_description = "Save every layer mask as a PNG in the configured mask folder"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        raw_directory = context.scene.sls_tools.export_directory
        if raw_directory.startswith("//") and not bpy.data.filepath:
            self.report({"ERROR"}, "Save the blend file first or choose an absolute Mask Folder")
            return {"CANCELLED"}
        directory = Path(bpy.path.abspath(raw_directory))
        exported: list[Path] = []
        failures: list[str] = []
        for layer in material.sls.layers:
            if layer.mask_image is None:
                continue
            filename = f"{safe_filename(material.name)}_{safe_filename(layer.name)}_mask"
            try:
                exported.append(images.export_mask(layer.mask_image, directory, filename))
            except RuntimeError:
                failures.append(layer.name)
        if failures:
            self.report({"WARNING"}, f"Exported {len(exported)}; failed: {', '.join(failures[:3])}")
        else:
            self.report({"INFO"}, f"Exported {len(exported)} mask(s) to {directory}")
        return {"FINISHED"}


CLASSES = (
    SLS_OT_new_mask,
    SLS_OT_fill_mask,
    SLS_OT_resize_mask,
    SLS_OT_start_paint,
    SLS_OT_finish_paint,
    SLS_OT_set_brush_mode,
    SLS_OT_swap_brush_mode,
    SLS_OT_select_soften_tool,
    SLS_OT_activate_mask,
    SLS_OT_cycle_layer,
    SLS_OT_pack_masks,
    SLS_OT_pack_sources,
    SLS_OT_export_masks,
)
