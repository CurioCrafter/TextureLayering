"""Persistent settings for the texture desk and non-destructive weathering."""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import PropertyGroup

from .desk_catalog import CATEGORIES, RECIPES
from .desk_pixels import PATTERNS
from .properties import SLS_Layer, _request_rebuild


def _filter_changed(self, _context):
    self.page = 0


class SLS_WeatherSettings(PropertyGroup):
    pattern: EnumProperty(name='Pattern', items=[(x, x.replace('_', ' ').title(), '') for x in PATTERNS], default='NONE', update=_request_rebuild)
    coordinates: EnumProperty(name='Generator coordinates', items=[('OBJECT', 'Object', 'Continuous 3D pattern; local object units'), ('WORLD', 'World', 'World-space pattern; shared across objects'), ('UV', 'UV', 'Follow the layer UV map')], default='OBJECT', update=_request_rebuild)
    scale: FloatProperty(name='Pattern scale', default=8, min=.01, max=1000, update=_request_rebuild)
    seed: IntProperty(name='Seed', default=1, min=0, max=100000, update=_request_rebuild)
    coverage: FloatProperty(name='Coverage', default=.5, min=0, max=1, subtype='FACTOR', update=_request_rebuild)
    softness: FloatProperty(name='Transition', default=.15, min=.001, max=1, update=_request_rebuild)
    detail: FloatProperty(name='Detail', default=3, min=0, max=8, update=_request_rebuild)
    stretch: FloatVectorProperty(name='Axis scale', size=3, default=(1,1,1), min=.001, max=100, update=_request_rebuild)
    placement: EnumProperty(name='Placement', items=[('ALL','Everywhere','No geometry direction restriction'), ('UP','Upward-facing','World normals: settled dust and silt'), ('DOWN','Downward-facing','World normals: sheltered undersides'), ('WATERLINE','World waterline','Band around a world-space Z height')], default='ALL', update=_request_rebuild)
    waterline: FloatProperty(name='Waterline Z', default=0, subtype='DISTANCE', update=_request_rebuild)
    band_width: FloatProperty(name='Band half-width', default=.3, min=.001, subtype='DISTANCE', update=_request_rebuild)
    black: FloatProperty(name='Black point', default=0, min=0, max=.999, update=_request_rebuild)
    white: FloatProperty(name='White point', default=1, min=.001, max=1, update=_request_rebuild)
    gamma: FloatProperty(name='Mask gamma', default=1, min=.05, max=8, update=_request_rebuild)
    secondary: FloatVectorProperty(name='Secondary tint', subtype='COLOR', size=4, default=(.2,.3,.2,1), min=0, max=1, update=_request_rebuild)
    variation: FloatProperty(name='Color variation', default=0, min=0, max=1, update=_request_rebuild)
    relief: FloatProperty(name='Procedural relief', default=0, min=0, max=1, update=_request_rebuild)
    roughness_variation: FloatProperty(name='Roughness variation', default=0, min=0, max=.5, update=_request_rebuild)
    source_projection: EnumProperty(name='Image projection', items=[('UV','UV','Use the source UV transform'), ('BOX','Object box','Triplanar box projection for color/scalar images; normal maps remain UV-mapped')], default='UV', update=_request_rebuild)
    previous_image: PointerProperty(type=bpy.types.Image, name='Previous image')
    previous_slot: StringProperty(default='', options={'HIDDEN'})
    previous_normal_format: StringProperty(default='OPENGL',options={'HIDDEN'})
    preset_id: StringProperty(default='', options={'HIDDEN'})


CHANNELS = [('mask_image','Mask','Edit the active layer paint mask'), ('base_color_image','Base color','Edit a copy of the color texture'), ('roughness_image','Roughness',''), ('metallic_image','Metallic',''), ('height_image','Height',''), ('ao_image','AO',''), ('normal_image','Normal',''), ('emission_image','Emission','')]


class SLS_DeskSettings(PropertyGroup):
    tab: EnumProperty(name='Desk', items=[('LIBRARY','Library','Preset swatches and complete recipes'), ('LAYERS','Layers','Layer stack and live weathering'), ('PAINT','Paint','Brush and image targets'), ('LAB','Lab','Copy-on-edit image tools'), ('EXPORT','Export','Flatten channels for a game engine')], default='LIBRARY')
    canvas_tab: EnumProperty(name='Desk', items=[('LIBRARY','Library','Preset swatches and complete recipes'), ('LAYERS','Layers','Layer stack and live weathering'), ('PAINT','Paint','Brush and image targets'), ('LAB','Lab','Copy-on-edit image tools'), ('EXPORT','Export','Flatten channels for a game engine')], default='PAINT')
    query: StringProperty(name='Search presets', default='', update=_filter_changed)
    category: EnumProperty(name='Category', items=[('ALL','All materials','')] + [(c,c,'') for c in CATEGORIES], default='ALL', update=_filter_changed)
    favorites: StringProperty(default='', options={'HIDDEN'})
    favorites_only: BoolProperty(name='Favorites only', default=False, update=_filter_changed)
    page: IntProperty(name='Page', default=0, min=0)
    recipe: EnumProperty(name='Scene recipe', items=[(k,v[0], 'Append '+str(len(v[1]))+' editable layers') for k,v in RECIPES.items()], default='WRECK_HULL')
    target: EnumProperty(name='Image target', items=CHANNELS, default='mask_image')
    lab_pattern: EnumProperty(name='2D pattern', items=[(p,p.title(),'') for p in PATTERNS], default='NOISE')
    lab_seed: IntProperty(name='Seed', default=1, min=0, max=100000)
    lab_scale: FloatProperty(name='Scale', default=8, min=1, max=128)
    lab_coverage: FloatProperty(name='Coverage', default=.5, min=0, max=1)
    lab_softness: FloatProperty(name='Softness', default=.15, min=.001, max=1)
    black: FloatProperty(name='Black / threshold', default=0, min=0, max=.999)
    white: FloatProperty(name='White', default=1, min=.001, max=1)
    gamma: FloatProperty(name='Gamma', default=1, min=.05, max=8)
    radius: IntProperty(name='Filter radius (px)', default=3, min=1, max=32)
    wrap: BoolProperty(name='Wrap filter edges', default=False)
    normal_strength: FloatProperty(name='Normal strength', default=4, min=0, max=100)
    normal_directx: BoolProperty(name='DirectX (-Y)', default=False)
    export_directory: StringProperty(name='Export folder', default='//textures/shipwreck/', subtype='DIR_PATH')
    export_resolution: EnumProperty(name='Resolution', items=[('256','256',''),('512','512',''),('1024','1K',''),('2048','2K',''),('4096','4K','')], default='1024')
    bake_ao: BoolProperty(name='Bake ambient occlusion', default=False, description='When off, ORM red is white; no AO is inferred')
    bake_normal: BoolProperty(name='Bake tangent normal', default=True)
    last_export: StringProperty(name='Last export', default='')
    status: StringProperty(name='Status', default='Local procedural tools. No API key or network required.')


_CLASSES = (SLS_WeatherSettings, SLS_DeskSettings)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    SLS_Layer.desk = PointerProperty(type=SLS_WeatherSettings)
    bpy.types.Scene.sls_desk = PointerProperty(type=SLS_DeskSettings)


def unregister():
    del bpy.types.Scene.sls_desk
    del SLS_Layer.desk
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
