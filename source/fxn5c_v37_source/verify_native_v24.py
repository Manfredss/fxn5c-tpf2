"""Decode shared native resources once and validate the ten v24 fleet models.

This verifier checks bytes, references, transforms, actual marking regions and
runtime node ownership. It does not substitute feature-counter metadata for
geometry. Detailed shape/cutout/roof/cab/livery tests remain independent audits;
their explicit replacement map is recorded below. This is not an in-game test.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from verify_native import read_lua, matrix_mul
from roster_v21 import ROSTER, description_key, group_stem

RES = ROOT/'staging/codex_fxn5c_1/res'
MOD = RES.parent
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
BASE_GAME_MATERIALS = {'vehicle/train/emissive/train_all_lights.mtl',
                       'vehicle/train/emissive/train_red_lights.mtl'}
ACTUAL_GEOMETRY_AUDIT_REPLACEMENTS = {
    'roof/front shape and upper glaze':
        'audit_roof_v24.py and audit_front_v24.py: actual fitted roof envelope, front mark placement and split blue/continuous red bands',
    'directional light nodes/colors':
        'audit_lights_v24.py: actual native six standard case lists, ten stable vehicle assignments and emitted optics positions/material colors',
    'running gear and unaffected equipment':
        'audit_native_patch_v24.py: preserved v23 wheel/bogie/rod bytes and unchanged local skin hierarchy; rod remains an LBS approximation',
    'source to native correspondence':
        'audit_native_patch_v24.py: independently checked targeted source triangle delta and unchanged original attribute prefixes',
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_transform(values, label):
    require(len(values) == 16 and all(math.isfinite(v) for v in values), ('invalid transform', label))
    require(max(abs(values[i]-v) for i, v in ((3, 0), (7, 0), (11, 0), (15, 1))) < 1e-7,
            ('non-affine transform', label))
    require(abs(float(np.linalg.det(np.asarray(values).reshape(4, 4).T[:3, :3]))) > 1e-8,
            ('singular transform', label))


def flatten(root):
    nodes = []
    def walk(node, parent_tf, parent_index=None):
        valid_transform(node['transf'], node['name'])
        index = len(nodes)
        world = matrix_mul(parent_tf, node['transf'])
        nodes.append((node, world, parent_index))
        for child in node.get('children', []):
            walk(child, world, index)
    walk(root, IDENTITY)
    by_name = {n[0]['name']: (i, n) for i, n in enumerate(nodes)}
    require(len(by_name) == len(nodes), 'duplicate native node names')
    return nodes, by_name


class SharedResources:
    def __init__(self):
        self.lua = {}
        self.meshes = {}
        self.descriptors = {}
        self.bounds_cache = {}
        self.external_materials = set()
        self.inputs = {}
        self.mesh_decode_count = 0
        self.material_count = 0
        self.referenced_meshes = set()

    def table(self, path):
        path = Path(path)
        if path not in self.lua:
            table = read_lua(path)
            require(isinstance(table, dict), ('Lua data() did not return a table', str(path)))
            self.lua[path] = table
            self.inputs[path.relative_to(ROOT).as_posix()] = sha(path)
        return self.lua[path]

    def decode_mesh(self, ref):
        if ref in self.meshes:
            return self.meshes[ref]
        path = RES/'models/mesh'/ref
        desc = self.table(path)
        blob_path = Path(str(path)+'.blob')
        blob = blob_path.read_bytes()
        self.inputs[blob_path.relative_to(ROOT).as_posix()] = hashlib.sha256(blob).hexdigest()
        attrs = {}
        for name, attr in desc['vertexAttr'].items():
            size, components, offset = attr['count'], attr['numComp'], attr['offset']
            require(isinstance(size, int) and isinstance(offset, int) and components > 0 and size > 0,
                    ('invalid attribute layout', ref, name))
            require(size % (4*components) == 0 and offset % 4 == 0 and 0 <= offset <= len(blob)-size,
                    ('attribute outside blob or unaligned', ref, name))
            values = np.frombuffer(blob, dtype='<f4', count=size//4, offset=offset).reshape(-1, components)
            require(bool(np.isfinite(values).all()), ('nonfinite vertex attribute', ref, name))
            attrs[name] = values
        require(set(attrs) in ({'position', 'normal', 'tangent', 'uv0'},
                              {'position', 'normal', 'tangent', 'uv0', 'jointWeights'}), ('unexpected attributes', ref))
        require(attrs['position'].shape[1] == 3 and attrs['normal'].shape[1] == 3
                and attrs['tangent'].shape[1] == 4 and attrs['uv0'].shape[1] == 2, ('attribute arity', ref))
        count = len(attrs['position'])
        require(all(len(a) == count for a in attrs.values()), ('attribute count mismatch', ref))
        normal = attrs['normal'].astype(np.float64)
        tangent = attrs['tangent'].astype(np.float64)
        require(bool((np.abs(np.einsum('ij,ij->i', normal, normal)-1) < 1e-4).all()), ('normal length', ref))
        require(bool((np.abs(np.einsum('ij,ij->i', tangent[:, :3], tangent[:, :3])-1) < 1e-4).all()), ('tangent length', ref))
        require(bool((np.abs(np.einsum('ij,ij->i', normal, tangent[:, :3])) < 1e-4).all()), ('tangent normal orthogonality', ref))
        require(bool((np.abs(np.abs(tangent[:, 3])-1) < 1e-4).all()), ('tangent handedness', ref))
        triangles = 0
        for sub in desc['subMeshes']:
            indices = sub['indices']
            require(set(indices) == set(attrs), ('missing attribute index stream', ref))
            streams = {}
            for name, index in indices.items():
                size, offset = index['count'], index['offset']
                require(size > 0 and size % 12 == 0 and offset % 4 == 0 and 0 <= offset <= len(blob)-size,
                        ('index block outside blob or non-triangles', ref, name))
                stream = np.frombuffer(blob, dtype='<u4', count=size//4, offset=offset)
                require(int(stream.max()) < len(attrs[name]), ('out-of-range vertex index', ref, name))
                streams[name] = stream
            require(all(np.array_equal(stream, streams['position']) for stream in streams.values()),
                    ('exported corner streams disagree', ref))
            triangles += len(streams['position'])//3
        require(triangles > 0, ('empty mesh', ref))
        self.descriptors[ref] = desc
        self.meshes[ref] = {'triangles': triangles, 'attributes': attrs, 'submeshes': len(desc['subMeshes']),
                            'blob_sha256': hashlib.sha256(blob).hexdigest()}
        self.mesh_decode_count += 1
        return self.meshes[ref]

    def material(self, ref):
        path = RES/'models/material'/ref
        if not path.is_file():
            require(ref in BASE_GAME_MATERIALS, ('missing material', ref))
            self.external_materials.add(ref)
            return None
        return self.table(path)

    def load(self):
        # Only the actual current MDL closure is distributable. Historical
        # unreferenced emitters in the working directory are not v24 evidence.
        from package_release_v21 import native_closure
        closure, _, _ = native_closure()
        for path in sorted(closure | {MOD/'mod.lua', MOD/'strings.lua'}):
            if path.suffix in {'.lua', '.mdl', '.msh', '.mtl'}:
                self.table(path)
        for path in sorted(p for p in closure if p.suffix == '.msh'):
            self.decode_mesh(path.relative_to(RES/'models/mesh').as_posix())
        for path in sorted(p for p in closure if p.suffix == '.mtl'):
            material = self.table(path)
            require(material['type'] in {'PHYSICAL_NRML_MAP', 'PHYS_TRANSPARENT', 'EMISSIVE', 'SKINNING_PHYS_NRML_MAP'},
                    ('unsupported material type', str(path)))
            for key, value in material['params'].items():
                if key.startswith('map_'):
                    texture = RES/'textures'/value['fileName']
                    require(texture.is_file(), ('missing material texture', str(texture)))
                    relative = texture.relative_to(ROOT).as_posix()
                    if relative not in self.inputs:
                        self.inputs[relative] = sha(texture)
            self.material_count += 1

    def bounds(self, ref, transform):
        key = ref, tuple(transform)
        if key not in self.bounds_cache:
            points = self.meshes[ref]['attributes']['position'].astype(np.float64)
            matrix = np.asarray(transform).reshape(4, 4).T
            points = points @ matrix[:3, :3].T + matrix[:3, 3]
            self.bounds_cache[key] = points.min(axis=0), points.max(axis=0)
        return self.bounds_cache[key]


def check_signage(mesh, row, lod):
    """Check actual exported regions, visible dimensions and end-letter bars."""
    points = mesh['attributes']['position'].astype(np.float64)
    covered = np.zeros(len(points), dtype=bool)
    regions = []
    def zone(name, low, high, expected_low=None, expected_high=None):
        mask = ((points >= np.asarray(low)-3e-5) & (points <= np.asarray(high)+3e-5)).all(axis=1)
        require(bool(mask.any()), ('missing native marking region', row['stem'], lod, name))
        covered[:] |= mask
        actual_low, actual_high = points[mask].min(axis=0), points[mask].max(axis=0)
        if expected_low is not None:
            require(bool((np.abs(actual_low[[0, 2]]-np.asarray(expected_low)[[0, 2]]) < 4e-5).all()),
                    ('native marking minimum', row['stem'], lod, name, actual_low.tolist(), expected_low))
            require(bool((np.abs(actual_high[[0, 2]]-np.asarray(expected_high)[[0, 2]]) < 4e-5).all()),
                    ('native marking maximum', row['stem'], lod, name, actual_high.tolist(), expected_high))
        regions.append({'region': name, 'vertices': int(mask.sum()),
                        'bounds_min': actual_low.tolist(), 'bounds_max': actual_high.tolist()})
    jw = row['jinwen']
    for side in (-1, 1):
        ymin, ymax = sorted((side*1.59, side*1.70))
        cx = -side*1.24
        low, high = [cx-1.38, ymin, 2.425], [cx+1.38, ymax, 2.855]
        zone(f'side_number_{side}', low, high, low, high)
        for end in (-1, 1):
            x, width, height, z = (end*10.00, .96, .155, 2.515) if jw else (end*9.84, 1.00, .148, 2.355)
            low, high = [x-width/2, ymin, z-height/2], [x+width/2, ymax, z+height/2]
            zone(f'cab_number_{end}_{side}', low, high, low, high)
            ew = .020 if end > 0 else .045
            ex = x-side*(width/2+.044+ew/2)
            ez = z-height/2+.043
            low, high = [ex-ew/2, ymin, ez-.033], [ex+ew/2, ymax, ez+.033]
            zone(f'cab_end_{end}_{side}', low, high, low, high)
            if not jw:
                dw = .165*len(row['depot'].replace(' ', '').replace('·', ''))
                low, high = [x-dw/2, ymin, 2.064], [x+dw/2, ymax, 2.196]
                zone(f'cab_depot_{end}_{side}', low, high, low, high)
    for end in (-1, 1):
        xmin, xmax = sorted((end*10.78, end*11.30))
        zone(f'nose_number_{end}', [xmin, -1.10, 1.890], [xmax, 1.10, 2.010])
    require(bool(covered.all()), ('native signage has stray/misplaced vertices', row['stem'], lod, int((~covered).sum())))
    return {'filename_number': row['number'], 'regions': regions,
            'all_vertices_in_expected_marking_regions': True,
            'scope': 'outline bounds/end locations and numbered resource ownership; glyph semantics additionally checked in source livery audit'}


def check_model(row, shared):
    stem = row['stem']
    style = 'fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
    model = shared.table(RES/f'models/model/vehicle/train/{stem}.mdl')
    require(len(model['lods']) == 3, (stem, 'expected three LODs'))
    require(len(model['metadata']['railVehicle']['configs']) == 3, (stem, 'expected three rail configs'))
    require(model['metadata']['description'] == {'name': description_key(row)+'_NAME', 'description': description_key(row)+'_DESC'},
            (stem, 'description/number lookup mismatch'))
    expected_group = 'vehicle/train/'+group_stem(row)+'.mdl'
    require(model['metadata']['transportVehicle']['groupFileName'] == expected_group, (stem, 'wrong purchase-menu group'))
    require((RES/'models/model'/expected_group).is_file(), (stem, 'missing purchase-menu group model'))
    require(model['metadata']['availability'] == {'yearFrom': 2025 if row['jinwen'] else 2024, 'yearTo': 0},
            (stem, 'availability does not match configured livery release'))
    reports = []
    for lod_index, lod in enumerate(model['lods']):
        require((lod['visibleFrom'], lod['visibleTo']) == ((0, 120), (120, 420), (420, 3000))[lod_index], (stem, 'LOD ranges'))
        nodes, by_name = flatten(lod['node'])
        require(nodes[0][0]['name'] == 'RootNode' and nodes[0][1] == IDENTITY, (stem, 'root transform/name'))
        require(by_name['body'][0] == 1, (stem, 'body DFS index changed'))
        require(by_name['body'][1][0]['mesh'] == f'vehicle/train/{style}/body_lod{lod_index}.msh', (stem, 'body not shared by livery'))
        expected_connections = {f'conn17_{part}_b{b}_s{s}' for part in ('body_A', 'arm_B') for b in (1, 2) for s in ('p', 'm')} if lod_index < 2 else set()
        require({name for name in by_name if name.startswith('conn17_')} == expected_connections, (stem, 'unexpected connection nodes'))
        require({name for name in by_name if re.fullmatch(r'w\d+', name)} == {f'w{i}' for i in range(1, 7)}, (stem, 'six actual axle nodes'))
        require({name for name in by_name if re.fullmatch(r'b\d+_grp', name)} == {'b1_grp', 'b2_grp'}, (stem, 'two actual bogie groups'))
        for bogie in (1, 2):
            _, (group, transform, parent) = by_name[f'b{bogie}_grp']
            required_children = [f'b{bogie}']+[f'w{i}' for i in range((bogie-1)*3+1, bogie*3+1)]
            if lod_index < 2:
                required_children += [f'conn17_arm_B_b{bogie}_s{s}' for s in ('m', 'p')]
            require([n['name'] for n in group['children']] == required_children, (stem, lod_index, 'bogie DFS children/order'))
            require(nodes[parent][0]['name'] == ('running_gear_skin' if lod_index < 2 else 'RootNode'), (stem, 'bogie parent'))
            require(abs(transform[12]-(6.40 if bogie == 1 else -6.40)) < 3e-5, (stem, lod_index, 'bogie pivot'))
            require(abs(transform[13])+abs(transform[14]) < 1e-6, (stem, 'bogie vertical/lateral displacement'))
            frame = by_name[f'b{bogie}'][1][0]
            require(frame['mesh'] == f'vehicle/train/{style}/bogie_frame_b{bogie}_lod{lod_index}.msh', (stem, 'wrong end-specific frame resource'))
            require(frame['transf'] == IDENTITY, (stem, 'end-specific frame local transform'))
        for name in expected_connections:
            _, (node, _, parent) = by_name[name]
            owner = f"b{name.split('_b')[1][0]}_grp" if name.startswith('conn17_arm_B_') else 'RootNode'
            require(nodes[parent][0]['name'] == owner, (stem, name, 'wrong linkage ownership'))
            require(node['mesh'] == f'vehicle/train/{style}/{name}_lod{lod_index}.msh', (stem, name, 'wrong common linkage resource'))
        wheel_x = []
        for i in range(1, 7):
            _, (node, transform, parent) = by_name[f'w{i}']
            wheel_x.append(round(transform[12], 4))
            require(abs(transform[14]-.625) < 1e-5 and abs(transform[13]) < 1e-5, (stem, i, 'wheel axle location'))
            require(node['mesh'] == f'vehicle/train/{style}/wheelset_lod{lod_index}.msh', (stem, 'shared axle resource'))
        require(wheel_x == [8.2, 6.4, 4.6, -4.6, -6.4, -8.2], (stem, lod_index, wheel_x))
        config = model['metadata']['railVehicle']['configs'][lod_index]
        require(config['axles'] == [f'vehicle/train/{style}/wheelset_lod{lod_index}.msh'], (stem, 'axle declaration'))
        require(not config['fakeBogies'], (stem, 'no artificial bogie linkage'))
        signage = None
        if lod_index < 2:
            _, (skin, transform, parent) = by_name['running_gear_skin']
            require(parent == 0 and transform == IDENTITY, (stem, 'skin owner/transform'))
            skin_ref = f'vehicle/train/{style}/connection_rods_lod{lod_index}.msh'
            require(skin['skin'] == skin_ref, (stem, 'skin path'))
            skeleton, _ = flatten(skin)
            expected = ['running_gear_skin']
            for i in (1, 2):
                expected += [f'b{i}_grp', f'b{i}']+[f'w{j}' for j in range((i-1)*3+1, i*3+1)]+[f'conn17_arm_B_b{i}_s{s}' for s in ('m', 'p')]
            require([n[0]['name'] for n in skeleton] == expected and len(skeleton) == 15, (stem, 'actual local DFS skin skeleton'))
            weights = shared.meshes[skin_ref]['attributes']['jointWeights'].astype(np.float64)
            joints = np.floor(weights)
            require(weights.shape[1] == 4 and bool(np.isin(joints, [0, 1, 8]).all()), (stem, 'packed joint indices'))
            require(bool((np.abs((weights-joints).sum(axis=1)-.999) < 1e-12).all()), (stem, 'packed weight sum'))
            require(all(shared.material(m)['type'] == 'SKINNING_PHYS_NRML_MAP' for m in skin['skinMaterials']), (stem, 'non-skin material on skin'))
            check_light_config(model, row, lod_index, shared)
            require(lod['node']['children'][-1]['name'] == 'vehicle_markings', (stem, 'signage must be last root child'))
            _, (mark, transform, parent) = by_name['vehicle_markings']
            require(parent == 0 and transform == IDENTITY, (stem, 'number marks must be body-owned'))
            require(mark['mesh'] == f'vehicle/train/{style}/signage_{row["number"]}_lod{lod_index}.msh', (stem, 'wrong vehicle number mesh'))
            signage = check_signage(shared.meshes[mark['mesh']], row, lod_index)
            panes = [n for n in lod['node']['children'] if n['name'].startswith('glazing_')]
            require(len(panes) == 26 and 'cab_interior' in by_name, (stem, 'cab transparency/interior completeness'))
            for pane in panes:
                require(len(pane['materials']) == 1, (stem, 'pane material count'))
                material = shared.material(pane['materials'][0])
                require(material['type'] == 'PHYS_TRANSPARENT' and material['params']['alpha_test']['sorted'] is True,
                        (stem, 'pane sorting/transparent shader'))
        else:
            require('vehicle_markings' not in by_name and 'running_gear_skin' not in by_name, (stem, 'distant signage/skin leaked'))
            require(all(not config[p+d+'Parts'] for p in ('front','inner','back') for d in ('Forward','Backward')),
                    (stem, 'distant light index leaked'))
        require(all(e['child'] == 1 for e in model['metadata']['particleSystem']['emitters']), (stem, 'smoke owner'))
        require(all(s['group'] == 1 for s in model['metadata']['seatProvider']['seats']), (stem, 'seat owner'))
        counts, triangles = Counter(), 0
        low, high = np.full(3, np.inf), np.full(3, -np.inf)
        for node, transform, parent in nodes:
            ref = node.get('mesh') or node.get('skin')
            if not ref:
                continue
            require(ref in shared.meshes, (stem, 'missing mesh', ref))
            require(ref.startswith(f'vehicle/train/{style}/'), (stem, 'mesh from wrong livery', ref))
            require(('jointWeights' in shared.meshes[ref]['attributes']) == ('skin' in node), (stem, 'skin data/node mismatch', ref))
            materials = node.get('materials', node.get('skinMaterials'))
            require(len(materials) == shared.meshes[ref]['submeshes'], (stem, 'material/submesh count', ref))
            for material in materials:
                shared.material(material)
            counts[ref] += 1
            triangles += shared.meshes[ref]['triangles']
            shared.referenced_meshes.add(ref)
            a, b = shared.bounds(ref, transform)
            low, high = np.minimum(low, a), np.maximum(high, b)
        require(sum(v for k, v in counts.items() if 'wheelset' in k) == 6, (stem, 'wheel instances'))
        require(sum(v for k, v in counts.items() if 'bogie_frame' in k) == 2, (stem, 'frame instances'))
        require(bool((low >= np.asarray(model['boundingInfo']['bbMin'])-1e-4).all()) and
                bool((high <= np.asarray(model['boundingInfo']['bbMax'])+1e-4).all()), (stem, 'geometry exceeds model bounds'))
        reports.append({'lod': lod_index, 'instanced_triangles': triangles, 'nodes': len(nodes),
                        'bounds_min': low.tolist(), 'bounds_max': high.tolist(), 'mesh_instance_counts': dict(counts),
                        'axle_x': wheel_x, 'signage': signage})
    triangle_counts = [r['instanced_triangles'] for r in reports]
    require(triangle_counts[0] > triangle_counts[1] > triangle_counts[2], (stem, 'LOD simplification order'))
    require(triangle_counts[0] < 500000 and triangle_counts[1] < 220000 and triangle_counts[2] < 6000,
            (stem, 'explicit polygon budgets exceeded', triangle_counts))
    require(model['collider']['transf'][14] == 2.45, (stem, 'collider height'))
    emitters = model['metadata']['particleSystem']['emitters']
    require([e['position'] for e in emitters] == [[-1.7, -.76, 4.675], [-1.7, .76, 4.675]]
            and all(e['frequency'] == 19 for e in emitters), (stem, 'smoke outlet correspondence'))
    return model, {'status': 'PASS', 'variant': stem, 'number': row['number'], 'depot': row['depot'],
                   'style_resource_key': style, 'group': expected_group, 'lods': reports,
                   'scope': 'native bytes/references/ownership and geometric marking bounds; not in-game verification',
                   'tangent_basis_checked': True, 'transparent_panes_per_detailed_lod': 26,
                   'old_feature_metadata_used_as_geometry_assertions': False,
                   'actual_geometry_audit_replacements': ACTUAL_GEOMETRY_AUDIT_REPLACEMENTS,
                   'game_installation_modified': False, 'game_verified': False}


def check_light_config(model, row, lod, shared):
    config=model['metadata']['railVehicle']['configs'][lod]
    nodes,by_name=flatten(model['lods'][lod]['node'])
    fields={p+d+'Parts':'light24_'+p.lower()+'_'+('fwd' if d=='Forward' else 'bwd')
            for p in ('front','inner','back') for d in ('Forward','Backward')}
    all_ids=[]
    for field,name in fields.items():
        require(name in by_name,('missing directional light node',row['stem'],name))
        index,(node,transform,parent)=by_name[name]
        require(parent==0 and transform==IDENTITY,('light ownership',name))
        require(config[field]==[index],('actual light DFS index',field,name))
        all_ids+=config[field]
    require(len(set(all_ids))==6,'one unique node per standard lamp case')
    require(not any(n[0]['name'] in ('headlights_fwd','headlights_bwd','taillights_fwd','taillights_bwd') for n in nodes),'old lamps leaked')
    require({n[0]['name'] for n in nodes if n[0]['name'].startswith('light24_')}==set(fields.values()),'conditional lamp cohort')

def common_topology(model):
    lods = deepcopy(model['lods'])
    for lod in lods:
        lod['node']['children'] = [n for n in lod['node']['children'] if n['name'] != 'vehicle_markings' and not n['name'].startswith('light24_')]
    return lods


def main():
    require(len(ROSTER) == 10 and len({r['stem'] for r in ROSTER}) == 10 and len({r['number'] for r in ROSTER}) == 10,
            'ten unique vehicle stems/numbers required')
    require(Counter(r['jinwen'] for r in ROSTER) == {False: 8, True: 2}, 'eight CR and two Jinwen variants required')
    shared = SharedResources()
    shared.load()
    shared.inputs['verify_native_v24.py'] = sha(Path(__file__))
    shared.inputs['roster_v21.py'] = sha(ROOT/'roster_v21.py')
    for name in ('roof_revision_v24.py','front_revision_v24.py','light_revision_v24.py'):
        shared.inputs[name] = sha(ROOT/name)
    for name in ('lamp_moon_v24', 'lamp_red'):
        material = shared.material(f'vehicle/train/fxn5c/{name}.mtl')
        require(material['type'] == 'EMISSIVE' and min(material['params']['emissive_scale']['emissiveScale']) > 0,
                ('dedicated emissive light material', name))
    models, reports, style_templates = {}, [], {}
    for row in ROSTER:
        model, report = check_model(row, shared)
        models[row['stem']] = model
        template = common_topology(model)
        if row['jinwen'] in style_templates:
            require(template == style_templates[row['jinwen']], (row['stem'], 'number variant altered common livery/gear topology'))
        else:
            style_templates[row['jinwen']] = template
        reports.append(report)
        print(json.dumps({'variant': row['stem'], 'status': 'PASS', 'triangles': [r['instanced_triangles'] for r in report['lods']]}, ensure_ascii=False), flush=True)
    for lod in (0, 1):
        hashes = [shared.meshes[f"vehicle/train/{'fxn5c_jinwen' if r['jinwen'] else 'fxn5c'}/signage_{r['number']}_lod{lod}.msh"]['blob_sha256'] for r in ROSTER]
        require(len(set(hashes)) == 10, ('different vehicle numbers reused identical actual signage bytes', lod))
    for jinwen in (False, True):
        base_row = next(row for row in ROSTER if row['jinwen'] == jinwen)
        group = shared.table(RES/'models/model/vehicle/train'/(group_stem(base_row)+'.mdl'))
        require(group['metadata']['transportVehicle']['groupFileName'] == '', 'purchase-menu group must not recursively group itself')
        require(group['metadata']['transportVehicle']['multipleUnitOnly'] is True,
                'menu-only group must not add an eleventh/twelfth standalone purchasable locomotive')
        require(group['lods'] == models[base_row['stem']]['lods'], 'group preview must reuse matching base variant native geometry')
    fleet = {'status': 'PASS', 'generated_utc': datetime.now(timezone.utc).isoformat(),
             'scope': 'ten native fleet models, two shared resource styles; NOT an in-game test',
             'models': reports, 'lua_files_evaluated': len(shared.lua),
             'unique_meshes_decoded': shared.mesh_decode_count, 'meshes_referenced_by_fleet': len(shared.referenced_meshes),
             'shared_mesh_decode_policy': 'each .msh/.blob once per fleet, bounds cached per mesh/transform',
             'materials_evaluated': shared.material_count, 'groups': sorted({r['group'] for r in reports}),
             'base_game_materials': sorted(shared.external_materials), 'inputs_sha256': shared.inputs,
             'actual_geometry_audit_replacements': ACTUAL_GEOMETRY_AUDIT_REPLACEMENTS,
             'game_verified': False, 'game_installation_modified': False}
    # Publish renderer manifests only after every fleet model has passed.
    for stem, model in models.items():
        (ROOT/f'native_scene_{stem}.json').write_text(json.dumps(model), encoding='utf-8')
    (ROOT/'native_scene.json').write_text(json.dumps(models['fxn5c']), encoding='utf-8')
    (ROOT/'native_scene_jinwen.json').write_text(json.dumps(models['fxn5c_jinwen']), encoding='utf-8')
    (ROOT/'native_meshes.json').write_text(json.dumps(shared.descriptors), encoding='utf-8')
    for report in reports:
        (ROOT/f'validation_{report["variant"]}_v24.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if report['variant'] in {'fxn5c', 'fxn5c_jinwen'}:
            name = 'validation_jinwen_v24.json' if report['variant'] == 'fxn5c_jinwen' else 'validation_v24.json'
            (ROOT/name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (ROOT/'validation_fleet_v24.json').write_text(json.dumps(fleet, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'models': len(reports), 'unique_meshes_decoded': shared.mesh_decode_count,
                      'groups': fleet['groups']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        (ROOT/'validation_fleet_v24.json').write_text(json.dumps({
            'status': 'FAIL', 'generated_utc': datetime.now(timezone.utc).isoformat(),
            'error': f'{type(exc).__name__}: {exc}', 'game_verified': False,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        raise
