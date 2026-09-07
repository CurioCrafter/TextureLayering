"""CI render driver: unchanged 2K asset bakes, full-size adaptive preview renders."""
from pathlib import Path
import json
import runpy
import sys
import bpy


def preview_samples(scene, *args):
    scene.cycles.samples = 32
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.035
    scene.cycles.use_denoising = True


bpy.app.handlers.render_pre.append(preview_samples)
runpy.run_path(str(Path(__file__).with_name('produce.py')), run_name='__main__')
args = sys.argv[sys.argv.index('--') + 1:]
if args[0] == 'gallery':
    name = {'BASALT': 'Basalt', 'LIMESTONE': 'Limestone', 'SLATE': 'Slate'}[args[2]]
    path = Path(args[1]) / 'examples' / name / 'mesh-report.json'
    report = json.loads(path.read_text())
    report['render_sampling'] = {'max_samples': 32, 'adaptive_threshold': 0.035, 'denoising': True}
    path.write_text(json.dumps(report, indent=2))
