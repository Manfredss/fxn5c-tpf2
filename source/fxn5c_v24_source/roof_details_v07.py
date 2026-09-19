"""Photo/video-informed FXN5C roof correction, original geometry for v0.7.

Reference: blue 0051, commons/ref_06.jpg, plus the parent agent's inspection
of BV1ehCvBcEVy at 00:42 and 00:44. Dimensions and hidden duct routing are
visual estimates, not factory drawings. The 0001 side illustration is not
used to transplant that variant's side-facing roof fans.
"""
import math
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody
from geometry_v06 import FrontRoofBuilder


# Particle origins just above the two recessed mouths, not a central chimney.
EXHAUST_OUTLETS = ((-1.70, -.76, 4.675), (-1.70, .76, 4.675))
DECK_SECTIONS = ((-1.02, 5.86, 4.640), (5.32, 3.43, 4.650))
DECK_HALF_TOP = 1.04
# End the grey cover above the blue shoulder vents; its lower lip meets the
# existing hull shoulder rather than covering the upper rows of their louvers.
DECK_HALF_BASE = 1.27
DECK_BASE_Z = 4.355


def feature(obj, name):
    obj["detail_v07_component"] = name
    return obj


def small_box(b, name, loc, dims, mat="roof", bevel=0):
    """Small sheet edges use one bevel segment to keep native LOD0 economical."""
    obj = BaseBody.box(b, name, loc, dims, mat)
    if bevel:
        b.bevel(obj, min(bevel, min(dims) * .28), 1)
    return obj


def deck_z(y, top):
    return top - max(0, abs(y) - DECK_HALF_TOP) * (
        top - DECK_BASE_Z) / (DECK_HALF_BASE - DECK_HALF_TOP)


def trapezoid_deck(b, x, length, top):
    """Broad planar crown with two straight, steep shoulder faces."""
    # Sloping transverse end sheets avoid a squared block at adjoining panels.
    verts = []
    for end in (-1, 1):
        verts += [(x + end * length / 2, -DECK_HALF_BASE, DECK_BASE_Z),
                  (x + end * length / 2, DECK_HALF_BASE, DECK_BASE_Z),
                  (x + end * (length / 2 - .075), DECK_HALF_TOP, top),
                  (x + end * (length / 2 - .075), -DECK_HALF_TOP, top)]
    obj = b.poly("trapezoid_roof_deck_v07", verts,
                 [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
                  (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)],
                 "roof", solid=True)
    obj["roof_flat_half_width"] = DECK_HALF_TOP
    obj["roof_shoulder_base_half_width"] = DECK_HALF_BASE
    obj["roof_crown_z"] = top
    obj["roof_shoulder_base_z"] = DECK_BASE_Z
    return feature(obj, "trapezoid_roof_deck")


def rectangle(cx, cy, width, height):
    return [(cx-width/2, cy-height/2), (cx+width/2, cy-height/2),
            (cx+width/2, cy+height/2), (cx-width/2, cy+height/2)]


def capsule(cx, cy, length, width, steps):
    r = width / 2
    straight = length / 2 - r
    result = []
    for sign, start in ((1, -math.pi/2), (-1, math.pi/2)):
        for i in range(steps + 1):
            angle = start + i * math.pi / steps
            result.append((cx + sign*straight + r*math.cos(angle),
                           cy + r*math.sin(angle)))
    return result


def exhaust_well(b, deck, x, y, top):
    """True deck opening, deep dark rectangular pocket and an open oval duct."""
    aperture = rectangle(x, y, 1.14, .512)
    cutter = b.sheet("lateral_exhaust_aperture_cutter", aperture,
                     lambda u, v: (u, v, top+.20), "black", .46, (0, 0, 1))
    b.cut(deck, cutter)
    # The original body crown ends at 4.48; pocket floor clears it by 14 mm.
    small_box(b, "lateral_exhaust_well_floor", (x, y, 4.494),
              (1.135, .507, .014), "black")
    outer = rectangle(x, y, 1.176, .548)
    inner = rectangle(x, y, 1.14, .512)
    lip = b.rim("lateral_exhaust_rectangular_rim", outer, inner,
                lambda u, v: (u, v, top+.007), "spring_steel", .022, (0, 0, 1))
    feature(lip, "lateral_exhaust")
    lip["mouth_center"] = (x, y, 4.603)
    lip["deck_aperture_size"] = (1.14, .512)
    # Four real inner walls, not a dark decal on an uncut top face.
    for yy in (y-.252, y+.252):
        small_box(b, "exhaust_pocket_inner_wall", (x, yy, 4.563),
                  (1.128, .011, .134), "graphite")
    for xx in (x-.564, x+.564):
        small_box(b, "exhaust_pocket_inner_end", (xx, y, 4.563),
                  (.011, .501, .134), "graphite")
    steps = 12 if b.lod == 0 else 6
    outer_duct = capsule(x, y, .81, .358, steps)
    inner_duct = capsule(x, y, .775, .323, steps)
    duct = b.rim("recessed_oval_exhaust_duct", outer_duct, inner_duct,
                 lambda u, v: (u, v, 4.603), "graphite", .105, (0, 0, 1))
    duct["open_exhaust_duct"] = True
    # A thin rolled edge is lower than the surrounding deck rim.
    b.tube("exhaust_rolled_mouth_edge", [(u, v, 4.605) for u, v in outer_duct+[outer_duct[0]]],
           .007, "spring_steel", sides=6)
    if b.lod == 0:
        for xx in (x-.493, x+.493):
            for yy in (y-.263, y+.263):
                b.cyl("exhaust_rim_captive_screw", (xx, yy, top+.010),
                      .007, .004, "spring_steel", "Z")


def vent_z(y):
    """Explicit break lines; no parabolic or rounded barrel-shaped cross vent."""
    return 4.685 - max(0, abs(y)-1.04) * (4.685-4.116) / (1.58-1.04)


def cross_vent(b):
    ys = (-1.58, -1.15, -1.04, 1.04, 1.15, 1.58)
    n = len(ys)
    b.poly("trapezoid_vent_dark_backing",
           [(x, y, vent_z(y)-.025) for x in (2.11, 3.59) for y in ys],
           [(i, i+1, n+i+1, n+i) for i in range(n-1)], "black", normal=(0, 0, 1))
    count = 63 if b.lod == 0 else 25
    for i in range(count):
        y = -1.58 + i*3.16/(count-1)
        b.tube("trapezoid_vent_longwire", [(2.13, y, vent_z(y)), (3.57, y, vent_z(y))],
               .004, "graphite", sides=6)
    count = 31 if b.lod == 0 else 11
    for i in range(count):
        x = 2.13+i*1.44/(count-1)
        b.tube("trapezoid_vent_crosswire", [(x, y, vent_z(y)+.005) for y in ys],
               .004, "graphite", sides=6)
    for x in (2.10, 2.60, 3.10, 3.60):
        # Rectangular folded-sheet strips keep the corner break visibly sharp.
        vertices = [(xx, y, vent_z(y)+.017) for xx in (x-.019, x+.019) for y in ys]
        rib = b.poly("trapezoid_vent_structural_rib", vertices,
                     [(i, i+1, n+i+1, n+i) for i in range(n-1)], "roof", normal=(0, 0, 1))
        feature(rib, "trapezoid_vent_rib")
    for side in (-1, 1):
        small_box(b, "trapezoid_vent_end_flange", (2.85, side*1.584, 4.122),
                  (1.56, .024, .054), "roof", .004)


def deck_fittings(b):
    # Hinged removable lids now sit on the raised crown, not inside the new deck.
    for x in (-.25, .70, 1.55):
        small_box(b, "roof_access_base_v07", (x, 0, 4.649), (.78, 1.75, .018), "black", .004)
        lid = small_box(b, "roof_access_lid_v07", (x, 0, 4.666), (.758, 1.728, .023), "roof", .006)
        b.feature(lid, "roof_access_lid")
        if b.lod == 0:
            for y in (-.58, .58):
                b.cyl("roof_access_hinge_v07", (x-.371, y, 4.681), .013, .115, "spring_steel", "Y")
                b.cyl("roof_access_flush_lock_v07", (x+.295, y, 4.681), .013, .006, "spring_steel", "Z")
                small_box(b, "roof_access_lock_slot_v07", (x+.295, y, 4.685), (.016, .003, .002), "black")
    for x in (4.11, 5.26, 6.41):
        small_box(b, "roof_transverse_gasket_v07", (x, 0, 4.653), (.012, 2.075, .006), "black")
        for y in (-.82, .82):
            profile = [(x-.16, 4.653), (x+.16, 4.653), (x+.055, 4.697), (x-.07, 4.697)]
            b.profile("pressed_roof_stiffener_v07", profile, y, .09, "roof")
            if b.lod == 0:
                small_box(b, "roof_recessed_pull_v07", (x+.13, y*.72, 4.657), (.115, .043, .006), "black", .002)
                b.rod("roof_pull_handle_v07", (x+.09, y*.72, 4.670), (x+.17, y*.72, 4.670), .006, "spring_steel")
    for x, length, top in DECK_SECTIONS:
        count = max(4, round(length/.45)) if b.lod == 0 else 4
        for side in (-1, 1):
            slope = (top-DECK_BASE_Z)/(DECK_HALF_BASE-DECK_HALF_TOP)
            normal = Vector((0, side*slope, 1)).normalized()
            for i in range(count):
                xx = x-length/2+.12+i*(length-.24)/(count-1)
                y = side*1.18
                pos = Vector((xx, y, deck_z(y, top)))+normal*.004
                screw = b.cyl("trapezoid_roof_shoulder_screw", pos, .009, .006, "spring_steel", "Z")
                screw.rotation_euler = normal.to_track_quat("Z", "Y").to_euler()


def aircon_fan(b, inherited):
    """Small circular lid grilles on the low equipment cases between fairings."""
    for end in (-1, 1):
        x = end*8.67
        # Cut the existing lid, seam and case: the visible fan sits below its lid.
        for obj in inherited:
            if obj.name.startswith(("cab_aircon_lid", "cab_aircon_case_v06")) and obj.location.x*end > 0:
                cutter = b.cyl("ac_roof_fan_cutter", (x, 0, 4.695), .246, .23, "black", "Z")
                b.cut(obj, cutter)
        small_box(b, "ac_fan_dark_well", (x, 0, 4.590), (.485, .485, .010), "black")
        b.cyl("ac_lid_fan_hub", (x, 0, 4.626), .051, .023, "graphite", "Z")
        if b.lod == 0:
            for i in range(7):
                a = i*math.tau/7
                loop = [(.043, -.015), (.187, -.047), (.211, .020), (.075, .035)]
                b.poly("ac_lid_fan_blade",
                       [(x+u*math.cos(a)-v*math.sin(a), u*math.sin(a)+v*math.cos(a), 4.630) for u, v in loop],
                       [(0, 1, 2, 3)], "graphite", normal=(0, 0, 1))
        feature(b.ring("ac_circular_lid_grille_rim", (x, 0, 4.709), .246, .010, "spring_steel"), "ac_lid_fan_grille")
        rings = (.074, .126, .181, .222) if b.lod == 0 else (.120, .218)
        for radius in rings:
            b.ring("ac_fan_concentric_grille", (x, 0, 4.709), radius, .004, "graphite")
        for i in range(8 if b.lod == 0 else 4):
            angle = i*math.tau/(8 if b.lod == 0 else 4)
            b.rod("ac_fan_radial_grille", (x, 0, 4.710),
                  (x+.239*math.cos(angle), .239*math.sin(angle), 4.710), .004, "graphite")


def cab_fairings(b):
    """Broad grey cab hoods, sloping into the brow instead of narrow beams."""
    # (absolute x, bottom z, lower half-width, crown z, crown half-width).
    # Front edge returns to the actual brow at x=10.02, z=4.48.
    front = ((9.10, 4.405, 1.235, 4.705, .90),
             (9.36, 4.405, 1.235, 4.705, .90),
             (9.49, 4.410, 1.225, 4.674, .925),
             (10.02, 4.460, 1.042, 4.484, 1.020))
    rear = ((7.40, 4.405, 1.235, 4.490, 1.125),
            (7.59, 4.405, 1.235, 4.705, .90),
            (7.89, 4.405, 1.235, 4.705, .90),
            (8.05, 4.405, 1.235, 4.660, .90))

    def shell_top(x,y):
        # Invert the actual shell mapping. A cover's shallow end ramp must
        # not cut through the body's flat crown/shoulder break underneath it.
        if abs(y)<=b.side_y(x,4.48):
            return 4.48
        low,high=3.95,4.48
        for _ in range(24):
            mid=(low+high)/2
            if b.side_y(x,mid)>abs(y): low=mid
            else: high=mid
        return (low+high)/2

    for end in (-1, 1):
        for name, stations in (("front", front), ("rear", rear)):
            rows=[]
            for a,c in zip(stations,stations[1:]):
                steps=max(1,math.ceil((c[0]-a[0])/(.045 if b.lod==0 else .09)))
                rows += [tuple(a[j]+(c[j]-a[j])*i/steps for j in range(5)) for i in range(steps)]
            rows.append(stations[-1])
            # Include crown edges exactly; split each shoulder into short strips
            # so clipping to the shell cannot reintroduce a long blue notch.
            strips=8 if b.lod==0 else 4
            verts=[]; bottom=[]
            for x,base,lower,top,upper in rows:
                ys=[-lower+i*(lower-upper)/strips for i in range(strips+1)]
                ys += [0]+[upper+i*(lower-upper)/strips for i in range(strips+1)]
                for y in ys:
                    nominal=top-max(0,abs(y)-upper)*(top-base)/(lower-upper)
                    support=shell_top(end*x,y)
                    margin=.006 if x>9.9 else .012
                    z=max(nominal,support+margin)
                    if abs(abs(y)-lower)<1e-7: z=support+margin
                    verts.append((end*x,y,z))
                    bottom.append((end*x,y,support-.012))
            columns=2*(strips+1)+1; count=len(verts)
            faces=[]
            for i in range(len(rows)-1):
                for j in range(columns-1):
                    a=i*columns+j; c=a+columns
                    faces += [(a,a+1,c+1),(a,c+1,c),
                              (count+a,count+c+1,count+a+1),(count+a,count+c,count+c+1)]
            edge=list(range(columns))
            edge += [i*columns+columns-1 for i in range(1,len(rows))]
            edge += list(range(count-2,count-columns-1,-1))
            edge += [i*columns for i in range(len(rows)-2,0,-1)]
            for a,c in zip(edge,edge[1:]+edge[:1]):
                faces.append((a,c,count+c,count+a))
            verts+=bottom
            obj = b.poly("cab_"+name+"_trapezoid_fairing_v07", verts, faces, "roof", solid=True)
            feature(obj, "cab_trapezoid_fairing")
            obj["brow_seated_cover"] = name == "front"
            # A 2 mm manufactured edge and weighted normals remove artificial
            # triangle highlights in the fitted lower return, keeping real folds.
            b.bevel(obj,.002,1)
        # The prior low mounting foot would be hidden inside the broad new hood.
        if b.lod == 0:
            b.cyl("antenna_hood_mount_v07", (end*9.25, .60, 4.715), .045, .020, "graphite", "Z")
            b.rod("radio_aerial_v07", (end*9.25, .60, 4.724), (end*9.25, .60, 4.840), .008, "black")


def build_roof(b):
    """Reuse unchanged radiator/AC hardware, replace all obsolete crown pieces."""
    if b.lod >= 2:
        return
    before = set(bpy.context.scene.objects)
    FrontRoofBuilder.roof(b)
    inherited = set(bpy.context.scene.objects)-before
    obsolete = ("removable_roof_deck", "seated_roof_deck_screw", "exhaust_",
                "rectangular_exhaust_", "arched_", "roof_access_", "roof_transverse_gasket",
                "pressed_roof_stiffener", "roof_recessed_pull", "roof_pull_handle",
                "cab_roof_cross_fairing", "antenna_mounting_foot", "radio_aerial_v06")
    kept = []
    for obj in inherited:
        if obj.name.startswith(obsolete):
            bpy.data.objects.remove(obj, do_unlink=True)
        else:
            kept.append(obj)
    decks = [trapezoid_deck(b, *section) for section in DECK_SECTIONS]
    for x, y, _ in EXHAUST_OUTLETS:
        exhaust_well(b, decks[0], x, y, DECK_SECTIONS[0][2])
    # Restrained edge highlights only; weighted normals do not round the shoulders.
    if b.lod == 0:
        for obj in decks:
            b.bevel(obj, .007, 1)
    deck_fittings(b)
    cross_vent(b)
    aircon_fan(b, kept)
    cab_fairings(b)
    # Move existing eyes and both mounting feet together onto their replacement deck.
    for obj in kept:
        if obj.name.startswith(("roof_lifting_eye_v06", "roof_eye_pad_v06")):
            coords = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            x = (min(v.x for v in coords)+max(v.x for v in coords))/2
            if abs(abs(x)-8.0) < .02:
                # Rear cab hood at x=8, y=.92; both feet and eye follow it.
                obj.location.z += .1781
            for centre, length, top in DECK_SECTIONS:
                if abs(x-centre) < length/2:
                    old_top = 4.56 if centre < 0 else 4.57
                    obj.location.z += top-old_top
    for obj in decks:
        obj["true_exhaust_apertures"] = 2 if obj == decks[0] else 0
