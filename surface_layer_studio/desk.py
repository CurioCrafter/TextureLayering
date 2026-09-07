"""Shipwreck Texture Desk feature lifecycle."""
from . import desk_props, desk_ops, desk_bake, desk_workspace, desk_ui

_MODULES = (desk_props, desk_ops, desk_bake, desk_workspace, desk_ui)


def register():
    registered = []
    try:
        for module in _MODULES:
            module.register()
            registered.append(module)
    except Exception:
        for module in reversed(registered):
            module.unregister()
        raise


def unregister():
    for module in reversed(_MODULES):
        module.unregister()
