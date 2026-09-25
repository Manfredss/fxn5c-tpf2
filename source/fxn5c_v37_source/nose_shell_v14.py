"""Continuous lower nose topology with shallow lamp lands and upper return.

Control points are estimates constrained by the 0060 and 0051 photographs.
The sloping boundary above the lamps is part of the shell, not a stuck-on disc
or a radially deformed boolean mesh. Window-zone coordinates are retained.
"""
import bpy
from mathutils import Vector
from geometry_v07 import SilhouetteBuilder
from geometry_v06 import front_loop
from cab_details_v14 import side_window_loop

# The windshield-side land is ONE plane, not a triangulated bilinear surface.
# v14 uses a shallower photo-fit to avoid an oversized blue outer-lamp barrel.
# Lengths are photographic estimates; side glazing remains on y=+/-1.65.
CORNER_SLOPE = .30
LAMP_FOLD_Z = 2.285


def front_half(z):
    if z <= LAMP_FOLD_Z:
        return 1.30+.18*max(0,min(1,(z-1.58)/(LAMP_FOLD_Z-1.58)))
    if z <= 2.55: return 1.48
    return SilhouetteBuilder.front_half(z)


def ring(z, special=False):
    x=SilhouetteBuilder.front_x(z)
    if z<=2.55:
        y=front_half(z); cy=1.65
        corner_x=x-CORNER_SLOPE*(cy-y)
    elif z<=3.95:
        y=SilhouetteBuilder.front_half(z); cy=1.65
        corner_x=x-CORNER_SLOPE*(cy-y)
    else:
        y=SilhouetteBuilder.front_half(z)
        cy=1.65-(z-3.95)*.53/.53
        # Same explicit plane up to the brow break, then a separate flat roof
        # shoulder. No inward notch at the intermediate 4.02 m ring.
        corner_x=x-CORNER_SLOPE*(cy-y)
    sy=1.65-max(0,z-3.95)*.50/.53
    cz=2.38 if special else z
    return [(x,-y,z),(x,y,z),(corner_x,cy,cz),(9.4,sy,cz),
            (-9.4,sy,cz),(-corner_x,cy,cz),(-x,y,z),(-x,-y,z),
            (-corner_x,-cy,cz),(-9.4,-sy,cz),(9.4,-sy,cz),(corner_x,-cy,cz)]


RINGS=[ring(z) for z in (1.58,LAMP_FOLD_Z,2.55,3.95,4.02,4.48)]
VERTS=[p for r in RINGS for p in r]
FACES=[]
for k in range(len(RINGS)-1):
    for j in range(12):
        a=k*12+j; b=k*12+(j+1)%12; c=(k+1)*12+(j+1)%12; d=(k+1)*12+j
        FACES.extend(((a,b,d),(b,c,d)) if abs(VERTS[a][0])<abs(VERTS[b][0])-1e-8 else ((a,b,c),(a,c,d)))


def _intersection(u,v,first,second,target,faces=FACES,return_face=False):
    for face in faces:
        p,q,r=[VERTS[i] for i in face]
        if min(p[0],q[0],r[0])<9.39 or min(p[1],q[1],r[1])<0: continue
        d=(q[first]-p[first])*(r[second]-p[second])-(r[first]-p[first])*(q[second]-p[second])
        if abs(d)<1e-9: continue
        a=((u-p[first])*(r[second]-p[second])-(r[first]-p[first])*(v-p[second]))/d
        b=((q[first]-p[first])*(v-p[second])-(u-p[first])*(q[second]-p[second]))/d
        if min(a,b,1-a-b)>=-1e-7:
            value=p[target]+a*(q[target]-p[target])+b*(r[target]-p[target])
            return (value,face) if return_face else value
    return None


def corner_x(y,z):
    # A forward-facing outer lamp can just straddle the facet/front boundary.
    # Its circular bore and return must follow BOTH lands without extrapolation.
    if abs(y)<=front_half(z): return SilhouetteBuilder.front_x(z)
    value=_intersection(abs(y),z,1,2,0)
    if value is None: raise ValueError(('Outside nose corner',y,z))
    return value


def side_y(x,z):
    if abs(x)<=9.4: return 1.65-max(0,z-3.95)*.50/.53
    value=_intersection(abs(x),z,0,2,1)
    return value if value is not None else SilhouetteBuilder.side_y(x,z)


def corner_point(end,side,z,fraction):
    outer=1.65 if z<=3.95 else 1.65-(z-3.95)
    y=front_half(z)+(outer-front_half(z))*fraction
    return Vector((end*corner_x(y,z),side*y,z))


def corner_normal(end,side,z,fraction):
    point=corner_point(1,1,z,fraction)
    _,face=_intersection(point.y,z,1,2,0,return_face=True)
    p,q,r=[Vector(VERTS[i]) for i in face]
    n=(q-p).cross(r-p).normalized()
    normal=Vector((end*n.x,side*n.y,n.z))
    if normal.dot(Vector((end,side,0)))<0: normal.negate()
    return normal


def hull(b):
    faces=FACES+[tuple(range(11,-1,-1)),tuple(range(len(VERTS)-12,len(VERTS)))]
    shell=b.poly('body_open_shell_v07',VERTS,faces,'blue',solid=True)
    if b.lod==2: return
    inner=shell.copy(); inner.data=shell.data.copy(); bpy.context.collection.objects.link(inner)
    for v in inner.data.vertices:
        v.co.x*=.993; v.co.y*=.947; v.co.z=3.03+(v.co.z-3.03)*.945
    b.cut(shell,inner)
    for end in (-1,1):
        for side in (-1,1):
            b.cut(shell,b.sheet('front_aperture_cutter_v12',front_loop(side,.004),
                lambda u,v:(end*(b.front_x(v)+.35),u,v),'black',.70,(end,0,0)))
            for which in ('front','rear'):
                b.cut(shell,b.sheet('side_aperture_cutter_v12',side_window_loop(end,which,.004),
                    lambda u,v:(u,side*(b.side_y(u,v)+.35),v),'black',.70,(0,side,0)))
    b.bevel(shell,.004,2 if b.lod==0 else 1)
    # A flat manufactured face must also retain a flat shading normal. Weighted
    # vertex normals across a wide obtuse corner gave the old sheet a hollow look.
    for face in shell.data.polygons:
        face.use_smooth=False
    shell['detail_v07_component']='faceted_aperture_shell'
    shell['detail_v12_component']='integrated_shallow_nose_shell'
    shell['detail_v13_component']='planar_cab_chamfer_shell'


def belt(b):
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(('nose_lower_grey','nose_grey_belt_v10','nose_grey_belt_v12')): bpy.data.objects.remove(o,do_unlink=True)
    for end in (-1,1):
        b.poly('nose_grey_belt_v12',[(end*11.046,y,z) for y,z in [(-front_half(1.58),1.58),(front_half(1.58),1.58),(front_half(1.78),1.78),(-front_half(1.78),1.78)]],
               [(0,1,2,3)],'dark',normal=(end,0,0))
        for side in (-1,1):
            pts=[]
            for z in (1.58,1.78):
                for y in (front_half(z),(front_half(z)+1.65)/2,1.65):
                    pts.append((end*(corner_x(y,z)+.005),side*y,z))
            faces=[f for f in [(0,1,4),(0,4,3),(1,2,5),(1,5,4)]
                   if (Vector(pts[f[1]])-Vector(pts[f[0]])).cross(Vector(pts[f[2]])-Vector(pts[f[0]])).length>1e-9]
            b.poly('nose_grey_belt_v12',pts,faces,'dark',normal=(end,side,0))
