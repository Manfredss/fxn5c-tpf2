"""Low, continuous FXN5C cab-roof hoods for v13.

Photo basis (not factory dimensions): 0050 cab-roof crop and the original
0063 high view.  Both show the sequence: short front brow -> low rectangular
AC module -> short falling rear transition -> machine-room roof.  In
particular, this replaces the four thick v07 front/rear fairing walls with one
continuous, folded hood at each cab.  The AC hardware remains the caller's
responsibility and sits in the deliberately oversize central pocket.
"""
import bpy
import math
from mathutils import Vector

from geometry_v02 import Builder as BaseBody


# Absolute-X stations for one end.  The same hood form is used at +/- X only;
# the caller retains the separately authored I (+X) and II (-X) transitions.
# Values are photo-estimated working coordinates, not measured vehicle data.
# (x, lower_half_width, shoulder_z, crown_half_width, crown_z)
HOOD_STATIONS = (
    (7.40, 1.235, 4.405, 1.125, 4.490),  # rear fall into machine-room roof
    (7.66, 1.235, 4.405, 1.035, 4.585),
    (8.10, 1.235, 4.405, 0.955, 4.650),  # rear edge of AC recess
    (9.11, 1.235, 4.405, 0.900, 4.705),  # short brow behind the falling front face
    (9.36, 1.235, 4.405, 0.900, 4.705),
    (9.50, 1.225, 4.410, 0.925, 4.665),
    (10.02, 1.042, 4.460, 1.020, 4.484), # short front brow return
)

# Existing v07 AC case is 0.80 x 1.14 m about |x|=8.67.  This is deliberately
# larger in X/Y and cuts down to the low shell, preserving its open equipment
# bay rather than merely making a lid-shaped hole above the AC fan.
AC_POCKET_X = (8.14, 9.18)
AC_POCKET_HALF_Y = 1.130
AC_POCKET_Z_FLOOR = 4.300


def _tag(obj, component, end=None):
    obj["detail_v13_component"] = component
    if end is not None:
        obj["roof_end"] = "I" if end > 0 else "II"
    return obj


def _shell_top(builder, x, y):
    """Return the current upper-body support under the hood without guessing it.

    v13 may alter the nose, but the integration contract promises old side_y
    for |x| <= 9.4.  Binary-searching side_y makes the outer shoulder sit on
    whatever shell the caller supplied rather than inserting blue geometry.
    """
    if abs(y) <= builder.side_y(x, 4.48):
        return 4.48
    low, high = 3.95, 4.48
    for _ in range(28):
        mid = (low + high) / 2
        if builder.side_y(x, mid) > abs(y):
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _make_end_hood(builder, end):
    """Create one closed, planar-folded hood, then open its AC pocket."""
    # Three segments per shoulder preserve the intended trapezoid folds while
    # avoiding the v07 visual of four tall rails surrounding the AC module.
    shoulder_steps = 8 if builder.lod==0 else 4
    rows = []
    stations=[]
    for a,c in zip(HOOD_STATIONS,HOOD_STATIONS[1:]):
        steps=max(1,math.ceil((c[0]-a[0])/(.045 if builder.lod==0 else .09)))
        stations.extend(tuple(a[j]+(c[j]-a[j])*i/steps for j in range(5)) for i in range(steps))
    stations.append(HOOD_STATIONS[-1])
    for x, lower, base, upper, top in stations:
        ys = [-lower + i * (lower - upper) / shoulder_steps
              for i in range(shoulder_steps + 1)]
        ys += [0.0]
        ys += [upper + i * (lower - upper) / shoulder_steps
               for i in range(shoulder_steps + 1)]
        rows.append((x, lower, base, upper, top, ys))

    columns = len(rows[0][5])
    top_vertices = []
    bottom_vertices = []
    for x, lower, base, upper, crown, ys in rows:
        for y in ys:
            # Plane crown plus straight shoulders: no barrel/arc profile.
            nominal = crown - max(0.0, abs(y) - upper) * (crown - base) / (lower - upper)
            support = _shell_top(builder, end * x, y)
            z = max(nominal, support + .008)
            if abs(abs(y) - lower) < 1e-7:
                z = support + .008
            top_vertices.append((end * x, y, z))
            bottom_vertices.append((end * x, y, support - .010))

    count = len(top_vertices)
    vertices = top_vertices + bottom_vertices
    faces = []
    for row in range(len(rows) - 1):
        for col in range(columns - 1):
            a = row * columns + col
            c = a + columns
            faces += [(a, c, c + 1), (a, c + 1, a + 1),
                      (count + a, count + c + 1, count + c),
                      (count + a, count + a + 1, count + c + 1)]

    edge = list(range(columns))
    edge += [r * columns + columns - 1 for r in range(1, len(rows))]
    edge += list(range(count - 2, count - columns - 1, -1))
    edge += [r * columns for r in range(len(rows) - 2, 0, -1)]
    for a, c in zip(edge, edge[1:] + edge[:1]):
        faces.append((a, c, count + c, count + a))

    hood = builder.poly("cab_continuous_low_hood_v13", vertices, faces, "roof", solid=True)
    _tag(hood, "continuous_cab_hood", end)
    hood["photo_estimated_station_range"] = (end * 7.40, end * 10.02)
    hood["ac_pocket_clearance"] = (end * AC_POCKET_X[0], end * AC_POCKET_X[1], AC_POCKET_HALF_Y)

    # A genuine opening is essential: retained AC hardware must remain visible,
    # and a solid flat cap would merely hide the old problem.
    centre = end * (AC_POCKET_X[0] + AC_POCKET_X[1]) / 2
    length = AC_POCKET_X[1] - AC_POCKET_X[0]
    cutter_top = 5.10
    cutter = BaseBody.box(builder, "cab_ac_pocket_cutter_v13",
                           (centre, 0.0, (AC_POCKET_Z_FLOOR + cutter_top) / 2),
                           (length, AC_POCKET_HALF_Y * 2,
                            cutter_top - AC_POCKET_Z_FLOOR), "black")
    builder.cut(hood, cutter)
    if builder.lod == 0:
        builder.bevel(hood, .004, 1)
    for face in hood.data.polygons:
        face.use_smooth=False
    return hood


def replace_cab_hoods(builder):
    """Remove only obsolete v07 cab fairings/antennae and add the two v13 hoods.

    Central decks, cross vents, both retained AC hardware assemblies and all
    other roof parts are intentionally untouched.  Call after that hardware has
    been created so its AC cases occupy the two open pockets.
    """
    obsolete_names = ("cab_front_trapezoid_fairing_v07", "cab_rear_trapezoid_fairing_v07", "cab_continuous_low_hood_v13",
                      "antenna_hood_mount_v13", "radio_aerial_v13",
                      "antenna_hood_mount_v07", "radio_aerial_v07")
    for obj in list(bpy.context.scene.objects):
        if (obj.get("detail_v07_component") == "cab_trapezoid_fairing" or
                obj.name.startswith(obsolete_names)):
            bpy.data.objects.remove(obj, do_unlink=True)
    hoods = [_make_end_hood(builder, end) for end in (-1, 1)]
    if builder.lod==0:
        for end in (-1,1):
            _tag(builder.cyl('antenna_hood_mount_v13',(end*9.25,.60,4.715),.045,.020,'graphite','Z'),'hood_aerial_mount',end)
            _tag(builder.rod('radio_aerial_v13',(end*9.25,.60,4.724),(end*9.25,.60,4.840),.008,'black'),'hood_radio_aerial',end)
    # Re-seat inherited lifting eyes and feet on the changed rear ramp. Leaving
    # their v07 vertical offset would suspend them 23 mm above the new sheet.
    for obj in bpy.context.scene.objects:
        if not obj.name.startswith(('roof_lifting_eye_v06','roof_eye_pad_v06')) or obj.get('reseated_hood_v13'):
            continue
        pts=[obj.matrix_world@v.co for v in obj.data.vertices]
        if abs(abs(sum(p.x for p in pts)/len(pts))-8.0)>.03:continue
        inv=obj.matrix_world.inverted()
        for vertex in obj.data.vertices:
            p=obj.matrix_world@vertex.co
            crown=4.585+(abs(p.x)-7.66)*(.065/.44)
            p.z+=crown+.001-4.6581
            vertex.co=inv@p
        obj['reseated_hood_v13']=True
    bpy.context.scene["detail_v13_continuous_cab_hoods"] = len(hoods)
    bpy.context.scene["detail_v13_cab_hood_parameters"] = (
        "stations 7.40..10.02; crown 4.484..4.705; open AC bay 8.14..9.18 x +/-1.130"
    )
    return hoods
