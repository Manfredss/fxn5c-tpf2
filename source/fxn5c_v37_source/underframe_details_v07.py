"""Photo-referenced FXN5C v0.7 reservoir placement and folded pilot returns.

Ref_05/ref_06 show the two transverse reservoirs at the inspection-door end of
the central cabinets, opposite the six large louver banks. The earlier yl02
close-up was taken from the other viewing direction. Preserve the existing
reservoir meshes and move only their explicitly named assembly members.

Ref_06 and TrainNets yl03 show the nose's broad grey side returns sweeping up
to the chassis. The return outline and hidden plate thickness are estimates,
not engineering dimensions. Neither helper edits bogies, wheels, or piping.
"""
import re
import bpy


_RESERVOIR_NAMES = re.compile(
    r"^(air_reservoir|reservoir_domed_end|reservoir_strap|reservoir_drain)(?:\.\d+)?$")
_RESERVOIR_CENTRES = ((-3.27, 3.00), (-2.59, 3.68))


def refine_underframe(builder):
    """Call after inherited underframe(); relocate complete existing reservoirs.

    At the largest retained strap radius (.308), the longitudinal envelopes
    are [2.692, 3.308] and [3.372, 3.988]. These clear the cabinet end at 2.659
    by .033 m and the innermost wheel envelope at 4.275 by .287 m.
    """
    if builder.lod >= 2:
        return
    tags = {"air_reservoir": "relocated_air_reservoir",
            "reservoir_domed_end": "relocated_reservoir_end",
            "reservoir_strap": "relocated_reservoir_strap",
            "reservoir_drain": "relocated_reservoir_drain"}
    counts = dict.fromkeys(tags, 0)
    for obj in list(bpy.context.scene.objects):
        match = _RESERVOIR_NAMES.fullmatch(obj.name)
        if not match:
            continue
        part = match.group(1)
        if obj.get("reservoir_relocated_v07"):
            counts[part] += 1
            continue
        # These cylinders/rods are unparented in geometry_v03. Refuse to move
        # differently owned geometry rather than guessing its local transform.
        if obj.parent is not None:
            raise ValueError(f"Unexpected parent on reservoir member: {obj.name}")
        source, target = min(_RESERVOIR_CENTRES,
                             key=lambda pair: abs(obj.location.x - pair[0]))
        if abs(obj.location.x - source) > .025:
            raise ValueError(f"Unexpected reservoir X origin: {obj.name}")
        obj.location.x += target - source
        obj["detail_v07_component"] = tags[part]
        obj["reservoir_relocated_v07"] = True
        obj["reservoir_original_x"] = source
        obj["reservoir_corrected_x"] = target
        counts[part] += 1
    expected = {"air_reservoir": 2, "reservoir_domed_end": 4,
                "reservoir_strap": 4 if builder.lod == 0 else 0,
                "reservoir_drain": 2 if builder.lod == 0 else 0}
    if counts != expected:
        raise ValueError(f"Incomplete inherited reservoir assemblies: {counts}")


def _folded_corner(builder, end, side):
    """Closed, triangulated sheet joining the side return to the existing nose.

    The three facets are deliberate sheet-metal folds. Avoid a single warped
    n-gon whose triangulation and highlights would vary in the native exporter.
    """
    outer = [(end * 10.90, side * 1.595, 1.57),
             (end * 11.10, side * 1.440, 1.33),
             (end * 11.10, side * 1.400, .48),
             (end * 11.10, side * 1.200, .26),
             (end * 10.91, side * 1.595, .41)]
    inner = [(x, y - side * .024, z) for x, y, z in outer]
    front = [(0, 1, 2), (0, 2, 4), (2, 3, 4)]
    faces = front + [tuple(i + 5 for i in reversed(face)) for face in front]
    faces += [(i, (i + 1) % 5, (i + 1) % 5 + 5, i + 5) for i in range(5)]
    obj = builder.poly("pilot_corner_fold_v07", outer + inner, faces,
                       "graphite", solid=True)
    obj["detail_v07_component"] = "pilot_corner_fold"
    obj["pilot_return_end_v07"] = end
    return obj


def add_pilot_returns(builder, end):
    """Call after inherited coupler(end); complete the grey nose side outline.

    Every added point has |X| >= 9.60: even the nearest upper end is outside
    the outermost wheel's X=9.125 limit. No panel is hung over a wheel or bogie.
    The aft lower edge rises to the beam rather than forming a deep rectangle.
    """
    if end not in (-1, 1):
        raise ValueError("end must be -1 or 1")
    if builder.lod >= 2:
        return
    for obj in list(bpy.context.scene.objects):
        if obj.get("pilot_return_end_v07") == end:
            bpy.data.objects.remove(obj, do_unlink=True)
    outline = [(9.60, 1.57), (10.90, 1.57), (10.91, .41),
               (10.64, .50), (10.10, 1.20), (9.60, 1.34)]
    for side in (-1, 1):
        loop = [(end * x, z) for x, z in outline]
        obj = builder.sheet("pilot_side_return_v07", loop,
                            lambda x, z, s=side: (x, s * 1.595, z),
                            "graphite", .024, (0, side, 0))
        # One narrow edge bevel makes the plate thickness legible without
        # subdividing the large, deliberately planar manufactured surfaces.
        if builder.lod == 0:
            builder.bevel(obj, .004, 1)
        obj["detail_v07_component"] = "pilot_side_return"
        obj["pilot_return_end_v07"] = end
        _folded_corner(builder, end, side)
