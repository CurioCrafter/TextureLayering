"""Build the installer, or package a complete release after all evidence passes."""
from pathlib import Path
import sys
import json
import zipfile
import hashlib
import shutil

ROOT = Path(__file__).resolve().parent
DIST = ROOT / 'dist'
DIST.mkdir(exist_ok=True)
INSTALLER = DIST / 'RockForge-Studio-1.0.0.zip'


def digest(path):
    hasher = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def build_installer():
    with zipfile.ZipFile(INSTALLER, 'w', zipfile.ZIP_DEFLATED) as archive:
        files = [(path, 'rockforge_studio/' + path.name) for path in sorted((ROOT / 'rockforge_studio').glob('*.py'))]
        files += [(ROOT / name, 'rockforge_studio/' + name) for name in ('README.md', 'LICENSE')]
        for path, destination in files:
            if path.suffix == '.py':
                compile(path.read_text(encoding='utf-8'), str(path), 'exec')
            info = zipfile.ZipInfo(destination, date_time=(2026, 9, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(INSTALLER) as archive:
        assert archive.testzip() is None
        assert 'rockforge_studio/__init__.py' in archive.namelist()
    receipt = {'filename': INSTALLER.name, 'bytes': INSTALLER.stat().st_size, 'sha256': digest(INSTALLER)}
    (DIST / 'installer.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt), flush=True)


def package(output):
    assert INSTALLER.is_file()
    reports = []
    for version in ('45', '52'):
        path = output / ('verification' + version) / 'verification.json'
        report = json.loads(path.read_text())
        assert report['success'] and all(report['checks'].values()), str(path)
        assert report['installer_sha256'] == digest(INSTALLER), 'Tests were not run against this installer'
        reports.append(report)
    matrix = json.loads((output / 'seed-matrix.json').read_text())
    assert matrix['success'] and len(matrix['cases']) == 18
    examples = []
    for name in ('Basalt', 'Limestone', 'Slate'):
        folder = output / 'examples' / name
        report = json.loads((folder / 'mesh-report.json').read_text())
        assert report['low']['structurally_valid'] and report['low']['faces'] == report['low']['quads']
        for extension in ('.blend', '.glb'):
            assert (folder / (name + extension)).stat().st_size > 10000
        for suffix in ('.jpg', '-topology.jpg'):
            assert (output / 'images' / (name + suffix)).stat().st_size > 20000
        assert json.loads((folder / 'reopen.json').read_text())['success']
        examples.append(report)
    ui = json.loads((output / 'images' / 'ui.json').read_text())
    assert ui['success'], 'Native GUI capture failed'
    verification = {'installed_zip_tests': reports, 'seed_matrix': matrix, 'examples': examples, 'ui': ui,
        'limitations': ['No guarantee of perfect geometry or texturing for arbitrary settings.',
            'Reference retopology transfers shape only, not reference textures.',
            'LOD normal maps are reused; inspect at intended viewing distance.',
            'QuadriFlow targets are approximate and may vary between versions or threads.',
            'Structural checks do not prove optimal topology or absence of every self-intersection.']}
    verification_path = DIST / 'Verification.json'
    verification_path.write_text(json.dumps(verification, indent=2))
    complete = DIST / 'RockForge-Studio-Complete.zip'
    with zipfile.ZipFile(complete, 'w', zipfile.ZIP_DEFLATED, compresslevel=4) as archive:
        archive.write(INSTALLER, INSTALLER.name)
        archive.write(verification_path, verification_path.name)
        for name in ('README.md', 'LICENSE', 'build.py'):
            archive.write(ROOT / name, name)
        for directory in ('rockforge_studio', 'tests'):
            for path in sorted((ROOT / directory).glob('*.py')):
                archive.write(path, 'source/' + str(path.relative_to(ROOT)))
        for directory in ('examples', 'images'):
            for path in sorted((output / directory).rglob('*')):
                if path.is_file() and path.suffix not in ('.blend1', '.pyc'):
                    archive.write(path, str(path.relative_to(output)))
        archive.write(output / 'seed-matrix.json', 'evidence/seed-matrix.json')
        for version in ('45', '52'):
            archive.write(output / ('verification' + version) / 'verification.json', 'evidence/blender-' + version + '.json')
    with zipfile.ZipFile(complete) as archive:
        assert archive.testzip() is None
    for path in (output / 'images').glob('*'):
        if path.suffix in ('.jpg', '.png'):
            shutil.copyfile(path, DIST / path.name)
    files = [INSTALLER, complete, verification_path] + list(DIST.glob('*.jpg')) + list(DIST.glob('*.png'))
    (DIST / 'SHA256SUMS.txt').write_text(''.join(digest(path) + '  ' + path.name + '\n' for path in files))
    print(json.dumps({'complete_bytes': complete.stat().st_size, 'assets': [path.name for path in files]}, indent=2), flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--complete':
        package(Path(sys.argv[2]).resolve())
    else:
        build_installer()
