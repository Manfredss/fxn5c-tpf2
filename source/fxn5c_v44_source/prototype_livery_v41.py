"""Isolated FXN5C0001 prototype paint and solid gold Fuxing lettering.

Apply only to a derived CR v40 scene, after prototype head/access geometry.
Photographs supply visible appearance, not factory paint or relief dimensions.
Existing font outlines are reused as mesh data; no font or photo is loaded.
"""
from collections import Counter, defaultdict
from pathlib import Path
import math
import bpy
import bmesh
from mathutils import Vector
from livery_revision_v21 import _split_attributes, clean_clipped_mesh

MATERIAL_SPECS = {
    'proto_red': ((.40, .014, .025, 1), .38, .12),
    'proto_gold': ((.68, .39, .055, 1), .30, .78),
    'proto_yellow': ((.95, .57, .012, 1), .36, .10),
    'proto_roof': ((.041, .048, .060, 1), .61, .23),
}
WAIST_BOTTOM = 1.80
WAIST_TOP = 1.92
RELIEF_DEPTH = .0095
RELIEF_BEVEL = .0008
PREFIX = 'proto41_'
NUMBER = 'FXN5C0001'


def register_materials(gen):
    gen.MATERIAL_SPECS.update(MATERIAL_SPECS)
    for key in MATERIAL_SPECS:
        gen.material(key)


def native_material_map(reference):
    """For unchanged animated CR mesh copies: replace paint slots only.

    Yellow here is the old production wave split on radiator/shutter geometry,
    not a request to recolor unrelated running-gear safety marks.
    """
    mapping = {'blue': 'proto_red', 'light_blue': 'proto_red',
               'yellow': 'proto_red', 'roof': 'proto_roof'}
    prefix = 'vehicle/train/fxn5c/'
    clean = reference.lstrip('/')
    if clean.startswith(prefix) and clean.endswith('.mtl'):
        key = clean[len(prefix):-4]
        if key in mapping:
            return prefix + mapping[key] + '.mtl'
    return reference


def _key(material):
    return Path(material.name).name.removesuffix('.mtl') if material else ''


def _world(obj):
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def _assign(obj, builder, key):
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    obj.data.materials.clear()
    obj.data.materials.append(builder.mat(key))
    for face in obj.data.polygons:
        face.material_index = 0


def _mesh(name, vertices, faces, builder, key):
    mesh = bpy.data.meshes.new(name + '_mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(builder.mat(key))
    uv = mesh.uv_layers.new(name='UVMap')
    for face in mesh.polygons:
        for loop in face.loop_indices:
            point = mesh.vertices[mesh.loops[loop].vertex_index].co
            uv.data[loop].uv = ((point.x + point.y) / 5, point.z / 5)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj['prototype41_livery'] = True
    return obj


def _solid_letter(obj, builder):
    """Close original glyph ink, including each counter, then bevel its rim."""
    points = _world(obj)
    side = 1 if points[0].y > 0 else -1
    outer = sum(abs(p.y) for p in points) / len(points)
    assert max(abs(abs(p.y) - outer) for p in points) < 2e-6
    front, directed = [], []
    for polygon in obj.data.polygons:
        face = list(polygon.vertices)
        normal = sum(((points[b] - points[a]).cross(points[c] - points[a])
                      for a, b, c in [(face[0], face[i], face[i + 1])
                                       for i in range(1, len(face) - 1)]), Vector())
        if normal.y * side < 0:
            face.reverse()
        front.append(face)
        directed.extend(zip(face, face[1:] + face[:1]))
    counts = Counter(tuple(sorted(edge)) for edge in directed)
    assert max(counts.values()) <= 2, 'Nonmanifold source glyph'
    boundary = [(a, b) for a, b in directed if counts[tuple(sorted((a, b)))] == 1]
    assert boundary
    count = len(points)
    base = outer - RELIEF_DEPTH
    vertices = [(p.x, side * base, p.z) for p in points] + [tuple(p) for p in points]
    faces = [list(reversed(face)) for face in front]
    faces += [[i + count for i in face] for face in front]
    faces += [(a, b, b + count, a + count) for a, b in boundary]
    name = obj.name
    new = _mesh(PREFIX + 'relief_' + ('p' if side > 0 else 'm'), vertices, faces, builder, 'proto_gold')
    # Coplanar triangulation is retained. Only the physically exposed hard rim
    # is chamfered; no projected dark silhouette or hidden duplicate ink layer.
    bevel = new.modifiers.new('true_gold_edge_bevel', 'BEVEL')
    bevel.width = RELIEF_BEVEL
    bevel.segments = 1
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = .55
    bevel.use_clamp_overlap = True
    bpy.context.view_layer.objects.active = new
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    bm = bmesh.new()
    bm.from_mesh(new.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    assert all(edge.is_manifold for edge in bm.edges), 'Relief must be a closed solid'
    volume = bm.calc_volume(signed=True)
    assert volume > 0, 'Gold solid has reversed normals or zero volume'
    bm.to_mesh(new.data)
    bm.free()
    new.data.update()
    new['prototype41_role'] = 'solid_fuxing_relief'
    new['prototype41_original_outline'] = name
    new['prototype41_side'] = side
    new['prototype41_depth_m'] = RELIEF_DEPTH
    new['prototype41_bevel_m'] = RELIEF_BEVEL
    new['prototype41_not_planar_shadow'] = True
    new['prototype41_visual_estimate'] = True
    new['livery19_text'] = '复 兴'
    bpy.data.objects.remove(obj, do_unlink=True)
    return dict(name=new.name, source=name, side=side, depth_m=RELIEF_DEPTH,
                bevel_m=RELIEF_BEVEL, signed_volume_m3=volume, closed=True,
                source_boundary_edges=len(boundary), vertices=len(new.data.vertices),
                polygons=len(new.data.polygons))


def _number_glyphs(obj, side, end):
    """Separate the nine existing FXN5C 0051 glyphs without reopening fonts."""
    points = _world(obj)
    coords = [Vector((-side * p.x if side else end * p.y, p.z)) for p in points]
    parent = list(range(len(points)))
    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    for face in obj.data.polygons:
        first = find(face.vertices[0])
        for i in face.vertices[1:]:
            parent[find(i)] = first
    parts = defaultdict(list)
    for index in range(len(points)):
        parts[find(index)].append(index)
    groups = sorted(parts.values(), key=lambda g: min(coords[i].x for i in g))
    # A font glyph may contain multiple disconnected filled islands. Group any
    # overlapping horizontal extents before checking the known nine letters.
    merged = []
    for group in groups:
        lo = min(coords[i].x for i in group)
        if merged and lo < max(coords[i].x for i in merged[-1]) - 1e-6:
            merged[-1].extend(group)
        else:
            merged.append(group)
    assert len(merged) == 9, ('Unexpected original number glyph inventory', obj.name, len(merged))
    return points, coords, merged


def _front_point(builder, end, y, z, depth=.0016):
    # Import is local so a side-only probe can run before head is finished.
    try:
        import prototype_head_v41 as head
    except ImportError:
        return Vector((end * (builder.front_x(z) + depth), y, z))
    return Vector(head.point(end, y, z, depth))


def _replace_number(obj, builder):
    role = obj.get('livery21_role')
    side = int(obj.get('livery21_side', 0))
    end = int(obj.get('livery21_end', 0))
    points, coords, groups = _number_glyphs(obj, side, end)
    groups_out = [groups[i] for i in (0, 1, 2, 3, 4, 5, 5, 5, 8)]
    bounds = [(min(coords[i].x for i in g), max(coords[i].x for i in g)) for g in groups]
    gaps = sorted(bounds[i+1][0] - bounds[i][1] for i in range(8))
    gap = gaps[3]
    widths = [max(coords[i].x for i in g) - min(coords[i].x for i in g) for g in groups_out]
    total = sum(widths) + gap * 8
    low_u, high_u = min(p.x for p in coords), max(p.x for p in coords)
    low_z, high_z = min(p.y for p in coords), max(p.y for p in coords)
    center_u, width = (low_u + high_u) / 2, high_u - low_u
    center_z, height = (low_z + high_z) / 2, high_z - low_z
    if role == 'nose_number':
        center_u, width, center_z, height = 0, .92, 2.035, .123
    vertices, faces = [], []
    cursor = -total / 2
    for group, glyph_width in zip(groups_out, widths):
        local = {old: len(vertices) + i for i, old in enumerate(group)}
        glyph_start = min(coords[i].x for i in group)
        for old in group:
            u = center_u + (cursor + coords[old].x - glyph_start) * width / total
            z = center_z + (coords[old].y - (low_z + high_z) / 2) * height / (high_z - low_z)
            if side:
                x = -side * u
                point = Vector((x, side * (builder.side_y(x, z) + .0007), z))
            else:
                point = _front_point(builder, end, end * u, z)
            vertices.append(tuple(point))
        for face in obj.data.polygons:
            if face.vertices[0] in local:
                assert all(i in local for i in face.vertices)
                faces.append([local[i] for i in face.vertices])
        cursor += glyph_width + gap
    name = obj.name
    # IDProperty arrays borrow Blender-owned memory; detach them before the
    # source object is removed, otherwise reassigning a freed array can crash.
    saved = {key: (obj[key].to_list() if hasattr(obj[key], 'to_list') else
                   obj[key].to_dict() if hasattr(obj[key], 'to_dict') else obj[key])
             for key in obj.keys()}
    bpy.data.objects.remove(obj, do_unlink=True)
    new = _mesh(name, vertices, faces, builder, 'proto_yellow')
    for key, value in saved.items():
        new[key] = value
    new['livery21_text'] = NUMBER
    new['livery19_text'] = NUMBER
    if role == 'nose_number':
        new['front11_text'] = NUMBER
    new['prototype41_number_source'] = 'recombined original mesh glyphs; no new font dependency'
    new['prototype41_livery'] = True
    return new.name


def _straight_waist(obj, builder):
    """Clip only red paint faces at two fixed heights, preserving UV/normals."""
    old = obj.data
    keys = [_key(m) for m in old.materials]
    if 'proto_red' not in keys:
        return False
    world = _world(obj)
    if min(p.z for p in world) >= WAIST_TOP or max(p.z for p in world) <= 1.58:
        return False
    # Animated mesh geometry stays exact; these parts are all above the band.
    assert not obj.get('roof26_animation_kind'), ('moving surface intersects waist', obj.name)
    tf, inv = obj.matrix_world.copy(), obj.matrix_world.inverted()
    layers = list(old.uv_layers)
    normals = [tuple(n.vector) for n in old.corner_normals]
    vertices, faces, ids, smooth, output_normals = [], [], [], [], []
    output_uv = [[] for _ in layers]
    mats = list(old.materials)
    slots = {key: index for index, key in enumerate(keys)}
    for key in ('proto_yellow', 'graphite'):
        if key not in slots:
            slots[key] = len(mats)
            mats.append(builder.mat(key))
    changed = 0
    for face in old.polygons:
        raw = [(*world[vi], *(v for layer in layers for v in layer.data[li].uv), *normals[li])
               for vi, li in zip(face.vertices, face.loop_indices)]
        eligible = keys[face.material_index] == 'proto_red'
        pieces = [raw]
        if eligible:
            for z in (WAIST_BOTTOM, WAIST_TOP):
                pieces = [part for piece in pieces for part in _split_attributes(piece, lambda p, z=z: p[2] - z)]
        for piece in pieces:
            center_z = sum(p[2] for p in piece) / len(piece)
            index = face.material_index
            if eligible and center_z < WAIST_TOP:
                index = slots['graphite' if center_z < WAIST_BOTTOM else 'proto_yellow']
            start = len(vertices)
            vertices.extend(tuple(inv @ Vector(p[:3])) for p in piece)
            faces.append(tuple(range(start, len(vertices))))
            ids.append(index)
            smooth.append(face.use_smooth)
            for point in piece:
                for j in range(len(layers)):
                    output_uv[j].append(point[3 + 2*j:5 + 2*j])
                normal = Vector(point[-3:])
                output_normals.append(tuple(normal.normalized()) if normal.length else tuple(face.normal))
        changed += eligible
    if not changed:
        return False
    mesh = bpy.data.meshes.new(old.name + '_prototype_straight_waist')
    mesh.from_pydata(vertices, [], faces)
    for mat in mats:
        mesh.materials.append(mat)
    for face, idx, flag in zip(mesh.polygons, ids, smooth):
        face.material_index = idx
        face.use_smooth = flag
    for layer, values in zip(layers, output_uv):
        target = mesh.uv_layers.new(name=layer.name)
        for item, value in zip(target.data, values):
            item.uv = value
    mesh.update()
    mesh.normals_split_custom_set(output_normals)
    mesh, cleanup = clean_clipped_mesh(mesh)
    obj.data = mesh
    obj['prototype41_straight_waist'] = True
    obj['prototype41_waist_bottom_m'] = WAIST_BOTTOM
    obj['prototype41_waist_top_m'] = WAIST_TOP
    return True


def _front_u(builder, end):
    # Screen-space U follows the folded head surface, never a floating board.
    yz = [(-1.235, 2.58), (-1.14, 2.34), (-1.07, 2.23), (-1.00, 2.18),
          (-.89, 2.16), (.89, 2.16), (1.00, 2.18), (1.07, 2.23),
          (1.14, 2.34), (1.235, 2.58)]
    width = .044
    band_yz = []
    inside = []
    coords = [Vector(p) for p in yz]
    for i, point in enumerate(coords):
        t0 = (point - coords[i-1]).normalized() if i else (coords[1] - point).normalized()
        t1 = (coords[i+1] - point).normalized() if i + 1 < len(coords) else t0
        n0, n1 = Vector((-t0.y, t0.x)), Vector((-t1.y, t1.x))
        offset = (n0 + n1) * (width / 2 / max(1 + n0.dot(n1), .1))
        low, high = point - offset, point + offset
        inside.append((0, float(high.x), float(high.y)))
        band_yz.extend(((0, float(low.x), float(low.y)),
                        (0, float(high.x), float(high.y))))
    # Split the unchanged painted outline before surface mapping. A quad
    # crossing the head's Z=2.55 or Y=+/-1.25 bends otherwise takes a chord
    # through the shell, hiding ink despite correctly seated endpoints.
    vertices, faces = [], []
    for i in range(len(yz)-1):
        polygon = [band_yz[j] for j in (2*i, 2*i+2, 2*i+3, 2*i+1)]
        pieces = [polygon]
        for split in (lambda p: p[2] - 2.55, lambda p: p[1] - 1.25, lambda p: p[1] + 1.25):
            pieces = [part for piece in pieces for part in _split_attributes(piece, split)]
        for piece in pieces:
            first = len(vertices)
            vertices.extend(_front_point(builder, end, p[1], p[2]) for p in piece)
            face = tuple(range(first, len(vertices)))
            faces.append(tuple(reversed(face)) if end < 0 else face)
    obj = _mesh(PREFIX + 'front_yellow_u_' + str(end), vertices, faces, builder, 'proto_yellow')
    obj['prototype41_role'] = 'front_u_border'
    obj['prototype41_end'] = end
    # A sub-millimetre paint layer follows the real head, split at its bend.
    # It is not an independent flat fascia spanning across the folded shell.
    contour = inside + [(0, 1.25, 2.62), (0, -1.25, 2.62)]
    pieces = [contour]
    for split in [lambda p: p[2] - 2.55] + [lambda p, y=p[1]: p[1] - y for p in inside[1:-1]]:
        pieces = [part for piece in pieces for part in _split_attributes(piece, split)]
    verts, polygons = [], []
    for piece in pieces:
        first = len(verts)
        verts.extend(_front_point(builder, end, p[1], p[2], .0007) for p in piece)
        face = tuple(range(first, len(verts)))
        polygons.append(tuple(reversed(face)) if end < 0 else face)
    panel = _mesh(PREFIX + 'front_black_below_window_' + str(end), verts, polygons, builder, 'graphite')
    panel.data, cleanup = clean_clipped_mesh(panel.data)
    panel['prototype41_role'] = 'surface_fitted_black_nose_paint'
    panel['prototype41_end'] = end
    panel['prototype41_surface_offset_m'] = .0007
    return [obj.name, panel.name]


def apply(builder):
    """Derive paint in the loaded prototype copy; no files are saved here."""
    assert not bpy.context.scene.get('prototype41_livery_applied'), 'Prototype paint already applied'
    register_materials(builder.g)
    report = dict(status='PASS', lod=int(builder.lod), variant='FXN5C0001 prototype',
                  dimensions='reference-estimated, not factory specifications',
                  materials=list(MATERIAL_SPECS), material_repainted=[], waist_repainted=[],
                  deleted=[], numbered=[], relief=[], added=[])
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH':
            continue
        if obj.name.startswith(('letter40_fuxing_edge', 'builder_plate_v05', 'builder_plate_engraving')) or obj.get('livery21_role') == 'cab_depot':
            report['deleted'].append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        keys = [_key(m) for m in obj.data.materials]
        paint = any(key in ('blue', 'light_blue') for key in keys)
        mapped = []
        for key in keys:
            new = 'proto_red' if key in ('blue', 'light_blue') or (paint and key == 'yellow') else key
            if new == 'roof':
                new = 'proto_roof'
            mapped.append(new)
        if mapped != keys:
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            for index, (old, new) in enumerate(zip(keys, mapped)):
                if old != new:
                    obj.data.materials[index] = builder.mat(new)
            report['material_repainted'].append(obj.name)
        if 'proto_red' in mapped and _straight_waist(obj, builder):
            report['waist_repainted'].append(obj.name)
    if builder.lod < 2:
        originals = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.name in ('side_fuxing', 'side_fuxing.001')]
        assert len(originals) == 2
        report['relief'] = [_solid_letter(o, builder) for o in originals]
        for obj in list(bpy.context.scene.objects):
            if obj.type != 'MESH':
                continue
            role = obj.get('livery21_role')
            if role in ('side_number', 'cab_number', 'nose_number'):
                report['numbered'].append(_replace_number(obj, builder))
            elif role == 'cab_end':
                # End marks are visible above the prototype door, not below
                # its cab-side number as in this production source.
                side = int(obj['livery21_side'])
                end = int(obj['livery21_end'])
                pts = _world(obj)
                cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2
                cz = (min(p.z for p in pts) + max(p.z for p in pts)) / 2
                inv = obj.matrix_world.inverted()
                for vertex, p in zip(obj.data.vertices, pts):
                    p.x += end * 7.55 - cx
                    p.z += 3.875 - cz
                    p.y = side * (builder.side_y(p.x, p.z) + .0007)
                    vertex.co = inv @ p
                obj.data.update()
                report['numbered'].append(obj.name)
            elif obj.name.startswith(('railway_emblem_v11_', 'nose_fuxing_v11_')):
                _assign(obj, builder, 'proto_gold')
                end = int(obj.get('front11_end', 1 if sum(p.x for p in _world(obj)) > 0 else -1))
                inv = obj.matrix_world.inverted()
                for vertex, point in zip(obj.data.vertices, _world(obj)):
                    vertex.co = inv @ _front_point(builder, end, point.y * .70,
                                                    (point.z - 2.26) * .68 + 2.39)
                obj.data.update()
                obj['prototype41_front_gold_reseated'] = True
    for end in (-1, 1):
        report['added'].extend(_front_u(builder, end))
    assert not any(o.get('livery21_role') == 'cab_depot' for o in bpy.context.scene.objects)
    assert not any(o.name.startswith('letter40_fuxing_edge') for o in bpy.context.scene.objects)
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            assert not any(_key(mat) in ('blue', 'light_blue') for mat in obj.data.materials), ('old production paint remains', obj.name)
    builder.g.ensure_uvs()
    bpy.context.view_layer.update()
    bpy.context.scene['prototype41_livery_applied'] = True
    bpy.context.scene['prototype41_reference'] = 'User photographs of FXN5C0001 plus side drawing; visual approximation'
    report['no_font_or_reference_photo_loaded'] = True
    return report
