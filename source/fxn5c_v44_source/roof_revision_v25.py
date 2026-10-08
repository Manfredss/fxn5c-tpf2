"""Correct the machine-room roof independently of the retained cab section.

Evidence: user roof drawing, BV1kwRpYGEwD at 01:31, 01:53 and 02:05.
Exterior dimensions are visual fits, not manufacturer CAD. No new assertion
about fan function, blade count or invisible far-side machinery is made.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector
from roof_revision_v24 import roof_half_width, _clip_mesh, _edit, _color_upper
from jinwen_roof_v20 import basis, rectangle

START, END = 7.10, 8.10
FAN_X0, FAN_X1 = 2.10, 3.60
RAD_X0, RAD_X1 = -7.20, -4.00
RAD_Z0, RAD_Z1 = 4.275, 4.615
GRAY_Z = 4.24


def old_width(z):
    rows=((3.95,1.65),(4.48,1.15),(4.65,1.04),(4.705,.90))
    for a,c in zip(rows,rows[1:]):
        if z<=c[0]:return a[1]+(c[1]-a[1])*(z-a[0])/(c[0]-a[0])
    return .90


def influence(x):return max(0.,min(1.,(END-abs(x))/(END-START)))


def restore_section(p):
    p=Vector(p)
    if p.z>3.95:
        p.y*=1+influence(p.x)*(old_width(p.z)/roof_half_width(p.z)-1)
    return p


def planarize_outer_shoulder(shell):
    # Previous repeated clipping/deformation left outer shoulder vertices
    # several centimetres off the intended manufactured planes. Project only
    # outward/upward sheet faces, never inward cavity walls or horizontal tops.
    _clip_mesh(shell,[lambda p:p[2]-3.95,lambda p:p[2]-4.48,
                      lambda p:p[2]-4.65],roof_only=True)
    tf=shell.matrix_world;inv=tf.inverted();moved=0
    for face in shell.data.polygons:
        pts=[tf@shell.data.vertices[i].co for i in face.vertices]
        c=sum(pts,Vector())/len(pts)
        n=tf.to_3x3()@face.normal
        if not (3.95<c.z<4.65 and abs(c.x)<END and abs(n.x)<.8 and
                n.y*c.y>.3 and n.z>.2):continue
        for i,p in zip(face.vertices,pts):
            if p.z<=3.95+1e-6 or abs(p.y)<.99:continue
            w=influence(p.x);target=(1 if p.y>0 else -1)*old_width(p.z)
            p.y+=(target-p.y)*w
            shell.data.vertices[i].co=inv@p;moved+=1
    shell.data.update()
    return moved


def restore_fan(p,side):
    # Invert the rigid v24 fan transform. Unlike an affine stretch, this keeps
    # circular shrouds/hubs circular and preserves all depths and clearances.
    target,sv,nv=basis(side)
    source=Vector((0,side*(1.34+.48)/2,(4.28+4.705)/2))
    oldv=Vector((0,side*(1.34-.48),4.28-4.705)).normalized()
    oldn=Vector((0,side*(4.705-4.28),1.34-.48)).normalized()
    rel=Vector(p)-source
    return target+Vector((rel.x,0,0))+sv*rel.dot(oldv)+nv*rel.dot(oldn)


def tag(obj,role,host):
    obj['roof25_role']=role;obj['roof25_host']=host
    obj['estimated_dimensions']=True
    return obj


def recolor(obj,b,mat):
    obj.data.materials.clear();obj.data.materials.append(b.mat(mat))
    for f in obj.data.polygons:f.material_index=0


def fan_skin(b,jw):
    section=[(-1.65,3.95),(-1.15,4.48),(-1.04,4.65),(-.9,4.705),
             (.9,4.705),(1.04,4.65),(1.15,4.48),(1.65,3.95)]
    n=len(section)
    skin=b.poly('roof25_fan_bay_skin',[(x,y,z) for x in (FAN_X0,FAN_X1) for y,z in section],
                [(i,i+1,n+i+1,n+i) for i in range(n-1)],'jw_roof' if jw else 'roof',normal=(0,0,1))
    tag(skin,'folded_fan_bay','body_shell')
    # Close the height step to the neighbouring removable roof sections. The
    # v24 open-ended bay left a visible slit beside the raised fan cover.
    for x,end in ((FAN_X0,-1),(FAN_X1,1)):
        cap=b.poly('roof25_fan_bay_end_return',[(x,y,z) for y,z in section],
            [tuple(range(len(section)))],'jw_roof' if jw else 'roof',normal=(end,0,0))
        tag(cap,'fan_bay_end_return','body_shell')
    # Analytic cuts of an open skin avoid Boolean-generated underside caps
    # below the eave. Existing recess returns bridge skin to fan face.
    c,v,norm=basis(1)
    z0=c.z-abs(v.z)*.338;z1=c.z+abs(v.z)*.338
    _clip_mesh(skin,[lambda p:p[0]-(2.85-.711),lambda p:p[0]-(2.85+.711),
                    lambda p:p[2]-z0,lambda p:p[2]-z1],
               lambda p:not(2.85-.711+1e-6<p.x<2.85+.711-1e-6 and
                            z0+1e-6<p.z<z1-1e-6 and abs(p.y)>.99))
    _color_upper(skin,b,jw)
    return skin


def fan_guards(b,jw):
    paint='jw_roof' if jw else 'roof'
    result=[]
    for side in (-1,1):
        c,v,n=basis(side);c.x=2.85
        def p(u,w,d=.030):return tuple(c+Vector((u,0,0))+v*w+n*d)
        # Two outer cells in the supplied drawing AND the 02:05 frame. The
        # former three-bay vertical members obscured both circular units.
        for u in (-.728,0,.728):
            result.append(tag(b.sheet('roof25_fan_mullion',rectangle(.012,.350),
                lambda a,w:p(u+a,w,.045),paint,.040,n),'two_cell_frame','fan_bay_return'))
        for w in (-.35,.35):
            result.append(tag(b.sheet('roof25_fan_edge',rectangle(.740,.012),
                lambda u,a:p(u,w+a,.045),paint,.040,n),'two_cell_edge','fan_bay_return'))
        # Open cage, not an opaque black rectangle or a glowing fan face.
        for i in range(9 if b.lod==0 else 5):
            w=-.33+i*.66/(8 if b.lod==0 else 4)
            result.append(tag(b.tube('roof25_fan_grid_h',[p(-.708,w),p(.708,w)],
                .0045,'spring_steel',sides=4),'fan_guard','two_cell_frame'))
        for i in range(23 if b.lod==0 else 13):
            u=-.708+i*1.416/(22 if b.lod==0 else 12)
            result.append(tag(b.tube('roof25_fan_grid_v',[p(u,-.33,.033),p(u,.33,.033)],
                .0030,'graphite',sides=4),'fan_guard','two_cell_frame'))
        if b.lod==0:
            for u in (-.68,-.34,0,.34,.68):
                for w in (-.35,.35):
                    o=b.cyl('roof25_fan_fastener',p(u,w,.049),.006,.012,'spring_steel','Z')
                    o.rotation_euler=n.to_track_quat('Z','Y').to_euler()
                    result.append(tag(o,'fastener','two_cell_edge'))
    return result


def cut_side_aperture(obj,x0,x1,z0,z1):
    # Clip only the outer roof shoulder, never the roof top, cab or underframe.
    _clip_mesh(obj,[lambda p:p[0]-x0,lambda p:p[0]-x1,
                   lambda p:p[2]-z0,lambda p:p[2]-z1],
               lambda p:not(x0+1e-6<p.x<x1-1e-6 and z0+1e-6<p.z<z1-1e-6
                            and abs(p.y)>.99),roof_only=True)


def radiator_shoulders(b,jw,shell):
    paint='jw_roof' if jw else 'roof'
    cut_side_aperture(shell,RAD_X0,RAD_X1,RAD_Z0,RAD_Z1)
    # Both side-facing radiator grilles are a visible exterior reconstruction;
    # retaining the old top grid does not substitute for these shoulder mouths.
    for side in (-1,1):
        def p(x,z,d=0):return (x,side*(old_width(z)+d),z)
        x0,x1,z0,z1=RAD_X0,RAD_X1,RAD_Z0,RAD_Z1
        # Recess floor and four sheet-metal returns attach the wire screen to
        # the skin. A black back wall is behind the open cells, never on top.
        back=b.poly('roof25_radiator_back',[p(x0,z0,-.10),p(x1,z0,-.10),p(x1,z1,-.10),p(x0,z1,-.10)],
                    [(0,1,2,3)],'grille_black',normal=(0,side,0))
        tag(back,'radiator_recess','body_shell')
        edges=[[(x0,z0),(x1,z0)],[(x0,z1),(x1,z1)],[(x0,z0),(x0,z1)],[(x1,z0),(x1,z1)]]
        for a,c in edges:
            tag(b.poly('roof25_radiator_return',[p(*a,.003),p(*c,.003),p(*c,-.105),p(*a,-.105)],
                [(0,1,2,3)],paint,normal=(0,side,0)),'aperture_return','body_shell')
        for z in (z0,z1):
            tag(b.tube('roof25_radiator_edge',[p(x0-.014,z,.012),p(x1+.014,z,.012)],
                .016,paint,sides=4),'grille_frame','aperture_return')
        panels=8
        for i in range(panels+1):
            x=x0+i*(x1-x0)/panels
            pts=[p(x,z,.012) for z in (z0,4.48,z1)]
            tag(b.tube('roof25_radiator_divider',pts,.010,paint,sides=4),'grille_divider','grille_frame')
            if b.lod==0:
                for z in (z0+.035,(z0+z1)/2,z1-.035):
                    o=b.cyl('roof25_radiator_screw',p(x,z,.022),.006,.018,'spring_steel','Y')
                    tag(o,'captive_screw','grille_divider')
        nh=17 if b.lod==0 else 9
        for i in range(nh):
            z=z0+.012+(z1-z0-.024)*i/(nh-1)
            tag(b.tube('roof25_radiator_grid_h',[p(x0,z,.005),p(x1,z,.005)],
                .0028,'graphite',sides=4),'radiator_screen','grille_frame')
        nv=113 if b.lod==0 else 49
        for i in range(nv):
            x=x0+.009+(x1-x0-.018)*i/(nv-1)
            tag(b.tube('roof25_radiator_grid_v',[p(x,z,.008) for z in (z0,4.48,z1)],
                .0025,'graphite',sides=4),'radiator_screen','grille_frame')


def side_seams(b,jw):
    paint='jw_roof' if jw else 'roof'
    for side in (-1,1):
        # Panel joints on actual shoulder rather than isolated lines in space.
        for x in (-3.91,2.08,3.62,7.02):
            points=[(x,side*(old_width(z)+.002),z) for z in (3.965,4.24,4.48,4.64)]
            tag(b.tube('roof25_panel_joint',points,.004,'black',sides=4),'panel_joint','body_shell')
        for x,w in ((-.1,.9),(1.05,.9)):
            # Folded removable upper-shoulder lids, corresponding to the pair
            # visible above the central side lettering in the 02:05 frame.
            z0,z1=4.39,4.615
            pts=[(x-w/2,side*(old_width(z0)+.006),z0),(x+w/2,side*(old_width(z0)+.006),z0),
                 (x+w/2,side*(old_width(z1)+.006),z1),(x-w/2,side*(old_width(z1)+.006),z1)]
            tag(b.poly('roof25_shoulder_service_lid',pts,[(0,1,2,3)],paint,normal=(0,side,0)),
                'service_lid','body_shell')
            tag(b.tube('roof25_lid_gasket',pts+[pts[0]],.006,'black',sides=4),'lid_gasket','service_lid')


def apply(b,jw=False):
    assert not bpy.context.scene.get('roof25_applied'),'v25 may run once only'
    originals=list(bpy.context.scene.objects)
    report={'lod':b.lod,'jinwen':jw,'changed':[],'removed':[],
        'fan_mount_angle_before_deg':math.degrees(math.atan2(.425,.86)),
        'fan_mount_angle_after_deg':math.degrees(math.atan2(.569,.54)),
        'evidence':'BV1kwRpYGEwD 01:31, 01:53, 02:05 and user roof drawing',
        'dimensions':'visual reconstruction; not surveyed','far_side_rotors':'not inferred'}
    old_guards=('roof20_guard_horizontal','roof20_guard_vertical','roof20_guard_mullion',
                'roof20_guard_edge','roof20_guard_fastener','roof24_shoulder_fan_skin')
    keep=('bounds|','glazing_','light24_','headlights_','taillights_','cab_interior',
          'cab_roof_well_floor','cab_aircon_','ac_','roof_ac_conduit',
          'recessed_fan_shroud','radiator_fan_hub','concealed_fan_blade')
    for obj in originals:
        if obj.type!='MESH' or obj.name.startswith(keep):continue
        pts=[obj.matrix_world@v.co for v in obj.data.vertices]
        if not pts or max(p.z for p in pts)<=3.95:continue
        if obj.name.startswith(old_guards):
            report['removed'].append(obj.name);bpy.data.objects.remove(obj,do_unlink=True);continue
        if obj.name.startswith('roof20_'):
            side=-1 if sum(p.y for p in pts)<0 else 1
            _edit(obj,lambda p,s=side:restore_fan(p,s),'roof25_rigid_fan_reseat')
            # v24's colour clipping used the old upper-face Z values. Keep
            # visible cell borders one neutral metal finish like the video.
            if obj.name.startswith('roof20_cell_frame'):recolor(obj,b,'jw_roof' if jw else 'roof')
            report['changed'].append(obj.name)
        elif min(p.x for p in pts)<END and max(p.x for p in pts)>-END:
            # Insert blend-zone stations before deforming long body surfaces.
            if obj.name.startswith(('body_open_shell','roof24_distant')):
                _clip_mesh(obj,[lambda p:p[0]+END,lambda p:p[0]+START,
                                lambda p:p[0]-START,lambda p:p[0]-END],roof_only=True)
            _edit(obj,restore_section,'roof25_machine_room_section')
            report['changed'].append(obj.name)
    shell=next(o for o in bpy.context.scene.objects if o.name.startswith('body_open_shell'))
    report['outer_shoulder_vertices_planarized']=planarize_outer_shoulder(shell)
    if b.lod<2:
        fan_skin(b,jw);fan_guards(b,jw);radiator_shoulders(b,jw,shell);side_seams(b,jw)
    else:
        # Coarse silhouettes remain visible after LOD changes, no dense wirework.
        for side in (-1,1):
            p=lambda x,z:(x,side*(old_width(z)+.006),z)
            tag(b.poly('roof25_distant_radiator',[p(RAD_X0,RAD_Z0),p(RAD_X1,RAD_Z0),p(RAD_X1,RAD_Z1),p(RAD_X0,RAD_Z1)],
                [(0,1,2,3)],'grille_black',normal=(0,side,0)),'distant_grille','body_shell')
            c,v,n=basis(side);c.x=2.85
            tag(b.sheet('roof25_distant_fan_face',rectangle(.71,.337),
                lambda u,w:tuple(c+Vector((u,0,0))+v*w+n*.004),'grille_black',.01,n),'distant_fan_face','body_shell')
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();b.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['roof25_applied']=True
    report['added']=[o.name for o in bpy.context.scene.objects if o.get('roof25_role')]
    return report
