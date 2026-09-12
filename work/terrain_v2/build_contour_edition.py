"""Apply the supplied tutorial's layered sculpture style to the Laos outline."""
import bpy,json,numpy as np,sys,argparse
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parents[1]/'outputs'
scene=bpy.context.scene
parser=argparse.ArgumentParser()
parser.add_argument('--clean',action='store_true')
parser.add_argument('--minimal',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
input_stem='contour_layers_minimal' if args.minimal else 'contour_layers_clean' if args.clean else 'contour_layers'
output_stem='laos_relief_contour_minimal' if args.minimal else 'laos_relief_contour_clean' if args.clean else 'laos_relief_contour'
meta=json.loads((ROOT/(input_stem+'.json')).read_text())
data=np.load(ROOT/(input_stem+'.npz'))
for name in ['LAOS | continuous real elevation surface','Vertical national-outline edge']:
    obj=bpy.data.objects.get(name)
    if obj:
        mesh=obj.data
        bpy.data.objects.remove(obj,do_unlink=True)
        if mesh.users==0: bpy.data.meshes.remove(mesh)
for obj in list(scene.objects):
    if obj.type=='LIGHT': bpy.data.objects.remove(obj,do_unlink=True)

with bpy.data.libraries.load('C:/Users/mikasaloli/Downloads/TOPOtutorial_End.blend',link=False) as (src,dst):
    dst.materials=['land','water',"pin'"]
    dst.worlds=src.worlds
    dst.objects=['Circle']
world=next(w for w in dst.worlds if w and w.use_nodes and any(n.type=='TEX_SKY' for n in w.node_tree.nodes))
scene.world=world
world.name='Tutorial atmosphere | sun and sky'
white=next(m for m in dst.materials if m.name=='land')
white.name='Tutorial pearl contour layers'
water=next(m for m in dst.materials if m.name=='water')
water.name='Tutorial turquoise resin'
pin=dst.objects[0]
scene.collection.objects.link(pin)
pin.name='Vientiane | tutorial red location pin'
pin.dimensions=(.19,.28,.024)
pin.location=(*meta['pin_xy'],.208)
pin['Location']='Vientiane city, approximately 17.9757 N, 102.6331 E'

def rgba(h):
    vals=[int(h[i:i+2],16)/255 for i in (0,2,4)]
    return tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in vals)+(1,)
def mat(name,color):
    m=bpy.data.materials.new(name)
    m.use_nodes=True
    n=m.node_tree.nodes['Principled BSDF']
    n.inputs['Base Color'].default_value=rgba(color)
    n.inputs['Roughness'].default_value=.28
    return m
base=mat('Deep lagoon coloured base','007b9b')
cyan=mat('Turquoise contour foundation','00b4c3')
resin=water.copy()
resin.name='Turquoise resin | decorative lowland layer'
resin.node_tree.nodes['Principled BSDF'].inputs['Transmission Weight'].default_value=.35
resin.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.18

collection=bpy.data.collections.new('LAOS | 100 metre stacked contour sculpture')
scene.collection.children.link(collection)
previous_level=0
for info in meta['layers']:
    level=info['level_m']
    xy=data[f'xy_{level}'];tri=data[f'tri_{level}'];edges=data[f'edge_{level}'];n=len(xy)
    upper=.095+level*.0004
    lower=.006 if level==0 else .095+previous_level*.0004-.001
    previous_level=level
    verts=np.empty((n*2,3),np.float32)
    verts[:n,:2]=xy;verts[n:,:2]=xy
    verts[:n,2]=upper;verts[n:,2]=lower
    # Ring orientation keeps exterior and hole wall normals consistent.
    walls=np.column_stack([edges[:,0],edges[:,0]+n,edges[:,1]+n,edges[:,1]])
    faces=[tuple(t) for t in tri]+[tuple(t[::-1]+n) for t in tri]+[tuple(t) for t in walls]
    mesh=bpy.data.meshes.new(f'Contour slab {level:04d} m')
    mesh.from_pydata(verts,[],faces)
    mesh.update()
    obj=bpy.data.objects.new(mesh.name,mesh)
    collection.objects.link(obj)
    mesh.materials.append(base if level==0 else cyan if level==100 else resin if level==200 else white)
    bevel=obj.modifiers.new('Fine cut edge','BEVEL')
    bevel.width=.004 if args.minimal else .0012;bevel.segments=3 if args.minimal else 2
    bevel.limit_method='ANGLE'
    obj['contour_elevation_m']=level
    obj['style']=f"Generalized DEM, {meta['smoothing_sigma_m']/1000:g} km smoothing; 40x vertical scale"
    print('BUILT_LAYER',level,len(verts),flush=True)

# Seat the source pin above the actual terrace at its map coordinate.
point=np.array(meta['pin_xy'])
surface=.095
for info in meta['layers']:
    level=info['level_m']
    t=data[f'xy_{level}'][data[f'tri_{level}']]
    signs=[]
    for k in range(3):
        a=t[:,k];b=t[:,(k+1)%3]
        signs.append((b[:,0]-a[:,0])*(point[1]-a[:,1])-(b[:,1]-a[:,1])*(point[0]-a[:,0]))
    if np.any(np.all(np.stack(signs)>=-1e-9,axis=0)):
        surface=.095+level*.0004
bpy.context.view_layer.update()
box=[pin.matrix_world@Vector(v) for v in pin.bound_box]
pin.location.z+=surface+.018-min(v.z for v in box)
print('PIN_SURFACE',surface,flush=True)

ground=bpy.data.objects['Matte studio ground']
ground.data.materials[0].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.95,.95,.95,1)
ground.is_shadow_catcher=False
scene.render.film_transparent=False
scene.view_settings.view_transform='Filmic'
scene.view_settings.look='Very High Contrast'
scene.view_settings.exposure=0
cam=scene.camera
cam.location=(0,-7,22)
cam.rotation_euler=(Vector((0,-.4,.08))-cam.location).to_track_quat('-Z','Y').to_euler()
cam.data.ortho_scale=11.65

lao=bpy.data.objects['Lao country title']
lao.data.font=bpy.data.fonts.load('C:/Users/mikasaloli/AppData/Local/Microsoft/Windows/Fonts/Phetsarath-Regular.ttf')
for obj in scene.objects:
    if obj.type=='FONT': obj.visible_shadow=False
caption=bpy.data.objects['Legend caption']
caption.data.body='STACKED CONTOURS / 100 METRE INTERVALS'
if args.minimal: caption.data.body='SCULPTED CONTOURS / SIMPLIFIED TERRAIN'
caption.data.size=.098
# Replace the continuous gradient legend with a discrete layer legend.
bar=bpy.data.objects['Continuous elevation scale 0 to 3000 metres']
bar.hide_render=True
bar.hide_viewport=True
for obj in list(scene.objects):
    if obj.name.startswith('Legend ') and obj.name!='Legend caption':
        obj.hide_render=True;obj.hide_viewport=True
for i,(color,body) in enumerate([(base,'0 m'),(cyan,'100 m'),(resin,'200 m'),(white,'400 m +' if args.minimal else '300 m +')]):
    bpy.ops.mesh.primitive_cube_add(size=1,location=(-3.73+i*.85,-5.42,.015))
    swatch=bpy.context.object
    swatch.name=f'Layer legend swatch | {body}'
    swatch.dimensions=(.28,.07,.016)
    swatch.data.materials.append(color)
    curve=bpy.data.curves.new(f'Layer legend {body}','FONT')
    curve.body=body;curve.size=.095
    curve.materials.append(bpy.data.materials['Typography | blue charcoal'])
    text=bpy.data.objects.new(curve.name,curve)
    scene.collection.objects.link(text)
    text.location=(-3.56+i*.85,-5.45,.01)
    text.visible_shadow=False
curve=bpy.data.curves.new('Contour style note','FONT')
curve.body='GENERALIZED RELIEF / TURQUOISE RESIN BASE / PIN: VIENTIANE'
curve.size=.078
curve.materials.append(bpy.data.materials['Typography | blue charcoal'])
note=bpy.data.objects.new(curve.name,curve);scene.collection.objects.link(note)
note.location=(-3.9,-5.73,.01);note.visible_shadow=False
scene['Design']='Laos stacked contour sculpture inspired by supplied TOPOtutorial_End.blend. Pearl terraces, turquoise decorative resin foundation, red Vientiane pin, imported atmospheric sun and sky.'
scene['Terrain generalization']=json.dumps({k:v for k,v in meta.items() if k not in ['layers','pin_xy']})
scene['Resin note']='Turquoise foundation is a decorative material treatment, not a depiction of water or flooding.'
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='HIP';prefs.refresh_devices()
for d in prefs.devices: d.use=d.type=='HIP'
scene.cycles.device='GPU'
scene.cycles.samples=512
scene.render.filepath=str(OUT/(output_stem+'_8k.png'))
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/(output_stem+'_8k.blend')),compress=True)
scene.render.resolution_x=1676;scene.render.resolution_y=2048
scene.cycles.samples=96;scene.cycles.adaptive_min_samples=16;scene.cycles.adaptive_threshold=.02
scene.render.image_settings.color_depth='8'
scene.render.filepath=str(OUT/(output_stem+'_preview.png'))
bpy.ops.render.render(write_still=True)
print('CONTOUR_PREVIEW_COMPLETE',flush=True)
