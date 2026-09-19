"""Independent native-byte audit for v24's six-case local-cab lamp arrangement.

Checks actual exported emitter triangles, materials, all ten assignments,
direction/consist-position IDs and lens seating. This is not an engine playtest.
"""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime'))
from verify_native import read_lua
import light_revision_v24 as lights
from roster_v21 import ROSTER

RES = ROOT / 'staging/codex_fxn5c_1/res'
BASE = ROOT.parent / 'fxn5c_v23_source'
EXPECTED_RED = {'0096', '0102', '0057', '0035', '0115'}
EXPECTED_NUMBERS = EXPECTED_RED | {'0051', '0081', '0066', '7006', '7005'}
EXPECTED_WHITE = 'vehicle/train/fxn5c/lamp_moon_v24.mtl'
EXPECTED_RED_MATERIAL = 'vehicle/train/fxn5c/lamp_red.mtl'
EXPECTED_FIELDS = {p + d + 'Parts': (p, direction)
                   for d, direction in (('Forward', 1), ('Backward', -1))
                   for p in ('front', 'inner', 'back')}
INPUTS = {}


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def track(path):
    INPUTS[path.relative_to(ROOT).as_posix()] = sha(path)
    return path


def tree(root):
    result = []
    def visit(n, parent_matrix):
        matrix = parent_matrix @ np.asarray(n['transf'], dtype=float).reshape(4, 4).T
        result.append((n, matrix))
        for c in n.get('children', []):
            visit(c, matrix)
    visit(root, np.eye(4))
    return result


class Geometry:
    def __init__(self):
        self.cache = {}

    def read(self, reference):
        if reference in self.cache:
            return self.cache[reference]
        path = track(RES / 'models/mesh' / reference)
        desc = read_lua(path)
        blob = track(Path(str(path) + '.blob')).read_bytes()
        arrays = {}
        for attr in ('position', 'normal'):
            a = desc['vertexAttr'][attr]
            arrays[attr] = np.frombuffer(blob, dtype='<f4', offset=a['offset'],
                                        count=a['count'] // 4).reshape(-1, a['numComp']).astype(float)
        groups = []
        for sub in desc['subMeshes']:
            a = sub['indices']['position']
            ids = np.frombuffer(blob, dtype='<u4', offset=a['offset'], count=a['count'] // 4).reshape(-1, 3)
            groups.append(ids)
        result = (arrays['position'], arrays['normal'], groups)
        self.cache[reference] = result
        return result

    def lens_triangles(self, nodes):
        result = []
        for node, transform in nodes:
            if 'mesh' not in node or not any(Path(m).stem == 'lamp_glass' for m in node['materials']):
                continue
            p, _, groups = self.read(node['mesh'])
            world = p @ transform[:3, :3].T + transform[:3, 3]
            for mat, ids in zip(node['materials'], groups):
                if Path(mat).stem == 'lamp_glass':
                    result.extend(world[ids])
        require(result, 'no actual native lamp glass triangles')
        return np.asarray(result)


def optical_slot(point):
    end = 1 if point[0] > 0 else -1
    side = 1 if point[1] > 0 else -1
    kind = 'top' if point[2] > 3.5 else ('outer' if abs(point[1]) > 1.4 else 'inner')
    return end, side, kind


def x_ray_distance(point, end, triangles):
    """Nearest actual triangle hit along outward X, independent of recipe tags."""
    yz = triangles[:, :, 1:3]
    a = yz[:, 0]
    v0, v1 = yz[:, 1] - a, yz[:, 2] - a
    q = np.asarray(point[1:3]) - a
    det = v0[:, 0] * v1[:, 1] - v0[:, 1] * v1[:, 0]
    usable = np.abs(det) > 1e-12
    safe = np.where(usable, det, 1)
    u = (q[:, 0] * v1[:, 1] - q[:, 1] * v1[:, 0]) / safe
    v = (v0[:, 0] * q[:, 1] - v0[:, 1] * q[:, 0]) / safe
    hit_x = triangles[:, 0, 0] + u * (triangles[:, 1, 0] - triangles[:, 0, 0]) + v * (triangles[:, 2, 0] - triangles[:, 0, 0])
    distance = end * (hit_x - point[0])
    good = usable & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (distance > .00001)
    require(np.any(good), ('no forward glass hit', point))
    return float(distance[good].min())


def audit_mesh(geometry, node, direction, number, lod, glass):
    position, normals, groups = geometry.read(node['mesh'])
    require(len(groups) == 3, ('expected separate fixed-white/inner/tail slots', node['name']))
    expected_materials = [EXPECTED_WHITE, EXPECTED_RED_MATERIAL if number in EXPECTED_RED else EXPECTED_WHITE,
                          EXPECTED_RED_MATERIAL]
    require(node['materials'] == expected_materials, ('wrong native lamp material slots', number, node['materials']))
    require(np.isfinite(position).all() and np.isfinite(normals).all(), 'non-finite optical geometry')
    expected_count = 24 if lod == 0 else 12
    slots = {}
    for group_index, ids in enumerate(groups):
        for indices in ids:
            points = position[indices]
            slot = optical_slot(points.mean(axis=0))
            require(all(optical_slot(p) == slot for p in points), 'triangle bridges different optical slots')
            end, _, kind = slot
            allowed_group = (0 if kind in ('outer', 'top') else (1 if end == direction else 2))
            require(group_index == allowed_group, ('wrong optical submesh', slot, group_index))
            require(float((normals[indices, 0] * end).min()) > .75, ('inward emitter normal', slot))
            area = np.linalg.norm(np.cross(points[1] - points[0], points[2] - points[0])) * .5
            require(area > 1e-10, ('degenerate emitter triangle', slot))
            slots.setdefault(slot, {'points': [], 'triangles': 0, 'material': node['materials'][group_index]})
            slots[slot]['points'].extend(points)
            slots[slot]['triangles'] += 1
    expected_slots = {(direction, s, k) for s in (-1, 1) for k in ('outer', 'inner', 'top')}
    expected_slots |= {(-direction, s, 'inner') for s in (-1, 1)}
    require(set(slots) == expected_slots, ('missing/unwanted optics, e.g. trailing outer/top', sorted(slots)))
    result = []
    for (end, side, kind), data in sorted(slots.items()):
        points = np.unique(np.round(np.asarray(data['points']), 6), axis=0)
        center = points.mean(axis=0)
        require(len(points) == expected_count and data['triangles'] == expected_count - 2,
                ('unexpected optical tessellation', kind, len(points), data['triangles']))
        if kind == 'top':
            expected_y, expected_z, radius = side * .15, 4.43, .038
        else:
            inner = kind == 'inner'
            expected_y = side * (1.24 if inner else 1.53)
            expected_z = 2.02 if inner else 2.055
            expected_x = end * (11.060 if inner else 11.010)
            radius = .068
            require(abs(center[0] - expected_x) < .000006, ('lower emitter detached from fixture plane', center))
        require(abs(center[1] - expected_y) < .000003 and abs(center[2] - expected_z) < .000003,
                ('emitter not concentric with required lens', kind, center))
        radial = np.linalg.norm(points[:, 1:3] - [expected_y, expected_z], axis=1)
        require(float(np.max(np.abs(radial - radius))) < .000002, ('incorrect optical disc radius', kind))
        # Center plus four points at half-radius; all must be behind the actual
        # emitted native optic. Top center is 8mm behind its inner glass; lower
        # discs are 10mm behind the lens. This catches stale old-Z emitters.
        samples = [center] + [center * .5 + points[i * expected_count // 4] * .5 for i in range(4)]
        gaps = [x_ray_distance(point, end, glass) for point in samples]
        expected_gap = .008 if kind == 'top' else .010
        require(max(abs(g - expected_gap) for g in gaps) < .00002, ('emitter/lens seating mismatch', kind, gaps))
        result.append({'end': end, 'side': side, 'kind': kind, 'material': data['material'],
                       'center': center.tolist(), 'radius_m': radius, 'triangles': data['triangles'],
                       'glass_outward_gaps_m': gaps})
    return {'mesh': node['mesh'], 'triangles': sum(x['triangles'] for x in result), 'optics': result}


def audit_mapping(model, number):
    reports = []
    for lod, entry in enumerate(model['lods']):
        nodes = tree(entry['node'])
        config = model['metadata']['railVehicle']['configs'][lod]
        seen = set()
        for field, (position, direction) in EXPECTED_FIELDS.items():
            indices = config[field]
            require(len(indices) == (1 if lod < 2 else 0), ('wrong config count', lod, field))
            for index in indices:
                require(index not in seen and 0 <= index < len(nodes), 'duplicate/out-of-range visibility ID')
                seen.add(index)
                node, transform = nodes[index]
                suffix = 'fwd' if direction == 1 else 'bwd'
                require(node['name'] == 'light24_' + position + '_' + suffix, ('wrong directional ID', field, node['name']))
                require(np.array_equal(transform, np.eye(4)), 'light instance world transform changed')
                require(node['materials'] == [EXPECTED_WHITE,
                        EXPECTED_RED_MATERIAL if number in EXPECTED_RED else EXPECTED_WHITE, EXPECTED_RED_MATERIAL],
                        ('wrong assignment', number, node['materials']))
        actual = {i for i, (n, _) in enumerate(nodes) if n['name'].startswith('light24_')}
        require(actual == seen, 'uncontrolled/unlisted lamp node')
        require(not any(n['name'] in lights.LEGACY_NAMES for n, _ in nodes), 'legacy lamp survives')
        cases = []
        for direction in ('fwd', 'bwd'):
            for position in ('front', 'inner', 'back', 'singleton'):
                preview = lights.preview_visibility(model, direction, position, lod)
                require(len(preview['visible_ids']) == (1 if lod < 2 else 0), 'preview does not select exactly one local-direction mesh')
                require(len(preview['raw_active_ids']) == ((2 if position == 'singleton' else 1) if lod < 2 else 0), 'preview raw role coverage')
                cases.append(preview)
        reports.append({'lod': lod, 'instance_ids': sorted(seen), 'cases': cases})
    return reports


def audit_materials():
    material = read_lua(track(RES / 'models/material' / EXPECTED_WHITE))
    require(material['type'] == 'EMISSIVE', 'moon material is not native EMISSIVE')
    require(material['params']['emissive_scale']['emissiveScale'] == [9, 9, 9], 'changed moon emission strength')
    require(material['params']['map_emissive']['type'] == 'TWOD', 'invalid emission texture type')
    texture = track(RES / 'textures' / material['params']['map_emissive']['fileName'])
    raw = texture.read_bytes()
    require(len(raw) == 66 and raw[2] == 2 and raw[12:18] == bytes((4, 0, 4, 0, 24, 32)), 'moon texture format')
    require(raw[18:] == bytes((255, 242, 224)) * 16, 'moon color is not specified RGB224/242/255')
    retained = {}
    unreferenced = {}
    for relative in ('models/material/vehicle/train/fxn5c/lamp_white.mtl',
                     'models/material/vehicle/train/fxn5c/lamp_red.mtl',
                     'textures/models/vehicle/train/fxn5c/lamp_white.tga',
                     'textures/models/vehicle/train/fxn5c/lamp_red.tga'):
        current = RES / relative
        if '/lamp_red.' in relative:
            track(current)
        old = BASE / 'staging/codex_fxn5c_1/res' / relative
        require(current.read_bytes() == old.read_bytes(), ('legacy lamp resource changed', relative))
        retained[relative] = sha(old)
        if '/lamp_white.' in relative:
            unreferenced[relative] = {'working_sha256': sha(current), 'baseline_sha256': sha(old)}
    return {'type': 'EMISSIVE', 'moon_srgb': [224, 242, 255], 'emission_scale': [9, 9, 9],
            'legacy_resources_byte_identical': retained,
            'unreferenced_working_baseline_sha256': unreferenced}


def main():
    require(set(lights.LEADING_INNER) == EXPECTED_NUMBERS, 'incomplete deterministic assignments')
    require({n for n, color in lights.LEADING_INNER.items() if color == 'red'} == EXPECTED_RED, 'assignment changed')
    require({r['number'] for r in ROSTER} == EXPECTED_NUMBERS, 'roster coverage')
    geometry = Geometry()
    results = []
    first = None
    for row in ROSTER:
        path = track(RES / 'models/model/vehicle/train' / (row['stem'] + '.mdl'))
        model = read_lua(path)
        if first is None:
            first = deepcopy(model)
        require(model['metadata']['transportVehicle']['reversible'] is True, 'reversible flag missing')
        mapping = audit_mapping(model, row['number'])
        meshes = []
        for lod in (0, 1):
            nodes = tree(model['lods'][lod]['node'])
            glass = geometry.lens_triangles(nodes)
            by_name = {n['name']: n for n, _ in nodes}
            for direction in (1, -1):
                suffix = 'fwd' if direction == 1 else 'bwd'
                mesh_report = audit_mesh(geometry, by_name['light24_front_' + suffix], direction,
                                         row['number'], lod, glass)
                mesh_report['lod'] = lod
                meshes.append(mesh_report)
        results.append({'stem': row['stem'], 'number': row['number'],
                        'leading_inner': 'red' if row['number'] in EXPECTED_RED else 'white',
                        'mapping': mapping, 'geometry': meshes})
    negative = []
    for case in ('swap_direction_lists', 'reuse_instance_id', 'wrong_leading_inner_color'):
        broken = deepcopy(first)
        cfg = broken['metadata']['railVehicle']['configs'][0]
        if case == 'swap_direction_lists':
            cfg['frontForwardParts'], cfg['frontBackwardParts'] = cfg['frontBackwardParts'], cfg['frontForwardParts']
        elif case == 'reuse_instance_id':
            cfg['innerForwardParts'] = list(cfg['frontForwardParts'])
        else:
            tree(broken['lods'][0]['node'])[cfg['frontForwardParts'][0]][0]['materials'][1] = EXPECTED_RED_MATERIAL
        try:
            audit_mapping(broken, '0051')
        except AssertionError as exc:
            negative.append({'case': case, 'rejected': True, 'reason': str(exc)})
        else:
            raise AssertionError(('negative control accepted', case))
    # A real decoded native mesh displaced 1cm in memory must fail geometry.
    node = next(n for n, _ in tree(first['lods'][0]['node']) if n['name'] == 'light24_front_fwd')
    original = geometry.cache[node['mesh']]
    moved = original[0].copy()
    moved[:, 2] += .010
    geometry.cache[node['mesh']] = (moved, original[1], original[2])
    try:
        audit_mesh(geometry, node, 1, '0051', 0, geometry.lens_triangles(tree(first['lods'][0]['node'])))
    except AssertionError as exc:
        negative.append({'case': 'emitter_detached_10mm', 'rejected': True, 'reason': str(exc)})
    else:
        raise AssertionError('negative control accepted: emitter detached')
    finally:
        geometry.cache[node['mesh']] = original
    materials = audit_materials()
    for name in ('audit_lights_v24.py', 'light_revision_v24.py', 'roof_revision_v24.py', 'roster_v21.py'):
        track(ROOT / name)
    report = {'status': 'PASS', 'generated_utc': datetime.now(timezone.utc).isoformat(),
              'engine_tested': False,
              'scope': 'Native metadata/bytes, fixed number mapping, actual optics and glass seating. No running/stopped engine claim.',
              'singleton_policy': 'If engine enables both front/back lists, both exact instances use identical geometry/materials. Preview deduplicates exact copies only; engine category exclusivity is not asserted.',
              'official_sources': ['https://www.wiki.transportfever2.com/doku.php?id=modding:vehicleadvancedtopics',
                                   'https://www.wiki.transportfever2.com/doku.php?id=modding:resourcetypes:mtl'],
              'materials': materials, 'models': results, 'negative_controls': negative,
              'inputs_sha256': INPUTS}
    output = ROOT / 'light_audit_v24.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('LIGHT AUDIT PASS: 10 models, 2 detailed LODs, both directions, 6 metadata cases, 4 negative controls; not engine-tested.', flush=True)


if __name__ == '__main__':
    main()
