"""FXN5C 0051 exterior, rebuilt against project reference photos 05/06.

Metric dimensions remain estimates, not a manufacturer's general arrangement.
X is longitudinal, Z is above rail; both cab fronts use one explicit surface
mapping so their windows, wipers and markings cannot float off the body.
"""
import math
import bpy
import bmesh
from mathutils import Vector

GAUGE = 1.435
WHEEL_TREAD_CENTER = 0.75
WHEEL_RADIUS = 0.625
EXHAUST = (-1.70, 0.0, 4.64)


class Builder:
    def __init__(self, lod, gen):
        self.lod, self.g = lod, gen

    def mat(self, name):
        return self.g.material(name)

    def box(self, name, loc, dims, mat="dark", bevel=0.0, parent=None):
        return self.g.add_box(name, loc, dims, self.mat(mat), bevel, parent=parent)

    def cyl(self, name, loc, radius, depth, mat="metal", axis="Y", parent=None):
        rot = {"X": (0, math.pi / 2, 0), "Y": (math.pi / 2, 0, 0), "Z": (0, 0, 0)}[axis]
        return self.g.add_cylinder(name, loc, radius, depth, self.mat(mat),
                                   24 if self.lod == 0 else 12, rot, parent)

    def poly(self, name, verts, faces, mat, solid=False, normal=None, parent=None):
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        if solid:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        elif normal:
            bm.normal_update()
            for f in bm.faces:
                if f.normal.dot(Vector(normal)) < 0:
                    f.normal_flip()
        bm.to_mesh(mesh)
        bm.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(self.mat(mat))
        if parent:
            obj.parent = parent
        return obj

    def rod(self, name, p1, p2, r=0.018, mat="metal", parent=None):
        a, b = Vector(p1), Vector(p2)
        obj = self.cyl(name, (a + b) / 2, r, (b - a).length, mat, "Z", parent)
        obj.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
        return obj

    @staticmethod
    def front_x(z):
        if z <= 2.55:
            return 11.04
        if z <= 4.02:
            return 11.04 - (z - 2.55) * (0.64 / 1.47)
        return 10.40 - (z - 4.02) * (0.38 / 0.46)

    def front(self, name, sign, yz, mat, offset=0.012):
        verts = [(sign * (self.front_x(z) + offset), y, z) for y, z in yz]
        return self.poly(name, verts, [tuple(range(len(verts)))], mat, normal=(sign, 0, 0))

    def front_rect(self, name, sign, y, z, width, height, mat, offset=0.012):
        return self.front(name, sign, [(y-width/2,z-height/2), (y+width/2,z-height/2),
                          (y+width/2,z+height/2), (y-width/2,z+height/2)], mat, offset)

    def front_rod(self, name, sign, a, b, radius=0.018, mat="metal", offset=0.042):
        return self.rod(name, (sign*(self.front_x(a[1])+offset), *a),
                        (sign*(self.front_x(b[1])+offset), *b), radius, mat)

    @staticmethod
    def side_y(x, z):
        # Cab narrows toward the end, including a separate upper shoulder.
        end_x=Builder.front_x(z)
        t=max(0,min(1,(abs(x)-9.4)/(end_x-9.4)))
        middle=1.65-max(0,z-3.95)*(.50/.53)
        tip=1.48-max(0,min(1,(z-2.55)/1.47))*.05
        return middle+(tip-middle)*t

    def side(self, name, sign, xz, mat, offset=0.012):
        verts = [(x, sign*(self.side_y(x,z)+offset), z) for x,z in xz]
        return self.poly(name, verts, [tuple(range(len(verts)))], mat, normal=(0,sign,0))

    def side_rect(self, name, sign, x, z, w, h, mat, offset=0.012):
        return self.side(name, sign, [(x-w/2,z-h/2),(x+w/2,z-h/2),
                                      (x+w/2,z+h/2),(x-w/2,z+h/2)], mat, offset)

    def hull(self):
        front = [(11.04,-1.48,1.58),(11.04,1.48,1.58),
                 (11.04,1.48,2.55),(10.40,1.43,4.02),
                 (10.02,1.02,4.48),(10.02,-1.02,4.48),
                 (10.40,-1.43,4.02),(11.04,-1.48,2.55)]
        middle = [(9.40,-1.65,1.58),(9.40,1.65,1.58),
                  (9.40,1.65,2.55),(9.40,1.65,3.95),
                  (9.40,1.15,4.48),(9.40,-1.15,4.48),
                  (9.40,-1.65,3.95),(9.40,-1.65,2.55)]
        rings = [[(-x,y,z) for x,y,z in front], [(-x,y,z) for x,y,z in middle], middle, front]
        verts = sum(rings, [])
        faces = []
        for ring in range(3):
            for i in range(8):
                faces.append((ring*8+i, ring*8+(i+1)%8, (ring+1)*8+(i+1)%8, (ring+1)*8+i))
        for start in (0,24):
            for f in [(0,1,2,7),(7,2,3,6),(6,3,4,5)]:
                faces.append(tuple(start+i for i in f))
        self.poly("body_shell_v02", verts, faces, "blue", solid=True)

    def livery(self):
        for side in (-1,1):
            # Tapered cyan sweeps fade into the upper shoulder at the centre.
            for end in (-1,1):
                ribbon=[(2.3,3.91,3.92),(4.0,3.72,3.90),(6.0,3.26,3.61),
                        (8.4,2.72,2.91),(9.4,2.53,2.67),(10.6,2.31,2.43)]
                for a,b in zip(ribbon,ribbon[1:]):
                    self.side(f"cyan_sweep_{side}_{end}",side,
                              [(end*a[0],a[1]),(end*b[0],b[1]),(end*b[0],b[2]),(end*a[0],a[2])],"light_blue",.022)
            points = [(-8.1,1.64),(-5.6,1.90),(-2.8,2.09),(0,2.16),(2.8,2.09),(5.6,1.90),(8.1,1.64)]
            self.side("gold_sweep_"+str(side), side,
                      points + [(x,z+0.15*(1-abs(x)/8.1)) for x,z in reversed(points)], "yellow", 0.018)
            # Thin body/roof seam.
            self.side_rect("roof_seam_"+str(side), side,0,3.92,18.7,0.028,"dark",0.025)
        for end in (-1,1):
            self.front("grey_brow_"+str(end),end,[(-1.425,4.02),(1.425,4.02),(1.02,4.48),(-1.02,4.48)],"roof")

    def cabs(self):
        for end in (-1,1):
            self.front_rect("windscreen_surround_"+str(end),end,0,3.295,2.64,1.45,"roof",0.018)
            for side in (-1,1):
                cy=side*0.61
                self.front_rect(f"window_seal_{end}_{side}",end,cy,3.34,1.16,1.14,"black",0.026)
                self.front_rect(f"windscreen_{end}_{side}",end,cy,3.34,1.075,1.055,"glass_transparent",0.034)
                # Pale sun blinds at the top, not a transparent window into a solid hull.
                self.front_rect(f"sun_blind_{end}_{side}",end,cy,3.735,1.025,0.13,"metal",0.039)
                if self.lod == 0:
                    self.front_rod(f"wiper_arm_{end}_{side}",end,(cy*0.62,2.70),(cy+0.23,2.95),0.015,"black")
                    self.front_rod(f"wiper_blade_{end}_{side}",end,(cy-0.13,3.13),(cy+0.40,2.88),0.022,"black")
                    self.front_rod(f"nose_grab_{end}_{side}",end,(side*0.96,1.80),(side*1.08,2.34),0.022)
                    for yy,zz in [(side*.96,1.80),(side*1.08,2.34)]:
                        self.cyl("grab_mount",(end*11.08,yy,zz),0.040,0.03,"metal","X")
                for y in (side*1.03,side*1.32):
                    self.cyl("marker_housing",(end*11.065,y,1.97),0.115,0.055,"metal","X")
                    self.cyl("marker_dark_lens",(end*11.098,y,1.97),0.087,0.020,"black","X")
            self.front("upper_lamp_housing",end,[(-.35,4.14),(.35,4.14),(.43,4.41),(-.43,4.41)],"metal",0.018)
            self.front("upper_lamp_insert",end,[(-.29,4.17),(.29,4.17),(.34,4.38),(-.34,4.38)],"black",0.025)
            for side in (-1,1):
                self.front("brow_vent",end,[(side*.48,4.11),(side*1.12,4.07),(side*.54,4.39)],"dark",.024)
                if self.lod == 0:
                    for i in range(9):
                        z=4.10+i*.029
                        outer=1.04-i*.055
                        self.front_rod("brow_vent_slat",end,(side*.53,z),(side*outer,z),.009,"metal",.034)
            # Full-height lower pilot, central coupler and anti-climber bars.
            self.box("end_sill",(end*10.98,0,1.44),(.18,3.0,.28),"dark",.02)
            self.front_rect("nose_lower_grey",end,0,1.68,2.96,.20,"dark",.024)
            self.poly("pilot",[(end*11.04,-1.45,1.32),(end*11.04,1.45,1.32),
                      (end*11.15,1.25,.25),(end*11.15,-1.25,.25)],[(0,1,2,3)],"dark",normal=(end,0,0))
            for side in (-1,1):
                for z in (1.59,1.68):
                    self.rod("anti_climber",(end*11.13,side*.22,z),(end*11.13,side*1.08,z),.026)
            self.box("coupler_shank",(end*11.30,0,1.04),(.52,.20,.23),"dark",.022)
            self.box("coupler_knuckle",(end*11.58,.06,1.04),(.24,.34,.36),"metal",.035)
            if self.lod == 0:
                for sy in (-.57,.57):
                    self.rod("air_hose_upper",(end*11.18,sy,1.18),(end*11.34,sy,.87),.036,"black")
                    self.rod("air_hose_lower",(end*11.34,sy,.87),(end*11.29,sy+.10,.69),.036,"black")
                    self.box("air_hose_valve",(end*11.18,sy,1.19),(.10,.15,.05),"yellow")
                for i in range(-3,4):
                    y=i*.23
                    self.poly("pilot_warning",[(end*11.166,y-.10,.29),(end*11.166,y+.04,.29),
                              (end*11.14,y+.25,.57),(end*11.14,y+.11,.57)],[(0,1,2,3)],"yellow",normal=(end,0,0))
            for side in (-1,1):
                # Door and cab window shapes, inset rubber seals and metal handrails.
                self.side_rect("cab_door",side,end*8.80,2.55,.86,1.90,"roof",.025)
                self.side_rect("cab_door_blue",side,end*8.80,2.55,.81,1.85,"blue",.031)
                for cx,w in [(end*9.61,.42),(end*8.91,.50)]:
                    z=3.32
                    self.side_rect("side_window_seal",side,cx,z,w+.07,.84,"black",.040)
                    self.side_rect("side_window",side,cx,z,w,.75,"glass_transparent",.048)
                if self.lod == 0:
                    for dx in (-.51,.51):
                        x=end*8.80+dx
                        self.rod("door_rail",(x,side*1.71,1.72),(x,side*1.71,3.50),.018)
                    self.rod("door_handle",(end*8.55,side*1.715,2.40),(end*8.73,side*1.715,2.40),.020)
                    for z in (.52,.81,1.10,1.39):
                        self.box("cab_step",(end*8.80,side*1.55,z),(.62,.31,.055),"metal",.009)

    def sides(self):
        for side in (-1,1):
            # Six banks of real horizontal louvers, rather than eight plain slots.
            for i in range(6):
                x=-6.45+i*.65
                self.side_rect("louver_recess",side,x,2.88,.58,1.47,"black",.032)
                count=21 if self.lod==0 else 9
                for j in range(count):
                    z=2.21+j*(1.34/(count-1))
                    self.box("louver_slat",(x,side*1.70,z),(.54,.085,.035 if self.lod==0 else .06),"blue")
                self.box("louver_stile",(x-.30,side*1.70,2.89),(.022,.08,1.54),"light_blue")
            for x in (4.1,4.84):
                self.side_rect("service_door_seam",side,x,2.95,.68,1.40,"roof",.029)
                self.side_rect("service_door",side,x,2.95,.63,1.35,"blue",.035)
                if self.lod==0:
                    self.rod("service_handle",(x+.23,side*1.72,2.92),(x+.23,side*1.72,3.12),.012)
            self.side_rect("small_access_panel",side,-7.65,2.55,.61,.47,"roof",.027)
            self.side_rect("small_access_blue",side,-7.65,2.55,.57,.43,"blue",.034)
            for x,w in [(-1.7,.75),(.25,.22),(1.60,.20),(7.6,.55),(-7.75,.55)]:
                self.side_rect("upper_side_vent",side,x,4.055,w,.26,"black",.023)

    def roof_module(self, name, x, length, z0, z1, mat="roof", half=1.25):
        verts=[(x-length/2,-half,z0),(x-length/2,half,z0),(x-length/2,half*.86,z1),(x-length/2,-half*.86,z1),
               (x+length/2,-half,z0),(x+length/2,half,z0),(x+length/2,half*.86,z1),(x+length/2,-half*.86,z1)]
        return self.poly(name,verts,[(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],mat,solid=True)

    def roof(self):
        # Separate grey removable sections and two unlike ventilation arrangements.
        for x,length,height in [(-8.55,1.65,4.55),(-1.20,4.0,4.56),(5.30,3.45,4.58),(8.55,1.6,4.55)]:
            self.roof_module("roof_section",x,length,4.42,height)
        self.roof_module("cooler_shroud",-5.60,3.30,4.42,4.52,"roof")
        self.box("cooler_grille_dark",(-5.60,0,4.54),(3.18,2.20,.028),"black")
        # Fan disks sit BELOW the grille. They are not exposed roof ornaments.
        if self.lod==0:
            for x in (-6.32,-4.86):
                self.cyl("concealed_fan",(x,0,4.556),.59,.012,"dark","Z")
                self.cyl("concealed_fan_hub",(x,0,4.562),.11,.013,"metal","Z")
        for i in range(29 if self.lod==0 else 11):
            x=-7.15+i*(3.10/(28 if self.lod==0 else 10))
            self.box("cooler_grille_bar",(x,0,4.585),(.018,2.18,.018),"metal")
        for y in (-1.12,-.55,0,.55,1.12):
            self.box("cooler_grille_rail",(-5.6,y,4.589),(3.22,.025,.025),"roof")
        self.roof_module("exhaust_fairing",-1.70,1.28,4.54,4.65,"roof",.55)
        self.box("exhaust_recess",(-1.70,0,4.657),(.70,.73,.018),"black")
        self.box("exhaust_outlet",(-1.70,0,4.67),(.40,.41,.12),"dark",.015)
        for x in (-.25,.70,1.55):
            self.box("roof_access_cover",(x,0,4.57),(.76,1.75,.055),"roof",.015)
        # Arched cross-roof mesh screen over a separate equipment opening.
        self.box("cross_vent_recess",(2.85,0,4.49),(1.52,2.35,.022),"black")
        count=21 if self.lod==0 else 7
        for i in range(count):
            y=-1.20+i*2.40/(count-1)
            z=4.60-.19*(abs(y)/1.20)**2
            self.rod("cross_vent_mesh",(2.15,y,z),(3.55,y,z),.009,"metal")
        for x in (2.13,2.60,3.10,3.57):
            for a,b in [(-1.20,-.60),(-.60,0),(0,.60),(.60,1.20)]:
                self.rod("cross_vent_rib",(x,a,4.62-.19*(abs(a)/1.2)**2),
                         (x,b,4.62-.19*(abs(b)/1.2)**2),.025,"roof")
        for x in (-8.66,8.66):
            self.box("cab_ac_unit",(x,0,4.55),(.82,1.05,.22),"metal",.07)
        if self.lod==0:
            for x in (-8.0,-3.4,.1,4.0,5.7,6.5,8.0):
                for y in (-.92,.92):
                    self.rod("roof_lift_eye",(x-.065,y,4.59),(x+.065,y,4.64),.015,"dark")
            for x in (-9.0,9.0):
                self.cyl("radio_base",(x,.6,4.58),.08,.09,"dark","Z")
                self.rod("radio_aerial",(x,.6,4.62),(x,.6,4.85),.013,"black")

    def underframe(self):
        self.box("underframe",(0,0,1.47),(21.7,3.20,.27),"dark",.025)
        self.box("fuel_tank",(0,0,.86),(4.1,2.1,.80),"dark",.12)
        for x in (-2.8,2.8):
            self.box("equipment_case",(x,0,1.04),(1.30,2.32,.61),"dark",.045)
        for side in (-1,1):
            for x in (-2.8,-1.75,-.65,.65,1.75,2.8):
                self.box("underframe_access",(x,side*1.19,1.04),(.9,.04,.52),"dark",.02)
                if self.lod==0:
                    self.box("case_lock",(x+.29,side*1.22,1.19),(.04,.025,.065),"metal")
                    self.box("warning_plate",(x,side*1.615,1.54),(.055,.012,.07),"yellow")

    def bogie(self,index,center):
        group=bpy.data.objects.new(f"b{index}_grp",None)
        bpy.context.collection.objects.link(group)
        group.location=(center,0,0)
        frame=[]
        for side in (-1,1):
            frame.append(self.box("bogie_sideframe",(0,side*1.10,.97),(4.70,.20,.29),"dark",.06,group))
            for axle in (-1.8,0,1.8):
                frame.append(self.box("axlebox",(axle,side*1.07,.64),(.36,.34,.33),"dark",.05,group))
                frame.append(self.cyl("axlebox_cap",(axle,side*1.255,.64),.13,.04,"metal","Y",group))
                if self.lod==0:
                    for dx in (-.30,.30):
                        frame.append(self.cyl("primary_spring",(axle+dx,side*1.11,.91),.095,.24,"metal","Z",group))
                        for z in (.82,.88,.94,1.00):
                            frame.append(self.cyl("spring_coil",(axle+dx,side*1.11,z),.105,.021,"dark","Z",group))
                    frame.append(self.rod("brake_link",(axle-.48,side*1.23,.42),(axle+.45,side*1.23,.42),.025,"metal",group))
            for x in (-.90,.90):
                frame.append(self.cyl("secondary_spring",(x,side*1.07,1.28),.18,.34,"dark","Z",group))
            if self.lod==0:
                frame.append(self.rod("traction_link",(-1.3,side*1.29,1.05),(1.3,side*1.29,1.16),.045,"metal",group))
        for x in (-1.8,0,1.8):
            frame.append(self.box("bogie_crossmember",(x,0,1.05),(.27,2.28,.28),"dark",.02,group))
            frame.append(self.box("traction_motor",(x+.3,0,.68),(.45,1.25,.38),"dark",.05,group))
        self.g.join_objects(frame,f"b{index}",group)
        for i,x in enumerate((1.8,0,-1.8),start=1):
            pieces=[self.cyl("axle",(x,0,WHEEL_RADIUS),.11,2.10,"metal","Y",group)]
            for side in (-1,1):
                pieces.append(self.cyl("wheel_tread",(x,side*WHEEL_TREAD_CENTER,WHEEL_RADIUS),WHEEL_RADIUS,.14,"metal","Y",group))
                pieces.append(self.cyl("wheel_disc",(x,side*.825,WHEEL_RADIUS),.525,.035,"dark","Y",group))
                pieces.append(self.cyl("wheel_flange",(x,side*.685,WHEEL_RADIUS),.645,.025,"dark","Y",group))
            wheel=self.g.join_objects(pieces,f"w{(index-1)*3+i}",group)
            wheel["tread_center_spacing_m"]=2*WHEEL_TREAD_CENTER
        return group

    def text(self,name,value,loc,size,rot,mat="white",cn=False):
        # Flat glyphs avoid the extruded, heavily decimated v0.1 lettering.
        bpy.ops.object.text_add(location=loc,rotation=rot)
        obj=bpy.context.object
        obj.name=name
        obj.data.body=value
        obj.data.align_x="CENTER"
        obj.data.align_y="CENTER"
        obj.data.size=size
        obj.data.extrude=0
        obj.data.resolution_u=2
        font=r"C:\Windows\Fonts\simkai.ttf" if cn else r"C:\Windows\Fonts\arialbd.ttf"
        try:
            obj.data.font=bpy.data.fonts.load(font)
        except RuntimeError:
            pass
        obj.data.materials.append(self.mat(mat))
        bpy.ops.object.convert(target="MESH")
        return obj

    def markings(self):
        for side in (-1,1):
            rot=(math.pi/2,0,math.pi if side>0 else 0)
            self.text("side_fuxing","复 兴",(-.95,side*1.724,2.82),.66,rot,"yellow",True)
            self.text("side_number","FXN5C 0051",(2.00,side*1.725,2.80),.45,rot)
            if self.lod==0:
                for end in (-1,1):
                    self.text("cab_number","FXN5C 0051",(end*9.2,side*1.72,2.51),.17,rot)
                    self.text("cab_depot","上局沪段",(end*9.2,side*1.723,2.29),.17,rot,cn=True)
        for end in (-1,1):
            rot=(math.pi/2,0,end*math.pi/2)
            self.text("nose_number","FXN5C 0051",(end*11.077,0,1.83),.20,rot)
            self.text("nose_fuxing","复       兴",(end*11.076,0,2.12),.24,rot,cn=True)
            # Stylised China Railway emblem, modeled as ring + T/rail motif.
            for i in range(25):
                a=math.radians(-55+i*290/25)
                b=math.radians(-55+(i+1)*290/25)
                self.front_rod("railway_emblem",end,(.19*math.cos(a),2.16+.21*math.sin(a)),
                               (.19*math.cos(b),2.16+.21*math.sin(b)),.018,"yellow",.045)
            self.front_rod("emblem_bar",end,(-.085,2.19),(.085,2.19),.021,"yellow")
            self.front_rod("emblem_stem",end,(0,2.19),(0,1.99),.021,"yellow")
            self.front_rod("emblem_base",end,(-.075,1.99),(.075,1.99),.021,"yellow")

    def lights(self):
        white=self.g.emissive_material("train_all_lights",(1,.88,.65,1),2)
        red=self.g.emissive_material("train_red_lights",(1,.015,.008,1),2)
        groups={n:[] for n in ("headlights_fwd","taillights_fwd","headlights_bwd","taillights_bwd")}
        for end in (-1,1):
            head="headlights_fwd" if end>0 else "headlights_bwd"
            tail="taillights_bwd" if end>0 else "taillights_fwd"
            for side in (-1,1):
                for name,y,r,mat in [(head,side*1.32,.083,white),(tail,side*1.03,.080,red)]:
                    obj=self.cyl("lamp",(end*11.118,y,1.97),r,.015,"white","X")
                    self.g.assign_material(obj,mat)
                    groups[name].append(obj)
                z=4.27
                obj=self.cyl("top_lamp",(end*(self.front_x(z)+.028),side*.15,z),.097,.024,"white","X")
                obj.rotation_euler[1]=end*(math.pi/2-math.atan(.38/.46))
                self.g.assign_material(obj,white)
                groups[head].append(obj)
        for name,objs in groups.items():
            self.g.join_objects(objs,name)


def build(lod, gen, builder_class=Builder):
    b=builder_class(lod,gen)
    b.hull()
    b.underframe()
    b.livery()
    if lod<2:
        b.cabs()
        b.sides()
        b.roof()
        b.markings()
        b.lights()
    else:
        for end in (-1,1):
            b.front_rect("distant_windows",end,0,3.30,2.55,1.30,"glass_transparent")
    # Wheels and pivoting frames are retained at every LOD.
    b.bogie(1,gen.BOGIE_CENTERS[0])
    b.bogie(2,gen.BOGIE_CENTERS[1])
