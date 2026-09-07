import bpy, math, os, wave, struct, random, subprocess
from mathutils import Vector
OUT=os.environ.get('RAKE_OUT','/tmp/rake_out'); os.makedirs(OUT,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
# materials
def mat(n,c,rough=.7,emit=0):
 m=bpy.data.materials.new(n); m.diffuse_color=(*c,1); m.use_nodes=True; p=m.node_tree.nodes.get('Principled BSDF'); p.inputs['Base Color'].default_value=(*c,1); p.inputs['Roughness'].default_value=rough
 if emit: p.inputs['Emission Color'].default_value=(*c,1); p.inputs['Emission Strength'].default_value=emit
 return m
skin=mat('Rake wet pallor',(0.22,.235,.22),.88); dark=mat('Rake mouth',(0.012,.006,.006),.9); eye=mat('Eyes',(.75,.78,.68),.2,4); human=mat('Human skin',(.32,.17,.12),.7); shirt=mat('Shirt',(.06,.07,.08),.85); bedmat=mat('Bed',(.11,.12,.13),.9); wall=mat('Wall',(.055,.065,.075),.95); wood=mat('Wood',(.10,.055,.035),.8); moon=mat('Moonlight',(.12,.2,.38),.4,2)
def cube(n,loc,sc,ma,bev=.03):
 bpy.ops.mesh.primitive_cube_add(location=loc); o=bpy.context.object;o.name=n;o.scale=sc; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bev: mod=o.modifiers.new('soft edges','BEVEL');mod.width=bev;mod.segments=2
 o.data.materials.append(ma); return o
def uv(n,loc,sc,ma):
 bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=16, location=loc);o=bpy.context.object;o.name=n;o.scale=sc;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(ma);return o
def limb(n,a,b,r,ma):
 mid=(Vector(a)+Vector(b))/2; d=Vector(b)-Vector(a); bpy.ops.mesh.primitive_cylinder_add(vertices=16,radius=r,depth=d.length,location=mid);o=bpy.context.object;o.name=n;o.data.materials.append(ma);o.rotation_mode='QUATERNION';o.rotation_quaternion=d.to_track_quat('Z','Y');return o
cube('Floor',(0,0,0),(3.2,4.2,.08),wood); cube('BackWall',(0,4.05,1.7),(3.2,.08,1.7),wall); cube('LeftWall',(-3.12,.2,1.7),(.08,3.9,1.7),wall)
cube('Bed',(0,1.15,.55),(1.45,2.15,.38),bedmat,.08); cube('Headboard',(0,3.05,1.25),(1.55,.12,.8),wood,.05); cube('Pillow',(0,2.35,1.03),(1.05,.5,.18),bedmat,.12); cube('Window',(1.9,3.94,2.05),(.72,.04,.85),moon,.01)
humanRoot=bpy.data.objects.new('Human_ROOT',None);bpy.context.collection.objects.link(humanRoot);humanRoot.location=(0,1.25,1.05)
head=uv('Human_head',(0,1.95,1.15),(.28,.32,.3),human); head.parent=humanRoot
body=cube('Human_torso',(0,1.15,1.08),(.42,.68,.18),shirt,.12);body.parent=humanRoot
for side in (-1,1):
 arm=limb('Human_arm',(.3*side,1.45,1.1),(.62*side,.8,1.15),.105,human);arm.parent=humanRoot
R=bpy.data.objects.new('RAKE_ROOT',None);bpy.context.collection.objects.link(R);R.location=(0,-3.0,0);R.scale=(1,1,1)
pel=uv('Rake_pelvis',(0,0,1.0),(.34,.22,.38),skin);pel.parent=R
ch=uv('Rake_chest',(0,0,1.75),(.43,.25,.68),skin);ch.parent=R
neck=limb('Rake_neck',(0,0,2.15),(0,.02,2.38),.14,skin);neck.parent=R
rh=uv('Rake_head',(0,.01,2.58),(.34,.30,.42),skin);rh.parent=R
for s in (-1,1):
 sock=uv('Eye_socket',(.13*s,-.265,2.67),(.11,.045,.075),dark);sock.parent=R
 e=uv('Eye',(.13*s,-.305,2.68),(.035,.025,.025),eye);e.parent=R
mouth=uv('Mouth',(0,-.285,2.48),(.18,.045,.105),dark);mouth.parent=R
jaw=uv('Jaw',(0,-.02,2.39),(.27,.28,.17),skin);jaw.parent=R
for z in [1.5,1.65,1.8,1.95]:
 for s in (-1,1):
  rib=limb('Rib',(.04*s,-.22,z),(.34*s,-.18,z+.03),.035,skin);rib.parent=R
for s in (-1,1):
 upper=limb('Rake_upperarm',(.34*s,0,2.0),(.63*s,-.03,1.35),.11,skin);upper.parent=R
 fore=limb('Rake_forearm',(.63*s,-.03,1.35),(.82*s,-.22,.58),.085,skin);fore.parent=R
 hand=uv('Rake_hand',(.82*s,-.23,.52),(.13,.16,.09),skin);hand.parent=R
 for j in range(4):
  x=.72*s + j*.065*s; finger=limb('Finger',(x,-.28,.5),(x+.05*s,-.46,.32),.022,skin);finger.parent=R
 thigh=limb('Rake_thigh',(.22*s,0,1.0),(.35*s,.02,.48),.13,skin);thigh.parent=R
 shin=limb('Rake_shin',(.35*s,.02,.48),(.48*s,-.18,.12),.095,skin);shin.parent=R
def k(o,f,loc=None,rot=None,scale=None):
 if loc is not None:o.location=loc;o.keyframe_insert('location',frame=f)
 if rot is not None:o.rotation_euler=rot;o.keyframe_insert('rotation_euler',frame=f)
 if scale is not None:o.scale=scale;o.keyframe_insert('scale',frame=f)
k(R,1,(0,-3,0));k(R,145,(0,-2.8,0));k(R,210,(0,-2.0,0));k(R,270,(0,-1.6,0));k(R,330,(0,.0,0));k(R,365,(0,.55,.05),rot=(.12,0,.08));k(R,430,(-.55,1.0,.12),rot=(.35,0,-.35));k(R,485,(.6,.9,.05),rot=(.15,0,.35));k(R,545,(0,-.3,0),rot=(0,0,0));k(R,650,(0,-.8,0));k(R,720,(0,1.2,.35),scale=(1.35,1.35,1.35))
for f,z in [(1,2.39),(230,2.39),(245,2.28),(270,2.39),(335,2.22),(380,2.39),(690,2.2),(720,2.34)]: jaw.location.z=z; jaw.keyframe_insert('location',frame=f)
k(humanRoot,1,(0,0,0));k(humanRoot,220,(0,0,0),rot=(0,0,0));k(humanRoot,285,(0,-.15,.18),rot=(.25,0,0));k(humanRoot,355,(0,-.45,.42),rot=(.65,0,.1));k(humanRoot,430,(.25,-.3,.35),rot=(.4,.2,-.35));k(humanRoot,490,(-.3,-.2,.28),rot=(.5,-.15,.3));k(humanRoot,550,(0,-.35,.2),rot=(.25,0,0));k(humanRoot,720,(0,-.25,.25),rot=(.45,0,0))
bpy.ops.object.camera_add(location=(0,-4.2,2.2));cam=bpy.context.object;cam.name='Phone_Camera';bpy.context.scene.camera=cam
def track(o,pt):o.rotation_euler=(Vector(pt)-o.location).to_track_quat('-Z','Y').to_euler()
for f,loc,pt in [(1,(0,-4.2,2.15),(0,1.0,1.2)),(200,(.1,-3.8,2.0),(0,.5,1.5)),(330,(-.25,-3.2,1.8),(0,.7,1.5)),(430,(.35,-2.8,1.65),(0,1.1,1.5)),(540,(-.3,-3.0,1.75),(0,.5,1.5)),(650,(0,-3.5,1.9),(0,.2,1.6)),(720,(0,-2.5,1.65),(0,1.3,1.8))]:
 cam.location=loc;track(cam,pt);cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
cam.data.lens=34
bpy.ops.object.light_add(type='AREA',location=(1.8,2.8,2.7));L=bpy.context.object;L.data.energy=380;L.data.shape='RECTANGLE';L.data.color=(.22,.38,1);L.data.size=2.0
bpy.ops.object.light_add(type='POINT',location=(-1.6,1.4,1.6));P=bpy.context.object;P.data.energy=110;P.data.color=(1,.25,.08)
sc=bpy.context.scene;sc.frame_start=1;sc.frame_end=720;sc.render.fps=24;sc.render.resolution_x=360;sc.render.resolution_y=640;sc.render.resolution_percentage=100
sc.render.image_settings.file_format='FFMPEG';sc.render.ffmpeg.format='MPEG4';sc.render.ffmpeg.codec='H264';sc.render.ffmpeg.constant_rate_factor='MEDIUM';sc.render.filepath=os.path.join(OUT,'silent.mp4')
sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.image_settings.color_mode='RGB';sc.world=bpy.data.worlds.new('Night World');sc.world.color=(.002,.003,.008)
sc.use_nodes=True; nt=sc.node_tree; nt.nodes.clear(); rl=nt.nodes.new('CompositorNodeRLayers'); glare=nt.nodes.new('CompositorNodeGlare');glare.glare_type='FOG_GLOW';glare.quality='LOW';glare.threshold=.8;comp=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],glare.inputs['Image']);nt.links.new(glare.outputs['Image'],comp.inputs['Image'])
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'Rake_Dont_Answer_It.blend'))
bpy.ops.render.render(animation=True)
sr=48000; dur=30; N=sr*dur; random.seed(8); audio=[0.0]*N
def add_tone(t,d,f,a,noise=0):
 st=int(t*sr);en=min(N,st+int(d*sr))
 for i in range(st,en):
  x=(i-st)/sr; env=min(1,x/.03,max(0,(d-x)/.08)); audio[i]+=a*env*(math.sin(2*math.pi*f*x)+.45*math.sin(2*math.pi*f*1.97*x))+noise*a*(random.random()*2-1)*env
def screech(t,d,a=0.7):
 st=int(t*sr);en=min(N,st+int(d*sr))
 for i in range(st,en):
  x=(i-st)/sr; env=math.sin(math.pi*min(1,x/d))**.45; f=700+1200*(x/d)+140*math.sin(2*math.pi*8*x); audio[i]+=a*env*(.55*math.sin(2*math.pi*f*x)+.25*math.sin(2*math.pi*f*2.13*x)+.2*(random.random()*2-1))
for i in range(N): audio[i]+=.035*math.sin(2*math.pi*47*i/sr)+.012*(random.random()*2-1)
add_tone(8.7,.55,310,.3,.18); add_tone(9.35,.45,390,.25,.15); screech(10.0,1.25,.58); screech(13.6,1.0,.8)
for t in [14.3,15.0,16.1,17.2,18.1,19.3,20.0,21.1,22.0]: add_tone(t,.16,75,.7,.7)
for t in [14.8,16.7,18.8,20.8]: screech(t,.55,.45)
add_tone(23.2,.7,250,.32,.2); screech(28.5,1.4,.95); add_tone(29.6,.35,55,1,.9)
mx=max(max(audio),-min(audio),1); audio=[max(-1,min(1,x/(mx*1.05))) for x in audio]
wav=os.path.join(OUT,'sound.wav')
with wave.open(wav,'w') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes(b''.join(struct.pack('<h',int(x*32767)) for x in audio))
final=os.path.join(OUT,'Rake_Dont_Answer_It_30s.mp4'); subprocess.run(['ffmpeg','-y','-i',sc.render.filepath,'-i',wav,'-c:v','copy','-c:a','aac','-b:a','192k','-shortest',final],check=True)
for f in [240,350,450,700]:
 sc.frame_set(f);sc.render.image_settings.file_format='PNG';sc.render.filepath=os.path.join(OUT,f'preview_{f}.png');bpy.ops.render.render(write_still=True)
print('DONE',final)