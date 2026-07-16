"""Automatic PBR texture-set import."""

from __future__ import annotations

from pathlib import Path

import bpy
from bpy.props import StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper

from .. import images, nodes
from ..core import detect_normal_format, detect_pbr_set, friendly_layer_name
from .common import add_layer, managed_material


_CHANNEL_TO_PROPERTY = {
    "base_color": "base_color_image",
    "roughness": "roughness_image",
    "metallic": "metallic_image",
    "normal": "normal_image",
    "height": "height_image",
    "ambient_occlusion": "ao_image",
    "emission": "emission_image",
}


class SLS_OT_import_pbr_set(Operator, ImportHelper):
    bl_idname = "sls.import_pbr_set"
    bl_label = "Import PBR Texture Set"
    bl_description = "Choose one texture; matching base color, roughness, metallic, normal, height, AO, and emission files are found automatically"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ""
    filter_glob: StringProperty(
        default="*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.tga;*.bmp;*.exr;*.hdr;*.webp;*.psd",
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        return managed_material(context) is not None

    def execute(self, context):
        material = managed_material(context)
        assert material is not None
        selected = Path(self.filepath)
        if not selected.is_file():
            self.report({"ERROR"}, "Choose one image from the PBR texture set")
            return {"CANCELLED"}
        try:
            candidates = tuple(path for path in selected.parent.iterdir() if path.is_file())
        except OSError as exc:
            self.report({"ERROR"}, f"Cannot scan texture folder: {exc}")
            return {"CANCELLED"}
        detected = detect_pbr_set(selected, candidates)
        if not detected:
            detected = {"base_color": selected}

        layer = add_layer(
            context,
            material,
            friendly_layer_name(selected),
            fill=context.scene.sls_tools.new_layer_fill,
        )
        layer.tint = (1.0, 1.0, 1.0, 1.0)
        loaded: list[str] = []
        failures: list[str] = []
        for channel, path in detected.items():
            prop_name = _CHANNEL_TO_PROPERTY.get(channel)
            if prop_name is None:
                continue
            try:
                image = bpy.data.images.load(str(path), check_existing=True)
                images.set_color_space(image, is_data=channel not in {"base_color", "emission"})
                setattr(layer, prop_name, image)
                loaded.append(channel.replace("_", " "))
                if channel == "normal":
                    layer.normal_format = detect_normal_format(path)
            except (RuntimeError, OSError) as exc:
                failures.append(f"{path.name}: {exc}")
        if not loaded:
            material.sls.layers.remove(material.sls.active_index)
            self.report({"ERROR"}, "No images in the selected texture set could be loaded")
            return {"CANCELLED"}
        nodes.rebuild_material(material)
        message = f"Imported {layer.name}: {', '.join(loaded)}"
        if failures:
            self.report({"WARNING"}, f"{message}. {len(failures)} file(s) failed.")
        else:
            self.report({"INFO"}, message)
        return {"FINISHED"}


CLASSES = (SLS_OT_import_pbr_set,)
