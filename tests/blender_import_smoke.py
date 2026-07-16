"""Exercise real image IO through the automatic PBR-set importer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import bpy


args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
parser = argparse.ArgumentParser()
parser.add_argument("--source-root", required=True)
parser.add_argument("--fixture-dir", required=True)
options = parser.parse_args(args)
root = Path(options.source_root).resolve()
fixture_dir = Path(options.fixture_dir).resolve()
fixture_dir.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(root))

import surface_layer_studio as addon  # noqa: E402


addon.register()
bpy.ops.mesh.primitive_cube_add()
bpy.context.scene.sls_tools.mask_resolution = "256"
assert "FINISHED" in bpy.ops.sls.setup_material(duplicate_existing=False, material_name="PBR Import Smoke")
assert "FINISHED" in bpy.ops.sls.smart_uv_project()

files = {
    "BaseColor": (0.25, 0.08, 0.03, 1.0),
    "Roughness": (0.72, 0.72, 0.72, 1.0),
    "Metallic": (0.1, 0.1, 0.1, 1.0),
    "NormalDX": (0.5, 0.5, 1.0, 1.0),
    "Height": (0.5, 0.5, 0.5, 1.0),
    "AO": (0.9, 0.9, 0.9, 1.0),
    "Emissive": (0.0, 0.1, 0.3, 1.0),
}
paths = {}
for channel, color in files.items():
    path = fixture_dir / f"RustedMetal_{channel}_1K.png"
    image = bpy.data.images.new(f"Fixture {channel}", 8, 8, alpha=True)
    image.generated_color = color
    image.file_format = "PNG"
    image.filepath_raw = str(path)
    image.save()
    bpy.data.images.remove(image)
    assert path.is_file(), path
    paths[channel] = path

result = bpy.ops.sls.import_pbr_set(filepath=str(paths["BaseColor"]))
assert "FINISHED" in result, result
material = bpy.context.active_object.active_material
assert len(material.sls.layers) == 2
layer = material.sls.layers[0]
assert layer.name == "Rusted Metal"
assert layer.base_color_image and not layer.base_color_image.colorspace_settings.is_data
assert layer.roughness_image and layer.roughness_image.colorspace_settings.is_data
assert layer.metallic_image and layer.metallic_image.colorspace_settings.is_data
assert layer.normal_image and layer.normal_image.colorspace_settings.is_data
assert layer.height_image and layer.height_image.colorspace_settings.is_data
assert layer.ao_image and layer.ao_image.colorspace_settings.is_data
assert layer.emission_image and not layer.emission_image.colorspace_settings.is_data
assert layer.normal_format == "DIRECTX"
print("SLS_IMPORT_SMOKE_PASS channels=7")
