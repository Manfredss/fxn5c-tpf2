"""Check reconstructed native FXN5C meshes, not source-only feature metadata.

Run after the exporter/reader has reconstructed opaque ``body``, a separate
``cab_interior`` and 26 ``glazing_*`` objects. Samples are kept strictly inside
the actual angular window polygons rather than an obsolete rectangular grid.
The corner test independently measures geometric normals, hit positions and
exported shading normals; smooth shading alone cannot certify a planar mesh.
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from geometry_v06 import front_loop
from geometry_v14 import ProductionBuilder14 as SilhouetteBuilder
from nose_shell_v14 import corner_point as lower_corner_point, corner_normal as lower_corner_normal
from cab_details_v14 import side_window_loop


def _point(values):
    return [round(float(v), 7) for v in values]


def _scanline(loop, z):
    intersections = []
    for (a, za), (b, zb) in zip(loop, loop[1:] + loop[:1]):
        if (za <= z < zb) or (zb <= z < za):
            intersections.append(a + (b - a) * (z - za) / (zb - za))
    if len(intersections) != 2:
        raise ValueError(f"Expected a convex window section, got {intersections}")
    return min(intersections), max(intersections)


def _internal_grid(loop, horizontal):
    low = min(p[1] for p in loop)
    high = max(p[1] for p in loop)
    for t in (.18, .39, .61, .82):
        z = low + (high - low) * t
        left, right = _scanline(loop, z)
        for fraction in horizontal:
            yield left + (right - left) * fraction, z


def _corner_point(end, side, z, fraction):
    return lower_corner_point(end,side,z,fraction)


def _corner_normal(end, side, z, fraction=.5):
    return lower_corner_normal(end,side,z,fraction)


def audit(root,version="v14"):
    """Validate native LOD0 aperture/land geometry; write PASS or FAIL JSON."""
    output = Path(root) / f"cab_aperture_audit_{version}.json"
    result = {"status": "RUNNING",
              "scope": "reconstructed native opaque mesh and separate glazing; NOT game rendering",
              "window_rays": [], "front_window_grid_rays": [],
              "side_window_grid_rays": [], "corner_lands": [],
              "intentional_sunblind_hits": [],
              "limitations": [
                  "Corner dimensions are photo estimates, not surveyed dimensions.",
                  "The corner test samples exposed low and window-side bands; it does not certify every brow transition.",
                  "Opaque aperture clearance does not prove in-game transparency sorting, reflections or interior lighting.",
                  "Finite ray grids do not certify every point of a frame or seal; photo-estimated attachment depths remain."]}
    try:
        body = bpy.data.objects.get("body")
        if body is None or body.type != "MESH":
            raise AssertionError("The reconstructed native body mesh is required")
        tree = BVHTree.FromPolygons([body.matrix_world @ v.co for v in body.data.vertices],
                                    [list(p.vertices) for p in body.data.polygons])

        def is_sunblind_face(face, direction):
            # v08 deliberately lowers the interior blinds into the upper glazing
            # band. Accept ONLY triangles wholly on that known rearward plane,
            # with the cabin-lining material. An arbitrary window obstruction,
            # even behind the glass, must still fail. The first hit also proves
            # the interval from outside the shell to this blind is unobstructed.
            if abs(direction.x) < .99:
                return False
            poly = body.data.polygons[face]
            if body.data.materials[poly.material_index].name != "/vehicle/train/fxn5c/cab_lining":
                return False
            end = -1 if direction.x > 0 else 1
            for index in poly.vertices:
                p = body.matrix_world @ body.data.vertices[index].co
                if not (3.6674 <= p.z <= 3.8726 and .1149 <= abs(p.y) <= 1.0651):
                    return False
                if abs(p.x - end * (SilhouetteBuilder.front_x(p.z) - .055)) > .0001:
                    return False
            return True

        def clear_ray(surface, direction, destination, location):
            direction = Vector(direction)
            origin = Vector(surface) - direction * .40
            hit, normal, face, distance = tree.ray_cast(origin, direction, .68)
            item = {"window": location, "origin": _point(origin),
                    "direction": _point(direction), "ray_length_m": .68,
                    "clear_through_shell": hit is None}
            if hit is not None:
                item.update({"hit": _point(hit), "distance_m": round(distance, 7),
                             "geometric_normal": _point(normal), "face": face})
                if is_sunblind_face(face, direction):
                    item.update({"clear_through_shell": True,
                                 "intentional_interior_occlusion": "sunblind, 55 mm behind shell"})
                    result["intentional_sunblind_hits"].append(item.copy())
            result[destination].append(item)
            if not item["clear_through_shell"]:
                raise AssertionError(f"Opaque obstruction in {location}: {item}")

        for end in (-1, 1):
            for side in (-1, 1):
                front = front_loop(side)
                y = sum(p[0] for p in front) / len(front)
                z = sum(p[1] for p in front) / len(front)
                location = f"front/end{end}/side{side}"
                clear_ray((end * SilhouetteBuilder.front_x(z), y, z), (-end, 0, 0),
                          "window_rays", location)
                for y, z in _internal_grid(front, (.14, .32, .50, .68, .86)):
                    clear_ray((end * SilhouetteBuilder.front_x(z), y, z), (-end, 0, 0),
                              "front_window_grid_rays", location)
                for which in ("front", "rear"):
                    loop = side_window_loop(end, which)
                    x = sum(p[0] for p in loop) / len(loop)
                    z = sum(p[1] for p in loop) / len(loop)
                    location = f"side/end{end}/side{side}/{which}"
                    clear_ray((x, side * SilhouetteBuilder.side_y(x, z), z), (0, -side, 0),
                              "window_rays", location)
                    for x, z in _internal_grid(loop, (.22, .50, .78)):
                        clear_ray((x, side * SilhouetteBuilder.side_y(x, z), z), (0, -side, 0),
                                  "side_window_grid_rays", location)

        panes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.startswith("glazing_")]
        if len(panes) != 26:
            raise AssertionError(f"Expected 26 independent glass objects, found {len(panes)}")
        result["separate_transparent_panes"] = len(panes)
        classes = {"angular_front_panes": [], "trapezoid_side_panes": [],
                   "rectangular_side_panes": []}
        occupied = set()
        for obj in panes:
            # Native export repeats triangle vertices and may split normals/UVs.
            # Count the geometric silhouette positions, not the packed vertices.
            points = {tuple(round(v, 5) for v in obj.matrix_world @ vertex.co)
                      for vertex in obj.data.vertices}
            centre = tuple(sum(p[i] for p in points) / len(points) for i in range(3))
            if not 3.05 < centre[2] < 3.65:
                continue  # Twelve inner lamp lenses plus two shared headlamp covers.
            if abs(centre[0]) > 10.35 and abs(centre[1]) < 1.30:
                kind, expected = "angular_front_panes", 8
            elif 9.80 < abs(centre[0]) < 10.30 and abs(centre[1]) > 1.30:
                kind, expected = "trapezoid_side_panes", 24
            elif 9.20 < abs(centre[0]) < 9.75 and abs(centre[1]) > 1.30:
                kind, expected = "rectangular_side_panes", 36
            else:
                raise AssertionError(f"Unclassified cab glass {obj.name}: {centre}")
            if len(points) != expected:
                raise AssertionError(f"{obj.name}: {kind} has {len(points)} unique vertices, expected {expected}")
            if kind != 'angular_front_panes':
                plane_error=max(abs(abs(p[1])-1.657) for p in points)
                assert plane_error<2e-5,('Side glass must be planar',obj.name,plane_error)
            if kind=='rectangular_side_panes':
                assert abs(abs(centre[0])-9.565)<2e-5,('Rear pane misses forward photo anchor',obj.name,centre)
            if kind=='trapezoid_side_panes':
                gaps=[]
                for x,y,z in points:
                    if 3.10<z<3.16:
                        face_x=11.04-.64*(z-2.55)/1.47
                        half_width=1.48-.05*(z-2.55)/1.47
                        gaps.append(face_x-.30*(1.65-half_width)-abs(x))
                assert gaps and .32<min(gaps)<.40,('Lower A-pillar gap misses photo-fit envelope',obj.name,gaps)
                result.setdefault('lower_a_pillar_glass_gaps',[]).append({'mesh':obj.name,'gap_m':min(gaps),'photo_fit_envelope_m':[.32,.40]})
            slot = (kind, 1 if centre[0] > 0 else -1, 1 if centre[1] > 0 else -1)
            if slot in occupied:
                raise AssertionError(f"Duplicate glass occupying {slot}")
            occupied.add(slot)
            classes[kind].append({"mesh": obj.name, "unique_vertices": len(points),
                                  "centre": _point(centre)})
        if any(len(group) != 4 for group in classes.values()):
            raise AssertionError({kind: len(group) for kind, group in classes.items()})
        result.update(classes)
        interior = bpy.data.objects.get("cab_interior")
        if interior is None or len(interior.data.polygons) <= 100:
            raise AssertionError("The independent cab interior is absent or empty")
        result["interior_mesh_present"] = True

        # Each nose-side land must be a genuinely distinct opaque surface. A
        # successful ray alone would also hit a sharp wedge; require the correct
        # surface position AND oblique geometric normal at three transverse points.
        for end in (-1, 1):
            for side in (-1, 1):
                land = {"end": end, "side": side, "samples": []}
                for z in (1.88, 2.45, 3.50):
                    hits = []
                    for fraction in (.18, .50, .82):
                        expected_normal = _corner_normal(end,side,z,fraction)
                        expected_point = _corner_point(end, side, z, fraction)
                        origin = expected_point + expected_normal * .18
                        hit, normal, face, distance = tree.ray_cast(origin, -expected_normal, .25)
                        if hit is None:
                            raise AssertionError(f"Missing corner land end={end} side={side} z={z}")
                        error = (hit - expected_point).length
                        alignment = normal.dot(expected_normal)
                        sample = {"z": z, "transverse_fraction": fraction,
                                  "expected_surface": _point(expected_point), "native_hit": _point(hit),
                                  "surface_error_m": round(error, 7),
                                  "distance_m": round(distance, 7), "face": face,
                                  "geometric_normal": _point(normal),
                                  "expected_normal": _point(expected_normal),
                                  "normal_dot_expected": round(alignment, 7)}
                        land["samples"].append(sample)
                        if error > .015 or abs(distance - .18) > .015 or alignment < .995:
                            raise AssertionError(f"Corner land position/normal mismatch: {sample}")
                        hits.append(hit)
                    span = (hits[-1] - hits[0]).length
                    expected_span=(_corner_point(end,side,z,.82)-_corner_point(end,side,z,.18)).length
                    if abs(span-expected_span)>.006:
                        raise AssertionError(f"Corner land is not a distinct finite-width face: {span}")
                land["status"] = "PASS"
                result["corner_lands"].append(land)
        # Independent analytic-plane acceptance, across multiple heights AND
        # widths. This fails a twisted quad even if its helper/ray tests agree.
        result['planar_windshield_chamfers']=[]
        slope=.30
        for end in (-1,1):
            for side in (-1,1):
                n=Vector((end,side*slope,(.64+slope*.05)/1.47)).normalized()
                anchor=Vector((end*11.04,side*1.48,2.55))
                samples=[]
                for z in (2.70,3.05,3.45,3.85):
                    for f in (.20,.5,.80):
                        p=lower_corner_point(end,side,z,f)
                        hit,normal,face,distance=tree.ray_cast(p+n*.08,-n,.12)
                        assert hit is not None,('Missing planar chamfer',end,side,z,f)
                        error=abs((hit-anchor).dot(n))
                        assert error<.00003 and normal.dot(n)>.99999,(error,normal.dot(n))
                        polygon=body.data.polygons[face]
                        shading_alignment=min(body.data.corner_normals[i].vector.dot(n) for i in polygon.loop_indices)
                        assert shading_alignment>.99999,('Non-planar exported shading normal',shading_alignment)
                        samples.append({'z':z,'fraction':f,'plane_error_m':error,'normal_alignment':normal.dot(n),'shading_normal_alignment':shading_alignment})
                result['planar_windshield_chamfers'].append({'end':end,'side':side,'samples':samples})
        # The lamp-level kink separates two independently planar lower corner
        # bands. Do not merely compare the ray hit with the meshing helper:
        # that would accept the previous twisted quad by construction.
        result['planar_lower_nose_bands']=[]
        crease_z=2.285
        for end in (-1,1):
            for side in (-1,1):
                anchor=Vector((end*11.04,side*1.48,crease_z))
                for band,zs,beta in (
                    ('lower_flared_chamfer',(1.84,2.20),-slope*.18/(crease_z-1.58)),
                    # Avoid warning lettering at 2.378/2.492 and lightning at
                    # 2.442: those intentionally sit just proud of the shell.
                    ('upper_vertical_land',(2.325,2.525),0.0)):
                    n=Vector((end,side*slope,beta)).normalized()
                    samples=[]
                    for z in zs:
                        # Stay outside the lamp bores and forward-facing rings.
                        for f in (.18,.50,.82):
                            p=lower_corner_point(end,side,z,f)
                            hit,normal,face,distance=tree.ray_cast(p+n*.08,-n,.12)
                            assert hit is not None,('Missing lower planar band',end,side,band,z,f)
                            error=abs((hit-anchor).dot(n))
                            assert error<.00003 and normal.dot(n)>.99999,(band,error,normal.dot(n))
                            shading_alignment=min(body.data.corner_normals[i].vector.dot(n)
                                                  for i in body.data.polygons[face].loop_indices)
                            assert shading_alignment>.99999,('False lower-nose shading',band,shading_alignment)
                            samples.append({'z':z,'fraction':f,'plane_error_m':error,
                                            'normal_alignment':normal.dot(n),'shading_normal_alignment':shading_alignment})
                    result['planar_lower_nose_bands'].append({'end':end,'side':side,'band':band,'samples':samples})
        result['lower_nose_crease']={'z_m':crease_z,'front_half_at_crease_m':1.48,
                                    'lower_vs_upper_normal_angle_degrees':math.degrees(math.atan(
                                        slope*.18/(crease_z-1.58)/math.sqrt(1+slope*slope))),
                                    'dimensions_are_photo_estimates':True}
        result['side_window_layout']={'rear_glass_centre_x_m':9.565,'glass_height_m':.630,
            'glass_top_z_m':3.720,'front_lower_glass_width_m':.370,'rear_glass_width_m':.500,
            'frame_to_frame_gap_m':.115,'photo_anchor_forward_shift_m':.180,
            'door_centre_abs_x_m':8.830,'dimensions_are_photo_estimates':True}
        result['flat_sidewall_shading']=[]
        for end in (-1,1):
            for side in (-1,1):
                expected=Vector((0,side,0))
                for x,z in ((10.40,3.02),(10.27,3.80),(9.70,3.83)):
                    hit,normal,face,distance=tree.ray_cast(Vector((end*x,side*1.9,z)),-expected,.3)
                    assert hit is not None and abs(abs(hit.y)-1.65)<.00003
                    alignment=min(body.data.corner_normals[i].vector.dot(expected) for i in body.data.polygons[face].loop_indices)
                    assert normal.dot(expected)>.99999 and alignment>.99999,('Twisted or falsely shaded sidewall',normal,alignment)
                    result['flat_sidewall_shading'].append({'end':end,'side':side,'x':x,'z':z,'shading_alignment':alignment})
        result.update({"status": "PASS", "corner_land_count": 4,
                       "front_grid_ray_count": len(result["front_window_grid_rays"]),
                       "side_grid_ray_count": len(result["side_window_grid_rays"]),
                       "centre_ray_count": len(result["window_rays"]),
                       "corner_surface_ray_count": sum(len(p["samples"]) for p in result["corner_lands"])})
    except Exception as error:
        result.update({"status": "FAIL", "error": f"{type(error).__name__}: {error}"})
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"{version.upper()} NATIVE CAB PASS: 12 centres, 80 front-grid + 96 side-grid rays, "
          "12 pane silhouettes, 36 corner-surface rays", flush=True)
    return result
