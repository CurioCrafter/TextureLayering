"""Procedural rock shading and baked glTF-compatible PBR materials."""
import bpy
from .geometry import PRESETS


def procedural(cfg, name):
    mat = bpy.data.materials.new(name + '_Procedural')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()

    def node(kind, title, x, y):
        value = nodes.new(kind)
        value.name = title
        value.label = title
        value.location = (x, y)
        return value

    def ramp(socket, stops, title, x, y):
        value = node('ShaderNodeValToRGB', title, x, y)
        for index, (position, color) in enumerate(stops):
            element = value.color_ramp.elements[index] if index < 2 else value.color_ramp.elements.new(position)
            element.position = position
            element.color = color
        links.new(socket, value.inputs[0])
        return value.outputs['Color']

    def texture(scale, detail, title, x, y, vector):
        value = node('ShaderNodeTexNoise', title, x, y)
        value.inputs['Scale'].default_value = scale
        value.inputs['Detail'].default_value = detail
        value.inputs['Roughness'].default_value = 0.72
        links.new(vector, value.inputs['Vector'])
        return value

    def mix(a, b, factor, title, x, y, mode='MIX'):
        value = node('ShaderNodeMixRGB', title, x, y)
        value.blend_type = mode
        if isinstance(factor, (float, int)):
            value.inputs[0].default_value = factor
        else:
            links.new(factor, value.inputs[0])
        for index, source in ((1, a), (2, b)):
            if isinstance(source, tuple):
                value.inputs[index].default_value = source
            else:
                links.new(source, value.inputs[index])
        return value.outputs[0]

    coords = node('ShaderNodeTexCoord', 'Local coordinates', -1700, 350)
    mapping = node('ShaderNodeMapping', 'Consistent scale', -1510, 350)
    scale = 1.0 / max(cfg['width'], cfg['depth'], cfg['height'])
    mapping.inputs['Scale'].default_value = (scale, scale, scale)
    seed = cfg['seed']
    mapping.inputs['Location'].default_value = ((seed % 19) * 2.31, (seed % 13) * 1.71, (seed % 23) * 0.83)
    links.new(coords.outputs['Object'], mapping.inputs['Vector'])
    vector = mapping.outputs[0]
    macro = texture(4, 4, 'Mineral variation', -1300, 630, vector)
    middle = texture(29, 4, 'Weathered grain', -1300, 350, vector)
    fine = texture(210, 3, 'Micro grains', -1300, 30, vector)
    palette = PRESETS[cfg['preset']]
    colors = ramp(macro.outputs['Fac'], [(0.22, palette['dark']), (0.72, palette['light'])], 'Stone palette', -1030, 720)
    mottling = ramp(middle.outputs['Fac'], [(0.22, (0.16, 0.15, 0.135, 1)), (0.78, (0.93, 0.92, 0.89, 1))], 'Weathering', -1030, 480)
    color = mix(colors, mottling, 0.5, 'Stone weathering', -760, 740, 'MULTIPLY')
    warp = node('ShaderNodeVectorMath', 'Fracture warp', -1050, -240)
    warp.operation = 'SCALE'
    links.new(middle.outputs['Color'], warp.inputs[0])
    warp.inputs['Scale'].default_value = 0.105
    add = node('ShaderNodeVectorMath', 'Fracture coordinates', -810, -240)
    add.operation = 'ADD'
    links.new(vector, add.inputs[0])
    links.new(warp.outputs[0], add.inputs[1])
    cells = node('ShaderNodeTexVoronoi', 'Hairline fractures', -590, -240)
    cells.feature = 'DISTANCE_TO_EDGE'
    cells.distance = 'EUCLIDEAN'
    cells.inputs['Scale'].default_value = 15
    links.new(add.outputs['Vector'], cells.inputs['Vector'])
    cracks = ramp(cells.outputs['Distance'], [(0.001, (0.035, 0.03, 0.022, 1)), (0.014, (0.57, 0.53, 0.45, 1)), (0.033, (1, 1, 1, 1))], 'Fracture width', -310, -240)
    color = mix(color, cracks, 0.43, 'Fracture tint', -490, 740, 'MULTIPLY')
    wave = node('ShaderNodeTexWave', 'Sediment bedding', -1030, -580)
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Z'
    for key, value in {'Scale': 9, 'Distortion': 5.5, 'Detail': 4, 'Detail Scale': 1.6}.items():
        wave.inputs[key].default_value = value
    links.new(vector, wave.inputs['Vector'])
    bedding = ramp(wave.outputs['Fac'], [(0.15, (0.31, 0.26, 0.21, 1)), (0.8, (1, 0.95, 0.85, 1))], 'Layer tint', -790, -580)
    color = mix(color, bedding, cfg['bedding'] * 0.37, 'Bedding color', -240, 740, 'MULTIPLY')
    algae = texture(10, 3, 'Marine colonies', -580, -600, vector)
    mask = ramp(algae.outputs['Fac'], [(0.49, (0, 0, 0, 1)), (0.68, (1, 1, 1, 1))], 'Growth mask', -300, -590)
    growth = node('ShaderNodeMath', 'Growth amount', -40, -540)
    growth.operation = 'MULTIPLY'
    links.new(mask, growth.inputs[0])
    growth.inputs[1].default_value = cfg.get('algae', 0)
    color = mix(color, (0.056, 0.096, 0.022, 1), growth.outputs[0], 'Algae color', 10, 730)
    grain = ramp(fine.outputs['Fac'], [(0.2, (0.45, 0.43, 0.4, 1)), (0.8, (1, 1, 1, 1))], 'Crystal grain', -820, 20)
    color = mix(color, grain, 0.6 if cfg['preset'] == 'GRANITE' else 0.3, 'RF_BASE_COLOR', 250, 730, 'MULTIPLY')
    roughness = node('ShaderNodeMath', 'Roughness variation', -230, 180)
    roughness.operation = 'MULTIPLY_ADD'
    links.new(middle.outputs['Fac'], roughness.inputs[0])
    roughness.inputs[1].default_value = 0.22
    roughness.inputs[2].default_value = 0.62 - cfg.get('wetness', 0) * 0.37
    rough = node('ShaderNodeClamp', 'RF_ROUGHNESS', 240, 190)
    links.new(roughness.outputs[0], rough.inputs[0])
    relief = mix(middle.outputs['Fac'], cracks, 0.22, 'Surface relief', -20, -150, 'MULTIPLY')
    bump = node('ShaderNodeBump', 'Weathering relief', 240, -170)
    bump.inputs['Strength'].default_value = 0.62
    bump.inputs['Distance'].default_value = max(cfg['width'], cfg['depth']) * 0.011
    links.new(relief, bump.inputs['Height'])
    micro = node('ShaderNodeBump', 'Mineral microrelief', 470, -130)
    micro.inputs['Strength'].default_value = 0.43
    micro.inputs['Distance'].default_value = max(cfg['width'], cfg['depth']) * 0.0018
    links.new(fine.outputs['Fac'], micro.inputs['Height'])
    links.new(bump.outputs['Normal'], micro.inputs['Normal'])
    surface = node('ShaderNodeBsdfPrincipled', 'RF_SURFACE', 740, 510)
    links.new(color, surface.inputs['Base Color'])
    links.new(rough.outputs[0], surface.inputs['Roughness'])
    links.new(micro.outputs['Normal'], surface.inputs['Normal'])
    surface.inputs['Specular IOR Level'].default_value = 0.28
    output = node('ShaderNodeOutputMaterial', 'Material Output', 1050, 510)
    links.new(surface.outputs['BSDF'], output.inputs['Surface'])
    mat.diffuse_color = palette['light']
    mat['rf_procedural'] = True
    return mat


def baked(name, images):
    mat = bpy.data.materials.new(name + '_BakedPBR')
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    surface = nodes.get('Principled BSDF')
    surface.location = (420, 250)
    surface.inputs['Specular IOR Level'].default_value = 0.28
    nodes.get('Material Output').location = (740, 250)
    for index, kind in enumerate(('BaseColor', 'Normal', 'Roughness', 'AO')):
        if kind not in images:
            continue
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = images[kind]
        texture.name = kind
        texture.label = kind
        texture.location = (-320, 540 - index * 260)
        if kind == 'BaseColor':
            links.new(texture.outputs['Color'], surface.inputs['Base Color'])
        elif kind == 'Roughness':
            links.new(texture.outputs['Color'], surface.inputs['Roughness'])
        elif kind == 'Normal':
            normal = nodes.new('ShaderNodeNormalMap')
            normal.location = (30, 80)
            links.new(texture.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], surface.inputs['Normal'])
        else:
            group = bpy.data.node_groups.get('glTF Material Output')
            if group is None:
                group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
                group.nodes.new('NodeGroupInput')
                group.nodes.new('NodeGroupOutput')
            inputs = {item.name for item in group.interface.items_tree if item.item_type == 'SOCKET' and item.in_out == 'INPUT'}
            for title, default in (('Occlusion', 1.0), ('Thickness', 0.0), ('Dispersion', 0.0), ('Iridescence Factor', 0.0), ('Iridescence Thickness Minimum', 100.0)):
                if title not in inputs:
                    socket = group.interface.new_socket(name=title, in_out='INPUT', socket_type='NodeSocketFloat')
                    socket.default_value = default
            output = nodes.new('ShaderNodeGroup')
            output.node_tree = group
            output.location = (30, -440)
            links.new(texture.outputs['Color'], output.inputs['Occlusion'])
    mat['rf_baked'] = True
    return mat
