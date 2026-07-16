"""End-to-end source-tree smoke test, run by Blender 4.5.11."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import time

import bmesh
import bpy


def parse_args():
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--artifact", required=True)
    return parser.parse_args(args)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


options = parse_args()
root = Path(options.source_root).resolve()
sys.path.insert(0, str(root))

import surface_layer_studio as addon  # noqa: E402
from surface_layer_studio import images, nodes  # noqa: E402
from surface_layer_studio.constants import MANAGED_TAG  # noqa: E402


addon.register()
require(bpy.app.version_string.startswith("4.5.11"), f"wrong Blender: {bpy.app.version_string}")

# UI icons fail at draw time, so validate every literal against Blender's RNA enum.
ui_source = (root / "surface_layer_studio" / "ui.py").read_text(encoding="utf-8")
icons = set(re.findall(r'icon="([A-Z0-9_]+)"', ui_source))
valid_icons = {
    item.identifier
    for item in bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items
}
invalid_icons = sorted(icons - valid_icons)
require(not invalid_icons, f"invalid UI icons: {invalid_icons}")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
obj.name = "SLS Smoke Cube"
bpy.context.scene.sls_tools.mask_resolution = "256"

result = bpy.ops.sls.setup_material(duplicate_existing=False, material_name="SLS Smoke Material")
require("FINISHED" in result, f"setup failed: {result}")
material = obj.active_material
require(material is not None and material.sls.enabled, "managed material missing")
require(len(material.sls.layers) == 1, "base layer not created")
require(material.sls.layers[0].pinned_base, "base layer not pinned")

result = bpy.ops.sls.smart_uv_project()
require("FINISHED" in result and bool(obj.data.uv_layers), "UV setup failed")
require(material.sls.layers[0].uv_map == obj.data.uv_layers.active.name, "stack UV was not updated")
healthy, message = nodes.graph_health(material)
require(healthy, message)

# Exercise every PBR channel and DirectX normal conversion.
base = material.sls.layers[0]
base.base_color_image = bpy.data.images.new("Smoke Base Color", 8, 8, alpha=True)
base.roughness_image = bpy.data.images.new("Smoke Roughness", 8, 8, alpha=False, is_data=True)
base.metallic_image = bpy.data.images.new("Smoke Metallic", 8, 8, alpha=False, is_data=True)
base.normal_image = bpy.data.images.new("Smoke NormalDX", 8, 8, alpha=False, is_data=True)
base.height_image = bpy.data.images.new("Smoke Height", 8, 8, alpha=False, is_data=True)
base.ao_image = bpy.data.images.new("Smoke AO", 8, 8, alpha=False, is_data=True)
base.emission_image = bpy.data.images.new("Smoke Emission", 8, 8, alpha=True)
base.normal_format = "DIRECTX"
base.emission_strength = 2.5
images.set_color_space(base.base_color_image, is_data=False)
images.set_color_space(base.emission_image, is_data=False)
for image in (base.roughness_image, base.metallic_image, base.normal_image, base.height_image, base.ao_image):
    images.set_color_space(image, is_data=True)
nodes.rebuild_material(material)
require(any(node.bl_idname == "ShaderNodeSeparateColor" for node in material.node_tree.nodes), "DX normal conversion missing")
require(material.node_tree.nodes.get("SLS_Normal_Map") is not None, "Normal Map node missing")
require(material.node_tree.nodes.get("SLS_Bump") is not None, "Bump node missing")
managed_shader = next(
    node for node in material.node_tree.nodes if node.get(MANAGED_TAG) and node.get("sls_role") == "principled"
)
require(abs(managed_shader.inputs["Emission Strength"].default_value - 1.0) < 1e-5, "emission strength is double-scaled")
emission_scale = next(node for node in material.node_tree.nodes if node.label == "Emission Strength")
require(abs(emission_scale.inputs[2].default_value[0] - 2.5) < 1e-5, "per-layer emission scale missing")
mask_texture = nodes.mask_node(material, base.uuid)
require(mask_texture.inputs["Vector"].links[0].from_node.bl_idname == "ShaderNodeUVMap", "mask was transformed with tiled sources")
base_texture = next(node for node in material.node_tree.nodes if getattr(node, "image", None) == base.base_color_image)
require(base_texture.inputs["Vector"].links[0].from_node.bl_idname == "ShaderNodeMapping", "source mapping was not applied")

# No artificial layer cap: verify normal workloads and a 20-layer stress stack.
for index in range(1, 8):
    bpy.ops.sls.add_layer(layer_name=f"Layer {index}", fill="BLACK")
require(len(material.sls.layers) == 8, "8-layer stack failed")
for index in range(8, 20):
    bpy.ops.sls.add_layer(layer_name=f"Layer {index}", fill="BLACK")
start = time.perf_counter()
nodes.rebuild_material(material)
elapsed = time.perf_counter() - start
require(len(material.sls.layers) == 20, "20-layer stack failed")
require(material.sls.layers[-1].pinned_base, "base did not remain at bottom")
require(len({layer.mask_image.as_pointer() for layer in material.sls.layers}) == 20, "masks are not independent")
require(elapsed < 30.0, f"20-layer rebuild is unreasonably slow: {elapsed:.2f}s")
print(f"SLS_PERF_20_LAYERS={elapsed:.4f}s")

# Duplicate/reorder/delete lifecycle.
source_mask = material.sls.layers[0].mask_image
bpy.ops.sls.duplicate_layer()
require(len(material.sls.layers) == 21, "duplicate did not add a layer")
require(material.sls.layers[0].mask_image != source_mask, "duplicate reused the source mask")
duplicate_mask = material.sls.layers[0].mask_image
require("FINISHED" in bpy.ops.sls.move_layer(direction="DOWN"), "move down failed")
require("FINISHED" in bpy.ops.sls.move_layer(direction="UP"), "move up failed")
require("FINISHED" in bpy.ops.sls.remove_layer(), "remove failed")
require(len(material.sls.layers) == 20, "remove did not restore count")
require(duplicate_mask.use_fake_user, "removed mask was not preserved for the next save")

# Pixel operations and paint canvas targeting.
layer = material.sls.layers[0]
material.sls.active_index = 0
require("FINISHED" in bpy.ops.sls.fill_mask(fill="WHITE"), "white fill failed")
require(layer.mask_image.pixels[0] > 0.99, "white fill pixel mismatch")
require("FINISHED" in bpy.ops.sls.fill_mask(fill="BLACK"), "black fill failed")
require(layer.mask_image.pixels[0] < 0.01, "black fill pixel mismatch")
require("FINISHED" in bpy.ops.sls.activate_mask(), "mask targeting failed")
canvas = getattr(bpy.context.scene.tool_settings.image_paint, "canvas", None)
require(canvas == layer.mask_image, "Blender paint canvas is not the active layer mask")
bpy.context.scene.sls_tools.brush_strength = 0.37
require("FINISHED" in bpy.ops.sls.start_paint(), "Texture Paint mode/brush activation failed")
require(obj.mode == "TEXTURE_PAINT", "object did not enter Texture Paint")
require("FINISHED" in bpy.ops.sls.set_brush_mode(mode="HIDE"), "hide brush failed")
brush = getattr(bpy.context.scene.tool_settings.image_paint, "brush", None)
require(brush is not None, "Texture Paint brush was not resolved")
require(abs(brush.strength - 0.37) < 1e-5, "brush strength was not applied")
require(max(brush.color) < 0.01, "hide brush is not black")
require("FINISHED" in bpy.ops.sls.set_brush_mode(mode="REVEAL"), "reveal brush failed")
require(min(brush.color) > 0.99, "reveal brush is not white")
require("FINISHED" in bpy.ops.sls.select_soften_tool(), "soften brush failed")
require(brush.image_tool == "SOFTEN", "soften did not select Blender's native image mode")
bpy.context.scene.sls_tools.brush_strength = 0.21
require(brush.image_tool == "SOFTEN", "changing opacity silently reverted Soften to Draw")
require("FINISHED" in bpy.ops.sls.set_brush_mode(mode="REVEAL"), "return to reveal failed")
require("FINISHED" in bpy.ops.sls.finish_paint(), "finish paint failed")
require(obj.mode == "OBJECT", "finish paint did not restore Object mode")
images.fill_image(layer.mask_image, 0.25)
require(abs(layer.mask_image.pixels[0] - 0.25) < 0.01, "non-default persistence pixel was not written")

# Surface assignment must affect only selected faces.
other = bpy.data.materials.new("Other Material")
obj.data.materials.append(other)
for polygon in obj.data.polygons:
    polygon.material_index = 1
obj.active_material_index = 0
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="DESELECT")
bm = bmesh.from_edit_mesh(obj.data)
bm.faces.ensure_lookup_table()
bm.faces[0].select = True
bmesh.update_edit_mesh(obj.data)
require("FINISHED" in bpy.ops.sls.assign_selected_faces(), "selected-face assignment failed")
bpy.ops.object.mode_set(mode="OBJECT")
require(sum(poly.material_index == 0 for poly in obj.data.polygons) == 1, "assignment escaped selected faces")

# Preview paths and damage/repair behavior.
for preview in ("ACTIVE_MASK", "BASE_COLOR", "ROUGHNESS", "METALLIC", "NORMAL", "HEIGHT", "EMISSION", "COMPOSITE"):
    material.sls.preview_mode = preview
    nodes.flush_pending_rebuilds()
    healthy, message = nodes.graph_health(material)
    require(healthy, f"preview {preview}: {message}")
managed_shader = next(
    node
    for node in material.node_tree.nodes
    if node.get(MANAGED_TAG) and node.get("sls_role") == "principled"
)
material.node_tree.nodes.remove(managed_shader)
require(not nodes.graph_health(material)[0], "damaged stack was reported healthy")
unmanaged_collision = material.node_tree.nodes.new("ShaderNodeValue")
unmanaged_collision.name = "SLS_Principled"
require("FINISHED" in bpy.ops.sls.repair_stack(), "repair operator failed")
require(nodes.graph_health(material)[0], "stack remained unhealthy after repair")
require(unmanaged_collision in material.node_tree.nodes[:], "repair deleted an unmanaged colliding node")

# Pending rebuilds survive material renames because the queue tracks datablocks, not names.
layer = material.sls.layers[0]
material.name = "SLS Smoke Material Renamed"
layer.opacity = 0.42
nodes.flush_pending_rebuilds()
short = layer.uuid.replace("-", "")[:10]
opacity_node = material.node_tree.nodes.get(f"SLS_{short}_Opacity")
require(opacity_node is not None and abs(opacity_node.inputs[1].default_value - 0.42) < 1e-5, "rename lost pending rebuild")

# Existing shader links are tagged, preserved, and restored even if the node is renamed.
bpy.ops.mesh.primitive_cube_add(location=(3.0, 0.0, 0.0))
restore_obj = bpy.context.active_object
restore_material = bpy.data.materials.new("Restore Probe")
restore_material.use_nodes = True
restore_obj.data.materials.append(restore_material)
output = next(node for node in restore_material.node_tree.nodes if node.bl_idname == "ShaderNodeOutputMaterial")
original_shader = output.inputs["Surface"].links[0].from_node
require("FINISHED" in bpy.ops.sls.setup_material(duplicate_existing=False), "restore-probe setup failed")
original_shader.name = "User Renamed Original Shader"
require("FINISHED" in bpy.ops.sls.disable_stack("EXEC_DEFAULT"), "disable/restore failed")
require(output.inputs["Surface"].is_linked and output.inputs["Surface"].links[0].from_node == original_shader, "original shader was not restored")
require(not any(node.get(MANAGED_TAG) for node in restore_material.node_tree.nodes), "disable left managed nodes behind")

bpy.context.view_layer.objects.active = obj
obj.select_set(True)
restore_obj.select_set(False)
obj.active_material_index = 0

require("FINISHED" in bpy.ops.sls.pack_masks(), "mask packing failed")
for stack_layer in material.sls.layers:
    require(stack_layer.mask_image is not None, "mask missing before save")

artifact = Path(options.artifact).resolve()
artifact.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(artifact), check_existing=False)
require(artifact.is_file(), "blend artifact was not saved")

print(f"SLS_SMOKE_PASS layers={len(material.sls.layers)} nodes={sum(bool(n.get(MANAGED_TAG)) for n in material.node_tree.nodes)}")
