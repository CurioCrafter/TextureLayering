"""Persistence check run after opening the blend produced by blender_smoke.py."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy


args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True)
options = parser.parse_args(args)
root = Path(options.source_root).resolve()
sys.path.insert(0, str(root))

import surface_layer_studio as addon  # noqa: E402
from surface_layer_studio import nodes  # noqa: E402


addon.register()
obj = bpy.data.objects.get("SLS Smoke Cube")
assert obj is not None, "smoke object did not persist"
material = obj.material_slots[0].material
assert material is not None and material.sls.enabled, "stack metadata did not persist"
assert len(material.sls.layers) == 20, f"layer order/count did not persist: {len(material.sls.layers)}"
assert material.sls.layers[-1].pinned_base, "base pin did not persist"
assert all(layer.mask_image is not None for layer in material.sls.layers), "mask pointer did not persist"
assert abs(material.sls.layers[0].mask_image.pixels[0] - 0.25) < 0.01, "painted mask pixel did not persist"
assert all(
    layer.mask_image.source == "GENERATED" or layer.mask_image.packed_file is not None
    for layer in material.sls.layers
), "an external mask was neither packed nor embedded"
healthy, message = nodes.graph_health(material)
assert healthy, message
print(f"SLS_REOPEN_PASS layers={len(material.sls.layers)} graph_version={material.sls.graph_version}")
