"""FXN5C v0.7 side-cab correction, independently callable after v0.6.cabs().

Evidence: TrainNets yl03 (0026/0027) and Commons ref_05/ref_06 (0050/0051).
Those production-car photos agree on two separate side windows followed by a
narrow, windowless access door.  The supplied red 0001 drawing corroborates that
layout, but is not used for production ventilation or livery. All dimensions,
hidden door hardware and the shallow foot-pocket depth are visual estimates.

The caller must cut the eight shell apertures using side_window_loop(), before
calling rebuild_side_cab(). This module does not touch the hull, front glazing,
lamps, coupling pipes, interior, or any approved running-gear meshes.
"""
import math
import bpy

from geometry_v04 import rounded_rect


DOOR_CENTRE = 8.15
DOOR_WIDTH = .52
DOOR_Z = 2.86
DOOR_HEIGHT = 1.98


def _cut_corners(corners, cut=.026):
    """Small straight clipped corners; retain the long, visibly straight edges."""
    result = []
    for i, point in enumerate(corners):
        for neighbour in (corners[i - 1], corners[(i + 1) % len(corners)]):
            dx = neighbour[0] - point[0]
            dz = neighbour[1] - point[1]
            length = math.hypot(dx, dz)
            distance = min(cut, length * .20)
            result.append((point[0] + dx * distance / length,
                           point[1] + dz * distance / length))
    return result


def side_window_loop(end, which, expand=0):
    """Return an X-Z pane/aperture loop; positive expand grows the opening.

    Both end values use the exact same mirrored template. Keep this helper as
    the single source for the shell cutter, pane and surrounding rubber frames.
    """
    if end not in (-1, 1):
        raise ValueError("end must be -1 or 1")
    if which == "front":
        # The nose-side edge leans inward at its top. Its rear edge is upright;
        # unlike v0.6 this is not a second rounded rectangular side window.
        corners = [(9.405 - expand, 2.945 - expand),
                   (9.840 + expand, 2.945 - expand),
                   (9.655 + expand, 3.695 + expand),
                   (9.405 - expand, 3.695 + expand)]
        loop = _cut_corners(corners)
    elif which == "rear":
        loop = rounded_rect(8.91, 3.32, .50 + 2 * expand,
                            .75 + 2 * expand, .052 + expand, n=4)
    else:
        raise ValueError("which must be 'front' or 'rear'")
    loop = [(end * x, z) for x, z in loop]
    return list(reversed(loop)) if end < 0 else loop


def rebuild_side_cab(builder):
    """Replace only the old exterior side-cab assemblies, once per near/mid LOD."""
    obsolete = ("side_window", "cab_side_glass", "cab_door",
                "continuous_door_grab", "door_grab_foot", "door_hinge_barrel",
                "door_latch_plate", "door_handle", "door_rail", "cab_step",
                "step_side_bracket", "step_open_grating")
    for obj in list(bpy.context.scene.objects):
        if obj.get("side_cab_v07") or obj.name.startswith(obsolete):
            bpy.data.objects.remove(obj, do_unlink=True)
    if builder.lod >= 2:
        return
    before = set(bpy.context.scene.objects)

    def surface(side, offset):
        return lambda x, z: (x, side * (builder.side_y(x, z) + offset), z)

    def point(side, x, z, offset=0):
        return surface(side, offset)(x, z)

    def flag(obj, name):
        obj["detail_v07_component"] = name
        return obj

    def sheet_box(name, side, x, z, width, height, depth, offset, mat):
        # All attachment vertices sample the side map, including cab taper.
        loop = [(x - width / 2, z - height / 2),
                (x + width / 2, z - height / 2),
                (x + width / 2, z + height / 2),
                (x - width / 2, z + height / 2)]
        return builder.sheet(name, loop, surface(side, offset), mat,
                             depth, (0, side, 0))

    for end in (-1, 1):
        for side in (-1, 1):
            for which in ("front", "rear"):
                loop = lambda e=0, w=which: side_window_loop(end, w, e)
                builder.rim("side_cab_window_frame_v07", loop(.040), loop(.015),
                            surface(side, .017), "graphite", .022, (0, side, 0))
                builder.rim("side_cab_window_rubber_v07", loop(.016), loop(-.002),
                            surface(side, .030), "black", .018, (0, side, 0))
                pane = builder.glass("side_cab_glass_v07", loop(.001),
                                     surface(side, .007), (0, side, 0))
                flag(pane, "trapezoid_side_pane" if which == "front"
                     else "rectangular_side_pane")
                if which == "rear" and builder.lod == 0:
                    # A slender sliding-window return at the lower seal, not a
                    # thick external box or an additional transparent surface.
                    sheet_box("side_window_slider_track_v07", side, end * 8.91,
                              2.967, .424, .018, .012, .034, "spring_steel")
                    sheet_box("side_window_pull_v07", side, end * 8.73,
                              3.035, .033, .092, .014, .024, "black")

            x = end * DOOR_CENTRE
            outer = rounded_rect(x, DOOR_Z, DOOR_WIDTH, DOOR_HEIGHT, .052, n=4)
            inner = rounded_rect(x, DOOR_Z, DOOR_WIDTH - .018,
                                 DOOR_HEIGHT - .018, .044, n=4)
            builder.rim("side_access_door_gap_v07", outer, inner,
                        surface(side, .011), "black", .008, (0, side, 0))
            skin = builder.painted_panel("side_access_door_skin_v07", side, x,
                                         DOOR_Z, DOOR_WIDTH - .024,
                                         DOOR_HEIGHT - .024, .006, .041)
            flag(skin, "side_cab_door")
            # The lower oval is a recessed foot pocket below the closed door;
            # no false transparent pane and no extra cab aperture are created.
            pocket = rounded_rect(x, 1.715, .37, .15, .065, n=4)
            builder.sheet("side_foot_pocket_dark_v07", pocket,
                          surface(side, .007), "black", axis=(0, side, 0))
            builder.rim("side_foot_pocket_lip_v07", pocket,
                        rounded_rect(x, 1.715, .338, .12, .050, n=4),
                        surface(side, .026), "graphite", .022, (0, side, 0))
            sheet_box("side_foot_pocket_tread_v07", side, x, 1.666,
                      .286, .023, .060, .038, "spring_steel")

            # Two continuous grabs flank the separate door, with feet attached
            # to the body; none pass through the rear window.
            for dx in (-.37, .37):
                rail_x = x + dx
                builder.tube("side_access_grab_v07",
                             [point(side, rail_x, 1.66, .007),
                              point(side, rail_x, 1.70, .065),
                              point(side, rail_x, 3.62, .065),
                              point(side, rail_x, 3.66, .007)],
                             .014, "metal", sides=8 if builder.lod == 0 else 6)
                if builder.lod == 0:
                    for z in (1.66, 3.66):
                        builder.cyl("side_access_grab_foot_v07",
                                    point(side, rail_x, z, .009),
                                    .025, .015, "metal", "Y")

            for z in (2.25, 2.89):
                handle_x = x - end * .160
                sheet_box("side_access_lock_plate_v07", side, handle_x, z,
                          .054, .112, .014, .025, "metal")
                builder.rod("side_access_lock_handle_v07",
                            point(side, handle_x, z + .018, .055),
                            point(side, handle_x + end * .120, z + .018, .055),
                            .010, "metal")
                if builder.lod == 0:
                    hinge_x = x + end * .249
                    sheet_box("side_access_hinge_leaf_v07", side, hinge_x, z,
                              .032, .092, .012, .022, "blue")
                    builder.cyl("side_access_hinge_pin_v07",
                                point(side, hinge_x, z, .027),
                                .010, .10, "spring_steel", "Z")

            # Fixed upper ladder, narrowly aligned with the doorway. Lower
            # bogie equipment stays untouched and is not joined to this ladder.
            for z in (1.16, 1.43):
                for dx in (-.19, .19):
                    sheet_box("side_door_step_bracket_v07", side, x + dx, z,
                              .025, .058, .25, .035, "graphite")
                count = 6 if builder.lod == 0 else 3
                for i in range(count):
                    off = -.20 + i * .23 / (count - 1)
                    sheet_box("side_door_step_grating_v07", side, x, z + .033,
                              .402, .018, .013, off, "spring_steel")

    for obj in set(bpy.context.scene.objects) - before:
        obj["side_cab_v07"] = True
