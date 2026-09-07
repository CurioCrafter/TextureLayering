"""Build, bake, export and non-destructive reference workflows."""
import contextlib
import json
from pathlib import Path
import re
import bpy
import bmesh
from . import geometry as geo
from . import materials


def safe_name(name):
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', name)


def build(cfg):
    label = geo.PRESETS[cfg['preset']]['label'].replace(' ', '_')
    name = f"RF_{label}_{cfg['seed']:04d}"
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    high = geo.generate_high(cfg, name, collection)
    high.data.materials.clear()
    high.data.materials.append(materials.procedural(cfg, name))
    low = geo.retopologize(high, cfg['quads'], cfg['seed'], name + '_LOW')
    low['rf_config'] = json.dumps(cfg, sort_keys=True)
    low['rf_source'] = high.name
    low['rf_baked'] = False
    high.parent = low
    high.matrix_parent_inverse = low.matrix_world.inverted()
    high.hide_render = True
    high.hide_set(True)
    geo.activate(low)
    return low, high


@contextlib.contextmanager
def emission_override(mat, socket):
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    output = next(n for n in nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output)
    old = [(link.from_socket, link.to_socket) for link in output.inputs['Surface'].links]
    emission = nodes.new('ShaderNodeEmission')
    for link in list(output.inputs['Surface'].links):
        links.remove(link)
    links.new(socket, emission.inputs['Color'])
    links.new(emission.outputs[0], output.inputs['Surface'])
    try:
        yield
    finally:
        nodes.remove(emission)
        for source, target in old:
            links.new(source, target)


def bake(low, high, directory, resolution=2048, samples=24):
    """Selected-to-active Cycles baking with render-state restoration."""
    directory = Path(bpy.path.abspath(str(directory))).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    geo.activate(low)
    if not low.data.uv_layers:
        raise ValueError('Unwrap the low mesh before baking.')
    if high is low:
        raise ValueError('High and low objects must be different.')
    if len(high.data.materials) != 1 or not high.data.materials[0].use_nodes:
        raise ValueError('The procedural baker requires one node-based source material.')
    source_mat = high.data.materials[0]
    if not source_mat.get('rf_procedural'):
        raise ValueError('Use a RockForge source for this baker. Reference texture transfer is not implemented.')
    scene = bpy.context.scene
    settings = scene.render.bake
    snapshot = {key: getattr(settings, key) for key in ('use_selected_to_active', 'use_clear', 'margin', 'cage_extrusion', 'max_ray_distance', 'use_cage')}
    engine = scene.render.engine
    old_samples, device = scene.cycles.samples, scene.cycles.device
    old_hidden, old_render = high.hide_get(), high.hide_render
    old_materials = list(low.data.materials)
    target_mat = bpy.data.materials.new('_RF_BakeTarget')
    target_mat.use_nodes = True
    low.data.materials.clear()
    low.data.materials.append(target_mat)
    target = target_mat.node_tree.nodes.new('ShaderNodeTexImage')
    target_mat.node_tree.nodes.active = target
    if not any(m.type == 'TRIANGULATE' and m.name == 'RF Export Triangulation' for m in low.modifiers):
        triangulation = low.modifiers.new('RF Export Triangulation', 'TRIANGULATE')
        triangulation.quad_method = 'SHORTEST_DIAGONAL'
        triangulation.ngon_method = 'BEAUTY'
    images = {}
    extent = max(high.dimensions)
    try:
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = samples
        settings.use_selected_to_active = True
        settings.use_clear = True
        settings.margin = max(8, resolution // 128)
        settings.use_cage = False
        settings.cage_extrusion = extent * 0.035
        settings.max_ray_distance = extent * 0.16
        high.hide_set(False)
        high.hide_render = False
        for kind, bake_type, initial in (
            ('BaseColor', 'EMIT', (0, 0, 0, 1)),
            ('Normal', 'NORMAL', (0.5, 0.5, 1, 1)),
            ('Roughness', 'EMIT', (0.8, 0.8, 0.8, 1)),
            ('AO', 'AO', (1, 1, 1, 1)),
        ):
            image = bpy.data.images.new(safe_name(low.name) + '_' + kind, width=resolution, height=resolution, alpha=False)
            image.generated_color = initial
            image.colorspace_settings.name = 'sRGB' if kind == 'BaseColor' else 'Non-Color'
            target.image = image
            geo.activate(low)
            high.select_set(True)
            if kind in ('BaseColor', 'Roughness'):
                node_name = 'RF_BASE_COLOR' if kind == 'BaseColor' else 'RF_ROUGHNESS'
                with emission_override(source_mat, source_mat.node_tree.nodes[node_name].outputs[0]):
                    bpy.ops.object.bake(type=bake_type)
            else:
                bpy.ops.object.bake(type=bake_type, normal_space='TANGENT')
            image.filepath_raw = str(directory / (safe_name(low.name) + '_' + kind + '.png'))
            image.file_format = 'PNG'
            image.save()
            image.pack()
            images[kind] = image
        low.data.materials.clear()
        low.data.materials.append(materials.baked(low.name, images))
        low['rf_baked'] = True
        low['rf_texture_resolution'] = resolution
        low['rf_texture_files'] = json.dumps({key: image.filepath_raw for key, image in images.items()})
        return images
    except Exception:
        low.data.materials.clear()
        for material in old_materials:
            low.data.materials.append(material)
        raise
    finally:
        for key, value in snapshot.items():
            setattr(settings, key, value)
        scene.cycles.samples = old_samples
        scene.cycles.device = device
        scene.render.engine = engine
        high.hide_render = old_render
        high.hide_set(old_hidden)
        geo.activate(low)
        if target_mat.users == 0:
            bpy.data.materials.remove(target_mat)


def export_glb(low, path):
    if not low.get('rf_baked'):
        raise ValueError('Bake first. Procedural Blender shaders cannot be exported as glTF PBR.')
    path = Path(bpy.path.abspath(str(path))).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    selected = list(bpy.context.selected_objects)
    active = bpy.context.view_layer.objects.active
    was_hidden = low.hide_get()
    try:
        geo.activate(low)
        result = bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
            export_apply=True, export_texcoords=True, export_normals=True, export_tangents=True,
            export_materials='EXPORT', export_image_format='AUTO', export_extras=False)
        if 'FINISHED' not in result or not path.is_file():
            raise RuntimeError('GLB exporter did not produce a file.')
    finally:
        bpy.ops.object.select_all(action='DESELECT')
        for obj in selected:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        low.hide_set(was_hidden)
    return str(path)


def make_lods(low):
    output = []
    for level, ratio in ((1, 0.5), (2, 0.25)):
        lod = geo.copy_object(low, low.name.replace('_LOW', f'_LOD{level}'), low.users_collection[0])
        for modifier in list(lod.modifiers):
            geo.apply(lod, modifier)
        decimate = lod.modifiers.new('Game LOD simplification', 'DECIMATE')
        decimate.ratio = ratio
        decimate.use_collapse_triangulate = True
        geo.apply(lod, decimate)
        lod['rf_role'] = f'LOD{level}'
        lod['rf_audit'] = json.dumps(geo.mesh_audit(lod))
        lod.hide_render = True
        lod.hide_set(True)
        output.append(lod)
    geo.activate(low)
    return output


def collision(low):
    obj = geo.copy_object(low, 'UCX_' + low.name, low.users_collection[0])
    for modifier in list(obj.modifiers):
        obj.modifiers.remove(modifier)
    obj.data.materials.clear()
    mesh = bmesh.new()
    for vertex in obj.data.vertices:
        mesh.verts.new(vertex.co)
    bmesh.ops.convex_hull(mesh, input=list(mesh.verts), use_existing_faces=False)
    unused = [vertex for vertex in mesh.verts if not vertex.link_faces]
    if unused:
        bmesh.ops.delete(mesh, geom=unused, context='VERTS')
    bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
    mesh.to_mesh(obj.data)
    mesh.free()
    obj.display_type = 'WIRE'
    obj.hide_render = True
    obj.hide_set(True)
    obj['rf_role'] = 'COLLISION'
    geo.activate(low)
    return obj


def reference_retopology(source, quads, seed):
    """Create a shape-only quad copy, preserving the selected original."""
    if source.type != 'MESH':
        raise ValueError('Select a mesh reference.')
    if source.library:
        raise ValueError('Make the reference local before retopology.')
    working = geo.copy_object(source, 'RF_ReferenceWorkingCopy', source.users_collection[0])
    try:
        for modifier in list(working.modifiers):
            geo.apply(working, modifier)
        if not geo.mesh_audit(working)['structurally_valid']:
            raise ValueError('Reference must be a closed manifold mesh. Repair it before retopology.')
        low = geo.retopologize(working, quads, seed, source.name + '_RF_Quads')
        low.data.materials.clear()
        clay = bpy.data.materials.new(low.name + '_Clay')
        clay.diffuse_color = (0.35, 0.38, 0.4, 1)
        low.data.materials.append(clay)
        low['rf_source'] = source.name
        low['rf_reference_shape_only'] = True
        low['rf_baked'] = False
        return low
    finally:
        bpy.data.objects.remove(working, do_unlink=True)
