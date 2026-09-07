"""Execute in a fresh Blender profile against the packaged installer."""
import sys
import json
import hashlib
import struct
import traceback
from pathlib import Path
import bpy
import addon_utils
import numpy as np

args = sys.argv[sys.argv.index('--') + 1:]
installer = Path(args[0]).resolve()
output = Path(args[1]).resolve()
output.mkdir(parents=True, exist_ok=True)
report = {'runtime': bpy.app.version_string, 'installer_sha256': hashlib.sha256(installer.read_bytes()).hexdigest(), 'checks': {}, 'success': False}


def check(name, value):
    report['checks'][name] = bool(value)
    print('RF_CHECK', name, bool(value), flush=True)
    assert value, name


def fingerprint(obj):
    coordinates = np.empty(len(obj.data.vertices) * 3, dtype=np.float32)
    obj.data.vertices.foreach_get('co', coordinates)
    return hashlib.sha256(coordinates.tobytes()).hexdigest()


try:
    check('install_zip', 'FINISHED' in bpy.ops.preferences.addon_install(filepath=str(installer), overwrite=True))
    bpy.utils.refresh_script_paths()
    addon_utils.modules(refresh=True)
    rf = addon_utils.enable('rockforge_studio', default_set=False, persistent=False)
    check('native_registration', bool(rf and addon_utils.check('rockforge_studio')[1]))
    report['module_file'] = rf.__file__
    report['version'] = list(rf.bl_info['version'])
    check('sidebar_registered', hasattr(bpy.types, 'RF_PT_main'))
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    settings = bpy.context.scene.rockforge
    settings.preset = 'LIMESTONE'
    settings.seed = 23
    settings.density = 80
    settings.quads = 1000
    check('preset_applied', abs(settings.height - 1.8) < 1e-5)
    check('build_operator', 'FINISHED' in bpy.ops.rockforge.build(bake_textures=False))
    low = bpy.context.object
    high = bpy.data.objects[low['rf_source']]
    audit = rf.geometry.mesh_audit(low)
    report['mesh'] = audit
    check('all_quad_base_mesh', audit['quads'] == audit['faces'] and audit['faces'] > 100)
    check('closed_positive_volume', audit['structurally_valid'])
    check('one_connected_component', audit['components'] == 1)
    check('unwrapped_uvs', bool(audit['uv_layer']) and audit['uv_in_0_1'])
    check('source_retained_hidden', high.hide_render and high.hide_get())
    check('source_follows_low_transform', high.parent is low)
    original = fingerprint(high)
    cfg = rf.configuration(settings)
    twin = rf.geometry.generate_high(cfg, 'Determinism')
    check('seeded_high_geometry_reproducible', original == fingerprint(twin))
    bpy.data.objects.remove(twin, do_unlink=True)
    cfg['seed'] += 1
    varied = rf.geometry.generate_high(cfg, 'Variation')
    check('different_seed_changes_shape', original != fingerprint(varied))
    bpy.data.objects.remove(varied, do_unlink=True)
    rf.geometry.activate(low)
    settings.seed = 99
    bpy.ops.rockforge.load_settings()
    check('load_settings_roundtrip', settings.seed == 23)
    engine = bpy.context.scene.render.engine
    samples = bpy.context.scene.cycles.samples
    images = rf.pipeline.bake(low, high, output / 'maps', 256, 8)
    check('four_real_pbr_maps', set(images) == {'BaseColor', 'Normal', 'Roughness', 'AO'})
    metrics = {}
    for kind, image in images.items():
        pixels = np.asarray(image.pixels[:], dtype=np.float32).reshape(-1, 4)[:, :3]
        metrics[kind] = {'bytes': Path(image.filepath_raw).stat().st_size, 'std': float(pixels.std()), 'min': float(pixels.min()), 'max': float(pixels.max()), 'packed': bool(image.packed_file)}
    report['maps'] = metrics
    check('pbr_files_nonempty', all(value['bytes'] > 1000 and value['packed'] for value in metrics.values()))
    check('albedo_has_variation', metrics['BaseColor']['std'] > 0.015)
    check('normal_has_detail', metrics['Normal']['std'] > 0.10)
    check('render_state_restored', bpy.context.scene.render.engine == engine and bpy.context.scene.cycles.samples == samples)
    check('source_geometry_preserved', fingerprint(high) == original and high.hide_render and high.hide_get())
    glb_path = output / 'test.glb'
    rf.pipeline.export_glb(low, glb_path)
    raw = glb_path.read_bytes()
    chunk_length, chunk_type = struct.unpack_from('<II', raw, 12)
    gltf = json.loads(raw[20:20 + chunk_length])
    report['gltf_counts'] = {key: len(gltf.get(key, [])) for key in ('meshes', 'materials', 'images')}
    check('glb_binary_valid', raw[:4] == b'glTF' and struct.unpack_from('<I', raw, 8)[0] == len(raw))
    check('glb_only_low_mesh', len(gltf['meshes']) == 1)
    check('glb_baked_material', bool(gltf['materials'][0].get('normalTexture')) and len(gltf['images']) >= 3)
    before = set(bpy.data.objects)
    check('native_glb_reimport', 'FINISHED' in bpy.ops.import_scene.gltf(filepath=str(glb_path)))
    imported = set(bpy.data.objects) - before
    check('reimport_contains_mesh', any(obj.type == 'MESH' for obj in imported))
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
    rf.geometry.activate(low)
    lods = rf.pipeline.make_lods(low)
    counts = [rf.geometry.mesh_audit(obj)['triangles'] for obj in lods]
    check('lod_triangle_reduction', audit['triangles'] > counts[0] > counts[1] > 0)
    rf.pipeline.export_glb(lods[0], output / 'test-lod.glb')
    check('hidden_lod_export_and_visibility_restore', (output / 'test-lod.glb').is_file() and lods[0].hide_get())
    proxy = rf.pipeline.collision(low)
    report['collision'] = rf.geometry.mesh_audit(proxy)
    check('convex_collision_closed', report['collision']['structurally_valid'])
    before_hash = fingerprint(high)
    before_materials = list(high.data.materials)
    before_visibility = (high.hide_get(), high.hide_render)
    reference = rf.pipeline.reference_retopology(high, 600, 2)
    check('reference_copy_all_quads', all(len(face.vertices) == 4 for face in reference.data.polygons))
    check('reference_original_unchanged', fingerprint(high) == before_hash and list(high.data.materials) == before_materials and (high.hide_get(), high.hide_render) == before_visibility)
    bpy.data.objects.remove(reference, do_unlink=True)
    rf.geometry.activate(low)
    check('audit_operator', 'FINISHED' in bpy.ops.rockforge.audit())
    before_lows = len([obj for obj in bpy.data.objects if obj.get('rf_role') == 'LOW'])
    settings.batch_count = 2
    settings.density = 64
    settings.quads = 600
    check('batch_variation_operator', 'FINISHED' in bpy.ops.rockforge.batch())
    check('batch_created_two_assets', len([obj for obj in bpy.data.objects if obj.get('rf_role') == 'LOW']) == before_lows + 2)
    rf.geometry.activate(low)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'smoke.blend'), compress=True)
    check('save_blend', (output / 'smoke.blend').is_file())
    addon_utils.disable('rockforge_studio', default_set=False)
    check('native_unregister', not addon_utils.check('rockforge_studio')[1] and not hasattr(bpy.types.Scene, 'rockforge'))
    addon_utils.enable('rockforge_studio', default_set=False)
    check('native_reregister', addon_utils.check('rockforge_studio')[1])
    report['success'] = True
except BaseException:
    report['error'] = traceback.format_exc()
    traceback.print_exc()
finally:
    (output / 'verification.json').write_text(json.dumps(report, indent=2))
print('RF_VERIFICATION', json.dumps(report), flush=True)
if not report['success']:
    raise RuntimeError('Native verification failed; see verification.json')
