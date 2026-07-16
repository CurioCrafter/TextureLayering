"""Run functionality using only the isolated installed extension copy."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys

import bpy


module_id = "bl_ext.user_default.surface_layer_studio"
assert module_id in bpy.context.preferences.addons, "extension was not enabled from saved isolated preferences"
module = importlib.import_module(module_id)
extensions_root = Path(os.environ["BLENDER_USER_EXTENSIONS"]).resolve()
module_path = Path(module.__file__).resolve()
assert module_path.is_relative_to(extensions_root), (module_path, extensions_root)
assert "H:\\layeringtextures\\surface_layer_studio" not in str(module_path)
assert hasattr(bpy.types.Material, "sls")
assert hasattr(bpy.types.Scene, "sls_tools")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
bpy.context.scene.sls_tools.mask_resolution = "256"
assert "FINISHED" in bpy.ops.sls.setup_material(duplicate_existing=False, material_name="Installed Smoke")
assert "FINISHED" in bpy.ops.sls.smart_uv_project()
assert "FINISHED" in bpy.ops.sls.add_layer(layer_name="Installed Rust", fill="BLACK")
material = obj.active_material
assert material.sls.enabled and len(material.sls.layers) == 2
installed_nodes = importlib.import_module(f"{module_id}.nodes")
healthy, message = installed_nodes.graph_health(material)
assert healthy, message
print(f"SLS_INSTALLED_SMOKE_PASS path={module_path} layers={len(material.sls.layers)}")
