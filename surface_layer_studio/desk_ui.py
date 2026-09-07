"""Searchable material shelf and task-oriented native Blender editing panels."""
from pathlib import Path
import tempfile
import textwrap

import bpy
import bpy.utils.previews
import numpy as np
from bpy.types import Panel

from .desk_catalog import PRESETS, BRUSHES, find_presets, rgb
from . import desk_pixels as px
from .operators.common import managed_material, require_active_layer, active_mesh, shared_material_objects
from .images import estimated_memory_mb

_PREVIEWS = None
_TEMP = None


def _preview_icons():
    global _PREVIEWS,_TEMP
    _PREVIEWS = bpy.utils.previews.new()
    _TEMP = tempfile.TemporaryDirectory(prefix='sls_swatches_')
    for i,p in enumerate(PRESETS):
        mask = px.pattern(72,72,p.pattern,i+7,p.scale,p.coverage,.25)
        detail = px.pattern(72,72,'NOISE',i+23,6,.6,.8)
        first,second = np.array(rgb(p.color)[:3]),np.array(rgb(p.secondary)[:3])
        color = first[None,None,:]*(1-detail[...,None]*.8)+second[None,None,:]*detail[...,None]*.8
        color = color*mask[...,None]+np.array((.12,.16,.17))*(1-mask[...,None])
        rgba = np.concatenate((color,np.ones((72,72,1))),axis=-1)
        file = Path(_TEMP.name)/f'{p.id}.png'
        px.write_png(file,rgba)
        _PREVIEWS.load(p.id,str(file),'IMAGE')


def icon(preset_id):
    return _PREVIEWS[preset_id].icon_id if _PREVIEWS and preset_id in _PREVIEWS else 0


def _library(layout,context):
    t = context.scene.sls_desk
    layout.prop(t,'query',text='',icon='VIEWZOOM')
    row = layout.row(align=True)
    row.prop(t,'category',text='')
    row.prop(t,'favorites_only',text='',icon='SOLO_ON')
    favorites = set(t.favorites.split(','))
    matches = find_presets(t.query,t.category,favorites if t.favorites_only else None)
    page_count = max(1,(len(matches)+7)//8)
    page = min(t.page,page_count-1)
    layout.label(text=f'{len(matches)} presets · page {page+1} / {page_count}')
    if not matches:
        layout.label(text='No presets match this search.',icon='INFO')
    row = layout.row(align=True)
    previous=row.row(align=True);previous.enabled=page>0
    previous.operator('sls.desk_page',text='Previous',icon='TRIA_LEFT').direction=-1
    following=row.row(align=True);following.enabled=page+1<page_count
    following.operator('sls.desk_page',text='Next',icon='TRIA_RIGHT').direction=1
    grid = layout.grid_flow(row_major=True,columns=2,even_columns=True,even_rows=True,align=True)
    for preset in matches[page*8:page*8+8]:
        card = grid.box()
        card.template_icon(icon_value=icon(preset.id),scale=4.5)
        for line in textwrap.wrap(preset.name,width=16):
            card.label(text=line)
        card.operator('sls.desk_preset',text='Add layer',icon='ADD').preset_id=preset.id
        row = card.row(align=True)
        row.label(text=preset.pattern.title())
        favorite = row.operator('sls.desk_favorite',text='',icon='SOLO_ON' if preset.id in favorites else 'SOLO_OFF')
        favorite.preset_id = preset.id
    layout.label(text='Swatches are 2D guides; inspect the 3D result.',icon='INFO')
    recipe = layout.box()
    recipe.label(text='Complete surface recipes',icon='MATERIAL')
    recipe.prop(t,'recipe',text='')
    recipe.prop(context.scene.sls_tools,'mask_resolution',text='Mask size')
    recipe.operator('sls.desk_recipe',icon='ADD')
    recipe.label(text='Appends layers. Does not clear your stack.')


def _layers(layout,context,material,layer):
    row = layout.row()
    row.template_list('SLS_UL_layers','desk',material.sls,'layers',material.sls,'active_index',rows=6)
    tools = row.column(align=True)
    tools.operator('sls.add_layer',text='',icon='ADD')
    tools.operator('sls.remove_layer',text='',icon='REMOVE')
    tools.operator('sls.duplicate_layer',text='',icon='DUPLICATE')
    tools.operator('sls.move_layer',text='',icon='TRIA_UP').direction = 'UP'
    tools.operator('sls.move_layer',text='',icon='TRIA_DOWN').direction = 'DOWN'
    layout.prop(layer,'name',text='')
    row = layout.row(align=True)
    row.prop(layer,'enabled',toggle=True)
    row.prop(layer,'solo',toggle=True)
    row.prop(layer,'locked',toggle=True)
    layout.prop(layer,'opacity',slider=True)
    layout.prop(layer,'blend_mode')
    row = layout.row(align=True)
    row.prop(layer,'tint',text='Color')
    row.prop(layer.desk,'secondary',text='Variation')
    layout.prop(layer.desk,'variation',slider=True)
    row = layout.row(align=True)
    row.prop(layer,'roughness')
    row.prop(layer,'metallic')
    w = layer.desk
    box = layout.box()
    box.label(text='Live weathering × painted mask',icon='MODIFIER')
    box.prop(w,'pattern')
    if w.pattern != 'NONE' or w.variation or w.relief:
        box.prop(w,'coordinates')
        row = box.row(align=True)
        row.prop(w,'scale')
        row.prop(w,'seed')
        box.prop(w,'coverage',slider=True)
        box.prop(w,'softness',slider=True)
        box.prop(w,'detail')
        box.prop(w,'stretch')
    box.prop(w,'placement')
    if w.placement == 'WATERLINE':
        box.prop(w,'waterline')
        box.prop(w,'band_width')
    row = box.row(align=True)
    row.prop(w,'black')
    row.prop(w,'white')
    if w.white <= w.black:
        box.label(text='White point must exceed black point.',icon='ERROR')
    box.prop(w,'gamma')
    box.prop(w,'relief',slider=True)
    box.prop(w,'roughness_variation',slider=True)
    box.prop(material.sls,'bump_distance')
    layout.prop(w,'source_projection')
    layout.prop_search(layer,'uv_map',context.active_object.data,'uv_layers')
    layout.prop(layer,'mapping_scale')
    layout.prop(layer,'mapping_offset')
    layout.prop(layer,'mapping_rotation')
    layout.prop(layer,'normal_format')
    row = layout.row(align=True)
    row.prop(layer,'emission_tint')
    row.prop(layer,'emission_strength')
    layout.operator('sls.import_pbr_set',icon='FILE_FOLDER')
    layout.prop(material.sls,'preview_mode')


def _target(layout,context,layer):
    t = context.scene.sls_desk
    layout.prop(t,'target',text='Target')
    layout.template_ID(layer,t.target,new='sls.desk_new_image')
    row = layout.row(align=True)
    row.operator('sls.desk_target',text='View / paint',icon='IMAGE_DATA')
    row.operator('sls.desk_new_image',text='New',icon='ADD')
    image = getattr(layer,t.target)
    if image:
        layout.label(text=f'{image.size[0]} × {image.size[1]}  ·  {image.colorspace_settings.name}')
    return image


def _paint(layout,context,material,layer):
    t = context.scene.sls_tools
    _target(layout,context,layer)
    layout.label(text='Mask brushes',icon='BRUSH_DATA')
    grid = layout.grid_flow(row_major=True,columns=2,even_columns=True,even_rows=True,align=True)
    for key,value in BRUSHES.items():
        grid.operator('sls.desk_brush',text=value[0]).preset = key
    layout.prop(t,'brush_mode',expand=True)
    layout.prop(t,'brush_strength',slider=True)
    layout.prop(t,'brush_size')
    layout.prop(t,'brush_falloff')
    row = layout.row(align=True)
    row.prop(t,'use_pressure_strength',text='Pressure opacity')
    row.prop(t,'use_pressure_size',text='Pressure size')
    layout.prop(t,'brush_spacing')
    layout.operator('sls.start_paint',text='Start mask painting in 3D',icon='BRUSH_DATA')
    layout.operator('sls.finish_paint',text='Finish painting',icon='CHECKMARK')
    row = layout.row(align=True)
    row.operator('sls.fill_mask',text='Hide all').fill = 'BLACK'
    row.operator('sls.fill_mask',text='Reveal all').fill = 'WHITE'
    layout.prop(layer,'invert_mask')
    layout.prop(material.sls,'preview_mode')
    layout.label(text='Native Image Editor tools remain available.')


def _lab(layout,context,layer):
    t = context.scene.sls_desk
    _target(layout,context,layer)
    layout.label(text='Edits create a copy, preserving source pixels.',icon='DUPLICATE')
    row = layout.row(align=True)
    row.prop(t,'black',text='Black')
    row.prop(t,'white')
    layout.prop(t,'gamma')
    row = layout.row(align=True)
    row.prop(t,'radius',text='Radius')
    row.prop(t,'wrap')
    grid = layout.grid_flow(row_major=True,columns=3,even_columns=True,align=True)
    for operation in px.OPERATIONS:
        grid.operator('sls.desk_edit',text=operation.replace('_',' ').title()).operation = operation
    layout.operator('sls.desk_restore',icon='LOOP_BACK')
    box = layout.box()
    box.label(text='Seeded 2D mask generator',icon='TEXTURE')
    box.prop(t,'lab_pattern')
    row = box.row(align=True)
    row.prop(t,'lab_seed')
    row.prop(t,'lab_scale')
    box.prop(t,'lab_coverage',slider=True)
    box.prop(t,'lab_softness',slider=True)
    box.operator('sls.desk_generate',icon='IMAGE_DATA')
    box.label(text='Multiplies any live weathering mask.')
    box = layout.box()
    box.label(text='Normal map tools',icon='NORMALS_FACE')
    box.prop(t,'normal_strength')
    box.prop(t,'normal_directx')
    box.operator('sls.desk_normal')
    layout.operator('sls.desk_export_image',icon='EXPORT')


def _export(layout,context,material):
    t = context.scene.sls_desk
    layout.label(text='Active material → game textures',icon='EXPORT')
    layout.prop(t,'export_directory')
    layout.prop(t,'export_resolution')
    layout.prop(t,'bake_normal')
    layout.prop(t,'bake_ao')
    layout.operator('sls.desk_bake',icon='RENDER_STILL')
    layout.label(text='Base color · Roughness · Metallic · Height')
    layout.label(text='Emission · optional Normal / AO · ORM')
    layout.label(text='ORM = AO (R), roughness (G), metallic (B).')
    layout.label(text='Unique output folder; source stack retained.')
    layout.label(text='0–1 UVs required. UV overlaps share pixels.',icon='INFO')
    layout.label(text='Finish painting before baking. Cycles CPU.')
    if material.sls.preview_mode != 'COMPOSITE':
        layout.prop(material.sls,'preview_mode')
    row = layout.row(align=True)
    row.operator('sls.uv_audit',text='Audit UVs',icon='UV')
    row.operator('sls.pack_masks',text='Pack masks',icon='PACKAGE')
    layout.operator('sls.pack_sources',text='Pack source textures',icon='PACKAGE')
    if t.last_export:
        layout.prop(t,'last_export',text='Last output')


def draw_desk(layout,context,canvas=False):
    t = context.scene.sls_desk
    if context.workspace.name!='Shipwreck Desk':
        layout.operator('sls.desk_workspace',icon='WINDOW')
    layout.row(align=True).prop(t,'canvas_tab' if canvas else 'tab',expand=True)
    tab = t.canvas_tab if canvas else t.tab
    material,layer = require_active_layer(context)
    if active_mesh(context) is None:
        layout.label(text='Select a mesh to begin.',icon='MESH_DATA')
        return
    users=shared_material_objects(material)
    if users>1:
        box = layout.box()
        box.alert = True
        box.label(text=f'Shared by {users} objects',icon='LINKED')
        box.operator('sls.make_single_user',icon='DUPLICATE')
    if tab == 'LIBRARY':
        _library(layout,context)
    elif not material or not layer:
        layout.operator('sls.setup_material',icon='ADD')
        layout.label(text='Or add a material from Library.')
    else:
        if layer.locked:
            row = layout.row()
            row.alert = True
            row.label(text='Layer is locked against image edits.',icon='LOCKED')
        if tab == 'LAYERS':
            _layers(layout,context,material,layer)
        elif tab == 'PAINT':
            _paint(layout,context,material,layer)
        elif tab == 'LAB':
            _lab(layout,context,layer)
        else:
            _export(layout,context,material)
    if material:
        unique = {l.mask_image for l in material.sls.layers if l.mask_image}
        size = sum(estimated_memory_mb(image) for image in unique)
        layout.separator()
        layout.label(text=f'{len(material.sls.layers)} layers · mask storage ≈ {size:.0f} MiB')
    if t.status:
        # Short lines avoid a status label widening the entire sidebar.
        for line in textwrap.wrap(t.status[:144],width=34):
            layout.label(text=line)


class SLS_PT_desk(Panel):
    bl_label = 'Shipwreck Texture Desk'
    bl_idname = 'SLS_PT_desk'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Shipwreck Desk'

    def draw(self,context):
        draw_desk(self.layout,context)


class SLS_PT_desk_image(Panel):
    bl_label = 'Shipwreck Image Desk'
    bl_idname = 'SLS_PT_desk_image'
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Shipwreck Desk'

    def draw(self,context):
        draw_desk(self.layout,context,canvas=True)


class SLS_PT_desk_shader(Panel):
    bl_label = 'Shipwreck Texture Desk'
    bl_idname = 'SLS_PT_desk_shader'
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'Shipwreck Desk'

    def draw(self,context):
        draw_desk(self.layout,context)


_CLASSES = (SLS_PT_desk,SLS_PT_desk_image,SLS_PT_desk_shader)


def register():
    if not bpy.app.background:
        _preview_icons()
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    global _PREVIEWS,_TEMP
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
    if _PREVIEWS is not None:
        bpy.utils.previews.remove(_PREVIEWS)
        _PREVIEWS = None
    if _TEMP:
        _TEMP.cleanup()
        _TEMP = None
