"""Independent prototype-only v43 -> v44 native static verification."""
from pathlib import Path, PurePosixPath
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import struct
import sys
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent/'fxn5c_v43_source'
MOD_REL = Path('staging/codex_fxn5c_1')
MOD, BASE_MOD = ROOT/MOD_REL, BASE/MOD_REL
RES = MOD/'res'
PROTO = 'fxn5c_prototype_0001'
BUDGETS = (500000, 220000, 6000)
RECIPES = {'build_v44.py', 'prototype_geometry_v44.py'}
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'runtime'))
from native_patch_v23 import decode, sha
from verify_native import read_lua
from verify_native_v24 import flatten, IDENTITY
from verify_v41 import Resources41
from roster_v21 import ROSTER, group_stem


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def checked(root, relative):
    ref = PurePosixPath(str(relative).replace('\\', '/'))
    assert not ref.is_absolute() and '..' not in ref.parts
    path = (root/ref.as_posix()).resolve()
    assert path.is_relative_to(root.resolve()) and path.is_file(), ('missing/scoped file', str(path))
    return path


def row_key(row):
    assert row['style'] == PROTO and row['lod'] in range(3)
    return row['style'], row['lod'], row['attachment']


def snapshot_world_matrices(root):
    result = {}
    def visit(node, parent):
        local = np.asarray(node['transf'], dtype=np.float32).reshape(4, 4).T
        world = (parent@local).astype(np.float32)
        result[node['name']] = world
        for child in node.get('children', []):
            visit(child, world)
    visit(root, np.eye(4, dtype=np.float32))
    return result


def source_contract(manifest):
    rows = manifest['sources']
    assert len(rows) == 3 and {(r['style'], r['lod']) for r in rows} == {(PROTO, i) for i in range(3)}
    old = {r['file']: r['sha256'] for r in load(BASE/'manifest_v43.json')['sources'] if r['style'] == PROTO}
    result = {}
    for row in rows:
        lod = row['lod']
        name = PROTO+'_source.blend' if lod == 0 else f'runtime/final43_{PROTO}_lod{lod}.blend'
        final = PROTO+'_source.blend' if lod == 0 else f'runtime/final44_{PROTO}_lod{lod}.blend'
        assert row['baseline_version'] == '0.43' and row['baseline'] == name and row['file'] == final
        assert sha(checked(BASE, name)) == row['baseline_sha256'] == old[name]
        assert sha(checked(ROOT, final)) == row['sha256']
        result[final] = row['sha256']
    return result


def zero_triangles(arrays, rows):
    points = arrays['position'][np.asarray([r[2] for r in rows])].astype(float)
    dead = np.all(np.cross(points[:,1]-points[:,0], points[:,2]-points[:,0]) == 0, axis=1)
    return Counter(r[0] for r, zero in zip(rows, dead) if zero)


def verify_patch(row):
    row_key(row)
    assert not row.get('before_normalization'), 'No historical retessellation exception authorized in v44'
    assert row['target'] == (MOD_REL/'res/models/mesh'/row['mesh_ref']).as_posix()
    assert row['mesh_ref'].startswith('vehicle/train/'+PROTO+'/')
    target, baseline = checked(ROOT, row['target']), checked(BASE, row['target'])
    assert sha(target) == row['mesh_sha256'] and sha(str(target)+'.blob') == row['blob_sha256']
    _, old, original_raw, original = decode(baseline, row['baseline_materials'])
    _, new, _, actual = decode(target, row['materials'])
    before, after = checked(ROOT, row['before']), checked(ROOT, row['after'])
    _, ba, _, br = decode(before, row['before_materials'])
    _, aa, _, ar = decode(after, row['after_materials'])
    assert all(np.isfinite(v).all() for arrays in (ba, aa, new) for v in arrays.values())
    bc, ac = Counter(r[0] for r in br), Counter(r[0] for r in ar)
    removed, added = bc-ac, ac-bc
    original_count = Counter(r[0] for r in original)
    assert removed or added, ('empty patch', row_key(row))
    assert not removed-original_count, ('source delta absent from immutable native baseline', row_key(row))
    assert Counter(r[0] for r in actual) == (original_count-removed+added)-zero_triangles(old, original)
    assert not zero_triangles(new, actual)
    pending, extra = added.copy(), []
    for signature, _, indices in ar:
        if pending[signature]:
            pending[signature] -= 1
            extra.extend(int(i) for i in indices)
    assert not sum(pending.values()) and set(old) == set(new) == set(aa)
    for key, values in old.items():
        assert values.tobytes() == new[key][:len(values)].tobytes(), ('original attributes changed', row_key(row), key)
        assert hashlib.sha256(original_raw[key]).hexdigest() == row['original_attribute_prefix_sha256'][key]
        assert aa[key][extra].astype('<f4').tobytes() == new[key][len(values):].tobytes(), ('added attributes differ', row_key(row), key)
    assert row['removed_triangles'] == sum(removed.values()) and row['added_triangles'] == sum(added.values())
    assert row['original_vertices'] == len(old['position']) and row['added_vertices'] == len(extra)
    return dict(style=PROTO, lod=row['lod'], attachment=row['attachment'], target=row['target'], mesh_ref=row['mesh_ref'],
                removed_triangles=sum(removed.values()), added_triangles=sum(added.values()), final_triangles=len(actual),
                original_attribute_prefix_preserved=True, appended_position_uv_normal_tangent_exact=True,
                before_sha256=sha(before), before_blob_sha256=sha(str(before)+'.blob'),
                after_sha256=sha(after), after_blob_sha256=sha(str(after)+'.blob'), zero_area_triangles=0)


def verify_ui(manifest):
    from PIL import Image
    rows = manifest.get('ui_artifacts', [])
    assert isinstance(rows, list)
    if not rows:
        return {}
    stems = {r['stem'] for r in ROSTER} | {group_stem(r) for r in ROSTER} | {PROTO}
    expected = {(MOD_REL/'res/textures/ui'/folder/'vehicle/train'/(stem+suffix+'.tga')).as_posix():
                (size[0]*scale, size[1]*scale)
                for stem in stems for folder, size in (('models_20', (64, 20)), ('models_small', (178, 56)))
                for suffix, scale in (('', 1), ('@2x', 2))}
    assert len(rows) == 52 and {r['file'] for r in rows} == set(expected)
    result = {}
    for row in rows:
        path = checked(ROOT, row['file'])
        with path.open('rb') as stream:
            data = stream.read(18)
        assert data[2] == 2 and data[16] == 32 and data[17] == 8, ('TGA native encoding/origin', row['file'])
        assert struct.unpack('<HH', data[12:16]) == expected[row['file']] == (row['width'], row['height'])
        with Image.open(path) as icon:
            assert icon.size == expected[row['file']] and icon.mode == 'RGBA'
            assert icon.getchannel('A').getbbox(), ('empty icon', row['file'])
        assert sha(path) == row['sha256']
        result[row['file']] = row['sha256']
    return result


def ui_inventory_changes(manifest):
    changes = manifest.get('ui_inventory_changes', {'added': [], 'removed': []})
    if not manifest.get('ui_artifacts'):
        assert changes == {'added': [], 'removed': []}
        return set(), set()
    root = MOD_REL/'res/textures/ui'
    added = {(root/folder/'vehicle/train'/(PROTO+suffix+'.tga')).as_posix()
             for folder in ('models_20', 'models_small') for suffix in ('', '@2x')}
    removed = {(root/folder/'vehicle/train'/(PROTO+'.png')).as_posix()
               for folder in ('models_20', 'models_small')}
    assert set(changes['added']) == added and set(changes['removed']) == removed
    assert len(changes['added']) == 4 and len(changes['removed']) == 2
    return added, removed


def localization():
    old, new = read_lua(BASE_MOD/'strings.lua'), read_lua(MOD/'strings.lua')
    assert set(old) == set(new)
    notes = {}
    for language, prior in old.items():
        current = new[language]
        assert set(prior) == set(current)
        for key, value in prior.items():
            if key == 'MOD_NAME':
                assert current[key] == value.replace('v0.43', 'v0.44')
            elif key == 'MOD_DESC':
                assert current[key].endswith(value) and len(current[key]) > len(value)
                note = current[key][:-len(value)]
                assert note.startswith('v0.44') and note.endswith('\n\n')
                assert '未游戏实测' in note or 'not engine-tested' in note.lower() or 'not game-tested' in note.lower()
                notes[language] = note.rstrip()
            else:
                assert current[key] == value, ('unrelated localization', language, key)
    old_mod = (BASE_MOD/'mod.lua').read_text(encoding='utf8')
    assert old_mod.count('minorVersion = 43') == 1
    assert (MOD/'mod.lua').read_text(encoding='utf8') == old_mod.replace('minorVersion = 43', 'minorVersion = 44')
    return notes


def main():
    manifest_path = ROOT/'manifest_v44.json'
    manifest, baseline = load(manifest_path), load(BASE/'manifest_v43.json')
    assert baseline['status'] == 'NATIVE_STATIC_PASS'
    assert manifest['baseline_version'] == '0.43' and manifest['baseline_manifest_sha256'] == sha(BASE/'manifest_v43.json')
    assert manifest['static_only'] is True and manifest['metadata_change_scope'] == 'none'
    assert all(manifest[k] is False for k in ('game_verified', 'model_editor_verified', 'installed', 'published'))
    assert set(manifest['recipe_sha256']) == RECIPES
    for name, digest in manifest['recipe_sha256'].items():
        assert sha(checked(ROOT, name)) == digest
    sources = source_contract(manifest)
    assert len(manifest['changes']) == 3 and {(r['style'], r['lod']) for r in manifest['changes']} == {(PROTO, i) for i in range(3)}
    assert manifest['shared_patches'] == [] and manifest['assets'] == [] and manifest['material_bindings'] == []
    patches = manifest['patches']
    assert patches and len({row_key(r) for r in patches}) == len(patches)
    assert {(PROTO, i, 'body') for i in range(3)} <= {row_key(r) for r in patches}
    by_ref = {r['mesh_ref']: r for r in patches}
    assert len(by_ref) == len({r['target'] for r in patches}) == len(patches)
    assert len({r[p] for r in patches for p in ('before', 'after')}) == len(patches)*2
    delta_reports = [verify_patch(r) for r in patches]
    names = {r['stem'] for r in ROSTER} | {group_stem(r) for r in ROSTER} | {PROTO}
    paths = sorted((RES/'models/model/vehicle/train').glob('*.mdl'))
    assert len(paths) == 13 and {p.stem for p in paths} == names == set(manifest['models'])
    for path in paths:
        if path.stem != PROTO:
            assert sha(path) == sha(BASE/path.relative_to(ROOT)), ('production MDL changed', path.name)
    ui = verify_ui(manifest)
    ui_added, ui_removed = ui_inventory_changes(manifest)
    changed = {r['target'] for r in patches}
    mutable = changed | {p+'.blob' for p in changed} | set(ui)
    mutable |= {(MOD_REL/p).as_posix() for p in ('mod.lua', 'strings.lua')}
    mutable.add((MOD_REL/'res/models/model/vehicle/train'/(PROTO+'.mdl')).as_posix())
    old_files = {p.relative_to(BASE).as_posix() for p in BASE_MOD.rglob('*') if p.is_file()}
    new_files = {p.relative_to(ROOT).as_posix() for p in MOD.rglob('*') if p.is_file()}
    assert new_files == (old_files-ui_removed)|ui_added, ('unexpected staging inventory change', sorted(new_files^((old_files-ui_removed)|ui_added)))
    preserved = sorted(old_files-mutable-ui_removed)
    for relative in preserved:
        assert sha(checked(ROOT, relative)) == sha(checked(BASE, relative)), ('protected native file changed', relative)
    assert manifest['animated'] == baseline['animated'] and len(manifest['animated']) == 272
    assert manifest['animation_files'] == baseline['animation_files'] and len(manifest['animation_files']) == 26
    assert manifest.get('placeholders', []) == baseline.get('placeholders', [])
    for row in manifest['animated']:
        assert row['target'] not in changed
        assert sha(checked(ROOT, row['target'])) == row['mesh_sha256']
        assert sha(checked(ROOT, row['target']+'.blob')) == row['blob_sha256']
    resources, models, reports, mapping, animations, used = Resources41(), {}, [], [], set(), set()
    max_frame_difference = 0.
    for path in paths:
        model = resources.table(path)
        old = read_lua(BASE/path.relative_to(ROOT))
        expected = deepcopy(old)
        for lod_index, lod in enumerate(expected['lods']):
            nodes, named = flatten(lod['node'])
            frames = snapshot_world_matrices(lod['node'])
            assert nodes[0][1] == IDENTITY and named['body'][0] == 1
            for node, matrix, parent in nodes:
                proof = by_ref.get(node.get('mesh'))
                if not proof:
                    continue
                assert path.stem == PROTO and proof['lod'] == lod_index, 'Patch touches production/shared resources'
                declared = named[proof['attachment']][1][0]
                assert declared['mesh'] == node['mesh']
                assert node['materials'] == proof['baseline_materials']
                assert np.array_equal(np.asarray(proof['native_world_matrix']), frames[node['name']].astype(float)), (
                    'snapshot frame/instance mismatch', lod_index, node['name'])
                max_frame_difference = max(max_frame_difference, float(np.max(np.abs(
                    np.asarray(proof['native_world_matrix'])-np.asarray(matrix).reshape(4,4).T))))
                node['materials'] = proof['materials']
                used.add(proof['mesh_ref'])
                mapping.append(dict(model=PROTO, style=PROTO, lod=lod_index, attachment=node['name'],
                                    source_attachment=proof['attachment'], mesh_ref=node['mesh'], target=proof['target'],
                                    materials=proof['materials'], local_transform=node['transf'], world_transform=matrix,
                                    parent=nodes[parent][0]['name'] if parent is not None else None))
        assert model == expected, ('unapproved metadata/hierarchy/transform/material change', path.name)
        totals = []
        for lod_index, lod in enumerate(model['lods']):
            total = 0
            nodes, named = flatten(lod['node'])
            for node, matrix, _ in nodes:
                ref = node.get('mesh') or node.get('skin')
                if ref:
                    desc = resources.decode_mesh(ref)
                    mats = node.get('materials', node.get('skinMaterials'))
                    assert len(mats) == desc['submeshes']
                    for material in mats:
                        resources.material(material)
                    low, high = resources.bounds(ref, matrix)
                    assert np.all(low >= np.asarray(model['boundingInfo']['bbMin'])-1e-4)
                    assert np.all(high <= np.asarray(model['boundingInfo']['bbMax'])+1e-4)
                    total += desc['triangles']
                    resources.referenced_meshes.add(ref)
                for animation in node.get('animations', {}).values():
                    assert animation['type'] == 'FILE_REF'
                    ref = animation['params']['id']
                    p = checked(RES/'models/animation', ref)
                    assert sha(p) == sha(checked(BASE_MOD/'res/models/animation', ref))
                    resources.table(p); animations.add(ref)
            for location in ('front', 'inner', 'back'):
                for direction in ('Forward', 'Backward'):
                    ids = model['metadata']['railVehicle']['configs'][lod_index][location+direction+'Parts']
                    name = 'light24_'+location+('_fwd' if direction == 'Forward' else '_bwd')
                    assert ids == [named[name][0]] if lod_index < 2 else not ids
            assert total < BUDGETS[lod_index], ('LOD triangle budget', path.stem, lod_index, total)
            totals.append(total)
        assert totals[0] > totals[1] > totals[2]
        reports.append(dict(model=path.stem, instanced_triangles=totals,
                            metadata_transforms_hierarchy_direction_emitters_exact=True,
                            production_file_byte_exact=path.stem != PROTO))
        models[path.stem] = model
        print('VERIFY44_BUDGET', path.stem, totals, flush=True)
    assert used == set(by_ref) and len(animations) == 27
    animation_files = {p.relative_to(RES/'models/animation').as_posix(): sha(p) for p in (RES/'models/animation').rglob('*') if p.is_file()}
    assert animation_files == {p.relative_to(BASE_MOD/'res/models/animation').as_posix(): sha(p)
                               for p in (BASE_MOD/'res/models/animation').rglob('*') if p.is_file()}
    notes = localization()
    for path in (MOD/'mod.lua', MOD/'strings.lua'):
        resources.inputs[path.relative_to(ROOT).as_posix()] = sha(path)
    resources.inputs.update(ui)
    documents = {f'native_scene_{stem}.json': model for stem, model in models.items()}
    documents.update({'native_meshes.json': resources.descriptors, 'native_patch_attachments_v44.json': mapping,
                      'native_scene.json': models['fxn5c'], 'native_scene_jinwen.json': models['fxn5c_jinwen']})
    outputs = {}
    for name, document in documents.items():
        p = ROOT/name; p.write_text(json.dumps(document,sort_keys=True), encoding='utf8'); outputs[name] = sha(p)
    helpers = ('verify_native.py', 'verify_native_v24.py', 'verify_v41.py', 'native_patch_v23.py')
    report = dict(status='PASS', scope='prototype-only native static verification; not engine execution',
                  generated_utc=datetime.now(timezone.utc).isoformat(), models=13, variants=11, source_count=3,
                  patches=len(patches), shared_source_proofs=0, delta_reports=delta_reports, models_report=reports,
                  preserved_files=len(preserved), preserved_paths=preserved, production_models_byte_exact=True,
                  production_resources_byte_exact_except_ui=True, all_272_motion_interface_meshes_unchanged=True,
                  all_animation_files_unchanged=True, metadata_parameters_transforms_hierarchy_lamps_emitters_unchanged=True,
                  source_inputs_sha256=sources, inputs_sha256=resources.inputs, render_inputs_sha256=outputs,
                  snapshot_world_matrices_exact_float32_composition=True,
                  snapshot_world_max_difference_from_float64=max_frame_difference,
                  animation_files_sha256=animation_files, unique_meshes=resources.mesh_decode_count,
                  materials=resources.material_count, localization_notes=notes, ui_artifacts=ui, ui_verified=bool(ui),
                  ui_inventory_changes=dict(added=sorted(ui_added), removed=sorted(ui_removed)),
                  validator_sha256=sha(Path(__file__)), helper_sha256={n:sha(ROOT/n) for n in helpers},
                  independent_source_audit_required=True, game_verified=False, model_editor_verified=False,
                  installed=False, published=False)
    report_path = ROOT/'validation_v44.json'
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    manifest['status'], manifest['validation_sha256'] = 'NATIVE_STATIC_PASS', sha(report_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf8')
    print('VERIFY44_PASS', len(preserved), len(models), resources.mesh_decode_count, flush=True)


if __name__ == '__main__':
    try:
        assert __debug__, 'Assertions must remain enabled'
        main()
    except Exception as error:
        (ROOT/'validation_v44.json').write_text(json.dumps(dict(status='FAIL', error=repr(error),
            scope='native static verification; not engine execution', game_verified=False, model_editor_verified=False), indent=2), encoding='utf8')
        raise

