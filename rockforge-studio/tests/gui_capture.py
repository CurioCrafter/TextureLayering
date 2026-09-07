"""Capture the real RockForge sidebar using native Blender mouse events.

Launch Blender with --enable-event-simulate. The workflow creates a no-splash
preference file first, so a first-run modal cannot cover the asset or controls.
"""
import sys
import json
import traceback
import subprocess
import shutil
from pathlib import Path
import bpy
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rockforge_studio as rf
rf.register()
output = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
output.mkdir(parents=True, exist_ok=True)
low = next(obj for obj in bpy.data.objects if obj.get('rf_role') == 'LOW')
rf.geometry.activate(low)
bpy.ops.rockforge.load_settings()
settings = bpy.context.scene.rockforge
settings.resolution = '2048'
Path(bpy.path.abspath(settings.output)).mkdir(parents=True, exist_ok=True)
state = {'attempt': 0, 'area': None}
report = {'runtime': bpy.app.version_string, 'success': False,
          'kind': 'Native Blender window and actual RockForge sidebar',
          'interaction': 'Blender event_simulate mouse events'}


def finish():
    (output / 'ui.json').write_text(json.dumps(report, indent=2))
    bpy.ops.wm.quit_blender()
    return None


def configure():
    try:
        area = max((a for a in bpy.context.window.screen.areas if a.type == 'VIEW_3D'),
                   key=lambda a: a.width * a.height)
        state['area'] = area
        space = area.spaces.active
        space.show_region_ui = True
        space.shading.type = 'SOLID'
        space.shading.color_type = 'MATERIAL'
        space.overlay.show_overlays = False
        space.region_3d.view_perspective = 'CAMERA'
        bpy.app.timers.register(select_tab, first_interval=2)
    except BaseException:
        report['error'] = traceback.format_exc()
        return finish()
    return None


def select_tab():
    try:
        area = state['area']
        window = bpy.context.window
        region = next(r for r in area.regions if r.type == 'UI')
        if region.active_panel_category == 'RockForge':
            report['active_sidebar'] = region.active_panel_category
            window.cursor_warp(area.x + 180, area.y + 180)
            bpy.app.timers.register(capture, first_interval=2)
            return None
        attempt = state['attempt']
        if attempt > 25:
            raise RuntimeError('RockForge sidebar was not activated by the native UI clicks.')
        state['attempt'] += 1
        x = area.x + area.width - 12
        y = area.y + area.height - 65 - attempt * 15
        window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
        window.event_simulate(type='LEFTMOUSE', value='PRESS', x=x, y=y)
        window.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x, y=y)
        return 0.25
    except BaseException:
        report['error'] = traceback.format_exc()
        return finish()


def capture():
    try:
        executable = shutil.which('import')
        if executable is None:
            raise RuntimeError('An X11-enabled ImageMagick import executable is required.')
        path = output / 'Blender-Interface.png'
        subprocess.run([executable, '-window', 'root', str(path)], check=True, timeout=25)
        image = bpy.data.images.load(str(path), check_existing=False)
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        report['pixel_std'] = float(pixels.reshape(-1, 4)[:, :3].std())
        report['image_bytes'] = path.stat().st_size
        report['success'] = (report.get('active_sidebar') == 'RockForge'
                             and report['image_bytes'] > 20000 and report['pixel_std'] > 0.03)
        bpy.data.images.remove(image)
    except BaseException:
        report['error'] = traceback.format_exc()
    return finish()


bpy.app.timers.register(configure, first_interval=3)
