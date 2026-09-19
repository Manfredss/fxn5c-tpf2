"""Conservative exterior reconstruction; not a mechanical section drawing.

Two fan motors are supported by DM1/DM2 in the 2021 electrical paper and two
circular units by 0004/7007 photographs. Only the observed negative-Y side
gets rotors. Opposite-side baffles and hidden depth are visual estimates;
no airflow direction, identical production batches or surveyed dimensions
are asserted. Dense external guards retain the appearance of the 0051 view.
"""
import math
import bpy
import bmesh
from mathutils import Vector
from jinwen_roof_v20 import basis, rectangle, disk_loop, fan_cell

OLD_PREFIXES = ('trapezoid_vent_', 'crossvent_inset_fin_v12', 'jinwen_roof15_')
FAN_X = (2.485, 3.215)
RESERVOIR_X = (3.00, 3.68)


def cut_opening(b, shell, side):
    """Clip the inclined tool to the approved shell region before subtraction.

    A thick inclined prism alone reaches below the visible lower lip at its
    back face, unnecessarily cutting the retained sill below Z=4.116.
    """
    center, slope, normal = basis(side)
    center.x = 2.85
    cutter = b.sheet('roof20_temporary_cutter', rectangle(.722, .352),
                     lambda u,v: tuple(center + Vector((u,0,0)) + slope*v + normal*.10),
                     'black', .47, normal)
    region = b.box('roof20_temporary_cut_region', (2.85,0,4.4005), (1.50,3.32,.569), 'black')
    bpy.context.view_layer.objects.active = cutter
    clip = cutter.modifiers.new('authorized_shell_region', 'BOOLEAN')
    clip.operation = 'INTERSECT'; clip.solver = 'EXACT'; clip.object = region
    bpy.ops.object.modifier_apply(modifier=clip.name)
    bpy.data.objects.remove(region, do_unlink=True)
    b.cut(shell, cutter)


def tag(obj, part, side=None):
    obj['roof20_part' if obj.name.startswith('roof20_') else 'equipment20_part'] = part
    obj['estimated_dimensions'] = True
    if side is not None:
        obj['equipment20_side'] = side
    return obj


def shoulder(b, side, jinwen):
    center, slope, normal = basis(side)
    center.x = 2.85
    def point(u, v, d=0):
        return tuple(center + Vector((u,0,0)) + slope*v + normal*d)
    paint = 'jw_roof' if jinwen else 'blue'
    # Visible aperture walls give the mesh a real folded return and recess.
    tag(b.rim('roof20_recess_return', rectangle(.743,.370), rectangle(.710,.337),
              lambda u,v:point(u,v,.010), paint,.225,normal),'recess_return',side)
    if side < 0:
        for x in FAN_X:
            before = set(bpy.context.scene.objects)
            fan_cell(b, side, x)
            for obj in set(bpy.context.scene.objects)-before:
                obj.name = obj.name.replace('jinwen_roof15_', 'roof20_')
                tag(obj, 'fan_'+obj.get('jinwen_roof15_component', 'frame_or_guard'),side)
                # Darker, recessed machinery stays behind the rectangular mesh.
                if any(s in obj.name for s in ('fan_shroud','fan_blades','metal_hub','well_back')):
                    obj.location -= normal*.080
                if 'metal_hub' in obj.name:
                    obj.data.materials.clear()
                    obj.data.materials.append(b.mat('jw_frame' if jinwen else 'cast_steel'))
                if 'cell_frame' in obj.name:
                    obj.data.materials.clear(); obj.data.materials.append(b.mat(paint))
    else:
        tag(b.sheet('roof20_baffle_back', rectangle(.707,.334),
                    lambda u,v:point(u,v,-.255),'grille_black',.012,normal),'baffle_back',side)
        # Only observed sheet-like silhouettes: do not clone invisible rotors.
        for u in (-.59,-.39,-.19,.19,.39,.59):
            tag(b.sheet('roof20_inner_baffle',rectangle(.027,.312),
                        lambda a,v:point(u+a,v,-.130),'roof',.023,normal),'inner_baffle',side)
    # A rectangular fine guard is common to both observed exterior states.
    # It is geometry with open cells, not an opaque texture over a fake hole.
    nv, nu = ((29,59) if b.lod==0 else (13,29))
    for i in range(nv):
        v=-.330+i*.660/(nv-1)
        tag(b.tube('roof20_guard_horizontal',[point(-.707,v,.030),point(.707,v,.030)],
                   .0027,'graphite',sides=4),'guard_horizontal',side)
    for i in range(nu):
        u=-.707+i*1.414/(nu-1)
        tag(b.tube('roof20_guard_vertical',[point(u,-.330,.033),point(u,.330,.033)],
                   .0027,'graphite',sides=4),'guard_vertical',side)
    # Three outer bays are visible in 0051's high-angle photograph; their
    # mullions need not coincide with the two internal circular windings.
    for u in (-.728,-.243,.243,.728):
        tag(b.sheet('roof20_guard_mullion',rectangle(.012,.351),
                    lambda a,v:point(u+a,v,.045),paint,.022,normal),'guard_mullion',side)
    for v in (-.351,.351):
        tag(b.sheet('roof20_guard_edge',rectangle(.734,.012),
                    lambda u,a:point(u,v+a,.045),paint,.022,normal),'guard_edge',side)
    if b.lod==0:
        for u in (-.68,0,.68):
            for v in (-.350,.350):
                o=b.cyl('roof20_guard_fastener',point(u,v,.054),.007,.009,'spring_steel','Z')
                o.rotation_euler=normal.to_track_quat('Z','Y').to_euler()
                tag(o,'guard_fastener',side)


def reservoir_details(b, jinwen):
    """Add bounded exterior details; preserve the original tanks and straps."""
    mat='jw_frame' if jinwen else 'graphite'
    n=32 if b.lod==0 else 16
    for x in RESERVOIR_X:
        for side in (-1,1):
            # Spun/pressed shallow end shell outside the retained flat cap.
            verts=[]
            profile=((.286,1.322),(.270,1.347),(.219,1.371),(.135,1.389),(.044,1.397))
            for radius,y in profile:
                verts.extend((x+u,side*y,.83+v) for u,v in disk_loop(radius,n))
            faces=[]
            for j in range(len(profile)-1):
                for k in range(n):
                    q=(k+1)%n; face=(j*n+k,j*n+q,(j+1)*n+q,(j+1)*n+k)
                    faces.append(face if side<0 else tuple(reversed(face)))
            f=tuple(range(4*n,5*n)); faces.append(f if side<0 else tuple(reversed(f)))
            o=tag(b.poly('equipment20_reservoir_head',verts,faces,mat,normal=(0,side,0)),
                  'reservoir_head',side)
            for p in o.data.polygons:p.use_smooth=len(p.vertices)==4
            points=[(x+u,side*1.329,.83+v) for u,v in disk_loop(.280,n)]
            tag(b.tube('equipment20_end_weld',points+[points[0]],.005,mat,sides=5),'end_weld',side)
            # Small central boss and short terminated pipe. No invented bolt ring.
            tag(b.cyl('equipment20_end_boss',(x,side*1.409,.83),.040,.026,mat,'Y'), 'end_boss',side)
            tag(b.cyl('equipment20_end_plug',(x,side*1.430,.83),.021,.016,'spring_steel','Y'), 'end_plug',side)
            if b.lod==0:
                path=[(x-.115,side*1.17,1.104),(x-.115,side*1.17,1.245),
                      (x-.070,side*1.18,1.290),(x+.10,side*1.18,1.290)]
                tag(b.tube('equipment20_reservoir_short_pipe',path,.013,'spring_steel',sides=8),'visible_short_pipe',side)
                tag(b.cyl('equipment20_pipe_union',(x-.115,side*1.17,1.160),.022,.040,mat,'Z'), 'pipe_union',side)
                tag(b.box('equipment20_pipe_clip',(x+.085,side*1.18,1.300),(.040,.048,.054),mat), 'pipe_clip',side)
        if b.lod==0:
            # Body-owned support feet are deliberately inside the sill envelope.
            for y in (-.91,.91):
                tag(b.box('equipment20_reservoir_mount',(x,y,1.190),(.115,.078,.130),mat),'reservoir_mount')
    if b.lod==0:
        for side in (-1,1):
            path=[(2.61,side*1.21,1.235),(2.71,side*1.21,1.235),
                  (2.76,side*1.21,1.280),(3.84,side*1.21,1.280),
                  (3.90,side*1.21,1.220),(3.90,side*1.13,1.220)]
            tag(b.tube('equipment20_visible_header',path,.014,'spring_steel',sides=8),'visible_header',side)
            # Terminate the retained exterior airline at this visible header;
            # do not leave its existing last point suspended above the tanks.
            path=[(3.70,side*1.30,1.180),(3.70,side*1.30,1.235),
                  (3.70,side*1.255,1.280),(3.70,side*1.21,1.280)]
            tag(b.tube('equipment20_airline_join',path,.018,'spring_steel',sides=8),'airline_join',side)
            tag(b.cyl('equipment20_airline_union',(3.70,side*1.30,1.209),.026,.038,mat,'Z'),'airline_union',side)


def apply(b,jinwen=False):
    if b.lod>=2:
        return {'lod':b.lod,'detail_omitted':True}
    if any(o.name.startswith(('roof20_','equipment20_')) for o in bpy.context.scene.objects):
        raise RuntimeError('v20 equipment pass may only run once per scene')
    shell=next(o for o in bpy.context.scene.objects if o.name.startswith('body_open_shell_v07'))
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(OLD_PREFIXES):bpy.data.objects.remove(obj,do_unlink=True)
    # Retain face materials, weld split paint vertices only for a robust cut.
    bm=bmesh.new(); bm.from_mesh(shell.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(shell.data);bm.free();shell.data.update()
    for side in (-1,1):
        cut_opening(b,shell,side)
        shoulder(b,side,jinwen)
    paint='jw_roof' if jinwen else 'roof'
    tag(b.sheet('roof20_flat_crown',rectangle(.75,1.04),
                lambda u,v:(2.85+u,v,4.685),paint,.025,(0,0,1)),'flat_crown')
    reservoir_details(b,jinwen)
    shell['roof20_open_shoulders']=2
    bpy.context.scene['roof20_fan_count']=2
    bpy.context.scene['roof20_fan_side']=-1
    bpy.context.scene['roof20_hidden_arrangement_estimated']=True
    # Remove superseded *counts*, not their photographic provenance.
    for key in ('jinwen_roof15_fan_cells','evidence_crossvent_inset_fin'):
        if key in bpy.context.scene:del bpy.context.scene[key]
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals()
    b.g.ensure_uvs();bpy.context.view_layer.update()
    return {'lod':b.lod,'fan_count':2,'fan_side':-1,'opposite_side':'mesh and baffles',
            'airflow_and_hidden_depth':'not verified','reservoir_centres':RESERVOIR_X}
