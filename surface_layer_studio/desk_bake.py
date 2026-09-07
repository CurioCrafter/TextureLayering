"""Flatten one material to game textures using disposable evaluated geometry.

The source object's materials, images, UVs, and modifiers are never rewritten.
Only faces using its active material are baked. Output always uses a unique folder.
"""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import json

import bpy
import numpy as np
from bpy.types import Operator

from . import nodes
from .core import safe_filename
from .desk_ops import read_pixels
from .desk_pixels import pack_orm
from .operators.common import managed_material, active_mesh


def bake_material(context, directory, resolution, include_ao=False, include_normal=True):
    obj, material = active_mesh(context), managed_material(context)
    if obj is None or material is None:
        raise ValueError('Select a mesh with a managed material')
    if obj.mode != 'OBJECT':
        raise ValueError('Finish painting or leave Edit Mode before baking')
    if not obj.data.uv_layers or obj.data.uv_layers.active is None:
        raise ValueError('Unwrap the mesh before baking')
    if not any(p.material_index == obj.active_material_index for p in obj.data.polygons):
        raise ValueError('No mesh faces use the active material')
    resolution = int(resolution)
    if resolution < 16 or resolution > 4096:
        raise ValueError('Bake size must be 16–4096 pixels')
    # Refuse ambiguous off-tile outputs, rather than silently dropping UDIM data.
    uv = obj.data.uv_layers.active
    for poly in obj.data.polygons:
        if poly.material_index == obj.active_material_index:
            if any(not (-1e-5 <= uv.data[i].uv.x <= 1.00001 and -1e-5 <= uv.data[i].uv.y <= 1.00001) for i in poly.loop_indices):
                raise ValueError('The active material must use the 0–1 UV tile; UDIM baking is not supported')
    nodes.flush_pending_rebuilds()
    nodes.rebuild_material(material)
    scene = context.scene
    original_selection, original_active = tuple(context.selected_objects), context.view_layer.objects.active
    saved = {'engine':scene.render.engine,'samples':scene.cycles.samples,'device':scene.cycles.device,
             'hide_render':obj.hide_render,'selected_to_active':scene.render.bake.use_selected_to_active,
             'margin':scene.render.bake.margin,'clear':scene.render.bake.use_clear,
             'target':scene.render.bake.target,'normal_space':scene.render.bake.normal_space,
             'normal_r':scene.render.bake.normal_r,'normal_g':scene.render.bake.normal_g,'normal_b':scene.render.bake.normal_b}
    temporary_object = temporary_mesh = temporary_material = helper_material = None
    temporary_images = []
    output = Path(directory) / f'{safe_filename(material.name)}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid4().hex[:8]}'
    output.mkdir(parents=True,exist_ok=False)
    manifest = {'material':material.name,'object':obj.name,'resolution':resolution,'uv_map':uv.name,
                'normal_convention':'OpenGL (+Y)','orm':{'R':'AO' if include_ao else 'constant 1','G':'roughness','B':'metallic'},
                'source_preserved':True,'color_images':'sRGB PNG8','data_images':'Non-Color PNG8',
                'occlusion_note':'Other material regions on the same mesh are opaque occluders',
                'files':{},'status':'incomplete'}
    results = {}
    try:
        depsgraph = context.evaluated_depsgraph_get()
        evaluated = obj.evaluated_get(depsgraph)
        temporary_mesh = bpy.data.meshes.new_from_object(evaluated,preserve_all_data_layers=True,depsgraph=depsgraph)
        # Keep the complete evaluated mesh: removing non-target faces changes
        # split normals, modifier results, and AO occlusion at material seams.
        active_faces = [p for p in temporary_mesh.polygons if p.material_index == obj.active_material_index]
        if not active_faces:
            raise ValueError('The evaluated mesh has no faces for this material')
        evaluated_uv = temporary_mesh.uv_layers.get(uv.name)
        if evaluated_uv is None:
            raise ValueError('Modifiers removed the target UV map')
        temporary_mesh.uv_layers.active = evaluated_uv
        for polygon in active_faces:
            if any(not (-1e-5 <= evaluated_uv.data[i].uv.x <= 1.00001 and -1e-5 <= evaluated_uv.data[i].uv.y <= 1.00001) for i in polygon.loop_indices):
                raise ValueError('Evaluated target UVs extend beyond the 0–1 tile')
        # Other material regions bake to a throw-away image, not the export.
        indices = [0 if p.material_index == obj.active_material_index else 1 for p in temporary_mesh.polygons]
        temporary_material = material.copy()
        temporary_material.name = '__SLS_BAKE_MATERIAL'
        temporary_material.sls.enabled = False
        helper_material = bpy.data.materials.new('__SLS_BAKE_OCCLUDER')
        helper_material.use_nodes = True
        scratch = bpy.data.images.new('__SLS_BAKE_SCRATCH',16,16,is_data=True)
        temporary_images.append(scratch)
        helper_target = helper_material.node_tree.nodes.new('ShaderNodeTexImage')
        helper_target.image = scratch
        helper_material.node_tree.nodes.active = helper_target
        temporary_mesh.materials.clear()
        temporary_mesh.materials.append(temporary_material)
        temporary_mesh.materials.append(helper_material)
        for polygon,index in zip(temporary_mesh.polygons,indices):
            polygon.material_index = index
        temporary_object = bpy.data.objects.new('__SLS_BAKE_OBJECT',temporary_mesh)
        temporary_object.matrix_world = obj.matrix_world.copy()
        context.collection.objects.link(temporary_object)
        for selected in original_selection:
            selected.select_set(False)
        temporary_object.select_set(True)
        context.view_layer.objects.active = temporary_object
        obj.hide_render = True
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'CPU'
        scene.cycles.samples = 16
        scene.render.bake.use_selected_to_active = False
        scene.render.bake.use_clear = True
        scene.render.bake.target = 'IMAGE_TEXTURES'
        scene.render.bake.margin = max(2,resolution//128)
        scene.render.bake.normal_space = 'TANGENT'
        scene.render.bake.normal_r,scene.render.bake.normal_g,scene.render.bake.normal_b = 'POS_X','POS_Y','POS_Z'
        tree = temporary_material.node_tree
        output_node = tree.nodes.get(material.get('sls_output_node',''))
        if output_node is None:
            output_node = next(n for n in tree.nodes if n.bl_idname == 'ShaderNodeOutputMaterial' and n.is_active_output)
        shader = tree.nodes['SLS_Principled']
        emission = tree.nodes.new('ShaderNodeEmission')
        emission.inputs['Strength'].default_value = 1
        target = tree.nodes.new('ShaderNodeTexImage')
        channels = [('BaseColor','color'),('Roughness','roughness'),('Metallic','metallic'),('Height','height'),('Emission','emission')]
        if include_normal:
            channels.append(('Normal','NORMAL'))
        if include_ao:
            channels.append(('AO','AO'))
        # Normal baking must use the composite shader, not a user-selected preview.
        if include_normal and material.sls.preview_mode != 'COMPOSITE':
            raise ValueError('Switch Channel Preview to Composite before baking tangent normals')
        for filename,channel in channels:
            image = bpy.data.images.new(f'__SLS_BAKE_{filename}',resolution,resolution,alpha=True,is_data=filename not in {'BaseColor','Emission'})
            temporary_images.append(image)
            target.image = image
            for node in tree.nodes:
                node.select = False
            target.select = True
            tree.nodes.active = target
            if channel in {'NORMAL','AO'}:
                tree.links.new(shader.outputs['BSDF'],output_node.inputs['Surface'])
                bake_type = channel
            else:
                source = tree.nodes.get(f'SLS_Channel_{channel}')
                if source is None:
                    raise RuntimeError(f'Export channel {channel} is unavailable; repair the stack')
                tree.links.new(source.outputs[0],emission.inputs['Color'])
                tree.links.new(emission.outputs[0],output_node.inputs['Surface'])
                bake_type = 'EMIT'
            context.view_layer.update()
            result = bpy.ops.object.bake(type=bake_type)
            if 'FINISHED' not in result:
                raise RuntimeError(f'{filename} bake did not finish')
            image.file_format,image.filepath_raw = 'PNG',str(output/f'{filename}.png')
            image.save()
            manifest['files'][filename] = f'{filename}.png'
            if filename in {'Roughness','Metallic','AO'}:
                results[filename] = read_pixels(image)[...,0].copy()
        ao = results.get('AO',np.ones((resolution,resolution),dtype=np.float32))
        orm_data = pack_orm(ao,results['Roughness'],results['Metallic'])
        orm = bpy.data.images.new('__SLS_BAKE_ORM',resolution,resolution,alpha=True,is_data=True)
        temporary_images.append(orm)
        orm.alpha_mode = 'CHANNEL_PACKED'
        orm.pixels.foreach_set(orm_data.astype(np.float32).ravel())
        orm.update()
        orm.file_format,orm.filepath_raw = 'PNG',str(output/'ORM.png')
        orm.save()
        manifest['files']['ORM'] = 'ORM.png'
        manifest['status'] = 'complete'
        return output
    except Exception as exc:
        manifest['error'] = str(exc)
        raise
    finally:
        # A manifest also identifies partial output after a failed bake.
        try:
            (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        finally:
            if temporary_object:
                bpy.data.objects.remove(temporary_object,do_unlink=True)
            if temporary_mesh:
                bpy.data.meshes.remove(temporary_mesh)
            if temporary_material:
                bpy.data.materials.remove(temporary_material)
            if helper_material:
                bpy.data.materials.remove(helper_material)
            for image in temporary_images:
                bpy.data.images.remove(image)
            obj.hide_render = saved['hide_render']
            scene.render.engine,scene.cycles.samples,scene.cycles.device = saved['engine'],saved['samples'],saved['device']
            scene.render.bake.use_selected_to_active = saved['selected_to_active']
            scene.render.bake.margin,scene.render.bake.use_clear = saved['margin'],saved['clear']
            scene.render.bake.target,scene.render.bake.normal_space = saved['target'],saved['normal_space']
            scene.render.bake.normal_r,scene.render.bake.normal_g,scene.render.bake.normal_b = saved['normal_r'],saved['normal_g'],saved['normal_b']
            for selected in context.selected_objects:
                selected.select_set(False)
            for selected in original_selection:
                selected.select_set(True)
            context.view_layer.objects.active = original_active


class SLS_OT_desk_bake(Operator):
    bl_idname = 'sls.desk_bake'
    bl_label = 'Bake PBR texture set + ORM'
    bl_description = 'Bake the active material into a new folder; the source material is not replaced'

    @classmethod
    def poll(cls,context):
        obj = active_mesh(context)
        return obj is not None and obj.mode == 'OBJECT' and managed_material(context) is not None

    def execute(self,context):
        settings = context.scene.sls_desk
        try:
            directory = bake_material(context,bpy.path.abspath(settings.export_directory),int(settings.export_resolution),settings.bake_ao,settings.bake_normal)
            settings.last_export = str(directory)
            settings.status = 'Baked texture set and manifest. Source material preserved.'
            self.report({'INFO'},f'Exported to {directory}')
            return {'FINISHED'}
        except (ValueError,RuntimeError,OSError) as exc:
            settings.status = f'Export failed: {exc}'
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}


def register():
    bpy.utils.register_class(SLS_OT_desk_bake)


def unregister():
    bpy.utils.unregister_class(SLS_OT_desk_bake)
