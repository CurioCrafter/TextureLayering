"""Launch in a real Blender window; capture the implemented UI, never a mockup."""
import argparse
from pathlib import Path
import sys
import math
import traceback
import os
import subprocess
import bpy
from mathutils import Quaternion, Euler, Vector

p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--output',required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
sys.path.insert(0,str(Path(a.source_root).resolve()))
out=Path(a.output).resolve();out.mkdir(exist_ok=True,parents=True)
for stale in ('gui-failure.txt','gui-report.txt'):
    (out/stale).unlink(missing_ok=True)
import surface_layer_studio as addon
from surface_layer_studio import nodes
from surface_layer_studio.desk_ops import apply_preset
addon.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.sls_tools.mask_resolution='512'
# A deliberately simple ship-interior sample panel with inset ribs and bolt heads.
bpy.ops.mesh.primitive_cube_add(size=2)
panel=bpy.context.active_object;panel.name='Weathered bulkhead — demo geometry'
panel.scale=(2,.14,1.6);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
bev=panel.modifiers.new('Manufactured edge radius','BEVEL');bev.width=.055;bev.segments=3
bpy.ops.object.modifier_apply(modifier=bev.name)
bpy.ops.sls.setup_material(material_name='Shipwreck / painted bulkhead')
bpy.ops.sls.smart_uv_project()
material=panel.active_material
for id in ('teal_paint','hull_oxide','biofilm'):
    apply_preset(bpy.context,id)
material.sls.bump_distance=.028
material.sls.layers[0].desk.coverage=.3
material.sls.layers[1].desk.coverage=.52
nodes.rebuild_material(material)
# Shared-material geometry provides recognizable scale without pretending to be a user asset.
for x in (-1.9,1.9):
    bpy.ops.mesh.primitive_cube_add(size=2,location=(x,-.2,0))
    rib=bpy.context.active_object;rib.scale=(.04,.05,1.5);rib.data.materials.append(material)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=rib.modifiers.new('Rounded rib','BEVEL');bevel.width=.022;bevel.segments=3
for x in (-1.68,1.68):
    for z in (-1.25,0,1.25):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.075,location=(x,-.17,z))
        bolt=bpy.context.active_object;bolt.scale=(1,.38,1);bolt.data.materials.append(material)
        for f in bolt.data.polygons:f.use_smooth=True
bpy.ops.object.select_all(action='SELECT');bpy.context.view_layer.objects.active=panel
bpy.ops.object.join()
bpy.ops.sls.smart_uv_project()
scene.sls_desk.tab='LIBRARY';scene.sls_desk.category='Marine growth';scene.sls_desk.canvas_tab='LAB'
scene.sls_desk.target='mask_image';scene.sls_desk.lab_pattern='NOISE';scene.sls_desk.lab_coverage=.28
bpy.ops.sls.desk_generate()
original=bpy.context.window.workspace
original_screen=bpy.context.window.screen
original_layout=[(area.type,area.x,area.y,area.width,area.height) for area in original_screen.areas]


def fail():
    (out/'gui-failure.txt').write_text(traceback.format_exc())
    traceback.print_exc()
    bpy.ops.wm.quit_blender()


def open_workspace():
    try:
        result=bpy.ops.sls.desk_workspace()
        assert 'FINISHED' in result,result
        bpy.app.timers.register(frame_workspace,first_interval=3.5)
    except Exception:fail()


def frame_workspace():
    try:
        window=bpy.context.window
        print('SLS_GUI_WORKSPACE',window.workspace.name,[(a.type,a.width,a.height) for a in window.screen.areas],flush=True)
        assert window.workspace.name=='Shipwreck Desk'
        current_original=[(area.type,area.x,area.y,area.width,area.height) for area in original_screen.areas]
        assert current_original==original_layout,('Original workspace changed',original_layout,current_original)
        for area in window.screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_rotation=Euler((math.radians(82),0,math.radians(-12)),'XYZ').to_quaternion()
                area.spaces.active.region_3d.view_distance=7
                area.spaces.active.region_3d.view_location=(.65,0,0)
                area.spaces.active.shading.studiolight_rotate_z=.6
                area.spaces.active.shading.studiolight_background_alpha=0
            if area.type=='IMAGE_EDITOR':
                area.spaces.active.image=material.sls.layers[0].mask_image
                region=next(r for r in area.regions if r.type=='WINDOW')
                with bpy.context.temp_override(window=window,area=area,region=region):bpy.ops.image.view_all(fit_view=True)
        bpy.app.timers.register(capture_library,first_interval=12)
    except Exception:fail()


def screenshot(path):
    # Window-system capture works around black framebuffer reads under Xvfb/Mesa.
    capture=os.environ.get('SLS_CAPTURE_PYTHON')
    if capture:
        script="from PIL import ImageGrab; import os,sys; i=ImageGrab.grab(xdisplay=os.environ['DISPLAY']); assert max(i.getextrema()[0])>0, 'Black screen capture'; i.save(sys.argv[1])"
        subprocess.run([capture,'-c',script,str(path)],check=True,timeout=15)
    else:
        bpy.ops.screen.screenshot(filepath=str(path))


def capture_library():
    try:
        screenshot(out/'shipwreck-desk-library.png')
        scene.sls_desk.tab='LAYERS';scene.sls_desk.canvas_tab='PAINT'
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:area.tag_redraw()
        bpy.app.timers.register(capture_layers,first_interval=2)
    except Exception:fail()


def capture_layers():
    try:
        screenshot(out/'shipwreck-desk-layers.png')
        print('SLS_GUI_PASS original workspace preserved; two screenshots saved',flush=True)
        (out/'gui-report.txt').write_text('PASS: workspace duplication, source layout preservation, native viewport and image panels, screenshots.\nBlender '+bpy.app.version_string)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'shipwreck-desk-demo.blend'))
        bpy.ops.wm.quit_blender()
    except Exception:fail()

bpy.app.timers.register(open_workspace,first_interval=1)
