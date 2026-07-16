"""Install the release zip into an isolated Blender extension profile."""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import sys

import bpy


args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--zip", required=True)
options = parser.parse_args(args)
package = Path(options.zip).resolve()
assert package.is_file(), package

repos = {repo.module: repo for repo in bpy.context.preferences.extensions.repos}
assert "user_default" in repos, f"user_default extension repository missing: {sorted(repos)}"
result = bpy.ops.extensions.package_install_files(
    filepath=str(package),
    repo="user_default",
    enable_on_install=True,
)
assert "FINISHED" in result, result
module_id = "bl_ext.user_default.surface_layer_studio"
assert module_id in bpy.context.preferences.addons, tuple(bpy.context.preferences.addons.keys())
module = importlib.import_module(module_id)
extensions_root = Path(os.environ["BLENDER_USER_EXTENSIONS"]).resolve()
module_path = Path(module.__file__).resolve()
assert module_path.is_relative_to(extensions_root), (module_path, extensions_root)
assert hasattr(bpy.types.Material, "sls")
assert hasattr(bpy.types.Scene, "sls_tools")
bpy.ops.wm.save_userpref()
print(f"SLS_INSTALL_PASS module={module_path}")
