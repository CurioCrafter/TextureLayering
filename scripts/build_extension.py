"""Reproducibly package the extension; run from any current directory."""
from pathlib import Path
import tomllib
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'surface_layer_studio'
version = tomllib.loads((SOURCE / 'blender_manifest.toml').read_text())['version']
target = ROOT / 'dist' / f'surface_layer_studio-{version}.zip'
target.parent.mkdir(exist_ok=True)
with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.suffix in {'.pyc', '.pyo'}:
            continue
        info = ZipInfo(path.relative_to(SOURCE).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, path.read_bytes())
print(target)
