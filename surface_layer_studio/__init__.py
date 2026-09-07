"""Surface Layer Studio - non-destructive PBR texture layering for Blender."""

from __future__ import annotations

try:
    import bpy  # type: ignore
except ModuleNotFoundError:  # Allows pure-Python unit tests outside Blender.
    bpy = None


if bpy is not None:
    from . import operators, properties, ui, desk

    _MODULES = (properties, operators, ui, desk)
else:
    _MODULES = ()


def register() -> None:
    if bpy is None:
        raise RuntimeError("Surface Layer Studio must be registered inside Blender")
    for module in _MODULES:
        module.register()


def unregister() -> None:
    if bpy is None:
        return
    for module in reversed(_MODULES):
        module.unregister()
