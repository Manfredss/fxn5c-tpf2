"""Add the visibly missing running-gear fittings from supplied drawing 4.

This is an additive pass: the v21 frame, equipment cases, wheelsets, dampers,
and body/bogie linkage are not modified. Dimensions fit the supplied drawing;
unseen depth and far-side repetition are estimates, not factory measurements.

u points towards the nearest cab. The ribbed auxiliary case and open hanger
occupy the interval between the outer axle (u=1.8) and body pin (u=.54).
Do not identify the small cases as a particular subsystem without evidence.
"""
import json
from collections import Counter
from pathlib import Path

import bpy
from mathutils import Matrix
from bogie_details_v20 import Batch

AUXILIARY_U = 1.235
JUNCTION_U = 1.530
EVIDENCE = 'user codex-clipboard-6c1a8e86-7cab-4295-a66a-9a65002a1924.png, drawing 4'


class DetailBatch(Batch):
    """Track polygon ranges so geometry tests need not trust counters alone."""
    def __init__(self, builder):
        super().__init__(builder)
        self.ranges = []

    def add(self, name, verts, faces, mat='graphite', smooth=False):
        start = len(self.f)
        super().add(name, verts, faces, mat, smooth)
        self.ranges.append({'role': name, 'first_polygon': start,
                            'polygon_count': len(faces)})


def _auxiliary(m, end, side):
    """Ribbed rectangular case, separate open hanging yoke and small case."""
    def p(u, y, z):
        return end*u, side*y, z
    def profile(name, coords, y, depth, mat='graphite'):
        m.profile(name, [(end*u, z) for u,z in coords], side*y, depth, mat)
    u = AUXILIARY_U
    # Main housing is outside the springs; two roots visibly join the beam.
    m.box('auxiliary_case',p(u,1.385,1.094),(.350,.145,.350),'graphite',.022)
    m.box('auxiliary_lid_field',p(u,1.465,1.094),(.302,.014,.296),'spring_steel',.015)
    # Thin face border has an actual open inner loop, not an opaque plate.
    outer=[(end*(u+dx),z) for dx,z in ((-.167,.925),(.167,.925),(.167,1.263),(-.167,1.263))]
    inner=[(end*(u+dx),z) for dx,z in ((-.146,.945),(.146,.945),(.146,1.242),(-.146,1.242))]
    m.rim_profile('auxiliary_lid_border',outer,inner,side*1.480,.018,'graphite')
    for z in (1.002,1.110,1.218):
        m.box('auxiliary_horizontal_rib',p(u,1.490,z),(.295,.026,.018),'graphite',.003)
    for dx in (-.132,.132):
        m.box('auxiliary_upper_mount',p(u+dx,1.305,1.203),(.042,.190,.080),'graphite')
    # Open inverted yoke: two tapered cheeks and lower pin, daylight remains
    # between them. Upper tips overlap housing and lower tips overlap pin.
    for direction in (-1,1):
        outline=[(u+direction*.156,.944),(u+direction*.101,.944),
                 (u+direction*.025,.672),(u+direction*.071,.654)]
        profile('auxiliary_open_yoke_cheek',outline,1.443,.052,'cast_steel')
    m.cyl('auxiliary_lower_pin',p(u,1.444,.676),.048,.091,'cast_steel','Y',12 if not m.b.lod else 8)
    m.cyl('auxiliary_pin_head',p(u,1.496,.676),.025,.017,'metal','Y',8 if not m.b.lod else 6)
    m.box('auxiliary_rear_anchor',p(u,1.283,.697),(.112,.270,.054),'graphite',.006)
    # Adjacent smaller sealed housing is distinct from the main ribbed case.
    q = JUNCTION_U
    m.box('junction_small_case',p(q,1.384,1.008),(.157,.102,.249),'graphite',.012)
    m.box('junction_lid',p(q,1.441,1.008),(.133,.016,.221),'spring_steel',.008)
    for dx in (-.055,.055):
        m.box('junction_mount',p(q+dx,1.306,1.110),(.032,.160,.061),'graphite')
    if not m.b.lod:
        for dx in (-.051,.051):
            for z in (.916,1.101):
                m.cyl('junction_lid_screw',p(q+dx,1.455,z),.009,.011,'metal','Y',6)
        for dx in (-.122,.122):
            m.cyl('auxiliary_lid_screw',p(u+dx,1.500,1.243),.009,.012,'metal','Y',6)
        m.box('auxiliary_top_latch',p(u,1.490,1.275),(.056,.023,.035),'spring_steel',.003)
    # Only a short riser/return is new: the existing v20 air main is retained.
    # Raw Z values anticipate _fit_under_sill. Actual start is z=1.183,
    # within the existing rising mainline's radius, then the elbow drops to
    # z=1.148 at the new case's upper inside edge.
    raw_z=lambda z:.676+(z-.676)/.795
    branch=[p(1.105,1.301,raw_z(1.183)),p(1.105,1.343,raw_z(1.183)),
            p(1.130,1.390,raw_z(1.148)),p(u,1.410,raw_z(1.148)),
            p(u,1.410,raw_z(1.125))]
    m.tube('auxiliary_upper_pipe_return',branch,.013,'spring_steel',8 if not m.b.lod else 6)
    m.cyl('auxiliary_pipe_union',p(u,1.410,raw_z(1.135)),.022,.034,'graphite','Z',8 if not m.b.lod else 6)
    for t,y,z in ((1.105,1.326,raw_z(1.180)),(1.210,1.410,raw_z(1.148))):
        m.box('auxiliary_pipe_clip',p(t,y,z),(.038,.048,.027),'graphite',.002)
    if not m.b.lod:
        m.tube('junction_short_flex_lead',
               [p(q,1.413,.882),p(q,1.430,.836),p(q-.060,1.430,.801),
                p(q-.165,1.398,.801),p(u+.165,1.377,.928)],.010,'black',6)


def _fit_under_sill(m, first_vertex, side):
    """Keep the fitting below the existing return sill without editing it.

    The supplied drawing has a taller-looking exposed gap than the v21 side
    plate; compress only the new fittings vertically around their lower pin.
    Pipe return upper vertices sit behind the case and attach at the retained
    air-main height. This reserve also prevents the new detail cutting through
    the body-fixed return when the bogie yaws; tested separately on triangles.
    """
    for i in range(first_vertex,len(m.v)):
        x,y,z=m.v[i]
        m.v[i]=(x,y,.676+(z-.676)*.795)


def _red_damper_sleeves(m, side):
    """Concentric with actual old dampers; no guessed axle-based offsets."""
    for axle in (-1.8,1.8):
        def p(t):
            # Exactly _vertical_damper's low/high centres including -.18 Z.
            return axle-.060+.019*t,side*1.423,.587+.473*t
        m.tube('damper_red_upper_sleeve',[p(.780),p(.900)],.0275,'red_paint',12 if not m.b.lod else 8)
        for lo,hi in ((.763,.780),(.900,.917)):
            m.tube('damper_sleeve_edge_band',[p(lo),p(hi)],.029,'graphite',10 if not m.b.lod else 6)


def _assign_materials(obj, builder, jinwen):
    if not jinwen:
        return
    mapping={'graphite':'jw_frame','spring_steel':'jw_frame','cast_steel':'jw_spring'}
    for index,mat in enumerate(list(obj.data.materials)):
        short=Path(mat.name).name
        if short in mapping:
            obj.data.materials[index]=builder.mat(mapping[short])


def _uvs(mesh):
    layer=mesh.uv_layers.new(name='UVMap')
    for loop in mesh.loops:
        p=mesh.vertices[loop.vertex_index].co
        layer.data[loop.index].uv=(p.x*.071+.5,p.z*.14+p.y*.03)


def apply(builder, jinwen=False):
    """Return two separate additive meshes, each a direct actual bogie child.

    LOD0 can open the saved v21 source. LOD1 may use that same source with
    builder.lod=1; only supplemental meshes are exported. No LOD2 additions.
    Idempotent for the same LOD/style, rejects mixing new detail passes.
    """
    if builder.lod>=2:
        return []
    out=[]
    for index,end in ((1,1),(2,-1)):
        name=f'bogie22_details_b{index}'
        existing=bpy.data.objects.get(name)
        if existing:
            if existing.get('bogie22_lod')!=builder.lod or bool(existing.get('bogie22_jinwen'))!=bool(jinwen):
                raise RuntimeError('Remove only the old bogie22 additions before changing LOD/style')
            out.append(existing)
            continue
        parent=bpy.data.objects.get(f'b{index}_grp')
        if parent is None:
            raise RuntimeError(f'Missing actual bogie parent b{index}_grp')
        m=DetailBatch(builder)
        for side in (-1,1):
            first_vertex=len(m.v)
            _auxiliary(m,end,side)
            _fit_under_sill(m,first_vertex,side)
            _red_damper_sleeves(m,side)
        obj=m.finish(name,parent)
        obj.matrix_parent_inverse=Matrix.Identity(4)
        obj.matrix_basis=Matrix.Identity(4)
        _assign_materials(obj,builder,jinwen)
        _uvs(obj.data)
        obj['bogie_revision']='v22_reference_drawing_additions'
        obj['detail_v20_component']='v22_addition_only'
        obj['geometry_basis']=EVIDENCE
        obj['bogie22_lod']=builder.lod
        obj['bogie22_jinwen']=bool(jinwen)
        obj['bogie22_bogie']=index
        obj['v22_part_id']=obj.name
        obj['attachment']=f'b{index}'
        obj['bogie22_cab_direction']=end
        obj['bogie22_roles_json']=json.dumps(m.ranges,separators=(',',':'))
        obj['bogie22_scope']='additive moving fittings; original frame/cases/linkage untouched'
        obj['bogie22_dimensions']='drawing-fit; concealed depth and opposite-side repetition estimated'
        obj.data.calc_loop_triangles()
        obj['bogie22_triangles']=len(obj.data.loop_triangles)
        limit=6000 if builder.lod==0 else 2000
        if obj['bogie22_triangles']>limit:
            raise RuntimeError(f'{name} LOD{builder.lod} exceeds {limit} triangle budget')
        out.append(obj)
    bpy.context.view_layer.update()
    return out


def summary(objects):
    """Geometry-derived bounds and semantic inventory for the release audit."""
    rows=[]
    for obj in objects:
        local=[v.co for v in obj.data.vertices]
        world=[obj.matrix_world@v for v in local]
        bounds=lambda ps:[[min(p[k] for p in ps),max(p[k] for p in ps)] for k in range(3)]
        obj.data.calc_loop_triangles()
        rows.append({'name':obj.name,'parent':obj.parent.name,
                     'lod':int(obj['bogie22_lod']),'triangles':len(obj.data.loop_triangles),
                     'local_bounds':bounds(local),'world_bounds':bounds(world),
                     'components':{k[10:]:int(v) for k,v in obj.items() if k.startswith('component_')}})
    return rows
