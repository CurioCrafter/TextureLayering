"""Pure-Python helpers shared by the add-on and its unit tests."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable


IMAGE_EXTENSIONS = {
    ".bmp",
    ".cin",
    ".dpx",
    ".exr",
    ".hdr",
    ".jpeg",
    ".jpg",
    ".png",
    ".psd",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
}

CHANNEL_ALIASES: dict[str, tuple[str, ...]] = {
    "base_color": (
        "base_color",
        "basecolor",
        "base_colour",
        "basecolour",
        "diffuse",
        "albedo",
        "color",
        "colour",
        "diff",
    ),
    "roughness": ("roughness", "rough"),
    "metallic": ("metallic", "metalness", "metal"),
    "normal": (
        "normal_directx",
        "normal_opengl",
        "normaldx",
        "normalgl",
        "normal_dx",
        "normal_gl",
        "normal",
        "nor",
        "nrm",
    ),
    "height": ("displacement", "height", "disp", "bump"),
    "ambient_occlusion": ("ambient_occlusion", "ambientocclusion", "occlusion", "ao"),
    "emission": ("emissive", "emission", "emit"),
}

_DECORATION_TOKENS = {
    "1k",
    "2k",
    "4k",
    "8k",
    "16k",
    "8bit",
    "16bit",
    "32bit",
    "linear",
    "srgb",
    "udim",
    "1001",
}


def _normalized_stem(path: str | Path) -> str:
    stem = Path(path).stem
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", stem)
    stem = stem.casefold()
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_")


def detect_channel(path: str | Path) -> str | None:
    """Return the most likely PBR channel encoded in a filename."""

    stem = _normalized_stem(path)
    padded = f"_{stem}_"
    matches: list[tuple[int, int, str]] = []
    for channel, aliases in CHANNEL_ALIASES.items():
        for alias in aliases:
            token = f"_{alias}_"
            position = padded.rfind(token)
            if position >= 0:
                # Channel suffixes normally appear after the material identity.
                # Position outranks alias length so "RustedMetal_AO" is AO,
                # not metallic because the asset name happens to contain Metal.
                matches.append((position, len(alias), channel))
    if not matches:
        return None
    return max(matches)[2]


def texture_set_key(path: str | Path) -> str:
    """Create a stable key for files belonging to one PBR texture set."""

    stem = _normalized_stem(path)
    channel = detect_channel(path)
    if channel is not None:
        padded = f"_{stem}_"
        for alias in sorted(CHANNEL_ALIASES[channel], key=len, reverse=True):
            token = f"_{alias}_"
            if token in padded:
                padded = padded.replace(token, "_", 1)
                stem = padded.strip("_")
                break
    tokens = stem.split("_")
    ignored = _DECORATION_TOKENS | {"dx", "gl", "directx", "opengl"}
    kept = [token for token in tokens if token not in ignored and not re.fullmatch(r"\d{4}", token)]
    return "_".join(kept) or stem


def detect_normal_format(path: str | Path) -> str:
    """Return DIRECTX when a filename explicitly says DX; OPENGL otherwise."""

    stem = _normalized_stem(path)
    tokens = set(stem.split("_"))
    if "directx" in tokens or "dx" in tokens or "normaldx" in tokens:
        return "DIRECTX"
    return "OPENGL"


def detect_pbr_set(selected_path: str | Path, candidates: Iterable[str | Path]) -> dict[str, Path]:
    """Find channel images that share the selected file's material stem.

    Duplicate candidates for a channel are resolved deterministically: an exact
    texture-set key wins, followed by the shortest filename and lexical order.
    """

    selected = Path(selected_path)
    selected_key = texture_set_key(selected)
    ranked: dict[str, list[tuple[int, int, str, Path]]] = {}

    for candidate_value in candidates:
        candidate = Path(candidate_value)
        if candidate.suffix.casefold() not in IMAGE_EXTENSIONS:
            continue
        channel = detect_channel(candidate)
        if channel is None:
            continue
        key = texture_set_key(candidate)
        exact_rank = 0 if key == selected_key else 1
        related = key == selected_key or key.startswith(selected_key) or selected_key.startswith(key)
        if not related:
            continue
        ranked.setdefault(channel, []).append(
            (exact_rank, len(candidate.name), candidate.name.casefold(), candidate)
        )

    result = {channel: min(options)[-1] for channel, options in ranked.items()}
    selected_channel = detect_channel(selected)
    if selected_channel is not None and selected.suffix.casefold() in IMAGE_EXTENSIONS:
        result[selected_channel] = selected
    return result


def friendly_layer_name(path: str | Path) -> str:
    key = texture_set_key(path)
    words = [word for word in key.split("_") if word]
    return " ".join(word.upper() if word.isdigit() else word.title() for word in words) or "Texture Layer"


def safe_filename(value: str, fallback: str = "layer") -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    while ".." in value:
        value = value.replace("..", "_")
    value = value.strip("._-")
    return value or fallback
