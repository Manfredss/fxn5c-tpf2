"""FXN5C v0.4: open cab shell, layered glazing and mechanical close-up detail.

Photo/video referenced proportions, NOT surveyed manufacturer CAD. Cabin controls
are an explicitly approximate interior because a verified FXN5C desk plan is absent.
"""
import math
from collections import Counter
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody, build as build_body
from geometry_v03 import DetailBuilder


def rounded_rect(cx,cy,w,h,r,n=8):
    r=min(r,w/2,h/2)
    out=[]
    for x,y,a in [(cx+w/2-r,cy+h/2-r,0),(cx-w/2+r,cy+h/2-r,90),
                  (cx-w/2+r,cy-h/2+r,180),(cx+w/2-r,cy-h/2+r,270)]:
        for i in range(n+1):
            t=math.radians(a+i*90/n)
            out.append((x+r*math.cos(t),y+r*math.sin(t)))
    return out


class PrecisionBuilder(DetailBuilder):
    def bevel(self,obj,width=.012,segments=3):
        bpy.context.view_layer.objects.active=obj
        mod=obj.modifiers.new("manufactured_edge_radius","BEVEL")
        mod.width=width; mod.segments=segments; mod.limit_method="ANGLE"
        bpy.ops.object.modifier_apply(modifier=mod.name)
        for p in obj.data.polygons:
            p.use_smooth=True
        # Large sheet faces remain flat while their real beveled edges interpolate.
        mod=obj.modifiers.new("weighted_surface_normals","WEIGHTED_NORMAL")
        mod.keep_sharp=True; mod.weight=50
        bpy.ops.object.modifier_apply(modifier=mod.name)
        return obj

    def box(self,name,loc,dims,mat="dark",bevel=0,parent=None):
        obj=super().box(name,loc,dims,mat,0,parent)
        if self.lod==0 and bevel:
            self.bevel(obj,min(bevel,min(dims)*.35),4)
        elif self.lod==1 and bevel:
            self.g.apply_bevel(obj,min(bevel,min(dims)*.30),2)
        return obj

    def profile(self,name,xz,y,depth,mat="graphite",parent=None):
        obj=super().profile(name,xz,y,depth,mat,parent)
        if self.lod==0:
            self.bevel(obj,.010,3)
        return obj

    def helix(self,name,center,radius,height,wire,turns,parent):
        if self.lod:
            return super().helix(name,center,radius,height,wire,turns,parent)
        pts=[]
        for i in range(round(turns*20)+1):
            t=i/(turns*20)
            a=t*turns*math.tau
            pts.append((center[0]+radius*math.cos(a),center[1]+radius*math.sin(a),center[2]-height/2+t*height))
        return self.tube(name,pts,wire,"spring_steel",parent,sides=10)

    def sheet(self,name,loop,mapper,mat,depth=0,axis=(1,0,0)):
        verts=[mapper(u,v) for u,v in loop]
        if not depth:
            return self.poly(name,verts,[tuple(range(len(verts)))],mat,normal=axis)
        n=len(verts); shift=Vector(axis)*depth
        verts += [tuple(Vector(v)-shift) for v in verts]
        faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        return self.poly(name,verts,faces,mat,solid=True)

    def rim(self,name,outer,inner,mapper,mat,depth=.020,axis=(1,0,0)):
        n=len(outer); assert len(inner)==n
        front=[mapper(u,v) for u,v in outer+inner]
        verts=front+[tuple(Vector(p)-Vector(axis)*depth) for p in front]
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces += [(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),
                      (i,2*n+i,2*n+j,j),(n+i,n+j,3*n+j,3*n+i)]
        obj=self.poly(name,verts,faces,mat,solid=True)
        return obj

    def cut(self,target,cutter):
        bpy.context.view_layer.objects.active=target
        mod=target.modifiers.new("true_aperture","BOOLEAN")
        mod.operation="DIFFERENCE"; mod.solver="EXACT"; mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter,do_unlink=True)

    def hull(self):
        BaseBody.hull(self)
        shell=bpy.data.objects["body_shell_v02"]
        shell.name="body_open_shell_v04"
        if self.lod==2:
            return
        inner=shell.copy(); inner.data=shell.data.copy()
        bpy.context.collection.objects.link(inner)
        for v in inner.data.vertices:
            v.co.x*=.993
            v.co.y*=.947
            v.co.z=3.03+(v.co.z-3.03)*.945
        self.cut(shell,inner)
        for end in (-1,1):
            for side in (-1,1):
                front=rounded_rect(side*.61,3.34,1.075,1.055,.055)
                self.cut(shell,self.sheet("window_cutter",front,
                    lambda u,v,e=end:(e*(self.front_x(v)+.35),u,v),"black",.70,(end,0,0)))
                for x,w in ((end*9.61,.42),(end*8.91,.50)):
                    loop=rounded_rect(x,3.32,w,.75,.075)
                    self.cut(shell,self.sheet("window_cutter",loop,
                        lambda u,v,s=side:(u,s*(self.side_y(u,v)+.35),v),"black",.70,(0,side,0)))
        self.bevel(shell,.018,4 if self.lod==0 else 2)
        shell["true_window_apertures"]=12
        shell["shell_wall_m_approx"]=.075

    def livery(self):
        super().livery()
        # Painted bands are almost flush instead of thick separate appliqué plates.
        for obj in list(bpy.context.scene.objects):
            if obj.type=="MESH" and obj.name.startswith(("cyan_sweep","gold_sweep","roof_seam")):
                for v in obj.data.vertices:
                    sign=1 if v.co.y>=0 else -1
                    v.co.y=sign*(self.side_y(v.co.x,v.co.z)+.002)

    def glass(self,name,loop,mapper,axis,material="glass_transparent"):
        obj=self.sheet(name,loop,mapper,material,axis=axis)
        obj["transparent_pane"]=True
        return obj

    def markings(self):
        before=set(bpy.context.scene.objects)
        super().markings()
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith(("railway_emblem","emblem_bar","emblem_stem","emblem_base")):
                bpy.data.objects.remove(obj,do_unlink=True)
        # The nose emblem is painted, not a tubular metal ornament.
        for end in (-1,1):
            verts=[]; faces=[]
            steps=64 if self.lod==0 else 24
            for i in range(steps+1):
                a=math.radians(-55+i*290/steps)
                for ry,rz in ((.208,.228),(.172,.192)):
                    z=2.16+rz*math.sin(a)
                    verts.append((end*(self.front_x(z)+.003),ry*math.cos(a),z))
            for i in range(steps):
                faces.append((2*i,2*i+2,2*i+3,2*i+1))
            self.poly("painted_railway_emblem",verts,faces,"yellow",normal=(end,0,0))
            self.front_rect("painted_emblem_bar",end,0,2.19,.205,.039,"yellow",.003)
            self.front_rect("painted_emblem_stem",end,0,2.09,.039,.20,"yellow",.003)
            self.front_rect("painted_emblem_base",end,0,1.99,.190,.039,"yellow",.003)

    def cabs(self):
        before=set(bpy.context.scene.objects)
        super().cabs()
        remove=("windscreen", "window_seal", "sun_blind", "side_window", "cab_door", "wiper_", 
                "marker_", "upper_lamp_", "door_handle", "door_rail", "cab_step", "coupler_", "pilot")
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith(remove):
                bpy.data.objects.remove(obj,do_unlink=True)
        for end in (-1,1):
            front=lambda u,v,e=end:(e*(self.front_x(v)+.016),u,v)
            self.rim("windshield_surround",rounded_rect(0,3.31,2.70,1.45,.060),
                     rounded_rect(0,3.34,2.35,1.105,.045),front,"roof",.045,(end,0,0))
            self.front_rect("windshield_centre_pillar",end,0,3.33,.095,1.20,"roof",.019)
            for side in (-1,1):
                cy=side*.61
                self.rim("windscreen_gasket",rounded_rect(cy,3.34,1.125,1.105,.064),
                         rounded_rect(cy,3.34,1.075,1.055,.055),
                         lambda u,v,e=end:(e*(self.front_x(v)+.028),u,v),"black",.025,(end,0,0))
                self.glass("cab_front_glass",rounded_rect(cy,3.34,1.078,1.058,.055),
                           lambda u,v,e=end:(e*(self.front_x(v)+.009),u,v),(end,0,0))
                self.front_rect("interior_sun_visor",end,cy,3.81,1.01,.10,"cab_lining",-.053)
                if self.lod==0:
                    # Articulated two-link wiper with blade carrier and pivots.
                    self.front_rod("wiper_primary_arm",end,(cy*.64,2.77),(cy+.20,2.98),.013,"metal",.075)
                    self.front_rod("wiper_parallel_arm",end,(cy*.64+.035,2.78),(cy+.235,2.995),.009,"black",.077)
                    self.front_rod("wiper_blade",end,(cy-.12,3.13),(cy+.40,2.88),.018,"black",.083)
                    self.cyl("wiper_pivot",(end*(self.front_x(2.77)+.058),cy*.64,2.77),.034,.024,"graphite","X")
                mapper=lambda u,v,s=side:(u,s*(self.side_y(u,v)+.015),v)
                self.rim("cab_door_reveal",rounded_rect(end*8.80,2.77,.865,2.25,.07),
                         rounded_rect(end*8.80,2.77,.842,2.227,.062),mapper,"black",.012,(0,side,0))
                for x,w in ((end*9.61,.42),(end*8.91,.50)):
                    self.rim("side_window_outer_frame",rounded_rect(x,3.32,w+.085,.835,.10),
                             rounded_rect(x,3.32,w+.025,.775,.085),mapper,"graphite",.026,(0,side,0))
                    self.rim("side_window_rubber",rounded_rect(x,3.32,w+.026,.776,.085),
                             rounded_rect(x,3.32,w,.750,.075),
                             lambda u,v,s=side:(u,s*(self.side_y(u,v)+.027),v),"black",.018,(0,side,0))
                    self.glass("cab_side_glass",rounded_rect(x,3.32,w+.003,.753,.075),
                               lambda u,v,s=side:(u,s*(self.side_y(u,v)+.008),v),(0,side,0))
                if self.lod==0:
                    for dx in (-.51,.51):
                        x=end*8.80+dx
                        self.tube("continuous_door_grab",[(x,side*1.658,1.75),(x,side*1.72,1.79),
                                  (x,side*1.72,3.45),(x,side*1.659,3.49)],.017,"metal",sides=12)
                        for z in (1.75,3.49):
                            self.cyl("door_grab_foot",(x,side*1.661,z),.034,.018,"metal","Y")
                    for z in (2.04,2.48):
                        self.cyl("door_hinge_barrel",(end*8.43,side*1.675,z),.027,.10,"metal","Z")
                    self.box("door_latch_plate",(end*8.64,side*1.678,2.45),(.060,.014,.16),"metal",.009)
                    self.rod("door_handle",(end*8.64,side*1.713,2.47),(end*8.82,side*1.713,2.47),.014)
                    for z in (.54,.81,1.08,1.35):
                        for dx in (-.28,.28):
                            self.box("step_side_bracket",(end*8.80+dx,side*1.52,z),(.035,.32,.072),"graphite",.005)
                        for j in range(7):
                            self.box("step_open_grating",(end*8.80,side*(1.37+j*.044),z),(.60,.013,.023),"metal",.003)
            self.lamp_housings(end)
            self.coupler(end)
            self.interior(end)

    def lamp_housings(self,end):
        # Recessed bowls, retaining rings, separate transparent lenses and LED emitters.
        top=rounded_rect(0,4.27,.78,.31,.045)
        self.sheet("upper_lamp_casting",top,lambda u,v:(end*(self.front_x(v)+.018),u,v),"roof",.055,(end,0,0))
        for side in (-1,1):
            for y,z,r in ((side*1.32,1.97,.088),(side*1.03,1.97,.085),(side*.15,4.27,.093)):
                fx=self.front_x(z)
                mapping=lambda u,v,e=end:(e*(self.front_x(v)+.042),u,v)
                circle=lambda rad:[(y+rad*math.cos(a*math.tau/48),z+rad*math.sin(a*math.tau/48)) for a in range(48)]
                self.sheet("lamp_recessed_bucket",circle(r*1.26),
                           lambda u,v,e=end:(e*(self.front_x(v)+.014),u,v),"black",.055,(end,0,0))
                self.rim("lamp_retaining_ring",circle(r*1.22),circle(r),mapping,"metal",.036,(end,0,0))
                self.sheet("lamp_reflector",circle(r*.96),
                           lambda u,v,e=end:(e*(self.front_x(v)+.027),u,v),"metal",axis=(end,0,0))
                self.glass("lamp_lens",circle(r*.99),lambda u,v,e=end:(e*(self.front_x(v)+.053),u,v),(end,0,0),"lamp_glass")
                if self.lod==0:
                    for a in (45,135,225,315):
                        t=math.radians(a)
                        self.bolt("lamp_ring_screw",(end*(fx+.066),y+r*1.11*math.cos(t),z+r*1.11*math.sin(t)),.008,"X")

    def coupler(self,end):
        # Thick folded pilot with an actual central coupler opening.
        contour=[(-1.44,1.33),(1.44,1.33),(1.40,.48),(1.20,.26),(-1.20,.26),(-1.40,.48)]
        pilot=self.sheet("folded_steel_pilot",contour,lambda y,z:(end*11.10,y,z),"graphite",.055,(end,0,0))
        cutter=self.box("coupler_aperture_cutter",(end*11.1,0,1.05),(.5,.62,.50),"black",.04)
        self.cut(pilot,cutter)
        if self.lod==0:
            self.bevel(pilot,.007,3)
        for i in range(-3,4):
            y=i*.23
            self.sheet("pilot_warning",[(y-.10,.29),(y+.04,.29),(y+.25,.57),(y+.11,.57)],
                       lambda u,v:(end*11.159,u,v),"yellow",axis=(end,0,0))
        self.box("coupler_drawbar",(end*11.24,0,1.04),(.49,.20,.24),"coupler_steel",.03)
        # Molded knuckle profile and a dark throat, visibly different from a box.
        yz=[(-.18,.89),(.06,.87),(.19,.95),(.20,1.15),(.10,1.22),(-.12,1.21),(-.20,1.12)]
        knuckle=self.sheet("coupler_cast_knuckle",yz,lambda y,z:(end*11.69,y,z),"coupler_steel",.28,(end,0,0))
        self.bevel(knuckle,.025,4 if self.lod==0 else 2)
        self.box("coupler_throat",(end*11.702,-.05,1.06),(.008,.19,.16),"black",.025)
        self.cyl("knuckle_pin",(end*11.56,.09,1.07),.043,.38,"coupler_steel","Z")
        if self.lod==0:
            for side in (-1,1):
                self.tube("cut_lever",[(end*11.21,side*.15,1.30),(end*11.21,side*.85,1.30),
                          (end*11.21,side*1.05,1.18)],.015,"metal",sides=10)
                self.box("pilot_bolt_plate",(end*11.165,side*.91,.78),(.02,.20,.10),"graphite",.012)
                self.bolt("pilot_bolt",(end*11.185,side*.91,.78),.023,"X")

    def interior(self,end):
        before=set(bpy.context.scene.objects)
        # Only the volume visible through the two cab ends is populated.
        self.box("cab_floor",(end*9.33,0,1.78),(2.28,2.91,.07),"cab_floor",.02)
        self.box("cab_bulkhead",(end*8.19,0,2.98),(.07,2.90,2.36),"cab_lining",.035)
        self.box("cab_inner_door",(end*8.238,0,2.76),(.025,.63,1.83),"console",.035)
        self.box("cab_ceiling",(end*9.10,0,4.30),(1.79,2.43,.05),"cab_lining",.045)
        self.box("desk_pedestal",(end*10.09,0,2.17),(.64,2.55,.70),"console",.06)
        self.box("desk_worktop",(end*10.06,0,2.56),(.79,2.64,.10),"console",.065)
        for side in (-1,1):
            y=side*.70
            self.cyl("seat_pedestal",(end*9.26,y,2.02),.11,.41,"graphite","Z")
            self.box("seat_cushion",(end*9.26,y,2.25),(.49,.49,.13),"seat_fabric",.065)
            self.box("seat_backrest",(end*9.01,y,2.62),(.13,.48,.63),"seat_fabric",.065)
            self.box("seat_headrest",(end*8.99,y,3.02),(.14,.32,.16),"seat_fabric",.06)
            self.box("instrument_housing",(end*10.03,y,2.75),(.14,.54,.30),"graphite",.032)
            self.box("instrument_screen",(end*9.949,y,2.75),(.012,.43,.22),"screen",.012)
            if self.lod==0:
                for j in range(6):
                    self.box("display_bar",(end*9.939,y-.16+j*.060,2.744),(.006,.025,.018+j*.010),"screen_mark")
                for offset in (-.25,.25):
                    self.box("seat_armrest",(end*9.22,y+offset,2.52),(.39,.048,.060),"black",.02)
                    self.rod("armrest_support",(end*9.01,y+offset,2.30),(end*9.01,y+offset,2.52),.013)
                self.cyl("controller_base",(end*9.82,y-.28,2.62),.045,.09,"black","Z")
                self.rod("controller_lever",(end*9.82,y-.28,2.65),(end*9.78,y-.28,2.79),.012)
                self.box("controller_grip",(end*9.78,y-.28,2.80),(.08,.04,.04),"black",.017)
                for j in range(5):
                    self.cyl("desk_button",(end*9.89,y-.17+j*.078,2.625),.014,.018,
                             "red_paint" if j==0 else "white","Z")
                self.box("desk_footrest",(end*9.91,y,1.96),(.12,.34,.05),"metal",.014)
        if self.lod==0:
            self.box("radio_unit",(end*9.97,0,2.76),(.11,.26,.13),"black",.015)
            for y in (-.075,.075):
                self.cyl("radio_knob",(end*9.902,y,2.76),.022,.025,"metal","X")
            self.cyl("extinguisher",(end*8.39,1.16,2.13),.095,.52,"red_paint","Z")
            self.box("cab_notice_board",(end*8.237,-.96,3.03),(.016,.30,.38),"white",.01)
            self.rod("bulkhead_door_handle",(end*8.263,.23,2.76),(end*8.263,.23,2.91),.014)
        for obj in set(bpy.context.scene.objects)-before:
            if obj.type=="MESH":
                obj["cab_interior"]=True

    def sides(self):
        super().sides()
        if self.lod!=0:
            return
        # Continuous fine panel edges, hardware and inspection labels on the sheet.
        for side in (-1,1):
            for x in (4.1,4.84):
                for z in (2.40,3.45):
                    self.box("service_hinge",(x-.27,side*1.69,z),(.033,.032,.095),"blue",.007)
                    self.cyl("service_hinge_pin",(x-.27,side*1.713,z),.012,.12,"metal","Z")
                for z in (2.30,3.58):
                    self.bolt("service_panel_fastener",(x+.26,side*1.704,z),.010)
            for i in range(6):
                x=-6.45+i*.65
                for dx in (-.28,.28):
                    for z in (2.15,3.60):
                        self.bolt("louver_frame_fastener",(x+dx,side*1.744,z),.010)
                self.box("louver_bottom_latch",(x,side*1.724,2.11),(.15,.015,.045),"blue",.008)
            for x in (-7.55,7.55):
                self.side_rect("manufacturer_plate",side,x,1.76,.46,.11,"metal",.025)
            rot=(math.pi/2,0,math.pi if side>0 else 0)
            for x in (-5.1,5.1):
                self.text("technical_stencil","自重 150t   换长 2.0",(x,side*1.676,1.73),.044,rot,cn=True)

    def roof_module(self,name,x,length,z0,z1,mat="roof",half=1.25):
        obj=super().roof_module(name,x,length,z0,z1,mat,half)
        if self.lod==0:
            self.bevel(obj,.018,4)
        return obj

    def roof(self):
        super().roof()
        if self.lod!=0:
            return
        # Replace coarse grille rods with a real close-spaced crossed mesh.
        for obj in list(bpy.context.scene.objects):
            if obj.name.startswith(("cooler_grille_bar","cooler_grille_rail","cross_vent_mesh")):
                bpy.data.objects.remove(obj,do_unlink=True)
        for i in range(61):
            self.box("radiator_long_wire",(-7.13+i*.051,0,4.586),(.008,2.17,.008),"graphite")
        for i in range(39):
            self.box("radiator_cross_wire",(-5.60,-1.06+i*.056,4.592),(3.16,.008,.008),"graphite")
        for x in (-7.20,-5.60,-4.00):
            self.box("radiator_mesh_frame",(x,0,4.596),(.025,2.22,.025),"roof",.005)
        for y in (-1.12,1.12):
            self.box("radiator_edge_frame",(-5.60,y,4.596),(3.23,.025,.025),"roof",.005)
        for i in range(43):
            y=-1.2+i*2.4/42
            z=4.60-.19*(abs(y)/1.20)**2
            self.rod("cross_vent_fine_wire",(2.15,y,z),(3.55,y,z),.006,"graphite")
        for i in range(25):
            x=2.15+i*1.40/24
            pts=[(x,y,4.605-.19*(abs(y)/1.2)**2) for y in (-1.20,-.9,-.6,-.3,0,.3,.6,.9,1.2)]
            self.tube("cross_vent_transverse_wire",pts,.006,"graphite",sides=6)
        for x,length in ((-8.55,1.65),(-1.20,4.0),(5.30,3.45),(8.55,1.60)):
            for side in (-1,1):
                for i in range(max(4,round(length/.40))):
                    self.bolt("roof_cover_screw",(x-length/2+.10+i*(length-.20)/(max(4,round(length/.40))-1),side*1.18,4.567),.011,"Z")
        for x in (-8.66,8.66):
            for j in range(10):
                self.box("ac_condenser_slot",(x-.34+j*.075,-.529,4.59),(.025,.009,.080),"black")
        for x in (-1.90,-1.51):
            self.cyl("exhaust_pipe_lip",(x,0,4.710),.125,.04,"graphite","Z")
            self.cyl("exhaust_pipe_dark_core",(x,0,4.733),.098,.009,"black","Z")

    def lights(self):
        groups={n:[] for n in ("headlights_fwd","taillights_fwd","headlights_bwd","taillights_bwd")}
        for end in (-1,1):
            head="headlights_fwd" if end>0 else "headlights_bwd"
            tail="taillights_bwd" if end>0 else "taillights_fwd"
            for side in (-1,1):
                for name,y,z,r,mat in ((head,side*1.32,1.97,.073,"lamp_white"),
                                     (tail,side*1.03,1.97,.070,"lamp_red"),
                                     (head,side*.15,4.27,.078,"lamp_white")):
                    # Emitters sit behind their glass. Native polygon offset resolves depth ordering.
                    circle=[(y+r*math.cos(i*math.tau/48),z+r*math.sin(i*math.tau/48)) for i in range(48)]
                    obj=self.sheet("lamp_emitter",circle,lambda u,v,e=end:(e*(self.front_x(v)+.037),u,v),mat,axis=(end,0,0))
                    groups[name].append(obj)
        for name,objs in groups.items():
            self.g.join_objects(objs,name)


def build(lod,gen):
    build_body(lod,gen,PrecisionBuilder)
    if lod<2:
        # Preserve separately sorted panes and interior in the native hierarchy.
        panes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("transparent_pane")]
        inner=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("cab_interior")]
        gen.join_objects(inner,"cab_interior")
        # Each pane remains independent for camera-distance sorting, not one whole-train glass mesh.
        for i,obj in enumerate(panes):
            obj.name=f"glazing_{i:02d}"
        bpy.context.scene["glazing_count"]=len(panes)
        bpy.context.scene["cab_openings"]=12
