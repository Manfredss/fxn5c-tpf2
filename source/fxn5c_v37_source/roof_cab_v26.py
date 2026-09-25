"""Level longitudinal cab equipment shoulders; keep transverse roof folds.

Input is an unjoined, final-v25 scene (or its reconstructed LOD). The shared
front canopy, headlights, cab windows, side text and machine-room fan bay are
outside this pass. Coordinates are exterior-reference fits, not factory CAD.
"""
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody
from roof_revision_v24 import _clip_mesh, roof_half_width
from roof_revision_v25 import old_width, influence

Z_KNEE, Z_TOP = 4.28, 4.65
END = 9.18
STARTS = {-1: 7.22, 1: 6.94}
POCKET_X = (8.14, 9.14)
POCKET_Y = 1.00
FLOOR_Z = 4.424


def width(x,z):
    # Keep the proven transverse profile below the new horizontal crown.
    a=roof_half_width(z)
    return a + influence(x)*(old_width(z)-a)


def surface_z(x,y):
    y=abs(y)
    rows=[(width(x,z),z) for z in (Z_KNEE,4.48,Z_TOP)]
    if y<=rows[-1][0]:return Z_TOP
    for (ya,za),(yb,zb) in zip(rows,rows[1:]):
        if yb<=y<=ya:return za+(zb-za)*(ya-y)/(ya-yb)
    return Z_KNEE


def tag(obj,role,host='body_shell'):
    obj['cab26_role']=role;obj['cab26_host']=host
    obj['estimated_dimensions']=True
    return obj


def points(obj):
    return [obj.matrix_world@v.co for v in obj.data.vertices]


def cut_region(obj,end,start):
    _clip_mesh(obj,[lambda p,e=end:p[0]*e-start,
                    lambda p,e=end:p[0]*e-END,lambda p:p[2]-Z_KNEE],
               lambda p:not(start+1e-7<p.x*end<END-1e-7 and p.z>Z_KNEE+1e-7),
               roof_only=True)


def sheet(b,name,verts,paint,normal,role,host='body_shell'):
    return tag(b.poly(name,verts,[tuple(range(len(verts)))],paint,normal=normal),role,host)


def make_hood(b,end,jw):
    start=STARTS[end];paint='jw_roof' if jw else 'roof'
    xs=sorted(set([start,7.10,7.22,7.40,8.10,*POCKET_X,END]))
    xs=[x for x in xs if start<=x<=END]
    verts=[]
    for x in xs:
        rows=[(-width(x,Z_KNEE),Z_KNEE),(-width(x,4.48),4.48),
              (-width(x,Z_TOP),Z_TOP),(width(x,Z_TOP),Z_TOP),
              (width(x,4.48),4.48),(width(x,Z_KNEE),Z_KNEE)]
        verts.extend((end*x,y,z) for y,z in rows)
    faces=[]
    for r in range(len(xs)-1):
        for c in range(5):
            a=r*6+c;face=(a,a+6,a+7,a+1)
            faces.append(face if end>0 else tuple(reversed(face)))
    hood=tag(b.poly('cab26_level_equipment_hood',verts,faces,paint,normal=(0,0,1)),
             'longitudinally_level_hood')
    # Open the actual crown and shoulder sheets, not just a painted dark patch.
    _clip_mesh(hood,[lambda p:p[0]*end-POCKET_X[0],
                     lambda p:p[0]*end-POCKET_X[1],
                     lambda p:p[1]-POCKET_Y,lambda p:p[1]+POCKET_Y],
               lambda p:not(POCKET_X[0]+1e-7<p.x*end<POCKET_X[1]-1e-7 and
                            abs(p.y)<POCKET_Y-1e-7))
    # Rear equipment-bay wall meets the retained low shell/radiator cassette.
    x=end*start
    upper=[(x,y,z) for y,z in [(-width(start,Z_KNEE),Z_KNEE),
           (-width(start,4.48),4.48),(-width(start,Z_TOP),Z_TOP),
           (width(start,Z_TOP),Z_TOP),(width(start,4.48),4.48),
           (width(start,Z_KNEE),Z_KNEE)]]
    sheet(b,'cab26_rear_join_return',upper,paint,(-end,0,0),'roof_join_return')
    # Four real pocket walls land on the existing support floor. The sides
    # intentionally remain low: the AC side intake is visible above them.
    for side in (-1,1):
        y=side*POCKET_Y
        v=[(end*x,y,z) for x,z in [(POCKET_X[0],FLOOR_Z),
           (POCKET_X[1],FLOOR_Z),(POCKET_X[1],surface_z(POCKET_X[1],y)),
           (POCKET_X[0],surface_z(POCKET_X[0],y))]]
        sheet(b,'cab26_ac_pocket_side',v,paint,(0,-side,0),'ac_pocket_wall','cab_roof_well_floor')
    for x,sgn in ((POCKET_X[0],1),(POCKET_X[1],-1)):
        ys=[-POCKET_Y,-width(x,Z_TOP),width(x,Z_TOP),POCKET_Y]
        # The multi-segment upper edge follows the transverse fold exactly.
        v=[(end*x,-POCKET_Y,FLOOR_Z),(end*x,POCKET_Y,FLOOR_Z)]
        v.extend((end*x,y,surface_z(x,y)) for y in reversed(ys))
        sheet(b,'cab26_ac_pocket_end',v,paint,(end*sgn,0,0),'ac_pocket_wall','cab_roof_well_floor')
    # A level floor is present in all LODs, including simplified legacy scenes.
    if not any(o.type=='MESH' and o.name.startswith('cab_roof_well_floor') and
               sum(p.x for p in points(o))*end>0 for o in bpy.context.scene.objects):
        tag(BaseBody.box(b,'cab26_ac_support_floor',(end*8.67,0,FLOOR_Z-.009),
                       (1.64,2.05,.018),paint),'ac_support_floor')
    if not any(o.type=='MESH' and o.name.startswith('cab_aircon_case') and
               sum(p.x for p in points(o))*end>0 for o in bpy.context.scene.objects):
        tag(BaseBody.box(b,'cab26_distant_aircon_case',(end*8.67,0,4.528),
                       (.80,1.14,.208),'metal'),'distant_aircon','cab26_ac_support_floor')
    if b.lod<2:
        # Thin joints are attached to the cut edge, not a new raised roof tier.
        for side in (-1,1):
            pts=[(end*x,side*POCKET_Y,surface_z(x,POCKET_Y)) for x in POCKET_X]
            tag(b.tube('cab26_pocket_edge_gasket',pts,.003,'black',sides=4),
                'pocket_edge_gasket','ac_pocket_wall')
    return hood


def apply(builder,jinwen=False):
    assert not bpy.context.scene.get('cab26_applied'),'cab v26 pass may run once only'
    report={'lod':builder.lod,'jinwen':jinwen,'removed':[],'changed':[],
            'added':[],'flat_crown_z':Z_TOP,'pocket_x':POCKET_X,'pocket_half_y':POCKET_Y,
            'front_canopy_preserved':True,'ac_rigid_translation_z':0.0,
            'dimensions':'exterior fit; not manufacturer CAD'}
    originals=list(bpy.context.scene.objects)
    for o in originals:
        if o.type!='MESH':continue
        if o.name.startswith('cab_continuous_low_hood_v13'):
            report['removed'].append(o.name);bpy.data.objects.remove(o,do_unlink=True)
        elif o.name.startswith(('body_open_shell','roof24_distant_center_roof')):
            for end,start in STARTS.items():cut_region(o,end,start)
            report['changed'].append(dict(name=o.name,operation='upper_cab_shell_opened'))
        elif o.name.startswith('trapezoid_roof_deck_v07'):
            ps=points(o)
            if max(p.x for p in ps)>STARTS[1]:
                cut_region(o,1,STARTS[1])
                report['changed'].append(dict(name=o.name,operation='removed_rear_end_ramp'))
    for end in (-1,1):make_hood(builder,end,jinwen)
    # Restore the four small lifting pads on the changed sheet. Only pads near
    # |x|=8 are affected; the older deformed pads had tilted floating corners.
    pads=[o for o in list(bpy.context.scene.objects) if o.type=='MESH' and
          o.name.startswith('roof_eye_pad_v06') and abs(abs(sum(p.x for p in points(o))/len(points(o)))-8)<.1]
    for o in pads:
        ps=points(o);centre=sum(ps,Vector())/len(ps);x=centre.x;y=centre.y
        # All four pad corners must lie on the flat crown, not hang over its
        # narrowing transverse fold near the equipment pocket.
        target_y=(1 if y>0 else -1)*min(abs(y),width(abs(x)+.065,Z_TOP)-.065)
        report['removed'].append(o.name);bpy.data.objects.remove(o,do_unlink=True)
        tag(BaseBody.box(builder,'cab26_level_lifting_pad',(x,target_y,Z_TOP+.005),
                       (.13,.10,.010),'roof' if not jinwen else 'jw_roof'),
            'lifting_pad','longitudinally_level_hood')
        eyes=[q for q in bpy.context.scene.objects if q.type=='MESH' and
              q.name.startswith('roof_lifting_eye_v06') and
              abs(sum(p.x for p in points(q))/len(points(q))-x)<.1 and
              (sum(p.y for p in points(q))/len(points(q)))*y>0]
        for q in eyes:
            dz=Z_TOP+.010-min(p.z for p in points(q))
            q.location.z+=dz;q.location.y+=target_y-y;q['cab26_host']='cab26_level_lifting_pad'
            report['changed'].append(dict(name=q.name,operation='rigid_lifting_eye_reseat',dz=dz,dy=target_y-y))
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();builder.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['cab26_applied']=True
    report['added']=[o.name for o in bpy.context.scene.objects if o.get('cab26_role')]
    return report
