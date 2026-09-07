"""Blender runtime checks: every preset, copy safety, UI contracts, real PBR bake."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import bpy
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',required=True)
parser.add_argument('--output',required=True)
options=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
root=Path(options.source_root).resolve();sys.path.insert(0,str(root))
out=Path(options.output).resolve();out.mkdir(parents=True,exist_ok=True)
import surface_layer_studio as addon
from surface_layer_studio import nodes, desk_ui
from surface_layer_studio.desk_catalog import PRESETS,RECIPES,BRUSHES
from surface_layer_studio.desk_ops import apply_preset,read_pixels
from surface_layer_studio.desk_pixels import PATTERNS,OPERATIONS
from surface_layer_studio.desk_bake import bake_material

checks=[]
def require(value,message):
    if not value:raise AssertionError(message)
    checks.append(message)

def run(operator,**kwargs):
    result=operator(**kwargs)
    require('FINISHED' in result,str(operator)+' finished')

addon.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
obj=bpy.context.active_object;obj.name='Desk regression'
scene=bpy.context.scene;scene.sls_tools.mask_resolution='256'
run(bpy.ops.sls.setup_material)
run(bpy.ops.sls.smart_uv_project)
material=obj.active_material
for preset in PRESETS:
    layer=apply_preset(bpy.context,preset.id)
    nodes.rebuild_material(material)
    require(nodes.graph_health(material)[0],preset.id+' graph')
    require(not material.sls.last_error,preset.id+' no graph errors')
    require(layer.desk.preset_id==preset.id,preset.id+' persisted metadata')
    # Avoid retaining a production-sized 49-layer test material.
    image=layer.mask_image;material.sls.layers.remove(0)
    bpy.data.images.remove(image)
for recipe in RECIPES:
    scene.sls_desk.recipe=recipe
    count=len(material.sls.layers)
    run(bpy.ops.sls.desk_recipe)
    require(len(material.sls.layers)==count+len(RECIPES[recipe][1]),recipe+' appends without deleting')
    while len(material.sls.layers)>1:
        image=material.sls.layers[0].mask_image
        material.sls.layers.remove(0)
        bpy.data.images.remove(image)
    material.sls.active_index=0
for brush in BRUSHES:
    run(bpy.ops.sls.desk_brush,preset=brush)
for pattern in PATTERNS:
    layer=material.sls.layers[0]
    layer.desk.pattern=pattern
    for placement in ('ALL','UP','DOWN','WATERLINE'):
        for coords in ('UV','OBJECT','WORLD'):
            layer.desk.placement=placement;layer.desk.coordinates=coords
            nodes.rebuild_material(material)
            require(not material.sls.last_error,f'{pattern}/{placement}/{coords} graph')
layer.desk.pattern='NONE';layer.desk.placement='ALL';layer.desk.coordinates='OBJECT'
layer.desk.variation=0;layer.desk.relief=0
# Unsaved pixels must survive duplication and copy-on-edit.
source=layer.mask_image
pixels=np.zeros((256,256,4),dtype=np.float32);pixels[...,3]=1;pixels[70:160,50:150,:3]=.37
source.pixels.foreach_set(pixels.ravel());source.update()
source_pixels=read_pixels(source).copy()
nodes.rebuild_material(material)
np.testing.assert_array_equal(read_pixels(source),source_pixels)
require(True,"graph rebuild preserves unsaved paint")
run(bpy.ops.sls.duplicate_layer)
layer=material.sls.layers[material.sls.active_index]
require(layer.mask_image!=source,'duplicate has independent mask')
np.testing.assert_allclose(read_pixels(layer.mask_image),source_pixels,atol=1/255)
require(True,'duplicate preserves unsaved pixels')
t=scene.sls_desk;t.target='mask_image'
for operation in OPERATIONS:
    before=layer.mask_image;before_pixels=read_pixels(before).copy()
    run(bpy.ops.sls.desk_edit,operation=operation)
    require(layer.mask_image!=before,operation+' creates copy')
    np.testing.assert_array_equal(read_pixels(before),before_pixels)
    edited=layer.mask_image
    run(bpy.ops.sls.desk_restore)
    require(layer.mask_image==before,operation+' restore')
    layer.desk.previous_image=None
    bpy.data.images.remove(edited)
layer.locked=True
require(not bpy.ops.sls.desk_edit.poll(),'locked filter disabled')
require(not bpy.ops.sls.desk_generate.poll(),'locked generator disabled')
require(bpy.ops.sls.desk_export_image.poll(),'locked images remain exportable')
layer.locked=False
for pattern in PATTERNS:
    t.lab_pattern=pattern
    run(bpy.ops.sls.desk_generate)
    require(layer.mask_image.is_dirty or layer.mask_image.packed_file is not None,'generated image retained')
run(bpy.ops.sls.desk_normal)
require(layer.normal_image is not None and layer.normal_format=='OPENGL','normal conversion')
t.normal_directx=True;run(bpy.ops.sls.desk_normal)
require(layer.normal_format=='DIRECTX','DirectX metadata')
run(bpy.ops.sls.desk_restore)
require(layer.normal_format=='OPENGL','normal restore also restores convention')
# Box projection must never project the tangent-space normal as a box.
layer.base_color_image=layer.mask_image
layer.desk.source_projection='BOX'
nodes.rebuild_material(material)
prefix='SLS_'+layer.uuid.replace('-','')[:10]
require(material.node_tree.nodes[prefix+'_BaseColor'].projection=='BOX','box color projection')
require(material.node_tree.nodes[prefix+'_Normal'].projection=='FLAT','normal stays UV projected')
# Draw all tabs and validate literal operator properties/icons against live RNA.
icons={i.identifier for i in bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items}
class Proxy:
    def __init__(self,rna):object.__setattr__(self,'rna',rna)
    def __setattr__(self,key,value):require(key in self.rna.properties,key+' is an operator property')
class Layout:
    def row(self,**k):return self
    def column(self,**k):return self
    def grid_flow(self,**k):return self
    def box(self,**k):return self
    def separator(self,**k):pass
    def label(self,**k):
        if 'icon' in k:require(k['icon'] in icons,k['icon']+' is a valid icon')
    def prop(self,data,key,**k):require(hasattr(data,key),'UI property '+key)
    def prop_search(self,data,key,search,search_key,**k):require(hasattr(data,key) and hasattr(search,search_key),'UI search '+key)
    def operator(self,id,**k):
        self.label(**k)
        namespace,name=id.split('.')
        rna=getattr(getattr(bpy.ops,namespace),name).get_rna_type()
        require(rna is not None,'UI operator '+id)
        return Proxy(rna)
    def template_list(self,*args,**k):pass
    def template_ID(self,data,key,**k):require(hasattr(data,key),'UI image '+key)
    def template_icon(self,**k):pass
for tab in ('LIBRARY','LAYERS','PAINT','LAB','EXPORT'):
    t.tab=t.canvas_tab=tab
    desk_ui.draw_desk(Layout(),bpy.context)
    desk_ui.draw_desk(Layout(),bpy.context,canvas=True)
require(True,'all ten panel tab states drawn')
# Restore a simple material and perform a real CPU bake, including AO/normal.
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.mesh.primitive_plane_add(size=2,location=(5,0,0))
plane=bpy.context.active_object;plane.name='Bake regression plane'
run(bpy.ops.sls.setup_material)
m=plane.active_material;m.sls.layers[0].roughness=.6;m.sls.layers[0].metallic=.2
m.sls.layers[0].tint=(.2,.4,.6,1)
engine=scene.render.engine;active=bpy.context.view_layer.objects.active
selection=tuple(bpy.context.selected_objects);images_before=set(bpy.data.images)
original_slots=tuple(plane.data.materials)
folder=bake_material(bpy.context,str(out/'bakes'),32,include_ao=True,include_normal=True)
manifest=json.loads((folder/'manifest.json').read_text())
require(manifest['status']=='complete','complete bake manifest')
require(set(manifest['files'])=={'BaseColor','Roughness','Metallic','Height','Emission','Normal','AO','ORM'},'all eight baked outputs')
require(scene.render.engine==engine,'render engine restored')
require(bpy.context.view_layer.objects.active==active,'active object restored')
require(tuple(bpy.context.selected_objects)==selection,'selection restored')
require(tuple(plane.data.materials)==original_slots,'source material slots preserved')
require(set(bpy.data.images)==images_before,'temporary bake images cleaned')
loaded=bpy.data.images.load(str(folder/'ORM.png'));loaded.colorspace_settings.name='Non-Color'
orm=read_pixels(loaded)[16,16]
np.testing.assert_allclose(orm[:3],[1,.6,.2],atol=.035)
bpy.data.images.remove(loaded)
require(True,'ORM actual baked channels verified')
# Failure must clean up the same way.
m.sls.preview_mode='ACTIVE_MASK'
try:bake_material(bpy.context,str(out/'bakes'),16,include_normal=True)
except ValueError:pass
else:raise AssertionError('Invalid preview bake should fail')
require(scene.render.engine==engine and bpy.context.view_layer.objects.active==active,'failed bake state restored')
require(not any(o.name.startswith('__SLS_BAKE') for o in bpy.data.objects),'failed bake object cleanup')
m.sls.preview_mode='COMPOSITE'
# Save/reopen checks run in this same fresh process; registration persists.
path=out/'desk-smoke.blend'
scene.sls_desk.query='biofilm';m.sls.layers[0].desk.seed=731
nodes.flush_pending_rebuilds()
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
require(bpy.context.scene.sls_desk.query=='biofilm','search persists after reopen')
require(bpy.data.objects['Bake regression plane'].active_material.sls.layers[0].desk.seed==731,'weathering persists after reopen')
report={'blender':bpy.app.version_string,'checks':len(checks),'presets':len(PRESETS),'patterns':len(PATTERNS),'result':'PASS','details':checks}
(out/'desk-test-report.json').write_text(json.dumps(report,indent=2))
print('SLS_DESK_SMOKE_PASS',json.dumps({k:v for k,v in report.items() if k!='details'}))
addon.unregister()
