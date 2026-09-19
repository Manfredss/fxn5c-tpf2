"""Exact, bounded JW LOD2 baseline tessellation alignment, not a looser matcher.

Released v23 retains a three-triangle roof patch from its native predecessor.
The editable reconstruction has five triangles covering the identical oriented
pentagon, because an interior point subdivides it. Align ONLY that patch before
the v24 deformation. All five boundary vertices are bit-identical float32;
material, area and winding are checked. All other triangle keys must survive.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fxn5c_v23_source'
MATERIAL = 'vehicle/train/fxn5c/jw_roof.mtl'


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _key(points):
    q = np.rint(np.asarray(points, dtype=float) * 100000).astype('<i4')
    return min(np.roll(q, -shift, axis=0).tobytes() for shift in range(3))


def _area(points):
    return float(np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) * .5)


def _boundary(triangles):
    """Cancel directed interior edges using exact original float coordinates."""
    counts = Counter()
    for points in triangles:
        for a, b in zip(points, np.roll(points, -1, axis=0)):
            edge = (tuple(a), tuple(b))
            if counts[edge[::-1]]:
                counts[edge[::-1]] -= 1
            else:
                counts[edge] += 1
    return +counts


def _in_patch(points):
    return (points[:, 0].min() >= -1e-6 and points[:, 0].max() <= 3.800001
            and points[:, 1].min() >= -1.650001 and points[:, 1].max() <= -1.29773
            and points[:, 2].min() >= 3.949999 and points[:, 2].max() <= 4.323405
            and _area(points) > 1e-9)


def _source_rows(obj):
    obj.data.calc_loop_triangles()
    result = []
    for triangle in obj.data.loop_triangles:
        material = obj.data.materials[triangle.material_index].name.lstrip('/')
        if not material.endswith('.mtl'):
            material += '.mtl'
        points = np.asarray([tuple(obj.matrix_world @ obj.data.vertices[i].co)
                             for i in triangle.vertices], dtype=float)
        result.append({'key': (material, _key(points)), 'points': points,
                       'indices': tuple(triangle.vertices), 'face': triangle.polygon_index,
                       'material_index': triangle.material_index,
                       'smooth': obj.data.polygons[triangle.polygon_index].use_smooth})
    return result


def apply(builder, jinwen=False):
    """Calibrate three source faces only; return a byte-bound geometric proof."""
    if not jinwen or builder.lod != 2:
        return {'applied': False, 'reason': 'only Jinwen LOD2 needs this baseline alignment'}
    import bpy
    import bmesh
    from native_patch_v23 import decode
    from verify_native import read_lua
    obj = bpy.data.objects['body_open_shell_v07']
    assert not obj.modifiers, 'do not calibrate an evaluated/modifier-dependent surface'
    folder = BASE / 'staging/codex_fxn5c_1/res'
    model_path = folder / 'models/model/vehicle/train/fxn5c_jinwen.mdl'
    model = read_lua(model_path)
    node = next(n for n in model['lods'][2]['node']['children'] if n['name'] == 'body')
    mesh_path = folder / 'models/mesh' / node['mesh']
    _, arrays, _, native = decode(mesh_path, node['materials'])
    current = _source_rows(obj)
    source_counts = Counter(row['key'] for row in current)
    native_counts = Counter(key for key, _, _ in native)
    missing_source = source_counts - native_counts
    source_patch = [row for row in current if row['key'][0] == MATERIAL
                    and missing_source[row['key']] and _in_patch(row['points'])]
    if not source_patch and obj.get('baseline_tessellation24_proof'):
        return json.loads(obj['baseline_tessellation24_proof'])
    assert len(source_patch) == 5, ('unexpected source patch', len(source_patch))
    native_patch = []
    missing_native = native_counts - source_counts
    for key, slot, ids in native:
        points = arrays['position'][ids].astype(float)
        if key[0] == MATERIAL and missing_native[key] and _in_patch(points):
            native_patch.append({'key': key, 'points': points, 'indices': ids.tolist()})
    assert len(native_patch) == 3, ('unexpected native patch', len(native_patch))
    before_points = [r['points'] for r in source_patch]
    replacement_points = [r['points'] for r in native_patch]
    boundary = _boundary(before_points)
    assert boundary == _boundary(replacement_points) and len(boundary) == 5
    assert set(boundary.values()) == {1}, 'not a single oriented boundary'
    source_area = sum(_area(p) for p in before_points)
    native_area = sum(_area(p) for p in replacement_points)
    assert abs(source_area - native_area) < 1e-10
    assert abs(source_area - 1.02982084157059) < 1e-10, 'unexpected geometric patch extent'
    points = before_points + replacement_points
    normals = [np.cross(p[1] - p[0], p[2] - p[0]) / (2 * _area(p)) for p in points]
    minimum_dot = min(float(n @ m) for n in normals for m in normals)
    plane_residual = max(float(np.abs((p - points[0][0]) @ normals[0]).max()) for p in points)
    assert minimum_dot > .99999999999 and plane_residual < .0000005
    # Positive same-winding triangles plus a shared simple perimeter and equal
    # area establish the same planar covered region. Check the five-vertex
    # perimeter closes once rather than disguising disconnected loops.
    walk = [next(iter(boundary))[0]]
    for _ in range(5):
        destinations = [b for a, b in boundary if a == walk[-1]]
        assert len(destinations) == 1
        walk.append(destinations[0])
    assert walk[-1] == walk[0] and len(set(walk[:-1])) == 5

    target_faces = {row['face'] for row in source_patch}
    assert len(target_faces) == 3
    replace_keys = Counter(row['key'] for row in source_patch)
    retained = [row for row in current if row['face'] in target_faces and not replace_keys[row['key']]]
    assert len(retained) == 2
    material_index = source_patch[0]['material_index']
    assert all(row['material_index'] == material_index for row in source_patch + retained)
    original_count = Counter(row['key'] for row in current)
    original_vertices = len(obj.data.vertices)
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table(); bm.verts.ensure_lookup_table()
    face_objects = [bm.faces[i] for i in target_faces]
    exact_vertices = {}
    for vertex in bm.verts:
        exact_vertices.setdefault(tuple(float(x) for x in obj.matrix_world @ vertex.co), vertex)
    native_loops = []
    for row in native_patch:
        loop = [exact_vertices.get(tuple(point)) for point in row['points']]
        assert all(v is not None for v in loop), 'native perimeter vertex absent in source'
        native_loops.append(loop)
    retained_loops = [[bm.verts[i] for i in row['indices']] for row in retained]
    bmesh.ops.delete(bm, geom=face_objects, context='FACES_ONLY')
    for loop, smooth in ([(loop, retained[i]['smooth']) for i, loop in enumerate(retained_loops)]
                         + [(loop, source_patch[0]['smooth']) for loop in native_loops]):
        face = bm.faces.new(loop)
        face.material_index = material_index
        face.smooth = smooth
    bm.normal_update(); bm.to_mesh(obj.data); bm.free(); obj.data.update()
    after_rows = _source_rows(obj)
    after_count = Counter(row['key'] for row in after_rows)
    assert original_count - after_count == replace_keys, 'unrelated source triangles removed'
    assert after_count - original_count == Counter(row['key'] for row in native_patch), 'unrelated source triangles added'
    assert len(obj.data.vertices) == original_vertices, 'baseline boundary coordinates changed'
    proof = {'applied': True, 'style': 'fxn5c_jinwen', 'lod': 2,
             'object': obj.name, 'original_face_indices': sorted(target_faces),
             'source_triangles_replaced': 5, 'native_triangles_inserted': 3,
             'retained_triangles_in_split_faces': 2,
             'all_other_triangle_keys_retained': True, 'new_vertices': 0,
             'material': MATERIAL, 'source_area_m2': source_area, 'native_area_m2': native_area,
             'oriented_boundary_float_coordinates_identical': True,
             'boundary_vertices': [list(p) for p in walk[:-1]],
             'minimum_normal_dot': minimum_dot, 'maximum_planarity_residual_m': plane_residual,
             'native_vertex_indices': [r['indices'] for r in native_patch],
             'source_patch_vertices': [p.tolist() for p in before_points],
             'native_patch_vertices': [p.tolist() for p in replacement_points],
             'native_patch_position_key_tolerance_unchanged_m': .00001,
             'baseline_sha256': {'../fxn5c_v23_source/' + path.relative_to(BASE).as_posix(): _sha(path)
                                 for path in (model_path, mesh_path, Path(str(mesh_path) + '.blob'))},
             'inputs_sha256': {'baseline_tessellation_v24.py': _sha(Path(__file__))}}
    obj['baseline_tessellation24_proof'] = json.dumps(proof, sort_keys=True)
    bpy.context.scene['baseline_tessellation24_proof'] = json.dumps(proof, sort_keys=True)
    return proof
