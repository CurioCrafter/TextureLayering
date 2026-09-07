"""Guarded preset, image-edit, and paint-target operators."""
from pathlib import Path
from uuid import uuid4

import bpy
import numpy as np
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy.types import Operator

from . import images, nodes
from .desk_catalog import BY_ID, BRUSHES, RECIPES, rgb, find_presets
from . import desk_pixels as px
from .operators.common import active_mesh, add_layer, managed_material, require_active_layer
from .properties import active_layer


def read_pixels(image):
    if image is None or image.source == 'TILED':
        raise ValueError('Choose a regular, non-UDIM image')
    width, height = map(int, image.size)
    if width * height > px.MAX_PIXELS or min(width,height) < 1:
        raise ValueError('Image lab supports nonempty images up to 16 megapixels')
    if len(image.pixels) != width * height * 4:
        raise ValueError('This operation requires an RGBA image buffer')
    pixels = np.empty(width*height*4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    return pixels.reshape(height,width,4)


def write_copy(layer, slot, pixels, label):
    source = getattr(layer,slot)
    data = px.checked(pixels)
    if data.ndim == 2:
        data = np.stack((data,data,data,np.ones_like(data)), -1)
    h,w,_ = data.shape
    output = bpy.data.images.new(f'SLS_{layer.name}_{label}', width=w, height=h, alpha=True,
                                 float_buffer=bool(source and source.is_float),
                                 is_data=slot not in {'base_color_image','emission_image'})
    try:
        if source:
            output.colorspace_settings.name = source.colorspace_settings.name
        if slot not in {'base_color_image','emission_image'}:
            images.set_color_space(output,is_data=True)
        output.pixels.foreach_set(np.ascontiguousarray(data,dtype=np.float32).ravel())
        output.update()
        output.pack()
    except Exception:
        bpy.data.images.remove(output)
        raise
    output['sls_desk_image'] = True
    layer.desk.previous_image, layer.desk.previous_slot = source, slot
    layer.desk.previous_normal_format=layer.normal_format
    setattr(layer,slot,output)
    return output


def show_image(context, image):
    if image is None:
        return
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                area.spaces.active.image = image
                area.spaces.active.mode = 'PAINT'
    paint = context.scene.tool_settings.image_paint
    paint.mode, paint.canvas = 'IMAGE', image


def apply_preset(context, preset_id):
    if preset_id not in BY_ID:
        raise ValueError('Unknown preset')
    if int(context.scene.sls_tools.mask_resolution) > 4096:
        raise ValueError('Use 4K or smaller masks for presets and recipes')
    obj = active_mesh(context)
    if obj is None:
        raise ValueError('Select a mesh first')
    if obj.library is not None or obj.data.library is not None or (obj.active_material and obj.active_material.library is not None):
        raise ValueError('Make linked objects and materials local before adding presets')
    if managed_material(context) is None:
        result = bpy.ops.sls.setup_material()
        if 'FINISHED' not in result:
            raise ValueError('Could not create a layer stack')
    material = managed_material(context)
    p = BY_ID[preset_id]
    layer = add_layer(context,material,p.name,fill='WHITE')
    layer.tint = rgb(p.color,linear=True)
    layer.roughness, layer.metallic = p.roughness,p.metallic
    w = layer.desk
    w.preset_id, w.pattern, w.coverage, w.scale = p.id,p.pattern,p.coverage,p.scale
    w.placement, w.secondary, w.variation, w.relief = p.placement,rgb(p.secondary,linear=True),.72,p.relief
    w.roughness_variation = .18 if not p.emission else 0
    w.seed = context.scene.sls_desk.lab_seed
    layer.emission_strength, layer.emission_tint = p.emission, rgb(p.secondary,linear=True)
    return layer


class DeskOperator:
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls, context):
        material, layer = require_active_layer(context)
        return layer is not None and not layer.locked and material.library is None

    def fail(self, context, exc):
        context.scene.sls_desk.status = str(exc)
        self.report({'ERROR'},str(exc))
        return {'CANCELLED'}


class ReadOnlyDeskOperator(DeskOperator):
    @classmethod
    def poll(cls,context):
        material,layer=require_active_layer(context)
        return material is not None and layer is not None


class SLS_OT_desk_preset(Operator):
    bl_idname = 'sls.desk_preset'
    bl_label = 'Add material preset'
    bl_description = 'Append an editable PBR layer with a procedural mask and independent paint image'
    bl_options = {'REGISTER','UNDO'}
    preset_id: StringProperty()

    @classmethod
    def poll(cls,context):
        return active_mesh(context) is not None

    def execute(self,context):
        try:
            layer = apply_preset(context,self.preset_id)
            nodes.rebuild_material(managed_material(context))
            context.scene.sls_desk.status = f'Added {layer.name}. White mask reveals the live pattern.'
            show_image(context,layer.mask_image)
            return {'FINISHED'}
        except (ValueError,RuntimeError) as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}


class SLS_OT_desk_recipe(Operator):
    bl_idname = 'sls.desk_recipe'
    bl_label = 'Append scene recipe'
    bl_description = 'Append the named layers; existing layers and material settings are not cleared'
    bl_options = {'REGISTER','UNDO'}

    @classmethod
    def poll(cls,context):
        return active_mesh(context) is not None

    def execute(self,context):
        name,presets = RECIPES[context.scene.sls_desk.recipe]
        try:
            for preset_id in presets:
                apply_preset(context,preset_id)
            nodes.rebuild_material(managed_material(context))
            context.scene.sls_desk.status = f'Added {name}: {len(presets)} editable layers.'
            show_image(context,active_layer(managed_material(context)).mask_image)
            return {'FINISHED'}
        except (ValueError,RuntimeError) as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}


class SLS_OT_desk_favorite(Operator):
    bl_idname = 'sls.desk_favorite'
    bl_label = 'Toggle favorite'
    bl_options = {'INTERNAL','UNDO'}
    preset_id: StringProperty()

    def execute(self,context):
        settings = context.scene.sls_desk
        favorites = set(filter(None,settings.favorites.split(',')))
        favorites.symmetric_difference_update({self.preset_id})
        settings.favorites = ','.join(sorted(favorites & BY_ID.keys()))
        return {'FINISHED'}


class SLS_OT_desk_page(Operator):
    bl_idname='sls.desk_page'
    bl_label='Browse preset shelf'
    bl_options={'INTERNAL'}
    direction: IntProperty(default=1,min=-1,max=1)

    def execute(self,context):
        t=context.scene.sls_desk
        favorites=set(t.favorites.split(',')) if t.favorites_only else None
        count=len(find_presets(t.query,t.category,favorites))
        t.page=max(0,min(max(0,(count-1)//8),t.page+self.direction))
        return {'FINISHED'}


class SLS_OT_desk_brush(DeskOperator,Operator):
    bl_idname = 'sls.desk_brush'
    bl_label = 'Use mask brush preset'
    preset: EnumProperty(items=[(k,v[0],'') for k,v in BRUSHES.items()])

    def execute(self,context):
        name,mode,strength,size,falloff,spacing = BRUSHES[self.preset]
        tools = context.scene.sls_tools
        tools.brush_mode,tools.brush_strength,tools.brush_size = mode,strength,size
        tools.brush_falloff,tools.brush_spacing = falloff,spacing
        context.scene.sls_desk.status = f'{name} selected. Start Mask Painting to paint in 3D.'
        return {'FINISHED'}


class SLS_OT_desk_target(ReadOnlyDeskOperator,Operator):
    bl_idname = 'sls.desk_target'
    bl_label = 'View / paint target'

    def execute(self,context):
        _,layer = require_active_layer(context)
        image = getattr(layer,context.scene.sls_desk.target)
        if image is None:
            return self.fail(context,ValueError('This channel has no image; create one or import a PBR set'))
        show_image(context,image)
        return {'FINISHED'}


class SLS_OT_desk_new_image(DeskOperator,Operator):
    bl_idname = 'sls.desk_new_image'
    bl_label = 'New channel image'
    bl_description = 'Create a new editable image, keeping the previous channel image as a restore point'

    def execute(self,context):
        _,layer = require_active_layer(context)
        tools = context.scene.sls_desk
        size = int(context.scene.sls_tools.mask_resolution)
        if size > 4096:
            return self.fail(context,ValueError('Image lab creates up to 4K images'))
        color = {'mask_image':(1,1,1,1),'base_color_image':(1,1,1,1),
                 'normal_image':(.5,.5,1,1),'height_image':(.5,.5,.5,1),
                 'roughness_image':(layer.roughness,)*3+(1,), 'metallic_image':(layer.metallic,)*3+(1,),
                 'ao_image':(1,1,1,1),'emission_image':(1,1,1,1)}[tools.target]
        try:
            pixels = np.empty((size,size,4),dtype=np.float32)
            pixels[:] = color
            image = write_copy(layer,tools.target,pixels,'Blank')
            if tools.target == 'normal_image':
                layer.normal_format = 'OPENGL'
            show_image(context,image)
            return {'FINISHED'}
        except (ValueError,RuntimeError) as exc:
            return self.fail(context,exc)


class SLS_OT_desk_edit(DeskOperator,Operator):
    bl_idname = 'sls.desk_edit'
    bl_label = 'Edit image copy'
    bl_description = 'Process a new image copy; the source pixels are never overwritten'
    operation: EnumProperty(items=[(x,x.replace('_',' ').title(),'') for x in px.OPERATIONS])

    def execute(self,context):
        _,layer = require_active_layer(context)
        t = context.scene.sls_desk
        try:
            data = read_pixels(getattr(layer,t.target))
            output = px.edit(data,self.operation,black=t.black,white=t.white,gamma=t.gamma,radius=t.radius,wrap=t.wrap)
            image = write_copy(layer,t.target,output,self.operation.title())
            show_image(context,image)
            t.status = f'{self.operation.title()}: edited copy created; Restore Last Edit retains the original.'
            return {'FINISHED'}
        except (ValueError,RuntimeError) as exc:
            return self.fail(context,exc)


class SLS_OT_desk_generate(DeskOperator,Operator):
    bl_idname = 'sls.desk_generate'
    bl_label = 'Generate 2D mask copy'
    bl_description = 'Replace the paint image with a generated UV mask; live geometry/procedural masks still multiply it'

    def execute(self,context):
        _,layer = require_active_layer(context)
        t = context.scene.sls_desk
        try:
            image = layer.mask_image
            width,height = map(int,image.size) if image else (int(context.scene.sls_tools.mask_resolution),)*2
            data = px.pattern(width,height,t.lab_pattern,t.lab_seed,t.lab_scale,t.lab_coverage,t.lab_softness)
            image = write_copy(layer,'mask_image',data,'GeneratedMask')
            t.target = 'mask_image'
            show_image(context,image)
            t.status = '2D paint mask created. Live weathering still multiplies this mask.'
            return {'FINISHED'}
        except (ValueError,RuntimeError) as exc:
            return self.fail(context,exc)


class SLS_OT_desk_restore(DeskOperator,Operator):
    bl_idname = 'sls.desk_restore'
    bl_label = 'Restore last image edit'
    bl_description = 'Swap the last image edit with its preserved source; also usable as an A/B comparison'

    def execute(self,context):
        _,layer = require_active_layer(context)
        w = layer.desk
        if not w.previous_image or not w.previous_slot:
            return self.fail(context,ValueError('No earlier image is stored for this layer'))
        current = getattr(layer,w.previous_slot)
        if w.previous_slot=='normal_image':
            previous_format=w.previous_normal_format
            w.previous_normal_format=layer.normal_format
            layer.normal_format=previous_format if previous_format in {'OPENGL','DIRECTX'} else 'OPENGL'
        setattr(layer,w.previous_slot,w.previous_image)
        show_image(context,w.previous_image)
        w.previous_image = current
        return {'FINISHED'}


class SLS_OT_desk_normal(DeskOperator,Operator):
    bl_idname = 'sls.desk_normal'
    bl_label = 'Height / mask to normal'
    bl_description = 'Convert the height image (or paint mask when no height exists) to a tangent-space normal texture'

    def execute(self,context):
        _,layer = require_active_layer(context)
        t = context.scene.sls_desk
        try:
            data = read_pixels(layer.height_image or layer.mask_image)[...,:3].mean(axis=-1)
            normal = px.height_to_normal(data,t.normal_strength,t.normal_directx,t.wrap)
            image = write_copy(layer,'normal_image',normal,'NormalDX' if t.normal_directx else 'NormalGL')
            layer.normal_format = 'DIRECTX' if t.normal_directx else 'OPENGL'
            t.target = 'normal_image'
            show_image(context,image)
            return {'FINISHED'}
        except (ValueError,RuntimeError) as exc:
            return self.fail(context,exc)


class SLS_OT_desk_export_image(ReadOnlyDeskOperator,Operator):
    bl_idname = 'sls.desk_export_image'
    bl_label = 'Export target PNG copy'

    def execute(self,context):
        _,layer = require_active_layer(context)
        t = context.scene.sls_desk
        image = getattr(layer,t.target)
        if image is None:
            return self.fail(context,ValueError('The target has no image'))
        copied = None
        try:
            directory = Path(bpy.path.abspath(t.export_directory))
            directory.mkdir(parents=True,exist_ok=True)
            data = read_pixels(image)
            copied = bpy.data.images.new('__SLS_EXPORT_COPY',width=image.size[0],height=image.size[1],alpha=True,float_buffer=image.is_float)
            copied.colorspace_settings.name = image.colorspace_settings.name
            copied.pixels.foreach_set(np.ascontiguousarray(data).ravel())
            copied.update()
            from .core import safe_filename
            target = directory / f'{safe_filename(layer.name)}_{t.target}_{uuid4().hex[:8]}.png'
            copied.file_format,copied.filepath_raw = 'PNG',str(target)
            copied.save()
            t.last_export,t.status = str(target),'Exported a PNG copy; original image paths were not changed.'
            return {'FINISHED'}
        except (ValueError,RuntimeError,OSError) as exc:
            return self.fail(context,exc)
        finally:
            if copied:
                bpy.data.images.remove(copied)


_CLASSES = (SLS_OT_desk_page,SLS_OT_desk_preset,SLS_OT_desk_recipe,SLS_OT_desk_favorite,SLS_OT_desk_brush,
            SLS_OT_desk_target,SLS_OT_desk_new_image,SLS_OT_desk_edit,SLS_OT_desk_generate,
            SLS_OT_desk_restore,SLS_OT_desk_normal,SLS_OT_desk_export_image)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
