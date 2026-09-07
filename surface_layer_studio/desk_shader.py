"""Procedural shader additions. Every node is owned by the existing graph builder."""


def _helpers():
    from .nodes import _new_node, _math
    return _new_node, _math


def _node(tree, kind, name, frame):
    new, _ = _helpers()
    return new(tree, kind, name, name.rsplit('_',1)[-1], -900, -900, frame)


def _math(tree, operation, name, a, b=None, frame=None, clamp=False):
    new, _ = _helpers()
    node = new(tree, 'ShaderNodeMath', name, name, -900, -900, frame)
    node.operation, node.use_clamp = operation, clamp
    for index, value in enumerate((a,b)):
        if value is not None:
            if isinstance(value, (int,float)):
                node.inputs[index].default_value = value
            else:
                tree.links.new(value, node.inputs[index])
    return node.outputs[0]


def _field(tree, layer, prefix, frame):
    w = layer.desk
    name = prefix+'_DeskField'
    existing = tree.nodes.get(name)
    if existing:
        return existing.outputs[0]
    tex = _node(tree, 'ShaderNodeTexCoord', prefix+'_DeskCoords', frame)
    if w.coordinates == 'WORLD':
        geo = _node(tree, 'ShaderNodeNewGeometry', prefix+'_DeskPosition', frame)
        vector = geo.outputs['Position']
    elif w.coordinates == 'UV':
        uv = _node(tree, 'ShaderNodeUVMap', prefix+'_DeskUV', frame)
        uv.uv_map = layer.uv_map
        vector = uv.outputs['UV']
    else:
        vector = tex.outputs['Object']
    mapping = _node(tree,'ShaderNodeMapping',prefix+'_DeskMapping',frame)
    tree.links.new(vector, mapping.inputs['Vector'])
    mapping.inputs['Scale'].default_value = (w.stretch[0], w.stretch[1], w.stretch[2] * (.08 if w.pattern == 'STREAKS' else 1))
    mapping.inputs['Location'].default_value = (w.seed * 1.371, w.seed * 2.713, w.seed * .917)
    vector = mapping.outputs['Vector']
    if w.pattern in {'CELLS','CRACKS'}:
        node = _node(tree,'ShaderNodeTexVoronoi',prefix+'_DeskCells',frame)
        node.feature = 'DISTANCE_TO_EDGE' if w.pattern == 'CRACKS' else 'F1'
        node.inputs['Scale'].default_value = w.scale
        tree.links.new(vector,node.inputs['Vector'])
        raw = node.outputs['Distance']
        if w.pattern == 'CRACKS':
            raw = _math(tree,'MULTIPLY',prefix+'_DeskEdgeScale',raw,4,frame)
        raw = _math(tree,'SUBTRACT',prefix+'_DeskCellInvert',1,raw,frame,True)
    elif w.pattern in {'STRIPES','TILES'}:
        node = _node(tree,'ShaderNodeTexWave' if w.pattern == 'STRIPES' else 'ShaderNodeTexBrick',prefix+'_DeskPattern',frame)
        node.inputs['Scale'].default_value = w.scale
        tree.links.new(vector,node.inputs['Vector'])
        if w.pattern == 'STRIPES':
            node.bands_direction = 'DIAGONAL'
            raw = node.outputs['Fac']
        else:
            node.inputs['Mortar Size'].default_value = .025
            node.offset = 0
            raw = _math(tree,'SUBTRACT',prefix+'_DeskTileInvert',1,node.outputs['Fac'],frame,True)
    else:
        node = _node(tree,'ShaderNodeTexNoise',prefix+'_DeskNoise',frame)
        # Seeded 3D coordinates already provide independent patterns; avoid the
        # redundant fourth noise dimension and its derivative cost in previews.
        node.noise_dimensions = '3D'
        node.inputs['Scale'].default_value = w.scale
        node.inputs['Detail'].default_value = w.detail
        tree.links.new(vector,node.inputs['Vector'])
        raw = node.outputs['Fac']
    reroute = _node(tree,'NodeReroute',name,frame)
    tree.links.new(raw,reroute.inputs[0])
    return reroute.outputs[0]


def mask(tree, layer, prefix, frame, paint_mask):
    if not hasattr(layer,'desk'):
        return paint_mask
    w = layer.desk
    result = paint_mask
    if w.pattern != 'NONE':
        field = _field(tree,layer,prefix,frame)
        ramp = _node(tree,'ShaderNodeMapRange',prefix+'_DeskCoverage',frame)
        ramp.clamp = True
        ramp.interpolation_type = 'SMOOTHSTEP'
        ramp.inputs['From Min'].default_value = 1-w.coverage-w.softness/2
        ramp.inputs['From Max'].default_value = 1-w.coverage+w.softness/2
        tree.links.new(field,ramp.inputs['Value'])
        generated = ramp.outputs['Result']
        if w.coverage <= 0 or w.coverage >= 1:
            generated = float(w.coverage >= 1)
        result = _math(tree,'MULTIPLY',prefix+'_DeskPaintMask',result,generated,frame,True)
    if w.placement != 'ALL':
        geo = _node(tree,'ShaderNodeNewGeometry',prefix+'_DeskGeometry',frame)
        xyz = _node(tree,'ShaderNodeSeparateXYZ',prefix+'_DeskWorldAxis',frame)
        tree.links.new(geo.outputs['Position' if w.placement == 'WATERLINE' else 'Normal'],xyz.inputs[0])
        axis = xyz.outputs['Z']
        if w.placement == 'WATERLINE':
            distance = _math(tree,'SUBTRACT',prefix+'_DeskWaterLevel',axis,w.waterline,frame)
            distance = _math(tree,'ABSOLUTE',prefix+'_DeskDistance',distance,frame=frame)
            distance = _math(tree,'DIVIDE',prefix+'_DeskBand',distance,max(.001,w.band_width),frame)
            placement = _math(tree,'SUBTRACT',prefix+'_DeskWaterMask',1,distance,frame,True)
        else:
            placement = _math(tree,'MULTIPLY',prefix+'_DeskFacing',axis,-1 if w.placement=='DOWN' else 1,frame,True)
        result = _math(tree,'MULTIPLY',prefix+'_DeskPlacement',result,placement,frame,True)
    if w.black > 0 or w.white < 1 or w.gamma != 1:
        result = _math(tree,'SUBTRACT',prefix+'_DeskBlack',result,w.black,frame)
        result = _math(tree,'DIVIDE',prefix+'_DeskWhite',result,max(.001,w.white-w.black),frame,True)
        result = _math(tree,'POWER',prefix+'_DeskGamma',result,1/w.gamma,frame,True)
    return result


def surface(tree, layer, prefix, frame, color, roughness):
    if not hasattr(layer,'desk'):
        return color, roughness, None
    w = layer.desk
    if not (w.variation or w.relief or w.roughness_variation):
        return color, roughness, None
    field = _field(tree,layer,prefix,frame)
    if w.variation:
        mix = _node(tree,'ShaderNodeMixRGB',prefix+'_DeskColor',frame)
        factor = _math(tree,'MULTIPLY',prefix+'_DeskColorAmount',field,w.variation,frame,True)
        tree.links.new(factor,mix.inputs[0])
        tree.links.new(color,mix.inputs[1])
        mix.inputs[2].default_value = w.secondary
        color = mix.outputs[0]
    if w.roughness_variation:
        centered = _math(tree,'SUBTRACT',prefix+'_DeskRoughCenter',field,.5,frame)
        scaled = _math(tree,'MULTIPLY',prefix+'_DeskRoughScale',centered,w.roughness_variation,frame)
        roughness = _math(tree,'ADD',prefix+'_DeskRoughness',roughness,scaled,frame,True)
    height = None
    if w.relief:
        centered = _math(tree,'SUBTRACT',prefix+'_DeskHeightCenter',field,.5,frame)
        scaled = _math(tree,'MULTIPLY',prefix+'_DeskHeightScale',centered,w.relief,frame)
        height = _math(tree,'ADD',prefix+'_DeskHeight',scaled,.5,frame,True)
    return color,roughness,height
