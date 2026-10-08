"""Append-only body-fixed equipment matching the user's v22 drawings.

Coordinates are a visual reconstruction, not manufacturer dimensions or a
claim to identify the concealed subsystem. The negative-X cabinet-end stack
is DISTINCT from the existing positive-X pair of large transverse tanks.
Existing v21 surfaces, pipework, paint, bogies and animation are not edited.
"""
import json
import math
import bpy
from bogie_details_v20 import Batch

GAP_X = -2.49
# Drawing 2: upper/lower visible diameters about 31/41 pixels (~0.76).
STACK_LEVELS = ((.73, .178), (1.12, .135))
EXPECTED_OBJECTS = ('body22_gap_sm', 'body22_gap_sp',
                    'body22_nose_em_sm', 'body22_nose_em_sp',
                    'body22_nose_ep_sm', 'body22_nose_ep_sp')


class EquipmentBatch(Batch):
    """Retain per-primitive provenance inside each inexpensive batched mesh."""
    def __init__(self, builder, jinwen):
        super().__init__(builder)
        self.jinwen = jinwen
        self.parts = []
        self.endpoints = []

    def add(self, name, verts, faces, mat='graphite', smooth=False):
        verts = list(verts); faces = list(faces)
        if self.jinwen:
            mat = {'graphite':'jw_frame', 'spring_steel':'jw_frame'}.get(mat,mat)
        start_v, start_f = len(self.v), len(self.f)
        super().add(name, verts, faces, mat, smooth)
        self.parts.append(dict(id=name, vertex_range=[start_v,len(self.v)],
            polygon_range=[start_f,len(self.f)], material=mat,
            bounds=[[min(p[i] for p in verts),max(p[i] for p in verts)] for i in range(3)]))

    def terminal(self, part, point, support):
        self.endpoints.append(dict(part=part, point=list(point), support=support))

    def finish_body(self, name, role):
        obj = super().finish(name, None)
        # Batch.finish defaults describe a bogie; replace them for static body
        # additions so exporter/auditor ownership cannot be misinterpreted.
        for key in ('bogie_revision','detail_v20_component','triangles_v20'):
            if key in obj: del obj[key]
        obj['v22_part_id'] = name
        obj['attachment'] = 'body'
        obj['detail_v22_component'] = role
        obj['geometry_basis'] = 'User v22 drawings 2/3; estimated hidden depth; original authored mesh'
        obj['v22_lod'] = self.b.lod
        obj['v22_components'] = json.dumps(self.parts, separators=(',',':'))
        obj['v22_supported_endpoints'] = json.dumps(self.endpoints, separators=(',',':'))
        obj['v22_component_counts'] = json.dumps(dict(self.counts), sort_keys=True)
        obj.data.calc_loop_triangles()
        obj['v22_triangles'] = len(obj.data.loop_triangles)
        return obj


def _housing(m, side, z, radius):
    """Side-facing round casing with a shallow tapered lid, not another tank."""
    n = 20 if m.b.lod == 0 else 8
    m.cyl('stack_housing', (GAP_X,side*1.32,z),radius,.21,'graphite',segments=n)
    # Three short rings form a modest dished lid and folded edge. This makes
    # the two distinct circles legible from side/oblique views.
    verts=[]
    for rr,yy in ((radius,1.418),(radius*.88,1.468),(radius*.47,1.490)):
        verts.extend((GAP_X+rr*math.cos(i*math.tau/n),side*yy,
                      z+rr*math.sin(i*math.tau/n)) for i in range(n))
    faces=[(k*n+i,k*n+(i+1)%n,(k+1)*n+(i+1)%n,(k+1)*n+i)
           for k in range(2) for i in range(n)]
    faces.append(tuple(range(2*n,3*n)))
    m.add('stack_dished_lid',verts,faces,'spring_steel',[True]*(2*n)+[False])
    m.cyl('stack_lid_boss',(GAP_X,side*1.50,z),.031,.036,'graphite',segments=8)
    # Two ears connect the case back to the common steel rack.
    for dx in (-.105,.105):
        m.box('stack_mount_ear',(GAP_X+dx,side*1.225,z),(.054,.10,.075),'graphite')
    if m.b.lod==0:
        for angle in (math.pi/4,3*math.pi/4,5*math.pi/4,7*math.pi/4):
            rr=radius*.87
            m.cyl('stack_cover_screw',(GAP_X+rr*math.cos(angle),side*1.466,
                  z+rr*math.sin(angle)),.009,.012,'metal',segments=6)


def _gap(builder, jinwen, side):
    m=EquipmentBatch(builder,jinwen)
    y=lambda value: side*value
    # Rack top overlaps the underside of the existing chassis sill (Z1.355).
    # Bottom/cabinet brace intersects the cabinet end X=-2.16; it is not hung
    # in space. The two circles stay outside the fuel tank X>=-2.20.
    m.box('stack_back_rack',(GAP_X,y(1.205),.965),(.292,.072,.940),'graphite')
    m.box('stack_sill_mount',(GAP_X,y(1.270),1.367),(.360,.236,.076),'graphite')
    m.box('stack_cabinet_brace',(-2.335,y(1.305),.555),(.450,.230,.058),'graphite')
    for z,r in STACK_LEVELS: _housing(m,side,z,r)

    # Front service line intersects both centre bosses; both ends are seated
    # in visible fittings instead of terminating in empty air.
    path=[(GAP_X,y(1.514),.73),(GAP_X,y(1.532),.78),
          (GAP_X,y(1.532),1.07),(GAP_X,y(1.514),1.12)]
    m.tube('stack_interconnect',path,.013,'ochre',6 if builder.lod==0 else 4)
    for z in (.807,1.035):
        m.cyl('stack_line_union',(GAP_X,y(1.532),z),.022,.035,'metal','Z',6)
    m.terminal('stack_interconnect',path[0],'lower_stack_lid_boss')
    m.terminal('stack_interconnect',path[-1],'upper_stack_lid_boss')

    # A small vertical valve/filter-like silhouette fills the remaining
    # cabinet-end gap. Deliberately generic names avoid assigning its function.
    vx=-3.005
    m.box('gap_sill_mount',(vx,y(1.29),1.372),(.160,.225,.070),'graphite')
    m.cyl('gap_vertical_unit',(vx,y(1.30),1.160),.061,.380,'spring_steel','Z',12 if builder.lod==0 else 6)
    for z in (1.035,1.255):
        m.cyl('gap_unit_band',(vx,y(1.30),z),.076,.038,'graphite','Z',8)
    m.box('gap_unit_red_tab',(vx,y(1.391),1.262),(.051,.035,.064),'red_paint')
    # Main exposed return rises into the sill beside the case. It does not
    # falsely join the rotating bogie, and has the same support at LOD1 where
    # the old high-detail airline is omitted.
    path=[(vx,y(1.30),1.16),(-2.805,y(1.30),1.16),
          (-2.775,y(1.30),1.205),(-2.775,y(1.30),1.377)]
    m.tube('gap_upper_return',path,.021,'spring_steel',8 if builder.lod==0 else 4)
    m.terminal('gap_upper_return',path[0],'gap_vertical_unit')
    m.terminal('gap_upper_return',path[-1],'chassis_sill')
    path=[(vx,y(1.30),1.030),(-2.90,y(1.30),.993),
          (-2.725,y(1.31),.993),(GAP_X-STACK_LEVELS[1][1],y(1.32),1.12)]
    m.tube('gap_lower_return',path,.015,'ochre',6 if builder.lod==0 else 4)
    m.terminal('gap_lower_return',path[0],'gap_vertical_unit')
    m.terminal('gap_lower_return',path[-1],'upper_stack_housing')
    if builder.lod==0:
        # Join the extant v21 airline without claiming its hidden continuation.
        path=[(-2.775,y(1.30),1.278),(-2.775,y(1.40),1.30),(-2.775,y(1.45),1.30)]
        m.tube('gap_airline_branch',path,.014,'spring_steel',6)
        m.terminal('gap_airline_branch',path[0],'gap_upper_return')
        m.terminal('gap_airline_branch',path[-1],'underframe_airline')
        m.cyl('gap_airline_tee',path[-1],.028,.058,'graphite','X',8)
        for x in (-2.62,-2.36):
            m.cyl('stack_mount_bolt',(x,y(1.388),1.362),.012,.014,'metal',segments=6)
    return m.finish_body('body22_gap_s'+('p' if side>0 else 'm'),'cabinet_end_stack')


def _nose(builder,jinwen,end,side):
    m=EquipmentBatch(builder,jinwen)
    p=lambda x,y,z:(end*x,side*y,z)
    # Everything is beyond the neutral bogie end |X|9.30. Pipes sit inward
    # of the pilot return's |Y|1.571 inner face and below its diagonal aperture.
    # Upper pipe terminals and mounting shoes penetrate the fixed sill.
    for x in (9.59,10.25):
        m.box('nose_pipe_sill_shoe',p(x,1.29,1.370),(.103,.215,.078),'graphite')
    path=[p(10.25,1.29,1.382),p(10.25,1.29,1.230),
          p(10.12,1.29,1.144),p(9.80,1.29,1.144),
          p(9.59,1.29,1.267),p(9.59,1.29,1.382)]
    m.tube('nose_upper_hardline',path,.024,'spring_steel',8 if builder.lod==0 else 4)
    m.terminal('nose_upper_hardline',path[0],'chassis_sill')
    m.terminal('nose_upper_hardline',path[-1],'chassis_sill')
    path=[p(10.25,1.29,1.275),p(10.13,1.34,1.140),
          p(9.85,1.34,1.044),p(9.65,1.34,1.044),
          p(9.59,1.34,1.117),p(9.59,1.29,1.270)]
    m.tube('nose_lower_hardline',path,.018,'graphite',6 if builder.lod==0 else 4)
    m.terminal('nose_lower_hardline',path[0],'nose_upper_hardline')
    m.terminal('nose_lower_hardline',path[-1],'nose_upper_hardline')
    # Small upright union below the inclined opening. The central lead ends
    # inside the lower line; the cap is closed, not an unsupported pipe tip.
    m.cyl('nose_vertical_fitting',p(9.65,1.34,1.044),.034,.143,'metal','Z',8 if builder.lod==0 else 6)
    m.cyl('nose_fitting_cap',p(9.65,1.34,.971),.046,.032,'graphite','Z',8 if builder.lod==0 else 6)
    for x,z in ((9.59,1.307),(10.25,1.294)):
        m.cyl('nose_hardline_union',p(x,1.29,z),.037,.052,'graphite','Z',8 if builder.lod==0 else 6)
    # Tie the visible service lines to a shallow bracket behind the pilot;
    # unlike the drawing's painted silhouette this is a real depth connection.
    m.box('nose_pipe_support_web',p(9.80,1.232,1.240),(.083,.058,.269),'graphite')
    m.box('nose_pipe_clamp',p(9.80,1.296,1.148),(.065,.138,.065),'graphite')
    if builder.lod==0:
        for x,z in ((9.59,1.343),(10.25,1.343),(9.80,1.146)):
            m.cyl('nose_support_fastener',p(x,1.399 if x!=9.80 else 1.365,z),.011,.014,'metal',segments=6)
    name='body22_nose_e'+('p' if end>0 else 'm')+'_s'+('p' if side>0 else 'm')
    return m.finish_body(name,'nose_recess_pipework')


def apply(builder,jinwen=False):
    """Return append-only body objects; LOD2 intentionally gains no polygons."""
    if builder.lod>=2:return []
    if any(bpy.data.objects.get(name) for name in EXPECTED_OBJECTS):
        raise RuntimeError('v22 body additions already exist; refusing duplicate geometry')
    added=[_gap(builder,jinwen,side) for side in (-1,1)]
    added += [_nose(builder,jinwen,end,side) for end in (-1,1) for side in (-1,1)]
    bpy.context.view_layer.update()
    triangles=sum(o['v22_triangles'] for o in added)
    budget=12000 if builder.lod==0 else 2500
    if triangles>budget:raise RuntimeError(f'Body v22 LOD{builder.lod} budget exceeded: {triangles}>{budget}')
    assert tuple(o.name for o in added)==EXPECTED_OBJECTS
    return added
