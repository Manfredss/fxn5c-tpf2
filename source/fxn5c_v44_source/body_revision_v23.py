"""Targeted common FXN5C body mount and cab-number corrections.

The supplied side drawing's 71 px cap-to-gauge separation is scaled by the
~170 px/1.8 m adjacent-axle spacing, hence 0.75 m. Reading direction is -side,
not a blind world-X mirror. These are visual reconstruction dimensions.
"""
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from lettering_v20 import LATIN_FONT

GAUGE_X = .19
FILLER_LEFT_OF_GAUGE = .75
FILLER_Z = 1.55
PAINT_OFFSET = .0007
CAB_NUMBER_OUTLINE_OFFSET = .006
FILLER_PARTS = ('fuel_neck_recess_v05', 'fuel_neck_rim_v05',
                'fuel_cap_v05', 'fuel_cap_crossbar')


def _world_points(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def _bounds(obj):
    p = _world_points(obj)
    return [(min(v[i] for v in p), max(v[i] for v in p)) for i in range(3)]


def _transform_vertices(obj, transform):
    inverse = obj.matrix_world.inverted()
    for vert in obj.data.vertices:
        vert.co = inverse @ Vector(transform(obj.matrix_world @ vert.co))
    obj.data.update()


def _body_tree():
    vertices, faces = [], []
    for name in ('body_open_shell_v07', 'chassis_sill'):
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise RuntimeError('Missing body paint host: '+name)
        base = len(vertices)
        vertices.extend(_world_points(obj))
        faces.extend(tuple(base+i for i in f.vertices) for f in obj.data.polygons)
    return BVHTree.FromPolygons(vertices, faces)


def conform_paint(obj, side, tree=None):
    """Seat decal vertices on actual fixed body faces, not a nominal width."""
    tree = tree or _body_tree()
    gaps = []
    def seat(p):
        hit, normal, index, distance = tree.ray_cast(Vector((p.x, side*3, p.z)), Vector((0,-side,0)), 4)
        if hit is None:
            raise RuntimeError(f'Unbacked paint vertex: {obj.name}, {tuple(p)}')
        gaps.append(abs(p.y-hit.y))
        return (p.x, hit.y+side*PAINT_OFFSET, p.z)
    _transform_vertices(obj, seat)
    obj['body23_supported_paint'] = True
    obj['body23_paint_gap_m'] = PAINT_OFFSET
    return max(gaps, default=0)


def _move_filler(builder, jinwen, side, tree):
    chosen = [o for o in bpy.context.scene.objects if o.type=='MESH'
              and o.name.startswith(FILLER_PARTS)
              and sum(_bounds(o)[1])*side>0]
    if not chosen:
        # Existing LOD1 intentionally omits the small service markings/neck.
        if builder.lod>0:
            return []
        raise RuntimeError('Missing LOD0 fuel neck assembly')
    if len(chosen)!=4:
        raise RuntimeError(f'Expected four fuel neck pieces: {len(chosen)}')
    new_x=GAUGE_X+side*FILLER_LEFT_OF_GAUGE
    for obj in chosen:
        # Compress only projection depth. The original four nested cylinders
        # overlap, and retain the same overlap after this affine remapping.
        def move(p):
            return (p.x+side*FILLER_LEFT_OF_GAUGE,
                    side*(1.648+(abs(p.y)-1.6165)*(.031/.0795)),
                    p.z+FILLER_Z-1.445)
        _transform_vertices(obj, move)
        obj['body23_filler'] = True
    host_y=1.65 if jinwen else 1.61
    rear=host_y-.007
    front=1.652
    collar=builder.cyl('fuel_mount_collar_v23',(new_x,side*((rear+front)/2),FILLER_Z),
                       .098,front-rear,'jw_frame' if jinwen else 'graphite','Y')
    collar['body23_attachment']='filler_to_sill'
    # Place all cap instructions to the reading-right, respecting the actual
    # stepped CR sill surface and the continuous Jinwen white fascia.
    for obj in list(bpy.context.scene.objects):
        if obj.type!='MESH' or not obj.name.startswith(('fuel_label_v05','fuel_warning_')):
            continue
        bounds=_bounds(obj)
        if sum(bounds[1])*side<=0:continue
        cx=sum(bounds[0])/2; cz=sum(bounds[2])/2
        warning=obj.name.startswith('fuel_warning_')
        target_x=new_x-side*(.410 if warning else .235)
        # The complete warning lockup moves as a unit; retain its layered
        # red header/ring/slash, now on the white sticker's real support.
        dz=1.525-1.445 if warning else 1.553-cz
        dx=target_x-(.4 if warning else cx)
        _transform_vertices(obj,lambda p:(p.x+dx,p.y,p.z+dz))
        if obj.name.startswith('fuel_label_v05') and jinwen:
            obj.data.materials.clear();obj.data.materials.append(builder.mat('graphite'))
        original_depth=[abs(p.y) for p in _world_points(obj)]
        depth_span=max(original_depth)-min(original_depth)
        conform_paint(obj,side,tree)
        # Paint layers must not fight for the same depth. Only the base paper
        # is 0.7 mm proud; red details sit another 0.1 mm above it.
        if warning and not obj.name.startswith('fuel_warning_label'):
            # Ring/slash are thin closed tubes, not flat decals. Retain a
            # small but nonzero thickness so their sidewalls do not collapse
            # into zero-area triangles when seating the instruction sticker.
            inv=obj.matrix_world.inverted()
            for vert,old_y in zip(obj.data.vertices,original_depth):
                p=obj.matrix_world@vert.co
                relief=.0001+(.00015*(old_y-min(original_depth))/depth_span if depth_span>1e-5 else 0)
                vert.co=inv@Vector((p.x,p.y+side*relief,p.z))
            obj.data.update()
    return chosen+[collar]


def _support_gauge(builder, jinwen, side):
    gauges=[o for o in bpy.context.scene.objects if o.type=='MESH'
            and o.name.startswith('fuel_level_gauge_dark') and sum(_bounds(o)[1])*side>0]
    if not gauges:return []
    # The gauge was a decal across a 0.38 m cabinet gap. Add the physical
    # slender housing behind it, penetrating the fuel tank's Y=1.20 side.
    rear,front=1.190,1.5714
    mount=builder.box('fuel_gauge_mount_v23',(GAUGE_X,side*((rear+front)/2),.905),
                    (.17,front-rear,.730),'jw_frame' if jinwen else 'graphite',.010)
    mount['body23_attachment']='gauge_to_fuel_tank'
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not obj.name.startswith(('gauge_mount_screw','fuel_gauge_divider')):continue
        if sum(_bounds(obj)[1])*side<=0:continue
        if obj.name.startswith('gauge_mount_screw'):
            _transform_vertices(obj,lambda p:(p.x,p.y-side*.004,p.z))
            obj['body23_attachment']='gauge_screw_to_bezel'
        elif obj.name.startswith('fuel_gauge_divider'):
            _transform_vertices(obj,lambda p:(GAUGE_X+(p.x-GAUGE_X)*(.078/.070),p.y,p.z))
            obj['body23_attachment']='gauge_divider_to_bezel'
    return [mount]


def apply_common(builder, jinwen=False):
    """Apply after livery23 paint_geometry, before saving the common body."""
    if builder.lod>=2:return {'lod':builder.lod,'changed':False}
    if bpy.context.scene.get('body23_common'):
        raise RuntimeError('body23 common revision already applied')
    tree=_body_tree()
    for side in (-1,1):
        _move_filler(builder,jinwen,side,tree)
        _support_gauge(builder,jinwen,side)
    builder.g.ensure_uvs()
    bpy.context.view_layer.update()
    bpy.context.scene['body23_common']=True
    return {'lod':builder.lod,'changed':True,'filler_offset_reading_x':-.75,
            'filler_z':FILLER_Z,'gauge_backing':'physical tank-supported housing'}


def _bold_mesh(builder, old, tree):
    bounds=_bounds(old)
    width=bounds[0][1]-bounds[0][0];height=bounds[2][1]-bounds[2][0]
    x=sum(bounds[0])/2;z=sum(bounds[2])/2
    side=int(old.get('livery21_side',1 if sum(bounds[1])>0 else -1))
    value=old.get('livery21_text',old.get('livery19_text'))
    if not value:raise RuntimeError('Missing cab number text '+old.name)
    bpy.ops.object.text_add()
    obj=bpy.context.object;obj.name='body23_bold_temp'
    curve=obj.data;curve.body=value
    curve.font=bpy.data.fonts.load(str(LATIN_FONT),check_existing=True)
    curve.size=1;curve.space_character=1.04
    curve.resolution_u=4 if builder.lod==0 else 2
    curve.offset=CAB_NUMBER_OUTLINE_OFFSET
    curve.extrude=0
    bpy.ops.object.convert(target='MESH')
    low=Vector((min(v.co.x for v in obj.data.vertices),min(v.co.y for v in obj.data.vertices),0))
    high=Vector((max(v.co.x for v in obj.data.vertices),max(v.co.y for v in obj.data.vertices),0))
    centre=(low+high)/2
    for vert in obj.data.vertices:
        p=vert.co.copy()
        vert.co=(x-side*(p.x-centre.x)*width/(high.x-low.x),side*1.65,
                 z+(p.y-centre.y)*height/(high.y-low.y))
    # Keep the existing object/variable-signage identity, not a new unexported
    # overlay. The native fleet path exports these exact tagged objects.
    for material in old.data.materials:obj.data.materials.append(material)
    old_data=old.data;old.data=obj.data
    bpy.data.objects.remove(obj,do_unlink=True)
    if old_data.users==0:bpy.data.meshes.remove(old_data)
    old['body23_number_outline_offset']=CAB_NUMBER_OUTLINE_OFFSET
    old['body23_original_footprint_m']=[x,z,width,height]
    conform_paint(old,side,tree)


def apply_number_weight(builder):
    """Call after each livery21._replace_signage for all ten variants."""
    if builder.lod>=2:return []
    tree=_body_tree();changed=[]
    for obj in list(bpy.context.scene.objects):
        if obj.get('livery21_role')=='cab_number':
            _bold_mesh(builder,obj,tree);changed.append(obj.name)
        elif obj.get('livery21_role') in ('cab_end','cab_depot'):
            side=int(obj.get('livery21_side',1 if sum(_bounds(obj)[1])>0 else -1))
            conform_paint(obj,side,tree)
    if len(changed)!=4:raise RuntimeError(f'Four cab numbers required, got {len(changed)}')
    builder.g.ensure_uvs();bpy.context.view_layer.update()
    return changed
