"""Normalize permitted v26 scenes and copied v25 baselines without geometry edits.

Never edits v25 originals. Pack exact existing image payloads and set paths for
their final archive locations. Compare actual geometry/material/UV/transform/tag
signatures before mutation, after mutation, and after reopening the saved file.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import sys

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / 'fxn5c_v25_source'
WORK = ROOT.parent
IMAGE_FILE_HASHES = {}
EXTRACTED_EXISTING_PAYLOADS = []
sys.path.insert(0, str(ROOT))
from audit_sourcekit_v26 import planned_files, sha, label


def plain(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, bpy.types.ID):
        return {'id_type': value.__class__.__name__, 'name': value.name}
    if hasattr(value, 'items'):
        return {str(key): plain(item) for key, item in value.items()}
    if hasattr(value, 'to_list'):
        return plain(value.to_list())
    try:
        return [plain(item) for item in value]
    except TypeError:
        return str(value)


def digest(value):
    return hashlib.sha256(json.dumps(plain(value), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rna_settings(value, excludes=()):
    result = {}
    for prop in value.bl_rna.properties:
        key = prop.identifier
        if key in {'rna_type', 'id_data'} | set(excludes):
            continue
        # ID runtime fields (users, session_uid, preview pointers, evaluation
        # flags) change when opening a file; they are not material settings.
        if prop.is_readonly:
            continue
        if prop.type in {'BOOLEAN', 'INT', 'FLOAT', 'STRING', 'ENUM', 'POINTER'}:
            try:
                result[key] = plain(getattr(value, key))
            except (TypeError, AttributeError, RuntimeError):
                pass
    return result


def array_hash(collection, attribute, count, width, dtype):
    values = np.empty(count * width, dtype=dtype)
    if len(values):
        collection.foreach_get(attribute, values)
    return hashlib.sha256(values.tobytes()).hexdigest()


def mesh_signature(mesh):
    result = {'vertices': array_hash(mesh.vertices, 'co', len(mesh.vertices), 3, np.float32),
              'edges': array_hash(mesh.edges, 'vertices', len(mesh.edges), 2, np.int32),
              'loops': array_hash(mesh.loops, 'vertex_index', len(mesh.loops), 1, np.int32),
              'polygons': {}, 'attributes': {}, 'materials': [m.name if m else None for m in mesh.materials]}
    for key, dtype in (('loop_start', np.int32), ('loop_total', np.int32),
                       ('material_index', np.int32), ('use_smooth', np.bool_)):
        result['polygons'][key] = array_hash(mesh.polygons, key, len(mesh.polygons), 1, dtype)
    types = {'FLOAT': ('value', 1, np.float32), 'INT': ('value', 1, np.int32),
             'INT32_2D': ('value', 2, np.int32), 'INT32_3D': ('value', 3, np.int32),
             'INT16_2D': ('value', 2, np.int16),
             'INT8': ('value', 1, np.int8), 'BOOLEAN': ('value', 1, np.bool_),
             'FLOAT_VECTOR': ('vector', 3, np.float32), 'FLOAT2': ('vector', 2, np.float32),
             'FLOAT_COLOR': ('color', 4, np.float32), 'BYTE_COLOR': ('color', 4, np.float32),
             'QUATERNION': ('value', 4, np.float32)}
    for attr in mesh.attributes:
        if attr.data_type not in types:
            raise RuntimeError(f'Unsupported attribute for preservation proof: {attr.name} {attr.data_type}')
        field, width, dtype = types[attr.data_type]
        result['attributes'][attr.name] = [attr.data_type, attr.domain,
            array_hash(attr.data, field, len(attr.data), width, dtype)]
    result['corner_normals'] = array_hash(mesh.corner_normals, 'vector', len(mesh.corner_normals), 3, np.float32)
    result['uv_layers'] = {layer.name: array_hash(layer.data, 'uv', len(layer.data), 2, np.float32)
                           for layer in mesh.uv_layers}
    result['tags'] = plain(dict(mesh.items()))
    if mesh.shape_keys:
        result['shape_keys'] = {key.name: array_hash(key.data, 'co', len(key.data), 3, np.float32)
                                for key in mesh.shape_keys.key_blocks}
    return digest(result)


def node_tree_signature(tree):
    if tree is None:
        return None
    return {'nodes': {node.name: {'type': node.bl_idname,
                'settings': rna_settings(node, {'rna_type', 'id_data', 'dimensions'}),
                'inputs': {socket.identifier: plain(socket.default_value)
                           for socket in node.inputs if hasattr(socket, 'default_value')}}
            for node in tree.nodes},
            'links': sorted((link.from_node.name, link.from_socket.identifier,
                             link.to_node.name, link.to_socket.identifier) for link in tree.links)}


def image_payload(image):
    if image.packed_file:
        return hashlib.sha256(image.packed_file.data).hexdigest()
    source = Path(bpy.path.abspath(image.filepath)).resolve()
    if not source.is_file():
        raise FileNotFoundError(f'Missing image payload {image.name}')
    return sha(source)


def scene_signature():
    objects = {}
    for obj in bpy.data.objects:
        objects[obj.name] = digest({'type': obj.type,
            'data': obj.data.name if obj.data else None,
            'matrix_world': plain(obj.matrix_world), 'matrix_local': plain(obj.matrix_local),
            'matrix_parent_inverse': plain(obj.matrix_parent_inverse),
            'parent': obj.parent.name if obj.parent else None,
            'tags': plain(dict(obj.items())),
            'materials': [(slot.link, slot.material.name if slot.material else None) for slot in obj.material_slots],
            'modifiers': [rna_settings(modifier) for modifier in obj.modifiers],
            'vertex_groups': [(group.name, group.index) for group in obj.vertex_groups],
            'deform_weights': [[(group.group, group.weight) for group in vertex.groups]
                               for vertex in obj.data.vertices] if obj.type == 'MESH' else None})
    return {'mesh_geometry_uv_normals_material_slots': {mesh.name: mesh_signature(mesh) for mesh in bpy.data.meshes},
            'objects_transform_parent_tags_modifiers': objects,
            'materials': {material.name: digest({'settings': rna_settings(material, {'node_tree', 'use_fake_user'}),
                            'nodes': node_tree_signature(material.node_tree), 'tags': dict(material.items())})
                          for material in bpy.data.materials},
            'images_content': {image.name: image_payload(image) for image in bpy.data.images if image.source == 'FILE'},
            '_orphan_images': {image.name: 0 for image in bpy.data.images if image.users == 0},
            'scene_tags': {scene.name: digest(dict(scene.items())) for scene in bpy.data.scenes},
            'collections': {collection.name: digest({'objects': sorted(obj.name for obj in collection.objects),
                'children': sorted(child.name for child in collection.children)}) for collection in bpy.data.collections}}


def compare(before, after, phase):
    changes = []
    orphan_cleanup = []
    for category in before.keys() | after.keys():
        if category.startswith('_'):
            continue
        old, new = before.get(category, {}), after.get(category, {})
        for key in old.keys() | new.keys():
            if old.get(key) != new.get(key):
                if category == 'images_content' and key not in new and key in before.get('_orphan_images', {}):
                    orphan_cleanup.append(key)
                    continue
                changes.append((category, key))
    if changes:
        raise AssertionError((phase, changes[:20], len(changes)))
    return {'phase': phase, 'status': 'PASS', 'signature_sha256': digest(before),
            'unused_images_discarded_by_blender_save': orphan_cleanup,
            'categories': {key: len(value) for key, value in before.items()}}


def normalize(source, target, archive_path, included):
    old_sha = sha(source)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    assert not bpy.data.libraries, 'Linked libraries require manual handling'
    assert not any(font.filepath and font.filepath != '<builtin>' for font in bpy.data.fonts)
    before = scene_signature()
    protected_orphans = []
    for material in bpy.data.materials:
        if material.users == 0:
            material.use_fake_user = True
            protected_orphans.append(material.name)
    image_rows = []
    owner = BASE if archive_path.parts[0] == BASE.name else ROOT
    logical_scene = WORK / archive_path
    for image in bpy.data.images:
        if image.source != 'FILE':
            continue
        payload = image_payload(image)
        # Blender's //source_textures/file is a relative path, not a Windows
        # UNC server/share path; pathlib.name would misparse shallow // paths.
        filename = image.filepath.replace('\\', '/').rsplit('/', 1)[-1]
        choices = []
        for path in included:
            if not path.is_file() or path.suffix.lower() not in {'.tga', '.png', '.dds', '.jpg', '.jpeg', '.exr', '.hdr', '.webp'}:
                continue
            if path not in IMAGE_FILE_HASHES:
                IMAGE_FILE_HASHES[path] = sha(path)
            if IMAGE_FILE_HASHES[path] == payload:
                choices.append(path)
        if not choices:
            if '--extract-packed' not in sys.argv or not image.packed_file:
                raise RuntimeError(f'No byte-identical packaged target for {image.name}')
            # Optional authorized source-asset copy: preserve the exact encoded
            # packed bytes. No pixel decode, image editing or recompression.
            name = Path(filename)
            destination = ROOT / 'source_textures' / (name.stem + '_packed_' + payload[:12] + name.suffix)
            assert destination.resolve().parent == (ROOT / 'source_textures').resolve()
            if destination.exists():
                assert sha(destination) == payload, 'Packed-payload filename collision'
            else:
                destination.write_bytes(bytes(image.packed_file.data))
            assert sha(destination) == payload
            included.add(destination.resolve())
            IMAGE_FILE_HASHES[destination.resolve()] = payload
            choices = [destination.resolve()]
            EXTRACTED_EXISTING_PAYLOADS.append({'image_name': image.name,
                'source_scene': label(source), 'copied_to': label(destination),
                'sha256': payload, 'bytes': destination.stat().st_size,
                'operation': 'Byte-for-byte copy of pre-existing embedded encoded image, not an image edit'})
        choices.sort(key=lambda path: (not path.is_relative_to(owner), path.name != filename,
            'source_textures' not in path.parts, len(path.parts), str(path)))
        texture = choices[0]
        if not image.packed_file:
            image.pack()
        assert image_payload(image) == payload, image.name
        relative = '//' + os.path.relpath(texture, logical_scene.parent).replace('\\', '/')
        image.filepath = relative
        image_rows.append({'name': image.name, 'payload_sha256': payload,
                           'archive_relative_path': relative,
                           'archive_texture_target': label(texture), 'packed': True})
    proofs = [compare(before, scene_signature(), 'after_image_path_and_pack')]
    target.parent.mkdir(parents=True, exist_ok=True)
    # Keep the path explicitly calculated for the archive, notably for v25
    # copies saved in a different temporary directory before package mapping.
    bpy.ops.wm.save_as_mainfile(filepath=str(target), relative_remap=False)
    new_sha = sha(target)
    bpy.ops.wm.open_mainfile(filepath=str(target), load_ui=False, use_scripts=False)
    proofs.append(compare(before, scene_signature(), 'reopened_saved_scene'))
    for image in bpy.data.images:
        if image.source == 'FILE':
            assert image.packed_file and image.filepath.startswith('//'), image.name
    if source != target:
        assert sha(source) == old_sha, 'Historical source mutated'
    return {'source': label(source), 'saved_copy': label(target), 'archive_mapping': archive_path.as_posix(),
            'source_sha256_before': old_sha, 'saved_sha256_after': new_sha,
            'historical_original_unchanged': source.is_relative_to(BASE),
            'orphan_materials_retained_with_fake_user': protected_orphans,
            'image_references': image_rows, 'proofs': proofs}


def main():
    included = planned_files()
    # Only this Blender process: do not replace verified recovery inputs with
    # automatic .blend1 backups while writing their normalized target paths.
    bpy.context.preferences.filepaths.save_version = 0
    original_manifest = json.loads((ROOT / 'manifest_v26.json').read_text(encoding='utf8'))
    expected_final_hashes = {row['file']: row['sha256'] for row in original_manifest['sources']}
    entries = []
    for style in ('fxn5c', 'fxn5c_jinwen'):
        path = ROOT / (style + '_source.blend')
        input_path = path
        prior = Path(str(path) + '1')
        # A pre-normalization backup can restore an orphan material that Blender
        # dropped during an earlier save. Use it ONLY if it is the exact final
        # build identified by the manifest, never an older geometric version.
        if prior.is_file() and sha(path) != expected_final_hashes[path.name] and sha(prior) == expected_final_hashes[path.name]:
            input_path = prior
        entries.append((input_path, path, Path(ROOT.name) / path.name))
        for lod in (1, 2):
            path = ROOT / 'runtime' / f'baseline26_{style}_lod{lod}.blend'
            entries.append((path, path, Path(ROOT.name) / 'runtime' / path.name))
        old = BASE / (style + '_source.blend')
        copy = ROOT / 'runtime/sourcekit_baseline' / old.name
        entries.append((old, copy, Path(BASE.name) / old.name))
    progress = ROOT / 'runtime/sourcekit_normalization_progress.json'
    rows = json.loads(progress.read_text(encoding='utf8'))['rows'] if '--resume' in sys.argv and progress.is_file() else []
    for source, target, mapping in entries:
        previous_row = next((row for row in rows if row['saved_copy'] == label(target)), None)
        if previous_row:
            assert sha(target) == previous_row['saved_sha256_after'], ('Changed completed output', target)
            continue
        print('NORMALIZE_SOURCEKIT', label(source), flush=True)
        rows.append(normalize(source, target, mapping, included))
        (ROOT / 'runtime/sourcekit_normalization_progress.json').write_text(
            json.dumps({'status': 'IN_PROGRESS', 'rows': rows}, indent=2), encoding='utf8')
    manifest_path = ROOT / 'manifest_v26.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    manifest_before = sha(manifest_path)
    updates = []
    for row in manifest['sources']:
        old = row['sha256']
        new = sha(ROOT / row['file'])
        row['sha256'] = new
        updates.append({'file': row['file'], 'old_sha256': old, 'new_sha256': new})
    assert len(updates) == 2
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf8')
    report = {'status': 'PASS', 'geometry_material_uv_transform_tags_preserved': True,
              'clean_extract_rebuild_tested': False, 'rows': rows,
              'manifest_updates': updates, 'manifest_sha256_before': manifest_before,
              'manifest_sha256_after': sha(manifest_path),
              'copied_preexisting_embedded_assets': EXTRACTED_EXISTING_PAYLOADS,
              'packed_payload_source_files': [{'file': label(path), 'sha256': sha(path), 'bytes': path.stat().st_size}
                   for path in sorted((ROOT / 'source_textures').glob('*_packed_*'))],
              'earlier_save_unused_image_cleanup': [{'file': 'fxn5c_v26_source/runtime/baseline26_fxn5c_jinwen_lod1.blend',
                   'image': 'cast_steel_surface.tga.001', 'original_users': 0,
                   'evidence': 'pre-normalization sourcekit_v26_audit.json; no face/material uses this orphan image'}],
              'scope': 'Only eight listed scenes and two manifest source hashes; v25 originals unchanged',
              'source_audit_must_use_mapped_v25_copies': True}
    (ROOT / 'sourcekit_normalization_v26.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    print('SOURCEKIT_NORMALIZATION_PASS', len(rows), flush=True)


if __name__ == '__main__':
    main()
