"""Rectangular FXN5C front panes, fitted to the supplied 0036 front photograph.

The existing bottom width and inclined cab plane are retained.  Each outer
upper edge moves out by 85 mm; this is a photo fit, not a surveyed dimension.
The change includes the real shell apertures, reveals, rubber and metal bead.
Side windows, wipers, interior, materials, UVs and all transforms are retained.
"""
import math
import bpy
from mathutils import Vector
from geometry_v06 import front_loop, chamfer_polygon
from geometry_v07 import SilhouetteBuilder

PANES = ('glazing_14', 'glazing_15', 'glazing_16', 'glazing_17')
PREFIXES = ('angular_glazing_reveal', 'angular_windscreen_bead',
            'angular_windscreen_gasket', 'angular_windshield_surround',
            'distant_windows')


def selected_objects():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH' and
            (o.name in PANES or o.name == 'body_open_shell_v07' or
             o.name.startswith(PREFIXES))]


def rectangle_loop(side=1, expand=0):
    loop = chamfer_polygon([(.070-expand, 2.810-expand),
                            (1.200+expand, 2.810-expand),
                            (1.200+expand, 3.890+expand),
                            (.070-expand, 3.890+expand)], .012)
    return [(side*y, z) for y, z in loop]


def _loop_map(expands):
    result = []
    for side in (-1, 1):
        for expand in expands:
            result.extend(zip(front_loop(side, expand), rectangle_loop(side, expand)))
    return result


def _replace_loop_points(obj, pairs, require_all=True):
    """Move existing vertices in place; retaining loops preserves per-corner UVs."""
    matrix = obj.matrix_world
    inverse = matrix.inverted()
    changed = 0
    matched = 0
    for vertex in obj.data.vertices:
        p = matrix @ vertex.co
        match = next((new for old, new in pairs
                      if math.hypot(p.y-old[0], p.z-old[1]) < 2e-6), None)
        if match is None:
            if require_all:
                raise AssertionError(('Unrecognised front-frame vertex', obj.name, tuple(p)))
            continue
        matched += 1
        new_y, new_z = match
        end = 1 if p.x > 0 else -1
        q = Vector((p.x + end*(SilhouetteBuilder.front_x(new_z)-
                              SilhouetteBuilder.front_x(p.z)), new_y, new_z))
        if (q-p).length > 1e-7:
            vertex.co = inverse @ q
            changed += 1
    obj.data.update()
    if not matched:
        raise AssertionError(('No expected window vertices found', obj.name))
    return changed


def _shell_shift(point):
    """Compact support around the existing hole, never move the cab silhouette.

    The aperture exterior-side wall receives the same linear de-rake as the
    pane.  Support fades outside the cut region into the unmodified cab face;
    X and Z are invariant, so the inclined face itself remains exactly planar.
    """
    x, y, z = point
    u = abs(y)
    if not (2.785 < z < 3.916 and .90 < u < 1.32):
        return 0.0
    depth = abs(x) - SilhouetteBuilder.front_x(z)
    if not (-.15 < depth < .045):
        return 0.0
    t = (z-2.810)/1.080
    old_outer = 1.200-.085*t
    # All aperture bevel vertices lie on the flat part of this support.
    if u <= old_outer-.035:
        weight = max(0, (u-.90)/(old_outer-.035-.90))
    elif u <= old_outer+.035:
        weight = 1.0
    else:
        weight = max(0, (1.32-u)/(1.32-old_outer-.035))
    return (1 if y > 0 else -1)*.085*t*weight


def _open_shell(obj):
    mesh = obj.data
    old_normals = [n.vector.copy() for n in mesh.corner_normals]
    old_face_normals = [p.normal.copy() for p in mesh.polygons]
    changed_vertices = set()
    mat = obj.matrix_world
    inv = mat.inverted()
    for vertex in mesh.vertices:
        p = mat @ vertex.co
        shift = _shell_shift(p)
        if abs(shift) > 1e-8:
            p.y += shift
            vertex.co = inv @ p
            changed_vertices.add(vertex.index)
    mesh.update()
    # Unaffected corner normals remain bit-for-bit source values.  Only changed
    # aperture side/bevel faces need their geometric normals updated; the large
    # planar face and all other original weighted normals are untouched.
    recalculated = 0
    if mesh.has_custom_normals:
        for poly, old_n in zip(mesh.polygons, old_face_normals):
            if any(i in changed_vertices for i in poly.vertices) and (poly.normal-old_n).length > 1e-5:
                for loop in poly.loop_indices:
                    old_normals[loop] = poly.normal.copy()
                recalculated += 1
        mesh.normals_split_custom_set(old_normals)
    assert changed_vertices, 'The front shell apertures were not updated'
    return {'vertices': len(changed_vertices), 'aperture_face_normals': recalculated}


def _far_proxy(obj):
    """Two matching rectangular dark panes at the existing far-LOD depth."""
    old_mesh = obj.data
    pts = [obj.matrix_world @ v.co for v in old_mesh.vertices]
    end = 1 if sum(p.x for p in pts) > 0 else -1
    offset = sum(abs(p.x)-SilhouetteBuilder.front_x(p.z) for p in pts)/len(pts)
    verts = []
    faces = []
    for side in (-1, 1):
        start = len(verts)
        for y, z in ((side*.070, 2.810), (side*1.200, 2.810),
                     (side*1.200, 3.890), (side*.070, 3.890)):
            verts.append(obj.matrix_world.inverted() @ Vector((end*(SilhouetteBuilder.front_x(z)+offset), y, z)))
        face = tuple(range(start, start+4))
        a, b, c = [verts[i] for i in face[:3]]
        if (b-a).cross(c-a).x*end < 0:
            face = tuple(reversed(face))
        faces.append(face)
    mesh = bpy.data.meshes.new(old_mesh.name+'_rect39')
    mesh.from_pydata(verts, [], faces)
    for material in old_mesh.materials:
        mesh.materials.append(material)
    # Preserve the existing planar material and use a non-mirrored local map.
    uv = mesh.uv_layers.new(name='UVMap')
    for poly in mesh.polygons:
        for loop_index in poly.loop_indices:
            p = verts[mesh.loops[loop_index].vertex_index]
            uv.data[loop_index].uv = ((abs(p.y)-.070)/1.130, (p.z-2.810)/1.080)
    mesh.update()
    obj.data = mesh
    return {'panes': 2, 'vertices': 8, 'triangles': 4}


def apply(builder, jw=False):
    if bpy.context.scene.get('glazing_revision_v39_done'):
        return {'status': 'ALREADY_APPLIED', 'lod': int(builder.lod)}
    report = {'status': 'PASS', 'lod': int(builder.lod), 'jinwen': bool(jw),
              'photo_fit_not_surveyed': True, 'glass_outer_half_width_m': 1.200,
              'glass_inner_half_width_m': .070, 'glass_z_m': [2.810, 3.890],
              'upper_edge_expansion_m': .085, 'objects': []}
    if builder.lod >= 2:
        for obj in selected_objects():
            if obj.name.startswith('distant_windows'):
                report['objects'].append({'name': obj.name, **_far_proxy(obj)})
        assert len(report['objects']) == 2
    else:
        assert all(bpy.data.objects.get(name) is not None for name in PANES)
        for obj in selected_objects():
            if obj.name == 'body_open_shell_v07':
                report['objects'].append({'name': obj.name, **_open_shell(obj)})
                continue
            if obj.name in PANES:
                pairs = _loop_map((.001,))
            elif obj.name.startswith('angular_glazing_reveal'):
                pairs = _loop_map((.030, -.001))
            elif obj.name.startswith('angular_windscreen_bead'):
                pairs = _loop_map((.037, .022))
            elif obj.name.startswith('angular_windscreen_gasket'):
                pairs = _loop_map((.023, -.002))
            elif obj.name.startswith('angular_windshield_surround'):
                old = chamfer_polygon([(-1.224,2.784),(1.224,2.784),
                                       (1.141,3.919),(-1.141,3.919)], .012)
                new = chamfer_polygon([(-1.224,2.784),(1.224,2.784),
                                       (1.224,3.919),(-1.224,3.919)], .012)
                count = _replace_loop_points(obj, list(zip(old,new)), require_all=False)
                report['objects'].append({'name': obj.name, 'vertices': count})
                continue
            else:
                continue
            count = _replace_loop_points(obj, pairs)
            report['objects'].append({'name': obj.name, 'vertices': count})
        assert len(report['objects']) == 19, report['objects']
    bpy.context.scene['glazing_revision_v39_done'] = True
    return report
