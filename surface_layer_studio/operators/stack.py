"""Stack creation, layer ordering, duplication, presets, and repair."""

from __future__ import annotations

from uuid import uuid4

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import Operator

from .. import images, nodes
from ..properties import active_layer
from .common import (
    active_mesh,
    add_layer,
    copy_layer_properties,
    ensure_material_slot,
    managed_material,
    material_slot_index,
    rebuild,
)


def _assign_slot_to_edit_selection(obj, slot_index: int) -> int:
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    count = 0
    for face in bm.faces:
        if face.select:
            face.material_index = slot_index
            count += 1
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    return count


class SLS_OT_setup_material(Operator):
    bl_idname = "sls.setup_material"
    bl_label = "Create Layer Stack"
    bl_description = "Create a non-destructive Surface Layer Studio material on the active mesh"
    bl_options = {"REGISTER", "UNDO"}

    material_name: StringProperty(name="Material Name", default="Layered Ship Surface")
    duplicate_existing: BoolProperty(
        name="Preserve Existing Material",
        description="Work on a copy so the original material remains untouched",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        assert obj is not None
        existing = obj.active_material
        if existing is not None and hasattr(existing, "sls") and existing.sls.enabled:
            self.report({"INFO"}, "The active material already has a layer stack")
            return {"CANCELLED"}

        selected_face_scope = obj.mode == "EDIT"
        if existing is not None and self.duplicate_existing:
            material = existing.copy()
            material.name = f"{existing.name} - Layered"
        elif existing is not None:
            material = existing
        else:
            material = bpy.data.materials.new(self.material_name)
            material.use_nodes = True

        if selected_face_scope:
            slot_index = ensure_material_slot(obj, material)
            obj.active_material_index = slot_index
            assigned = _assign_slot_to_edit_selection(obj, slot_index)
            if assigned == 0:
                self.report({"WARNING"}, "No faces were selected; the material slot was created but not assigned")
        elif existing is not None and material != existing:
            slot_index = obj.active_material_index
            obj.material_slots[slot_index].material = material
        else:
            slot_index = ensure_material_slot(obj, material)
            obj.active_material_index = slot_index

        settings = material.sls
        settings.enabled = True
        settings.stack_id = settings.stack_id or str(uuid4())
        nodes.capture_original_surface(material)
        settings.base_color = tuple(material.diffuse_color)
        settings.base_roughness = float(getattr(material, "roughness", 0.5))
        settings.base_metallic = float(getattr(material, "metallic", 0.0))

        if not settings.layers:
            base = add_layer(context, material, "Base Surface", fill="WHITE", pinned=True, to_top=False)
            base.tint = tuple(material.diffuse_color)
            base.roughness = settings.base_roughness
            base.metallic = settings.base_metallic
        rebuild(material)

        if not obj.data.uv_layers:
            self.report({"WARNING"}, "Layer stack created. Create or unwrap a UV map before mask painting.")
        else:
            self.report({"INFO"}, "Layer stack created; select a layer and start mask painting")
        return {"FINISHED"}


class SLS_OT_add_layer(Operator):
    bl_idname = "sls.add_layer"
    bl_label = "Add Layer"
    bl_description = "Add a PBR layer with an independent paint mask"
    bl_options = {"REGISTER", "UNDO"}

    layer_name: StringProperty(name="Name", default="New Surface Layer")
    fill: EnumProperty(
        name="Initial Mask",
        items=(
            ("DEFAULT", "Use Tool Setting", "Use the New Overlay Mask setting"),
            ("BLACK", "Hidden", "Start hidden"),
            ("GRAY", "Half", "Start half visible"),
            ("WHITE", "Visible", "Start visible"),
        ),
        default="DEFAULT",
    )

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        fill = context.scene.sls_tools.new_layer_fill if self.fill == "DEFAULT" else self.fill
        add_layer(context, material, self.layer_name, fill=fill)
        rebuild(material)
        self.report({"INFO"}, "Layer added. A black mask is hidden until you paint Reveal.")
        return {"FINISHED"}


class SLS_OT_remove_layer(Operator):
    bl_idname = "sls.remove_layer"
    bl_label = "Remove Layer"
    bl_description = "Remove the layer from the stack without deleting its source images"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        material = managed_material(context)
        return material is not None and bool(material.sls.layers)

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        settings = material.sls
        layer = active_layer(material)
        if layer is None:
            return {"CANCELLED"}
        if layer.pinned_base:
            self.report({"ERROR"}, "The pinned base layer cannot be removed")
            return {"CANCELLED"}
        if layer.locked:
            self.report({"ERROR"}, "Unlock the layer before removing it")
            return {"CANCELLED"}
        name = layer.name
        if layer.mask_image is not None:
            layer.mask_image.use_fake_user = True
        settings.layers.remove(settings.active_index)
        settings.active_index = min(settings.active_index, max(0, len(settings.layers) - 1))
        rebuild(material)
        self.report({"INFO"}, f"Removed '{name}'. Its image datablocks were preserved.")
        return {"FINISHED"}


class SLS_OT_duplicate_layer(Operator):
    bl_idname = "sls.duplicate_layer"
    bl_label = "Duplicate Layer"
    bl_description = "Duplicate layer settings and create an independent copy of its mask"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        material = managed_material(context)
        return material is not None and active_layer(material) is not None

    def execute(self, context):
        material = managed_material(context)
        source = active_layer(material)
        assert material is not None and source is not None
        settings = material.sls
        source_index = settings.active_index
        duplicate = settings.layers.add()
        duplicate.uuid = str(uuid4())
        copy_layer_properties(source, duplicate)
        duplicate.name = f"{source.name} Copy"
        duplicate.pinned_base = False
        if source.mask_image:
            duplicate.mask_image = images.duplicate_mask(
                source.mask_image,
                material,
                duplicate.name,
                duplicate.uuid,
                pack=context.scene.sls_tools.auto_pack_masks,
            )
        settings.layers.move(len(settings.layers) - 1, source_index)
        settings.active_index = source_index
        rebuild(material)
        return {"FINISHED"}


class SLS_OT_move_layer(Operator):
    bl_idname = "sls.move_layer"
    bl_label = "Move Layer"
    bl_description = "Move the layer in the top-to-bottom composite order"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=(("UP", "Up", "Move toward the top"), ("DOWN", "Down", "Move toward the base")))

    @classmethod
    def poll(cls, context):
        material = managed_material(context)
        return material is not None and len(material.sls.layers) > 1

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        settings = material.sls
        index = settings.active_index
        layer = settings.layers[index]
        if layer.pinned_base:
            self.report({"ERROR"}, "The base layer is pinned")
            return {"CANCELLED"}
        target = index - 1 if self.direction == "UP" else index + 1
        if target < 0 or target >= len(settings.layers):
            return {"CANCELLED"}
        if settings.layers[target].pinned_base:
            self.report({"ERROR"}, "Layers cannot move below the pinned base")
            return {"CANCELLED"}
        settings.layers.move(index, target)
        settings.active_index = target
        rebuild(material)
        return {"FINISHED"}


class SLS_OT_ship_starter(Operator):
    bl_idname = "sls.ship_starter"
    bl_label = "Build Ship Interior Starter"
    bl_description = "Create a practical painted-metal, wear, rust, grime, damp, and emissive layer stack"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None

    def execute(self, context):
        material = managed_material(context)
        if material is None:
            result = bpy.ops.sls.setup_material("EXEC_DEFAULT")
            if "FINISHED" not in result:
                return {"CANCELLED"}
            material = managed_material(context)
        assert material is not None

        settings = material.sls
        base = next((layer for layer in settings.layers if layer.pinned_base), None)
        if base is not None:
            base.name = "Painted Steel Base"
            base.tint = (0.12, 0.16, 0.18, 1.0)
            base.roughness = 0.48
            base.metallic = 0.18

        presets = (
            ("Secondary Paint & Markings", (0.28, 0.34, 0.32, 1.0), 0.52, 0.0, "MIX"),
            ("Exposed Edge Metal", (0.18, 0.20, 0.21, 1.0), 0.30, 0.88, "MIX"),
            ("Rust & Oxidation", (0.38, 0.095, 0.025, 1.0), 0.88, 0.0, "OVERLAY"),
            ("Oil & Engine Grime", (0.018, 0.014, 0.011, 1.0), 0.24, 0.0, "MULTIPLY"),
            ("Salt & Damp Staining", (0.45, 0.51, 0.48, 1.0), 0.76, 0.0, "SOFT_LIGHT"),
            ("Emissive Panels", (0.02, 0.03, 0.04, 1.0), 0.35, 0.0, "MIX"),
        )
        existing = {layer.name for layer in settings.layers}
        for name, tint, roughness, metallic, blend_mode in presets:
            if name in existing:
                continue
            layer = add_layer(context, material, name, fill="BLACK")
            layer.tint = tint
            layer.roughness = roughness
            layer.metallic = metallic
            layer.blend_mode = blend_mode
            if name == "Emissive Panels":
                layer.emission_tint = (0.08, 0.55, 1.0, 1.0)
                layer.emission_strength = 4.0
        rebuild(material)
        self.report({"INFO"}, "Ship starter created. Overlay masks start hidden; paint Reveal to place them.")
        return {"FINISHED"}


class SLS_OT_repair_stack(Operator):
    bl_idname = "sls.repair_stack"
    bl_label = "Repair Stack"
    bl_description = "Rebuild generated nodes from the saved layer metadata"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        try:
            rebuild(material)
        except Exception as exc:
            self.report({"ERROR"}, f"Repair failed: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, "Layer stack repaired from metadata")
        return {"FINISHED"}


class SLS_OT_make_single_user(Operator):
    bl_idname = "sls.make_single_user"
    bl_label = "Make Stack Single User"
    bl_description = "Copy the material and every paint mask so painting cannot affect another object"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        material = managed_material(context)
        assert obj is not None and material is not None
        copy = material.copy()
        copy.name = f"{material.name} - {obj.name}"
        copy.sls.stack_id = str(uuid4())
        for layer in copy.sls.layers:
            if layer.mask_image:
                layer.mask_image = images.duplicate_mask(
                    layer.mask_image,
                    copy,
                    layer.name,
                    layer.uuid,
                    pack=context.scene.sls_tools.auto_pack_masks,
                )
        index = material_slot_index(obj, material)
        if index is None:
            index = ensure_material_slot(obj, copy)
        else:
            obj.material_slots[index].material = copy
        obj.active_material_index = index
        rebuild(copy)
        self.report({"INFO"}, "Material and masks are now independent for this object")
        return {"FINISHED"}


class SLS_OT_disable_stack(Operator):
    bl_idname = "sls.disable_stack"
    bl_label = "Disable and Restore Material"
    bl_description = "Disconnect the generated stack and restore the shader that was connected before conversion"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def invoke(self, context, _event):
        return context.window_manager.invoke_confirm(self, _event)

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        restored = nodes.restore_original_surface(material)
        material.sls.enabled = False
        self.report({"INFO"}, "Original shader restored" if restored else "Layer stack disabled; no original shader link was recorded")
        return {"FINISHED"}


CLASSES = (
    SLS_OT_setup_material,
    SLS_OT_add_layer,
    SLS_OT_remove_layer,
    SLS_OT_duplicate_layer,
    SLS_OT_move_layer,
    SLS_OT_ship_starter,
    SLS_OT_repair_stack,
    SLS_OT_make_single_user,
    SLS_OT_disable_stack,
)
