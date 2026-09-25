"""7006 paint reconstruction from photographs, not official licensed artwork.

Paint is split into the actual existing sheet/blade polygons: no floating side
billboards, no photographs, no AI-enhanced evidence, no borrowed 3D assets.
JWR's connected letter mark is reconstructed from the user-supplied logo,
not a generic wave. Branding rights remain with their respective owners.
"""
import math
from pathlib import Path
import bpy
from mathutils import Vector
from geometry_v05 import split_polygon

NUMBER = '7006'
PAINT_MATS = ('blue', 'light_blue', 'yellow')
HEIGHT_BREAKS = (1.58, 1.64, 1.70, 1.73, 1.765, 1.77, 1.83, 1.865, 1.925, 2.60, 3.45, 3.95, 4.02)
SLASHES = (6.72, 7.58, 8.44)
SLASH_WIDTH = .30
OUTER_BLUE_EDGE = 9.20


def paint_at(x, y, z, front=False):
    """Metric control lines estimated against 7006 and 7007 reference photos."""
    if z >= 4.02 or (z >= 3.95 and not front):
        return 'jw_roof'
    if z < 1.58:
        return 'jw_blue' if abs(x) > 9.9 else 'jw_white'
    if front:
        if 1.77 <= z < 1.83:
            return 'jw_red'
        if 1.865 <= z < 1.925:
            return 'jw_blue'
        return 'jw_blue' if z >= 2.60 else 'jw_white'
    if 1.77 <= z < 1.83:
        return 'jw_red'
    if 1.865 <= z < 1.925:
        return 'jw_blue'
    if abs(x) >= 9.30 and z >= 2.60:
        return 'jw_blue'
    if 1.925 <= z < 3.45 and abs(x) + .48 * (z - 1.925) <= OUTER_BLUE_EDGE:
        q = abs(x) + .48 * (z - 1.925)
        if any(a <= q <= a + SLASH_WIDTH for a in SLASHES):
            return 'jw_white'
        return 'jw_blue'
    return 'jw_white'


def paint_mesh(obj, gen, force=False, front=False, classifier=None, simple=False):
    """Clip only painted triangular faces; retain every aperture and fold."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    old_mats = list(mesh.materials)
    keys = [Path(m.name).name for m in old_mats]
    if not force and not any(k in PAINT_MATS for k in keys):
        return
    # Polygons remain in object-local coordinates. World-space paint control
    # planes make the stripes line up across body skin, doors and louver blades.
    tf, inv = obj.matrix_world.copy(), obj.matrix_world.inverted()
    verts, faces, indices, smooth = [], [], [], []
    new_mats = list(old_mats)
    indices_by_name = {m.name: i for i, m in enumerate(new_mats)}
    def material_index(key):
        mat = gen.material(key)
        if mat.name not in indices_by_name:
            indices_by_name[mat.name] = len(new_mats)
            new_mats.append(mat)
        return indices_by_name[mat.name]
    for tri in mesh.loop_triangles:
        old_index = tri.material_index
        painted = force or keys[old_index] in PAINT_MATS
        pieces = [[tuple(tf @ mesh.vertices[v].co) for v in tri.vertices]]
        if painted:
            for z in ((1.925,2.60,3.45,3.95) if simple else HEIGHT_BREAKS) + ((.65,) if classifier else ()):
                pieces = [q for p in pieces for q in split_polygon(p, lambda v, z=z: v[2]-z)]
            for x in ((-9.30,-9.05,0,9.05,9.30) if simple else (-9.9, -9.30, -9.05, 0, 9.05, 9.30, 9.9)):
                pieces = [q for p in pieces for q in split_polygon(p, lambda v, x=x: v[0]-x)]
            for sign in (() if simple else (-1, 1)):
                for a in SLASHES+(OUTER_BLUE_EDGE,):
                    for edge in ((a,) if a==OUTER_BLUE_EDGE else (a,a+SLASH_WIDTH)):
                        pieces = [q for p in pieces for q in split_polygon(p,
                                  lambda v, s=sign, e=edge: s*v[0]+.48*(v[2]-1.925)-e)]
        for points in pieces:
            center = sum((Vector(p) for p in points), Vector()) / len(points)
            # A cab end is almost perpendicular to X. Chamfer faces receive
            # front paint as well so the white nose wraps continuously.
            is_front = front or (abs(center.x) > 10.78 and center.z < 2.61)
            color = classifier(*center) if classifier else paint_at(*center, front=is_front)
            if simple:
                x,y,z=center
                color='jw_roof' if z>=3.95 else 'jw_blue' if (abs(x)<9.05 and 1.925<=z<3.45) or (abs(x)>=9.30 and 2.60<=z<3.95) else 'jw_white'
            idx = material_index(color) if painted else old_index
            start = len(verts)
            verts.extend(tuple(inv @ Vector(p)) for p in points)
            faces.append(tuple(range(start, len(verts))))
            indices.append(idx)
            smooth.append(mesh.polygons[tri.polygon_index].use_smooth)
    replacement = bpy.data.meshes.new(mesh.name + '_7006_paint')
    replacement.from_pydata(verts, [], faces)
    for m in new_mats:
        replacement.materials.append(m)
    for face, idx, sm in zip(replacement.polygons, indices, smooth):
        face.material_index, face.use_smooth = idx, sm
    replacement.update()
    if simple:
        from china_livery_v20 import compact_distant_paint
        compact_distant_paint(replacement)
    obj.data = replacement
    obj['jinwen15_paint_split'] = True


def recolor(obj, gen, mapping):
    for i, mat in enumerate(obj.data.materials):
        key = Path(mat.name).name
        if key in mapping:
            obj.data.materials[i] = gen.material(mapping[key])


def set_material(obj, gen, key):
    obj.data.materials.clear()
    obj.data.materials.append(gen.material(key))
    for face in obj.data.polygons:
        face.material_index = 0


def side_text(b, name, value, x, side, z, size, key='jw_blue', cn=False):
    obj = b.text(name, value, (x, side*1.67, z), size,
                 (math.pi/2, 0, math.pi if side > 0 else 0), key, cn)
    bpy.context.view_layer.update()
    tf, inv = obj.matrix_world.copy(), obj.matrix_world.inverted()
    for v in obj.data.vertices:
        p = tf @ v.co
        p.y = side*(b.side_y(p.x, p.z)+.010)
        v.co = inv @ p
    obj['jinwen15_mark'] = value
    return obj


def apply(b):
    gen = b.g
    assert not bpy.context.scene.get('jinwen15_applied'), 'Apply to a clean CR scene once only'
    delete = ('cyan_sweep', 'gold_sweep', 'cab_number', 'cab_depot', 'side_number',
              'nose_number', 'central_plough_yellow', 'pilot_chevron', 'pilot_warning')
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(delete):
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.context.view_layer.update()
    for obj in list(bpy.context.scene.objects):
        if obj.type != 'MESH' or obj.name.startswith('bounds|'):
            continue
        if obj.name.startswith(('railway_emblem', 'side_fuxing', 'sill_warning', 'cock_coloured_lever')):
            continue
        if obj.name.startswith('nose_fuxing'):
            set_material(obj, gen, 'jw_red')
            continue
        paint_mesh(obj, gen, simple=b.lod==2)
        recolor(obj, gen, {'roof':'jw_roof'})
        if obj.name.startswith(('radiator_long_grid_v12','radiator_cross_grid_v12')):
            set_material(obj,gen,'grille_black')
        # Only underframe/body equipment is painted grey: cab seats, rubber
        # gaskets and internal dark baffles must not turn pale blue.
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        if obj.get('connection_role') or (points and max(v.z for v in points) < 1.61):
            recolor(obj, gen, {'graphite':'jw_frame', 'cast_steel':'jw_spring', 'spring_steel':'jw_frame'})
        if obj.name.startswith(('angular_windshield_surround', 'windscreen_angular_surround', 'windshield_surround',
                                'windshield_centre_pillar', 'windshield_lower_surround')):
            set_material(obj, gen, 'jw_blue')
        if obj.name.startswith(('thin_anti_climber', 'anticlimber_')):
            set_material(obj, gen, 'jw_white')
        if obj.name.startswith('nose_grey_belt'):
            paint_mesh(obj, gen, force=True, front=True)
        if obj.name.startswith(('central_pointed_plough', 'central_plough_half', 'central_plough_core')):
            set_material(obj, gen, 'red_paint')
        if obj.name.startswith(('black_pilot_plate', 'pilot_corner_fold', 'pilot_side_return')):
            # Real 7006 has blue upper and red lower end plates, not the
            # yellow/black warning scheme of the small 7005 drawing.
            paint_mesh(obj, gen, force=True, classifier=lambda x,y,z: 'red_paint' if z < .65 else 'jw_blue')
        if obj.name.startswith('side_skirt'):
            recolor(obj, gen, {'graphite':'jw_blue', 'dark':'jw_blue'})
    if b.lod < 2:
        from lettering_v20 import side_titles, jwr_mark, jinwen_cab_sign
        side_titles(b, NUMBER, jinwen=True)
        for side in (-1,1):
            side_text(b, 'jinwen_depot', '金温·温段', .30, side, 3.73, .10, 'jw_frame', True)
            for end in (-1,1):
                if b.lod == 0:
                    jinwen_cab_sign(b,end*9.65,side)
            if b.lod == 0:
                jwr_mark(b,.75,side,1.52,.33)
        from front_finish_v11 import _paint, _number_placement, NUMBER_FONT_SIZE
        base, scale, _ = _number_placement()
        for end in (-1,1):
            obj = _paint(b, 'jinwen_nose_number', 'FXN5C '+NUMBER, NUMBER_FONT_SIZE, base, end, scale=scale)
            set_material(obj, gen, 'jw_red')
        from jinwen_roof_v20 import apply as apply_roof
        apply_roof(b)
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals()
    gen.ensure_uvs()
    bpy.context.scene['jinwen15_applied'] = True
    bpy.context.scene['livery'] = 'Jinwen Railway FXN5C 7006 (photo reconstruction)'
    bpy.context.view_layer.update()
