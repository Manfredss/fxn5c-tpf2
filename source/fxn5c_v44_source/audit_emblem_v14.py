"""Check SVG-derived emblems on the reconstructed native game body mesh.

This audit reads actual material-assigned triangles. It does not use object
feature counters or trust the original Blender badge objects. Export changes,
old yellow bars, a filled arc mouth, reflection errors and dropped faces fail.
"""
from collections import Counter
import json
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

import emblem_v11 as emblem

TOLERANCE_M = 1.5e-5  # Strictly less than 2e-5 m; native data are float32.
FRONT_X_M = 11.0415


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _inside(point, contour):
    x, y = point
    inside = False
    for a, b in zip(contour, contour[1:]+contour[:1]):
        if (a[1] > y) != (b[1] > y):
            if x < a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                inside = not inside
    return inside


def _covered(point, triangles):
    for a, b, c in triangles:
        signs = (_cross(a,b,point), _cross(b,c,point), _cross(c,a,point))
        if min(signs) >= -1e-12 or max(signs) <= 1e-12:
            return True
    return False


def _edge_distance(point, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0, min(1, ((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return ((point[0]-a[0]-t*dx)**2+(point[1]-a[1]-t*dy)**2)**.5


def _expected_geometry():
    points, faces, world_contours = [], [], []
    scale = emblem.WIDTH_M/200.0
    for contour in emblem.sample_contours(0):
        offset = len(points)
        world_contours.append(tuple((u*scale, emblem.CENTER_Z-(v-5)*scale)
                                    for u,v in contour))
        points.extend(world_contours[-1])
        faces.extend(tuple(offset+i for i in face)
                     for face in emblem.tessellate_contour(contour))
    return points, faces, tuple(world_contours)


def _native_yellow_triangles(body):
    """Select every yellow triangle intersecting the prescribed badge region.

    Intersection by axis-aligned bounds catches a surviving old triangle even
    if one of its vertices falls beyond the exact emblem bounds. The eventual
    one-to-one reference correspondence rejects any such unrelated triangle.
    """
    body.data.calc_loop_triangles()
    vertices = [body.matrix_world@v.co for v in body.data.vertices]
    by_end = {-1: [], 1: []}
    for tri in body.data.loop_triangles:
        material = body.data.materials[tri.material_index]
        if material is None or material.name.rsplit("/",1)[-1] != "yellow":
            continue
        ps = tuple(vertices[i] for i in tri.vertices)
        ys, zs = [p.y for p in ps], [p.z for p in ps]
        if min(ys) > .23 or max(ys) < -.23 or min(zs) > 2.42 or max(zs) < 1.90:
            continue
        for end in (-1,1):
            if max(p.x*end for p in ps) > 10.9:
                assert all(p.x*end > 10.9 for p in ps), "Yellow triangle crosses badge ROI longitudinally"
                by_end[end].append(ps)
    return by_end


def audit(root, version='v14'):
    path = Path(root)/f"emblem_geometry_audit_{version}.json"
    report = {
        "status": "RUNNING",
        "scope": "Actual native LOD0 body triangles and material assignments; not a game test or factory-dimension certification",
        "reference": "assets/China_Railways.svg; Commons TB1838-87-based public redrawing",
        "position_tolerance_m": TOLERANCE_M,
        "selection": "yellow body triangles intersecting abs(x)>10.9, abs(y)<0.23, z=1.90..2.42",
        "ends": [],
    }
    try:
        assert TOLERANCE_M < 2e-5
        body = bpy.data.objects["body"]
        assert body.type == "MESH", "Native body is not a mesh"
        reference_points, reference_faces, contours = _expected_geometry()
        reference_counter = Counter(tuple(sorted(face)) for face in reference_faces)
        native = _native_yellow_triangles(body)
        report["expected_total_triangles"] = len(reference_faces)*2
        report["actual_total_triangles"] = sum(map(len,native.values()))
        assert report["actual_total_triangles"] == report["expected_total_triangles"], report
        expected_area = sum(abs(_cross(*(reference_points[i] for i in face)))/2
                            for face in reference_faces)
        edge_pairs = [pair for contour in contours
                      for pair in zip(contour,contour[1:]+contour[:1])]
        for end in (-1,1):
            ps_by_face = native[end]
            assert len(ps_by_face) == len(reference_faces), (end,len(ps_by_face),len(reference_faces))
            kd = KDTree(len(reference_points))
            for i,(y,z) in enumerate(reference_points):
                kd.insert(Vector((end*FRONT_X_M,y,z)),i)
            kd.balance()
            actual_counter = Counter()
            maximum_error, minimum_alignment = 0.0, 1.0
            triangles_2d, all_points = [], []
            for ps in ps_by_face:
                indices = []
                for point in ps:
                    _, index, distance = kd.find(point)
                    maximum_error = max(maximum_error,distance)
                    assert distance < TOLERANCE_M, ("unexpected yellow vertex",end,list(point),distance)
                    indices.append(index)
                assert len(set(indices)) == 3, ("collapsed native triangle",end,indices)
                actual_counter[tuple(sorted(indices))] += 1
                normal = (ps[1]-ps[0]).cross(ps[2]-ps[0])
                assert normal.length > 1e-13, ("zero-area native triangle",end)
                alignment = normal.normalized().x*end
                minimum_alignment = min(minimum_alignment,alignment)
                assert alignment > .9999, ("inward or tilted badge triangle",end,alignment)
                triangles_2d.append(tuple((p.y,p.z) for p in ps))
                all_points.extend(ps)
            # A complete one-to-one triangle multiset rules out hidden duplicate
            # legacy bars, overlapping old paint or arbitrary retriangulated fills.
            assert actual_counter == reference_counter, {
                "end":end,
                "missing":len(reference_counter-actual_counter),
                "extra":len(actual_counter-reference_counter),
            }
            lo_y,hi_y = min(p.y for p in all_points),max(p.y for p in all_points)
            lo_z,hi_z = min(p.z for p in all_points),max(p.z for p in all_points)
            x_error = max(abs(p.x-end*FRONT_X_M) for p in all_points)
            assert x_error < TOLERANCE_M
            assert abs(hi_y-lo_y-.416) < TOLERANCE_M
            assert abs(hi_z-lo_z-.4784) < TOLERANCE_M
            assert abs((lo_y+hi_y)/2) < TOLERANCE_M
            assert abs((lo_z+hi_z)/2-2.16) < TOLERANCE_M
            actual_area = sum(abs(_cross(a,b,c))/2 for a,b,c in triangles_2d)
            assert abs(actual_area-expected_area) < 2e-7, (end,actual_area,expected_area)
            grid_checked, grid_skipped = 0, 0
            scale = emblem.WIDTH_M/200
            for u in range(-102,103,4):
                for v in range(-112,123,4):
                    point = ((u+.213)*scale,emblem.CENTER_Z-(v+.317-5)*scale)
                    # Points closer than float32 tolerance to a polygon edge are
                    # not reliable binary witnesses. Triangle matching above
                    # remains strict and covers the exact boundary geometry.
                    if min(_edge_distance(point,a,b) for a,b in edge_pairs) < TOLERANCE_M:
                        grid_skipped += 1
                        continue
                    expected_fill = any(_inside(point,contour) for contour in contours)
                    assert _covered(point,triangles_2d) == expected_fill, ("native union mismatch",end,point)
                    grid_checked += 1
            witnesses = []
            for name,y,z,painted in (
                ("top_bump",0,2.393,True),
                ("arc_right",.18,2.17,True),
                ("rounded_rail_head",0,2.18,True),
                ("narrow_rail_web",0,2.08,True),
                ("flared_rail_base",0,1.926,True),
                ("open_arc_interior",0,2.30,False),
                ("old_T_right_bar_removed",.09,2.19,False),
                ("old_T_left_bar_removed",-.09,2.19,False),
                ("old_base_right_bar_removed",.08,1.99,False),
                ("old_base_left_bar_removed",-.08,1.99,False),
                ("open_arc_lower_right_gap",.05,1.99,False),
                ("open_arc_lower_left_gap",-.05,1.99,False),
            ):
                actual_fill = _covered((y,z),triangles_2d)
                assert actual_fill == painted, (end,name,actual_fill,painted)
                witnesses.append({"name":name,"y":y,"z":z,"painted":actual_fill})
            report["ends"].append({
                "end":end,"triangles":len(ps_by_face),
                "exact_reference_triangle_multiset":True,
                "max_reference_vertex_error_m":maximum_error,
                "minimum_outward_normal_alignment":minimum_alignment,
                "bbox_yz":[lo_y,hi_y,lo_z,hi_z],
                "width_m":hi_y-lo_y,"height_m":hi_z-lo_z,
                "max_x_plane_error_m":x_error,
                "painted_area_m2":actual_area,"reference_area_m2":expected_area,
                "union_grid_points_checked":grid_checked,
                "near_boundary_grid_points_skipped":grid_skipped,
                "positive_negative_and_legacy_witnesses":witnesses,
            })
        report["status"] = "PASS"
    except Exception as exc:
        report.update(status="FAIL",error=repr(exc))
        path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        raise
    path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"V14 EMBLEM NATIVE PASS: {report['actual_total_triangles']} yellow triangles, two forward faces, SVG correspondence and open arc/legacy-bar witnesses",flush=True)
    return report
