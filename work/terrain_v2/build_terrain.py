"""Physically based Laos relief; isolated Blender background build."""
import argparse
import gc
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent.parent / 'outputs'
p = argparse.ArgumentParser()
p.add_argument('--stage', choices=['proof', 'final'], default='proof')
p.add_argument('--style', choices=['blue', 'green-paper'], default='blue')
args = p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
FINAL = args.stage == 'final'
SCALE = 1e-5  # one scene unit = 100 km
EXAG = 14.0
BASE = 0.028
STOPS = [(0,'eef3f3'), (150,'dfecef'), (350,'b5d2df'), (650,'78a9c5'),
         (1000,'4483ad'), (1600,'245b87'), (2200,'153e65'), (3000,'102c4a')]
if args.style == 'green-paper':
    BASE = .052
    STOPS = [(0,'4b7845'), (150,'688f50'), (350,'82a25c'), (650,'a7b86d'),
             (1000,'c9c47f'), (1600,'dfb57a'), (2200,'cd8b67'), (3000,'fff0cc')]

def log(s):
    print('LAOS: ' + s, flush=True)

def rgba(h):
    v = [int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in v)+(1,)

def solid(name, color, rough=.8):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba(color)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = rgba(color)
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Specular IOR Level'].default_value = .2
    return mat

def color_ramp(nodes):
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.interpolation = 'LINEAR'
    for i,(height,color) in enumerate(STOPS):
        el = ramp.color_ramp.elements[i] if i < 2 else ramp.color_ramp.elements.new(height/3000)
        el.position = height/3000
        el.color = rgba(color)
    return ramp

def mesh_arrays(name, vertices, faces, material, smooth=True):
    mesh = bpy.data.meshes.new(name)
    mesh.vertices.add(len(vertices))
    mesh.vertices.foreach_set('co', np.asarray(vertices,dtype=np.float32).ravel())
    mesh.loops.add(faces.size)
    mesh.loops.foreach_set('vertex_index', np.asarray(faces,dtype=np.int32).ravel())
    mesh.polygons.add(len(faces))
    mesh.polygons.foreach_set('loop_start', np.arange(len(faces),dtype=np.int32)*4)
    mesh.polygons.foreach_set('loop_total', np.full(len(faces),4,dtype=np.int32))
    mesh.polygons.foreach_set('use_smooth', np.full(len(faces),smooth,dtype=bool))
    mesh.update(calc_edges=True)
    obj = bpy.data.objects.new(name,mesh)
    bpy.context.collection.objects.link(obj)
    mesh.materials.append(material)
    return obj

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
pref = bpy.context.preferences.addons['cycles'].preferences
pref.compute_device_type = 'HIP'
pref.refresh_devices()
for dev in pref.devices:
    dev.use = dev.type == 'HIP'
scene.cycles.device = 'GPU'
scene.cycles.samples = 1024 if FINAL else 128
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = .005 if FINAL else .02
scene.cycles.adaptive_min_samples = 64 if FINAL else 16
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.use_auto_tile = True
scene.cycles.tile_size = 1024
scene.cycles.max_bounces = 8
scene.cycles.diffuse_bounces = 4
scene.cycles.glossy_bounces = 4
scene.render.resolution_x = 6284 if FINAL else 1676
scene.render.resolution_y = 7680 if FINAL else 2048
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.render.image_settings.color_depth = '16'
scene.render.image_settings.compression = 30
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.render.film_transparent = False
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.78,.85,1,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .3

mat = solid('Elevation | metres, white lowlands to blue summits', '78a9c5')
nt = mat.node_tree
geo = nt.nodes.new('ShaderNodeNewGeometry')
sep = nt.nodes.new('ShaderNodeSeparateXYZ')
remap = nt.nodes.new('ShaderNodeMapRange')
remap.inputs['From Min'].default_value = BASE
remap.inputs['From Max'].default_value = BASE + 3000*SCALE*EXAG
remap.clamp = True
ramp = color_ramp(nt.nodes)
nt.links.new(geo.outputs['Position'],sep.inputs[0])
nt.links.new(sep.outputs['Z'],remap.inputs['Value'])
nt.links.new(remap.outputs['Result'],ramp.inputs[0])
nt.links.new(ramp.outputs['Color'],nt.nodes['Principled BSDF'].inputs['Base Color'])

log('Loading projected DEM')
data = np.load(ROOT/'dem_mesh.npz')
stride = 1 if FINAL else 2
e = data['elevation_m'][::stride,::stride].copy()
m = data['mask'][::stride,::stride].copy()
x = data['x_m'][::stride]
y = data['y_m'][::stride]
cx,cy = (x[0]+x[-1])/2,(y[0]+y[-1])/2
rows,cols = np.nonzero(m)
verts = np.empty((len(rows),3),np.float32)
verts[:,0]=(x[cols]-cx)*SCALE
verts[:,1]=(y[rows]-cy)*SCALE
verts[:,2]=BASE+e[rows,cols]*SCALE*EXAG
ids = np.full(m.shape,-1,np.int32)
ids[rows,cols]=np.arange(len(rows),dtype=np.int32)
q = m[:-1,:-1]&m[1:,:-1]&m[1:,1:]&m[:-1,1:]
r,c = np.nonzero(q)
faces = np.column_stack((ids[r,c],ids[r+1,c],ids[r+1,c+1],ids[r,c+1])).astype(np.int32)
log(f'Top surface {len(verts):,} vertices; {len(faces):,} quads; {150*stride} m grid')
terrain = mesh_arrays('LAOS | continuous real elevation surface', verts, faces, mat)
terrain['source_grid_metres'] = 150*stride
terrain['vertical_exaggeration'] = EXAG
terrain['projection'] = 'EPSG:32648'
terrain['height_color'] = 'Geometry Z converted linearly to elevation; stops in metres'
# Explicit vertical perimeter. No solidify or normal-directed offset.
boundaries=[]
for shift,edge in [((-1,0),(3,0)),((1,0),(1,2)),((0,-1),(0,1)),((0,1),(2,3))]:
    rr,cc=r+shift[0],c+shift[1]
    valid=(rr>=0)&(rr<q.shape[0])&(cc>=0)&(cc<q.shape[1])
    neighbour=np.zeros(len(r),bool)
    neighbour[valid]=q[rr[valid],cc[valid]]
    boundaries.append(faces[~neighbour][:,edge])
edges=np.concatenate(boundaries)
wallv=np.empty((len(edges)*4,3),np.float32)
wallv[0::4]=verts[edges[:,1]]
wallv[1::4]=verts[edges[:,0]]
wallv[2::4]=verts[edges[:,0]]
wallv[3::4]=verts[edges[:,1]]
wallv[2::4,2]=.004
wallv[3::4,2]=.004
mesh_arrays('Vertical national-outline edge',wallv,np.arange(len(wallv),dtype=np.int32).reshape(-1,4),mat,False)
del data,e,m,x,y,rows,cols,ids,q,r,c,faces,verts,boundaries,edges,wallv,rr,cc,valid,neighbour
gc.collect()
log('Terrain geometry complete')

ground=solid('Warm porcelain backdrop','e5e7e5')
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.name='Matte studio ground'
bpy.context.object.data.materials.append(ground)

ink=solid('Typography | blue charcoal','344b5a')
ink.node_tree.nodes.clear()
text_output=ink.node_tree.nodes.new('ShaderNodeOutputMaterial')
text_emission=ink.node_tree.nodes.new('ShaderNodeEmission')
text_emission.inputs['Color'].default_value=rgba('344b5a')
ink.node_tree.links.new(text_emission.outputs[0],text_output.inputs['Surface'])
english=bpy.data.fonts.load('C:/Windows/Fonts/segoeui.ttf')
lao=bpy.data.fonts.load('C:/Windows/Fonts/LeelawUI.ttf')
def label(name,body,x,y,size,font=english):
    curve=bpy.data.curves.new(name,'FONT')
    curve.body=body
    curve.font=font
    curve.size=size
    curve.space_character=1.05
    obj=bpy.data.objects.new(name,curve)
    bpy.context.collection.objects.link(obj)
    obj.location=(x,y,.008)
    curve.materials.append(ink)
    return obj
label('Country title',"LAO PEOPLE’S DEMOCRATIC REPUBLIC",-3.9,-4.48,.255)
label('Lao country title','ສາທາລະນະລັດ ປະຊາທິປະໄຕ ປະຊາຊົນລາວ',-3.9,-4.86,.225,lao)
label('Legend caption','ELEVATION  /  METRES',-3.9,-5.22,.11)
bar=solid('Continuous elevation legend','ffffff')
nt=bar.node_tree
tex=nt.nodes.new('ShaderNodeTexCoord')
sep=nt.nodes.new('ShaderNodeSeparateXYZ')
ramp=color_ramp(nt.nodes)
nt.links.new(tex.outputs['Generated'],sep.inputs[0])
nt.links.new(sep.outputs['X'],ramp.inputs[0])
nt.links.new(ramp.outputs[0],nt.nodes['Principled BSDF'].inputs['Base Color'])
bpy.ops.mesh.primitive_cube_add(size=1,location=(-2.275,-5.40,.008))
bpy.context.object.name='Continuous elevation scale 0 to 3000 metres'
bpy.context.object.dimensions=(3.25,.052,.006)
bpy.context.object.data.materials.append(bar)
for height in [0,500,1000,1500,2000,2500,3000]:
    obj=label('Legend '+str(height),f'{height:,}',-3.9+3.25*height/3000,-5.57,.1)
    obj.data.align_x='CENTER'

def aim(obj,target):
    obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
light=bpy.data.lights.new('Large northwest softbox','AREA')
light.energy=1800
light.shape='DISK'
light.size=5
obj=bpy.data.objects.new(light.name,light)
bpy.context.collection.objects.link(obj)
obj.location=(-5,4,9)
aim(obj,(0,0,0))
sun=bpy.data.lights.new('Northwest raking relief light','SUN')
sun.energy=2.0
sun.angle=.09
obj=bpy.data.objects.new(sun.name,sun)
bpy.context.collection.objects.link(obj)
obj.location=(-6,5,8)
aim(obj,(0,0,0))
cam=bpy.data.cameras.new('Near-overhead orthographic portrait')
obj=bpy.data.objects.new(cam.name,cam)
bpy.context.collection.objects.link(obj)
obj.location=(0,-2.7,22)
aim(obj,(0,-.35,0))
cam.type='ORTHO'
cam.ortho_scale=11.45
cam.lens=50
cam.clip_end=300
scene.camera=obj
scene['DEM provenance']=json.loads((ROOT/'dem_metadata.json').read_text())['source']
scene['Design']='Elevation-based blue relief. True projected XY; 14x vertical exaggeration.'
scene['Sources']='Mapzen Terrain Tiles / geoBoundaries gbOpen LAO ADM0'
if args.style == 'green-paper':
    sys.path.insert(0,str(ROOT))
    import green_paper
    green_paper.apply(scene, rgba, solid, aim)
stem = 'laos_relief_green_paper_8k' if args.style == 'green-paper' else 'laos_relief_rebuilt_8k'
if FINAL:
    scene.render.filepath=str(OUT/(stem+'.png'))
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(stem+'.blend')),compress=True)
else:
    scene.render.filepath=str(ROOT/('proof_green_paper.png' if args.style == 'green-paper' else 'proof.png'))
log('Rendering '+args.stage)
bpy.ops.render.render(write_still=True)
log('FINISHED '+scene.render.filepath)
