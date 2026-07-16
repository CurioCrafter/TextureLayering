import bpy

print("PROBE_VERSION", bpy.app.version_string)
paint = bpy.context.scene.tool_settings.image_paint
print("PROBE_INITIAL_BRUSH", paint.brush)
print("PROBE_BRUSH_EDITABLE", not paint.is_property_readonly("brush"))
print("PROBE_AREAS", [(area.type, [region.type for region in area.regions]) for area in bpy.context.screen.areas])
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
obj.data.uv_layers.new(name="UVMap")
material = bpy.data.materials.new("Probe")
material.use_nodes = True
obj.data.materials.append(material)
image = bpy.data.images.new("Probe Mask", 32, 32, alpha=False, is_data=True)
bpy.context.scene.tool_settings.image_paint.mode = "IMAGE"
bpy.context.scene.tool_settings.image_paint.canvas = image
bpy.ops.object.mode_set(mode="TEXTURE_PAINT")
print("PROBE_MODE", obj.mode)
window = bpy.context.window
area = next(area for area in window.screen.areas if area.type == "VIEW_3D")
region = next(region for region in area.regions if region.type == "WINDOW")
with bpy.context.temp_override(window=window, screen=window.screen, area=area, region=region, space_data=area.spaces.active):
    print("PROBE_TOOL_RESULT", bpy.ops.wm.tool_set_by_id(name="builtin.brush", space_type="VIEW_3D"))
print("PROBE_ACTIVE_BRUSH", paint.brush)
if paint.brush:
    print("PROBE_BRUSH_NAME", paint.brush.name, paint.brush.image_tool, paint.brush.blend)
print("SLS_API_PROBE_PASS")
