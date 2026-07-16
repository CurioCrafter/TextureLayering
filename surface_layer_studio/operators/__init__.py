"""Operator registration."""

from __future__ import annotations

import bpy

from . import importers, masks, stack, surface


_MODULES = (stack, masks, surface, importers)
_CLASSES = tuple(cls for module in _MODULES for cls in module.CLASSES)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
