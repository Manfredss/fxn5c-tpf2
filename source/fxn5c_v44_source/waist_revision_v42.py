"""Warm only the existing waist paint; lettering/safety paint remain immutable."""
from pathlib import Path
import bpy

KEY = 'waist42_amber'
SPEC = ((.96, .445, .012, 1), .36, .12)
PREFIX = 'vehicle/train/fxn5c/'


def key(mat):
    return Path(mat.name).name.removesuffix('.mtl') if mat else ''


def eligible(obj, style):
    if obj.type != 'MESH' or style == 'fxn5c_jinwen':
        return False
    if style == 'fxn5c_prototype_0001':
        return bool(obj.get('prototype41_straight_waist'))
    assert style == 'fxn5c'
    return obj.name == 'body_open_shell_v07' or obj.name.startswith((
        'roof28_radiator_', 'window30_side_', 'window34_radiator_leaf'))


def objects(style):
    old = 'proto_yellow' if style == 'fxn5c_prototype_0001' else 'yellow'
    return sorted([o for o in bpy.context.scene.objects if eligible(o, style) and
                   any(key(o.data.materials[p.material_index]) in (old, KEY)
                       for p in o.data.polygons)], key=lambda o: o.name)


def selected_objects(style):
    return [o for o in objects(style) if not o.get('roof26_animation_kind')]


def apply(builder, style):
    if style == 'fxn5c_jinwen':
        return dict(status='NO_OP', reason='JW magenta belt retained')
    builder.g.MATERIAL_SPECS[KEY] = SPEC
    material = builder.mat(KEY)
    old = 'proto_yellow' if style == 'fxn5c_prototype_0001' else 'yellow'
    result = []
    for obj in objects(style):
        slots = {p.material_index for p in obj.data.polygons
                 if key(obj.data.materials[p.material_index]) == old}
        assert slots, ('already applied', obj.name)
        points = [obj.matrix_world @ obj.data.vertices[i].co
                  for p in obj.data.polygons if p.material_index in slots for i in p.vertices]
        low, high = min(p.z for p in points), max(p.z for p in points)
        assert 1.60 < low < high < 2.20, ('non-waist yellow', obj.name, low, high)
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        for index in slots:
            obj.data.materials[index] = material
        obj['waist42_local_material_only'] = True
        result.append(dict(name=obj.name, material_slots=sorted(slots),
                           animated=bool(obj.get('roof26_animation_kind')),
                           z_range=[low, high]))
    assert result, ('no waist found', style)
    return dict(status='PASS', color_linear=list(SPEC[0]), changed=result,
                gold_and_safety_materials_unchanged=True)


def motion_material(reference, style):
    if style == 'fxn5c' and reference.lstrip('/') == PREFIX+'yellow.mtl':
        return PREFIX+KEY+'.mtl'
    return reference


def check_saved_scene(lod, style):
    rows = objects(style)
    if style == 'fxn5c_jinwen':
        assert not rows
        return dict(status='NO_OP', objects=0)
    assert rows
    for obj in rows:
        assert obj.get('waist42_local_material_only'), obj.name
        assert any(key(m) == KEY for m in obj.data.materials), obj.name
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and any(key(m) == KEY for m in obj.data.materials):
            assert eligible(obj, style), ('amber outside waist', obj.name)
    return dict(status='PASS', objects=len(rows), lod=lod)
