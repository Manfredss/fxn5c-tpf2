"""Independent static native audit of the isolated FXN5C0001 prototype.

Decode the actual 13-model closure without historical hard-coded loaders.
Source/geometry correspondence is a separate audit; this is not engine testing.
"""
from pathlib import Path, PurePosixPath
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import struct
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fxn5c_v40_source'
MOD_REL = Path('staging/codex_fxn5c_1')
MOD = ROOT / MOD_REL
BASE_MOD = BASE / MOD_REL
RES = MOD / 'res'
STEM = 'fxn5c_prototype_0001'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runtime'))
from verify_native import read_lua
from verify_native_v24 import SharedResources, flatten, IDENTITY

BUDGETS = (500000, 220000, 6000)
RECIPES = {'build_v41.py', 'prototype_head_v41.py', 'prototype_access_v41.py', 'prototype_livery_v41.py'}
PALETTE = {'proto_red', 'proto_gold', 'proto_yellow', 'proto_roof'}
FIELDS = {p + ('Forward' if d == 'fwd' else 'Backward') + 'Parts': (p, d)
          for d in ('fwd', 'bwd') for p in ('front', 'inner', 'back')}
WHITE = 'vehicle/train/fxn5c/lamp_moon_v24.mtl'
RED = 'vehicle/train/fxn5c/lamp_red.mtl'
EXTERNAL = {'vehicle/train/wagon_standard.mtl',
            'vehicle/train/emissive/train_all_lights.mtl',
            'vehicle/train/emissive/train_red_lights.mtl'}
PREFIX = 'fxn5c_v26_'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def checked(root, relative):
    ref = PurePosixPath(str(relative).replace('\\', '/'))
    assert not ref.is_absolute() and '..' not in ref.parts, ('unsafe relative path', str(relative))
    path = (root / ref.as_posix()).resolve()
    assert path.is_relative_to(root.resolve()) and path.is_file(), ('missing/scoped input', str(path))
    return path


def visit(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from visit(child)
    elif isinstance(value, list):
        for child in value:
            yield from visit(child)


def motion_material(ref):
    expected = {'blue': 'proto_red', 'light_blue': 'proto_red',
                'yellow': 'proto_red', 'roof': 'proto_roof'}
    prefix = 'vehicle/train/fxn5c/'
    if ref.startswith(prefix) and ref.endswith('.mtl'):
        key = ref[len(prefix):-4]
        if key in expected:
            return prefix + expected[key] + '.mtl'
    return ref


class Resources41(SharedResources):
    """Keep only the decoder/cache; do not invoke old load/native_closure."""
    def material(self, ref):
        if ref in self.external_materials:
            return None
        path = RES / 'models/material' / ref
        if not path.is_file():
            assert ref in EXTERNAL, ('missing material', ref)
            self.external_materials.add(ref)
            return None
        path = checked(RES / 'models/material', ref)
        first = path not in self.lua
        material = self.table(path)
        assert material['type'] in {'PHYSICAL_NRML_MAP', 'PHYS_TRANSPARENT',
                                    'EMISSIVE', 'SKINNING_PHYS_NRML_MAP'}, ('material type', ref)
        for row in visit(material):
            if row.get('fileName'):
                texture = checked(RES / 'textures', row['fileName'])
                self.inputs[texture.relative_to(ROOT).as_posix()] = sha(texture)
        if first:
            self.material_count += 1
        return material

    def decode_mesh(self, ref):
        checked(RES / 'models/mesh', ref)
        checked(RES / 'models/mesh', ref + '.blob')
        return super().decode_mesh(ref)


def new_part_geometry(row, resources):
    path = checked(ROOT, row['target'])
    assert path == checked(RES / 'models/mesh', row['mesh'])
    assert row['mesh'].startswith('vehicle/train/' + STEM + '/'), ('prototype part namespace', row['mesh'])
    assert row['mesh_sha256'] == sha(path)
    assert row['blob_sha256'] == sha(str(path) + '.blob')
    assert row['transf'] == IDENTITY, ('exported world-space part transform', row['attachment'])
    assert row['source_objects'] and len(set(row['source_objects'])) == len(row['source_objects'])
    mesh = resources.decode_mesh(row['mesh'])
    assert mesh['triangles'] == row['triangles']
    assert len(mesh['attributes']['position']) == row['vertices']
    assert len(row['materials']) == mesh['submeshes']
    blob = Path(str(path) + '.blob').read_bytes()
    points = mesh['attributes']['position'].astype(np.float64)
    low, high = np.asarray(row['bbMin'], dtype=float), np.asarray(row['bbMax'], dtype=float)
    assert low.shape == high.shape == (3,) and np.isfinite(low).all() and np.isfinite(high).all()
    assert np.all(low <= high), ('invalid declared part bounds', row['mesh'])
    # Source bounds include every source vertex, while the exporter only emits
    # face corners. They may conservatively contain unused source vertices.
    assert np.all(points.min(axis=0) >= low - 1e-5) and np.all(points.max(axis=0) <= high + 1e-5), (
        'decoded part outside its declared source bounds', row['mesh'])
    for sub in resources.descriptors[row['mesh']]['subMeshes']:
        index = sub['indices']['position']
        ids = np.frombuffer(blob, dtype='<u4', count=index['count']//4, offset=index['offset']).reshape(-1, 3)
        triangle = points[ids]
        zero = np.all(np.cross(triangle[:, 1] - triangle[:, 0], triangle[:, 2] - triangle[:, 0]) == 0, axis=1)
        assert not bool(zero.any()), ('zero-area new geometry', row['mesh'])
    for mat in row['materials']:
        resources.material(mat)
    if row['attachment'] == 'body':
        assert not set(row['materials']) & {'vehicle/train/fxn5c/blue.mtl', 'vehicle/train/fxn5c/light_blue.mtl'}
        assert 'vehicle/train/fxn5c/proto_red.mtl' in row['materials']
        assert 'vehicle/train/fxn5c/proto_yellow.mtl' in row['materials']
    return dict(lod=row['lod'], attachment=row['attachment'], mesh=row['mesh'],
                triangles=mesh['triangles'], vertices=len(points), finite_attributes=True,
                normals_tangents_indices_valid=True, zero_area_triangles=0)


def verify_strings():
    old = read_lua(BASE_MOD / 'strings.lua')
    current = read_lua(MOD / 'strings.lua')
    assert set(current) == set(old)
    new_keys = {'VEHICLE_FXN5C_0001_NAME', 'VEHICLE_FXN5C_0001_DESC'}
    names = {}
    for language, original in old.items():
        values = current[language]
        assert set(values) == set(original) | new_keys
        for key in original:
            if key not in ('MOD_NAME', 'MOD_DESC'):
                assert values[key] == original[key], ('production localization changed', language, key)
        assert values['MOD_NAME'] == original['MOD_NAME'].replace('v0.40', 'v0.41')
        assert values['MOD_DESC'] == 'v0.41: ' + values['VEHICLE_FXN5C_0001_DESC'] + '\n\n' + original['MOD_DESC']
        zh = language.lower().startswith(('zh', 'cn'))
        expected = '复兴 FXN5C 0001 红色原型车' if zh else 'FXN5C 0001 Red Prototype'
        assert values['VEHICLE_FXN5C_0001_NAME'] == expected
        assert isinstance(values['VEHICLE_FXN5C_0001_DESC'], str) and values['VEHICLE_FXN5C_0001_DESC']
        names[language] = expected
    assert len(names) >= 2, 'Both language names are required'
    before = (BASE_MOD / 'mod.lua').read_text(encoding='utf8')
    assert before.count('minorVersion = 40') == before.count('local ownModels = {') == 1
    expected = before.replace('local ownModels = {', 'local ownModels = {\n  ["vehicle/train/' + STEM + '.mdl"] = true,', 1)
    expected = expected.replace('minorVersion = 40', 'minorVersion = 41')
    assert (MOD / 'mod.lua').read_text(encoding='utf8') == expected, 'Unexpected option/loader changes'
    return names


def verify_ui(manifest):
    """Optional during static construction, exact and complete once declared."""
    rows = manifest.get('ui_artifacts', [])
    assert isinstance(rows, list), 'ui_artifacts must be an array'
    if not rows:
        return {}, False
    expected = {(MOD_REL / 'res/textures/ui' / folder / 'vehicle/train' / (STEM + '.png')).as_posix(): size
                for folder, size in (('models_20', (192, 40)), ('models_small', (640, 150)))}
    assert len(rows) == 2 and {r['file'] for r in rows} == set(expected), 'Declare exactly both prototype UI images'
    records = {}
    for row in rows:
        relative = row['file']
        size = expected[relative]
        assert (row['width'], row['height']) == size, ('Declared UI dimensions', relative)
        path = checked(ROOT, relative)
        assert sha(path) == row['sha256'], ('UI hash mismatch', relative)
        with path.open('rb') as stream:
            header = stream.read(33)
        assert len(header) == 33 and header[:8] == b'\x89PNG\r\n\x1a\n', ('Invalid PNG signature', relative)
        assert struct.unpack('>I', header[8:12])[0] == 13 and header[12:16] == b'IHDR', ('Invalid PNG IHDR', relative)
        assert struct.unpack('>II', header[16:24]) == size, ('Actual UI dimensions', relative)
        records[relative] = dict(sha256=row['sha256'], width=size[0], height=size[1],
                                 png_magic_and_ihdr_verified=True)
    return records, True


def prototype_contract(model, baseline, parts, resources):
    assert set(model) == set(baseline)
    for key in set(model) - {'lods', 'metadata', 'boundingInfo'}:
        assert model[key] == baseline[key], ('collider/outer contract changed', key)
    # The wider prototype access gear needs a conservative visual culling
    # envelope. Recompute precisely from declared world-space part bounds;
    # never accept an arbitrary bounding box or silently enlarge the collider.
    expected_bounds = deepcopy(baseline['boundingInfo'])
    for axis in range(3):
        expected_bounds['bbMin'][axis] = min(baseline['boundingInfo']['bbMin'][axis],
                                              *(row['bbMin'][axis] for row in parts))
        expected_bounds['bbMax'][axis] = max(baseline['boundingInfo']['bbMax'][axis],
                                              *(row['bbMax'][axis] for row in parts))
    assert model['boundingInfo'] == expected_bounds, 'Prototype bounds must equal baseline/part union'
    old_min = np.asarray(baseline['boundingInfo']['bbMin'], dtype=float)
    old_max = np.asarray(baseline['boundingInfo']['bbMax'], dtype=float)
    new_min = np.asarray(expected_bounds['bbMin'], dtype=float)
    new_max = np.asarray(expected_bounds['bbMax'], dtype=float)
    assert np.all(new_min <= old_min) and np.all(new_max >= old_max), 'Original envelope must remain contained'
    assert np.all(old_min - new_min < .15) and np.all(new_max - old_max < .15), 'Excessive prototype envelope expansion'
    assert np.array_equal(new_min[[0, 2]], old_min[[0, 2]]) and np.array_equal(new_max[[0, 2]], old_max[[0, 2]]), (
        'Only lateral access-gear envelope expansion is authorized')
    metadata = deepcopy(baseline['metadata'])
    metadata['description'] = {'name': 'VEHICLE_FXN5C_0001_NAME', 'description': 'VEHICLE_FXN5C_0001_DESC'}
    metadata['availability'] = {'yearFrom': 0, 'yearTo': 0}
    metadata['transportVehicle']['groupFileName'] = ''
    assert len(model['lods']) == len(model['metadata']['railVehicle']['configs']) == 3
    reports, mapping, motion_counts = [], [], []
    for lod_index, lod in enumerate(model['lods']):
        old_lod = baseline['lods'][lod_index]
        assert {k: v for k, v in lod.items() if k != 'node'} == {k: v for k, v in old_lod.items() if k != 'node'}
        rows = [row for row in parts if row['lod'] == lod_index]
        by_attachment = {row['attachment']: row for row in rows}
        assert len(rows) == len(by_attachment), ('duplicate attachment', lod_index)
        fixed = {'body', 'cab_interior', 'vehicle_markings', 'light24_fwd', 'light24_bwd'} if lod_index < 2 else {'body'}
        assert fixed <= set(by_attachment)
        if lod_index == 2:
            assert not set(by_attachment) & {'cab_interior', 'vehicle_markings', 'light24_fwd', 'light24_bwd'}
        glass = [row for row in rows if row['attachment'] not in fixed]
        if lod_index < 2:
            assert glass, ('no detailed prototype glass', lod_index)
        else:
            # Distant glazing is deliberately opaque dark gray over the
            # uncut hull, so red paint cannot bleed through it. Saved-source
            # audit independently checks all 12 proxy objects/materials.
            assert not glass, 'Distant glazing must be merged into body'
            assert 'vehicle/train/fxn5c/graphite.mtl' in by_attachment['body']['materials']
            assert all(resources.material(mat)['type'] != 'PHYS_TRANSPARENT'
                       for mat in by_attachment['body']['materials']), 'Transparent distant hull proxy'
        for row in glass:
            assert len(row['source_objects']) == 1
            assert all(resources.material(m)['type'] == 'PHYS_TRANSPARENT' for m in row['materials']), ('non-glass additional attachment', row['attachment'])

        expected = deepcopy(old_lod['node'])
        children = []
        for child in expected['children']:
            name = child['name']
            if name.startswith(('glazing_', 'light24_')):
                continue
            if name in by_attachment:
                row = by_attachment[name]
                assert name in fixed
                for key in ('mesh', 'materials', 'transf'):
                    child[key] = deepcopy(row[key])
            for node, _, _ in flatten(child)[0]:
                if node['name'].startswith(PREFIX) and 'materials' in node:
                    node['materials'] = [motion_material(m) for m in node['materials']]
            children.append(child)
        for row in glass:
            children.append(dict(name=row['attachment'], **{k: deepcopy(row[k]) for k in ('mesh', 'materials', 'transf')}))
        if lod_index < 2:
            for direction in ('fwd', 'bwd'):
                row = by_attachment['light24_' + direction]
                assert len(row['materials']) == 2 and set(row['materials']) == {WHITE, RED}, ('white/red light slots', row['mesh'])
                for position in ('front', 'inner', 'back'):
                    children.append(dict(name='light24_' + position + '_' + direction,
                                         **{k: deepcopy(row[k]) for k in ('mesh', 'materials', 'transf')}))
        children.sort(key=lambda n: n['name'] == 'vehicle_markings')
        expected['children'] = children
        assert lod['node'] == expected, ('unapproved skeleton/static/motion change', lod_index)
        nodes, by_name = flatten(lod['node'])
        old_nodes, old_names = flatten(old_lod['node'])
        assert nodes[0][0]['name'] == 'RootNode' and nodes[0][1] == IDENTITY
        assert by_name['body'][0] == 1 and by_name['body'][1][1] == IDENTITY
        light_sources = {'light24_' + position + '_' + direction: 'light24_' + direction
                         for position, direction in FIELDS.values()} if lod_index < 2 else {}
        for index, (node, matrix, parent) in enumerate(nodes):
            source_attachment = light_sources.get(node['name'], node['name'])
            if source_attachment in by_attachment:
                row = by_attachment[source_attachment]
                assert all(node[key] == row[key] for key in ('mesh', 'materials', 'transf')), (
                    'native instance/source part mismatch', lod_index, node['name'], source_attachment)
                mapping.append(dict(model=STEM, lod=lod_index, attachment=node['name'],
                                    source_attachment=source_attachment,
                                    mesh_ref=node['mesh'], target=row['target'], materials=node['materials'],
                                    local_transform=node['transf'], world_transform=matrix,
                                    parent=nodes[parent][0]['name'] if parent is not None else None))
        motion = [node for node, _, _ in nodes if node['name'].startswith(PREFIX)]
        old_motion = [node for node, _, _ in old_nodes if node['name'].startswith(PREFIX)]
        assert [n['name'] for n in motion] == [n['name'] for n in old_motion]
        for node, previous in zip(motion, old_motion):
            wanted = deepcopy(previous)
            # Animation parents are groups, not drawable meshes. Preserve the
            # entire subtree while applying the same allowed material mapping
            # to its drawable descendants as the builder does.
            for descendant, _, _ in flatten(wanted)[0]:
                if descendant['name'].startswith(PREFIX) and 'materials' in descendant:
                    descendant['materials'] = [motion_material(m) for m in descendant['materials']]
            assert node == wanted
            if 'mesh' in node:
                assert sha(checked(RES / 'models/mesh', node['mesh'])) == sha(checked(BASE_MOD / 'res/models/mesh', node['mesh']))
                assert sha(checked(RES / 'models/mesh', node['mesh'] + '.blob')) == sha(checked(BASE_MOD / 'res/models/mesh', node['mesh'] + '.blob'))
        motion_counts.append(len(motion))
        # Complete gear subtrees (including skin weights, bind refs, wheel and
        # bogie order) remain exact, not merely in the same broad region.
        protected = ['running_gear_skin'] if lod_index < 2 else ['b1_grp', 'b2_grp']
        protected += [name for name in old_names if name.startswith('conn17_body_A_')]
        for name in protected:
            assert by_name[name][1][0] == old_names[name][1][0], ('running gear changed', name, lod_index)
            assert by_name[name][1][1] == old_names[name][1][1]

        config = model['metadata']['railVehicle']['configs'][lod_index]
        assigned = []
        for field, (position, direction) in FIELDS.items():
            ids = config[field]
            if lod_index < 2:
                name = 'light24_' + position + '_' + direction
                assert ids == [by_name[name][0]], ('lamp field/index mismatch', lod_index, field)
                assigned += ids
                target = nodes[ids[0]][0]
                assert target['name'] == name and target['name'].startswith('light24_')
                assert set(target['materials']) == {WHITE, RED}
            else:
                assert not ids, ('far LOD light IDs', field)
            metadata['railVehicle']['configs'][lod_index][field] = deepcopy(ids)
        assert len(assigned) == len(set(assigned)) == (6 if lod_index < 2 else 0)
        light_names = {name for name in by_name if name.startswith('light24_')}
        assert light_names == ({'light24_' + p + '_' + d for p, d in FIELDS.values()} if lod_index < 2 else set())
        assert not set(by_name) & {'headlights_fwd', 'headlights_bwd', 'taillights_fwd', 'taillights_bwd'}
        reports.append(dict(lod=lod_index, nodes=len(nodes), glass_attachments=len(glass),
                            inherited_motion_nodes=len(motion), distinct_lamp_part_ids=assigned,
                            body_child_index=1, running_gear_exact=True, source_exports=len(rows)))
    assert model['metadata'] == metadata, 'Unapproved prototype simulation/emitter/other metadata changes'
    assert all(e['child'] == 1 for e in model['metadata']['particleSystem']['emitters'])
    assert model['metadata']['particleSystem'] == baseline['metadata']['particleSystem']
    return reports, mapping, motion_counts


def main():
    manifest_path = ROOT / 'manifest_v41.json'
    m = load(manifest_path)
    old_manifest = load(BASE / 'manifest_v40.json')
    assert old_manifest['status'] == 'NATIVE_STATIC_PASS'
    assert m['version'] == '0.41' and m['baseline_version'] == '0.40'
    assert m['prototype'] == STEM and m['number'] == '0001'
    assert m['baseline_manifest_sha256'] == sha(BASE / 'manifest_v40.json')
    assert m['baseline_models_unchanged'] is True and m['provisional_dynamics'] is True
    assert all(m[key] is False for key in ('game_verified', 'model_editor_verified', 'installed', 'published'))
    assert set(m['recipe_sha256']) == RECIPES
    for name, digest in m['recipe_sha256'].items():
        assert sha(checked(ROOT, name)) == digest, ('recipe changed after build', name)
    assert len(m['sources']) == 3
    expected_sources = {'fxn5c_prototype_0001_source.blend': 'fxn5c_source.blend',
                        'runtime/final41_prototype_lod1.blend': 'runtime/final40_fxn5c_lod1.blend',
                        'runtime/final41_prototype_lod2.blend': 'runtime/final40_fxn5c_lod2.blend'}
    assert {r['file']: r['baseline'] for r in m['sources']} == expected_sources
    source_hashes = {}
    old_source_hashes = {r['file']: r['sha256'] for r in old_manifest['sources']}
    for row in m['sources']:
        assert sha(checked(ROOT, row['file'])) == row['sha256']
        assert sha(checked(BASE, row['baseline'])) == row['baseline_sha256'] == old_source_hashes[row['baseline']]
        source_hashes[row['file']] = row['sha256']
    parts = m['parts']
    assert parts and {r['lod'] for r in parts} == {0, 1, 2}
    assert len({r['mesh'] for r in parts}) == len(parts)
    assert {(r['lod'], r['attachment']) for r in parts if r['attachment'] == 'body'} == {(i, 'body') for i in range(3)}
    assert len(m['changes']) == 3 and {row['lod'] for row in m['changes']} == {0, 1, 2}
    source_motion_counts = {}
    for change in m['changes']:
        hashes = change['motion_source_hashes']
        assert isinstance(hashes, dict)
        assert bool(hashes) == (change['lod'] < 2), ('missing/unexpected motion source record', change['lod'])
        assert all(isinstance(name, str) and isinstance(digest, str) and len(digest) == 64
                   and set(digest) <= set('0123456789abcdef') for name, digest in hashes.items())
        source_motion_counts[str(change['lod'])] = len(hashes)
    assets = {r['file']: r['sha256'] for r in m['assets']}
    expected_assets = {(MOD_REL / 'res/models/material/vehicle/train/fxn5c' / (key + '.mtl')).as_posix() for key in PALETTE}
    expected_assets |= {(MOD_REL / 'res/textures/models/vehicle/train/fxn5c' / (key + suffix + '.tga')).as_posix()
                        for key in PALETTE for suffix in ('_surface', '_rough', '_mga', '_normal')}
    assert len(assets) == len(m['assets']) and set(assets) == expected_assets
    for relative, digest in assets.items():
        assert sha(checked(ROOT, relative)) == digest
    ui_records, ui_verified = verify_ui(m)
    old_files = {p.relative_to(BASE).as_posix() for p in BASE_MOD.rglob('*') if p.is_file()}
    new_files = {p.relative_to(ROOT).as_posix() for p in MOD.rglob('*') if p.is_file()}
    prototype_model = (MOD_REL / 'res/models/model/vehicle/train' / (STEM + '.mdl')).as_posix()
    declared = set(assets) | set(ui_records) | {prototype_model}
    declared |= {r['target'] for r in parts} | {r['target'] + '.blob' for r in parts}
    assert not declared & old_files, ('new prototype assets overwrite production', sorted(declared & old_files))
    assert new_files == old_files | declared, ('undeclared/missing staging files', sorted(new_files - old_files - declared), sorted((old_files | declared) - new_files))
    mutable = {(MOD_REL / name).as_posix() for name in ('mod.lua', 'strings.lua')}
    preserved = sorted(old_files - mutable)
    for relative in preserved:
        assert sha(checked(ROOT, relative)) == sha(checked(BASE, relative)), ('production file changed', relative)
    names = verify_strings()
    resources = Resources41()
    part_reports = [new_part_geometry(row, resources) for row in parts]
    model_paths = sorted((RES / 'models/model/vehicle/train').glob('*.mdl'))
    previous_paths = sorted((BASE_MOD / 'res/models/model/vehicle/train').glob('*.mdl'))
    assert len(previous_paths) == 12 and len(model_paths) == 13
    assert {p.stem for p in model_paths} == {p.stem for p in previous_paths} | {STEM}
    models = {p.stem: resources.table(p) for p in model_paths}
    inherited = read_lua(BASE_MOD / 'res/models/model/vehicle/train/fxn5c.mdl')
    prototype_reports, mapping, motion_counts = prototype_contract(models[STEM], inherited, parts, resources)

    model_reports, animation_refs, material_refs = [], set(), set()
    for stem, model in models.items():
        assert len(model['lods']) == 3
        lod_counts = []
        for lod_index, lod in enumerate(model['lods']):
            total = 0
            for node, matrix, parent in flatten(lod['node'])[0]:
                reference = node.get('mesh') or node.get('skin')
                if reference:
                    mesh = resources.decode_mesh(reference)
                    materials = node.get('materials', node.get('skinMaterials'))
                    assert isinstance(materials, list) and len(materials) == mesh['submeshes']
                    for material in materials:
                        resources.material(material)
                        material_refs.add(material)
                    low, high = resources.bounds(reference, matrix)
                    assert np.all(low >= np.asarray(model['boundingInfo']['bbMin']) - 1e-4), (stem, lod_index, reference, 'minimum bounds', low.tolist())
                    assert np.all(high <= np.asarray(model['boundingInfo']['bbMax']) + 1e-4), (stem, lod_index, reference, 'maximum bounds', high.tolist())
                    total += mesh['triangles']
                    resources.referenced_meshes.add(reference)
                for animation in node.get('animations', {}).values():
                    assert animation['type'] == 'FILE_REF'
                    ref = animation['params']['id']
                    path = checked(RES / 'models/animation', ref)
                    assert sha(path) == sha(checked(BASE_MOD / 'res/models/animation', ref))
                    resources.table(path)
                    animation_refs.add(ref)
            assert total < BUDGETS[lod_index], ('LOD triangle budget exceeded', stem, lod_index, total, BUDGETS[lod_index])
            lod_counts.append(total)
        assert lod_counts[0] > lod_counts[1] > lod_counts[2]
        model_reports.append(dict(model=stem, instanced_triangles=lod_counts))
        print('VERIFY41_BUDGET', stem, lod_counts, flush=True)
    assert len(animation_refs) == 27, '26 shutters plus the shared fan file'
    animation_dir = RES / 'models/animation'
    previous_animation_dir = BASE_MOD / 'res/models/animation'
    current_animation_files = {p.relative_to(animation_dir).as_posix(): sha(p) for p in animation_dir.rglob('*') if p.is_file()}
    previous_animation_files = {p.relative_to(previous_animation_dir).as_posix(): sha(p) for p in previous_animation_dir.rglob('*') if p.is_file()}
    assert current_animation_files == previous_animation_files
    assert all(row['mesh'] in resources.referenced_meshes for row in parts), 'Unreferenced prototype export'
    for row in old_manifest['animated']:
        assert sha(checked(ROOT, row['target'])) == row['mesh_sha256']
        assert sha(checked(ROOT, row['target'] + '.blob')) == row['blob_sha256']
    assert len(old_manifest['animated']) == 272

    # Refresh every render input from the current files, not copied v40 JSON.
    outputs = {}
    for stem, model in models.items():
        path = ROOT / f'native_scene_{stem}.json'
        path.write_text(json.dumps(model), encoding='utf8')
        outputs[path.name] = sha(path)
    for name, value in [('native_scene.json', models['fxn5c']), ('native_scene_jinwen.json', models['fxn5c_jinwen']),
                        ('native_meshes.json', resources.descriptors), ('native_prototype_attachments_v41.json', mapping)]:
        path = ROOT / name
        path.write_text(json.dumps(value), encoding='utf8')
        outputs[name] = sha(path)
    for path in (MOD / 'mod.lua', MOD / 'strings.lua'):
        resources.inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    for relative, proof in ui_records.items():
        resources.inputs[relative] = proof['sha256']
    report = dict(status='PASS', scope='independent native static prototype audit; not source correspondence or engine execution',
                  generated_utc=datetime.now(timezone.utc).isoformat(), models=13, variants=11,
                  preserved_production_models=12, prototype=STEM, provisional_dynamics=True,
                  independent_purchase_entry=True, availability={'yearFrom': 0, 'yearTo': 0},
                  production_files_preserved=len(preserved), preserved_paths=preserved,
                  prototype_exports=part_reports, prototype_lods=prototype_reports, models_report=model_reports,
                  motion_node_counts=motion_counts, all_272_motion_interface_meshes_unchanged=True,
                  builder_recorded_motion_source_hash_counts=source_motion_counts,
                  source_motion_hash_scope='builder pre/post protection records; independent saved-source correspondence remains separate',
                  prototype_bounding_info=models[STEM]['boundingInfo'],
                  bounding_info_exact_baseline_and_export_part_union=True,
                  bounding_info_only_y_expansion_below_0_15m=True, collider_unchanged=True,
                  all_animation_files_unchanged=True, animation_refs=sorted(animation_refs),
                  animation_files_sha256=current_animation_files, production_localization_preserved=True,
                  localized_prototype_names=names, no_production_blue_in_prototype_body=True,
                  ui_verified=ui_verified, ui_artifacts=ui_records,
                  metadata_only_description_availability_group_and_six_lamp_lists_changed=True,
                  source_inputs_sha256=source_hashes, inputs_sha256=resources.inputs,
                  unique_meshes=resources.mesh_decode_count, materials=resources.material_count,
                  external_materials=sorted(resources.external_materials), render_inputs_sha256=outputs,
                  validator_sha256=sha(Path(__file__)),
                  helper_sha256={name: sha(ROOT / name) for name in ('verify_native.py', 'verify_native_v24.py')},
                  additional_source_geometry_correspondence_required=True,
                  game_verified=False, model_editor_verified=False, installed=False, published=False)
    report_path = ROOT / 'validation_v41.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    m['status'] = 'NATIVE_STATIC_PASS'
    m['validation_sha256'] = sha(report_path)
    manifest_path.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding='utf8')
    print('VERIFY41_PASS', len(preserved), len(models), resources.mesh_decode_count, flush=True)


if __name__ == '__main__':
    try:
        assert __debug__, 'Run without -O so all validation gates remain active'
        main()
    except Exception as error:
        (ROOT / 'validation_v41.json').write_text(json.dumps(dict(
            status='FAIL', error=repr(error), scope='native static checks; not engine execution',
            game_verified=False, model_editor_verified=False), indent=2), encoding='utf8')
        raise
