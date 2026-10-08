"""Jinwen 7006 shoulder fan cells, authored from exterior photographs.

The 7006 high-side view and 7007 broadside show two circular fans behind the
sloping rectangular guard rather than the CR variant's fine louver infill.
Dimensions, blade count, recess depth and far-side duplication are visual
reconstruction choices, NOT manufacturer CAD. The observed exterior is the
scope: no claim is made about the internal ventilation circuit.

Call apply(builder) on the unjoined CR scene before final planar-normal reset
and export. The existing crown, exhaust outlets and cab hoods stay unchanged.
"""
import math
import bpy
import bmesh
from mathutils import Vector

X0, X1 = 2.10, 3.60
FAN_X = (2.485, 3.215)
TOP_Y, EDGE_Y = 1.04, 1.58
TOP_Z, EDGE_Z = 4.685, 4.116


def tag(obj, value):
    obj['jinwen_roof15_component'] = value
    return obj


def remove_old():
    removed = []
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('trapezoid_vent_', 'crossvent_inset_fin_v12',
                                'jinwen_roof15_')):
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    return removed


def basis(side):
    """u along the vehicle, v down the actual flat shoulder, d outwards."""
    slope = Vector((0, side*(EDGE_Y-TOP_Y), EDGE_Z-TOP_Z)).normalized()
    normal = Vector((0, side*(TOP_Z-EDGE_Z), EDGE_Y-TOP_Y)).normalized()
    center = Vector((0, side*(TOP_Y+EDGE_Y)/2, (TOP_Z+EDGE_Z)/2))
    return center, slope, normal


def rectangle(half_x, half_v):
    return [(-half_x, -half_v), (half_x, -half_v),
            (half_x, half_v), (-half_x, half_v)]


def disk_loop(radius, count):
    return [(radius*math.cos(i*math.tau/count),
             radius*math.sin(i*math.tau/count)) for i in range(count)]


def fan_cell(b, side, x):
    roof_mat = 'jw_roof' if 'jw_roof' in b.g.MATERIAL_SPECS else 'roof'
    center, slope, normal = basis(side)
    center.x = x
    def point(u, v, d=0):
        return tuple(center + Vector((u, 0, 0)) + slope*v + normal*d)
    n = 40 if b.lod == 0 else 20
    # A dark shallow chamber behind the circular shroud, visible through its
    # center. No solid body face remains behind this cell after cut_opening().
    tag(b.sheet('jinwen_roof15_well_back', rectangle(.337,.343),
                lambda u,v: point(u,v,-.170), 'grille_black', .010, normal),
        'fan_well_back')
    b.rim('jinwen_roof15_cell_frame', rectangle(.352,.363),
          rectangle(.328,.339), lambda u,v: point(u,v,.011),
          roof_mat, .042, normal)
    outer, inner = disk_loop(.302,n), disk_loop(.279,n)
    tag(b.rim('jinwen_roof15_fan_shroud', outer, inner,
              lambda u,v: point(u,v,-.022), 'graphite', .114, normal),
        'circular_fan_shroud')
    # Broad blade silhouettes remain darker than the hub. Exact blade number
    # is not resolved by either source photograph; six is an explicit estimate.
    verts, faces = [], []
    for i in range(6):
        a = i*math.tau/6
        shape = ((.085,-.035),(.246,-.028),(.270,.030),(.160,.082),(.085,.035))
        start = len(verts)
        for u,v in shape:
            uu, vv = u*math.cos(a)-v*math.sin(a), u*math.sin(a)+v*math.cos(a)
            verts.append(point(uu,vv,-.116+.08*v))
        faces.append(tuple(range(start,start+len(shape))))
    tag(b.poly('jinwen_roof15_fan_blades', verts, faces, 'grille_black', normal=normal),
        'approximate_fan_blades')
    # The shallow metallic hub is visibly domed, not an illuminated lamp.
    verts, faces = [], []
    for radius, depth in ((.106,-.105),(.122,-.074),(.108,-.047),(.076,-.034),(.025,-.029)):
        verts.extend(point(u,v,depth) for u,v in disk_loop(radius,n))
    for j in range(4):
        for i in range(n):
            q=(i+1)%n
            faces.append((j*n+i,j*n+q,(j+1)*n+q,(j+1)*n+i))
    faces.append(tuple(range(4*n,5*n)))
    hub=tag(b.poly('jinwen_roof15_metal_hub',verts,faces,'metal',normal=normal),
            'visible_metal_hub')
    for face in hub.data.polygons:
        face.use_smooth = len(face.vertices)==4
    # Visible thin, open circular safety cage. Rings and radial members are
    # physically separated from the dark chamber, not opaque texture panels.
    rings=(.145,.205,.268) if b.lod==0 else (.205,.268)
    for r in rings:
        pts=[point(u,v,.018) for u,v in disk_loop(r,n)]
        b.tube('jinwen_roof15_guard_ring',pts+[pts[0]],.0045,'graphite',sides=4)
    for i in range(8 if b.lod==0 else 4):
        a=i*math.tau/(8 if b.lod==0 else 4)
        b.tube('jinwen_roof15_guard_spoke',
               [point(.025*math.cos(a),.025*math.sin(a),.018),
                point(.289*math.cos(a),.289*math.sin(a),.018)],
               .0045,'graphite',sides=4)
    # Sparse straight strips follow the rectangular cover seen in the photos.
    for u in (-.315,-.18,.18,.315):
        b.tube('jinwen_roof15_guard_strip',
               [point(u,-.33,.024),point(u,.33,.024)],.004,'graphite',sides=4)


def cut_opening(b, shell, side):
    center, slope, normal = basis(side)
    center.x=(X0+X1)/2
    def point(u,v):
        return tuple(center+Vector((u,0,0))+slope*v+normal*.10)
    cutter=b.sheet('jinwen_roof15_opening_cutter',rectangle(.722,.352),
                   point,'black',.47,normal)
    b.cut(shell,cutter)


def apply(b):
    """Replace only the proven shoulder-fan area; return honest build counts."""
    if b.lod>=2:
        return {'lod': b.lod, 'fan_cells': 0, 'detail_omitted': True}
    roof_mat = 'jw_roof' if 'jw_roof' in b.g.MATERIAL_SPECS else 'roof'
    shell = next((o for o in bpy.context.scene.objects
                  if o.name.startswith('body_open_shell_v07')),None)
    if shell is None:
        raise RuntimeError('Jinwen roof conversion needs unjoined body_open_shell_v07')
    # The livery pass splits every painted face and duplicates its vertices.
    # Restore welded connectivity before Boolean subtraction; face materials
    # and the explicit paint boundaries remain intact.
    bm=bmesh.new()
    bm.from_mesh(shell.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(shell.data)
    bm.free()
    shell.data.update()
    removed=remove_old()
    for side in (-1,1):
        cut_opening(b,shell,side)
        for x in FAN_X:
            fan_cell(b,side,x)
        center,slope,normal=basis(side)
        for x in (X0,X1):
            pts=[tuple(Vector((x,side*TOP_Y,TOP_Z))+normal*.008),
                 tuple(Vector((x,side*EDGE_Y,EDGE_Z))+normal*.008)]
            b.tube('jinwen_roof15_outer_frame',pts,.015,roof_mat,sides=4)
    # The center crown is a thin real sheet, not a closure across fan mouths.
    crown=b.sheet('jinwen_roof15_flat_crown',rectangle((X1-X0)/2,TOP_Y),
                   lambda u,v: ((X0+X1)/2+u,v,TOP_Z), roof_mat,.025,(0,0,1))
    tag(crown,'retained_flat_crown')
    shell['jinwen_roof15_open_shoulder_apertures']=2
    bpy.context.scene['jinwen_roof15_fan_cells']=4
    bpy.context.scene['jinwen_roof15_external_estimate']=True
    return {'lod':b.lod,'fan_cells':4,'body_apertures':2,
            'removed_objects':len(removed),
            'retained_exhaust_layout':True,
            'far_side_arrangement':'mirrored visual reconstruction; not surveyed'}
