"""Seeded geological block construction and native Blender retopology.

No external assets, downloaded libraries, or source-scene dependencies.
"""
import math
import random
import json
import bpy
import bmesh
from mathutils import Vector, Euler
from mathutils import noise

PRESETS = {
    'BASALT': dict(label='Jointed basalt', height=2.6, width=4.0, depth=2.8,
                   blocks=22, angularity=.88, erosion=.16, bedding=.18, tilt=.20,
                   dark=(.038,.049,.057,1), light=(.32,.34,.33,1)),
    'LIMESTONE': dict(label='Coastal limestone', height=1.8, width=4.4, depth=3.0,
                      blocks=17, angularity=.67, erosion=.30, bedding=.34, tilt=.14,
                      dark=(.19,.165,.115,1), light=(.66,.62,.49,1)),
    'SLATE': dict(label='Fractured slate', height=2.8, width=4.1, depth=2.1,
                  blocks=24, angularity=.96, erosion=.09, bedding=.84, tilt=.42,
                  dark=(.035,.043,.050,1), light=(.26,.30,.31,1)),
    'SANDSTONE': dict(label='Bedded sandstone', height=2.0, width=4.3, depth=2.8,
                      blocks=15, angularity=.78, erosion=.22, bedding=.85, tilt=.13,
                      dark=(.20,.084,.038,1), light=(.69,.40,.19,1)),
    'GRANITE': dict(label='Fractured granite', height=2.0, width=3.7, depth=3.0,
                    blocks=16, angularity=.73, erosion=.19, bedding=.09, tilt=.22,
                    dark=(.105,.098,.090,1), light=(.49,.45,.39,1)),
    'REEF': dict(label='Submerged bedrock', height=1.4, width=4.5, depth=3.0,
                 blocks=20, angularity=.60, erosion=.40, bedding=.38, tilt=.16,
                 dark=(.066,.080,.052,1), light=(.42,.43,.29,1)),
}


def activate(obj):
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply(obj, modifier):
    activate(obj)
    bpy.ops.object.modifier_apply(modifier=modifier.name)


def copy_object(obj, name, collection=None):
    out = obj.copy()
    out.data = obj.data.copy()
    out.name = name
    (collection or bpy.context.collection).objects.link(out)
    out.hide_render = False
    out.hide_viewport = False
    out.hide_set(False)
    return out


def mesh_audit(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    components = 0
    seen = set()
    for v in bm.verts:
        if v.index in seen:
            continue
        components += 1
        todo = [v]
        seen.add(v.index)
        while todo:
            q = todo.pop()
            for e in q.link_edges:
                other = e.other_vert(q)
                if other.index not in seen:
                    seen.add(other.index)
                    todo.append(other)
    areas = [f.calc_area() for f in bm.faces]
    report = {
        'vertices': len(bm.verts), 'edges': len(bm.edges), 'faces': len(bm.faces),
        'quads': sum(len(f.verts) == 4 for f in bm.faces),
        'triangles': sum(len(f.verts)-2 for f in bm.faces),
        'nonmanifold_edges': sum(not e.is_manifold for e in bm.edges),
        'zero_area_faces': sum(a < 1e-12 for a in areas),
        'loose_vertices': sum(not v.link_faces for v in bm.verts),
        'components': components,
        'signed_volume': bm.calc_volume(signed=True),
        'euler_characteristic': len(bm.verts)-len(bm.edges)+len(bm.faces),
    }
    bm.free()
    uv = obj.data.uv_layers.active
    report['uv_layer'] = uv.name if uv else None
    if uv:
        report['uv_in_0_1'] = all(-1e-6 <= c <= 1.000001 for p in uv.data for c in p.uv)
    report['structurally_valid'] = bool(report['faces'] and not report['nonmanifold_edges']
        and not report['zero_area_faces'] and not report['loose_vertices']
        and report['signed_volume'] > 0)
    return report


def _orient_outward(obj):
    """Consistent outward winding for the generator's closed surfaces."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def _largest_component(obj):
    """Discard detached voxel debris; keep the connected formation, not a pile."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    todo = set(bm.verts)
    groups = []
    while todo:
        seed = todo.pop()
        group, stack = {seed}, [seed]
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o in todo:
                    todo.remove(o)
                    group.add(o)
                    stack.append(o)
        groups.append(group)
    if len(groups) > 1:
        keep = max(groups, key=len)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(obj.data)
    bm.free()


def _block(rng, center, scale, angularity, tilt, slate=False):
    """Clipped polyhedron with a fractured crown; not a displaced UV sphere."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2)
    for j in range(5):
        n = Vector((rng.choice((-1,1))*rng.uniform(.35,1),
                    rng.choice((-1,1))*rng.uniform(.35,1), rng.uniform(-.15,1)))
        n.normalize()
        distance = rng.uniform(.98,1.30)
        geom = list(bm.verts)+list(bm.edges)+list(bm.faces)
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-6,
            plane_co=n*distance, plane_no=n, clear_outer=True, clear_inner=False)
        boundary = [e for e in bm.edges if e.is_boundary]
        if boundary:
            bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
    crown=Vector((rng.uniform(-.75,.75),rng.uniform(-.6,.6),1.0))
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
        dist=1e-6,plane_co=(0,0,rng.uniform(.45,.8)),plane_no=crown,
        clear_outer=True,clear_inner=False)
    boundary=[e for e in bm.edges if e.is_boundary]
    if boundary:bmesh.ops.holes_fill(bm,edges=boundary,sides=0)
    taper=rng.uniform(.12,.32)
    crown_tilt=rng.uniform(-.15,.25)
    rotation = Euler((rng.uniform(-.17,.17), tilt+rng.uniform(-.11,.11),
                      rng.uniform(-.45,.45)), 'XYZ').to_matrix()
    for v in bm.verts:
        co = v.co.copy()
        co.x *= 1.0 - max(0, co.z)*taper
        co.y *= 1.0 - max(0, co.z)*taper*.65
        co.z += co.x*crown_tilt
        co = rotation @ Vector((co.x*scale[0], co.y*scale[1], co.z*scale[2]))
        v.co = co + Vector(center)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    mesh = bpy.data.meshes.new('RF_JointBlock')
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('RF_JointBlock', mesh)
    bpy.context.collection.objects.link(obj)
    bevel = obj.modifiers.new('Small fracture-edge erosion', 'BEVEL')
    bevel.width = min(scale)*(.025+.13*(1-angularity))
    bevel.segments = 2
    apply(obj, bevel)
    return obj


def generate_high(cfg, name='RockForge', collection=None):
    rng = random.Random(int(cfg['seed']))
    w,d,h = cfg['width'],cfg['depth'],cfg['height']
    count = int(cfg['blocks'])
    angularity = cfg['angularity']
    ridge = cfg.get('formation','MOUND') == 'RIDGE'
    single = cfg.get('formation') == 'BOULDER'
    parts = []
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3,radius=1)
    base=bpy.context.object
    for v in base.data.vertices:
        p=v.co.copy()
        p *= 1+.10*noise.noise(p*4+Vector((cfg['seed']*.01,3,7)))
        v.co=(p.x*w*.48,p.y*d*.46,p.z*h*.16-h*.015)
    base.data.update()
    parts.append(base)
    if single:
        count = 1
    cols = max(1,round(math.sqrt(count*w/d)))
    rows = max(1,math.ceil(count/cols))
    for i in range(count):
        ix,iy = i%cols,i//cols
        nx = ((ix+.5)/cols-.5)*2
        ny = ((iy+.5)/rows-.5)*2
        x = nx*w*.38 + rng.uniform(-.07,.07)*w/cols
        y = ny*d*.37 + rng.uniform(-.13,.13)*d/rows
        envelope = max(.08,1-.83*(nx*nx+.78*ny*ny))
        top = h*(.23+.73*envelope)*rng.uniform(.66,1.28)
        if ridge:
            top *= (.64+.46*(1-abs(ny)))
        sx = w/(cols*2)*rng.uniform(.87,1.22)
        sy = d/(rows*2)*rng.uniform(.86,1.14)
        if cfg['preset'] == 'SLATE':
            sx *= .67
            top *= 1.15
        if single:
            x=y=0
            sx,sy,top=w*.46,d*.46,h
        bottom = -h*.075
        parts.append(_block(rng, (x,y,(bottom+top)*.5), (sx,sy,(top-bottom)*.5),
                             angularity,cfg['tilt'],cfg['preset']=='SLATE'))
    if not single:
        for i in range(max(5,count//3)):
            a = 2*math.pi*i/max(5,count//3)+rng.uniform(-.16,.16)
            sx,sy = w*rng.uniform(.065,.11),d*rng.uniform(.07,.12)
            top = h*rng.uniform(.15,.29)
            parts.append(_block(rng,(math.cos(a)*w*.38, math.sin(a)*d*.36,top*.35),
                (sx,sy,top*.6),angularity,rng.uniform(-.2,.2)))
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.join()
    high = base
    high.name = name+'_HIGH'
    density = int(cfg.get('density',160))
    high.data.remesh_voxel_size = max(w,d,h)/density
    high.data.use_remesh_preserve_volume = True
    activate(high)
    bpy.ops.object.voxel_remesh()
    _largest_component(high)
    _orient_outward(high)
    sm = high.modifiers.new('Weathered joints', 'SMOOTH')
    sm.factor = .55
    sm.iterations = 2+round(cfg['erosion']*4)
    apply(high, sm)
    mesh = high.data
    mesh.update()
    offset = Vector((rng.uniform(5,50),rng.uniform(5,50),rng.uniform(5,50)))
    amp = min(w,d,h)*(.002+.020*cfg['erosion'])
    normals = [v.normal.copy() for v in mesh.vertices]
    for v,n in zip(mesh.vertices,normals):
        p = v.co/max(w,d,h) + offset
        q = noise.noise_vector(p*8.4)
        val = noise.multi_fractal(p*22+q*.32, .85, 2.0, 3)
        v.co += n * amp * (val-.45)
    mesh.update()
    for face in mesh.polygons:
        face.use_smooth = True
    if collection:
        for c in list(high.users_collection): c.objects.unlink(high)
        collection.objects.link(high)
    high['rf_role'] = 'HIGH'
    high['rf_config'] = json.dumps(cfg,sort_keys=True)
    return high


def _retopologize_once(high, target_quads, seed=0, name='RockForge_LOW'):
    """Native QuadriFlow with explicit failure checks; no decimate fallback."""
    low = copy_object(high,name,high.users_collection[0])
    for mod in list(low.modifiers): low.modifiers.remove(mod)
    activate(low)
    try:
        result = bpy.ops.object.quadriflow_remesh(use_mesh_symmetry=False,
            use_preserve_sharp=False, use_preserve_boundary=False,
            mode='FACES', target_faces=int(target_quads), seed=int(seed))
    except RuntimeError:
        bpy.data.objects.remove(low, do_unlink=True)
        raise
    if 'FINISHED' not in result:
        bpy.data.objects.remove(low,do_unlink=True)
        raise RuntimeError('QuadriFlow failed; the high-detail source has been retained.')
    shrink = low.modifiers.new('Project to high-detail surface','SHRINKWRAP')
    shrink.target = high
    shrink.wrap_method = 'NEAREST_SURFACEPOINT'
    shrink.wrap_mode = 'ON_SURFACE'
    apply(low,shrink)
    _orient_outward(low)
    for p in low.data.polygons: p.use_smooth=True
    report = mesh_audit(low)
    if not report['structurally_valid'] or report['quads'] != report['faces']:
        bpy.data.objects.remove(low,do_unlink=True)
        raise RuntimeError('Retopology failed structural/all-quad checks: '+str(report))
    activate(low)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.018,
                            area_weight=.3, correct_aspect=True, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    low.data.uv_layers.active.name = 'RockForgeUV'
    low['rf_role']='LOW'
    low['rf_source']=high.name
    low['rf_audit']=json.dumps(mesh_audit(low),sort_keys=True)
    return low


def retopologize(high, target_quads, seed=0, name='RockForge_LOW'):
    """Retry solver seeds without changing the requested shape or polygon target."""
    expected_components = mesh_audit(high)['components']
    attempts = []
    for attempt in range(4):
        native_seed = int(seed) + 7919 * attempt
        candidate = None
        try:
            candidate = _retopologize_once(high, target_quads, native_seed, name)
            audit = mesh_audit(candidate)
            if audit['components'] != expected_components:
                raise RuntimeError('Retopology changed the connected-component count.')
            candidate['rf_remesh_attempts'] = attempt + 1
            candidate['rf_native_remesh_seed'] = native_seed
            candidate['rf_requested_seed'] = int(seed)
            return candidate
        except RuntimeError as error:
            attempts.append(str(error))
            if candidate is not None and candidate.name in bpy.data.objects:
                bpy.data.objects.remove(candidate, do_unlink=True)
    raise RuntimeError('QuadriFlow failed four validated attempts; the source is retained. '
                       'Increase the quad budget or source resolution. Last error: ' + attempts[-1])
