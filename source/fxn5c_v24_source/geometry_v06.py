"""v0.6: angular windscreen, roof equipment and end air-pipe assemblies.

Photo-referenced visual reconstruction; sizes and hidden pipe routing are estimates.
All added geometry is original. The supplied scale-model photo is secondary evidence.
"""
import math
from collections import Counter
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody, build as build_body
from geometry_v04 import rounded_rect
from geometry_v05 import BodyDetailBuilder


def chamfer_polygon(corners, distance=.012):
    """Two straight segments at each corner: no large circular window corners."""
    points=[Vector(p) for p in corners]
    result=[]
    for i,p in enumerate(points):
        for adjacent in (points[i-1],points[(i+1)%len(points)]):
            delta=adjacent-p
            result.append(tuple(p+delta.normalized()*min(distance,delta.length*.2)))
    return result


def front_loop(side, expand=0):
    # Slight inward rake of the outer edge; inner edges remain straight.
    corners=[(.070-expand,2.810-expand),(1.200+expand,2.810-expand),
             (1.115+expand,3.890+expand),(.070-expand,3.890+expand)]
    points=chamfer_polygon(corners,.012)
    return [(side*y,z) for y,z in points]


def smooth_path(points, steps=7):
    """Centrally tangent Catmull-Rom path for a hanging flexible hose."""
    p=[Vector(v) for v in points]
    out=[]
    for i in range(len(p)-1):
        a,b,c,d=p[max(0,i-1)],p[i],p[i+1],p[min(len(p)-1,i+2)]
        for j in range(steps):
            t=j/steps
            out.append(tuple(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)))
    return out+[tuple(p[-1])]


class FrontRoofBuilder(BodyDetailBuilder):
    def box(self,name,loc,dims,mat="dark",bevel=0,parent=None):
        # Millimetre-scale sheet hardware needs a highlight edge, not four
        # subdivisions on every corner. Do not alter inherited v0.5 parts.
        simple={"ac_intake_fin","pilot_step_grating","radiator_captive_tab","ac_side_walkway_bar",
                "coupling_claw_lug","roof_eye_pad_v06","anti_climber_vertical_web",
                "ac_grating_crossmember","anti_climber_folded_shelf","end_pipe_mounting_plate",
                "cock_handle_root","pilot_step_frame","roof_access_base","roof_access_lid_v06",
                "radiator_screen_crossframe","radiator_screen_sideframe","roof_recessed_pull"}
        if name not in simple:
            return super().box(name,loc,dims,mat,bevel,parent)
        obj=BaseBody.box(self,name,loc,dims,mat,0,parent)
        if bevel:
            width=min(bevel,min(dims)*.30)
            self.bevel(obj,width,1)
        return obj

    def feature(self,obj,name):
        obj["detail_v06_component"]=name
        return obj

    def hull(self):
        BaseBody.hull(self)
        shell=bpy.data.objects["body_shell_v02"]
        shell.name="body_open_shell_v06"
        if self.lod==2: return
        inner=shell.copy(); inner.data=shell.data.copy()
        bpy.context.collection.objects.link(inner)
        for v in inner.data.vertices:
            v.co.x*=.993; v.co.y*=.947
            v.co.z=3.03+(v.co.z-3.03)*.945
        self.cut(shell,inner)
        for end in (-1,1):
            for side in (-1,1):
                self.cut(shell,self.sheet("angular_window_cutter",front_loop(side,.004),
                    lambda u,v,e=end:(e*(self.front_x(v)+.35),u,v),"black",.70,(end,0,0)))
                for x,w in ((end*9.61,.42),(end*8.91,.50)):
                    self.cut(shell,self.sheet("side_window_cutter",rounded_rect(x,3.32,w,.75,.075),
                        lambda u,v,s=side:(u,s*(self.side_y(u,v)+.35),v),"black",.70,(0,side,0)))
        self.bevel(shell,.009,3 if self.lod==0 else 2)
        shell["true_window_apertures"]=12
        self.feature(shell,"angular_aperture_shell")

    def cabs(self):
        before=set(bpy.context.scene.objects)
        super().cabs()
        remove=("windshield_surround","windshield_centre_pillar","windscreen_gasket",
                "cab_front_glass","interior_sun_visor","wiper_","air_hose_","anti_climber")
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith(remove): bpy.data.objects.remove(obj,do_unlink=True)
        for end in (-1,1):
            mapper=lambda y,z,e=end:(e*(self.front_x(z)+.016),y,z)
            outer=chamfer_polygon([(-1.392,2.635),(1.392,2.635),(1.335,3.985),(-1.335,3.985)],.020)
            inner=chamfer_polygon([(-1.224,2.784),(1.224,2.784),(1.141,3.919),(-1.141,3.919)],.012)
            self.feature(self.rim("angular_windshield_surround",outer,inner,mapper,"roof",.035,(end,0,0)),"angular_surround")
            self.front_rect("straight_centre_mullion",end,0,3.350,.100,1.170,"roof",.020)
            self.front_rect("mullion_metal_bead",end,0,3.350,.016,1.122,"spring_steel",.024)
            for side in (-1,1):
                self.rim("angular_glazing_reveal",front_loop(side,.030),front_loop(side,-.001),
                         lambda y,z,e=end:(e*(self.front_x(z)+.018),y,z),"black",.080,(end,0,0))
                self.rim("angular_windscreen_bead",front_loop(side,.037),front_loop(side,.022),
                         lambda y,z,e=end:(e*(self.front_x(z)+.030),y,z),"spring_steel",.012,(end,0,0))
                self.rim("angular_windscreen_gasket",front_loop(side,.023),front_loop(side,-.002),
                         lambda y,z,e=end:(e*(self.front_x(z)+.034),y,z),"black",.020,(end,0,0))
                self.feature(self.glass("angular_front_glass",front_loop(side,.001),
                             lambda y,z,e=end:(e*(self.front_x(z)+.012),y,z),(end,0,0)),"angular_front_pane")
                self.front_rect("front_sun_visor",end,side*.590,3.830,.950,.092,"cab_lining",-.055)
                if self.lod==0:
                    # Parked low on the glass, with flat arms and rubber blade backs.
                    cy=side*.610
                    for offset,radius,mat in ((0,.009,"spring_steel"),(.026,.006,"metal")):
                        self.front_rod("parked_wiper_arm",end,(side*.17+offset,2.720),(cy+.09+offset,2.835),radius,mat,.067)
                    self.front_rod("parked_wiper_spine",end,(cy-.33,2.880),(cy+.37,2.817),.009,"spring_steel",.074)
                    self.front_rod("parked_wiper_rubber",end,(cy-.35,2.863),(cy+.39,2.800),.008,"black",.063)
                    self.cyl("wiper_drive_cap_v06",(end*(self.front_x(2.720)+.056),side*.17,2.720),.025,.027,"graphite","X")
                    for y in (side*1.29,):
                        for z in (2.687,3.942):
                            self.cyl("surround_recessed_screw",(end*(self.front_x(z)+.019),y,z),.006,.004,"spring_steel","X")
            # Real anti-climber plates, rather than isolated round bars.
            for side in (-1,1):
                for z in (1.586,1.685):
                    self.box("anti_climber_folded_shelf",(end*11.130,side*.64,z),(.155,.91,.026),"graphite",.006)
                for y in (.23,.64,1.07):
                    self.box("anti_climber_vertical_web",(end*11.115,side*y,1.635),(.118,.024,.205),"graphite",.005)

    def ring(self,name,center,radius,wire,mat="metal",axis="Z"):
        count=24 if self.lod==0 else 12
        points=[]
        for i in range(count+1):
            a=i*math.tau/count
            u,v=radius*math.cos(a),radius*math.sin(a)
            offset={"X":(0,u,v),"Y":(u,0,v),"Z":(u,v,0)}[axis]
            points.append(tuple(center[j]+offset[j] for j in range(3)))
        return self.tube(name,points,wire,mat,sides=8 if self.lod==0 else 6)

    def coupler(self,end):
        before=set(bpy.context.scene.objects)
        super().coupler(end)
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith("cut_lever"): bpy.data.objects.remove(obj,do_unlink=True)
        # Existing knuckle/pilot retained; add its carrier, locking linkage and piping.
        self.box("drawgear_carrier",(end*11.27,0,.863),(.40,.48,.050),"coupler_steel",.012)
        for side in (-1,1):
            self.box("carrier_bearing_cheek",(end*11.29,side*.226,1.015),(.18,.054,.28),"coupler_steel",.010)
            if self.lod==0:
                for z in (.90,1.12):
                    self.bolt("carrier_mount_bolt",(end*11.397,side*.224,z),.018,"X")
                self.box("end_pipe_mounting_plate",(end*11.167,side*.63,1.256),(.035,.65,.17),"graphite",.006)
                for y in (.36,.91):
                    self.bolt("end_pipe_mount_bolt",(end*11.191,side*y,1.295),.014,"X")
            for idx,y in enumerate((side*.48,side*.82)):
                z=1.225 if idx==0 else 1.255
                self.rod("fixed_brake_pipe",(end*11.072,y,z+.108),(end*11.267,y,z+.108),.019,"graphite")
                self.rod("angle_cock_body",(end*11.258,y,z+.096),(end*11.305,y,z-.010),.033,"metal")
                self.feature(self.cyl("angle_cock_union",(end*11.274,y,z+.074),.038,.041,"spring_steel","X"),"angle_cock")
                self.cyl("cock_spindle",(end*11.310,y-.034,z+.030),.018,.10,"metal","Y")
                self.box("cock_handle_root",(end*11.316,y-.087,z+.028),(.050,.018,.038),"red_paint",.005)
                self.rod("cock_coloured_lever",(end*11.316,y-.087,z+.028),(end*11.380,y-.087,z+.114),.011,
                         "red_paint" if idx==0 else "yellow")
                low=.46 if idx==0 else .635
                pts=[(11.314,y,z-.015),(11.365,y,z-.17),(11.405,y+side*.012,low+.19),
                     (11.420,y+side*.046,low+.046),(11.385,y+side*.105,low)]
                path=smooth_path([(end*x,yy,zz) for x,yy,zz in pts],7 if self.lod==0 else 3)
                self.feature(self.tube("flexible_air_hose",path,.026 if idx==0 else .023,"black",
                                     sides=12 if self.lod==0 else 8),"air_hose")
                # Crimp sleeves are coaxial with the hose ends, not floating collars.
                for pos in (0,-1):
                    p=Vector(path[pos]); toward=Vector(path[1 if pos==0 else -2]); direction=(toward-p).normalized()
                    self.rod("hose_crimp_sleeve",p-direction*.007,p+direction*.054,.033,"metal")
                    if self.lod==0:
                        for shift in (.004,.020,.039):
                            self.rod("hose_ferrule_band",p+direction*shift,p+direction*(shift+.009),.035,"spring_steel")
                p=Vector(path[-1])
                self.box("air_hose_claw_coupling",(p.x+end*.013,p.y+side*.035,p.z),(.072,.108,.053),"metal",.012)
                self.cyl("hose_coupling_rubber_seal",(p.x+end*.054,p.y+side*.036,p.z),.027,.009,"black","X")
                self.ring("coupling_sealing_face",(p.x+end*.061,p.y+side*.036,p.z),.030,.006,"metal","X")
                if self.lod==0:
                    for dz in (-.031,.031):
                        self.box("coupling_claw_lug",(p.x+end*.044,p.y+side*.052,p.z+dz),(.058,.026,.016),"metal",.004)
                    self.tube("hose_retaining_wire",[(end*11.192,y+side*.09,1.19),
                              (end*11.290,y+side*.15,.99),(p.x+end*.02,p.y+side*.035,p.z+.026)],.0035,"spring_steel",sides=6)
            # An outer electrical jumper hangs on its parking socket.
            jp=[(11.16,side*1.01,1.37),(11.23,side*1.24,1.36),(11.25,side*1.29,1.20),
                (11.27,side*1.29,.94),(11.24,side*1.20,.88),(11.20,side*1.16,1.03)]
            self.feature(self.tube("parked_end_jumper",smooth_path([(end*x,y,z) for x,y,z in jp],6 if self.lod==0 else 2),
                                  .016,"black",sides=10 if self.lod==0 else 6),"end_jumper")
            for y,z in ((side*1.01,1.37),(side*1.16,1.03)):
                self.cyl("jumper_socket",(end*11.17,y,z),.034,.065,"graphite","X")
                self.ring("jumper_socket_lock_ring",(end*11.210,y,z),.031,.005,"metal","X")
            if self.lod==0:
                # Perforated standing tread at each bottom pilot corner.
                self.box("pilot_step_frame",(end*11.24,side*1.215,.278),(.25,.28,.028),"graphite",.006)
                for j in range(6):
                    self.box("pilot_step_grating",(end*11.244,side*(1.105+j*.044),.296),(.24,.015,.013),"metal",.002)
        if self.lod==0:
            self.tube("coupler_release_crossbar",[(end*11.213,-1.02,1.35),(end*11.225,-.83,1.405),
                      (end*11.245,0,1.405),(end*11.225,.83,1.405),(end*11.213,1.02,1.35)],.012,"graphite",sides=10)
            for y in (-.91,.91):
                self.ring("release_lever_bearing",(end*11.225,y,1.386),.021,.007,"metal","Y")
            for i in range(6):
                self.ring("coupler_lock_link",(end*(11.27+i*.038),.015,1.398-i*.024),.021,.0045,
                          "coupler_steel","X" if i%2 else "Y")
            self.cyl("knuckle_pin_cap",(end*11.56,.09,1.276),.047,.022,"spring_steel","Z")
            self.rod("lock_link_attachment",(end*11.460,.015,1.259),(end*11.560,.090,1.267),.009,"coupler_steel")

    @staticmethod
    def arch_z(y):
        y=abs(y)
        return 4.64-.055*(y/1.05)**2 if y<=1.05 else 4.585-(y-1.05)*.90

    def roof(self):
        # Built as one coherent replacement, with no stacked legacy roof hardware.
        sections=((-1.02,5.86,4.56),(5.32,3.43,4.57))
        for x,length,top in sections:
            self.roof_module("removable_roof_deck",x,length,4.43,top)
            for side in (-1,1):
                count=max(4,round(length/.45)) if self.lod==0 else 4
                for i in range(count):
                    xx=x-length/2+.09+i*(length-.18)/(count-1)
                    y=side*1.18
                    slope=(top-4.43)/.175; z=top-.105*slope
                    normal=Vector((0,side*slope,1)).normalized()
                    obj=self.cyl("seated_roof_deck_screw",Vector((xx,y,z))+normal*.003,.009,.006,"spring_steel","Z")
                    obj.rotation_euler=normal.to_track_quat("Z","Y").to_euler()
        # Flat radiator cassette: fan blades below a black open lattice.
        self.roof_module("radiator_coaming",-5.6,3.35,4.44,4.520,"roof",1.23)
        self.box("radiator_well_bottom",(-5.6,0,4.525),(3.20,2.14,.018),"black")
        for x in (-6.36,-4.84):
            self.ring("recessed_fan_shroud",(x,0,4.545),.53,.014,"graphite")
            self.cyl("radiator_fan_hub",(x,0,4.544),.100,.030,"spring_steel","Z")
            if self.lod==0:
                for i in range(9):
                    a=i*math.tau/9
                    loop=[(.09,-.036),(.46,-.13),(.51,.015),(.19,.082)]
                    verts=[(x+u*math.cos(a)-v*math.sin(a),u*math.sin(a)+v*math.cos(a),4.541+.012*u/.51) for u,v in loop]
                    self.poly("concealed_fan_blade",verts,[(0,1,2,3)],"graphite",normal=(0,0,1))
        nx,ny=(77,51) if self.lod==0 else (27,17)
        for i in range(nx):
            self.box("radiator_screen_wire",(-7.18+i*3.16/(nx-1),0,4.575),(.005,2.14,.005),"black")
        for i in range(ny):
            self.box("radiator_screen_crosswire",(-5.60,-1.07+i*2.14/(ny-1),4.580),(3.16,.005,.005),"black")
        for x in (-7.22,-5.60,-3.98):
            self.box("radiator_screen_crossframe",(x,0,4.579),(.022,2.21,.028),"roof",.004)
        for y in (-1.11,1.11):
            self.box("radiator_screen_sideframe",(-5.6,y,4.579),(3.26,.025,.028),"roof",.004)
        self.feature(bpy.data.objects["radiator_coaming"],"radiator_cassette")
        if self.lod==0:
            for x in (-6.96,-6.30,-5.62,-4.94,-4.24):
                for y in (-.85,-.30,.30,.85):
                    self.box("radiator_captive_tab",(x,y,4.586),(.037,.018,.007),"spring_steel",.002)
        # Rectangular, baffled exhaust outlet, rather than two exposed round pipes.
        self.roof_module("exhaust_mounting_fairing",-1.70,1.32,4.554,4.623,"roof",.56)
        self.box("exhaust_dark_well",(-1.70,0,4.632),(.75,.59,.018),"black")
        for y in (-.175,.175):
            self.box("rectangular_exhaust_wall",(-1.70,y,4.674),(.50,.025,.094),"coupler_steel",.006)
        for x in (-1.95,-1.45):
            self.box("rectangular_exhaust_end",(x,0,4.674),(.025,.375,.094),"coupler_steel",.006)
        for x in (-1.87,-1.70,-1.53):
            self.box("exhaust_internal_baffle",(x,0,4.681),(.018,.31,.052),"graphite",.003)
        self.feature(bpy.data.objects["exhaust_dark_well"],"rectangular_exhaust")
        # Removable, fully supported inspection lids, with small hinges/flush locks.
        for x in (-.25,.70,1.55):
            self.box("roof_access_base",(x,0,4.575),(.78,1.75,.028),"black",.008)
            self.feature(self.box("roof_access_lid_v06",(x,0,4.595),(.758,1.728,.025),"roof",.007),"roof_access_lid")
            if self.lod==0:
                for y in (-.58,.58):
                    self.cyl("roof_access_hinge",(x-.371,y,4.610),.013,.115,"spring_steel","Y")
                    self.cyl("roof_access_flush_lock",(x+.295,y,4.611),.013,.006,"spring_steel","Z")
                    self.box("roof_access_lock_slot",(x+.295,y,4.615),(.016,.003,.002),"black")
        # Curved transverse grille wraps down onto both roof shoulders.
        steps=16 if self.lod==0 else 8
        ys=sorted(set([-1.58+i*3.16/steps for i in range(steps+1)]+[-1.15,-1.05,1.05,1.15]))
        n=len(ys)
        self.poly("arched_vent_baffle",[(x,y,max(4.48-max(0,abs(y)-1.15)*1.06+.009,self.arch_z(y)-.028))
                   for x in (2.11,3.59) for y in ys],
                  [(i,i+1,n+i+1,n+i) for i in range(n-1)],"black",normal=(0,0,1))
        count=63 if self.lod==0 else 25
        for i in range(count):
            y=-1.58+i*3.16/(count-1)
            self.tube("arched_screen_longwire",[(2.13,y,self.arch_z(y)),(3.57,y,self.arch_z(y))],.004,"graphite",sides=6)
        for i in range(31 if self.lod==0 else 11):
            x=2.13+i*1.44/(30 if self.lod==0 else 10)
            self.tube("arched_screen_crosswire",[(x,y,self.arch_z(y)+.005) for y in ys],.004,"graphite",sides=6)
        for x in (2.10,2.60,3.10,3.60):
            self.feature(self.tube("arched_screen_structural_rib",[(x,y,self.arch_z(y)+.014) for y in ys],
                                  .013,"roof",sides=8),"arched_roof_rib")
        for side in (-1,1):
            self.box("arched_screen_end_flange",(2.85,side*1.584,4.115),(1.56,.024,.054),"roof",.005)
        # Long removable roof has cross-panel seams and small pressed stiffeners.
        for x in (4.11,5.26,6.41):
            self.box("roof_transverse_gasket",(x,0,4.573),(.012,2.10,.006),"black")
            for y in (-.82,.82):
                profile=[(x-.16,4.574),(x+.16,4.574),(x+.055,4.618),(x-.07,4.618)]
                self.profile("pressed_roof_stiffener",profile,y,.09,"roof")
                if self.lod==0:
                    self.box("roof_recessed_pull",(x+.13,y*.72,4.577),(.115,.043,.006),"black",.008)
                    self.rod("roof_pull_handle",(x+.09,y*.72,4.590),(x+.17,y*.72,4.590),.006,"spring_steel")
        self.cab_roof()
        # Eyes follow their actual deck, with both legs attached to a small pad.
        for x in (-8.0,-3.4,.1,4.0,5.7,6.5,8.0):
            surface=4.48
            for centre,length,top in sections:
                if abs(x-centre)<=length/2: surface=top
            for y in (-.92,.92):
                self.box("roof_eye_pad_v06",(x,y,surface+.005),(.13,.058,.010),"roof",.003)
                pts=[(x-.038,y,surface+.010),(x-.038,y,surface+.032)]
                pts += [(x+.038*math.cos(a),y,surface+.032+.038*math.sin(a)) for a in [math.pi-i*math.pi/10 for i in range(11)]]
                pts.append((x+.038,y,surface+.010))
                obj=self.tube("roof_lifting_eye_v06",pts,.007,"roof",sides=8)
                obj["body_v05_component"]="roof_lifting_eye"
        for side in (-1,1):
            for x in (-8.95,-8.25,-3.15,-2.30,-.75,.8,4.05,5.1,6.25,8.3,9.05):
                z=3.998; y=side*(self.side_y(x,z)+.020)
                obj=self.box("shoulder_cover_latch",(x,y,z),(.055,.025,.032),"blue",.007)
                obj["body_v05_component"]="shoulder_latch"

    def cab_roof(self):
        for end in (-1,1):
            x=end*8.67
            self.box("cab_roof_well_floor",(x,0,4.486),(1.64,2.05,.016),"roof",.006)
            # A low air-conditioning unit sits between angular protective fairings.
            for sign in (-1,1):
                xx=x+sign*.75
                self.roof_module("cab_roof_cross_fairing",xx,.35,4.48,4.72,"roof",1.13)
            self.feature(self.box("cab_aircon_case_v06",(x,0,4.578),(.78,1.12,.18),"metal",.020),"cab_aircon_unit")
            self.box("cab_aircon_lid_seam",(x,0,4.672),(.795,1.135,.009),"graphite",.010)
            self.box("cab_aircon_lid",(x,0,4.689),(.80,1.14,.026),"metal",.018)
            for side in (-1,1):
                self.box("ac_intake_black",(x,side*.567,4.570),(.64,.010,.10),"black",.007)
                for i in range(14 if self.lod==0 else 7):
                    xx=x-.30+i*.60/(13 if self.lod==0 else 6)
                    self.box("ac_intake_fin",(xx,side*.577,4.570),(.010,.014,.089),"graphite",.002)
                for j in range(5):
                    self.box("ac_side_walkway_bar",(x,side*(.65+j*.082),4.517),(1.30,.012,.016),"spring_steel",.002)
                for dx in (-.52,.52):
                    self.box("ac_grating_crossmember",(x+dx,side*.816,4.510),(.025,.38,.019),"roof",.003)
            if self.lod==0:
                for dx in (-.29,.29):
                    for y in (-.43,.43):
                        self.cyl("ac_lid_captive_screw",(x+dx,y,4.705),.008,.004,"spring_steel","Z")
                self.tube("roof_ac_conduit",[(x+.42,-.36,4.532),(x+.51,-.36,4.515),(x+.53,-.57,4.510)],.012,"black",sides=8)
                self.cyl("antenna_mounting_foot",(end*9.12,.60,4.500),.055,.035,"graphite","Z")
                self.rod("radio_aerial_v06",(end*9.12,.60,4.519),(end*9.12,.60,4.84),.009,"black")


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(("body_detail_","refinement_")): del bpy.context.scene[key]
    build_body(lod,gen,FrontRoofBuilder)
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("transparent_pane")]
        inner=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("cab_interior")]
        gen.join_objects(inner,"cab_interior")
        for i,obj in enumerate(panes): obj.name=f"glazing_{i:02d}"
        bpy.context.scene["glazing_count"]=len(panes)
        bpy.context.scene["cab_openings"]=12
    for tag,prefix in (("body_v05_component","body_detail_"),("detail_v06_component","refinement_")):
        counts=Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag))
        for name,count in counts.items(): bpy.context.scene[prefix+name]=count
