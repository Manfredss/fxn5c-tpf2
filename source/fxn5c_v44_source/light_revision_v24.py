"""Local-cab lighting using TPF2's documented six railVehicle visibility lists.

The number-to-pattern assignment is deliberately frozen, not a claim about the
real units' wiring. Each direction resource contains both locomotive ends, so a
locomotive hauling wagons still shows its own rear INNER red pair. The six
instances are required because an instance ID may belong to only one Parts list.

https://www.wiki.transportfever2.com/doku.php?id=modding:vehicleadvancedtopics
https://www.wiki.transportfever2.com/doku.php?id=modding:resourcetypes:mtl

For a singleton, the documentation does not establish front/back exclusivity.
If both lists are enabled they reference identical geometry/materials, never
opposite colors. Native reconstruction may deduplicate those exact instances;
that is explicitly a preview policy, not an engine-behavior assertion.

No bpy import at module scope: exporter, independent verifier and release audit
can all read this assignment and manipulate literal native model dictionaries.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import struct

WHITE = 'vehicle/train/fxn5c/lamp_moon_v24.mtl'
RED = 'vehicle/train/fxn5c/lamp_red.mtl'
MOON_TEXTURE = 'models/vehicle/train/fxn5c/lamp_moon_v24.tga'
MOON_RGB = (224, 242, 255)
PATTERN_SLOT_MATERIAL = 'light24_leading_inner_SLOT'
LEGACY_NAMES = ('headlights_fwd', 'taillights_fwd', 'headlights_bwd', 'taillights_bwd')
SOURCE_NAMES = ('light24_fwd', 'light24_bwd')
POSITIONS = ('front', 'inner', 'back')
DIRECTIONS = ('fwd', 'bwd')
FIELDS = {p + ('Forward' if d == 'fwd' else 'Backward') + 'Parts': (p, d)
          for d in DIRECTIONS for p in POSITIONS}
NATIVE_NAMES = tuple('light24_' + p + '_' + d for d in DIRECTIONS for p in POSITIONS)
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
SEGMENTS = {0: 24, 1: 12}
# SHA256('FXN5C-v24-headlamp:' + number), sorted once; first five red.
# Freeze the result so a future roster extension cannot change saved choices.
LEADING_INNER = {'0051': 'white', '0096': 'red', '0102': 'red', '0057': 'red',
                 '0081': 'white', '0066': 'white', '0035': 'red', '0115': 'red',
                 '7006': 'white', '7005': 'white'}


def pattern_for(number):
    """No fallback randomness: unknown roster numbers require a conscious choice."""
    return LEADING_INNER[str(number)]


def register_source_materials(generator):
    """Match the actual sRGB texture in Blender's linear emission shader."""
    def linear(v):
        s = v / 255.0
        return s / 12.92 if s <= .04045 else ((s + .055) / 1.055) ** 2.4
    generator.EMISSIVE['lamp_moon_v24'] = (tuple(linear(v) for v in MOON_RGB) + (1.0,), 9.0)


def write_material_resources(mod_root):
    """New opt-in shader/solid-color texture; never rewrite v23 white/red."""
    root = Path(mod_root) / 'res'
    mat = root / 'models/material' / WHITE
    texture = root / 'textures' / MOON_TEXTURE
    mat.parent.mkdir(parents=True, exist_ok=True)
    texture.parent.mkdir(parents=True, exist_ok=True)
    text = '''function data()
return {
 order = 0,
 params = {
  fade_out_range = { fadeOutEndDist = 20000, fadeOutStartDist = 10000, },
  two_sided = { flipNormal = false, twoSided = false, },
  emissive_scale = { emissiveScale = { 9.0, 9.0, 9.0, }, },
  map_emissive = { fileName = "''' + MOON_TEXTURE + '''", type = "TWOD", },
  polygon_offset = { factor = -1, units = -1, forceDepthWrite = false, },
 },
 type = "EMISSIVE",
}
end
'''
    mat.write_text(text, encoding='utf-8')
    # Uncompressed, top-origin, 4x4 RGB TGA. This is shader color data, not an
    # edited reference photograph or a replacement for native lamp geometry.
    header = struct.pack('<BBBHHBHHHHBB', 0, 0, 2, 0, 0, 0, 0, 0, 4, 4, 24, 32)
    texture.write_bytes(header + bytes(reversed(MOON_RGB)) * 16)
    return (mat, texture)


def is_light_object(obj):
    return (obj.name in LEGACY_NAMES or obj.name.startswith('light24_')
            or bool(obj.get('light24_emitter')))


def flatten(node):
    result = []
    def visit(n):
        result.append(n)
        for child in n.get('children', []):
            visit(child)
    visit(node)
    return result


def upper_emitter_point(builder, end, side, u, v):
    """Resolved from the v24 fixture recipe, never an independent lamp offset."""
    from roof_revision_v24 import upper_emitter_point as point
    return point(builder, end, side, u, v)


def lower_emitter_point(end, side, inner, u, v):
    # Same frame as front_lamps_v14.mapper. Historical kind='red' means OUTER
    # fixture position, not the emitted color; outer lamps are white in v24.
    return (end * ((11.04 if inner else 10.990) + .020),
            side * ((1.24 if inner else 1.53) + u),
            (2.02 if inner else 2.055) + v)


def build(builder, jw=False, number='0051'):
    """Replace emitters, retaining every bezel, lens and reflector fixture.

    Source objects are only TWO resources. Their extra per-position instances
    are native metadata, not duplicated editable source geometry. Backward is
    hidden in ordinary source previews. Export uses the object irrespective of
    hide_render. LOD2 intentionally remains unlit as in v23.
    """
    import bpy
    register_source_materials(builder.g)
    for obj in list(bpy.context.scene.objects):
        if is_light_object(obj):
            bpy.data.objects.remove(obj, do_unlink=True)
    if builder.lod >= 2:
        return {'lod': builder.lod, 'number': number, 'objects': []}
    color = pattern_for(number)
    marker = bpy.data.materials.get(PATTERN_SLOT_MATERIAL)
    if marker:
        bpy.data.materials.remove(marker)
    marker = builder.g.material('lamp_moon_v24' if color == 'white' else 'lamp_red').copy()
    marker.name = PATTERN_SLOT_MATERIAL
    marker['light24_slot'] = 'leading_inner'
    marker['light24_color'] = color
    n = SEGMENTS[builder.lod]
    report = {'lod': builder.lod, 'jinwen': bool(jw), 'number': number,
              'leading_inner': color, 'objects': [], 'optics': {}}
    for direction, end in (('fwd', 1), ('bwd', -1)):
        objects = []
        optics = []
        specs = [('outer', end, 'white', .068), ('top', end, 'white', .038),
                 ('inner', end, color, .068), ('inner', -end, 'red', .068)]
        for kind, lamp_end, lamp_color, radius in specs:
            for side in (-1, 1):
                loop = [(radius * math.cos(i * math.tau / n),
                         radius * math.sin(i * math.tau / n)) for i in range(n)]
                mapper = ((lambda u, v, e=lamp_end, s=side:
                           upper_emitter_point(builder, e, s, u, v)) if kind == 'top'
                          else (lambda u, v, e=lamp_end, s=side, inner=kind == 'inner':
                                lower_emitter_point(e, s, inner, u, v)))
                material = 'lamp_moon_v24' if lamp_color == 'white' else 'lamp_red'
                obj = builder.sheet('light24_disc', loop, mapper, material,
                                    axis=(lamp_end, 0, 0))
                if kind == 'inner' and lamp_end == end:
                    obj.data.materials.clear()
                    obj.data.materials.append(marker)
                objects.append(obj)
                optics.append({'end': lamp_end, 'side': side, 'kind': kind,
                               'color': lamp_color, 'radius': radius,
                               'center': list(mapper(0, 0))})
        name = 'light24_' + direction
        obj = builder.g.join_objects(objects, name)
        obj['light24_emitter'] = True
        obj['light24_direction'] = direction
        obj['light24_number'] = number
        obj['light24_optics_json'] = json.dumps(optics)
        obj.hide_render = direction == 'bwd'
        report['objects'].append(name)
        report['optics'][direction] = optics
    bpy.context.scene['light24_assignment_json'] = json.dumps(LEADING_INNER, sort_keys=True)
    bpy.context.scene['light24_source_report_json'] = json.dumps(report, sort_keys=True)
    return report


def export_lights(exporter, builder):
    """Write TWO meshes into current style MESH_DIR; return JSON-safe resources.

    Do NOT pass material_mapper to export_mesh: remapping its grouping keys would
    merge the independent leading-inner submesh with permanent white faces.
    Instead native material slots may deliberately refer to the same resource.
    """
    import bpy
    if builder.lod >= 2:
        return {}
    write_material_resources(exporter.MOD_ROOT)
    resources = {}
    for direction in DIRECTIONS:
        name = 'light24_' + direction
        obj = bpy.data.objects[name]
        mesh_name = name + '_lod' + str(builder.lod)
        materials, vertices, triangles = exporter.export_mesh(
            mesh_name, [(obj, obj.matrix_world.copy())])
        marker = PATTERN_SLOT_MATERIAL + '.mtl'
        assert len(materials) == 3 and materials.count(marker) == 1, materials
        slot = materials.index(marker)
        materials[slot] = WHITE
        resources[direction] = {
            'mesh': 'vehicle/train/' + exporter.RESOURCE_KEY + '/' + mesh_name + '.msh',
            'materials': materials, 'pattern_slot': slot,
            'vertices': vertices, 'triangles': triangles,
        }
    return resources


def patch_mdl(model, row, lod_resources):
    """Mutate a decoded .mdl in place, return the same dictionary.

    All retained nodes keep relative order and the skin subtree is untouched.
    The six replacement instances follow retained geometry but precede final
    vehicle_markings, preserving the exporter contract that signage is last.
    Their IDs are derived only after the actual tree is final.
    """
    assert model['metadata']['transportVehicle']['reversible'] is True
    assert len(model['lods']) == 3
    color = pattern_for(row['number'])
    for lod, entry in enumerate(model['lods']):
        root = entry['node']
        before = flatten(root)
        retained = {n['name']: deepcopy(n) for n in before if n.get('skin')}
        root['children'] = [n for n in root['children']
                            if n['name'] not in LEGACY_NAMES and not n['name'].startswith('light24_')]
        replacements = []
        if lod < 2:
            resources = lod_resources.get(lod, lod_resources.get(str(lod)))
            assert set(resources) == set(DIRECTIONS)
            for direction in DIRECTIONS:
                res = resources[direction]
                assert len(res['materials']) == 3
                mats = list(res['materials'])
                mats[res['pattern_slot']] = RED if color == 'red' else WHITE
                assert all(m in (WHITE, RED) for m in mats)
                for position in POSITIONS:
                    replacements.append({
                        'name': 'light24_' + position + '_' + direction,
                        'mesh': res['mesh'], 'materials': list(mats),
                        'transf': list(IDENTITY),
                    })
        insertion = next((i for i, n in enumerate(root['children'])
                          if n['name'] == 'vehicle_markings'), len(root['children']))
        root['children'][insertion:insertion] = replacements
        nodes = flatten(root)
        by_name = {n['name']: i for i, n in enumerate(nodes)}
        assert len(by_name) == len(nodes)
        config = model['metadata']['railVehicle']['configs'][lod]
        for field, (position, direction) in FIELDS.items():
            config[field] = ([by_name['light24_' + position + '_' + direction]] if lod < 2 else [])
        assert retained == {n['name']: n for n in nodes if n.get('skin')}
    return model


def validate_configuration(model, number):
    """Metadata-only independent integration guard; geometry audit is separate."""
    color = pattern_for(number)
    report = []
    assert model['metadata']['transportVehicle']['reversible'] is True
    for lod, entry in enumerate(model['lods']):
        nodes = flatten(entry['node'])
        config = model['metadata']['railVehicle']['configs'][lod]
        seen = set()
        for field, (position, direction) in FIELDS.items():
            ids = config[field]
            assert len(ids) == (1 if lod < 2 else 0), (lod, field, ids)
            for index in ids:
                assert index not in seen, ('instance ID in multiple lists', lod, index)
                seen.add(index)
                node = nodes[index]
                assert node['name'] == 'light24_' + position + '_' + direction
                assert node['transf'] == IDENTITY
                assert len(node['materials']) == 3
                # Exported submesh order: permanent white, leading-inner, rear-red.
                assert node['materials'] == [WHITE, RED if color == 'red' else WHITE, RED]
        expected = set(NATIVE_NAMES) if lod < 2 else set()
        actual = {n['name'] for n in nodes if n['name'].startswith('light24_')}
        assert actual == expected and not any(n['name'] in LEGACY_NAMES for n in nodes)
        report.append({'lod': lod, 'instance_count': len(seen), 'leading_inner': color})
    return report


def preview_visibility(model, direction='fwd', position='front', lod=0, deduplicate_singleton=True):
    """Resolve actual IDs, not assumed indices; optionally dedup exact singleton instances."""
    assert direction in DIRECTIONS
    assert position in POSITIONS + ('singleton',)
    nodes = flatten(model['lods'][lod]['node'])
    config = model['metadata']['railVehicle']['configs'][lod]
    wanted = POSITIONS[::2] if position == 'singleton' else (position,)
    ids = [i for field, (p, d) in FIELDS.items() if d == direction and p in wanted
           for i in config[field]]
    keep = []
    signatures = set()
    for i in ids:
        node = nodes[i]
        signature = (node['mesh'], tuple(node['materials']), tuple(node['transf']))
        if not deduplicate_singleton or signature not in signatures:
            keep.append(i)
        signatures.add(signature)
    return {'direction': direction, 'position': position, 'lod': lod,
            'raw_active_ids': ids, 'visible_ids': keep,
            'visible_names': [nodes[i]['name'] for i in keep],
            'all_lamp_names': [n['name'] for n in nodes if n['name'].startswith('light24_')],
            'exact_duplicate_instances_hidden_for_preview': len(ids) - len(keep),
            'engine_tested': False}


def apply_native_preview(model, direction='fwd', position='front', lod=0):
    """After render_native.load_native, configure directional visibility in Blender."""
    import bpy
    report = preview_visibility(model, direction, position, lod)
    visible = set(report['visible_names'])
    for name in report['all_lamp_names']:
        obj = bpy.data.objects.get(name)
        assert obj is not None, ('native light node missing from reconstructed scene', name)
        obj.hide_render = name not in visible
        obj.hide_set(name not in visible)
    return report
