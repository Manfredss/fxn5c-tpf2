"""Independent red FXN5C 0001 prototype head, photo-fitted, not OEM CAD.

Four brow lamps, wider true front corner facets, more upright twin glazing and
vertically stacked corner lamps distinguish it from the production cab. Source
photos establish appearance only; the fixed directional lamp policy is a game
configuration, not a claim about the prototype's electrical wiring.
"""
import math,json
import bpy
from mathutils import Vector,Matrix
from geometry_v02 import Builder as BaseBody
from geometry_v04 import rounded_rect
from geometry_v06 import chamfer_polygon
from roof_revision_v24 import roof_half_width,upper_front_x
from roof_revision_v40 import _clip_box
from front_details_v10 import circle

FRONT_HALF=1.25
CORNER_SETBACK=.55
LOWER_CORNER_SETBACK=.035
TOP_LAMPS=(-.45,-.15,.15,.45)
TOP_Z=4.43
LOWER_Y=1.395
LOWER_Z=(2.025,2.325)
FRONT_GLASS_Y=(.065,1.15)
FRONT_GLASS_Z=(2.76,3.96)
OLD_PREFIX=('angular_glazing_reveal','angular_windscreen_bead','angular_windscreen_gasket',
    'angular_windshield_surround','straight_centre_mullion','mullion_metal_bead','distant_windows',
    'flush_upper_lamp_gasket','upper_lamp_cavity_back','concave_upper_reflector','upper_reflector_retainer',
    'upper_inner_optic','shared_lamp_cover','lower_lamp_back','lower_lamp_bezel','lower_reflector',
    'lower_bezel_screw','aux_optic_annulus','aux_optic_radial','compact_lamp_skin_return',
    'inboard_folded_skin','outboard_oblique_joint','brow_horizontal_joint','brow_vent_',
    'roof24_full_height_brow','light24_','headlights_','taillights_')
RESEAT_PREFIX=('parked_wiper','wiper_drive','wiper_pull','wiper_service','surround_recessed_screw',
    'front_sun_visor','sunblind_roller','nose_fuxing','railway_emblem','livery21_nose_number',
    'nose_grab','grab_mount','front_finish_v11_mount_bolt','nose_grey_belt','cab_hazard')
SIDE_PREFIX=('side_cab_window_frame','side_cab_window_rubber','side_window_pull','side_window_slider_track')


def front_x(z):
    if z<=2.55:return 11.04
    if z<=4.02:return 11.04-(z-2.55)*.24/1.47
    return 10.80-(z-4.02)*.36/.685


def front_half(z):return FRONT_HALF


def corner_setback(z):
    """Shallow nose lamp plane, widening continuously into the upper cheek."""
    t=max(0,min(1,(z-2.55)/(3.95-2.55)))
    return LOWER_CORNER_SETBACK+(CORNER_SETBACK-LOWER_CORNER_SETBACK)*t


def lower_y(z):return 1.355 if z<2.15 else 1.420


def point(end,y,z,depth=0):
    """Body-global attachment point. Positive depth is outward longitudinally.

    Upper outer |Y|>1.25 follows a real .55-m-setback corner facet. The low
    lamp panel has a shallow front-facing cheek, as the prototype photograph
    shows thin flush optics, not production-type projecting lamp barrels.
    """
    t=max(0,min(1,(abs(y)-FRONT_HALF)/(.40)))
    shoulder=max(0,min(1,(4.24-z)/(.24)))if z>4.0 else 1.
    q=max(0,min(1,(z-2.55)/(3.95-2.55)))
    # Two real triangular folded facets, not a bilinear curved patch. This
    # formula is the barycentric interpolation along the explicit 0--2 seam.
    setback=LOWER_CORNER_SETBACK*t+(CORNER_SETBACK-LOWER_CORNER_SETBACK)*min(t,q)
    return(end*(front_x(z)-setback*shoulder+depth),y,z)


def points(o):return[o.matrix_world@v.co for v in o.data.vertices]


def _tag(o,role):
    o['prototype41_head_role']=role;o['prototype41_dimensions']='photo-fitted estimates';return o


def _glass(b,name,loop,mapper,axis,material='glass_transparent'):
    o=b.glass(name,loop,mapper,axis,material);o.name='glazing_proto41_'+name
    return _tag(o,'transparent_pane')


def _front_loop(side,expand=0):
    a,c=FRONT_GLASS_Y;lo,hi=FRONT_GLASS_Z
    return[(side*y,z)for y,z in chamfer_polygon([(a-expand,lo-expand),(c+expand,lo-expand),
        (c+expand,hi+expand),(a-expand,hi+expand)],.013)]


def _slab(b,name,verts,shift,mat,role):
    surface=[(0,1,2),(0,2,3)]if len(verts)==4 else[tuple(range(len(verts)))]
    if b.lod==2:
        return _tag(BaseBody.poly(b,name,verts,surface,mat,normal=shift),role)
    n=len(verts);allverts=verts+[tuple(Vector(p)-Vector(shift))for p in verts]
    fs=surface+[tuple(i+n for i in f)[::-1]for f in surface]+[(i,(i+1)%n,(i+1)%n+n,i+n)for i in range(n)]
    return _tag(BaseBody.poly(b,name,allverts,fs,mat,solid=True),role)


def _remove_old(report):
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        remove=o.name.startswith(OLD_PREFIX)
        # All existing transparent front/side/lamp panes belong to the cab;
        # register fresh panes consistently for all three LODs below.
        if o.name.startswith('glazing_') and not o.name.startswith('glazing_proto41_'):remove=True
        if remove:report['removed'].append(o.name);bpy.data.objects.remove(o,do_unlink=True)


def _reseat_existing(report):
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        if o.name.startswith(RESEAT_PREFIX):
            inv=o.matrix_world.inverted()
            for v in o.data.vertices:
                p=o.matrix_world@v.co;end=1 if p.x>0 else-1
                depth=abs(p.x)-BaseBody.front_x(p.z)
                v.co=inv@Vector(point(end,p.y,p.z,depth))
            o.data.update();o.data.normals_split_custom_set([(0,0,0)]*len(o.data.loops))
            _tag(o,'front_detail_reseated');report['reseated'].append(o.name)
        elif o.name.startswith(SIDE_PREFIX):
            p=sum(points(o),Vector())/len(o.data.vertices)
            o.location.x-=.25 if p.x>0 else-.25
            _tag(o,'side_window_reseated')


def _brow_width(z):
    rows=((3.95,1.65),(4.28,1.34),(4.705,.74))
    for(a,y),(c,v)in zip(rows,rows[1:]):
        if z<=c:return y+(v-y)*(z-a)/(c-a)
    return .74


def _canopy():
    for o in bpy.context.scene.objects:
        if o.type!='MESH'or not o.name.startswith('roof24_front_folded_canopy'):continue
        inv=o.matrix_world.inverted()
        for v in o.data.vertices:
            p=o.matrix_world@v.co;end=1 if p.x>0 else-1
            old_x=upper_front_x(p.z);w=max(0,min(1,(abs(p.x)-9.18)/(old_x-9.18)))
            target_y=p.y*_brow_width(p.z)/roof_half_width(p.z)
            p.y+=(target_y-p.y)*w
            target_x=abs(point(end,p.y,p.z)[0])
            p.x=end*(abs(p.x)+(target_x-old_x)*w)
            v.co=inv@p
        o.data.update();o.data.normals_split_custom_set([(0,0,0)]*len(o.data.loops));_tag(o,'wider_folded_canopy')


def _shoulder_connection(b,end):
    # The replaced side shell ends at X9.0; the retained canopy begins at
    # X9.18. Only this lower folded shoulder was missing. Above Z4.28 the
    # existing equipment hood already supplies the surface: do not overlap it.
    for side in(-1,1):
        for lo,hi,mat in((3.95,4.24,'blue'),(4.24,4.28,'roof')):
            verts=[(end*x,side*roof_half_width(z),z)for x,z in
                   ((9.0,lo),(9.18,lo),(9.18,hi),(9.0,hi))]
            _slab(b,'proto41_head_shoulder_connection',verts,(0,side*.013,.012),mat,'closed_canopy_rear_shoulder')


def _shell(b,end,report):
    shell=bpy.data.objects['body_open_shell_v07']
    xa,xb=sorted((end*9.0,end*11.9))
    _clip_box(shell,((xa,xb),(-1.9,1.9),(1.580001,4.9)))
    _shoulder_connection(b,end)
    plates=[]
    for lo,hi in((1.58,2.55),(2.55,3.95),(3.95,4.02)):
        mat='graphite'if lo>=2.55 else'blue'
        plate=_slab(b,'proto41_head_front_skin',[point(end,y,z)for y,z in((-FRONT_HALF,lo),(FRONT_HALF,lo),(FRONT_HALF,hi),(-FRONT_HALF,hi))],(end*.028,0,0),mat,'main_front_skin')
        plates.append(plate)
        for side in(-1,1):
            if lo>=3.95:continue
            corner=[point(end,side*y,z)for y,z in((FRONT_HALF,lo),(1.65,lo),(1.65,hi),(FRONT_HALF,hi))]
            _slab(b,'proto41_head_wide_corner',corner,(end*.020,side*.014,0),'blue','wide_corner_facet')
    # Side skins meet the same physical corner vertices as the front facets.
    sides=[]
    for side in(-1,1):
        vs=[(end*9.0,side*1.65,1.58),point(end,side*1.65,1.58),
            point(end,side*1.65,2.55),point(end,side*1.65,3.95),
            (end*9.0,side*1.65,3.95)]
        o=_slab(b,'proto41_head_side_skin',vs,(0,side*.026,0),'blue','side_cab_skin');sides.append((side,o))
    if b.lod<2:
        for side in(-1,1):
            for plate in plates:
                cutter=b.sheet('proto41_window_cutter',_front_loop(side,.004),lambda y,z:point(end,y,z,.15),'black',.36,(end,0,0))
                b.cut(plate,cutter)
    # The upper brow has genuine apertures for the lamp cover and horn cages.
    yz=[(-1.25,4.02),(-1.34,4.28),(-.74,4.705),(.74,4.705),(1.34,4.28),(1.25,4.02)]
    brow=_slab(b,'proto41_head_brow',[(end*front_x(z),y,z)for y,z in yz],(end*.026,0,0),'graphite','wide_four_lamp_brow')
    for side in(-1,1):
        # Explicit triangles connect side eave, wide corner, upright window
        # panel and planar brow. No non-planar n-gon spans the old joint.
        wing=[point(end,side*1.65,3.95),point(end,side*1.25,3.95),
              point(end,side*1.25,4.02),(end*front_x(4.28),side*1.34,4.28)]
        for ids in((0,1,2),(0,2,3)):
            _slab(b,'proto41_head_brow_wing',[wing[i]for i in ids],(end*.024,side*.006,0),'blue','closed_brow_corner_transition')
    for side in(-1,1):
        if b.lod<2:
            cutter=b.sheet('proto41_glass_brow_cutter',_front_loop(side,.004),lambda y,z:point(end,y,z,.15),'black',.36,(end,0,0));b.cut(brow,cutter)
    for side,sideplate in sides:
        for which in('front','rear'):
            loop=_side_loop(end,which)
            if b.lod<2:
                cutter=b.sheet('proto41_side_cutter',_side_loop(end,which,.005),lambda x,z:(x,side*1.8,z),'black',.35,(0,side,0));b.cut(sideplate,cutter)
                _glass(b,f'side_{end}_{side}_{which}',loop,lambda x,z:(x,side*1.657,z),(0,side,0))
            else:
                x0,x1=(9.76,10.13)if which=='front'else(9.064,9.566)
                loop=[(end*x,z)for x,z in((x0,3.09),(x1,3.09),(x1-(.095 if which=='front'else 0),3.72),(x0,3.72))]
                _tag(b.sheet('proto41_side_window_proxy',loop,lambda x,z:(x,side*1.657,z),'graphite',axis=(0,side,0)),'side_window_proxy')
    report['new_shells'].extend(o.name for o in plates)
    return brow


def _side_loop(end,which,expand=0):
    if which=='front':
        pts=chamfer_polygon([(9.76-expand,3.09-expand),(10.13+expand,3.09-expand),
            (10.035+expand,3.72+expand),(9.76-expand,3.72+expand)],.045)
    else:pts=rounded_rect(9.315,3.405,.502+2*expand,.632+2*expand,.065,n=4)
    return[(end*x,z)for x,z in pts]


def _windows(b,end):
    # Side window frames were old fitted loops; replace with the exact new
    # loops so the more upright front-side pane cannot separate from its hole.
    for side in(-1,1):
        mapper=lambda y,z:point(end,y,z,.014)
        if b.lod<2:
            b.rim('proto41_windscreen_reveal',_front_loop(side,.035),_front_loop(side,-.001),mapper,'black',.08,(end,0,0))
            b.rim('proto41_windscreen_rubber',_front_loop(side,.024),_front_loop(side,.003),lambda y,z:point(end,y,z,.033),'graphite',.018,(end,0,0))
            _glass(b,f'front_{end}_{side}',_front_loop(side),lambda y,z:point(end,y,z,.012),(end,0,0))
        else:
            a,c=FRONT_GLASS_Y;lo,hi=FRONT_GLASS_Z
            _tag(b.sheet('proto41_front_window_proxy',[(side*a,lo),(side*c,lo),(side*c,hi),(side*a,hi)],mapper,'graphite',axis=(end,0,0)),'front_window_proxy')
        for which in('front','rear'):
            if b.lod==2:continue
            b.rim('proto41_side_window_frame',_side_loop(end,which,.033),_side_loop(end,which,.001),
                lambda x,z:(x,side*1.675,z),'metal',.027,(0,side,0))
            b.rim('proto41_side_window_rubber',_side_loop(end,which,.020),_side_loop(end,which,-.002),
                lambda x,z:(x,side*1.678,z),'black',.018,(0,side,0))


def _upper_loop(expand=0):
    return chamfer_polygon([(-.60-expand,4.235-expand),(.60+expand,4.235-expand),
        (.71+expand,4.645+expand),(-.71-expand,4.645+expand)],.014)


def _horn_loop(side,inner=False):
    pts=[(.738,4.257),(1.242,4.257),(.790,4.578)]if inner else[(.720,4.240),(1.270,4.240),(.776,4.610)]
    return[(side*y,z)for y,z in chamfer_polygon(pts,.012)]


def _horns(b,end,brow):
    # Reuse the already hollow v39 bells and their attached drivers. Only
    # their rigid orientation/location changes; do not copy FXN3B horn sizes.
    old_axis=Vector((end,0,.38/.46)).normalized();new_axis=Vector((end,0,.36/.685)).normalized()
    rot=old_axis.rotation_difference(new_axis).to_matrix().to_4x4()
    for side in(-1,1):
        if b.lod==2:
            b.sheet('proto41_horn_cover_proxy',_horn_loop(side),lambda y,z:point(end,y,z,.010),'graphite',axis=(end,0,0));continue
        cutter=b.sheet('proto41_horn_cutter',_horn_loop(side,True),lambda y,z:point(end,y,z,.10),'black',.35,(end,0,0));b.cut(brow,cutter)
        b.rim('proto41_horn_cover_frame',_horn_loop(side),_horn_loop(side,True),lambda y,z:point(end,y,z,.014),'graphite',.055,(end,0,0))
        # Triangular horizontal guards are an open cover, not a solid vent.
        tri=_horn_loop(side,True)
        for j in range(12 if b.lod==0 else 7):
            z=4.270+j*.025 if b.lod==0 else 4.275+j*.042
            hits=[]
            for p,q in zip(tri,tri[1:]+tri[:1]):
                if min(p[1],q[1])<=z<=max(p[1],q[1])and abs(p[1]-q[1])>1e-9:
                    hits.append(p[0]+(q[0]-p[0])*(z-p[1])/(q[1]-p[1]))
            if len(hits)<2:continue
            a,c=min(hits),max(hits)
            b.sheet('proto41_horn_cover_bar',[(a-.003,z-.003),(c+.003,z-.003),(c+.003,z+.003),(a-.003,z+.003)],lambda y,z:point(end,y,z,.016),'graphite',.012,(end,0,0))
        old_center=Vector((end*(upper_front_x(4.370)-.016),side*.566,4.370))
        target=Vector(point(end,side*.885,4.395,-.016));tf=Matrix.Translation(target)@rot@Matrix.Translation(-old_center)
        for o in list(bpy.context.scene.objects):
            if o.name.startswith('horn39_')and o.get('horn39_end')==end and o.get('horn39_side')==side:
                if o.name.startswith(('horn39_cover','horn39_cavity')):
                    bpy.data.objects.remove(o,do_unlink=True)
                else:o.matrix_world=tf@o.matrix_world;_tag(o,'reused_hollow_horn')
        b.sheet('proto41_horn_cavity_back',_horn_loop(side),lambda y,z:point(end,y,z,-.146),'graphite',.010,(end,0,0))
        b.rim('proto41_horn_recess_wall',_horn_loop(side),_horn_loop(side,True),lambda y,z:point(end,y,z,-.010),'graphite',.137,(end,0,0))


def _lower_mapper(end,side,z,depth):
    # Optical axes remain longitudinal; the shallow adapter varies in depth
    # to attach to the oblique front-corner panel without skewing the lens.
    center=Vector(point(end,side*lower_y(z),z,.012))
    return lambda u,v:(center.x+end*depth,center.y+u,center.z+v)


def _lamps(b,end,brow):
    n=32 if b.lod==0 else 16 if b.lod==1 else 8
    if b.lod<2:
        cutter=b.sheet('proto41_top_light_cutter',_upper_loop(),lambda y,z:point(end,y,z,.15),'black',.45,(end,0,0));b.cut(brow,cutter)
        b.rim('proto41_top_light_cowl',_upper_loop(.036),_upper_loop(),lambda y,z:point(end,y,z,.016),'blue',.17,(end,0,0))
        b.sheet('proto41_top_light_back',_upper_loop(),lambda y,z:point(end,y,z,-.16),'grille_black',.01,(end,0,0))
        _glass(b,f'top_cover_{end}',_upper_loop(),lambda y,z:point(end,y,z,.006),(end,0,0),'lamp_glass')
    else:
        b.sheet('proto41_top_light_cowl_proxy',_upper_loop(.02),lambda y,z:point(end,y,z,.012),'graphite',axis=(end,0,0))
    for y in TOP_LAMPS:
        if b.lod==2:
            b.sheet('proto41_top_lens_proxy',circle(.078,n),lambda u,v:point(end,y+u,TOP_Z+v,.017),'metal',axis=(end,0,0))
            continue
        for radius,depth in((.090,-.028),(.055,-.095)):
            if b.lod==2 and radius<.08:continue
            b.rim('proto41_upper_reflector',circle(radius,n),circle(radius-.009,n),lambda u,v:point(end,y+u,TOP_Z+v,depth),'metal',.018,(end,0,0))
        if b.lod<2:
            # Real concave bowl behind the clear common cover.
            rings=((.034,-.108),(.055,-.087),(.078,-.049),(.090,-.025))
            verts=[point(end,y+u,TOP_Z+v,d)for r,d in rings for u,v in circle(r,n)]
            fs=[(j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i)for j in range(3)for i in range(n)]
            o=b.poly('proto41_upper_reflector_bowl',verts,fs,'metal',normal=(end,0,0))
            for f in o.data.polygons:f.use_smooth=True
        else:b.sheet('proto41_top_lens_proxy',circle(.078,n),lambda u,v:point(end,y+u,TOP_Z+v,.017),'metal',axis=(end,0,0))
    for side in(-1,1):
        yz=[(side*1.215,1.875),(side*1.510,1.875),(side*1.610,2.485),(side*1.305,2.485)]
        panel=b.sheet('proto41_vertical_lamp_panel',yz,lambda y,z:point(end,y,z,.003),'graphite',.012 if b.lod<2 else 0,(end,0,0))
        for z in LOWER_Z:
            cy=side*lower_y(z)
            if b.lod==2:
                verts=[point(end,cy+u,z+v,.014)for rr in(.112,.085)for u,v in circle(rr,n)]
                b.poly('proto41_lower_lamp_far_rim',verts,[(i,(i+1)%n,n+(i+1)%n,n+i)for i in range(n)],'metal',normal=(end,0,0))
                b.sheet('proto41_lower_lamp_far_lens',circle(.085,n),lambda u,v:point(end,cy+u,z+v,.015),'metal',axis=(end,0,0))
                continue
            # True longitudinal bores expose the complete circular optic from
            # the front; the broad angled corner cannot mask its inner half.
            targets=[panel]+[o for o in bpy.context.scene.objects if o.name.startswith('proto41_head_wide_corner')and
                sum(p.x for p in points(o))*end>0 and min(p.z for p in points(o))<z<max(p.z for p in points(o))]
            for target in targets:
                cutter=b.sheet('proto41_corner_lamp_cutter',circle(.114,n),
                    lambda u,v:(end*11.25,cy+u,z+v),'black',.85,(end,0,0))
                b.cut(target,cutter)
            mapper=_lower_mapper(end,side,z,0)
            # Finite-thickness ANNULAR return, not a capped tapered cylinder:
            # the oblique rear disk of a cylinder would cross the longitudinal
            # lens plane and mask its inboard half even after cutting the shell.
            verts=[mapper(u,v)for u,v in circle(.112,n)]
            verts += [mapper(u,v)for u,v in circle(.103,n)]
            verts += [point(end,cy+u,z+v,-.008)for u,v in circle(.114,n)]
            verts += [point(end,cy+u,z+v,-.008)for u,v in circle(.105,n)]
            fs=[]
            for i in range(n):
                j=(i+1)%n
                fs += [(i,j,n+j,n+i),(i,2*n+i,2*n+j,j),
                       (n+i,n+j,3*n+j,3*n+i),(2*n+i,3*n+i,3*n+j,2*n+j)]
            b.poly('proto41_lower_lamp_adapter',verts,fs,'graphite',solid=True)
            b.rim('proto41_lower_lamp_bezel',circle(.112,n),circle(.087,n),_lower_mapper(end,side,z,.007),'metal',.008,(end,0,0))
            b.sheet('proto41_lower_lamp_reflector',circle(.085,n),_lower_mapper(end,side,z,.001),'metal',axis=(end,0,0))
            if b.lod<2:_glass(b,f'lower_{end}_{side}_{z}',circle(.085,n),_lower_mapper(end,side,z,.009),(end,0,0),'lamp_glass')


def _emitters(b):
    import light_revision_v24 as lights
    lights.register_source_materials(b.g)
    result={}
    if b.lod==2:return result
    for direction,end in(('fwd',1),('bwd',-1)):
        made=[];optics=[];n=24 if b.lod==0 else 12
        specs=[('top',end,y,TOP_Z,'white')for y in TOP_LAMPS]
        specs += [('lower',end,side*lower_y(z),z,'white')for side in(-1,1)for z in LOWER_Z]
        specs += [('tail_upper',-end,side*lower_y(LOWER_Z[1]),LOWER_Z[1],'red')for side in(-1,1)]
        for kind,e,y,z,color in specs:
            mapper=(lambda u,v,e=e,y=y,z=z:point(e,y+u,z+v,-.102))if kind=='top'else _lower_mapper(e,1 if y>0 else-1,z,.005)
            radius=.034 if kind=='top'else .066
            made.append(b.sheet('proto41_light_disc',circle(radius,n),mapper,'lamp_moon_v24'if color=='white'else'lamp_red',axis=(e,0,0)))
            optics.append(dict(kind=kind,end=e,y=y,z=z,color=color,radius=radius,center=list(mapper(0,0))))
        o=b.g.join_objects(made,'light24_'+direction)
        o['light24_emitter']=True;o['light24_direction']=direction;o['light24_number']='0001'
        o['light24_optics_json']=json.dumps(optics);o.hide_render=direction=='bwd'
        result[direction]=dict(name=o.name,optics=optics,policy='fixed game policy: leading 8 white, trailing upper pair red; not verified wiring')
    return result


def apply(b):
    assert not bpy.context.scene.get('prototype41_head_applied')
    report=dict(lod=b.lod,removed=[],reseated=[],new_shells=[],head_front_x=((2.55,11.04),(4.02,10.80),(4.705,10.44)),
        head_front_half=FRONT_HALF,corner_setback=CORNER_SETBACK,lower_corner_setback=LOWER_CORNER_SETBACK,front_glass_y=FRONT_GLASS_Y,front_glass_z=FRONT_GLASS_Z,
        lower_lamp_z=LOWER_Z,lower_lamp_y=[lower_y(z)for z in LOWER_Z],upper_lamp_y=TOP_LAMPS,upper_lamp_z=TOP_Z,
        estimates='Visual fit to three supplied 0001 photographs, not factory drawings')
    _remove_old(report);_reseat_existing(report);_canopy()
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(('side_cab_window_frame','side_cab_window_rubber')):bpy.data.objects.remove(o,do_unlink=True)
    for end in(-1,1):
        brow=_shell(b,end,report);_windows(b,end);_horns(b,end,brow);_lamps(b,end,brow)
    report['lights']=_emitters(b)
    b.g.ensure_uvs();bpy.context.view_layer.update()
    report['glass_objects']=[o.name for o in bpy.context.scene.objects if o.type=='MESH'and o.get('transparent_pane')]
    bpy.context.scene['prototype41_head_applied']=True
    return report
