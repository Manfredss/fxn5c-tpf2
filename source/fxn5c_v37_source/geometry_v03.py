"""FXN5C running gear refinement.

Evidence: TrainNets Yang Li photos yl08/09/10/11 and the existing 0051 photos.
The general form is photo-referenced. Mounting dimensions, fastener count,
hidden motor/gearcase internals and pipe routes remain visual estimates.
No Workshop mesh, texture or source code is reused.
"""
import math
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BodyBuilder, build as build_body


class DetailBuilder(BodyBuilder):
    def text(self,name,value,loc,size,rot,mat="white",cn=False):
        if name in {"cab_number","cab_depot"}:
            # Keep both small cab markings below the descending cyan ribbon.
            height=2.30 if name=="cab_number" else 2.10
            loc=(math.copysign(9.62,loc[0]),loc[1],height)
        obj=super().text(name,value,loc,size,rot,mat,cn)
        if name in {"side_fuxing","side_number","cab_number","cab_depot"}:
            # Paint-like glyphs follow the tapered cab/body surface instead of
            # floating 7 cm off the sheet metal and casting an artificial shadow.
            bpy.context.view_layer.update()
            tf=obj.matrix_world.copy()
            inv=tf.inverted()
            sign=1 if loc[1]>0 else -1
            for vertex in obj.data.vertices:
                p=tf @ vertex.co
                p.y=sign*(self.side_y(p.x,p.z)+.008)
                vertex.co=inv @ p
        return obj

    def cyl(self,name,loc,radius,depth,mat="metal",axis="Y",parent=None):
        obj=super().cyl(name,loc,radius,depth,mat,axis,parent)
        for face in obj.data.polygons:
            face.use_smooth=len(face.vertices)==4
        return obj

    def tube(self,name,points,radius,mat="graphite",parent=None,sides=8):
        """A continuous tube, not a chain of intersecting cylinder objects."""
        points=[Vector(p) for p in points]
        verts=[]
        for i,p in enumerate(points):
            tangent=points[min(i+1,len(points)-1)]-points[max(0,i-1)]
            tangent.normalize()
            reference=Vector((0,0,1)) if abs(tangent.z)<.92 else Vector((1,0,0))
            u=tangent.cross(reference).normalized()
            v=tangent.cross(u).normalized()
            for j in range(sides):
                angle=2*math.pi*j/sides
                verts.append(tuple(p+radius*(math.cos(angle)*u+math.sin(angle)*v)))
        faces=[]
        for i in range(len(points)-1):
            for j in range(sides):
                faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
        faces += [tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))]
        obj=self.poly(name,verts,faces,mat,solid=True,parent=parent)
        for face in obj.data.polygons[:-2]:
            face.use_smooth=True
        return obj

    def helix(self,name,center,radius,height,wire,turns,parent):
        if self.lod>0:
            return self.cyl(name,center,radius+wire,height,"spring_steel","Z",parent)
        steps=round(turns*12)
        points=[]
        for i in range(steps+1):
            t=i/steps
            a=t*turns*2*math.pi
            points.append((center[0]+radius*math.cos(a),center[1]+radius*math.sin(a),center[2]-height/2+t*height))
        return self.tube(name,points,wire,"spring_steel",parent,sides=6)

    def profile(self,name,xz,y,depth,mat="graphite",parent=None):
        n=len(xz)
        verts=[(x,y+offset,z) for offset in (-depth/2,depth/2) for x,z in xz]
        faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
        faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        return self.poly(name,verts,faces,mat,solid=True,parent=parent)

    def bolt(self,name,loc,r=.026,axis="Y",parent=None):
        rotation={"Y":(math.pi/2,0,0),"Z":(0,0,0),"X":(0,math.pi/2,0)}[axis]
        obj=self.g.add_cylinder(name,loc,r,.025,self.mat("spring_steel"),6,rotation,parent)
        return obj

    def lathe_y(self,name,x,profile,mat,parent):
        """Turned wheel/dished motor cover with a (axial y, radius) profile."""
        segments=48 if self.lod==0 else 16 if self.lod==1 else 10
        verts=[(x+r*math.cos(2*math.pi*j/segments),y,.625+r*math.sin(2*math.pi*j/segments))
               for y,r in profile for j in range(segments)]
        faces=[]
        for i in range(len(profile)-1):
            for j in range(segments):
                faces.append((i*segments+j,i*segments+(j+1)%segments,(i+1)*segments+(j+1)%segments,(i+1)*segments+j))
        faces += [tuple(range(segments-1,-1,-1)),tuple((len(profile)-1)*segments+j for j in range(segments))]
        obj=self.poly(name,verts,faces,mat,solid=True,parent=parent)
        for face in obj.data.polygons[:-2]:
            face.use_smooth=True
        if name=="dished_wheel":
            # Only the running surface is polished. The broad wheel web is
            # painted/oxidised steel in the real close-ups, not a chrome disk.
            obj.data.materials.append(self.mat("graphite"))
            for i in range(len(profile)-1):
                if (profile[i][1]+profile[i+1][1])/2 < .607:
                    for face in obj.data.polygons[i*segments:(i+1)*segments]:
                        face.material_index=1
            for face in obj.data.polygons[-2:]:
                face.material_index=1
        return obj

    def wheelset(self,index,x,parent):
        parts=[self.cyl("wheel_axle",(x,0,.625),.105,2.16,"graphite","Y",parent)]
        for side in (-1,1):
            # Wheel tread centred over the 1.435 m track, flanges face inward.
            profile=[(.670,.135),(.670,.59),(.680,.645),(.700,.645),(.713,.625),
                     (.797,.625),(.817,.608),(.825,.565),(.798,.485),(.785,.265),(.842,.165),(.86,.13)]
            if self.lod==2:
                profile=[(.68,.13),(.68,.645),(.71,.625),(.81,.625),(.825,.13)]
            parts.append(self.lathe_y("dished_wheel",x,[(side*y,r) for y,r in profile],"wheel_steel",parent))
            # Dark recessed wheel centre and small raised bearing shoulder.
            parts.append(self.cyl("wheel_centre",(x,side*.804,.625),.29,.020,"graphite","Y",parent))
        obj=self.g.join_objects(parts,f"w{index}",parent)
        obj["tread_center_spacing_m"]=1.50
        return obj

    def bogie(self,index,center):
        group=bpy.data.objects.new(f"b{index}_grp",None)
        bpy.context.collection.objects.link(group)
        group.location=(center,0,0)
        frame=[]
        add=frame.append
        axles=(-1.8,0,1.8)
        if self.lod==2:
            for side in (-1,1):
                add(self.box("distant_bogie_beam",(0,side*1.12,1.14),(4.65,.22,.25),"graphite",parent=group))
                for x in axles:
                    add(self.box("distant_axlebox",(x,side*1.16,.65),(.37,.29,.34),"graphite",parent=group))
            add(self.box("distant_bolster",(0,0,1.17),(.55,2.35,.30),"graphite",parent=group))
        else:
            for side in (-1,1):
                y=side*1.15
                # Deep box girder with tapered ends; springs/axleboxes remain visible underneath.
                contour=[(-2.45,1.30),(-2.12,1.43),(2.12,1.43),(2.45,1.30),
                         (2.32,1.14),(.42,1.12),(.28,1.01),(-.28,1.01),(-.42,1.12),(-2.32,1.14)]
                add(self.profile("cast_side_beam",contour,y,.24,parent=group))
                add(self.box("beam_lower_flange",(0,y,1.14),(4.53,.32,.05),"graphite",.012,group))
                # Pipe carried on the upper outside of the real side frame.
                if self.lod==0:
                    add(self.tube("bogie_air_main",[(-2.22,side*1.32,1.39),(-1.72,side*1.32,1.40),
                            (.95,side*1.32,1.40),(1.85,side*1.32,1.35),(2.25,side*1.25,1.23)],.017,"ochre",group))
                    for x in (-1.9,-.90,0,.95,1.85):
                        add(self.box("pipe_clip",(x,side*1.33,1.40),(.035,.035,.11),"graphite",parent=group))
                for x in axles:
                    # U-shaped axlebox pedestal, paired substantial coil springs, steel seats.
                    add(self.profile("axlebox_cradle",[(x-.61,.61),(x-.61,.52),(x+.61,.52),(x+.61,.61),
                            (x+.24,.67),(x+.18,.86),(x-.18,.86),(x-.24,.67)],y,.31,parent=group))
                    add(self.box("axlebox_housing",(x,side*1.18,.69),(.35,.35,.35),"graphite",.055,group))
                    add(self.cyl("axlebox_seal",(x,side*1.365,.70),.117,.035,"black","Y",group))
                    add(self.cyl("axlebox_cover",(x,side*1.389,.70),.095,.027,"graphite","Y",group))
                    for dx in (-.42,.42):
                        add(self.cyl("spring_lower_seat",(x+dx,y,.605),.167,.052,"graphite","Z",group))
                        add(self.cyl("spring_upper_seat",(x+dx,y,1.095),.165,.055,"graphite","Z",group))
                        add(self.helix("primary_coil",(x+dx,y,.85),.125,.392,.029,5,group))
                    add(self.box("axlebox_guide",(x,side*1.21,1.02),(.14,.18,.29),"graphite",.018,group))
                    if self.lod==0:
                        for angle in (45,135,225,315):
                            a=math.radians(angle)
                            add(self.bolt("bearing_cover_bolt",(x+.065*math.cos(a),side*1.416,.70+.065*math.sin(a)),.020,parent=group))
                        # Visible vertical shock body and flexible axle sensor lead.
                        add(self.rod("damper_chrome_rod",(x-.17,side*1.43,.78),(x-.17,side*1.43,1.28),.022,"wheel_steel",group))
                        add(self.rod("damper_body",(x-.17,side*1.43,.79),(x-.17,side*1.43,1.05),.045,"graphite",group))
                        add(self.tube("axle_sensor_lead",[(x,side*1.39,.76),(x+.08,side*1.44,.91),
                            (x+.13,side*1.38,1.18),(x+.28,side*1.31,1.35)],.012,"black",group,sides=6))
                # Photo yl09: a broad longitudinal arm terminates in a stacked rubber bush.
                for direction in (-1,1):
                    a=direction*.18
                    b=direction*1.02
                    add(self.profile("traction_arm",[(a,.98),(a,1.10),(b,1.06),(b,.94)],side*1.44,.13,parent=group))
                    for x in (a,b):
                        add(self.cyl("traction_bush_lower",(x,side*1.44,.935),.15,.08,"black","Z",group))
                        add(self.cyl("traction_bush_upper",(x,side*1.44,1.095),.15,.065,"black","Z",group))
                        add(self.cyl("traction_bush_cap",(x,side*1.44,1.137),.143,.030,"graphite","Z",group))
                        if self.lod==0:
                            add(self.bolt("traction_pivot_bolt",(x,side*1.44,1.162),.040,"Z",group))
                for x in (-.90,.90):
                    add(self.cyl("secondary_mount",(x,side*.88,1.45),.18,.18,"black","Z",group))
                # End equipment box and rounded cable exits, seen above the outer wheel corners.
                for x in (-2.03,2.03):
                    add(self.box("bogie_terminal_box",(x,side*1.36,1.04),(.45,.26,.40),"graphite",.022,group))
                    add(self.box("terminal_lid",(x,side*1.503,1.04),(.42,.025,.36),"graphite",.014,group))
                    if self.lod==0:
                        for dx in (-.16,.16):
                            for z in (.91,1.17):
                                add(self.bolt("terminal_screw",(x+dx,side*1.522,z),.013,parent=group))
            for x in axles:
                add(self.box("transom",(x+.43,0,1.18),(.27,2.29,.24),"graphite",.025,group))
                # Axle-hung traction motor: cylindrical housing, vented end plate and gear cover.
                add(self.cyl("traction_motor_casing",(x+.32,0,.70),.39,1.20,"graphite","Y",group))
                for side in (-1,1):
                    add(self.cyl("motor_endplate",(x+.32,side*.625,.70),.37,.05,"graphite","Y",group))
                    add(self.cyl("motor_bearing",(x+.32,side*.66,.70),.10,.06,"spring_steel","Y",group))
                    if self.lod==0:
                        for j in range(10):
                            a=j*math.tau/10
                            cx=x+.32+.268*math.cos(a)
                            z=.70+.268*math.sin(a)
                            # Dark slots and narrow web ribs suggest the visible vented cover.
                            vent=self.box("motor_air_slot",(cx,side*.653,z),(.105,.018,.09),"black",.008,group)
                            vent.rotation_euler.y=-a
                            add(vent)
                            add(self.bolt("motor_flange_bolt",(x+.32+.34*math.cos(a),side*.67,.70+.34*math.sin(a)),.018,parent=group))
                add(self.cyl("axle_gearcase",(x,-.46,.625),.31,.22,"graphite","Y",group))
                add(self.box("gearcase_bridge",(x+.14,-.46,.63),(.38,.22,.42),"graphite",.08,group))
                for side in (-1,1):
                    # Simplified tread-brake shoe: not a disc brake borrowed from an electric locomotive.
                    for direction in (-1,1):
                        xx=x+direction*.565
                        shoe=self.box("tread_brake_shoe",(xx,side*.75,.84),(.09,.13,.25),"graphite",.018,group)
                        shoe.rotation_euler.y=direction*math.radians(20)
                        add(shoe)
                        add(self.rod("brake_hanger",(xx,side*.87,.85),(xx,side*.87,1.16),.025,"graphite",group))
                    if self.lod==0:
                        add(self.cyl("brake_actuator",(x+.51,side*.93,1.12),.105,.22,"graphite","X",group))
            if self.lod==0:
                for side in (-1,1):
                    for sign in (-1,1):
                        # Sand pipe tip ends ahead of the outer wheel, safely above the rail head.
                        add(self.tube("sand_pipe",[(sign*2.18,side*1.12,1.10),(sign*2.29,side*1.10,.72),
                            (sign*2.37,side*.77,.31),(sign*2.31,side*.75,.14)],.028,"black",group))
                    label=self.text("bogie_service_stencil","转向架禁止用水冲洗",(0,side*1.285,1.295),.065,
                                    (math.pi/2,0,math.pi if side>0 else 0),cn=True)
                    label.parent=group
                    add(label)
                add(self.cyl("centre_pivot",(0,0,1.37),.36,.28,"graphite","Z",group))
        from collections import Counter
        categories=Counter(obj.name.split(".")[0] for obj in frame)
        frame_obj=self.g.join_objects(frame,f"b{index}",group)
        for category,count in categories.items():
            frame_obj["component_"+category]=count
        for i,x in enumerate((1.8,0,-1.8),start=1):
            self.wheelset((index-1)*3+i,x,group)
        return group

    def underframe(self):
        if self.lod==2:
            self.box("distant_chassis",(0,0,1.45),(21.7,3.18,.27),"graphite")
            self.box("distant_fuel_case",(0,0,.85),(4.4,2.5,.80),"graphite")
            return
        self.box("chassis_sill",(0,0,1.48),(21.75,3.22,.25),"graphite",.018)
        self.box("main_fuel_tank",(0,0,.82),(4.4,2.40,.77),"graphite",.10)
        for side in (-1,1):
            # Six louvered access covers and two transverse reservoirs, based on yl02.
            for x in (-1.8,-1.05,-.30,.80,1.55,2.30):
                self.box("battery_box",(x,side*1.28,.87),(.69,.32,.63),"graphite",.026)
                self.box("battery_lid",(x,side*1.46,.88),(.63,.025,.55),"graphite",.014)
                if self.lod==0:
                    for z in (.77,.83,.89):
                        self.box("battery_vent",(x,side*1.482,z),(.22,.016,.023),"black")
                    for dx in (-.245,.245):
                        self.box("battery_hinge",(x+dx,side*1.49,1.00),(.045,.030,.13),"spring_steel",.007)
                    self.rod("battery_latch",(x,side*1.503,1.02),(x,side*1.503,1.12),.014,"spring_steel")
            if self.lod==0:
                self.tube("underframe_airline",[(-3.95,side*1.45,1.30),(-2.5,side*1.45,1.30),
                    (2.7,side*1.45,1.30),(3.7,side*1.30,1.18)],.022,"ochre")
                self.cyl("fuel_filler",(.18,side*1.47,.78),.105,.035,"graphite","Y")
                self.cyl("fuel_cap",(.18,side*1.50,.78),.075,.022,"spring_steel","Y")
                self.rod("fuel_sight_glass",(.18,side*1.50,.97),(.18,side*1.50,1.32),.018,"metal")
                for x in (-9.4,-7.5,-4,0,4,7.5,9.4):
                    self.box("sill_warning",(x,side*1.62,1.54),(.08,.012,.08),"yellow")
                for x in (-6.7,6.7):
                    # Body-side lifting point and brake indicator, not attached to the rotating frame.
                    self.cyl("lifting_recess",(x,side*1.626,1.46),.080,.023,"black","Y")
                    self.cyl("lifting_rim",(x,side*1.640,1.46),.104,.018,"graphite","Y")
                    self.cyl("lifting_hole",(x,side*1.652,1.46),.072,.020,"black","Y")
                for end in (-1,1):
                    for j in range(3):
                        self.box("brake_indicator_frame",(end*9.80+j*.105,side*1.57,1.48),(.08,.02,.10),"white")
                        self.box("brake_indicator",(end*9.80+j*.105,side*1.584,1.48),(.056,.012,.05),"ochre" if j<2 else "light_blue")
        for x in (-3.27,-2.59):
            self.cyl("air_reservoir",(x,0,.83),.30,2.58,"graphite","Y")
            for side in (-1,1):
                self.cyl("reservoir_domed_end",(x,side*1.295,.83),.287,.06,"graphite","Y")
            if self.lod==0:
                for y in (-.90,.90):
                    self.cyl("reservoir_strap",(x,y,.83),.308,.04,"spring_steel","Y")
                self.rod("reservoir_drain",(x,.45,.55),(x,.45,.43),.020,"ochre")


def build(lod,gen):
    build_body(lod,gen,DetailBuilder)
