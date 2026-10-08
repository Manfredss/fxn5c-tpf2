"""Photo-guided static geometry delta on immutable v37 native resources.

Only selected static body objects may change. Existing animation meshes,
curves, hierarchy, wheel transforms and variable signage remain untouched.
"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fxn5c_v37_source'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runtime'))

import generate_fxn5c as gen
import export_tpf2 as exporter
from geometry_v20 import ProductionBuilder15
from photo_revision_v38 import apply, selected_objects
from build_release_v24 import body_items, lua_literal, normalize_empty, walk
from native_patch_v23 import patch, sha
from roof_revision_v24 import sanitize_after_export
from verify_native import read_lua

EXHAUST_EMITTER_Z = 4.4758  # Lowered outlet upper edge 4.4608 m + 15 mm.


def fingerprint(obj):
    mesh = obj.data
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get('co', coords)
    payload = [coords.tobytes()]
    payload.append(repr([(tuple(p.vertices), p.material_index, p.use_smooth)
                         for p in mesh.polygons]).encode())
    payload.append(repr([m.name for m in mesh.materials]).encode())
    for layer in mesh.uv_layers:
        uv = np.empty(len(layer.data) * 2, dtype=np.float32)
        layer.data.foreach_get('uv', uv)
        payload.append(uv.tobytes())
    payload.append(repr([tuple(row) for row in obj.matrix_world]).encode())
    payload.append(repr(obj.parent.name if obj.parent else None).encode())
    return hashlib.sha256(b''.join(payload)).hexdigest()


def selected():
    objects = sorted(selected_objects(), key=lambda o: o.name)
    assert objects and len(objects) == len({o.name for o in objects})
    allowed = {o.name for o, _ in body_items()}
    for obj in objects:
        assert obj.type == 'MESH' and obj.name in allowed, ('not static body', obj.name)
        assert not obj.get('roof26_animation_kind'), ('animated object selected', obj.name)
    return objects


def snapshot(style, lod, phase, objects):
    folder = ROOT / 'runtime/patch38' / style
    folder.mkdir(parents=True, exist_ok=True)
    exporter.MESH_DIR = str(folder)
    name = f'selected_{phase}_lod{lod}'
    materials, _, _ = exporter.export_mesh(
        name, [(obj, obj.matrix_world.copy()) for obj in objects])
    path = folder / (name + '.msh')
    cleanup = sanitize_after_export(path)
    return path, materials, cleanup


def save(path):
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(path), relative_remap=False)


def main():
    old = json.loads((BASE / 'manifest_v37.json').read_text(encoding='utf8'))
    assert old['status'] == 'NATIVE_STATIC_PASS' and len(old['animated']) == 272
    assert (ROOT / 'staging/codex_fxn5c_1/mod.lua').is_file(), 'Copy v37 staging first'
    patches, changes, sources = [], [], []
    for jw in (False, True):
        style = 'fxn5c_jinwen' if jw else 'fxn5c'
        model = read_lua(BASE / f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
        for lod in (0, 1, 2):
            source = BASE / (style + '_source.blend') if lod == 0 else BASE / 'runtime' / f'final37_{style}_lod{lod}.blend'
            bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
            builder = ProductionBuilder15(lod, gen)
            before_objects = selected()
            selected_names = {o.name for o in before_objects}
            untouched = {o.name: fingerprint(o) for o in bpy.context.scene.objects
                         if o.type == 'MESH' and o.name not in selected_names}
            before, before_materials, _ = snapshot(style, lod, 'before', before_objects)
            change = apply(builder, jw)
            bpy.context.view_layer.update()
            after_objects = selected()
            after_names = {o.name for o in after_objects}
            for name, digest in untouched.items():
                obj = bpy.data.objects.get(name)
                assert obj is not None and fingerprint(obj) == digest, ('out-of-scope source change', name)
            new_names = {o.name for o in bpy.context.scene.objects if o.type == 'MESH'} - set(untouched) - selected_names
            assert new_names <= after_names, ('unexported new objects', sorted(new_names - after_names))
            after, after_materials, _ = snapshot(style, lod, 'after', after_objects)
            body = next(n for n in walk(model['lods'][lod]['node']) if n['name'] == 'body')
            rel = 'staging/codex_fxn5c_1/res/models/mesh/' + body['mesh']
            proof = patch(BASE / rel, before, after, ROOT / rel,
                          body['materials'], before_materials, after_materials)
            proof['zero_area_cleanup'] = sanitize_after_export(ROOT / rel)
            proof['mesh_sha256'] = sha(ROOT / rel)
            proof['blob_sha256'] = sha(str(ROOT / rel) + '.blob')
            patches.append(dict(style=style, lod=lod, target=rel, mesh_ref=body['mesh'],
                                before=before.relative_to(ROOT).as_posix(), after=after.relative_to(ROOT).as_posix(),
                                before_materials=before_materials, after_materials=after_materials,
                                baseline_materials=body['materials'], selected_before=sorted(selected_names),
                                selected_after=sorted(after_names), untouched_source_meshes=len(untouched), **proof))
            changes.append(dict(style=style, lod=lod, report=change))
            out = ROOT / (style + '_source.blend') if lod == 0 else ROOT / 'runtime' / f'final38_{style}_lod{lod}.blend'
            save(out)
            sources.append(dict(file=out.relative_to(ROOT).as_posix(), sha256=sha(out),
                                baseline=source.relative_to(BASE).as_posix(), baseline_sha256=sha(source)))
            print('BUILD38_SCENE', style, lod, proof['removed_triangles'], proof['added_triangles'], flush=True)
    by_ref = {p['mesh_ref']: p for p in patches}
    models = []
    for path in sorted((BASE / 'staging/codex_fxn5c_1/res/models/model/vehicle/train').glob('*.mdl')):
        model = read_lua(path)
        for lod in model['lods']:
            for node in walk(lod['node']):
                if node.get('mesh') in by_ref:
                    assert node['name'] == 'body'
                    node['materials'] = by_ref[node['mesh']]['materials']
        emitters = model['metadata']['particleSystem']['emitters']
        assert [e['position'] for e in emitters] == [[-1.7, -.76, 4.675], [-1.7, .76, 4.675]]
        for emitter in emitters:
            emitter['position'][2] = EXHAUST_EMITTER_Z
        text = lua_literal(model)
        for value in model['metadata']['description'].values():
            token = lua_literal(value)
            assert text.count(token) == 1
            text = text.replace(token, '_(' + token + ')', 1)
        target = ROOT / path.relative_to(BASE)
        target.write_text('function data()\nreturn ' + text + '\nend\n', encoding='utf8')
        assert read_lua(target) == normalize_empty(model)
        models.append(path.stem)
    assert len(models) == 12
    mod = ROOT / 'staging/codex_fxn5c_1'
    text = (BASE / 'staging/codex_fxn5c_1/mod.lua').read_text(encoding='utf8')
    assert text.count('minorVersion = 37') == 1
    (mod / 'mod.lua').write_text(text.replace('minorVersion = 37', 'minorVersion = 38'), encoding='utf8')
    lines = (BASE / 'staging/codex_fxn5c_1/strings.lua').read_text(encoding='utf8').splitlines(keepends=True)
    for i, line in enumerate(lines):
        if 'MOD_NAME =' in line:
            lines[i] = line.replace('v0.37', 'v0.38')
        elif 'MOD_DESC = "' in line:
            note = ('v0.38 候选：依据新增实车照片细化静态结构与涂装；保留 v0.37 风扇和百叶配置。未游戏实测。'
                    if '复兴5C' in line else
                    'v0.38 candidate: photo-guided static detail and paint corrections; v0.37 fans and shutters preserved. Not engine-tested.')
            lines[i] = line.replace('MOD_DESC = "', 'MOD_DESC = "' + note + '\\n\\n', 1)
    (mod / 'strings.lua').write_text(''.join(lines), encoding='utf8')
    manifest = dict(status='BUILT_PENDING_AUDIT', baseline_version='0.37',
                    patches=patches, changes=changes, sources=sources, models=models,
                    animated=deepcopy(old['animated']), animation_files=deepcopy(old['animation_files']),
                    placeholders=deepcopy(old.get('placeholders', [])),
                    exhaust_emitter_z=EXHAUST_EMITTER_Z,
                    metadata_change_scope='Only two exhaust emitter position Z values: 4.675 to 4.4758 m',
                    baseline_manifest_sha256=sha(BASE / 'manifest_v37.json'),
                    recipe_sha256={p: sha(ROOT / p) for p in ('build_v38.py', 'photo_revision_v38.py', 'front_photo_v38.py')},
                    static_only=True, game_verified=False, model_editor_verified=False,
                    installed=False, published=False)
    (ROOT / 'manifest_v38.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf8')
    print('BUILD38_PASS', len(models), len(patches), len(manifest['animated']), flush=True)


if __name__ == '__main__':
    main()
