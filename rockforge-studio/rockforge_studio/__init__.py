"""RockForge Studio — procedural, all-quad rock formations for Blender."""
bl_info = {
    'name': 'RockForge Studio', 'author': 'CurioCrafter', 'version': (1,0,0),
    'blender': (4,5,0), 'location': '3D View > Sidebar > RockForge',
    'description': 'Seeded geological formations, native quad retopology, PBR baking and GLB export',
    'category': 'Add Mesh',
}
import json
import random
import traceback
from pathlib import Path
import bpy
from bpy.props import (EnumProperty,FloatProperty,IntProperty,PointerProperty,StringProperty,BoolProperty)
from . import geometry, pipeline

FIELDS=('preset','formation','seed','width','depth','height','blocks','angularity','erosion',
        'bedding','tilt','algae','wetness','quads','density')


def configuration(settings):
    return {key:getattr(settings,key) for key in FIELDS}


def preset_changed(self,context):
    p=geometry.PRESETS[self.preset]
    for key in ('width','depth','height','blocks','angularity','erosion','bedding','tilt'):
        setattr(self,key,p[key])
    self.algae=.55 if self.preset=='REEF' else 0
    self.wetness=.35 if self.preset=='REEF' else 0


class RF_Settings(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Geology',items=[(k,v['label'],v['label']) for k,v in geometry.PRESETS.items()],
                         default='BASALT',update=preset_changed)
    formation: EnumProperty(name='Formation',items=[('MOUND','Outcrop','A connected multi-block outcrop'),
        ('RIDGE','Ridge','Taller central ridge'),('BOULDER','Single boulder','One fractured stone')],default='MOUND')
    seed: IntProperty(name='Seed',default=42,min=0,max=999999)
    width: FloatProperty(name='Width',default=4,min=.1,max=100,unit='LENGTH')
    depth: FloatProperty(name='Depth',default=2.8,min=.1,max=100,unit='LENGTH')
    height: FloatProperty(name='Height',default=2.6,min=.1,max=100,unit='LENGTH')
    blocks: IntProperty(name='Joint blocks',default=22,min=4,max=60)
    angularity: FloatProperty(name='Angularity',default=.88,min=0,max=1)
    erosion: FloatProperty(name='Erosion',default=.16,min=0,max=1)
    bedding: FloatProperty(name='Bedding',default=.18,min=0,max=1)
    tilt: FloatProperty(name='Joint tilt',default=.20,min=-.65,max=.65,subtype='ANGLE')
    algae: FloatProperty(name='Algae coverage',default=0,min=0,max=1)
    wetness: FloatProperty(name='Wetness',default=0,min=0,max=1)
    quads: IntProperty(name='Target quads',default=5000,min=500,max=30000,
                      description='Approximate QuadriFlow target; game triangles are about twice the face count')
    density: IntProperty(name='Source resolution',default=160,min=64,max=280,
                        description='Voxels across longest dimension. Higher values cost time and memory')
    batch_count: IntProperty(name='Variants',default=3,min=1,max=12)
    resolution: EnumProperty(name='Texture size',items=[('512','512','Preview'),('1024','1024','Compact'),
        ('2048','2048','High detail'),('4096','4096','Close-up; higher memory cost')],default='2048')
    output: StringProperty(name='Output folder',subtype='DIR_PATH',default='//rockforge_exports/')
    status: StringProperty(default='Choose a preset, then build a quad mesh.')


class RF_OT_build(bpy.types.Operator):
    bl_idname='rockforge.build';bl_label='Build Quad Mesh';bl_options={'REGISTER','UNDO'}
    bake_textures: BoolProperty(default=False,options={'HIDDEN'})
    def execute(self,context):
        s=context.scene.rockforge
        wm=context.window_manager;wm.progress_begin(0,3)
        try:
            wm.progress_update(0)
            low,high=pipeline.build(configuration(s))
            low.location=context.scene.cursor.location
            wm.progress_update(1)
            if self.bake_textures:
                directory=Path(bpy.path.abspath(s.output))/pipeline.safe_name(low.name)
                pipeline.bake(low,high,directory,int(s.resolution))
            wm.progress_update(2)
            a=geometry.mesh_audit(low)
            s.status=f"Built {a['quads']:,} quads / {a['triangles']:,} triangles"
            self.report({'INFO'},s.status)
            return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();s.status=str(exc);self.report({'ERROR'},str(exc));return {'CANCELLED'}
        finally:wm.progress_end()


class RF_OT_batch(bpy.types.Operator):
    bl_idname='rockforge.batch';bl_label='Build Seed Variations';bl_options={'REGISTER','UNDO'}
    def execute(self,c):
        s=c.scene.rockforge;cfg=configuration(s);origin=c.scene.cursor.location.copy()
        try:
            for i in range(s.batch_count):
                cfg['seed']=s.seed+i
                low,high=pipeline.build(dict(cfg))
                low.location=origin
                low.location.x+=i*s.width*1.3
            self.report({'INFO'},f'Built {s.batch_count} quad variations. Bake each chosen rock separately.')
            return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();self.report({'ERROR'},str(exc));return {'CANCELLED'}


class RF_OT_seed(bpy.types.Operator):
    bl_idname='rockforge.random_seed';bl_label='Random Seed';bl_options={'UNDO'}
    def execute(self,context):
        context.scene.rockforge.seed=random.SystemRandom().randrange(1000000);return {'FINISHED'}


class RF_OT_load(bpy.types.Operator):
    bl_idname='rockforge.load_settings';bl_label='Load Settings from Active';bl_options={'UNDO'}
    @classmethod
    def poll(cls,c):return bool(c.object and c.object.get('rf_config'))
    def execute(self,c):
        cfg=json.loads(c.object['rf_config']);s=c.scene.rockforge
        # Set preset first; the update callback must not overwrite custom settings later.
        s.preset=cfg['preset']
        for k in FIELDS:
            if k in cfg:setattr(s,k,cfg[k])
        return {'FINISHED'}


class RF_Active:
    @classmethod
    def poll(cls,c):return bool(c.object and c.object.type=='MESH' and c.object.get('rf_role')=='LOW')


class RF_OT_bake(RF_Active,bpy.types.Operator):
    bl_idname='rockforge.bake';bl_label='Bake Active Rock';bl_options={'REGISTER','UNDO'}
    def execute(self,c):
        low=c.object;s=c.scene.rockforge
        try:
            high=bpy.data.objects.get(low.get('rf_source',''))
            if high is None:raise ValueError('The retained high-detail source is missing.')
            pipeline.bake(low,high,Path(bpy.path.abspath(s.output))/pipeline.safe_name(low.name),int(s.resolution))
            s.status='Baked BaseColor / Normal / Roughness / AO'
            self.report({'INFO'},s.status);return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();self.report({'ERROR'},str(exc));return {'CANCELLED'}


class RF_OT_export(RF_Active,bpy.types.Operator):
    bl_idname='rockforge.export_glb';bl_label='Export Active GLB'
    @classmethod
    def poll(cls,c):
        return bool(c.object and c.object.type=='MESH' and c.object.get('rf_baked')
                    and c.object.get('rf_role') in ('LOW','LOD1','LOD2'))
    def execute(self,c):
        try:
            path=Path(bpy.path.abspath(c.scene.rockforge.output))/(pipeline.safe_name(c.object.name)+'.glb')
            pipeline.export_glb(c.object,path)
            self.report({'INFO'},str(path));return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();self.report({'ERROR'},str(exc));return {'CANCELLED'}


class RF_OT_lods(RF_Active,bpy.types.Operator):
    bl_idname='rockforge.lods';bl_label='Create LOD 1 + 2';bl_options={'REGISTER','UNDO'}
    def execute(self,c):
        try:
            pipeline.make_lods(c.object)
            self.report({'INFO'},'Created hidden 50% and 25% LOD meshes; inspect their shading before shipping.')
            return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();self.report({'ERROR'},str(exc));return {'CANCELLED'}


class RF_OT_collision(RF_Active,bpy.types.Operator):
    bl_idname='rockforge.collision';bl_label='Create Convex Collision';bl_options={'REGISTER','UNDO'}
    def execute(self,c):
        try:pipeline.collision(c.object);return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();self.report({'ERROR'},str(exc));return {'CANCELLED'}


class RF_OT_audit(bpy.types.Operator):
    bl_idname='rockforge.audit';bl_label='Inspect Topology'
    @classmethod
    def poll(cls,c):return bool(c.object and c.object.type=='MESH')
    def execute(self,c):
        a=geometry.mesh_audit(c.object)
        txt=bpy.data.texts.get('RockForge Mesh Report') or bpy.data.texts.new('RockForge Mesh Report')
        txt.clear();txt.write(json.dumps(a,indent=2))
        c.scene.rockforge.status=f"{a['quads']:,} quads | {a['nonmanifold_edges']} nonmanifold edges | {a['components']} component(s)"
        self.report({'INFO'},c.scene.rockforge.status)
        return {'FINISHED'}


class RF_OT_reference(bpy.types.Operator):
    bl_idname='rockforge.reference_quads';bl_label='Retopologize Reference (Shape Only)';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,c):return bool(c.object and c.object.type=='MESH')
    def execute(self,c):
        try:
            s=c.scene.rockforge
            low=pipeline.reference_retopology(c.object,s.quads,s.seed);geometry.activate(low)
            self.report({'INFO'},'Created clay quad copy. Original untouched; reference textures are not transferred.')
            return {'FINISHED'}
        except Exception as exc:
            traceback.print_exc();self.report({'ERROR'},str(exc));return {'CANCELLED'}


class RF_PT_main(bpy.types.Panel):
    bl_label='RockForge Studio';bl_idname='RF_PT_main'
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RockForge'
    def draw(self,c):
        l=self.layout;s=c.scene.rockforge
        l.label(text='GEOLOGY  /  QUADS  /  PBR',icon='MESH_ICOSPHERE')
        l.prop(s,'preset');l.prop(s,'formation')
        row=l.row(align=True);row.prop(s,'seed');row.operator('rockforge.random_seed',text='',icon='FILE_REFRESH')
        l.operator('rockforge.load_settings',icon='IMPORT')
        box=l.box();box.label(text='Formation')
        row=box.row(align=True);row.prop(s,'width');row.prop(s,'depth');row.prop(s,'height')
        box.prop(s,'blocks');box.prop(s,'angularity',slider=True);box.prop(s,'tilt')
        box.prop(s,'erosion',slider=True);box.prop(s,'bedding',slider=True)
        row=box.row(align=True);row.prop(s,'algae',slider=True);row.prop(s,'wetness',slider=True)
        box=l.box();box.label(text='Mesh and texture budget')
        box.prop(s,'quads');box.label(text=f'Approx. {s.quads*2:,} game triangles')
        box.prop(s,'density');box.prop(s,'resolution');box.prop(s,'output')
        row=l.row(align=True);row.scale_y=1.4
        row.operator('rockforge.build',text='Build Mesh',icon='MESH_DATA').bake_textures=False
        row.operator('rockforge.build',text='Build + Bake',icon='RENDER_STILL').bake_textures=True
        l.label(text='Native remesh/bake may take several minutes.',icon='INFO')
        row=l.row(align=True);row.prop(s,'batch_count');row.operator('rockforge.batch',text='Variations')
        l.separator()
        row=l.row(align=True);row.operator('rockforge.bake',text='Bake Active');row.operator('rockforge.export_glb',text='Export GLB')
        row=l.row(align=True);row.operator('rockforge.lods',text='LODs');row.operator('rockforge.collision',text='Collision')
        l.operator('rockforge.audit',icon='VIEWZOOM')
        if c.object and c.object.type=='MESH':
            mesh=c.object.data
            l.label(text=f'Active: {len(mesh.polygons):,} faces / {len(mesh.vertices):,} vertices')
        # Status stays in its own panel so long strings don't widen the sidebar.


class RF_PT_reference(bpy.types.Panel):
    bl_label='Reference retopology';bl_parent_id='RF_PT_main';bl_options={'DEFAULT_CLOSED'}
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='RockForge'
    def draw(self,c):
        self.layout.label(text='Closed meshes only. Original is preserved.')
        self.layout.label(text='Shape transfer only; no reference texture bake.')
        self.layout.operator('rockforge.reference_quads')


CLASSES=(RF_Settings,RF_OT_build,RF_OT_batch,RF_OT_seed,RF_OT_load,RF_OT_bake,RF_OT_export,
    RF_OT_lods,RF_OT_collision,RF_OT_audit,RF_OT_reference,RF_PT_main,RF_PT_reference)


def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.rockforge=PointerProperty(type=RF_Settings)


def unregister():
    if hasattr(bpy.types.Scene,'rockforge'):del bpy.types.Scene.rockforge
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)


if __name__=='__main__':register()
