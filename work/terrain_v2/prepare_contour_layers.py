"""Build generalized 100 m contour slabs from the existing Laos DEM."""
from pathlib import Path
import sys,json,argparse
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'deps'))
import numpy as np
from scipy.ndimage import gaussian_filter
import shapely
from shapely.geometry import shape,Polygon
from shapely.ops import transform
from pyproj import Transformer
import contourpy

parser=argparse.ArgumentParser()
parser.add_argument('--clean',action='store_true')
parser.add_argument('--minimal',action='store_true')
args=parser.parse_args()
sigma_m=18000 if args.minimal else 6000 if args.clean else 1500
simplify_m=700 if args.minimal else 500 if args.clean else 180
min_area=1000e6 if args.minimal else 50e6 if args.clean else 1e6
min_hole=1e30 if args.minimal else 20e6 if args.clean else 0
stem='contour_layers_minimal' if args.minimal else 'contour_layers_clean' if args.clean else 'contour_layers'
levels=[0,100,200,400,600,800,1000,1200,1400] if args.minimal else range(0,2801,100)

data=np.load(ROOT/'dem_mesh.npz')
stride=4
x=data['x_m'][::stride]
y=data['y_m'][::stride][::-1]
z=gaussian_filter(data['elevation_m'][::stride,::stride][::-1].astype(float),sigma_m/600)
center=np.array([(data['x_m'][0]+data['x_m'][-1])/2,(data['y_m'][0]+data['y_m'][-1])/2])
geo=json.loads((ROOT.parent/'laos_adm0.geojson').read_text())
boundary=shapely.union_all([shape(f['geometry']) for f in geo['features']])
project=Transformer.from_crs(4326,32648,always_xy=True)
boundary=transform(project.transform,boundary).simplify(180,preserve_topology=True)
contours=contourpy.contour_generator(x=x,y=y,z=z,fill_type='OuterOffset')
arrays={}
summary=[]
for level in levels:
    if level==0:
        region=boundary
    else:
        points,offsets=contours.filled(level,10000)
        polys=[]
        for p,o in zip(points,offsets):
            rings=[p[a:b] for a,b in zip(o[:-1],o[1:])]
            q=Polygon(rings[0],[] if args.minimal else rings[1:])
            if q.area>min_area:
                polys.append(q)
        if not polys:
            continue
        region=shapely.union_all(polys)
        if args.minimal:
            # Close narrow notches and soften peaks into broad rounded terraces.
            region=region.buffer(4500,quad_segs=8).buffer(-4500,quad_segs=8)
            region=region.buffer(-1800,quad_segs=8).buffer(1800,quad_segs=8)
        region=shapely.intersection(region,boundary)
        region=shapely.make_valid(region.simplify(simplify_m,preserve_topology=True))
    parts=[Polygon(p.exterior,[r for r in p.interiors if Polygon(r).area>min_hole]) for p in shapely.get_parts(region) if p.geom_type=='Polygon' and p.area>min_area]
    if not parts:
        continue
    region=shapely.MultiPolygon(parts)
    triangles=shapely.get_parts(shapely.constrained_delaunay_triangles(region))
    triangle_xy=np.concatenate([shapely.get_coordinates(t)[:3] for t in triangles])
    xy,inv=np.unique(triangle_xy,axis=0,return_inverse=True)
    top=inv.reshape(-1,3)
    a,b,c=xy[top[:,0]],xy[top[:,1]],xy[top[:,2]]
    flip=((b[:,0]-a[:,0])*(c[:,1]-a[:,1])-(b[:,1]-a[:,1])*(c[:,0]-a[:,0]))<0
    top[flip]=top[flip][:,::-1]
    lookup={tuple(v):i for i,v in enumerate(xy)}
    edges=[]
    for p in parts:
        p=shapely.orient_polygons(p)
        for ring in [p.exterior,*p.interiors]:
            coords=np.asarray(ring.coords)
            ids=[lookup[tuple(v)] for v in coords]
            edges.extend(zip(ids[:-1],ids[1:]))
    edges=np.asarray(edges,dtype=np.int32)
    arrays[f'xy_{level}']=((xy-center)*1e-5).astype(np.float32)
    arrays[f'tri_{level}']=top.astype(np.int32)
    arrays[f'edge_{level}']=edges
    summary.append({'level_m':level,'islands':len(parts),'holes':sum(len(p.interiors) for p in parts),'vertices':len(xy),'triangles':len(top)})
    print(summary[-1],flush=True)
np.savez_compressed(ROOT/(stem+'.npz'),**arrays)
pin=np.array(project.transform(102.6331,17.9757))
meta={'layers':summary,'contour_interval_m':200 if args.minimal else 100,'smoothing_sigma_m':sigma_m,'simplification_m':simplify_m,'minimum_island_area_m2':min_area,'minimum_hole_area_m2':min_hole,'all_enclosed_holes_filled':args.minimal,'pin_xy':((pin-center)*1e-5).tolist(),'source':'Existing Laos Mapzen DEM, EPSG:32648; generalized for layered sculpture.'}
(ROOT/(stem+'.json')).write_text(json.dumps(meta,indent=2))
print('CONTOUR_DATA_COMPLETE',flush=True)
