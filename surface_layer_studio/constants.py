"""Constants kept separate to make UI and shader behavior easy to audit."""

ADDON_ID = "surface_layer_studio"
ADDON_VERSION = (1, 0, 0)
MANAGED_TAG = "sls_managed"
NODE_PREFIX = "SLS_"
MASK_NODE_SUFFIX = "_MASK"
DEFAULT_UV_NAME = "SurfaceUV"

BLEND_MODES = (
    ("MIX", "Normal", "Normal alpha-style layering"),
    ("MULTIPLY", "Multiply", "Darken using the layer color"),
    ("OVERLAY", "Overlay", "Increase contrast while preserving detail"),
    ("SOFT_LIGHT", "Soft Light", "Gentle contrast and color variation"),
    ("SCREEN", "Screen", "Lighten using the layer color"),
    ("ADD", "Add", "Add the layer color"),
    ("DARKEN", "Darken", "Keep the darker result"),
    ("LIGHTEN", "Lighten", "Keep the lighter result"),
)

PREVIEW_MODES = (
    ("COMPOSITE", "Composite", "Show the complete layered material"),
    ("ACTIVE_MASK", "Active Mask", "Show the active grayscale paint mask"),
    ("BASE_COLOR", "Base Color", "Show the final base-color channel"),
    ("ROUGHNESS", "Roughness", "Show the final roughness channel"),
    ("METALLIC", "Metallic", "Show the final metallic channel"),
    ("NORMAL", "Normal", "Show the blended tangent-space normal colors"),
    ("HEIGHT", "Height", "Show the blended height channel"),
    ("EMISSION", "Emission", "Show the blended emission channel"),
)

MASK_RESOLUTIONS = (
    ("256", "256", "Fast draft mask"),
    ("512", "512", "Small props and draft work"),
    ("1024", "1K", "General-purpose mask"),
    ("2048", "2K", "Detailed ship surfaces"),
    ("4096", "4K", "Hero surfaces; higher memory use"),
    ("8192", "8K", "Extreme detail; very high memory use"),
)
