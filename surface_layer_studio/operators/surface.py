"""Selected-face material scope, paint guards, and UV workflow operators."""

from __future__ import annotations

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty
from bpy.types import Operator

from .. import nodes
from ..constants import DEFAULT_UV_NAME
from ..uv import active_uv_name, audit_uv
from .common import active_mesh, ensure_material_slot, managed_material


class SLS_OT_assign_selected_faces(Operator):
    bl_idname = "sls.assign_selected_faces"
    bl_label = "Assign Stack to Selected Faces"
    bl_description = "Assign the entire layered material to the currently selected mesh faces"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = active_mesh(context)
        return obj is not None and obj.mode == "EDIT" and managed_material(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        material = managed_material(context)
        assert obj is not None and material is not None
        slot_index = ensure_material_slot(obj, material)
        bm = bmesh.from_edit_mesh(obj.data)
        count = 0
        for face in bm.faces:
            if face.select:
                face.material_index = slot_index
                count += 1
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        obj.active_material_index = slot_index
        if count == 0:
            self.report({"ERROR"}, "Select one or more faces in Edit Mode first")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Assigned layered material to {count} face(s)")
        return {"FINISHED"}


class SLS_OT_select_assigned_faces(Operator):
    bl_idname = "sls.select_assigned_faces"
    bl_label = "Select Stack Faces"
    bl_description = "Select faces assigned to this layered material"
    bl_options = {"REGISTER", "UNDO"}

    extend: BoolProperty(name="Extend Selection", default=False)

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None and managed_material(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        material = managed_material(context)
        assert obj is not None and material is not None
        slot_index = next((index for index, slot in enumerate(obj.material_slots) if slot.material == material), None)
        if slot_index is None:
            self.report({"ERROR"}, "The layered material is not assigned to this object")
            return {"CANCELLED"}
        if obj.mode != "EDIT":
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(obj.data)
        count = 0
        for face in bm.faces:
            if not self.extend:
                face.select = False
            if face.material_index == slot_index:
                face.select = True
                count += 1
        bm.select_flush_mode()
        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
        self.report({"INFO"}, f"Selected {count} face(s) assigned to the stack")
        return {"FINISHED"}


class SLS_OT_paint_selected_faces(Operator):
    bl_idname = "sls.paint_selected_faces"
    bl_label = "Paint Only Selected Faces"
    bl_description = "Enter mask painting with Blender's face-selection paint guard enabled"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None and managed_material(context) is not None

    def execute(self, _context):
        result = bpy.ops.sls.start_paint("EXEC_DEFAULT", selected_faces_only=True)
        return {"FINISHED"} if "FINISHED" in result else {"CANCELLED"}


class SLS_OT_uv_audit(Operator):
    bl_idname = "sls.uv_audit"
    bl_label = "Audit UVs"
    bl_description = "Check for missing, zero-area, outside-tile, and exactly overlapping UV faces"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        assert obj is not None
        report = audit_uv(obj, active_uv_name(obj))
        obj["sls_uv_audit"] = report["message"]
        obj["sls_uv_zero_area"] = report["zero_area_faces"]
        obj["sls_uv_outside_tile"] = report["outside_tile_faces"]
        obj["sls_uv_overlap_groups"] = report["exact_overlap_groups"]
        level = {"INFO"} if report["ok"] and report["message"].startswith("UV map is ready") else {"WARNING"}
        self.report(level, str(report["message"]))
        return {"FINISHED"}


class SLS_OT_smart_uv_project(Operator):
    bl_idname = "sls.smart_uv_project"
    bl_label = "Smart UV Project"
    bl_description = "Explicitly unwrap selected faces (or the whole object) for texture painting"
    bl_options = {"REGISTER", "UNDO"}

    angle_limit: FloatProperty(name="Angle Limit", default=1.15192, min=0.0, max=1.5708, subtype="ANGLE")
    island_margin: FloatProperty(name="Island Margin", default=0.02, min=0.0, max=0.2)
    apply_to_stack: BoolProperty(
        name="Use for All Layers",
        description="Set the generated UV map on every layer in the active stack",
        default=True,
    )

    @classmethod
    def poll(cls, context):
        return active_mesh(context) is not None

    def execute(self, context):
        obj = active_mesh(context)
        assert obj is not None
        original_mode = obj.mode
        if not obj.data.uv_layers:
            uv_layer = obj.data.uv_layers.new(name=DEFAULT_UV_NAME)
            obj.data.uv_layers.active = uv_layer
        else:
            uv_layer = obj.data.uv_layers.active
            if uv_layer is None:
                uv_layer = obj.data.uv_layers[0]
                obj.data.uv_layers.active = uv_layer
        uv_name = uv_layer.name
        uv_layer.active_render = True

        if obj.mode != "EDIT":
            if obj.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
        try:
            result = bpy.ops.uv.smart_project(angle_limit=self.angle_limit, island_margin=self.island_margin)
        except (RuntimeError, TypeError) as exc:
            self.report({"ERROR"}, f"Smart UV Project failed: {exc}")
            return {"CANCELLED"}
        finally:
            if original_mode != "EDIT" and obj.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
        if "FINISHED" not in result:
            self.report({"ERROR"}, "Smart UV Project did not run; make sure faces are selected")
            return {"CANCELLED"}

        material = managed_material(context)
        if self.apply_to_stack and material is not None:
            for layer in material.sls.layers:
                layer.uv_map = uv_name
            nodes.rebuild_material(material)
        self.report({"INFO"}, f"Unwrapped to UV map '{uv_name}'")
        return {"FINISHED"}


class SLS_OT_open_uv_workspace(Operator):
    bl_idname = "sls.open_uv_workspace"
    bl_label = "Open UV Editing"
    bl_description = "Switch to Blender's UV Editing workspace"
    bl_options = {"REGISTER"}

    def execute(self, context):
        workspace = bpy.data.workspaces.get("UV Editing")
        if workspace is None or context.window is None:
            self.report({"ERROR"}, "The UV Editing workspace is unavailable")
            return {"CANCELLED"}
        context.window.workspace = workspace
        return {"FINISHED"}


CLASSES = (
    SLS_OT_assign_selected_faces,
    SLS_OT_select_assigned_faces,
    SLS_OT_paint_selected_faces,
    SLS_OT_uv_audit,
    SLS_OT_smart_uv_project,
    SLS_OT_open_uv_workspace,
)
