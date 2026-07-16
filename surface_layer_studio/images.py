"""Image datablock creation, copying, filling, packing, and export helpers."""

from __future__ import annotations

from pathlib import Path

import bpy

from .core import safe_filename


def set_color_space(image: bpy.types.Image | None, *, is_data: bool) -> None:
    if image is None:
        return
    desired = "Non-Color" if is_data else "sRGB"
    try:
        image.colorspace_settings.name = desired
    except TypeError:
        # A custom OCIO config can use different display names. Blender's data
        # flag is the stable fallback when the stock name is unavailable.
        try:
            image.colorspace_settings.is_data = is_data
        except AttributeError:
            pass


def mask_fill_value(fill: str | float) -> float:
    if isinstance(fill, (int, float)):
        return min(max(float(fill), 0.0), 1.0)
    return {"BLACK": 0.0, "GRAY": 0.5, "WHITE": 1.0}.get(fill, 0.0)


def create_mask(
    material: bpy.types.Material,
    layer_name: str,
    layer_id: str,
    size: int,
    fill: str | float,
    *,
    pack: bool,
) -> bpy.types.Image:
    value = mask_fill_value(fill)
    short_id = layer_id.replace("-", "")[:8]
    image_name = f"SLS_{safe_filename(material.name)}_{safe_filename(layer_name)}_{short_id}_Mask"
    image = bpy.data.images.new(
        name=image_name,
        width=size,
        height=size,
        alpha=False,
        float_buffer=False,
        is_data=True,
    )
    image.generated_type = "BLANK"
    image.generated_color = (value, value, value, 1.0)
    set_color_space(image, is_data=True)
    image["sls_mask"] = True
    image["sls_layer_id"] = layer_id
    image["sls_material"] = material.name
    if pack:
        try:
            image.pack()
        except RuntimeError:
            # Generated images are still stored in the blend before their first
            # external save. The pack-all operator retries after painting.
            pass
    return image


def fill_image(image: bpy.types.Image, value: float) -> None:
    """Fill a regular mask without allocating a multi-gigabyte Python list."""

    value = min(max(float(value), 0.0), 1.0)
    width, height = int(image.size[0]), int(image.size[1])
    if width < 1 or height < 1:
        raise RuntimeError("Mask image has no pixel storage")
    if image.source == "TILED":
        raise RuntimeError("UDIM mask filling is not available in this release")
    image.scale(1, 1)
    image.pixels[:] = (value, value, value, 1.0)
    image.scale(width, height)
    image.generated_color = (value, value, value, 1.0)
    image.update()


def duplicate_mask(
    source: bpy.types.Image,
    material: bpy.types.Material,
    layer_name: str,
    layer_id: str,
    *,
    pack: bool,
) -> bpy.types.Image:
    image = source.copy()
    short_id = layer_id.replace("-", "")[:8]
    image.name = f"SLS_{safe_filename(material.name)}_{safe_filename(layer_name)}_{short_id}_Mask"
    image["sls_mask"] = True
    image["sls_layer_id"] = layer_id
    image["sls_material"] = material.name
    set_color_space(image, is_data=True)
    if pack:
        try:
            image.pack()
        except RuntimeError:
            pass
    return image


def estimated_memory_mb(image: bpy.types.Image | None) -> float:
    if image is None or image.size[0] < 1 or image.size[1] < 1:
        return 0.0
    channels = int(getattr(image, "channels", 4) or 4)
    bytes_per_channel = 4 if image.is_float else 1
    return image.size[0] * image.size[1] * channels * bytes_per_channel / (1024.0 * 1024.0)


def export_mask(image: bpy.types.Image, directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{safe_filename(filename)}.png"
    image.file_format = "PNG"
    image.filepath_raw = str(target)
    image.save()
    return target
