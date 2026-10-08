"""Read-only v44 prototype sources, exact v43 baselines, and native snapshots.

No apply() or scene save is called. Geometry snapshots and reports go to
scratch; engine/Model Editor testing is intentionally not claimed.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import struct
import sys
import bpy
import numpy as np
from mathutils import Matrix

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'runtime'))
import export_tpf2 as exporter
import prototype_geometry_v44 as profile
from audit_geometry_v44 import check_saved_scene as check_profile
from audit_sourcekit_v40 import inspect_scene
from snapshot_v42 import clean_snapshot
from native_patch_v23 import decode, sha
from verify_native import read_lua
from verify_native_v24 import flatten
from verify_v44 import BASE, MOD_REL, PROTO, checked, source_contract, row_key, snapshot_world_matrices


def owner(obj):
    if obj.name.startswith('glazing_'):
        return obj.name
    if obj.get('light24_emitter'):
        direction = obj.get('light24_direction')
        assert direction in ('fwd', 'bwd'), ('unknown emitter direction', obj.name)
        return 'light24_front_'+direction
    if obj.get('livery21_variable'):
        return 'vehicle_markings'
    if obj.name == 'cab_interior':
        return 'cab_interior'
    parent = obj
    while parent:
        assert parent.name not in ('b1_grp', 'b2_grp'), ('prototype cab revision selected bogie geometry', obj.name)
        parent = parent.parent
    assert not obj.get('connection_role'), ('cab revision selected connection', obj.name)
    return 'body'


def selected(nodes):
    pool = {obj.name: obj for module in (profile,) for obj in module.selected_objects(PROTO)}
    groups = {}
    for name, obj in sorted(pool.items()):
        assert obj.type == 'MESH' and not obj.get('roof26_animation_kind'), ('invalid static selection', name)
        role = owner(obj)
        assert role in nodes
        native = nodes[role][1][0]
        assert native.get('mesh', '').startswith('vehicle/train/'+PROTO+'/'), ('shared/native owner', name, role)
        groups.setdefault(role, []).append(obj)
    return groups


def mesh_geometry(obj):
    h = hashlib.sha256()
    h.update(obj.name.encode()+b'\0'+(obj.parent.name if obj.parent else '').encode())
    h.update(struct.pack('<16d', *(x for row in obj.matrix_world for x in row)))
    for vertex in obj.data.vertices:
        h.update(struct.pack('<3f', *vertex.co))
    for face in obj.data.polygons:
        h.update(struct.pack('<II?', len(face.vertices), face.material_index, face.use_smooth))
        h.update(struct.pack('<'+'I'*len(face.vertices), *face.vertices))
    for layer in obj.data.uv_layers:
        h.update(layer.name.encode()+b'\0')
        for uv in layer.data:
            h.update(struct.pack('<2f', *uv.uv))
    for normal in obj.data.corner_normals:
        h.update(struct.pack('<3f', *normal.vector))
    h.update(json.dumps([m.name if m else None for m in obj.data.materials]).encode())
    return h.hexdigest()


def nonmesh_state():
    return {o.name: dict(type=o.type, parent=o.parent.name if o.parent else None,
                         world=[list(row) for row in o.matrix_world])
            for o in bpy.context.scene.objects if o.type != 'MESH'}


def material_state():
    """Record actual shader values and image bytes, not just slot labels."""
    result = {}
    used = {mat for o in bpy.context.scene.objects if o.type == 'MESH' for mat in o.data.materials if mat}
    for material in used:
        nodes = []
        if material.use_nodes:
            for node in material.node_tree.nodes:
                values = {}
                for socket in node.inputs:
                    if not hasattr(socket, 'default_value'):
                        continue
                    value = socket.default_value
                    if isinstance(value, (int, float, bool, str)):
                        values[socket.identifier] = value
                    elif hasattr(value, '__iter__'):
                        try:
                            values[socket.identifier] = [float(v) for v in value]
                        except (TypeError, ValueError):
                            pass
                row = dict(name=node.name, type=node.bl_idname, inputs=values)
                image = getattr(node, 'image', None)
                if image:
                    pixels = np.asarray(image.pixels[:], dtype='<f4')
                    row['image'] = dict(name=image.name, size=list(image.size),
                                        pixels_sha256=hashlib.sha256(pixels.tobytes()).hexdigest(),
                                        colorspace=image.colorspace_settings.name)
                nodes.append(row)
            links = sorted((link.from_node.name, link.from_socket.identifier,
                            link.to_node.name, link.to_socket.identifier) for link in material.node_tree.links)
        else:
            links = []
        result[material.name] = dict(diffuse=list(material.diffuse_color), metallic=material.metallic,
                                    roughness=material.roughness, use_nodes=material.use_nodes,
                                    nodes=sorted(nodes, key=lambda r:r['name']), links=links)
    return result


def resnapshot(row, objects, phase, world):
    assert [o.name for o in objects] == row['selected_'+phase], ('selector differs', row_key(row), phase)
    expected_world = np.asarray(world, dtype=float)
    assert np.array_equal(np.asarray(row['native_world_matrix']), expected_world)
    inverse = Matrix(expected_world.tolist()).inverted()
    folder = ROOT/'runtime/audit44'/f'lod{row["lod"]}'
    folder.mkdir(parents=True, exist_ok=True)
    exporter.MESH_DIR = str(folder)
    name = row['attachment']+'_'+phase
    mats, _, _ = exporter.export_mesh(name, [(o, inverse@o.matrix_world) for o in objects])
    actual_path = folder/(name+'.msh')
    exported_materials = list(mats)
    mats = clean_snapshot(actual_path, mats)
    assert not row.get('before_normalization'), 'No v44 retessellation waiver authorized'
    reference = checked(ROOT, row[phase])
    assert mats == row[phase+'_materials'], ('snapshot material order', row_key(row), phase)
    _, actual, _, actual_rows = decode(actual_path, mats)
    _, expected, _, expected_rows = decode(reference, mats)
    assert Counter(r[0] for r in actual_rows) == Counter(r[0] for r in expected_rows), ('saved source triangles differ', row_key(row), phase)
    assert set(actual) == set(expected)
    errors = {}
    for key in expected:
        assert actual[key].shape == expected[key].shape
        assert np.isfinite(actual[key]).all()
        error = float(np.max(np.abs(actual[key].astype(float)-expected[key].astype(float))))
        assert error < 2e-5, ('saved source attributes differ', row_key(row), phase, key, error)
        errors[key] = error
    return dict(attachment=row['attachment'], phase=phase, objects=[o.name for o in objects],
                snapshot=row[phase], snapshot_sha256=sha(reference), snapshot_blob_sha256=sha(str(reference)+'.blob'),
                scratch=actual_path.relative_to(ROOT).as_posix(), triangles=len(actual_rows),
                maximum_attribute_errors=errors, native_local_frame_exact_float32=True,
                exact_zero_slot_cleanup=dict(exported_materials=exported_materials, retained_materials=mats))


def main():
    manifest_path = ROOT/'manifest_v44.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf8'))
    manifest_hash = sha(manifest_path)
    source_contract(manifest)
    assert manifest['shared_patches'] == [] and manifest['material_bindings'] == [] and manifest['assets'] == []
    patches = manifest['patches']
    assert len({row_key(r) for r in patches}) == len(patches)
    native = read_lua(BASE/MOD_REL/'res/models/model/vehicle/train'/(PROTO+'.mdl'))
    scenes, portability_records = [], []
    for entry in sorted(manifest['sources'], key=lambda r:r['lod']):
        lod = entry['lod']
        before_path, after_path = checked(BASE, entry['baseline']), checked(ROOT, entry['file'])
        _, nodes = flatten(native['lods'][lod]['node'])
        frames = snapshot_world_matrices(native['lods'][lod]['node'])
        rows = {r['attachment']:r for r in patches if r['lod'] == lod}
        prior_portability = inspect_scene(before_path, BASE, entry['baseline_sha256'])
        assert not prior_portability['issues'], ('baseline source portability', lod, prior_portability['issues'])
        groups = selected(nodes)
        assert set(groups) == set(rows), ('baseline attachment inventory', lod, sorted(groups), sorted(rows))
        snapshots = [resnapshot(rows[role], objects, 'before', frames[role]) for role, objects in groups.items()]
        names = {o.name for group in groups.values() for o in group}
        before_all = {o.name for o in bpy.context.scene.objects if o.type == 'MESH'}
        untouched = {o.name:mesh_geometry(o) for o in bpy.context.scene.objects if o.type == 'MESH' and o.name not in names}
        motions = {o.name:mesh_geometry(o) for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('roof26_animation_kind')}
        old_nonmesh, old_materials = nonmesh_state(), material_state()
        current_portability = inspect_scene(after_path, ROOT, entry['sha256'])
        assert not current_portability['issues'], ('final source portability', lod, current_portability['issues'])
        groups = selected(nodes)
        assert set(groups) == set(rows), ('final attachment inventory', lod, sorted(groups), sorted(rows))
        selected_after = {o.name for group in groups.values() for o in group}
        actual_all = {o.name for o in bpy.context.scene.objects if o.type == 'MESH'}
        assert actual_all-selected_after == before_all-names, ('undeclared source object addition/removal', lod)
        for name, digest in untouched.items():
            assert name in bpy.data.objects and mesh_geometry(bpy.data.objects[name]) == digest, ('out-of-scope source edit', lod, name)
        current_motions = {o.name:mesh_geometry(o) for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('roof26_animation_kind')}
        assert current_motions == motions, ('source motion/paint changed', lod)
        assert nonmesh_state() == old_nonmesh, ('nonmesh transform/hierarchy changed', lod)
        assert material_state() == old_materials, ('source shader changed without native asset declaration', lod)
        snapshots += [resnapshot(rows[role], objects, 'after', frames[role]) for role, objects in groups.items()]
        components = dict(geometry=check_profile(lod, PROTO))
        assert all(r['status'] in ('PASS', 'NO_OP', 'NO_OP_FAR', 'SKIPPED_FAR') for r in components.values())
        assert not bpy.data.libraries and not any(o.type == 'FONT' for o in bpy.context.scene.objects)
        assert sha(before_path) == entry['baseline_sha256'] and sha(after_path) == entry['sha256']
        portability_records.extend([prior_portability, current_portability])
        scenes.append(dict(file=entry['file'], sha256=entry['sha256'], style=PROTO, lod=lod,
                           baseline=entry['baseline'], baseline_version='0.43', baseline_sha256=entry['baseline_sha256'],
                           snapshot_reexports=snapshots, untouched_source_meshes=len(untouched),
                           motion_objects=len(motions), motion_geometry_material_hashes=motions,
                           source_shaders_unchanged=True, source_nonmesh_transforms_unchanged=True,
                           component_checks=components, portability=current_portability, baseline_portability=prior_portability))
        print('SOURCE44_LOD_PASS', lod, len(rows), flush=True)
    assert sha(manifest_path) == manifest_hash
    helpers = ('audit_geometry_v44.py', 'audit_sourcekit_v40.py', 'verify_v44.py',
               'native_patch_v23.py', 'export_tpf2.py', 'snapshot_v42.py', 'roof_revision_v24.py')
    report = dict(status='PASS', scope='independent saved-source/baseline/snapshot audit; not engine execution',
                  generated_utc=datetime.now(timezone.utc).isoformat(), source_count=3, baseline_count=3,
                  source_snapshot_rows=len(patches), snapshot_reexports=sum(len(r['snapshot_reexports']) for r in scenes),
                  scenes=scenes, source_files_modified=False, manifest_sha256=manifest_hash,
                  verifier_sha256=sha(Path(__file__)), helper_sha256={n:sha(ROOT/n) for n in helpers},
                  recipe_sha256=manifest['recipe_sha256'], game_verified=False, model_editor_verified=False,
                  installed=False, published=False)
    (ROOT/'source_validation_v44.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf8')
    portability = dict(status='PASS', scope='three v43 prototype baselines and three v44 final sources', scene_count=6,
                       scenes=portability_records, issues=[], source_files_modified=False, clean_extract_rebuild_tested=False,
                       warnings=[dict(file=r['file'], **w) for r in portability_records for w in r['warnings']],
                       manifest_records=[dict(file='../fxn5c_v43_source/manifest_v43.json', sha256=sha(BASE/'manifest_v43.json')),
                                         dict(file='manifest_v44.json', sha256=manifest_hash)],
                       required_sibling_layout=['fxn5c_v43_source', 'fxn5c_v44_source'])
    (ROOT/'sourcekit_validation_v44.json').write_text(json.dumps(portability, indent=2, ensure_ascii=False), encoding='utf8')
    print('SOURCE44_PASS', len(scenes), len(patches), flush=True)


if __name__ == '__main__':
    try:
        assert __debug__, 'Assertions must remain enabled'
        main()
    except Exception as error:
        (ROOT/'source_validation_v44.json').write_text(json.dumps(dict(status='FAIL', error=repr(error),
            scope='saved-source audit; not engine execution', source_files_modified=False,
            game_verified=False, model_editor_verified=False), indent=2), encoding='utf8')
        raise

