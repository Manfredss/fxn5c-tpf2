"""FXN5C v0.26 native cooling-equipment animation adapter.

Pure Python; does not edit source geometry, model files, or game installation.
Use append_animation_nodes(model, parts_by_lod) on a parsed plain-Python MDL.
Each movable blade is its own node. Static grille, hub support and hinges remain
in the body mesh. These are decorative forever loops, NOT temperature control.

Part schema: {kind: 'fan'|'louver', name, mesh, materials, pivot,
              mesh_local=True, enabled=True, ... factory options ...}.
Default mesh coordinates are local to pivot; the node is translated to pivot.
Set mesh_local=False for an identity/world-coordinate mesh and animation origin
at pivot. Do not use both coordinate conventions at once.
"""

from __future__ import annotations

import copy
import math
from pathlib import PurePosixPath

IDENTITY = [1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1., 0., 0., 0., 0., 1.]
PREFIX = 'fxn5c_v26_'
DOCUMENTATION = {
    'events': 'https://wiki.transportfever2.com/doku.php?id=modding:vehicletypes',
    'nodes': 'https://wiki.transportfever2.com/doku.php?id=modding:resourcetypes:mdl',
    'local_events_evidence': 'res/models/model.zip: model/vehicle/train/usa/emd_sd40_v2.mdl',
    'local_degrees_evidence': 'res/models/model.zip: model/asset/icon/marker_exclamation.mdl',
}


def _vector3(values, name):
    values = [float(value) for value in values]
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError(f'{name} must contain exactly three finite numbers')
    return values


def _resource(value, suffix):
    value = str(value).replace('\\', '/')
    parsed = PurePosixPath(value)
    if (parsed.is_absolute() or '..' in parsed.parts or ':' in value
            or parsed.suffix != suffix):
        raise ValueError(f'Expected relative {suffix} resource, got {value!r}')
    return value


def _axis_index(axis):
    axis = str(axis).upper()
    if axis not in ('X', 'Y', 'Z'):
        raise ValueError(f'Expected axis X, Y or Z, got {axis!r}')
    return 'XYZ'.index(axis)


def _frame(time_ms, angle, axis):
    rotation = [0., 0., 0.]
    rotation[_axis_index(axis)] = float(angle)
    return {'time': int(time_ms), 'rot': rotation, 'transl': [0., 0., 0.]}


def _base_node(mesh, materials, pivot, name, mesh_local):
    pivot = _vector3(pivot, 'pivot')
    if not isinstance(name, str) or not name.startswith(PREFIX):
        raise ValueError(f'Animation names must begin with {PREFIX!r}')
    materials = [_resource(material, '.mtl') for material in materials]
    if not materials:
        raise ValueError('A mesh requires at least one material')
    transf = list(IDENTITY)
    if mesh_local:
        transf[12:15] = pivot
    return {'name': name, 'mesh': _resource(mesh, '.msh'),
            'materials': materials, 'transf': transf}, (
                [0., 0., 0.] if mesh_local else pivot)


def _forever(node, origin, frames, enabled):
    if enabled:
        node['animations'] = {'forever': {
            'forward': True,
            'params': {'keyframes': frames, 'origin': origin},
            'type': 'KEYFRAME',
        }}
    return node


def make_fan_node(mesh, materials, pivot, name, *, mesh_local=True,
                  period_ms=1500, direction=1, enabled=True):
    """Create a horizontal-Y-axis rotor. One mesh contains only moving parts.

    1500 ms/rev matches a vanilla fan animation period, not FXN5C measured RPM.
    At standstill it continues because native forever is independent of speed.
    Four quarter-turn intervals avoid an ambiguous identity-to-identity turn.
    """
    if not isinstance(period_ms, int) or period_ms < 100 or period_ms % 4:
        raise ValueError('period_ms must be an integer >=100 divisible by four')
    if direction not in (-1, 1):
        raise ValueError('direction must be -1 or +1')
    node, origin = _base_node(mesh, materials, pivot, name, mesh_local)
    frames = [_frame(period_ms * step // 4, direction * 90. * step, 'Y')
              for step in range(5)]
    return _forever(node, origin, frames, enabled)


def make_louver_node(mesh, materials, pivot, name, *, mesh_local=True,
                     period_ms=18000, angle_degrees=30., direction=1,
                     enabled=True):
    """Create a single longitudinal-X hinged blade with a slow display cycle.

    Source mesh is its rest pose; animation adds 0..angle_degrees around the
    actual hinge. 0..4 s rest, 4..6 s open, 6..13 s hold, 13..15 s close,
    15..18 s rest (scaled for another period). This is intentionally a visual
    approximation, not an assertion that real shutters repeatedly cycle.
    """
    if not isinstance(period_ms, int) or period_ms < 1000:
        raise ValueError('period_ms must be an integer >=1000')
    if not math.isfinite(angle_degrees) or not 0 < angle_degrees <= 45:
        raise ValueError('angle_degrees must be finite and in (0,45]')
    if direction not in (-1, 1):
        raise ValueError('direction must be -1 or +1')
    node, origin = _base_node(mesh, materials, pivot, name, mesh_local)
    angle = float(angle_degrees) * direction
    frames = [_frame(round(period_ms * fraction / 18), value, 'X')
              for fraction, value in ((0, 0), (4, 0), (6, angle),
                                       (13, angle), (15, 0), (18, 0))]
    return _forever(node, origin, frames, enabled)


def flatten_nodes(node):
    """Native depth-first node order, including grouping nodes and root."""
    yield node
    for child in node.get('children', []):
        yield from flatten_nodes(child)


def assert_original_nodes_preserved(before, after):
    """Prove all original node IDs, metadata and LOD ranges remain unchanged.

    Do not remove/reorder old nodes to insert animations: lights, bogie ids,
    particle emitters and cameras can refer to these numeric node indices.
    """
    assert before.keys() == after.keys(), 'Unexpected model-level changes'
    for key in before:
        if key != 'lods':
            assert before[key] == after[key], f'Changed protected model field {key}'
    assert len(before['lods']) == len(after['lods'])
    proofs = []
    for lod_index, (old_lod, new_lod) in enumerate(zip(before['lods'], after['lods'])):
        for key in old_lod:
            if key != 'node':
                assert old_lod[key] == new_lod[key], (lod_index, key)
        old_root, new_root = old_lod['node'], new_lod['node']
        for key in old_root:
            if key != 'children':
                assert old_root[key] == new_root[key], (lod_index, key)
        old_children = old_root.get('children', [])
        assert new_root.get('children', [])[:len(old_children)] == old_children
        old_flat = list(flatten_nodes(old_root))
        new_flat = list(flatten_nodes(new_root))
        # Root itself changed only by appending children, already checked.
        assert old_flat[1:] == new_flat[1:len(old_flat)], f'Node ID shift in LOD {lod_index}'
        proofs.append({'lod': lod_index, 'preserved_nodes': len(old_flat),
                       'appended_nodes': len(new_flat) - len(old_flat)})
    return proofs


def append_animation_nodes(model, parts_by_lod, *, animate_fans=True,
                           animate_louvers=True):
    """Return (new_model, report); never mutate the caller's parsed MDL.

    parts_by_lod maps zero-based LOD indexes to lists of part dicts. Missing
    LODs remain exactly unchanged. To maintain the silhouette in distant LODs,
    callers retain static reduced geometry there rather than dropping it.
    Disabling motion keeps the independent geometry present at the rest pose.
    """
    result = copy.deepcopy(model)
    part_report = []
    for lod_index, parts in sorted(parts_by_lod.items()):
        if not isinstance(lod_index, int) or not 0 <= lod_index < len(result['lods']):
            raise ValueError(f'Invalid zero-based LOD index {lod_index!r}')
        root = result['lods'][lod_index]['node']
        names = {node.get('name') for node in flatten_nodes(root)}
        children = root.setdefault('children', [])
        for part in parts:
            arguments = dict(part)
            kind = arguments.pop('kind')
            if arguments.get('name') in names:
                raise ValueError(f'Duplicate node name {arguments["name"]!r}')
            enabled = arguments.get('enabled', True)
            if kind == 'fan':
                arguments['enabled'] = enabled and animate_fans
                node = make_fan_node(**arguments)
            elif kind == 'louver':
                arguments['enabled'] = enabled and animate_louvers
                node = make_louver_node(**arguments)
            else:
                raise ValueError(f'Unknown animated part kind {kind!r}')
            node_id = len(list(flatten_nodes(root)))
            children.append(node)
            names.add(node['name'])
            part_report.append({'lod': lod_index, 'node_id': node_id,
                                'kind': kind, 'name': node['name'],
                                'mesh': node['mesh'], 'pivot': list(part['pivot']),
                                'enabled': bool(node.get('animations'))})
    proof = assert_original_nodes_preserved(model, result)
    return result, {'parts': part_report, 'preservation': proof,
                    'model_editor_tested': False, 'game_tested': False,
                    'behavior': 'decorative forever loops; no temperature simulation',
                    'documentation': DOCUMENTATION}


def sample_keyframe_rotation(node, time_ms):
    """Linear angles for static animation-sweep QA; not a game-engine emulator."""
    frames = node['animations']['forever']['params']['keyframes']
    duration = frames[-1]['time']
    time_ms %= duration
    for start, end in zip(frames, frames[1:]):
        if start['time'] <= time_ms <= end['time']:
            portion = (time_ms - start['time']) / (end['time'] - start['time'])
            return [a + (b - a) * portion for a, b in zip(start['rot'], end['rot'])]
    raise AssertionError('No keyframe interval')


def _multiply_matrix(a, b):
    return [sum(a[k * 4 + row] * b[column * 4 + k] for k in range(4))
            for column in range(4) for row in range(4)]


def _translation(vector):
    matrix = list(IDENTITY)
    matrix[12:15] = vector
    return matrix


def _rotation(axis, degrees):
    angle = math.radians(degrees)
    cosine, sine = math.cos(angle), math.sin(angle)
    matrix = list(IDENTITY)
    if axis == 0:
        matrix[5], matrix[6], matrix[9], matrix[10] = cosine, sine, -sine, cosine
    elif axis == 1:
        matrix[0], matrix[2], matrix[8], matrix[10] = cosine, -sine, sine, cosine
    else:
        matrix[0], matrix[1], matrix[4], matrix[5] = cosine, sine, -sine, cosine
    return matrix


def evaluate_keyframe_transform(node, time_ms):
    """Return a column-major 4x4 node-to-parent matrix sampled from native MDL.

    This CPU sampler is for QA/illustrative rendering, NOT a game test. It uses
    linear keyframe interpolation and XYZ Euler rotation, suitable for our
    one-axis fan/louver loops. Parent-to-world transform is caller's concern.
    Animation origin is node-local; base node transform is applied exactly once.
    """
    base = node.get('transf', IDENTITY)
    animation = node.get('animations', {}).get('forever')
    if not animation:
        return list(base)
    if animation['type'] != 'KEYFRAME':
        raise ValueError('This scoped sampler accepts inline KEYFRAME only')
    parameters = animation['params']
    frames = parameters['keyframes']
    if len(frames) < 2:
        raise ValueError('At least two keyframes are required')
    duration = frames[-1]['time']
    local_time = time_ms % duration
    if not animation.get('forward', True):
        local_time = (duration - local_time) % duration
    for start, end in zip(frames, frames[1:]):
        if start['time'] <= local_time <= end['time']:
            portion = (local_time - start['time']) / (end['time'] - start['time'])
            def interpolate(key):
                return [a + (b - a) * portion for a, b in zip(
                    start.get(key, [0., 0., 0.]), end.get(key, [0., 0., 0.]))]
            rotation, translation = interpolate('rot'), interpolate('transl')
            origin = parameters.get('origin', [0., 0., 0.])
            turn = list(IDENTITY)
            for axis, degrees in enumerate(rotation):
                turn = _multiply_matrix(_rotation(axis, degrees), turn)
            local = _multiply_matrix(
                _translation([a + b for a, b in zip(origin, translation)]),
                _multiply_matrix(turn, _translation([-value for value in origin])))
            return _multiply_matrix(base, local)
    raise AssertionError('No keyframe interval')


def patch_mod_lua(text):
    """Return a bounded patch of the existing v25 mod.lua, without file writes.

    Exact context is required; fail instead of altering an unfamiliar mod file.
    Caller installs animation_options_v26.lua as res/scripts/fxn5c_animation_v26.lua
    and adds the five documented translation keys in strings.lua.
    """
    text = text.replace('\r\n', '\n')
    require = 'local roofAnimation26 = require "fxn5c_animation_v26"\n'
    if require in text:
        raise ValueError('Animation options patch already applied')
    edits = [
        ('    params = {\n', '    params = {\n      roofAnimation26.parameter(_),\n'),
        ('    -- Index 1 preserves the original MDL availability; no modifier is registered.\n'
         '    if policy == 1 then return end\n',
         '    -- Keep the modifier for animation choices even when preserving years.\n'
         '    local animationMode = params["codex_fxn5c_roof_animation"] or 0\n'),
        ('      if not ownModel(fileName) or type(model) ~= "table" then return model end\n',
         '      if not ownModel(fileName) or type(model) ~= "table" then return model end\n'
         '      roofAnimation26.apply(model, animationMode)\n'),
        ('      if type(metadata) == "table" and type(metadata.availability) == "table" then\n',
         '      if policy ~= 1 and type(metadata) == "table" and type(metadata.availability) == "table" then\n'),
    ]
    for before, after in edits:
        if text.count(before) != 1:
            raise ValueError(f'Expected one exact mod.lua patch context: {before!r}')
        text = text.replace(before, after, 1)
    return require + text


def self_test():
    """Small independent tests requiring no Blender/game installation."""
    baseline = {'version': 1, 'metadata': {'railVehicle': {'configs': [{
        'frontForwardParts': [4], 'axles': ['vehicle/train/example_axle.msh']}]}},
        'lods': [{'visibleFrom': 0, 'visibleTo': 100, 'static': False, 'node': {
            'name': 'RootNode', 'transf': list(IDENTITY), 'children': [
                {'name': 'body'}, {'name': 'bogie', 'children': [
                    {'name': 'wheel'}, {'name': 'old_front_light'}]}]}}]}
    parts = {0: [
        {'kind': 'fan', 'name': PREFIX + 'fan_0',
         'mesh': 'vehicle/train/fxn5c/fan_lod0.msh',
         'materials': ['vehicle/train/fxn5c/metal.mtl'], 'pivot': [2.4, -1.5, 4.3]},
        {'kind': 'louver', 'name': PREFIX + 'louver_0',
         'mesh': 'vehicle/train/fxn5c/louver_lod0.msh',
         'materials': ['vehicle/train/fxn5c/metal.mtl'], 'pivot': [-8., -1.6, 4.2]},
    ]}
    snapshot = copy.deepcopy(baseline)
    model, report = append_animation_nodes(baseline, parts)
    assert baseline == snapshot, 'Input mutation'
    fan, blade = model['lods'][0]['node']['children'][-2:]
    assert sample_keyframe_rotation(fan, 375) == [0., 90., 0.]
    assert sample_keyframe_rotation(fan, 1500) == [0., 0., 0.]
    assert sample_keyframe_rotation(blade, 7000) == [30., 0., 0.]
    assert sample_keyframe_rotation(blade, 16000) == [0., 0., 0.]
    assert report['parts'][0]['node_id'] == 5
    assert fan['transf'][12:15] == [2.4, -1.5, 4.3]
    assert fan['animations']['forever']['params']['origin'] == [0., 0., 0.]
    static, _ = append_animation_nodes(baseline, parts, animate_louvers=False)
    assert not static['lods'][0]['node']['children'][-1].get('animations')
    world_fan = make_fan_node('a.msh', ['a.mtl'], [3, -1, 4],
                             PREFIX + 'test', mesh_local=False)
    assert world_fan['transf'] == IDENTITY
    assert world_fan['animations']['forever']['params']['origin'] == [3., -1., 4.]
    def point(matrix, value):
        return [sum(matrix[column * 4 + row] * value[column] for column in range(3))
                + matrix[12 + row] for row in range(3)]
    for time_ms in (0, 375, 750, 1125, 1500):
        local_matrix = evaluate_keyframe_transform(fan, time_ms)
        assert all(abs(a - b) < 1e-10 for a, b in zip(
            point(local_matrix, [0., 0., 0.]), [2.4, -1.5, 4.3]))
        world_matrix = evaluate_keyframe_transform(world_fan, time_ms)
        assert all(abs(a - b) < 1e-10 for a, b in zip(
            point(world_matrix, [3., -1., 4.]), [3., -1., 4.]))
    assert all(abs(a - b) < 1e-10 for a, b in zip(
        evaluate_keyframe_transform(fan, 0), evaluate_keyframe_transform(fan, 1500)))
    for path in ('../a.msh', 'C:/a.msh', '/a.msh'):
        try:
            make_fan_node(path, ['a.mtl'], [0, 0, 0], PREFIX + 'bad')
        except ValueError:
            pass
        else:
            raise AssertionError('Unsafe resource path accepted')
    return {'status': 'STATIC_UNIT_TEST_PASS', 'tests': [
        'fan horizontal Y rotation and seamless rest pose',
        'louver X hinge and cycle holds', 'nonmutating root-tail insertion',
        'original metadata and preorder node IDs preserved',
        'independent motion-disable options', 'local/world pivot conventions',
        'resource path rejection', 'sampled 0/quarter/half/full-cycle pivot invariance'],
        'game_tested': False}


if __name__ == '__main__':
    import json
    print(json.dumps(self_test(), ensure_ascii=False, indent=2))
