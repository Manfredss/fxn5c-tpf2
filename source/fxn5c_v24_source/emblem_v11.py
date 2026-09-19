"""Thin, SVG-derived China Railways emblems for the FXN5C cab ends.

The bundled public-domain-labelled reference is a TB1838-87-based public
redrawing, not factory CAD. See assets/China_Railways_SOURCE.md. The two simple,
closed subpaths are triangulated separately: the open arc is NOT a filled disc.
Only marking objects are replaced; no shell, lamp, glazing or coupler is edited.
"""
from functools import lru_cache
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SVG_PATH = Path(__file__).parent / "assets" / "China_Railways.svg"
WIDTH_M = 0.416
HEIGHT_M = WIDTH_M * 230.0 / 200.0
CENTER_Z = 2.16
SURFACE_OFFSET_M = 0.0015
OLD_PREFIXES = ("painted_railway_emblem", "painted_emblem_", "railway_emblem", "emblem_")
CONTOUR_NAMES = ("open_arc", "rail_section")
TOKEN_RE = re.compile(r"[MmLlHhVvAaZz]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?")


def _arc_points(start, values, relative, chord_error):
    """SVG endpoint arcs, following W3C SVG implementation notes B.2.4/5.

    Returns samples after start, including the exact endpoint. Sampling also
    includes axis extrema, keeping the overall bounds independent of LOD.
    """
    rx, ry, rotation, large_arc, sweep, x2, y2 = values
    if large_arc not in (0, 1) or sweep not in (0, 1):
        raise ValueError("SVG arc flags must be 0 or 1")
    x1, y1 = start
    if relative:
        x2 += x1
        y2 += y1
    end = (x2, y2)
    if math.dist(start, end) < 1e-10:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return [end]
    phi = math.radians(rotation % 360)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = cp * dx + sp * dy, -sp * dx + cp * dy
    correction = xp * xp / (rx * rx) + yp * yp / (ry * ry)
    if correction > 1:
        rx *= math.sqrt(correction)
        ry *= math.sqrt(correction)
    denominator = rx * rx * yp * yp + ry * ry * xp * xp
    numerator = rx * rx * ry * ry - denominator
    sign = -1 if large_arc == sweep else 1
    factor = sign * math.sqrt(max(0.0, numerator / denominator))
    cxp, cyp = factor * rx * yp / ry, -factor * ry * xp / rx
    cx = cp * cxp - sp * cyp + (x1 + x2) / 2
    cy = sp * cxp + cp * cyp + (y1 + y2) / 2
    ux, uy = (xp - cxp) / rx, (yp - cyp) / ry
    vx, vy = (-xp - cxp) / rx, (-yp - cyp) / ry
    theta = math.atan2(uy, ux)
    delta = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    if not sweep and delta > 0:
        delta -= math.tau
    elif sweep and delta < 0:
        delta += math.tau
    angle_step = 2 * math.acos(max(-1.0, 1 - chord_error / max(rx, ry)))
    count = max(1, math.ceil(abs(delta) / min(math.pi / 12, angle_step)))
    fractions = {i / count for i in range(1, count + 1)}
    x_extreme = math.atan2(-ry * sp, rx * cp)
    y_extreme = math.atan2(ry * cp, rx * sp)
    for extreme in (x_extreme, x_extreme + math.pi, y_extreme, y_extreme + math.pi):
        for winding in range(-2, 3):
            fraction = (extreme + winding * math.tau - theta) / delta
            if 1e-10 < fraction < 1 - 1e-10:
                fractions.add(fraction)
    out = []
    for fraction in sorted(fractions):
        angle = theta + fraction * delta
        out.append((cx + cp * rx * math.cos(angle) - sp * ry * math.sin(angle),
                    cy + sp * rx * math.cos(angle) + cp * ry * math.sin(angle)))
    out[-1] = end
    return out


def sample_path(path_data, chord_error=0.018):
    """Sample the M/L/H/V/A/Z subset used by the bundled asset, failing closed."""
    if chord_error <= 0:
        raise ValueError("chord_error must be positive")
    tokens = TOKEN_RE.findall(path_data)
    if TOKEN_RE.sub("", path_data).strip(" ,\t\r\n"):
        raise ValueError("Unsupported SVG path command or token")
    sizes = {"M": 2, "L": 2, "H": 1, "V": 1, "A": 7}
    current = (0.0, 0.0)
    start = None
    contour = []
    contours = []
    command = None
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
        if command is None:
            raise ValueError("SVG path has no command")
        kind, relative = command.upper(), command.islower()
        if kind == "Z":
            if start is None or len(contour) < 3:
                raise ValueError("Invalid SVG close command")
            # Extrema can coincide with a regular angular sample. Remove only
            # numerical duplicates before single-precision Blender conversion.
            contour = [p for j, p in enumerate(contour)
                       if j == 0 or math.dist(p, contour[j-1]) >= 1e-5]
            if math.dist(contour[-1], contour[0]) < 1e-5:
                contour.pop()
            contours.append(tuple(contour))
            current, start, contour, command = start, None, [], None
            continue
        n = sizes[kind]
        if i + n > len(tokens) or any(t.isalpha() for t in tokens[i:i+n]):
            raise ValueError("Incomplete SVG command")
        values = [float(t) for t in tokens[i:i+n]]
        i += n
        if kind in ("M", "L"):
            point = (values[0] + (current[0] if relative else 0),
                     values[1] + (current[1] if relative else 0))
            if kind == "M":
                if contour:
                    raise ValueError("Every emblem subpath must explicitly close")
                start = point
                command = "l" if relative else "L"
            current = point
            contour.append(point)
        elif kind == "H":
            current = (values[0] + (current[0] if relative else 0), current[1])
            contour.append(current)
        elif kind == "V":
            current = (current[0], values[0] + (current[1] if relative else 0))
            contour.append(current)
        elif kind == "A":
            points = _arc_points(current, values, relative, chord_error)
            if points:
                contour.extend(points)
                current = points[-1]
    if contour:
        raise ValueError("Unclosed SVG subpath")
    return tuple(contours)


@lru_cache(maxsize=4)
def sample_contours(lod=0):
    root = ET.parse(SVG_PATH).getroot()
    bounds = tuple(float(v) for v in root.attrib["viewBox"].split())
    if bounds != (-100.0, -110.0, 200.0, 230.0):
        raise ValueError("Unexpected emblem asset viewBox; re-audit dimensions")
    paths = root.findall("{http://www.w3.org/2000/svg}path")
    if len(paths) != 1 or paths[0].get("transform"):
        raise ValueError("Expected one untransformed SVG path")
    contours = sample_path(paths[0].attrib["d"], 0.018 if lod == 0 else 0.08)
    if len(contours) != 2:
        raise ValueError("The open arc and rail must be separate closed subpaths")
    return contours


def tessellate_contour(contour):
    """Return explicit triangles, retaining the concave arc's opening."""
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon
    points = [Vector((x, y, 0)) for x, y in contour]
    indices = {tuple(p): i for i, p in enumerate(points)}
    if len(indices) != len(points):
        raise ValueError("Emblem contour has duplicate vertices")
    # Blender 5.2 returns indices; older mathutils versions returned Vectors.
    triangles = [tuple(p if isinstance(p, int) else indices[tuple(p)] for p in tri)
                 for tri in tessellate_polygon([points])]
    if len(triangles) != len(contour) - 2:
        raise ValueError("Incomplete emblem triangulation")
    return triangles


def make_emblems(b):
    """Replace only emblem objects, using b.poly and the current front surface.

    CENTER_Z is the center of the entire 200-by-230 SVG bounds, not the center
    of the circular part (SVG Y=0). The latter is 5 SVG units above CENTER_Z.
    """
    import bpy
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(OLD_PREFIXES):
            bpy.data.objects.remove(obj, do_unlink=True)
    if b.lod >= 2:
        return []
    scale = WIDTH_M / 200.0
    objects = []
    for end in (-1, 1):
        for label, contour in zip(CONTOUR_NAMES, sample_contours(b.lod)):
            vertices = []
            for u, v in contour:
                z = CENTER_Z - (v - 5.0) * scale
                vertices.append((end * (b.front_x(z) + SURFACE_OFFSET_M), u * scale, z))
            obj = b.poly(f"railway_emblem_v11_{label}_{'p' if end > 0 else 'n'}",
                         vertices, tessellate_contour(contour), "yellow", normal=(end, 0, 0))
            obj["emblem_v11_component"] = label
            obj["emblem_end"] = end
            obj["emblem_width_m"] = WIDTH_M
            obj["emblem_height_m"] = HEIGHT_M
            obj["emblem_center_z_m"] = CENTER_Z
            obj["emblem_surface_offset_m"] = SURFACE_OFFSET_M
            obj["emblem_reference"] = "assets/China_Railways.svg; Commons TB1838-87-based redrawing"
            objects.append(obj)
    return objects
