"""Photo-referenced, budgeted FXN5C running gear (not manufacturer CAD).

Evidence: TrainNets Yang Li yl08/09/10 close-ups and user supplied 0019/7006
side views. Hidden transoms, cable continuations and mount dimensions remain
estimates. All vertices are authored here, without external model assets.
"""
import math
from collections import Counter
from contextlib import contextmanager
import bpy
import bmesh
from mathutils import Vector

# Lower-wheel-arc fitting does NOT support the initial rough 2 m estimate.
# Preserve the existing running dimensions; local hardware is photo-fitted.
AXLE_PITCH = 1.8
AXLES = (-AXLE_PITCH, 0.0, AXLE_PITCH)
AXLE_HEIGHT = .625
EQUIPMENT_X = 2.56


class Batch:
    """One mesh per bogie; no thousands of modifier-bearing tiny objects."""
    def __init__(self, builder):
        self.b = builder
        self.v, self.f, self.mi, self.smooth = [], [], [], []
        self.materials = []
        self.counts = Counter()
        self.z_offset = 0.0

    @contextmanager
    def level(self, offset):
        old=self.z_offset
        self.z_offset=old+offset
        try: yield
        finally: self.z_offset=old

    def add(self, name, verts, faces, mat="graphite", smooth=False):
        if mat not in self.materials:
            self.materials.append(mat)
        base = len(self.v)
        self.v.extend((x,y,z+self.z_offset) for x,y,z in verts)
        self.f.extend(tuple(base+i for i in face) for face in faces)
        self.mi.extend([self.materials.index(mat)]*len(faces))
        self.smooth.extend([smooth]*len(faces) if isinstance(smooth, bool) else smooth)
        self.counts[name] += 1

    def profile(self, name, xz, y, depth, mat="graphite"):
        n = len(xz)
        verts = [(x, y+d, z) for d in (-depth/2, depth/2) for x,z in xz]
        faces = [tuple(range(n-1,-1,-1)), tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        self.add(name, verts, faces, mat)

    def box(self, name, center, dims, mat="graphite", bevel=0):
        x,y,z=center; w,d,h=dims
        if bevel:
            r=min(bevel,w*.23,h*.23)
            loop=[(x-w/2+r,z-h/2),(x+w/2-r,z-h/2),
                  (x+w/2,z-h/2+r),(x+w/2,z+h/2-r),
                  (x+w/2-r,z+h/2),(x-w/2+r,z+h/2),
                  (x-w/2,z+h/2-r),(x-w/2,z-h/2+r)]
        else:
            loop=[(x-w/2,z-h/2),(x+w/2,z-h/2),
                  (x+w/2,z+h/2),(x-w/2,z+h/2)]
        self.profile(name,loop,y,d,mat)

    def tube(self, name, points, radius, mat="graphite", sides=8):
        points=[Vector(p) for p in points]
        verts=[]
        for i,p in enumerate(points):
            tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
            ref=Vector((0,0,1)) if abs(tangent.z)<.92 else Vector((1,0,0))
            u=tangent.cross(ref).normalized(); v=tangent.cross(u).normalized()
            verts += [tuple(p+radius*(math.cos(j*math.tau/sides)*u+math.sin(j*math.tau/sides)*v)) for j in range(sides)]
        faces=[(i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j)
               for i in range(len(points)-1) for j in range(sides)]
        smooth=[True]*len(faces)
        faces.extend([tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))])
        self.add(name,verts,faces,mat,smooth+[False,False])

    def cyl(self, name, center, radius, depth, mat="graphite", axis="Y", segments=None):
        n=segments or (16 if self.b.lod==0 else 10)
        x,y,z=center
        mapping={"Y":lambda a,b,c:(x+a,y+c,z+b),
                 "Z":lambda a,b,c:(x+a,y+b,z+c),
                 "X":lambda a,b,c:(x+c,y+a,z+b)}[axis]
        verts=[mapping(radius*math.cos(j*math.tau/n),radius*math.sin(j*math.tau/n),d)
               for d in (-depth/2,depth/2) for j in range(n)]
        faces=[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
        faces += [tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        self.add(name,verts,faces,mat,[True]*n+[False,False])

    def annulus(self, name, center, inner, outer, depth, a0, a1, mat="graphite", steps=8):
        """Closed curved brake shoe / radial motor vent in the XZ plane."""
        x,y,z=center; verts=[]
        for yy in (-depth/2,depth/2):
            for r in (inner,outer):
                for j in range(steps+1):
                    a=a0+(a1-a0)*j/steps
                    verts.append((x+r*math.cos(a),y+yy,z+r*math.sin(a)))
        n=steps+1; faces=[]
        for j in range(steps):
            faces.extend([(j,j+1,n+j+1,n+j),(2*n+j,3*n+j,3*n+j+1,2*n+j+1),
                          (j,2*n+j,2*n+j+1,j+1),(n+j,n+j+1,3*n+j+1,3*n+j)])
        faces.extend([(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)])
        self.add(name,verts,faces,mat)

    def finish(self, name, parent):
        mesh=bpy.data.meshes.new(name+"_v20_mesh")
        mesh.from_pydata(self.v,[],self.f); mesh.update()
        for mat in self.materials: mesh.materials.append(self.b.mat(mat))
        for face,mi,s in zip(mesh.polygons,self.mi,self.smooth):
            face.material_index=mi; face.use_smooth=s
        bm=bmesh.new(); bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bm.to_mesh(mesh); bm.free()
        obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj)
        obj.parent=parent
        for key,count in self.counts.items(): obj["component_"+key]=count
        obj["bogie_revision"]="v19_photo_rebuild"
        obj["detail_v20_component"]="rebuilt_bogie"
        obj["geometry_basis"]="TrainNets yl08/09/10 + supplied 0019/7006; dimensions estimated"
        mesh.calc_loop_triangles()
        obj["triangles_v20"]=len(mesh.loop_triangles)
        return obj

    def rim_profile(self, name, outer, inner, y, depth, mat='graphite'):
        """A genuine through opening; corresponding loops have equal lengths."""
        assert len(outer)==len(inner)
        n=len(outer)
        verts=[(x,y+dy,z) for dy in (-depth/2,depth/2) for loop in (outer,inner) for x,z in loop]
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces += [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
                      (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]
        self.add(name,verts,faces,mat)


def _rounded_loop(x,z,w,h,r=.025):
    return [(x-w/2+r,z-h/2),(x+w/2-r,z-h/2),(x+w/2,z-h/2+r),
            (x+w/2,z+h/2-r),(x+w/2-r,z+h/2),(x-w/2+r,z+h/2),
            (x-w/2,z+h/2-r),(x-w/2,z-h/2+r)]


def _cradle(m, x, side):
    """Shallow cast spring tray with open rounded windows and rising cheeks."""
    y=side*1.15
    m.profile('cradle_cast_bottom',[(x-.59,.567),(x-.53,.503),(x-.20,.483),
        (x+.20,.483),(x+.53,.503),(x+.59,.567),(x+.52,.554),(x+.19,.527),
        (x-.19,.527),(x-.52,.554)],y,.30,'cast_steel')
    m.box('cradle_centre_web',(x,y,.568),(.37,.30,.077),'cast_steel',.025)
    for direction in (-1,1):
        xx=x+direction*.433
        m.rim_profile('cradle_rounded_window',_rounded_loop(xx,.582,.258,.154,.034),
            _rounded_loop(xx,.587,.150,.077,.021),y,.30,'cast_steel')
        pts=[(x+direction*.574,.619),(x+direction*.553,.646),
             (x+direction*.26,.672),(x+direction*.165,.785),
             (x+direction*.137,.772),(x+direction*.214,.618)]
        m.profile('axlebox_cradle_cheek',pts,y,.29,'cast_steel')
        m.box('cradle_spring_foot',(x+direction*.413,y,.650),(.31,.32,.035),'cast_steel',.022)
    m.counts["slotted_axlebox_cradle"] += 1


def _coil(m, x, y, z=.858, central=False):
    b=m.b
    top=.999 if central else 1.050
    for zz in (.663,top):
        m.cyl("spring_seat",(x,y,zz),.149,.038,"graphite","Z")
        if not b.lod:
            m.cyl("spring_seat_lip",(x,y,zz+(.022 if zz<.8 else -.022)),.139,.014,"cast_steel","Z")
    n=72 if not b.lod else 32
    points=[]
    for i in range(n+1):
        t=i/n; a=t*4.5*math.tau
        h=max(0,min(1,(t-.055)/.89))
        points.append((x+.110*math.cos(a),y+.110*math.sin(a),.708+(top-.750)*h))
    m.tube("primary_coil",points,.031,"cast_steel",8 if not b.lod else 6)
    m.counts["seated_primary_coil"]+=1


def _equipment(m, x, side):
    y=side*1.34; w=.64
    inward=-1 if x>0 else 1
    outline=[(x-w/2,1.035),(x+w/2,1.035),(x+w/2,.585),
             (x+.115,.585),(x+.115,.490),(x-w/2+.018,.490)]
    if inward<0: outline=[(2*x-xx,zz) for xx,zz in reversed(outline)]
    m.profile("bogie_terminal_box",outline,y,.25)
    front=side*1.475
    # The complete stepped silhouette has a separate thin lid / folded edge.
    m.profile("stepped_bogie_equipment_lid",outline,front,.021,"spring_steel")
    inner=[(x+(xx-x)*.94,.503+(zz-.490)*.95) for xx,zz in outline]
    m.profile("equipment_lid_field",inner,front+side*.016,.016)
    for xx in (x-w/2+.070,x+w/2-.070):
        m.box("equipment_hinge",(xx,front+side*.029,1.022),(.069,.035,.034),"spring_steel",.004)
        if not m.b.lod:
            for zz in (.622,.979):
                m.cyl("equipment_screw",(xx,front+side*.028,zz),.012,.011,"metal",segments=6)
    for xx in (x-.19,x+.19):
        m.box("equipment_mount",(xx,side*1.26,1.095),(.056,.34,.125))
    # Recessed lower tray and thin folded lip, not an oversized plain cube.
    m.box('equipment_lower_recess',(x-inward*.065,front+side*.027,.602),(.34,.012,.13),'black',.006)
    m.box('equipment_lower_shelf',(x-inward*.065,front+side*.052,.532),(.37,.081,.019),'spring_steel')
    if not m.b.lod:
        m.box('equipment_data_plate',(x-.13,front+side*.041,.986),(.072,.008,.024),'metal')
    if not m.b.lod:
        m.tube("equipment_flex_lead",[(x+.12,side*1.40,.515),(x+.20,side*1.43,.45),
                                     (x+.30,side*1.36,.46),(x+.31,side*1.29,1.08)],.013,"black",6)


def _axlebox(m, x, side):
    y=side*1.15
    central=abs(x)<.01
    with m.level(-.20): _cradle(m,x,side)
    # This visible cover is photo-estimated external hardware; it is NOT
    # forced to be the actual axle bearing. The true wheel rotation stays .625.
    if central:
        # Open centre saddle observed in yl10/7001: do not paste the end
        # station's circular cover onto it. Its hidden bearing is not modeled.
        m.annulus('centre_open_saddle',(x,side*1.24,.572),.099,.147,.20,
                  math.pi,2*math.pi,'cast_steel',16 if not m.b.lod else 8)
        for d in (-1,1):
            m.box('centre_saddle_ear',(x+d*.126,side*1.24,.605),(.043,.20,.068),'cast_steel',.008)
        m.counts['axlebox_housing']+=1
    else:
        outline=_rounded_loop(x,.507,.340,.247,.055)
        m.profile("axlebox_housing",outline,side*1.177,.285)
        m.cyl("axlebox_seal",(x,side*1.329,.505),.100,.018,"black")
        m.cyl("axlebox_cover",(x,side*1.344,.505),.086,.022,"cast_steel")
        m.cyl("axlebox_centre_plug",(x,side*1.359,.505),.027,.010,"graphite",segments=12)
    m.box('carrier_centre_riser',(x,y,.426),(.34,.29,.18),'cast_steel',.018)
    with m.level(-.20):
        for dx in (-.413,.413): _coil(m,x+dx,y,central=central)
    # The centre station is low and open: it must not inherit the tall
    # external guide/damper fork silhouette of the two end stations.
    if central:
        m.box('centre_station_saddle',(x,side*1.20,.695),(.35,.33,.055),'graphite',.022)
        for dx in (-.178,.178):
            m.box('centre_short_guide',(x+dx,side*1.17,.608),(.054,.265,.29),'cast_steel',.012)
        m.counts['low_centre_station']+=1
    else:
        for dx in (-.164,.164):
            with m.level(-.18):
                m.box("axlebox_guide",(x+dx,side*1.20,.967),(.046,.245,.442),bevel=.01)
                m.box("guide_wear_plate",(x+dx,side*1.337,.985),(.036,.015,.341),"spring_steel")
                m.profile("guide_top_gusset",[(x+dx-.065,1.239),(x+dx+.065,1.239),
                             (x+dx+.036,1.10),(x+dx-.031,1.10)],side*1.29,.032)
        # Two slim diagonal cheeks leave daylight around the spring tray.
        for d in (-1,1):
            with m.level(-.18):
                m.profile('outer_station_fork_cheek',[(x+d*.274,1.213),(x+d*.320,1.213),
                    (x+d*.393,.710),(x+d*.462,.653),(x+d*.375,.653),
                    (x+d*.326,.741)],side*1.325,.035,'cast_steel')
        m.counts['tall_end_station']+=1
    if not m.b.lod and not central:
        for angle in (30,90,150,210,270,330):
            a=math.radians(angle)
            m.cyl("bearing_cover_bolt",(x+.066*math.cos(a),side*1.365,.505+.066*math.sin(a)),.009,.011,
                  "spring_steel",segments=6)
        m.tube("axle_sensor_lead",[(x+.045,side*1.412,.557),(x+.115,side*1.448,.617),
                    (x+.13,side*1.44,.78),(x+.17,side*1.385,.987),(x+.24,side*1.322,1.082)],.009,"black",6)
    if not central:
        with m.level(-.18): _vertical_damper(m,x,side)


def _vertical_damper(m, x, side):
    """Visible near-vertical damper, with a real fork/pin at both ends.

    It is deliberately not identified as a yaw damper.  The photos establish
    position and attachment, not a manufacturer subsystem designation.
    """
    low=Vector((x-.060,side*1.423,.767))
    high=Vector((x-.041,side*1.423,1.240))
    def p(t): return tuple(low.lerp(high,t))
    m.tube("damper_body",[p(.075),p(.59)],.031,"graphite",12 if not m.b.lod else 8)
    m.tube("damper_rod",[p(.54),p(.93)],.013,"wheel_steel",8)
    # Short necks join both eye castings to the concentric tube/rod assembly.
    m.tube("damper_lower_neck",[p(0),p(.105)],.024,"graphite",8)
    m.tube("damper_upper_neck",[p(.90),p(1)],.016,"wheel_steel",8)
    for label,point in (("lower",low),("upper",high)):
        xx,yy,zz=point
        m.cyl("damper_eye",tuple(point),.041,.042,"graphite",segments=12 if not m.b.lod else 8)
        ear=[(xx-.044,zz-.045),(xx+.044,zz-.045),(xx+.052,zz+.026),
             (xx+.033,zz+.054),(xx-.034,zz+.054),(xx-.052,zz+.022)]
        # A fork has two distinct plates, with daylight around the eye.
        for ay in (1.384,1.462):
            m.profile("damper_"+label+"_clevis_ear",ear,side*ay,.027,"cast_steel")
        # Pin spans both ears and the eye; it is not a cap floating outside it.
        m.cyl("damper_"+label+"_through_pin",(xx,side*1.423,zz),.018,.151,
              "spring_steel",segments=8)
        if not m.b.lod:
            m.cyl("damper_pin_head",(xx,side*1.503,zz),.027,.015,"metal",segments=6)
    m.box("damper_lower_anchor",(low.x,side*1.325,low.z-.045),(.16,.16,.065),"cast_steel",.012)
    m.box("damper_upper_anchor",(high.x,side*1.323,high.z+.041),(.143,.165,.064),"cast_steel",.012)
    # Solid fork roots connect BOTH ears behind/below the eye, not only by
    # the moving transverse pin. The eye's central working gap stays open.
    m.box("damper_lower_clevis_bridge",(low.x,side*1.425,low.z-.063),(.14,.13,.035),"cast_steel")
    m.box("damper_upper_clevis_bridge",(high.x,side*1.425,high.z+.068),(.14,.13,.032),"cast_steel")


def _frame_side(m, side):
    y=side*1.14
    # Thin upper box girder plus local downstands; no blanket deep rectangular bar.
    outline=[(-2.90,1.245),(-2.74,1.320),(-1.53,1.320),(-1.38,1.296),
             (-.46,1.296),(-.29,1.273),(.29,1.273),(.46,1.296),
             (1.38,1.296),(1.53,1.320),(2.74,1.320),(2.90,1.245),
             (2.80,1.168),(1.22,1.168),(1.06,1.117),(.57,1.117),
             (.39,1.166),(-.39,1.166),(-.57,1.117),(-1.06,1.117),
             (-1.22,1.168),(-2.80,1.168)]
    with m.level(-.13): m.profile("cast_side_beam",outline,y,.25)
    for a,b,z in [(-2.80,-1.22,1.169),(-1.06,-.57,1.118),(-.39,.39,1.167),
                  (.57,1.06,1.118),(1.22,2.80,1.169)]:
        m.box("segmented_lower_flange",((a+b)/2,y,z-.13),(b-a,.319,.039))
    for x in AXLES: _axlebox(m,x,side)
    # v19: do not put a fictitious longitudinal two-ended arm in the frame.
    # body_bogie_connection_v20 builds the three separately-owned components.
    for xx in (-EQUIPMENT_X,EQUIPMENT_X): _equipment(m,xx,side)
    for xx in AXLES:
        central=abs(xx)<.01
        for dx in (-.413,.413):
            sx=xx+dx
            bottom=.789 if central else .840
            m.profile('spring_upper_pocket',[(sx-.15,bottom),(sx+.15,bottom),
                (sx+.15,bottom+.045),(sx+.10,1.110),(sx-.10,1.110),
                (sx-.15,bottom+.045)],y,.28,'graphite')
    for xx in (-.90,.90):
        m.cyl("secondary_mount",(xx,side*.91,1.46),.176,.14,"black","Z")
        m.cyl("secondary_seat",(xx,side*.91,1.200),.193,.045,"graphite","Z")
        m.cyl('secondary_support_column',(xx,side*.91,1.312),.123,.20,'cast_steel','Z')
    if not m.b.lod:
        path=[(-2.65,side*1.291,1.325),(-1.66,side*1.301,1.325),(-1.44,side*1.301,1.298),
              (.70,side*1.301,1.298),(1.45,side*1.301,1.325),(2.65,side*1.301,1.325)]
        with m.level(-.13): m.tube("bogie_air_main",path,.014,"ochre",8)
        for xx,zz in ((-1.98,1.325),(-1.26,1.298),(-.40,1.298),(.68,1.298),(1.85,1.325)):
            m.box("pipe_clip",(xx,side*1.311,zz-.13),(.025,.050,.070),"spring_steel",.003)
        m.box("bogie_builder_plate",(.59,side*1.277,1.106),(.22,.010,.052),"metal")
        for xx in (.515,.555,.595,.635,.675):
            m.box("builder_plate_etch",(xx,side*1.284,1.106),(.018,.003,.019),"graphite")
        for sign in (-1,1):
            m.tube("sand_pipe",[(sign*2.67,side*1.205,1.15),(sign*2.69,side*1.205,.82),
                (sign*2.56,side*.98,.39),(sign*2.43,side*.75,.15)],.019,"black",8)
            m.box("sand_pipe_anchor",(sign*2.68,side*1.20,.82),(.08,.09,.06))


def _drive_and_brakes(m):
    for x in AXLES:
        m.box("transom",(x+.40,0,1.20),(.27,2.24,.23),bevel=.025)
        m.cyl("traction_motor_casing",(x+.30,0,.714),.382,1.15,"graphite",segments=24 if not m.b.lod else 12)
        for side in (-1,1):
            m.cyl("motor_endplate",(x+.30,side*.591,.714),.386,.043,"cast_steel",segments=24 if not m.b.lod else 12)
            m.cyl("motor_bearing",(x+.30,side*.623,.714),.111,.045,"graphite",segments=16)
            if not m.b.lod:
                # Dark recessed annular slots, with a sparse protective cross mesh.
                for j in range(8):
                    a=j*math.tau/8
                    m.annulus("motor_radial_vent",(x+.30,side*.615,.714),.178,.318,.009,
                              a+.085,a+.61,"grille_black",2)
                    rr=.253
                    for d in (0,):
                        aa=a+.347+d
                        p1=(x+.30+.187*math.cos(aa),side*.624,.714+.187*math.sin(aa))
                        p2=(x+.30+.309*math.cos(aa),side*.624,.714+.309*math.sin(aa))
                        m.tube("motor_vent_mesh",[p1,p2],.0035,"graphite",4)
                    m.cyl("motor_flange_bolt",(x+.30+.350*math.cos(a),side*.623,.714+.350*math.sin(a)),
                          .015,.014,"spring_steel",segments=6)
            # Shoes conform concentrically to the wheel tread, with an air gap.
            for direction in (-1,1):
                a=.38 if direction>0 else math.pi-.38
                m.annulus("curved_tread_brake_shoe",(x,side*.753,.625),.645,.699,.142,a-.185,a+.185,
                          "cast_steel",5 if not m.b.lod else 3)
                xx=x+.716*math.cos(a); zz=.625+.716*math.sin(a)
                m.tube("brake_hanger",[(xx,side*.895,zz),(xx+direction*.012,side*.895,1.165)],.020,"graphite",8)
                m.cyl("brake_hanger_pin",(xx,side*.918,1.15),.030,.045,"spring_steel",segments=10)
            m.cyl("brake_actuator",(x+.56,side*.93,1.175),.09,.25,"graphite","X",16 if not m.b.lod else 10)
            m.tube("brake_pushrod",[(x+.42,side*.93,1.175),(x+.28,side*.93,1.10)],.018,"spring_steel",8)
            if not m.b.lod:
                m.tube("brake_air_branch",[(x+.58,side*1.30,1.197),(x+.62,side*1.18,1.20),
                            (x+.63,side*1.03,1.225),(x+.60,side*.96,1.22)],.010,"black",6)
        m.cyl("axle_gearcase",(x,-.46,.625),.305,.205,"graphite",segments=20 if not m.b.lod else 12)
        m.box("gearcase_bridge",(x+.12,-.46,.632),(.37,.205,.39),"graphite",.065)
        m.box("motor_suspension_lug",(x+.57,0,1.11),(.25,.50,.14),bevel=.035)
    m.cyl("centre_pivot",(0,0,1.385),.34,.24,"graphite","Z")
    for xx in (-2.74,2.74):
        m.box("end_tie_beam",(xx,0,1.235),(.17,2.27,.16),bevel=.025)


def build_bogie(builder, index, center):
    """Build a complete replacement; all moving names match native export."""
    from geometry_v03 import DetailBuilder
    if builder.lod>=2:
        return DetailBuilder.bogie(builder,index,center)
    assert bpy.data.objects.get(f"b{index}_grp") is None, "Delete old bogie before replacement"
    group=bpy.data.objects.new(f"b{index}_grp",None)
    bpy.context.collection.objects.link(group); group.location=(center,0,0)
    m=Batch(builder)
    for side in (-1,1): _frame_side(m,side)
    _drive_and_brakes(m)
    frame=m.finish(f"b{index}",group)
    for i,x in enumerate((AXLE_PITCH,0,-AXLE_PITCH),start=1):
        # Original turned running surface / correct inward flanges are retained.
        DetailBuilder.wheelset(builder,(index-1)*3+i,x,group)
    bpy.context.view_layer.update()
    total=0
    for obj in group.children:
        if obj.type=="MESH":
            obj.data.calc_loop_triangles(); total+=len(obj.data.loop_triangles)
    frame["total_bogie_triangles_v20"]=total
    group["bogie_revision"]="v19_photo_rebuild"
    group["total_triangles_v20"]=total
    # v19 includes true clevis ears / through pins in the visible suspension.
    assert total<=50000 if builder.lod==0 else total<=22000, (index,builder.lod,total)
    return group


def rebuild_saved_bogies(gen,lod=0,builder=None):
    """Incremental saved-source path; deletes only the two named moving trees."""
    if builder is None:
        from geometry_v14 import ProductionBuilder14
        builder=ProductionBuilder14(lod,gen)
    for index,center in enumerate(gen.BOGIE_CENTERS,start=1):
        group=bpy.data.objects.get(f"b{index}_grp")
        if group:
            for obj in list(group.children_recursive):
                bpy.data.objects.remove(obj,do_unlink=True)
            bpy.data.objects.remove(group,do_unlink=True)
        build_bogie(builder,index,center)
    # New counts reflect generated components, not a retained v08 scene counter.
    bpy.context.scene["running_gear15_rebuilt_bogie"]=2
    bpy.context.scene["running_gear15_curved_brake_shoe"]=24 if lod<2 else 0
    bpy.context.scene["running_gear15_slotted_cradle"]=12 if lod<2 else 0
    gen.ensure_uvs()


if __name__=="__main__":
    import os,sys,json
    root=os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0,root)
    import generate_fxn5c as gen
    from geometry_v14 import ProductionBuilder14
    result=[]
    for lod in (0,1,2):
        gen.clear_scene(); b=ProductionBuilder14(lod,gen)
        build_bogie(b,1,0); gen.ensure_uvs()
        result.append({"lod":lod,"triangles":sum(len(o.data.loop_triangles) for o in bpy.context.scene.objects if o.type=="MESH"),
                       "objects":[o.name for o in bpy.context.scene.objects]})
    print("BOGIE_V16_TEST",json.dumps(result))
