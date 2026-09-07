"""Native Blender evidence: gallery, quad views, regression, reopen, GUI."""
import sys
import json
import time
import traceback
import subprocess
from pathlib import Path
import bpy
from mathutils import Vector
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rockforge_studio as rf

args = sys.argv[sys.argv.index('--') + 1:]
mode = args[0]
output = Path(args[1]).resolve()
output.mkdir(parents=True, exist_ok=True)
rf.register()


def clear():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.orphans_purge(do_recursive=True)


def point(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def studio(low):
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = 48
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 94
    scene.world.use_nodes = True
    scene.world.node_tree.nodes['Background'].inputs[0].default_value = (0.31, 0.36, 0.42, 1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value = 0.32
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.exposure = -1.0
    try:
        scene.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    bounds = [low.matrix_world @ Vector(corner) for corner in low.bound_box]
    center = sum(bounds, Vector()) / 8
    bottom = min(vertex.z for vertex in bounds)
    size = max(low.dimensions)
    bpy.ops.mesh.primitive_plane_add(size=size * 200, location=(0, 0, bottom - 0.025))
    floor = bpy.context.object
    floor.name = 'Studio Ground'
    material = bpy.data.materials.new('Studio mineral grey')
    material.use_nodes = True
    surface = material.node_tree.nodes.get('Principled BSDF')
    surface.inputs['Base Color'].default_value = (0.125, 0.147, 0.156, 1)
    surface.inputs['Roughness'].default_value = 0.83
    floor.data.materials.append(material)
    bpy.ops.object.camera_add(location=center + Vector((1.45, -1.9, 1.03)) * size)
    camera = bpy.context.object
    camera.name = 'RockForge Camera'
    camera.data.type = 'ORTHO'
    camera.data.ortho_scale = size * 1.48
    point(camera, center + Vector((0, 0, -0.06 * size)))
    scene.camera = camera
    for title, position, power, diameter, color in (
        ('Warm key', (-1.1, -1.5, 2.0), 100, 1.25, (1, 0.9, 0.76)),
        ('Cool edge', (0.5, 1.2, 1.5), 160, 1.0, (0.73, 0.83, 1)),
        ('Front fill', (1.3, -0.5, 0.8), 45, 1.7, (0.89, 0.95, 1)),
    ):
        data = bpy.data.lights.new(title, 'AREA')
        data.energy = power * size * size
        data.shape = 'DISK'
        data.size = diameter * size
        data.color = color
        obj = bpy.data.objects.new(title, data)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(position) * size
        point(obj, center)


def render(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def topology(low, path):
    original_materials = list(low.data.materials)
    modifiers = [(modifier, modifier.show_render) for modifier in low.modifiers]
    for modifier, previous in modifiers:
        if modifier.type == 'TRIANGULATE':
            modifier.show_render = False
    clay = bpy.data.materials.new('Topology clay')
    clay.use_nodes = True
    surface = clay.node_tree.nodes.get('Principled BSDF')
    surface.inputs['Base Color'].default_value = (0.25, 0.4, 0.4, 1)
    surface.inputs['Roughness'].default_value = 0.78
    low.data.materials.clear()
    low.data.materials.append(clay)
    wire = rf.geometry.copy_object(low, 'Actual quad edges')
    for modifier in list(wire.modifiers):
        wire.modifiers.remove(modifier)
    dark = bpy.data.materials.new('Quad edges')
    dark.use_nodes = True
    dark.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (0.003, 0.008, 0.012, 1)
    wire.data.materials.clear()
    wire.data.materials.append(dark)
    modifier = wire.modifiers.new('Editable quad edges', 'WIREFRAME')
    modifier.thickness = max(low.dimensions) * 0.0009
    modifier.use_replace = True
    modifier.offset = 1
    try:
        render(path)
    finally:
        bpy.data.objects.remove(wire, do_unlink=True)
        low.data.materials.clear()
        for material in original_materials:
            low.data.materials.append(material)
        for modifier, previous in modifiers:
            modifier.show_render = previous


if mode == 'gallery':
    preset = args[2]
    name = {'BASALT': 'Basalt', 'LIMESTONE': 'Limestone', 'SLATE': 'Slate'}[preset]
    folder = output / 'examples' / name
    folder.mkdir(parents=True, exist_ok=True)
    images_folder = output / 'images'
    images_folder.mkdir(exist_ok=True)
    clear()
    settings = bpy.context.scene.rockforge
    settings.preset = preset
    settings.seed = {'BASALT': 42, 'LIMESTONE': 17, 'SLATE': 73}[preset]
    settings.density = 176
    settings.quads = 6000
    settings.resolution = '2048'
    if preset == 'BASALT':
        settings.width, settings.depth, settings.height = 5, 3.5, 2.6
    if preset == 'SLATE':
        settings.formation = 'RIDGE'
        settings.width, settings.depth, settings.height = 5, 2.8, 2.5
        settings.blocks = 28
    config = rf.configuration(settings)
    start = time.monotonic()
    low, high = rf.pipeline.build(config)
    build_seconds = time.monotonic() - start
    start = time.monotonic()
    textures = rf.pipeline.bake(low, high, folder / 'textures', 2048, 24)
    bake_seconds = time.monotonic() - start
    rf.pipeline.export_glb(low, folder / (name + '.glb'))
    lods = rf.pipeline.make_lods(low)
    for index, lod in enumerate(lods, 1):
        rf.pipeline.export_glb(lod, folder / (name + f'_LOD{index}.glb'))
    proxy = rf.pipeline.collision(low)
    report = {'runtime': bpy.app.version_string, 'preset': preset, 'config': config,
        'build_seconds': build_seconds, 'bake_seconds': bake_seconds,
        'low': rf.geometry.mesh_audit(low), 'high': rf.geometry.mesh_audit(high),
        'lod_triangles': [rf.geometry.mesh_audit(lod)['triangles'] for lod in lods],
        'collision_triangles': rf.geometry.mesh_audit(proxy)['triangles'], 'resolution': 2048,
        'textures': {key: Path(image.filepath_raw).name for key, image in textures.items()}}
    for image in textures.values():
        image.filepath = '//textures/' + Path(image.filepath_raw).name
    studio(low)
    rf.geometry.activate(low)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                space.region_3d.view_perspective = 'CAMERA'
                space.overlay.show_overlays = False
                space.shading.type = 'SOLID'
                space.shading.color_type = 'MATERIAL'
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / (name + '.blend')), compress=True)
    render(images_folder / (name + '.jpg'))
    topology(low, images_folder / (name + '-topology.jpg'))
    rf.geometry.activate(low)
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / (name + '.blend')), compress=True)
    (folder / 'mesh-report.json').write_text(json.dumps(report, indent=2))
    print('RF_EXAMPLE_DONE', json.dumps(report), flush=True)

elif mode == 'matrix':
    report = {'runtime': bpy.app.version_string, 'cases': [], 'success': False}
    for preset in rf.geometry.PRESETS:
        for seed, formation in ((3, 'MOUND'), (47, 'RIDGE'), (109, 'BOULDER')):
            case = {'preset': preset, 'seed': seed, 'formation': formation, 'passed': False}
            try:
                clear()
                settings = bpy.context.scene.rockforge
                settings.preset = preset
                settings.seed = seed
                settings.formation = formation
                settings.density = 80
                settings.quads = 1200
                low, high = rf.pipeline.build(rf.configuration(settings))
                audit = rf.geometry.mesh_audit(low)
                case['audit'] = audit
                case['passed'] = bool(audit['structurally_valid'] and audit['components'] == 1 and audit['faces'] == audit['quads'] and audit['uv_in_0_1'])
            except BaseException:
                case['error'] = traceback.format_exc()
            report['cases'].append(case)
            print('RF_MATRIX_CASE', json.dumps(case), flush=True)
    report['success'] = all(case['passed'] for case in report['cases'])
    (output / 'seed-matrix.json').write_text(json.dumps(report, indent=2))
    if not report['success']:
        raise RuntimeError('Preset/seed regression failed')

elif mode == 'reopen':
    rocks = [obj for obj in bpy.data.objects if obj.get('rf_role') == 'LOW' and obj.get('rf_baked')]
    images = [image for image in bpy.data.images if image.type == 'IMAGE' and image.size[0] > 128]
    report = {'runtime': bpy.app.version_string, 'blend': bpy.data.filepath, 'baked_rocks': len(rocks),
        'texture_images': len(images), 'packed': all(bool(image.packed_file) for image in images)}
    report['success'] = len(rocks) > 0 and len(images) >= 4 and report['packed']
    (output / 'reopen.json').write_text(json.dumps(report, indent=2))
    if not report['success']:
        raise RuntimeError('Packed-scene reopen check failed')

elif mode == 'ui':
    low = next(obj for obj in bpy.data.objects if obj.get('rf_role') == 'LOW')
    rf.geometry.activate(low)
    bpy.ops.rockforge.load_settings()
    bpy.context.scene.rockforge.resolution = '2048'

    def configure():
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    space = area.spaces.active
                    space.show_region_ui = True
                    space.shading.type = 'SOLID'
                    space.shading.color_type = 'MATERIAL'
                    space.overlay.show_overlays = False
                    space.region_3d.view_perspective = 'CAMERA'
                    for region in area.regions:
                        if region.type == 'UI':
                            try:
                                region.active_panel_category = 'RockForge'
                            except Exception:
                                pass
        return None

    def capture():
        report = {'runtime': bpy.app.version_string, 'success': False, 'kind': 'Native Xvfb desktop screenshot'}
        try:
            path = output / 'Blender-Interface.png'
            subprocess.run(['/usr/bin/import', '-window', 'root', str(path)], check=True, timeout=25)
            image = bpy.data.images.load(str(path), check_existing=False)
            pixels = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(pixels)
            report['pixel_std'] = float(pixels.reshape(-1, 4)[:, :3].std())
            report['success'] = path.stat().st_size > 20000 and report['pixel_std'] > 0.03
            bpy.data.images.remove(image)
        except BaseException:
            report['error'] = traceback.format_exc()
        (output / 'ui.json').write_text(json.dumps(report, indent=2))
        bpy.ops.wm.quit_blender()
        return None

    bpy.app.timers.register(configure, first_interval=3)
    bpy.app.timers.register(capture, first_interval=40)
else:
    raise ValueError('Unknown evidence mode: ' + mode)
