"""Photo-fitted cab markings and Jinwen door-side paint refinement.

The user-specified fleet/depot labels are customization, not a historical
allocation claim. Installed fonts supply converted outlines; no font binary or
reference photograph is copied. Paint is clipped into existing sheet polygons,
not a billboard over door apertures or louvers. Call after the v20 livery pass.
"""
from pathlib import Path
import bpy
from mathutils import Vector
from lettering_v20 import fitted_text, LATIN_FONT

CAB_X = 9.84
CAB_WIDTH = 1.00
CAB_HEIGHT = .148
CAB_Z = 2.355
DEPOT_WIDTH = .66
DEPOT_HEIGHT = .132
DEPOT_Z = 2.130
DEPOT_FONT = Path('C:/Windows/Fonts/simsun.ttc')
JW_CAB_X = 10.00
JW_CAB_WIDTH = .96
JW_CAB_HEIGHT = .155
JW_CAB_Z = 2.515
JW_SLASHES = (7.12, 7.98, 8.84)
JW_SLASH_WIDTH = .30
JW_OUTER_EDGE = 9.60
JW_SLOPE = .48
JW_CAB_BLUE_EDGE = 9.65
JW_CAB_BLUE_SLOPE = .35
VARIABLE_PREFIXES = ('cab_number', 'cab_depot', 'side_number', 'nose_number',
                     'jinwen_cab_number', 'jinwen_side_number', 'jinwen_nose_number',
                     'livery21_cab_', 'livery21_side_number', 'livery21_nose_number')


def _strictly_degenerate_triangle(points):
    """Exact zero cross product of stored float32 positions, evaluated in doubles.

    No area epsilon: valid sub-micrometre clipping slivers must survive. Blender's
    polygon.area may report cancellation noise on an exactly collinear polygon.
    """
    a,b,c=(tuple(p) for p in points)
    u=tuple(b[i]-a[i] for i in range(3)); v=tuple(c[i]-a[i] for i in range(3))
    return (u[1]*v[2]-u[2]*v[1]==0 and u[2]*v[0]-u[0]*v[2]==0
            and u[0]*v[1]-u[1]*v[0]==0)


def clean_clipped_mesh(mesh):
    """Drop only zero-area loop triangles, retaining each valid corner verbatim.

    Only polygons containing such a triangle are retriangulated, using Blender's
    pre-existing loop-triangle choices. This also eliminates coincident corners
    without exchanging their possibly different UV values on valid triangles.
    Returns a replacement mesh and a count report; an unaffected mesh is reused.
    """
    mesh.calc_loop_triangles()
    by_face={}; zero=[]
    for tri in mesh.loop_triangles:
        dead=_strictly_degenerate_triangle([mesh.vertices[i].co for i in tri.vertices])
        by_face.setdefault(tri.polygon_index,[]).append((tuple(tri.loops),dead))
        if dead:zero.append(tri.index)
    report={'strict_zero_area_triangles_removed':len(zero),'polygons_replaced':0,
            'valid_micro_triangles_retained':0}
    if not zero:return mesh,report
    old_normals=[tuple(n.vector) for n in mesh.corner_normals]
    face_loops=[]; materials=[]; smooth=[]
    for face in mesh.polygons:
        tris=by_face[face.index]
        if any(dead for _,dead in tris):
            report['polygons_replaced']+=1
            keep=[loops for loops,dead in tris if not dead]
            report['valid_micro_triangles_retained']+=len(keep)
        else:keep=[tuple(face.loop_indices)]
        for loops in keep:
            face_loops.append(loops);materials.append(face.material_index);smooth.append(face.use_smooth)
    result=bpy.data.meshes.new(mesh.name+'_valid')
    result.from_pydata([tuple(v.co) for v in mesh.vertices],[],
                      [tuple(mesh.loops[i].vertex_index for i in loops) for loops in face_loops])
    for mat in mesh.materials:result.materials.append(mat)
    for face,index,flag in zip(result.polygons,materials,smooth):
        face.material_index=index;face.use_smooth=flag
    loops_flat=[i for loops in face_loops for i in loops]
    for old_layer in mesh.uv_layers:
        layer=result.uv_layers.new(name=old_layer.name)
        for new_loop,old_loop in zip(layer.data,loops_flat):new_loop.uv=old_layer.data[old_loop].uv
    result.update()
    result.normals_split_custom_set([old_normals[i] for i in loops_flat])
    result.update()
    return result,report


def _split_attributes(polygon, plane):
    """Convex clipping with UV/normal interpolation, not XYZ-only clipping."""
    distances = [plane(p) for p in polygon]
    if min(distances) >= -1e-8 or max(distances) <= 1e-8:
        return [polygon]
    result = []
    for sign in (-1, 1):
        output = []
        for i, p in enumerate(polygon):
            q = polygon[(i+1) % len(polygon)]
            a, c = sign*distances[i], sign*distances[(i+1) % len(polygon)]
            if a >= 0:
                output.append(p)
            if a*c < 0:
                t = a/(a-c)
                output.append(tuple(p[j]+t*(q[j]-p[j]) for j in range(len(p))))
        if len(output) >= 3:
            result.append(output)
    return result


def jinwen_side_paint(x, z):
    """Only valid in the revised side ROI: |x| 5.7..10.78, z 1.925..3.95."""
    a = abs(x)
    if z >= 2.60 and a + JW_CAB_BLUE_SLOPE * (z - 2.60) >= JW_CAB_BLUE_EDGE:
        return 'jw_blue'
    q = a + JW_SLOPE * (z - 1.925)
    if z < 3.45 and q <= JW_OUTER_EDGE:
        return 'jw_white' if any(start <= q <= start + JW_SLASH_WIDTH for start in JW_SLASHES) else 'jw_blue'
    return 'jw_white'


def _paint_roi(p):
    return 5.70 <= abs(p[0]) <= 10.78 and abs(p[1]) > 1.20 and 1.925 <= p[2] < 3.95


def _repaint_side_mesh(obj, b):
    """Split eligible polygons, preserving original loops outside revised paint.

Split points interpolate UV and corner-normal values on the source face. Black
apertures, glass, roof, waistlines and all non-paint materials stay unchanged.
"""
    old = obj.data
    keys = [Path(m.name).name for m in old.materials]
    if not any(k in {'jw_blue', 'jw_white'} for k in keys):
        return False
    tf, inv = obj.matrix_world.copy(), obj.matrix_world.inverted()
    world = [tf @ v.co for v in old.vertices]
    uv_layers = list(old.uv_layers)
    old_normals = [tuple(n.vector) for n in old.corner_normals]
    vertices = [tuple(v.co) for v in old.vertices]
    faces, material_ids, smooth_flags, uvs, normals = [], [], [], [[] for _ in uv_layers], []
    materials = list(old.materials)
    slots = {Path(m.name).name: i for i, m in enumerate(materials)}
    for key in ('jw_blue', 'jw_white'):
        if key not in slots:
            slots[key] = len(materials)
            materials.append(b.mat(key))
    changed = 0
    # The planes delimit both the restricted editing region and new oblique
    # bands. All coefficients are metric photo fits, not factory measurements.
    # Reach past the innermost old v20 slash at |x|5.99, otherwise a white
    # remnant survives when moving all three separators toward the cab.
    planes = [lambda p, x=x: p[0]-x for x in (-10.78, -5.70, 0, 5.70, 10.78)]
    planes += [lambda p, z=z: p[2]-z for z in (1.925, 2.60, 3.45, 3.95)]
    for sign in (-1, 1):
        for edge in (*[v for a in JW_SLASHES for v in (a, a+JW_SLASH_WIDTH)], JW_OUTER_EDGE):
            planes.append(lambda p, s=sign, edge=edge: s*p[0]+JW_SLOPE*(p[2]-1.925)-edge)
        planes.append(lambda p, s=sign: s*p[0]+JW_CAB_BLUE_SLOPE*(p[2]-2.60)-JW_CAB_BLUE_EDGE)
    for face in old.polygons:
        points = [world[i] for i in face.vertices]
        eligible = (keys[face.material_index] in {'jw_blue', 'jw_white'}
                    and max(p.z for p in points) > 1.925 and min(p.z for p in points) < 3.95
                    and max(abs(p.y) for p in points) > 1.20
                    and max(p.x for p in points) > -10.78 and min(p.x for p in points) < 10.78
                    and (max(p.x for p in points) > 5.70 or min(p.x for p in points) < -5.70))
        if not eligible:
            faces.append(tuple(face.vertices)); material_ids.append(face.material_index)
            smooth_flags.append(face.use_smooth)
            normals.extend(old_normals[i] for i in face.loop_indices)
            for j, layer in enumerate(uv_layers):
                uvs[j].extend(tuple(layer.data[i].uv) for i in face.loop_indices)
            continue
        polygon = []
        for vi, li in zip(face.vertices, face.loop_indices):
            attrs = [v for layer in uv_layers for v in layer.data[li].uv]
            polygon.append((*world[vi], *attrs, *old_normals[li]))
        pieces = [polygon]
        for plane in planes:
            pieces = [part for piece in pieces for part in _split_attributes(piece, plane)]
        for piece in pieces:
            center = [sum(p[i] for p in piece)/len(piece) for i in range(3)]
            key = jinwen_side_paint(center[0], center[2]) if _paint_roi(center) else keys[face.material_index]
            start = len(vertices)
            vertices.extend(tuple(inv @ Vector(p[:3])) for p in piece)
            faces.append(tuple(range(start, len(vertices))))
            material_ids.append(slots[key]); smooth_flags.append(face.use_smooth)
            for p in piece:
                for j in range(len(uv_layers)):
                    uvs[j].append(tuple(p[3+2*j:5+2*j]))
                n = Vector(p[-3:])
                normals.append(tuple(n.normalized()) if n.length else tuple(face.normal))
            changed += key != keys[face.material_index] or len(pieces) > 1
    if not changed:
        return False
    mesh = bpy.data.meshes.new(old.name+'_livery21')
    mesh.from_pydata(vertices, [], faces)
    for mat in materials:
        mesh.materials.append(mat)
    for face, idx, smooth in zip(mesh.polygons, material_ids, smooth_flags):
        face.material_index = idx
        face.use_smooth = smooth
    for layer, values in zip(uv_layers, uvs):
        target = mesh.uv_layers.new(name=layer.name)
        for item, value in zip(target.data, values):
            item.uv = value
    mesh.update()
    mesh.normals_split_custom_set(normals)
    mesh,cleanup=clean_clipped_mesh(mesh)
    obj['livery21_zero_area_triangles_removed']=cleanup['strict_zero_area_triangles_removed']
    if b.lod == 2:
        # Retain every blue/white boundary but dissolve the coplanar clipping
        # diagonals inherited from two livery passes. Detailed LODs are untouched.
        from china_livery_v20 import compact_distant_paint
        compact_distant_paint(mesh)
    obj.data = mesh
    obj['livery21_paint_revision'] = 'door-side oblique blue/white boundaries'
    return True


def _move_branding(b):
    # Existing logo/operator outlines are retained; only their cab location is
    # corrected to stay centered in the white field after the bands move out.
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or not obj.name.startswith(('jinwen_jwr_logo_v19', 'jinwen_cab_operator')):
            continue
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        x = (min(p.x for p in points)+max(p.x for p in points))/2
        if abs(x) < 8:
            continue
        side = 1 if points[0].y > 0 else -1
        dx = (JW_CAB_X if x > 0 else -JW_CAB_X)-x
        inv = obj.matrix_world.inverted()
        for vertex, p in zip(obj.data.vertices, points):
            p.x += dx
            p.y = side*(b.side_y(p.x, p.z)+.011)
            vertex.co = inv @ p
        obj.data.update()
        obj['livery21_fixed_branding'] = True


def _tag(obj, role, value, side=0, end=0):
    obj['livery21_variable'] = True
    obj['livery21_role'] = role
    obj['livery21_text'] = value
    obj['livery21_side'] = side
    obj['livery21_end'] = end
    return obj


def variable_signage_objects():
    """Use this collection to export fleet-number meshes independently."""
    return sorted((o for o in bpy.context.scene.objects if o.get('livery21_variable')), key=lambda o: o.name)


def depot_width(depot):
    # Keep two-character custom operators at the same approximate glyph scale
    # as four-character bureau/depot codes, rather than stretching each glyph.
    return DEPOT_WIDTH * len(depot.replace(' ', '').replace('·', '')) / 4


def _replace_signage(b, jinwen, number, depot):
    from front_finish_v11 import _paint, _number_placement, NUMBER_FONT_SIZE
    if b.lod < 2:
        for font in (LATIN_FONT, DEPOT_FONT):
            if not font.is_file():
                raise FileNotFoundError(f'Required local outline font: {font}')
    for obj in list(bpy.context.scene.objects):
        if obj.get('livery21_variable') or obj.name.startswith(VARIABLE_PREFIXES):
            bpy.data.objects.remove(obj, do_unlink=True)
    if b.lod >= 2:
        return
    for side in (-1, 1):
        direction = -side
        obj = fitted_text(b, f'livery21_side_number_{side}', 'FXN5C '+number,
                          direction*1.24, side, 2.64, 2.76, .43, 'white')
        _tag(obj, 'side_number', 'FXN5C '+number, side)
        for end in (-1, 1):
            x = end*(JW_CAB_X if jinwen else CAB_X)
            width, height, z = (JW_CAB_WIDTH, JW_CAB_HEIGHT, JW_CAB_Z) if jinwen else (CAB_WIDTH, CAB_HEIGHT, CAB_Z)
            key = 'jw_red' if jinwen else 'white'
            obj = fitted_text(b, f'livery21_cab_number_{end}_{side}', 'FXN5C '+number,
                              x, side, z, width, height, key)
            _tag(obj, 'cab_number', 'FXN5C '+number, side, end)
            # The same physical cab keeps its end label on both sides. Small
            # Roman letters always follow the text in viewer reading direction.
            label = 'I' if end > 0 else 'II'
            ew = .020 if end > 0 else .045
            ex = x + direction*(width/2+.044+ew/2)
            obj = fitted_text(b, f'livery21_cab_end_{end}_{side}', label, ex, side,
                              z-height/2+.043, ew, .066, key)
            _tag(obj, 'cab_end', label, side, end)
            if not jinwen:
                obj = fitted_text(b, f'livery21_cab_depot_{end}_{side}', depot,
                                  x, side, DEPOT_Z, depot_width(depot), DEPOT_HEIGHT,
                                  'white', DEPOT_FONT)
                _tag(obj, 'cab_depot', depot, side, end)
    base, scale, _ = _number_placement()
    for end in (-1, 1):
        obj = _paint(b, f'livery21_nose_number_{end}', 'FXN5C '+number,
                     NUMBER_FONT_SIZE, base, end, scale=scale)
        if jinwen:
            obj.data.materials.clear(); obj.data.materials.append(b.mat('jw_red'))
        _tag(obj, 'nose_number', 'FXN5C '+number, end=end)


def apply(builder, jinwen=False, number='0051', depot='上局沪段'):
    """Idempotent per-scene postprocess; paint once, replace fleet labels often."""
    number = str(number)
    if len(number) != 4 or not number.isdigit():
        raise ValueError('FXN5C number must contain four digits')
    if not depot or not isinstance(depot, str):
        raise ValueError('A non-empty user-selected depot label is required')
    b = builder
    changed = []
    if jinwen:
        excluded = ('jinwen_', 'livery21_', 'side_fuxing', 'nose_fuxing',
                    'railway_emblem', 'sill_warning', 'cock_coloured_lever', 'bounds|',
                    'angular_windshield_surround', 'windscreen_angular_surround',
                    'windshield_surround', 'windshield_centre_pillar',
                    'windshield_lower_surround', 'eaves_return_lip')
        for obj in list(bpy.context.scene.objects):
            if (obj.type != 'MESH' or obj.name.startswith(excluded)
                    or obj.get('livery21_paint_revision')):
                continue
            if _repaint_side_mesh(obj, b):
                changed.append(obj.name)
        _move_branding(b)
    _replace_signage(b, jinwen, number, depot)
    if changed:
        from planar_shading_v13 import apply_planar_normals
        apply_planar_normals()
    b.g.ensure_uvs()
    bpy.context.view_layer.update()
    bpy.context.scene['livery21_number'] = number
    bpy.context.scene['livery21_depot'] = depot
    bpy.context.scene['livery21_jinwen'] = bool(jinwen)
    bpy.context.scene['livery21_scope'] = 'User-configured numbering; photo-fit outlines, not confirmed OEM fonts or historical allocations'
    return {'number': number, 'depot': depot, 'repainted_objects': changed,
            'variable_objects': [o.name for o in variable_signage_objects()]}
