"""Cab-derived two-fold roof, conformal guards and genuinely recessed shutters.

Dimensions and animation timing are exterior reconstruction/display estimates.
The visible guard contour does not determine the independent horizontal rotor
shaft. Run once on the editable v26 scene. All four near-cab apertures are cut
through the painted shell; a dark rectangle is not treated as an opening.
"""
import math
import bpy
import bmesh
from mathutils import Vector
from roof_revision_v24 import _edit, _clip_mesh, roof_half_width
from roof_revision_v25 import old_width, influence
from roof_cab_v26 import width as previous_width

EAVE,KNEE,TOP=3.95,4.28,4.65
X0,X1=2.10,3.60
FAN_SHIFT=.66
VENT_CENTERS=(-7.75,7.60)
VENT_Z=4.115
VENT_HALF_X,VENT_HALF_T=.28,.185

def points(o):return [o.matrix_world@v.co for v in o.data.vertices]

def tag(o,role,host='body_shell'):
    o['roof27_role']=role;o['roof27_host']=host
    return o

def remove(o):bpy.data.objects.remove(o,do_unlink=True)

def map_section(p):
    p=Vector(p)
    if p.z<=EAVE or abs(p.x)>=8.10:return p
    z=min(p.z,TOP)
    p.y*=roof_half_width(z)/previous_width(abs(p.x),z)
    return p

def section(b,jw,report):
    # The cab face at |x| >= 9.18 is deliberately untouched, as are its lamps,
    # panes, AC assembly and cabin. Rigid fan parts are handled separately.
    skip=('bounds|','glazing_','light24_','cab_interior','roof20_', 'roof26_',
          'cab_aircon_','cab_roof_well_floor','ac_','roof_ac_conduit',
          'recessed_fan_shroud','radiator_fan_hub','concealed_fan_blade')
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or o.name.startswith(skip):continue
        ps=points(o)
        if not ps or max(p.z for p in ps)<=EAVE or min(abs(p.x) for p in ps)>=8.10:continue
        if o.name.startswith('shoulder_vent') and abs(sum(p.x for p in ps)/len(ps))>7:
            remove(o);continue
        # Insert the fold before projection, otherwise a long polygon bridges
        # the two slopes and silently restores the original single plane.
        if o.name.startswith(('body_open_shell','trapezoid_roof_deck','cab26_level_equipment_hood',
                              'roof24_distant','roof25_radiator','roof25_panel_joint')):
            _clip_mesh(o,[lambda p:p[2]-KNEE],roof_only=True)
        _edit(o,map_section,'v27_cab_section_reference')
        if o.name.startswith('body_open_shell'):
            # v25 additionally projected this one object during the cab blend,
            # so its old shape was NOT the same mapping used by equipment.
            # Explicitly seat its exterior sheet on the common target planes.
            tf=o.matrix_world;inv=tf.inverted()
            for f in o.data.polygons:
                vs=[tf@o.data.vertices[i].co for i in f.vertices]
                c=sum(vs,Vector())/len(vs);n=tf.to_3x3()@f.normal
                if not(EAVE<c.z<4.65 and abs(c.x)<9.18 and
                       abs(n.x)<.8 and n.y*c.y>.3 and n.z>.2):continue
                for i,p in zip(f.vertices,vs):
                    if p.z>EAVE-1e-6 and abs(p.y)>.99:
                        p.y=(1 if p.y>0 else -1)*roof_half_width(p.z)
                        o.data.vertices[i].co=inv@p
            o.data.update()
        tag(o,'aligned_roof_section')
        report['section_objects'].append(o.name)

def guard(b,jw):
    paint='jw_roof' if jw else 'roof'
    profile=[(-roof_half_width(z),z) for z in (EAVE,KNEE,TOP)]
    profile += [(roof_half_width(z),z) for z in (TOP,KNEE,EAVE)]
    for x in (X0,X1):
        tag(b.poly('roof27_fan_bay_end',[(x,y,z) for y,z in profile],
            [tuple(range(6))],paint,normal=(-1 if x==X0 else 1,0,0)),'fan_bay_end')
    tag(b.poly('roof27_fan_crown',[(x,y,TOP) for x,y in
        ((X0,-roof_half_width(TOP)),(X1,-roof_half_width(TOP)),
         (X1,roof_half_width(TOP)),(X0,roof_half_width(TOP)))],[(0,1,2,3)],
        paint,normal=(0,0,1)),'fan_crown')
    for side in (-1,1):
        p=lambda x,z,d=0:(x,side*(roof_half_width(z)+d),z)
        if b.lod==2:
            for za,zb in ((EAVE,KNEE),(KNEE,TOP)):
                tag(b.poly('roof27_distant_guard',[p(X0,za),p(X1,za),p(X1,zb),p(X0,zb)],
                    [(0,1,2,3)],'grille_black',normal=(0,side,1)),'distant_guard')
            continue
        for x in (X0+.015,2.85,X1-.015):
            tag(b.tube('roof27_guard_rib',[p(x,z,.010) for z in (EAVE+.01,KNEE,TOP)],
                .016,paint,sides=4),'contour_rib','fan_bay_end')
        for z in (EAVE+.01,TOP):
            tag(b.tube('roof27_guard_edge',[p(X0,z,.010),p(X1,z,.010)],.012,paint,sides=4),
                'guard_edge','fan_bay_end')
        for i in range(17 if b.lod==0 else 10):
            z=EAVE+.035+(TOP-EAVE-.06)*i/(16 if b.lod==0 else 9)
            tag(b.tube('roof27_guard_h',[p(X0+.028,z,.006),p(X1-.028,z,.006)],
                .0035,'spring_steel',sides=4),'guard_grid','contour_rib')
        for i in range(25 if b.lod==0 else 15):
            x=X0+.03+(X1-X0-.06)*i/(24 if b.lod==0 else 14)
            tag(b.tube('roof27_guard_v',[p(x,z,.007) for z in (EAVE+.022,KNEE,TOP-.009)],
                .0028,'graphite',sides=4),'guard_grid','guard_edge')
        back_y=side*.33
        tag(b.poly('roof27_fan_well_back',[(X0,back_y,EAVE),(X1,back_y,EAVE),
            (X1,back_y,TOP),(X0,back_y,TOP)],[(0,1,2,3)],'grille_black',normal=(0,side,0)),
            'fan_well_back','fan_bay_end')
        tag(b.poly('roof27_fan_sill',[(X0,back_y,EAVE),(X1,back_y,EAVE),
            (X1,side*1.65,EAVE),(X0,side*1.65,EAVE)],[(0,1,2,3)],paint,normal=(0,0,1)),
            'fan_sill','body_eave')
        if side==1:
            for x in (2.30,2.52,2.74,2.96,3.18,3.40):
                tag(b.box('roof27_far_baffle',(x,.53,4.275),(.020,.40,.51),'graphite'),
                    'far_baffle','fan_well_back')

def reseat_fans(b,jw):
    mounts=('roof26_shroud_standoff','roof26_fan_motor','roof26_fan_shaft','roof26_cage_tie')
    for o in list(bpy.context.scene.objects):
        if o.name.startswith('roof26_louver') or (o.name.startswith('roof26_') and not o.name.startswith(mounts)):
            remove(o);continue
        if o.name.startswith(('roof20_',)+mounts):
            # Rigid translation keeps every circular part circular and all
            # motor/shaft/shroud connections intact inside the tapered well.
            o.location.y+=FAN_SHIFT
            if o.get('roof26_animation_kind'):
                q=list(o['roof26_pivot']);q[1]+=FAN_SHIFT;o['roof26_pivot']=q
            tag(o,'recessed_horizontal_fan','fan_well_back')
    guard(b,jw)

def vent_basis(side):
    tangent=Vector((0,-side*.31,.33)).normalized()
    normal=Vector((0,side*.33,.31)).normalized()
    return tangent,normal

def cut_vents(report):
    tz=vent_basis(1)[0].z
    z0,z1=VENT_Z-VENT_HALF_T*tz,VENT_Z+VENT_HALF_T*tz
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or o.get('roof26_animation_kind'):continue
        ps=points(o)
        if not ps or max(p.z for p in ps)<z0 or min(p.z for p in ps)>z1:continue
        if o.name.startswith(('bounds|','glazing_','light24_','cab_interior')):continue
        for x in VENT_CENTERS:
            if max(p.x for p in ps)<x-VENT_HALF_X or min(p.x for p in ps)>x+VENT_HALF_X:continue
            # Only the upper shoulder surface. Includes legacy overlapping
            # skin where present, not just the named visible hood object.
            _clip_mesh(o,[lambda p:p[0]-(x-VENT_HALF_X),lambda p:p[0]-(x+VENT_HALF_X),
                          lambda p:p[2]-z0,lambda p:p[2]-z1],
                lambda p:not(x-VENT_HALF_X+1e-7<p.x<x+VENT_HALF_X-1e-7 and
                              z0+1e-7<p.z<z1-1e-7 and abs(p.y)>1.20),roof_only=True)
            report['aperture_cut_objects'].append(o.name)

def shutters(b,jw):
    for x in VENT_CENTERS:
        for side in (-1,1):
            t,n=vent_basis(side);c=Vector((x,side*roof_half_width(VENT_Z),VENT_Z))
            def p(u,v,d=0):return c+Vector((u,0,0))+t*v+n*d
            paint='jw_roof' if jw else 'blue'
            def sheet(name,coords,mat,role):
                return tag(b.poly(name,[p(*v) for v in coords],[tuple(range(len(coords)))],mat,normal=n),
                    role,'vent_aperture')
            def solid(name,u,v,d,w,h,depth,mat,role):
                verts=[p(u+a*w/2,v+q*h/2,d+r*depth/2) for a,q,r in
                    [(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                     (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]]
                return tag(b.poly(name,verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),
                    (1,2,6,5),(2,3,7,6),(3,0,4,7)],mat,solid=True),role,'vent_aperture')
            hx,ht=VENT_HALF_X,VENT_HALF_T
            sheet('roof27_vent_back',[(-hx,-ht,-.080),(hx,-ht,-.080),(hx,ht,-.080),(-hx,ht,-.080)],
                  'grille_black','vent_back')
            for a,d in [((-hx,-ht),(hx,-ht)),((hx,-ht),(hx,ht)),((hx,ht),(-hx,ht)),((-hx,ht),(-hx,-ht))]:
                sheet('roof27_vent_return',[(a[0],a[1],-.080),(d[0],d[1],-.080),
                    (d[0],d[1],.004),(a[0],a[1],.004)],paint,'vent_return')
            for sign in (-1,1):
                solid('roof27_vent_side_frame',sign*.282,0,.005,.028,.400,.018,paint,'vent_frame')
                solid('roof27_vent_cross_frame',0,sign*.185,.005,.588,.023,.018,paint,'vent_frame')
            count=10 if b.lod==0 else 5
            pitch=.340/count
            for i in range(count):
                v=-.170+pitch*(i+.5)
                leaf=solid('roof27_louver_leaf',0,v,.005,.514,pitch-.005,.0025,
                    'jw_roof' if jw else ('roof' if p(0,v).z>=4.24 else 'blue'),'louver_leaf')
                pivot=p(0,v,.005)
                leaf['roof26_animation_kind']='louver'
                leaf['roof26_animation_group']=f'louver_{"m" if x<0 else "p"}_{"m" if side<0 else "p"}_{i:02}'
                leaf['roof26_pivot']=tuple(pivot);leaf['roof26_axis']=(1,0,0);leaf['roof26_direction']=side
                leaf['roof27_mount_normal']=tuple(n);leaf['roof27_mount_tangent']=tuple(t)
                for sign in (-1,1):
                    tag(b.cyl('roof27_louver_hinge',p(sign*.274,v,.005),.0035,.040,'spring_steel','X'),
                        'louver_hinge','vent_frame')

def apply(b,jw=False):
    assert not bpy.context.scene.get('roof27_applied')
    report=dict(lod=b.lod,jinwen=jw,section_objects=[],aperture_cut_objects=[],
        reference='user-confirmed cab two-fold cross-section; BV1kwRpYGEwD 02:12 onward',
        section_yz=[(roof_half_width(z),z) for z in (EAVE,KNEE,TOP)],
        front_canopy_preserved=True,dimensions='visual fit, not factory dimensions')
    section(b,jw,report);reseat_fans(b,jw)
    if b.lod<2:cut_vents(report);shutters(b,jw)
    if b.lod==1:
        # Mid-distance wire screens use a coarser grid, while the frame and
        # two-fold silhouette stay intact. Do not increase the established
        # fleet polygon budget simply to keep sub-pixel wires.
        report['lod1_reduced_wires']=[]
        for side in (-1,1):
            wires=[o for o in bpy.context.scene.objects if o.name.startswith('roof25_radiator_grid_v')
                   and sum(p.y for p in points(o))*side>0]
            wires.sort(key=lambda o:sum(p.x for p in points(o))/len(o.data.vertices))
            for i,o in enumerate(wires):
                if i%3 and i!=len(wires)-1:
                    report['lod1_reduced_wires'].append(o.name);remove(o)
    # Repeated historical section/colour cuts left redundant coplanar roof
    # subdivisions. Dissolve only the scoped roof region, never cab fronts or
    # lower carbody; preserve material boundaries and non-coplanar folds.
    for o in bpy.context.scene.objects:
        if not o.name.startswith('body_open_shell'):continue
        bm=bmesh.new();bm.from_mesh(o.data)
        selected=[v for v in bm.verts if EAVE+1e-6<v.co.z and abs(v.co.x)<9.179]
        bmesh.ops.remove_doubles(bm,verts=selected,dist=1e-6)
        selected=[v for v in bm.verts if EAVE+1e-6<v.co.z and abs(v.co.x)<9.179]
        allowed=set(selected);edges=[e for e in bm.edges if all(v in allowed for v in e.verts)]
        bmesh.ops.dissolve_limit(bm,angle_limit=1e-5,verts=selected,edges=edges,
            use_dissolve_boundaries=False,delimit={'MATERIAL','NORMAL','UV'})
        bm.to_mesh(o.data);bm.free();o.data.update()
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();b.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['roof27_applied']=True
    return report
