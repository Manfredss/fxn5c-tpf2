"""Original front-end geometry from FXN5C production photos and CRRC coupler casting.

Visible structure is referenced; dimensions and exact fitted coupler subtype are
not surveyed. No third-party meshes are used. X points outward at end +1.
"""
import math
import bpy
from mathutils import Vector
from geometry_v06 import chamfer_polygon
from geometry_v05 import split_polygon
from geometry_v07 import SilhouetteBuilder

TOP_OUTER = [(-.294,4.108),(.294,4.108),(.369,4.415),(-.369,4.415)]
TOP_INNER = [(-.273,4.128),(.273,4.128),(.344,4.393),(-.344,4.393)]


def circle(radius, count=48):
    return [(radius*math.cos(i*math.tau/count), radius*math.sin(i*math.tau/count)) for i in range(count)]


def lower_frame(end, side, kind):
    if kind == "white":
        # Trainfanz production 0013 front photo: inner centres are about 0.79
        # of the outer centres' lateral offset. Photo estimate, not a dimension.
        return Vector((end*11.04,side*1.24,2.02)), Vector((0,side,0)), Vector((end,0,0))
    # Exactly on the existing finite-width corner, NOT the flat nose.
    tangent = Vector((-end*.24,side*.17,0)).normalized()
    normal = Vector((end*.17,side*.24,0)).normalized()
    center = Vector((end*(11.04-.12),side*(1.48+.085),2.055))
    return center, tangent, normal


def lower_mapper(end, side, kind, offset):
    center, tangent, normal = lower_frame(end,side,kind)
    return lambda u,v: tuple(center+tangent*u+Vector((0,0,v))+normal*offset)


def remove_at_end(prefixes, end):
    removed=[]
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH" or not obj.name.startswith(prefixes):
            continue
        center=sum((obj.matrix_world@v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
        if center.x*end>10:
            removed.append(obj.name)
            bpy.data.objects.remove(obj,do_unlink=True)
    return removed


def cut_top_aperture(b,end):
    loop=chamfer_polygon(TOP_INNER,.010)
    targets=[o for o in bpy.context.scene.objects if o.type=="MESH" and
             (o.name.startswith("body_open_shell_v07") or o.name.startswith("grey_brow_"))]
    for obj in targets:
        if obj.name.startswith("grey_brow_"):
            xs=[(obj.matrix_world@v.co).x for v in obj.data.vertices]
            if sum(xs)*end<0: continue
        cutter=b.sheet("toplamp_actual_aperture_cutter_v09",loop,
                       lambda y,z:(end*(b.front_x(z)+.15),y,z),"black",.48,(end,0,0))
        b.cut(obj,cutter)


def make_lamps(b,end):
    cut_top_aperture(b,end)
    outer=chamfer_polygon(TOP_OUTER,.012)
    inner=chamfer_polygon(TOP_INNER,.010)
    front=lambda y,z:(end*(b.front_x(z)+.004),y,z)
    b.tag(b.rim("flush_upper_lamp_gasket_v09",outer,inner,front,"black",.136,(end,0,0)),"recessed_upper_lamp_cavity")
    b.sheet("upper_lamp_cavity_back_v09",inner,
            lambda y,z:(end*(b.front_x(z)-.145),y,z),"grille_black",.006,(end,0,0))
    glass=b.glass("shared_lamp_cover_v09",inner,
                  lambda y,z:(end*(b.front_x(z)-.005),y,z),(end,0,0),"lamp_glass")
    b.tag(glass,"flush_upper_cover")
    # Actual concave reflector bowls; emitters are at their backs, behind cover.
    for side in (-1,1):
        verts=[]; n=48 if b.lod==0 else 24
        rings=((.030,-.110),(.045,-.096),(.070,-.064),(.090,-.036),(.103,-.022))
        for radius,offset in rings:
            for u,v in circle(radius,n):
                y=side*.15+u; z=4.27+v
                verts.append((end*(b.front_x(z)+offset),y,z))
        faces=[(r*n+i,r*n+(i+1)%n,(r+1)*n+(i+1)%n,(r+1)*n+i) for r in range(len(rings)-1) for i in range(n)]
        obj=b.poly("concave_upper_reflector_v09",verts,faces,"metal",normal=(end,0,0))
        for face in obj.data.polygons: face.use_smooth=True
        b.rim("upper_reflector_retainer_v09",circle(.107,n),circle(.100,n),
              lambda u,v:(end*(b.front_x(4.27+v)-.019),side*.15+u,4.27+v),"spring_steel",.012,(end,0,0))
        b.glass("upper_inner_optic_v09",circle(.041,n),
                lambda u,v:(end*(b.front_x(4.27+v)-.082),side*.15+u,4.27+v),(end,0,0),"lamp_glass")
    # The lower four fixtures belong to two genuinely different planes.
    for side in (-1,1):
        for kind in ("white","red"):
            _,_,normal=lower_frame(end,side,kind)
            b.sheet("lower_lamp_back_v09",circle(.106),lower_mapper(end,side,kind,.003),"graphite",.006,normal)
            rim=b.rim("lower_lamp_bezel_v09",circle(.109),circle(.086),
                      lower_mapper(end,side,kind,.028),"metal",.026,normal)
            b.tag(rim,"front_white_fixture" if kind=="white" else "corner_red_fixture")
            b.sheet("lower_lamp_reflector_v09",circle(.085),lower_mapper(end,side,kind,.012),"metal",axis=normal)
            b.glass("lower_lamp_lens_v09",circle(.085),lower_mapper(end,side,kind,.030),normal,"lamp_glass")
            if b.lod==0:
                for a in (45,135,225,315):
                    u=.098*math.cos(math.radians(a)); v=.098*math.sin(math.radians(a))
                    p=Vector(lower_mapper(end,side,kind,.029)(u,v))
                    b.rod("lower_bezel_captive_screw_v09",p,p+normal*.003,.0035,"spring_steel")


def make_emitters(b):
    groups={name:[] for name in ("headlights_fwd","taillights_fwd","headlights_bwd","taillights_bwd")}
    for end in (-1,1):
        head="headlights_fwd" if end==1 else "headlights_bwd"
        tail="taillights_bwd" if end==1 else "taillights_fwd"
        for side in (-1,1):
            for kind,node in (("white",head),("red",tail)):
                _,_,normal=lower_frame(end,side,kind)
                obj=b.sheet("lower_emitter_v09",circle(.068,32),lower_mapper(end,side,kind,.020),
                            "lamp_"+kind,axis=normal)
                groups[node].append(obj)
            obj=b.sheet("recessed_top_emitter_v09",circle(.038,32),
                        lambda u,v:(end*(b.front_x(4.27+v)-.090),side*.15+u,4.27+v),"lamp_white",axis=(end,0,0))
            groups[head].append(obj)
    for name,objects in groups.items(): b.g.join_objects(objects,name)


def striped_facet(b,end,points):
    # Split the actual 3D triangular face; paint follows it with no flattening.
    # The production 0013 front photograph shows steep rising-right bands.
    # Use the end-local lateral coordinate to retain that appearance at both ends.
    pieces=[points]
    for i in range(-8,9):
        pieces=[q for p in pieces for q in split_polygon(p,lambda v,k=i*.225:v[2]-end*v[1]*1.50-k)]
    for p in pieces:
        center=sum((Vector(v) for v in p),Vector())/len(p)
        if math.floor((center.z-end*center.y*1.50)/.225)%2:
            b.poly("central_plough_yellow_v09",[(x+end*.0015,y,z) for x,y,z in p],
                   [tuple(range(len(p)))],"yellow",normal=(end,0,0))


def make_pilot(b,end):
    contour=[(-1.44,1.33),(1.44,1.33),(1.40,.48),(1.20,.26),(-1.20,.26),(-1.40,.48)]
    obj=b.sheet("black_pilot_plate_v09",contour,lambda y,z:(end*11.105,y,z),"graphite",.038,(end,0,0))
    cutter=b.box("drawgear_hole_cutter_v09",(end*11.10,0,1.04),(.5,.54,.40),"black",.025)
    b.cut(obj,cutter); b.bevel(obj,.004,2 if b.lod==0 else 1)
    b.sheet("drawgear_dark_recess_v09",[(-.29,.82),(.29,.82),(.29,1.26),(-.29,1.26)],
            lambda y,z:(end*10.90,y,z),"grille_black",axis=(end,0,0))
    # Central pointed volume. Its footprint stops before either black side tread.
    apex=(end*11.53,0,.28); ridge=(end*11.24,0,.715)
    for side in (-1,1):
        low=(end*11.108,side*.80,.275)
        # The top edge descends straight from the central ridge to the outer
        # corner, not the broad flat shoulder of the first v09 draft.
        upper=tuple(Vector(ridge).lerp(Vector(low),.405/.80))
        verts=[apex,low,upper,ridge]
        facets=[(0,1,2),(0,2,3)]
        obj=b.poly("central_pointed_plough_v09",verts,facets,"grille_black",normal=(end,0,0))
        mod=obj.modifiers.new("real_folded_plate","SOLIDIFY"); mod.thickness=.016
        bpy.context.view_layer.objects.active=obj; bpy.ops.object.modifier_apply(modifier=mod.name)
        b.tag(obj,"central_plough_half")
        for f in facets: striped_facet(b,end,[verts[i] for i in f])
        # Treads are bolted to unpainted black plate, with visible angle supports.
        center=side*1.155
        b.tag(b.small_box("independent_pilot_tread_v09",(end*11.242,center,.294),(.276,.430,.027),"graphite",.004),"black_side_tread")
        for dy in (-.155,.155):
            y=center+dy
            profile=[(end*11.102,.420),(end*11.112,.275),(end*11.365,.275),(end*11.365,.286),(end*11.125,.305)]
            b.profile("tread_angle_support_v09",profile,y,.022,"graphite")
        if b.lod==0:
            for j in range(12):
                b.small_box("tread_open_grating_v09",(end*11.245,center-.193+j*.035,.314),(.267,.010,.010),"metal",.001)
            for y in (center-.16,center+.16):
                b.bolt("tread_attachment_bolt_v09",(end*11.128,y,.355),.011,"X")


def make_coupler(b,end):
    # A closed, static Janney-family joint: separate fixed jaw and knuckle,
    # actual open throat, pivot pin, locking linkage and cast shoulders.
    # Handedness is preserved by a 180-degree rotation at the opposite end.
    transform=lambda x,y,z:(end*x,end*y,z)
    def casting(name,outline,zlow,zhigh,bevel=.012):
        n=len(outline)
        verts=[transform(x,y,zlow(x)) for x,y in outline]+[transform(x,y,zhigh(x)) for x,y in outline]
        faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        obj=b.poly(name,verts,faces,"coupler_steel",solid=True)
        b.bevel(obj,bevel,3 if b.lod==0 else 1)
        return obj
    outline=[(10.88,-.10),(11.24,-.115),(11.36,-.22),(11.55,-.255),(11.70,-.195),
             (11.72,-.105),(11.66,-.065),(11.50,-.080),(11.41,-.015),(11.41,.060),
             (11.52,.130),(11.57,.205),(11.48,.265),(11.35,.225),(11.24,.120),(10.88,.10)]
    height=lambda x:.108+.077*max(0,min(1,(x-11.20)/.21))
    body=casting("janney_fixed_head_v09",outline,lambda x:1.04-height(x),lambda x:1.04+height(x),.018)
    b.tag(body,"janney_fixed_head")
    # Two shallow cast recesses in the guard nose, not a painted fake throat.
    if b.lod==0:
        for z in (.951,1.115):
            cutter=b.small_box("guard_recess_cutter_v09",transform(11.712,-.147,z),(.07,.083,.036),"black",.009)
            b.cut(body,cutter)
    knuckle=[(11.48,.16),(11.54,.205),(11.63,.208),(11.72,.125),(11.73,.015),
             (11.69,-.042),(11.64,-.040),(11.60,.035),(11.515,.065),(11.475,.108)]
    b.tag(casting("janney_moving_knuckle_v09",knuckle,lambda x:.900,lambda x:1.184,.015),"janney_knuckle")
    for z in (.874,1.209):
        ear=[(11.44,.135),(11.49,.235),(11.59,.234),(11.627,.185),(11.596,.123),(11.49,.095)]
        casting("janney_pivot_ear_v09",ear,lambda x,z=z:z-.025,lambda x,z=z:z+.025,.009)
    b.cyl("janney_vertical_knuckle_pin_v09",transform(11.55,.165,1.04),.027,.402,"spring_steel","Z")
    b.cyl("janney_pin_head_v09",transform(11.55,.165,1.250),.040,.022,"coupler_steel","Z")
    b.small_box("coupler_carrier_v09",transform(11.21,0,.886),(.37,.40,.047),"graphite",.008)
    for side in (-1,1):
        b.small_box("drawgear_pocket_cheek_v09",transform(11.075,side*.245,1.04),(.18,.032,.35),"graphite",.009)
    # Top-operated linkage represented externally only; internal locking gear
    # and the fitted FXN5C subtype remain unverified, and no animation is claimed.
    b.cyl("janney_lift_eye_boss_v09",transform(11.35,.025,1.198),.031,.045,"coupler_steel","Z")
    b.ring("janney_lift_eye_v09",transform(11.35,.025,1.24),.029,.007,"coupler_steel","Y")
    if b.lod==0:
        start=Vector((end*11.245,0,1.405)); finish=Vector(transform(11.35,.025,1.267))
        for i in range(7):
            p=start.lerp(finish,i/6)
            b.ring("janney_operating_chain_v09",tuple(p),.017,.0038,"coupler_steel","X" if i%2 else "Y")


OLD_PILOT=("folded_steel_pilot","pilot_warning","folded_pilot_toe_v08","pilot_chevron_paint_v08",
           "pilot_step_frame","pilot_step_grating","pilot_flush_fastener_v08","pilot_bolt_plate","pilot_bolt")
OLD_COUPLER=("coupler_drawbar","coupler_cast_knuckle","coupler_throat","knuckle_pin",
             "drawgear_carrier","carrier_bearing_cheek","carrier_mount_bolt","coupler_lock_link","lock_link_attachment")


def replace_pilot_coupler(b,end):
    remove_at_end(OLD_PILOT+OLD_COUPLER,end)
    make_pilot(b,end); make_coupler(b,end)
