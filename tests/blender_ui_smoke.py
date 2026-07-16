"""Headless draw-contract smoke for every panel and layer-list state."""

from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
import sys

import bpy


args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True)
options = parser.parse_args(args)
root = Path(options.source_root).resolve()
sys.path.insert(0, str(root))

import surface_layer_studio as addon  # noqa: E402
from surface_layer_studio import ui  # noqa: E402


class OperatorProxy:
    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


class LayoutProbe:
    operator_ids: set[str] = set()

    def __init__(self):
        self.enabled = True
        self.active = True
        self.alert = False
        self.alignment = "EXPAND"
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.use_property_split = False
        self.use_property_decorate = True
        self.operator_context = "INVOKE_DEFAULT"

    def row(self, **_kwargs):
        return self

    def column(self, **_kwargs):
        return self

    def box(self):
        return self

    def split(self, **_kwargs):
        return self

    def grid_flow(self, **_kwargs):
        return self

    def separator(self, **_kwargs):
        return None

    def label(self, **_kwargs):
        return None

    def prop(self, data, property_name, **_kwargs):
        assert hasattr(data, property_name), f"missing UI property {type(data).__name__}.{property_name}"
        return None

    def prop_search(self, data, property_name, search_data, search_property, **_kwargs):
        assert hasattr(data, property_name), property_name
        assert hasattr(search_data, search_property), search_property
        return None

    def operator(self, operator_id, **_kwargs):
        self.operator_ids.add(operator_id)
        return OperatorProxy()

    def template_list(self, _list_type, _list_id, data, property_name, active_data, active_property, **_kwargs):
        assert hasattr(data, property_name), property_name
        assert hasattr(active_data, active_property), active_property

    def template_ID(self, data, property_name, **_kwargs):
        assert hasattr(data, property_name), property_name


def draw_panel(panel_class):
    probe = LayoutProbe()
    panel_class.draw(SimpleNamespace(layout=probe), bpy.context)


addon.register()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
draw_panel(ui.SLS_PT_layers)  # Empty-scene onboarding state.

bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
draw_panel(ui.SLS_PT_layers)  # Mesh without a material.
bpy.context.scene.sls_tools.mask_resolution = "256"
assert "FINISHED" in bpy.ops.sls.setup_material(duplicate_existing=False, material_name="UI Smoke")
assert "FINISHED" in bpy.ops.sls.smart_uv_project()
material = obj.active_material
layer = material.sls.layers[0]

for panel_class in (
    ui.SLS_PT_layers,
    ui.SLS_PT_textures,
    ui.SLS_PT_paint,
    ui.SLS_PT_surface_uv,
    ui.SLS_PT_files_output,
    ui.SLS_PT_image_editor,
):
    draw_panel(panel_class)

# Locked, dirty/preview, shared-material, and Texture Paint branches.
layer.locked = True
draw_panel(ui.SLS_PT_paint)
layer.locked = False
material.sls.preview_mode = "ACTIVE_MASK"
draw_panel(ui.SLS_PT_files_output)
copy = obj.copy()
copy.data = obj.data.copy()
bpy.context.collection.objects.link(copy)
copy.data.materials.clear()
copy.data.materials.append(material)
draw_panel(ui.SLS_PT_layers)
material.sls.preview_mode = "COMPOSITE"
assert "FINISHED" in bpy.ops.sls.start_paint()
draw_panel(ui.SLS_PT_paint)
assert "FINISHED" in bpy.ops.sls.finish_paint()

for layout_type in ("DEFAULT", "COMPACT", "GRID"):
    fake_list = SimpleNamespace(layout_type=layout_type)
    ui.SLS_UL_layers.draw_item(
        fake_list,
        bpy.context,
        LayoutProbe(),
        material.sls,
        layer,
        0,
        material.sls,
        "active_index",
        0,
    )

for operator_id in LayoutProbe.operator_ids:
    namespace, name = operator_id.split(".", 1)
    assert hasattr(getattr(bpy.ops, namespace), name), f"UI references missing operator {operator_id}"

print(f"SLS_UI_SMOKE_PASS panels=6 operators={len(LayoutProbe.operator_ids)}")
