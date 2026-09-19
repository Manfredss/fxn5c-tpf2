"""Reimport six static-forward FBXs; compare exact native material triangles.

Lighting expectation is independently derived from actual frontForwardParts,
not the export helper. Actual optical world coordinates also must match, since
triangle counts alone cannot distinguish opposite driving directions. No FBX
animation or engine lamp-switching support is claimed.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
import numpy as np
from mathutils import Matrix

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'runtime'))
import generate_fxn5c as gen
from verify_native import read_lua

RES = ROOT / 'staging/codex_fxn5c_1/res'
FIELDS = tuple(p + d + 'Parts' for d in ('Forward', 'Backward') for p in ('front', 'inner', 'back'))
INPUTS = {}


def track(path):
    INPUTS[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path


def matkey(name):
    return re.sub(r'\.\d{3}$', '', Path(name).name).removesuffix('.mtl').removesuffix('_skin19')


def flatten(node):
    result = []
    def visit(n, parent):
        t = n['transf']
        matrix = parent @ Matrix([[t[c * 4 + r] for c in range(4)] for r in range(4)])
        result.append((n, matrix))
        for child in n.get('children', []):
            visit(child, matrix)
    visit(node, Matrix.Identity(4))
    return result


def material_counts(objects):
    counts = Counter()
    for obj in objects:
        obj.data.calc_loop_triangles()
        for triangle in obj.data.loop_triangles:
            material = obj.data.materials[triangle.material_index]
            assert material is not None, ('missing FBX material', obj.name)
            counts[matkey(material.name)] += 1
    return counts


def native_points(node, transform, descriptor):
    path = track(RES / 'models/mesh' / (node['mesh'] + '.blob'))
    a = descriptor['vertexAttr']['position']
    points = np.frombuffer(path.read_bytes(), dtype='<f4', offset=a['offset'],
                           count=a['count'] // 4).reshape(-1, a['numComp']).astype(float)
    matrix = np.asarray(transform, dtype=float)
    return points @ matrix[:3, :3].T + matrix[:3, 3]


def bidirectional_distance(expected, actual):
    # Optical meshes are tiny. All native/FBX vertices are compared despite
    # FBX's legal welding of repeated triangle corners and material seams.
    expected = np.unique(np.round(expected, 6), axis=0)
    actual = np.unique(np.round(actual, 6), axis=0)
    squared = np.sum((expected[:, None, :] - actual[None, :, :]) ** 2, axis=2)
    return float(np.sqrt(max(squared.min(axis=0).max(), squared.min(axis=1).max())))


def main():
    descriptor_file = track(ROOT / 'native_meshes.json')
    desc = json.loads(descriptor_file.read_text(encoding='utf-8'))
    checked_meshes = set()
    rows = []
    for style in ('fxn5c', 'fxn5c_jinwen'):
        model_path = track(ROOT / ('native_scene_' + style + '.json'))
        model = json.loads(model_path.read_text(encoding='utf-8'))
        actual_model_path = track(RES / 'models/model/vehicle/train' / (style + '.mdl'))
        assert read_lua(actual_model_path) == model, ('stale native model descriptor', style)
        for lod in (0, 1, 2):
            nodes = flatten(model['lods'][lod]['node'])
            config = model['metadata']['railVehicle']['configs'][lod]
            all_ids = {i for field in FIELDS for i in config[field]}
            active_ids = set(config['frontForwardParts'])
            assert len(all_ids) == (6 if lod < 2 else 0)
            assert len(active_ids) == (1 if lod < 2 else 0)
            excluded = all_ids - active_ids
            active_names = {nodes[i][0]['name'] for i in active_ids}
            assert active_names == ({'light24_front_fwd'} if lod < 2 else set())
            expected = Counter()
            expected_mesh_names = set()
            for index, (node, transform) in enumerate(nodes):
                if index in excluded:
                    continue
                field = 'mesh' if 'mesh' in node else 'skin' if 'skin' in node else None
                if field is None:
                    continue
                reference = node[field]
                if reference not in checked_meshes:
                    path = track(RES / 'models/mesh' / reference)
                    assert read_lua(path) == desc[reference], ('stale native mesh descriptor', reference)
                    track(Path(str(path) + '.blob'))
                    checked_meshes.add(reference)
                materials = node['materials' if field == 'mesh' else 'skinMaterials']
                assert len(desc[reference]['subMeshes']) == len(materials)
                for sub, material in zip(desc[reference]['subMeshes'], materials):
                    expected[matkey(material)] += sub['indices']['position']['count'] // 12
                expected_mesh_names.add(node['name'] if field == 'mesh' else node['name'] + '_native_skin')
            folder = 'vehicle-train-fxn5c-jinwen' if style.endswith('jinwen') else 'vehicle-train-fxn5c'
            path = track(ROOT / 'fbx_import' / folder / ('fxn5c_lod' + str(lod) + '.fbx'))
            gen.clear_scene()
            bpy.ops.import_scene.fbx(filepath=str(path))
            meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
            actual = material_counts(meshes)
            assert actual == expected, (style, lod, 'FBX face/material mismatch', actual - expected, expected - actual)
            assert {o.name for o in meshes} == expected_mesh_names, (style, lod, 'mesh node coverage',
                    {o.name for o in meshes} - expected_mesh_names, expected_mesh_names - {o.name for o in meshes})
            lamp_names = {o.name for o in meshes if o.name.startswith('light24_')}
            assert lamp_names == active_names, ('inactive/opposite-direction lamps exported', style, lod, lamp_names)
            assert not any(o.type == 'ARMATURE' for o in bpy.context.scene.objects), 'static FBX unexpectedly contains a rig'
            assert not any(o.animation_data for o in bpy.context.scene.objects), 'static FBX unexpectedly contains animation data'
            optical_errors = {}
            for index in sorted(active_ids):
                node, transform = nodes[index]
                expected_points = native_points(node, transform, desc[node['mesh']])
                obj = bpy.data.objects[node['name']]
                actual_points = np.asarray([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices])
                error = bidirectional_distance(expected_points, actual_points)
                assert error < .00005, (style, lod, 'optics moved/flipped in FBX', error)
                optical_errors[node['name']] = error
                counts = material_counts([obj])
                assert counts['lamp_moon_v24'] == 6 * ((24 if lod == 0 else 12) - 2)
                assert counts['lamp_red'] == 2 * ((24 if lod == 0 else 12) - 2)
            rows.append({'style': style, 'lod': lod, 'mesh_objects': len(meshes),
                         'triangles': sum(actual.values()), 'material_triangle_counts': dict(actual),
                         'exact_native_material_counts': True,
                         'static_direction': 'forward', 'native_position_case': 'front',
                         'active_light_ids': sorted(active_ids), 'active_light_names': sorted(active_names),
                         'excluded_conditional_light_ids': sorted(excluded),
                         'optical_world_position_max_error_m': optical_errors,
                         'animation_or_armature_present': False})
    for name in ('audit_fbx_v24.py', 'fbx_native_v24.py', 'light_revision_v24.py',
                 'render_native.py', 'generate_fxn5c.py'):
        track(ROOT / name)
    report = {'status': 'PASS', 'generated_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'Six static forward-state FBX readbacks versus current native byte descriptors; exact per-material triangles and optical world positions. Native six-case lamp configuration is authoritative; FBXs contain no switching rig.',
              'game_verified': False, 'static_interchange_only': True,
              'models': rows, 'inputs_sha256': INPUTS}
    (ROOT / 'fbx_audit_v24.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('FBX AUDIT PASS: six static-forward files, exact native material counts, optical coordinates, no inactive lamp nodes or rig.', flush=True)


if __name__ == '__main__':
    main()
