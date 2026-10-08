"""Scoped front paint fits to the user's five September 2026 photographs.

Original folded steel, body outline, lights, signs and animation are retained.
The dimensions below are visual fits, not factory measurements. No photograph
pixels or third-party fonts are copied into the model.
"""
from pathlib import Path
import math
import bpy
from mathutils import Vector
from geometry_v05 import split_polygon
from livery_revision_v21 import _split_attributes

STRIPE_PITCH = .225
STRIPE_SLOPE = 1.50
STRIPE_PHASE = .275
PAINT_OFFSET = .0015
BLUE_BOTTOM, BLUE_TOP = 1.865, 1.925
GAP_HALF_TOP, GAP_HALF_BOTTOM = .55, .61


def selected_objects(jw=None):
    """Exact static delta set before/after apply; never selects labels/lamps.

    For Jinwen the inherited paint is part of body_open_shell_v07. The complete
    authored shell must therefore be exported for the delta, although only
    blue-band corner polygons are edited and all other loops are retained.
    """
    selected = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH':
            continue
        plow = obj.name.startswith(('central_plough_yellow_v09', 'front38_plough_yellow'))
        band = bool(obj.get('front24_blue_band_split'))
        if (jw is not True and plow) or (jw is not False and band):
            selected.append(obj)
    return sorted(selected, key=lambda obj: obj.name)


def _plough(b):
    old = selected_objects(False)
    if old and all(obj.get('front38_role') == 'convergent_plough_paint' for obj in old):
        return {'unchanged': True, 'objects': [obj.name for obj in old]}
    plates = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH'
              and obj.name.startswith('central_pointed_plough_v09')]
    # Far LOD omits these small paint patches; do not manufacture new detail.
    if not old and not plates:
        return {'omitted_in_lod': b.lod}
    assert len(plates) == 4, ('Expected four unchanged folded plough wings', len(plates))
    assert old, 'Folded plough exists but baseline paint delta is missing'
    new = []
    for plate in plates:
        transform = plate.matrix_world
        points = [transform @ vertex.co for vertex in plate.data.vertices]
        end = 1 if sum(p.x for p in points) > 0 else -1
        side = 1 if sum(p.y for p in points[:4]) > 0 else -1
        # The source has two front triangles followed by the solidified back
        # and edge faces. Assert this contract; do not repaint plate returns.
        for face in list(plate.data.polygons)[:2]:
            assert len(face.vertices) == 3 and max(face.vertices) < 4
            assert (transform.to_3x3() @ face.normal).x * end > .70
            parts = [[tuple(points[i]) for i in face.vertices]]
            # Wing-local lateral distance makes bands converge at the ridge
            # on both wings and both ends, not one global diagonal direction.
            for i in range(-8, 17):
                level = STRIPE_PHASE + i * STRIPE_PITCH
                parts = [part for poly in parts for part in split_polygon(
                    poly, lambda p, k=level, side=side: p[2] + side*p[1]*STRIPE_SLOPE-k)]
            for part in parts:
                center = sum((Vector(p) for p in part), Vector()) / len(part)
                band = math.floor((center.z + side*center.y*STRIPE_SLOPE-STRIPE_PHASE) / STRIPE_PITCH)
                if band % 2:
                    obj = b.poly('front38_plough_yellow',
                                 [(x+end*PAINT_OFFSET, y, z) for x, y, z in part],
                                 [tuple(range(len(part)))], 'yellow', normal=(end, 0, 0))
                    obj['front38_role'] = 'convergent_plough_paint'
                    obj['front38_host'] = plate.name
                    obj['front38_end'] = end
                    obj['front38_wing'] = side
                    obj['front38_dimensions_estimated'] = True
                    new.append(obj.name)
    assert new
    removed = [obj.name for obj in old]
    for obj in old:
        bpy.data.objects.remove(obj, do_unlink=True)
    return {'removed': removed, 'added': new, 'plate_geometry': 'unchanged',
            'stripe_pitch_m': STRIPE_PITCH, 'wing_local_slope': STRIPE_SLOPE,
            'paint_offset_m': PAINT_OFFSET}


def _gap_half(z):
    return GAP_HALF_TOP + (BLUE_TOP-z) * (GAP_HALF_BOTTOM-GAP_HALF_TOP)/(BLUE_TOP-BLUE_BOTTOM)


def _jinwen_band(obj, b):
    if obj.get('front38_band_applied'):
        return {'object': obj.name, 'unchanged': True}
    old = obj.data
    keys = [Path(mat.name).name for mat in old.materials]
    assert 'jw_blue' in keys and 'jw_white' in keys
    world = [obj.matrix_world @ vertex.co for vertex in old.vertices]
    inverse = obj.matrix_world.inverted()
    old_normals = [tuple(n.vector) for n in old.corner_normals]
    layers = list(old.uv_layers)
    vertices = [tuple(vertex.co) for vertex in old.vertices]
    faces, indices, flags, normals = [], [], [], []
    uvs = [[] for _ in layers]
    affected = []
    retained = 0

    def retain(face):
        nonlocal retained
        faces.append(tuple(face.vertices)); indices.append(face.material_index)
        flags.append(face.use_smooth)
        normals.extend(old_normals[i] for i in face.loop_indices)
        for j, layer in enumerate(layers):
            uvs[j].extend(tuple(layer.data[i].uv) for i in face.loop_indices)
        retained += 1

    for face in old.polygons:
        points = [world[i] for i in face.vertices]
        # Widen only a small blue corner next to the already-white centre gap.
        # This avoids touching red paint, chamfers, side stripes and the large
        # inherited shell polygons outside the exact horizontal blue strip.
        eligible = (keys[face.material_index] == 'jw_blue'
                    and min(p.z for p in points) >= BLUE_BOTTOM-2e-6
                    and max(p.z for p in points) <= BLUE_TOP+2e-6
                    and all(abs(abs(p.x)-b.front_x(p.z)) < 3e-5 for p in points)
                    and min(abs(p.y) for p in points) < GAP_HALF_BOTTOM-1e-7
                    and max(abs(p.y) for p in points) > GAP_HALF_TOP-1e-7)
        if not eligible:
            retain(face)
            continue
        polygon = []
        for vertex_id, loop_id in zip(face.vertices, face.loop_indices):
            attrs = [value for layer in layers for value in layer.data[loop_id].uv]
            polygon.append((*world[vertex_id], *attrs, *old_normals[loop_id]))
        parts = [polygon]
        for sign in (-1, 1):
            parts = [part for poly in parts for part in _split_attributes(
                poly, lambda p, sign=sign: sign*p[1]-_gap_half(p[2]))]
        # If this blue polygon does not actually intersect the new white wedge,
        # keep its old loops exactly, without even harmless retessellation.
        is_white = [abs(sum(p[1] for p in part)/len(part)) <
                    _gap_half(sum(p[2] for p in part)/len(part))-1e-8 for part in parts]
        if not any(is_white):
            retain(face)
            continue
        affected.append(face.index)
        for part, white in zip(parts, is_white):
            first = len(vertices)
            vertices.extend(tuple(inverse @ Vector(p[:3])) for p in part)
            faces.append(tuple(range(first, len(vertices))))
            indices.append(keys.index('jw_white') if white else face.material_index)
            flags.append(face.use_smooth)
            for p in part:
                for j in range(len(layers)):
                    uvs[j].append(tuple(p[3+2*j:5+2*j]))
                normal = Vector(p[-3:])
                normals.append(tuple(normal.normalized()) if normal.length else tuple(face.normal))
    assert affected, ('No Jinwen blue-band corners changed', obj.name)
    mesh = bpy.data.meshes.new(old.name+'_front38_slanted_band_ends')
    mesh.from_pydata(vertices, [], faces)
    for material in old.materials:
        mesh.materials.append(material)
    for face, index, smooth in zip(mesh.polygons, indices, flags):
        face.material_index = index; face.use_smooth = smooth
    for layer, values in zip(layers, uvs):
        target = mesh.uv_layers.new(name=layer.name)
        for entry, value in zip(target.data, values):
            entry.uv = value
    mesh.update(); mesh.normals_split_custom_set(normals); mesh.update()
    obj.data = mesh
    obj['front38_band_applied'] = True
    obj['front38_role'] = 'slanted_blue_band_inner_ends'
    obj['front38_gap_half_bottom_top'] = [GAP_HALF_BOTTOM, GAP_HALF_TOP]
    obj['front38_dimensions_estimated'] = True
    return {'object': obj.name, 'changed_original_faces': affected,
            'retained_faces_exact': retained, 'original_faces': len(old.polygons),
            'result_faces': len(mesh.polygons), 'red_and_other_surfaces': 'unchanged',
            'uv_and_corner_normal_interpolation': True}


def apply(b, jw=False):
    """Apply to an editable v37 source; caller handles source/native export."""
    report = {'lod': b.lod, 'jinwen': bool(jw), 'estimated_dimensions': True,
              'reference': 'user five FXN5C photographs; no image pixels reused'}
    if jw:
        targets = selected_objects(True)
        if not targets:
            assert b.lod == 2, 'Missing inherited Jinwen front paint selection'
            report['omitted_in_lod'] = b.lod
        else:
            report['band'] = [_jinwen_band(obj, b) for obj in targets]
            report['gap_half_bottom_top_m'] = [GAP_HALF_BOTTOM, GAP_HALF_TOP]
    else:
        report['plough'] = _plough(b)
    bpy.context.view_layer.update()
    report['selected_after'] = [obj.name for obj in selected_objects(jw)]
    return report
