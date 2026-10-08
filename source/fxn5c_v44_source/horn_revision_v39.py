"""FXN5C covered horns, replacing the former decorative triangular vents.

The supplied frontal photograph and the user's identification establish a
horizontal-bar triangular cover, with a horn behind each cover.  Mouth, throat,
rear pressure chamber and brackets are deliberately modest visual estimates,
not OEM dimensions; no FXN3B long/short-horn arrangement is imported.

Only the two brow sheets and their four old covers are changed. Lamp geometry,
lighting domains, cab interior, windows, and the far-LOD proxy stay untouched.
"""
import math
import bpy
from mathutils import Vector
from geometry_v06 import chamfer_polygon
from roof_revision_v24 import upper_front_x

OLD_PREFIX=('brow_vent_recess_v08','brow_vent_flush_rim_v08',
            'brow_recessed_flat_slat_v08')
SELECT_PREFIX=OLD_PREFIX+('roof24_full_height_brow','horn39_')
MOUTH_RADIUS=.076
HORN_Y=.566
HORN_Z=4.370
BAR_COUNT=14


def selected_objects():
    return [o for o in bpy.context.scene.objects if o.type=='MESH' and
            o.name.startswith(SELECT_PREFIX)]


def _tag(o,role,end,side):
    o['horn39_role']=role;o['horn39_end']=end;o['horn39_side']=side
    o['horn39_dimensions']='photo-fitted approximate; no OEM section available'
    return o


def _outline(side,inner=False):
    points=[(.487,4.121),(1.095,4.121),(.521,4.365)] if inner else [(.47,4.105),(1.15,4.105),(.51,4.390)]
    return [(side*y*.90,z+.14) for y,z in chamfer_polygon(points,.012 if inner else .022)]


def _point(end,y,z,d=0):
    return (end*(upper_front_x(z)+d),y,z)


def _lathe(b,end,side,role,profile):
    """Closed finite-thickness flared wall, with an uncapped circular mouth.

    Its axis is normal to the inclined cover.  Each ring is a true circle in
    that plane, rather than a circle sheared to follow the sloping body sheet.
    """
    n=24 if b.lod==0 else 16
    axis=Vector((end,0,.38/.46)).normalized()
    up=Vector((-end*.38/.46,0,1)).normalized()
    sideways=Vector((0,1,0))
    center=Vector(_point(end,side*HORN_Y,HORN_Z,-.016))
    verts=[]
    for d,r in profile:
        for i in range(n):
            a=i*math.tau/n
            verts.append(tuple(center+axis*d+(sideways*math.cos(a)+up*math.sin(a))*r))
    faces=[]
    for j in range(len(profile)):
        nxt=(j+1)%len(profile)
        for i in range(n):
            k=(i+1)%n
            faces.append((j*n+i,j*n+k,nxt*n+k,nxt*n+i))
    o=_tag(b.poly('horn39_'+role,verts,faces,'exhaust_steel',solid=True),role,end,side)
    o['horn39_axis']=tuple(axis);o['horn39_mouth_center']=tuple(center)
    for f in o.data.polygons:f.use_smooth=True
    return o


def _cylinder(b,end,side,role,d0,d1,r,material):
    axis=Vector((end,0,.38/.46)).normalized()
    center=Vector(_point(end,side*HORN_Y,HORN_Z,-.016))
    return _tag(b.rod('horn39_'+role,center+axis*d0,center+axis*d1,r,material),role,end,side)


def _bar_bounds(loop,z):
    hits=[]
    for p,q in zip(loop,loop[1:]+loop[:1]):
        if min(p[1],q[1])-1e-8<=z<=max(p[1],q[1])+1e-8 and abs(q[1]-p[1])>1e-9:
            hits.append(p[0]+(q[0]-p[0])*(z-p[1])/(q[1]-p[1]))
    assert len(hits)>=2,(z,loop)
    return min(hits),max(hits)


def _cover(b,end,side,jw):
    outer,inner=_outline(side),_outline(side,True)
    paint='jw_roof' if jw else 'roof'
    front=lambda y,z:_point(end,y,z,.014)
    frame=_tag(b.rim('horn39_cover_frame',outer,inner,front,paint,.058,(end,0,0)),
               'triangular_cover_frame',end,side)
    # The long return has a real inside wall and joins the mounted backplate;
    # it does not put a black surface immediately across the horn mouth.
    n=len(inner);center_y=sum(y for y,z in inner)/n;center_z=sum(z for y,z in inner)/n
    outer_liner=[(center_y+(y-center_y)*1.030,center_z+(z-center_z)*1.030)for y,z in inner]
    liner=_tag(b.rim('horn39_cavity_return',outer_liner,inner,
        lambda y,z:_point(end,y,z,-.010),'graphite',.135,(end,0,0)),
        'recess_wall',end,side)
    back=_tag(b.sheet('horn39_cavity_back',outer_liner,
        lambda y,z:_point(end,y,z,-.146),'graphite',.006,(end,0,0)),
        'mounted_rear_bulkhead',end,side)
    frame['horn39_real_aperture']=True
    # 14 finite rectangular horizontal bars, not 20 overlapping single faces.
    # Both ends bury 1.5 mm in the frame. Bars are intentionally not animated.
    for j in range(BAR_COUNT):
        z=4.269+j*.0164;h=.0062
        lo,hi=_bar_bounds(inner,z+h/2)
        if hi-lo<.032:continue
        yz=[(lo-.0015,z-h/2),(hi+.0015,z-h/2),(hi+.0015,z+h/2),(lo-.0015,z+h/2)]
        bar=_tag(b.sheet('horn39_cover_bar',yz,lambda y,z:_point(end,y,z,.016),
            paint,.012,(end,0,0)),'horizontal_guard_bar',end,side)
    # A shallow flare sits entirely behind the cover. Its throat remains open
    # until the small rear driver recess, never a dark disk at the bell mouth.
    profile=[(-.065,.025),(-.051,.028),(-.036,.039),(-.016,.061),(0,MOUTH_RADIUS),
             (0,MOUTH_RADIUS-.004),(-.016,.057),(-.036,.035),(-.051,.024),(-.065,.021)]
    horn=_lathe(b,end,side,'hollow_flared_horn',profile)
    horn['horn39_inner_radius']=MOUTH_RADIUS-.004;horn['horn39_internal_depth']=.065
    _lathe(b,end,side,'rolled_mouth_edge',[(.002,MOUTH_RADIUS+.001),(.002,MOUTH_RADIUS-.004),
                                        (-.004,MOUTH_RADIUS-.004),(-.004,MOUTH_RADIUS+.001)])
    _lathe(b,end,side,'hollow_throat',[(-.078,.026),(-.061,.026),(-.061,.021),(-.078,.021)])
    _cylinder(b,end,side,'rear_pressure_chamber',-.096,-.076,.038,'graphite')
    _cylinder(b,end,side,'deep_driver_opening',-.077,-.075,.020,'black')
    # Mount below the pressure chamber, attached to the back wall.  This is an
    # approximate support, not a claimed construction drawing of this unit.
    cy=side*HORN_Y
    mount=_tag(b.sheet('horn39_mount_backplate',[(cy-.043,4.258),(cy+.043,4.258),
        (cy+.043,4.308),(cy-.043,4.308)],lambda y,z:_point(end,y,z,-.143),
        'exhaust_steel',.009,(end,0,0)),'attached_mount_backplate',end,side)
    _tag(b.box('horn39_mount_foot',_point(end,cy,4.272,-.103),(.086,.068,.022),
               'exhaust_steel'),'attached_support_foot',end,side)
    _tag(b.box('horn39_mount_pedestal',_point(end,cy,4.288,-.105),(.048,.048,.024),
               'exhaust_steel'),'driver_pedestal',end,side)
    if b.lod==0:
        # Corner screws stay within the frame and are absent at mid distance.
        for y,z in [(side*.445,4.261),(side*.964,4.260),(side*.465,4.493)]:
            _tag(b.cyl('horn39_cover_fastener',_point(end,y,z,.018),.005,.007,
                'exhaust_steel','X'),'cover_fastener',end,side)
    return {'end':end,'side':side,'guard_bars':BAR_COUNT,
            'mouth_radius_m':MOUTH_RADIUS,'inner_depth_m':.065,
            'cavity_back_horizontal_setback_m':.146}


def apply(builder,jw=False):
    if builder.lod>=2:
        return {'far_proxy_preserved':True,'covers':[],'removed_objects':[]}
    assert not any(o.name.startswith('horn39_')for o in bpy.context.scene.objects),'Apply only to clean v38 baseline'
    removed=[]
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(OLD_PREFIX):
            removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True)
    brows=[o for o in bpy.context.scene.objects if o.name.startswith('roof24_full_height_brow')]
    assert len(brows)==2,len(brows)
    covers=[]
    for brow in brows:
        end=int(brow['roof24_end'])
        for side in (-1,1):
            # A true hole behind the cover, restricted to the old opening
            # footprint. The centre lamp cut-out and its nodes are untouched.
            cutter=builder.sheet('horn39_aperture_cutter',_outline(side,True),
                lambda y,z,e=end:_point(e,y,z,.20),'black',.60,(end,0,0))
            builder.cut(brow,cutter)
            covers.append(_cover(builder,end,side,jw))
        brow['horn39_apertures']=2
        for f in brow.data.polygons:f.use_smooth=False
    return {'far_proxy_preserved':False,'covers':covers,'removed_objects':removed,
            'lamp_geometry_unchanged':True,'cab_interior_unchanged':True,
            'dimension_status':'visual estimates; not OEM horn model or surveyed dimensions'}
