"""Package verified LOCAL v40 candidates; never install, upload or publish.

Use the actual game-resource closure and AST-discovered local Python imports.
Saved audits are copied byte-for-byte; photographs, fonts and runtimes are not
deliverables. The six v39 scenes remain immutable incremental-build inputs.
"""
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED
import ast
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fxn5c_v39_source'
OUT = ROOT.parents[1] / 'outputs'
MOD = ROOT / 'staging/codex_fxn5c_1'
BASE_MOD = BASE / 'staging/codex_fxn5c_1'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runtime'))
from verify_native import read_lua

AUDITS = {'validation_v40.json': 'PASS',
          'geometry_validation_v40.json': 'PASS',
          'sourcekit_validation_v40.json': 'PASS'}
ENTRIES = ('build_v40.py', 'roof_revision_v40.py', 'lettering_revision_v40.py',
           'verify_v40.py', 'render_v40.py', 'audit_geometry_v40.py',
           'audit_sourcekit_v40.py', 'package_v40.py')
RECIPES = {'build_v40.py', 'roof_revision_v40.py', 'lettering_revision_v40.py'}
OUTPUT_NAMES = ('FXN5C_TPF2_v0.40_candidate.zip',
                'FXN5C_Source_v0.40_candidate.zip', 'FXN5C_v0.40_package_audit.json')
EXTERNAL_MATERIALS = {'vehicle/train/wagon_standard.mtl',
                      'vehicle/train/emissive/train_all_lights.mtl',
                      'vehicle/train/emissive/train_red_lights.mtl'}
FORBIDDEN_SUFFIXES = {'.exe', '.dll', '.pyd', '.so', '.dylib', '.ttf', '.ttc',
                      '.otf', '.blend1', '.blend2', '.pyc', '.log', '.zip'}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


def safe_file(root, relative):
    relative = PurePosixPath(str(relative).replace('\\', '/'))
    assert not relative.is_absolute() and '..' not in relative.parts
    path = (root / relative.as_posix()).resolve()
    assert path.is_relative_to(root.resolve()) and path.is_file(), ('missing/scoped input', str(path))
    return path


def dependencies(entrypoints):
    """Find local imports, including functions and literal dynamic imports.

    Discovery does not execute imported modules. Third-party packages remain
    external requirements; no whole Python/Blender runtime directory is added.
    """
    pending, found, external = list(entrypoints), set(), set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        path = safe_file(ROOT, name)
        found.add(name)
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=name)
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                fn = node.func
                dynamic = ((isinstance(fn, ast.Name) and fn.id == '__import__') or
                           (isinstance(fn, ast.Attribute) and fn.attr == 'import_module'))
                if dynamic and isinstance(node.args[0].value, str):
                    modules.append(node.args[0].value)
        for module in modules:
            top = module.split('.')[0]
            local = top + '.py'
            if (ROOT / local).is_file():
                pending.append(local)
            else:
                external.add(top)
    return found, external


def native_closure():
    res = MOD / 'res'
    files, meshes, materials, animations = set(), set(), set(), set()
    models = sorted((res / 'models/model/vehicle/train').glob('*.mdl'))
    assert len(models) == 12
    for path in models:
        files.add(path)
        for node in walk(read_lua(path)):
            meshes.update(node[key] for key in ('mesh', 'skin') if node.get(key))
            for key in ('materials', 'skinMaterials'):
                materials.update(node.get(key, []))
            for animation in node.get('animations', {}).values():
                assert animation['type'] == 'FILE_REF'
                animations.add(animation['params']['id'])
    for reference in meshes:
        files.update((safe_file(res / 'models/mesh', reference),
                      safe_file(res / 'models/mesh', reference + '.blob')))
    external = set()
    for reference in materials:
        material = res / 'models/material' / reference
        if not material.is_file():
            assert reference in EXTERNAL_MATERIALS, ('missing material', reference)
            external.add(reference)
            continue
        files.add(safe_file(res / 'models/material', reference))
        for row in walk(read_lua(material)):
            if row.get('fileName'):
                files.add(safe_file(res / 'textures', row['fileName']))
    for reference in animations:
        files.add(safe_file(res / 'models/animation', reference))
    assert len(animations) == 27
    for folder in ('res/textures/ui', 'res/scripts', 'LICENSES'):
        files.update(p for p in (MOD / folder).rglob('*') if p.is_file())
    files.update(p for p in MOD.iterdir() if p.is_file())
    return files, len(animations), sorted(external)


def verify_evidence():
    manifest = load(ROOT / 'manifest_v40.json')
    baseline = load(BASE / 'manifest_v39.json')
    assert manifest['status'] == baseline['status'] == 'NATIVE_STATIC_PASS'
    assert manifest['baseline_version'] == '0.39'
    assert manifest['baseline_manifest_sha256'] == sha(BASE / 'manifest_v39.json')
    assert manifest['validation_sha256'] == sha(ROOT / 'validation_v40.json')
    assert manifest['static_only'] is True
    assert all(manifest[key] is False for key in ('game_verified', 'model_editor_verified', 'installed', 'published'))
    assert not manifest.get('pending_materials'), 'New material review is pending'
    assert len(manifest['patches']) == 4
    assert {(r['style'], r['lod'], r['attachment']) for r in manifest['patches']} == {
        (style, lod, 'body') for style in ('fxn5c', 'fxn5c_jinwen') for lod in (0, 1)}
    assert len(manifest['animated']) == 272 and manifest['animated'] == baseline['animated']
    # The incremental manifest lists 26 shutter-row files; the referenced
    # native closure additionally includes the preserved fan rotation file.
    assert len(manifest['animation_files']) == 26
    assert manifest['animation_files'] == baseline['animation_files']
    reports = {name: load(ROOT / name) for name in AUDITS}
    assert all(reports[name]['status'] == status for name, status in AUDITS.items())
    native = reports['validation_v40.json']
    assert native['validator_sha256'] == sha(ROOT / 'verify_v40.py')
    assert native['models'] == 12 and native['variants'] == 10
    assert native['static_body_deltas'] == 4
    assert all(native[key] == 0 for key in ('static_bogie_deltas', 'glazing_deltas',
               'numbered_signage_deltas', 'far_native_deltas'))
    assert all(native[key] is True for key in (
        'all_272_motion_interface_meshes_unchanged', 'all_animation_files_unchanged',
        'all_metadata_and_simulation_parameters_unchanged',
        'hierarchy_transforms_lights_emitters_and_numbered_signage_unchanged'))
    assert native['game_verified'] is False and native['model_editor_verified'] is False
    for relative, digest in native['inputs_sha256'].items():
        assert sha(safe_file(ROOT, relative)) == digest, ('audited input changed', relative)
    assert sha(safe_file(ROOT, native['attachment_map'])) == native['attachment_map_sha256']
    assert set(manifest['recipe_sha256']) == RECIPES
    for recipe, digest in manifest['recipe_sha256'].items():
        assert sha(safe_file(ROOT, recipe)) == digest, ('recipe changed after build', recipe)
    assert len(manifest['sources']) == len(baseline['sources']) == 6
    for row in manifest['sources']:
        assert sha(safe_file(ROOT, row['file'])) == row['sha256']
        assert sha(safe_file(BASE, row['baseline'])) == row['baseline_sha256']
    for row in baseline['sources']:
        assert sha(safe_file(BASE, row['file'])) == row['sha256']
    for row in manifest['patches'] + manifest['animated']:
        assert sha(safe_file(ROOT, row['target'])) == row['mesh_sha256']
        assert sha(safe_file(ROOT, row['target'] + '.blob')) == row['blob_sha256']
    for reference, digest in manifest['animation_files'].items():
        assert sha(safe_file(MOD / 'res/models/animation', reference)) == digest

    # Recheck non-target bytes and inventories now, not only at validation time.
    # In particular, new material files have no implicit approval in v40.
    current_files = {p.relative_to(ROOT).as_posix() for p in MOD.rglob('*') if p.is_file()}
    baseline_files = {p.relative_to(BASE).as_posix() for p in BASE_MOD.rglob('*') if p.is_file()}
    assert current_files == baseline_files, (
        'Native inventory changed; new materials require explicit review',
        sorted(current_files - baseline_files), sorted(baseline_files - current_files))
    mutable = {r['target'] for r in manifest['patches']}
    mutable |= {r['target'] + '.blob' for r in manifest['patches']}
    mutable |= {p.relative_to(ROOT).as_posix() for p in (MOD / 'res/models/model/vehicle/train').glob('*.mdl')}
    mutable |= {(MOD.relative_to(ROOT) / name).as_posix() for name in ('mod.lua', 'strings.lua')}
    assert set(native['preserved_paths']) == baseline_files - mutable
    assert native['preserved_files'] == len(native['preserved_paths'])
    for relative in native['preserved_paths']:
        assert sha(safe_file(ROOT, relative)) == sha(safe_file(BASE, relative)), ('preserved asset changed', relative)

    sources = {r['file']: r['sha256'] for r in manifest['sources']}
    assert native['source_inputs_sha256'] == sources
    geometry = reports['geometry_validation_v40.json']
    assert geometry['verifier_sha256'] == sha(ROOT / 'audit_geometry_v40.py')
    for helper, digest in geometry['helper_sha256'].items():
        assert sha(safe_file(ROOT, helper)) == digest, ('geometry audit helper changed', helper)
    assert geometry['source_count'] == len(geometry['scenes']) == 6
    assert {r['file']: r['sha256'] for r in geometry['scenes']} == sources
    assert {(r['style'], r['lod']) for r in geometry['scenes']} == {
        (style, lod) for style in ('fxn5c', 'fxn5c_jinwen') for lod in range(3)}

    portability = reports['sourcekit_validation_v40.json']
    assert portability['scene_count'] == len(portability['scenes']) == 12
    assert portability['issues'] == [] and portability['source_files_modified'] is False
    expected_scenes = {ROOT.name + '/' + row['file']: row['sha256'] for row in manifest['sources']}
    expected_scenes.update({BASE.name + '/' + row['file']: row['sha256'] for row in baseline['sources']})
    assert {row['file'] for row in portability['scenes']} == set(expected_scenes)
    for row in portability['scenes']:
        assert row['unchanged'] is True and row['issues'] == []
        assert row['sha256_before'] == row['sha256_after'] == row['manifest_sha256_expected'] == expected_scenes[row['file']]
        assert sha(safe_file(ROOT.parent, row['file'])) == expected_scenes[row['file']]
    records = portability['manifest_records']
    assert len(records) == 2 and {r['file'] for r in records} == {
        ROOT.name + '/manifest_v40.json', BASE.name + '/manifest_v39.json'}
    for row in records:
        assert sha(safe_file(ROOT.parent, row['file'])) == row['sha256'], ('sourcekit manifest changed', row['file'])
    parameters = load(ROOT / 'parameter_audit_v40.json')
    assert parameters['status'] == 'READ_ONLY_REVIEW_COMPLETE'
    assert parameters['baseline'] == BASE.name
    assert parameters['baseline_manifest_sha256'] == sha(BASE / 'manifest_v39.json')
    assert parameters['source_evidence']['original_image_included'] is False
    assert parameters['source_evidence']['manufacturer_independently_verified'] is False
    return manifest, baseline, reports


def prepare(entries):
    prepared, names = [], set()
    for path, name in sorted(entries, key=lambda row: row[1]):
        path, name = Path(path), PurePosixPath(name).as_posix()
        assert path.is_file() and not path.is_symlink(), ('missing/symlink input', str(path))
        assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
        assert name.casefold() not in names, ('duplicate archive name', name)
        names.add(name.casefold())
        assert path.suffix.lower() not in FORBIDDEN_SUFFIXES, ('prohibited payload', name)
        assert not any(token in name.lower() for token in ('workshop_fileid', '__pycache__',
                       'codex-clipboard', '/preview', '/reference_assets/', '/photos/')), name
        if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.tga', '.dds'):
            assert '/staging/' in name or '/source_textures/' in name or name.startswith('codex_fxn5c_1/'), name
        prepared.append(dict(path=path, name=name, sha256=sha(path)))
    return prepared


def archive(path, entries):
    assert not path.exists(), ('Refuse to overwrite existing artifact', str(path))
    with ZipFile(path, 'x', ZIP_DEFLATED, compresslevel=6, allowZip64=True) as output:
        for row in entries:
            output.write(row['path'], row['name'])
    members = []
    with ZipFile(path) as check:
        assert check.testzip() is None, ('ZIP CRC failed', path.name)
        assert check.namelist() == [r['name'] for r in entries]
        for row in entries:
            digest = hashlib.sha256()
            with check.open(row['name']) as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(block)
            assert digest.hexdigest() == row['sha256'], ('ZIP member hash mismatch', row['name'])
            info = check.getinfo(row['name'])
            members.append(dict(file=row['name'], bytes=info.file_size,
                                sha256=row['sha256'], crc32=f'{info.CRC:08x}',
                                original_sha256=row['sha256'], normalized_archive_copy=False))
    return dict(file=path.name, bytes=path.stat().st_size, sha256=sha(path),
                entries=len(entries), crc_test='PASS', member_sha256_test='PASS', members=members)


def main():
    OUT.mkdir(exist_ok=True)
    # Preflight the entire pair. Exclusive creation also protects races.
    assert all(not (OUT / name).exists() for name in OUTPUT_NAMES), (
        'Refuse to overwrite existing artifact', [name for name in OUTPUT_NAMES if (OUT / name).exists()])
    manifest, baseline, reports = verify_evidence()
    native, animations, external = native_closure()
    game_entries = [(p, 'codex_fxn5c_1/' + p.relative_to(MOD).as_posix()) for p in native]
    game_entries.append((ROOT / 'README_V40.md', 'codex_fxn5c_1/README_V40.md'))
    scripts, external_modules = dependencies(ENTRIES)
    own = {ROOT / name for name in scripts}
    own.update(ROOT / name for name in ('README_V40.md', 'requirements.txt', 'manifest_v40.json',
               'native_meshes.json', 'native_scene.json', 'native_scene_jinwen.json',
               'native_patch_attachments_v40.json', 'parameter_audit_v40.json', *AUDITS))
    own.update(ROOT / row['file'] for row in manifest['sources'])
    own.update(ROOT / f'native_scene_{stem}.json' for stem in manifest['models'])
    for row in manifest['patches']:
        for key in ('before', 'after'):
            own.update((ROOT / row[key], ROOT / (row[key] + '.blob')))
    # Old audit is historical baseline evidence, never substituted for v40 gates.
    old = {BASE / name for name in ('manifest_v39.json', 'README_V39.md', 'validation_v39.json')}
    old.update(BASE / row['file'] for row in baseline['sources'])
    for folder in ('staging', 'source_textures'):
        for root, files in ((ROOT, own), (BASE, old)):
            assert (root / folder).is_dir(), ('missing source folder', str(root / folder))
            files.update(p for p in (root / folder).rglob('*') if p.is_file())
    source_entries = [(p, p.relative_to(ROOT.parent).as_posix()) for p in own | old]
    source_map = {name: path for path, name in source_entries}
    for scene in reports['sourcekit_validation_v40.json']['scenes']:
        for image in scene['images']:
            if image['resolved_exists']:
                target = image['resolved_target']
                assert target in source_map, ('scene texture absent from package', scene['file'], target)
                assert sha(source_map[target]) == image['resolved_sha256'], ('scene texture changed', target)
    game_rows, source_rows = prepare(game_entries), prepare(source_entries)
    # Both scopes are complete and hashed before the first ZIP is opened.
    game = archive(OUT / OUTPUT_NAMES[0], game_rows)
    source = archive(OUT / OUTPUT_NAMES[1], source_rows)
    report = dict(status='PASS', version='0.40', game=game, source=source,
                  models=12, variants=10, static_body_deltas=4, animation_files=animations,
                  source_scenes=6, baseline_scenes=6, baseline='0.39',
                  ast_dependency_closure=sorted(scripts), external_python_modules=sorted(external_modules),
                  external_game_materials=external, new_native_materials='none; unreviewed additions block packaging',
                  source_portability_audit='PASS', clean_extracted_rebuild_verified=False,
                  source_archive_scope='v39 immutable inputs plus v40 final scenes, native assets, AST scripts, snapshots and audits',
                  source_report_path_normalization='none; all files archived byte-for-byte',
                  reports_sha256={name: sha(ROOT / name) for name in AUDITS},
                  parameter_audit_sha256=sha(ROOT / 'parameter_audit_v40.json'),
                  parameter_evidence='user-supplied reference; no independent manufacturer confirmation; no simulation change',
                  package_script_sha256=sha(Path(__file__)),
                  game_verified=False, model_editor_verified=False, installed=False, published=False)
    with (OUT / OUTPUT_NAMES[2]).open('x', encoding='utf8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
    print(json.dumps(dict(status='PASS', game={k: v for k, v in game.items() if k != 'members'},
                          source={k: v for k, v in source.items() if k != 'members'},
                          audit=OUTPUT_NAMES[2], installed=False, published=False), indent=2))


if __name__ == '__main__':
    assert __debug__, 'Run without -O: packaging safety checks must remain enabled'
    main()
