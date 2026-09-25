"""Nine enlarged roof blades; large side shutters held at the prior open pose."""
import bpy,math
from mathutils import Vector,Matrix
from geometry_v02 import Builder as BaseBody
from roof_revision_v27 import vent_basis,VENT_CENTERS,VENT_Z,remove,tag
from roof_revision_v24 import roof_half_width

COUNTS={0:9,1:4}
MAX_DEGREES=40
FIXED_OPEN_DEGREES=55

def hinges():return [o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('roof27_role')=='louver_hinge']

def apply(b,jw):
    if b.lod==2:return dict(roof_blades=0,side_blades_held_open=0)
    for o in list(bpy.context.scene.objects):
        if o.get('roof26_animation_kind')=='louver' or o.get('roof27_role')=='louver_hinge':remove(o)
    count=COUNTS[b.lod];pitch=.340/count;size=pitch-.005
    for x in VENT_CENTERS:
        for side in (-1,1):
            t,n=vent_basis(side);c=Vector((x,side*roof_half_width(VENT_Z),VENT_Z))
            def p(u,v,d=0):return c+Vector((u,0,0))+t*v+n*d
            for i in range(count):
                v=-.170+pitch*(i+.5);pivot=p(0,v,.005)
                verts=[p(a*.514/2,v+q*size/2,.005+r*.0025/2) for a,q,r in
                    [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
                mat='jw_roof' if jw else ('roof' if p(0,v).z>=4.24 else 'blue')
                o=BaseBody.poly(b,'roof37_louver_leaf',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),
                    (1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,solid=True)
                tag(o,'louver_leaf','vent_aperture')
                o['roof26_animation_kind']='louver';o['roof26_animation_group']=f'louver_{"m" if x<0 else "p"}_{"m" if side<0 else "p"}_{i:02}'
                o['roof26_pivot']=tuple(pivot);o['roof26_axis']=(1,0,0);o['roof26_direction']=side
                o['roof27_mount_normal']=tuple(n);o['roof27_mount_tangent']=tuple(t)
                o['shutter37_height']=size;o['shutter37_count']=count
                for sign in (-1,1):
                    tag(b.cyl('roof37_louver_hinge',p(sign*.274,v,.005),.0035,.040,'spring_steel','X'),'louver_hinge','vent_frame')
    big=0
    for o in bpy.context.scene.objects:
        if o.get('roof26_animation_kind')!='side_louver':continue
        pivot=Vector(o['roof26_pivot']);side=o['roof26_direction']
        o.matrix_world=Matrix.Translation(pivot)@Matrix.Rotation(math.radians(side*FIXED_OPEN_DEGREES),4,'X')@Matrix.Translation(-pivot)@o.matrix_world
        o['shutter37_fixed_degrees']=FIXED_OPEN_DEGREES;big+=1
    b.g.ensure_uvs();bpy.context.view_layer.update()
    return dict(roof_blades=4*count,blades_per_window=count,blade_height_m=size,side_blades_held_open=big,
                roof_max_degrees=MAX_DEGREES,side_fixed_degrees=FIXED_OPEN_DEGREES)
