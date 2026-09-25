"""Read-only source-package hygiene and dependency audit; never saves scenes.

Run in Blender background with --disable-autoexec. Writes only its JSON report.
It inspects final editable scenes and immutable build caches, not a rebuild.
"""
from pathlib import Path
import ast
import hashlib
import json
import re
import sys

import bpy

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fxn5c_v25_source'
WORK = ROOT.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def label(path):
    try:
        return Path(path).relative_to(WORK).as_posix()
    except ValueError:
        return '<outside-sourcekit>/' + Path(path).name


def absolute_path(value):
    return bool(re.match(r'^[A-Za-z]:[/\\]', value) or value.startswith('\\\\')
                or (value.startswith('/') and not value.startswith('//')))


def script_dependencies():
    queue = ['build_v26', 'metadata_v26', 'verify_v26', 'audit_roof_v26', 'preview_v26']
    seen, rows, external, missing, hardcoded = set(), [], set(), [], []
    while queue:
        module = queue.pop()
        if module in seen:
            continue
        seen.add(module)
        path = ROOT / (module + '.py')
        if not path.is_file():
            missing.append(module)
            continue
        tree = ast.parse(path.read_text(encoding='utf8'))
        local = set()
        for node in ast.walk(tree):
            imports = []
            if isinstance(node, ast.Import):
                imports = [item.name.split('.')[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports = [node.module.split('.')[0]]
            for name in imports:
                if (ROOT / (name + '.py')).is_file():
                    local.add(name)
                    queue.append(name)
                elif name not in sys.stdlib_module_names and name != '__future__':
                    external.add(name)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if re.match(r'^[A-Za-z]:[/\\]', node.value):
                    hardcoded.append({'script': path.name, 'line': node.lineno,
                                      'basename': Path(node.value).name,
                                      'font_candidate': Path(node.value).suffix.lower()
                                          in ('.ttf', '.ttc', '.otf'),
                                      'note': 'Lexical reference; may occur in a legacy path not called by v26.'})
        rows.append({'file': path.name, 'sha256': sha(path), 'imports': sorted(local)})
    return {'entrypoints': ['build_v26.py', 'metadata_v26.py', 'verify_v26.py',
                            'audit_roof_v26.py', 'preview_v26.py'],
            'local_module_count': len(rows), 'modules': sorted(rows, key=lambda row: row['file']),
            'external_modules': sorted(external), 'missing_local_modules': missing,
            'absolute_literal_references': hardcoded,
            'method': 'Conservative AST transitive imports including imports inside legacy functions; no script executed.'}


def planned_files():
    paths = set(ROOT.glob('*.py')) | set(ROOT.glob('*.md')) | set(ROOT.glob('*.lua'))
    paths |= {ROOT / 'requirements.txt'}
    for directory in (ROOT / 'source_textures', ROOT / 'staging',
                      BASE / 'source_textures', BASE / 'staging/codex_fxn5c_1/res'):
        paths |= {path for path in directory.rglob('*') if path.is_file()}
    paths |= {BASE / 'staging/codex_fxn5c_1/mod.lua', BASE / 'staging/codex_fxn5c_1/strings.lua'}
    paths |= set(ROOT.glob('*_source.blend')) | set(BASE.glob('*_source.blend'))
    paths |= set((ROOT / 'runtime').glob('baseline26_*.blend'))
    return {path.resolve() for path in paths}


def audit_blend(path, included, archive_path=None):
    before = sha(path)
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False, use_scripts=False)
    images = []
    for image in bpy.data.images:
        if image.source != 'FILE':
            continue
        filepath = image.filepath
        if filepath.startswith('//') and archive_path:
            target = (archive_path.parent / filepath[2:]).resolve()
        else:
            target = Path(bpy.path.abspath(filepath)).resolve() if filepath else None
        packed = bool(image.packed_file or len(image.packed_files))
        exists = bool(target and target.is_file())
        payload_sha = sha(target) if exists else (
            hashlib.sha256(image.packed_file.data).hexdigest() if image.packed_file else None)
        candidates = sorted(candidate for candidate in included
            if target and candidate.name == target.name and candidate.is_file()
            and payload_sha and sha(candidate) == payload_sha)
        images.append({'name': image.name, 'users': image.users,
                       'filepath_kind': 'absolute' if absolute_path(filepath) else 'relative',
                       'filepath': '<absolute>/' + Path(filepath).name if absolute_path(filepath) else filepath,
                       'packed': packed, 'resolved_exists': exists,
                       'resolved_in_package_plan': bool(target in included),
                       'resolved_target': label(target) if target else '',
                       'resolved_sha256': sha(target) if exists else None,
                       'same_bytes_package_candidates': [label(candidate) for candidate in candidates]})
    fonts = [{'name': font.name, 'users': font.users,
              'filepath': '<absolute>/' + Path(font.filepath).name
                if absolute_path(font.filepath) else font.filepath,
              'packed': bool(font.packed_file),
              'external': bool(font.filepath and font.filepath != '<builtin>')}
             for font in bpy.data.fonts]
    libraries = [{'name': library.name, 'filepath': library.filepath,
                  'packed': bool(library.packed_file)} for library in bpy.data.libraries]
    texts = [{'name': text.name, 'filepath_kind': 'absolute' if absolute_path(text.filepath) else 'relative',
              'filepath': '<absolute>/' + Path(text.filepath).name if absolute_path(text.filepath) else text.filepath,
              'use_module': text.use_module} for text in bpy.data.texts]
    after = sha(path)
    return {'file': label(path), 'archive_file': label(archive_path) if archive_path else label(path),
            'sha256': before, 'unchanged_during_read': before == after,
            'objects': len(bpy.data.objects), 'images': images, 'fonts': fonts,
            'linked_libraries': libraries, 'text_blocks': texts,
            'font_objects': [obj.name for obj in bpy.data.objects if obj.type == 'FONT'],
            'blocking_external_images': [row['name'] for row in images
                if not row['packed'] and not row['resolved_in_package_plan']],
            'absolute_image_paths': [row['name'] for row in images if row['filepath_kind'] == 'absolute'],
            'external_fonts': [row['name'] for row in fonts if row['external']],
            'packed_external_fonts': [row['name'] for row in fonts if row['external'] and row['packed']]}


def main():
    included = planned_files()
    scenes = [ROOT / (style + '_source.blend') for style in ('fxn5c', 'fxn5c_jinwen')]
    scenes += [ROOT / 'runtime' / f'baseline26_{style}_lod{lod}.blend'
               for style in ('fxn5c', 'fxn5c_jinwen') for lod in (1, 2)]
    scenes += [BASE / (style + '_source.blend') for style in ('fxn5c', 'fxn5c_jinwen')]
    mappings = [(path, path) for path in scenes]
    if '--mapped' in sys.argv:
        normalized = json.loads((ROOT / 'sourcekit_normalization_v26.json').read_text(encoding='utf8'))
        assert normalized['status'] == 'PASS'
        mappings = [(WORK / row['saved_copy'], WORK / row['archive_mapping']) for row in normalized['rows']]
    missing = [label(path) for path, _ in mappings if not path.is_file()]
    rows = [audit_blend(path, included, logical) for path, logical in mappings if path.is_file()]
    binaries = [label(path) for path in included if path.suffix.lower() in ('.ttf', '.otf', '.ttc', '.woff', '.woff2')]
    problems = []
    for row in rows:
        for key in ('blocking_external_images', 'absolute_image_paths', 'external_fonts',
                    'packed_external_fonts', 'linked_libraries'):
            if row[key]:
                problems.append({'file': row['file'], 'type': key, 'count': len(row[key])})
        if not row['unchanged_during_read']:
            problems.append({'file': row['file'], 'type': 'concurrent_write_during_audit'})
    recommendations = []
    if any(row['absolute_image_paths'] for row in rows):
        recommendations.append('In package copies only, rebase image paths to packaged relative locations; keep packed payload, compare mesh/material/transform hashes before and after saving. Do not byte-replace .blend data.')
    if any(row['external_fonts'] for row in rows) or binaries:
        recommendations.append('Do not distribute font binaries. In package copies only remove unused external font datablocks after confirming no FONT objects; preserve converted glyph meshes.')
    if any(row['blocking_external_images'] for row in rows):
        recommendations.append('Include every referenced texture at its resolved relative location or pack it in the copied scene; cache paths resolve relative to runtime rather than project root.')
    unresolved_rebase = [{'file': row['file'], 'image': image['name']}
        for row in rows for image in row['images']
        if image['filepath_kind'] == 'absolute' and not image['same_bytes_package_candidates']]
    dependencies = script_dependencies()
    report = {'status': 'NEEDS_PACKAGE_HYGIENE' if (problems or binaries or missing) else 'READ_ONLY_INSPECTION_PASS',
              'scope': 'Planned source kit, eight Blender scenes and conservative script imports; no rebuild and no package rewrite performed',
              'clean_extract_rebuild_tested': False, 'game_tested': False,
              'source_files_modified': False, 'missing_scenes': missing,
              'scenes': rows, 'font_binary_files_in_plan': binaries,
              'images_without_byte_identical_packaged_rebase_target': unresolved_rebase,
              'script_dependencies': dependencies, 'issues': problems,
              'recommendations': recommendations,
              'required_layout': {'v25_sibling': 'fxn5c_v25_source',
                 'v25_inputs': ['two *_source.blend', 'source_textures/', 'staging/codex_fxn5c_1/res/',
                               'staging/codex_fxn5c_1/mod.lua', 'staging/codex_fxn5c_1/strings.lua'],
                 'v26_runtime_caches': [path.name for path in scenes if path.parent.name == 'runtime'],
                 'fallback': 'Missing any v26 cache invokes legacy v24 dependency; ship all four caches and do not claim fallback is self-contained.'}}
    target = ROOT / 'sourcekit_v26_audit.json'
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    print('SOURCEKIT_AUDIT', report['status'], 'issues', len(problems), 'fonts', len(binaries), flush=True)
    for item in problems:
        print(item, flush=True)


if __name__ == '__main__':
    main()
