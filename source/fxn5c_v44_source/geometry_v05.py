"""Photo-referenced carbody refinements; retains the approved v0.4 cabs/gear.

Evidence: FXN5C 0053 in BV1W8FNzMEGd, TrainNets Yang Li close-ups, existing
0050/0051 photos. Locations remain photo estimates, not engineering drawings.
"""
import math
from collections import Counter
import bpy
from mathutils import Vector
from geometry_v02 import build as build_body
from geometry_v04 import PrecisionBuilder, rounded_rect


def lerp_table(x,points):
    if x<=points[0][0]: return points[0][1]
    for (a,u),(b,v) in zip(points,points[1:]):
        if x<=b: return u+(v-u)*(x-a)/(b-a)
    return points[-1][1]


def paint_bands(x):
    x=abs(x)
    gold=lerp_table(x,[(0,2.16),(2.8,2.09),(5.6,1.90),(8.1,1.64)])
    gtop=gold+.15*max(0,1-x/8.1)
    if x>8.1: gold=gtop=-10
    ribbon=[(2.3,3.91,3.92),(4.0,3.72,3.90),(6.0,3.26,3.61),
            (8.4,2.72,2.91),(9.4,2.53,2.67),(10.6,2.31,2.43)]
    cyan_lo=lerp_table(x,[(a,b) for a,b,c in ribbon])
    cyan_hi=lerp_table(x,[(a,c) for a,b,c in ribbon])
    if x<2.3: cyan_lo=cyan_hi=10
    return gold,gtop,cyan_lo,cyan_hi


def split_polygon(poly,fn):
    """Split a convex 3D polygon by a linear signed-distance function."""
    vals=[fn(p) for p in poly]
    if min(vals)>=-1e-8 or max(vals)<=1e-8: return [poly]
    sides=[]
    for sign in (-1,1):
        out=[]
        for i,p in enumerate(poly):
            q=poly[(i+1)%len(poly)]; a=vals[i]*sign; b=vals[(i+1)%len(poly)]*sign
            if a>=0: out.append(p)
            if (a<0<b) or (b<0<a):
                t=a/(a-b); out.append(tuple(p[j]+t*(q[j]-p[j]) for j in range(3)))
        if len(out)>=3: sides.append(out)
    return sides


class BodyDetailBuilder(PrecisionBuilder):
    def paint_mesh(self,name,side,polygons):
        """Paint follows the folded surfaces, including the diagonal waist bands."""
        verts=[]; faces=[]; mats=[]
        for poly in polygons:
            pieces=[poly]
            xmin=min(p[0] for p in poly); xmax=max(p[0] for p in poly)
            for k in (-8.4,-8.1,-6,-5.6,-4,-2.8,-2.3,0,2.3,2.8,4,5.6,6,8.1,8.4):
                if xmin<k<xmax:
                    pieces=[q for p in pieces for q in split_polygon(p,lambda v,k=k:v[0]-k)]
            for i in range(4):
                pieces=[q for p in pieces for q in split_polygon(p,lambda v,i=i:v[2]-paint_bands(v[0])[i])]
            for p in pieces:
                x=sum(v[0] for v in p)/len(p); z=sum(v[2] for v in p)/len(p)
                g0,g1,c0,c1=paint_bands(x)
                mat=2 if g0<z<g1 else 1 if c0<z<c1 else 0
                start=len(verts); verts.extend(p); faces.append(tuple(range(start,len(verts)))); mats.append(mat)
        obj=self.poly(name,verts,faces,"blue",normal=(0,side,0))
        obj.data.materials.append(self.mat("light_blue")); obj.data.materials.append(self.mat("yellow"))
        for face,mat in zip(obj.data.polygons,mats): face.material_index=mat
        obj["body_v05_component"]=name
        return obj

    def painted_panel(self,name,side,x,z,w,h,offset=.012,r=.014):
        loop=rounded_rect(x,z,w,h,r,n=4)
        return self.paint_mesh(name,side,[[(u,side*(self.side_y(u,v)+offset),v) for u,v in loop]])

    def panel_ring(self,name,side,x,z,w,h,border,mat="blue",offset=.018):
        outer=rounded_rect(x,z,w,h,.018,n=4)
        inner=rounded_rect(x,z,w-2*border,h-2*border,.009,n=4)
        mapper=lambda u,v:(u,side*(self.side_y(u,v)+offset),v)
        if mat=="blue":
            return self.paint_mesh(name,side,[[mapper(*outer[i]),mapper(*outer[(i+1)%len(outer)]),
                mapper(*inner[(i+1)%len(inner)]),mapper(*inner[i])] for i in range(len(outer))])
        obj=self.rim(name,outer,inner,mapper,mat,.005,(0,side,0))
        obj["body_v05_component"]=name
        return obj

    def flush_screw(self,name,x,side,z,offset=.025,r=.009):
        y=side*(self.side_y(x,z)+offset)
        self.cyl(name,(x,y,z),r,.007,"spring_steel","Y")
        self.box("fastener_drive_slot",(x,y+side*.004,z),(r*1.1,.003,.0025),"black")

    def louver_bank(self,side,x):
        w=.595; h=1.73; z=2.90
        obj=self.side_rect("louver_baffle_v05",side,x,z,w-.018,h-.015,"black",.004)
        obj["body_v05_component"]="louver_bank"
        self.panel_ring("louver_gasket_v05",side,x,z,w+.014,h+.014,.010,"black",.006)
        self.panel_ring("louver_folded_frame_v05",side,x,z,w,h,.023,"blue",.021)
        count=26 if self.lod==0 else 13
        pitch=(h-.074)/count
        polygons=[]
        for i in range(count):
            zz=z-h/2+.041+i*pitch
            # Folded sheet blade: a shallow sloping face, narrow return and gap.
            profile=[(.008,zz+pitch*.88),(.032,zz+pitch*.19),(.032,zz+pitch*.08),(.020,zz+pitch*.08)]
            left=x-w/2+.030; right=x+w/2-.030
            for (d,a),(e,b) in zip(profile,profile[1:]):
                polygons.append([(left,side*(1.65+d),a),(right,side*(1.65+d),a),
                                 (right,side*(1.65+e),b),(left,side*(1.65+e),b)])
        obj=self.paint_mesh("folded_louver_blades_v05",side,polygons)
        obj["blade_count"]=count
        if self.lod==0:
            for zz in (z-h/2-.017,z+h/2+.017):
                self.side_rect("louver_latch_recess",side,x,zz,.16,.013,"black",.011)
                self.box("louver_quarter_turn",(x,side*1.681,zz),(.052,.010,.009),"blue",.002)
            for zz in (2.38,3.42):
                self.cyl("louver_hinge_barrel",(x-w/2-.014,side*1.676,zz),.010,.070,"blue","Z")
            for dx in (-.26,.26):
                for zz in (2.075,3.725): self.flush_screw("louver_flush_screw",x+dx,side,zz)

    def service_door(self,side,x):
        z=2.91; w=.71; h=1.74
        self.panel_ring("service_door_gap_v05",side,x,z,w,h,.009,"black",.006)
        self.painted_panel("service_skin_v05",side,x,z,w-.024,h-.024,.010)
        self.panel_ring("service_pressing_v05",side,x,z,w-.053,h-.048,.012,"blue",.016)
        self.painted_panel("service_centre_rib",side,x,2.89,w-.067,.019,.024,.004)
        if self.lod==0:
            for zz in (2.27,3.54):
                self.painted_panel("service_hinge_leaf",side,x-.297,zz,.055,.13,.021,.005)
                self.cyl("service_hinge_pin_v05",(x-.311,side*1.682,zz),.010,.105,"blue","Z")
                self.flush_screw("service_hinge_screw",x-.284,side,zz+.044,.024,.006)
            for zz in (2.45,3.30):
                self.side_rect("recessed_door_lock",side,x+.235,zz,.073,.11,"black",.014)
                self.panel_ring("door_lock_bezel",side,x+.235,zz,.073,.11,.007,"metal",.021)
                self.box("flush_door_latch",(x+.235,side*1.679,zz),(.015,.008,.064),"spring_steel",.003)

    def shoulder_vent(self,side,x,w):
        z=4.13; h=.30
        self.side_rect("shoulder_vent_dark",side,x,z,w,h,"black",.008)
        self.panel_ring("shoulder_vent_frame",side,x,z,w+.023,h+.026,.015,"blue",.019)
        count=10 if self.lod==0 else 5
        polygons=[]
        for i in range(count):
            zz=z-h/2+.021+i*(h-.042)/(count-1)
            polygons.append([(u,side*(self.side_y(u,v)+off),v) for u,v,off in
                             [(x-w/2+.01,zz,.023),(x+w/2-.01,zz,.023),
                              (x+w/2-.01,zz+.014,.012),(x-w/2+.01,zz+.014,.012)]])
        self.paint_mesh("shoulder_vent_slats",side,polygons)

    def sides(self):
        # Replace the earlier coarse side plates completely; no stacked duplicates.
        for side in (-1,1):
            for i in range(6): self.louver_bank(side,-6.45+i*.65)
            for x in (4.1,4.84): self.service_door(side,x)
            self.panel_ring("small_access_gap_v05",side,-7.65,2.58,.64,.51,.009,"black",.008)
            self.painted_panel("small_access_skin_v05",side,-7.65,2.58,.615,.486,.012)
            # Narrow vertical grille visible behind the opposite cab on production cars.
            x=7.58; z=2.64; w=.66; h=.50
            self.side_rect("auxiliary_grille_baffle",side,x,z,w,h,"black",.004)
            self.panel_ring("auxiliary_grille_frame",side,x,z,w+.04,h+.04,.018,"blue",.021)
            for i in range(27 if self.lod==0 else 12):
                xx=x-w/2+.015+i*(w-.03)/(26 if self.lod==0 else 11)
                self.box("auxiliary_grille_fin",(xx,side*1.672,z),(.010,.027,h-.024),"blue")
            for xx,ww in [(-1.7,.75),(.25,.22),(1.60,.20),(7.6,.55),(-7.75,.55)]:
                self.shoulder_vent(side,xx,ww)
            # A restrained panel joint pattern, following removable sections.
            for xx in (-7.15,-2.92,3.67,5.27):
                self.side_rect("carbody_sheet_joint",side,xx,2.89,.004,2.01,"dark",.003)
            self.side_rect("eaves_shadow_gap",side,0,3.941,18.60,.012,"black",.007)
            self.side_rect("eaves_return_lip",side,0,3.930,18.60,.010,"blue",.020)
            # Round inspection cover visible below the main side lettering.
            x=.05; z=2.335; r=.12
            circle=lambda rad:[(x+rad*math.cos(i*math.tau/48),z+rad*math.sin(i*math.tau/48)) for i in range(48)]
            self.rim("round_inspection_seam",circle(r),circle(r-.004),
                     lambda u,v:(u,side*1.654,v),"dark",.002,(0,side,0))
            if self.lod==0:
                for xx in (-7.85,-7.45): self.flush_screw("access_panel_screw",xx,side,2.58)
                for xx in (-7.55,7.55):
                    self.side_rect("builder_plate_v05",side,xx,1.71,.46,.11,"metal",.020)
                    for zz in (1.686,1.711,1.736):
                        self.side_rect("builder_plate_engraving",side,xx+.025,zz,.29,.0025,"graphite",.024)
                rot=(math.pi/2,0,math.pi if side>0 else 0)
                for xx in (-5.1,5.1):
                    self.text("body_technical_stencil","自重 150t   换长 2.0",(xx,side*1.660,1.73),.044,rot,cn=True)
                for xx in (-6.72,6.72):
                    self.text("body_jacking_label","架车点",(xx,side*1.670,1.625),.035,rot,cn=True)

    def underframe(self):
        before=set(bpy.context.scene.objects)
        super().underframe()
        if self.lod==2: return
        remove=("battery_","fuel_filler","fuel_cap","fuel_sight_glass")
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith(remove): bpy.data.objects.remove(obj,do_unlink=True)
        for side in (-1,1):
            # Six individual lids with flush handles, hanging hasps and small vents.
            for x in (-1.8,-1.05,-.30,.80,1.55,2.30):
                self.box("body_equipment_case",(x,side*1.35,.91),(.72,.39,.78),"graphite",.022)
                obj=self.box("equipment_lid_v05",(x,side*1.557,.91),(.698,.022,.753),"graphite",.010)
                obj["body_v05_component"]="equipment_lid"
                if self.lod==0:
                    self.box("equipment_handle_recess",(x,side*1.574,1.155),(.11,.005,.033),"black",.009)
                    self.box("equipment_flush_handle",(x,side*1.580,1.158),(.076,.006,.010),"metal",.003)
                    self.box("equipment_hasps",(x-.245,side*1.585,1.18),(.051,.029,.19),"graphite",.007)
                    self.cyl("equipment_hasp_pin",(x-.245,side*1.606,1.268),.018,.073,"spring_steel","X")
                    for dx in (-.20,.20):
                        self.cyl("equipment_lid_screw",(x+dx,side*1.579,1.205),.012,.009,"metal","Y")
                    for zz in (.645,.695):
                        self.box("equipment_vent_shadow",(x,side*1.573,zz),(.205,.008,.014),"black",.005)
                        self.box("equipment_pressed_vent",(x,side*1.582,zz+.009),(.225,.023,.015),"graphite",.006)
            self.box("equipment_lower_rail",(.25,side*1.559,.493),(5.47,.032,.023),"graphite",.005)
            if self.lod==0:
                # Service neck above a long, slotted fuel-level sight gauge.
                self.cyl("fuel_neck_recess_v05",(.19,side*1.630,1.445),.102,.027,"black","Y")
                self.cyl("fuel_neck_rim_v05",(.19,side*1.650,1.445),.081,.024,"metal","Y")
                self.cyl("fuel_cap_v05",(.19,side*1.670,1.445),.065,.018,"spring_steel","Y")
                self.rod("fuel_cap_crossbar",(.14,side*1.687,1.445),(.24,side*1.687,1.445),.009,"metal")
                loop=rounded_rect(.19,.905,.12,.70,.055,n=6)
                self.sheet("fuel_level_gauge_dark",loop,lambda u,v:(u,side*1.572,v),"black",axis=(0,side,0))
                self.rim("fuel_level_gauge_bezel",loop,rounded_rect(.19,.905,.072,.638,.030,n=6),
                         lambda u,v:(u,side*1.578,v),"metal",.005,(0,side,0))
                self.box("fuel_gauge_divider",(.19,side*1.581,.905),(.070,.008,.034),"metal",.004)
                for zz in (.62,1.18):
                    self.cyl("gauge_mount_screw",(.19,side*1.584,zz),.007,.006,"graphite","Y")
                rot=(math.pi/2,0,math.pi if side>0 else 0)
                self.text("fuel_label_v05","燃油加入口",(-.22,side*1.670,1.455),.036,rot,cn=True)
                self.side_rect("fuel_warning_label",side,.40,1.445,.078,.10,"white",.029)
                self.side_rect("fuel_warning_header",side,.40,1.413,.070,.020,"red_paint",.032)
                rr=.025
                pts=[(.40+rr*math.cos(i*math.tau/24),side*1.684,1.458+rr*math.sin(i*math.tau/24)) for i in range(25)]
                self.tube("fuel_warning_symbol",pts,.003,"red_paint",sides=6)
                self.rod("fuel_warning_slash",(.381,side*1.686,1.477),(.419,side*1.686,1.439),.003,"red_paint")

    def roof(self):
        before=set(bpy.context.scene.objects)
        super().roof()
        if self.lod!=0: return
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith("roof_lift_eye"): bpy.data.objects.remove(obj,do_unlink=True)
            elif obj.name.startswith("roof_cover_screw"):
                # The old screw Z was on the flat crown, leaving edge screws
                # floating above the sloping shoulder. Seat each on its panel.
                x,y,_=obj.location
                for centre,length,top in ((-8.55,1.65,4.55),(-1.20,4.0,4.56),(5.30,3.45,4.58),(8.55,1.60,4.55)):
                    if abs(x-centre)<=length/2:
                        slope=(top-4.42)/.175
                        z=top-max(0,abs(y)-1.075)*slope
                        normal=Vector((0,math.copysign(slope,y),1)).normalized()
                        obj.location=Vector((x,y,z))+normal*.003
                        obj.scale.z*=.4
                        obj.rotation_euler=normal.to_track_quat("Z","Y").to_euler()
                        break
        # Inspection lids spanning the lower roof section need a raised coaming.
        for x in (.70,1.55):
            self.box("roof_access_coaming_v05",(x,0,4.512),(.714,1.69,.066),"roof",.008)
        for x in (-8.0,-3.4,.1,4.0,5.7,6.5,8.0):
            for y in (-.92,.92):
                surface=4.48
                for centre,length,top in ((-8.55,1.65,4.55),(-1.20,4.0,4.56),(5.30,3.45,4.58),(8.55,1.60,4.55)):
                    if abs(x-centre)<=length/2: surface=top
                z=surface+.006
                self.box("roof_lifting_pad",(x,y,z),(.16,.068,.012),"roof",.005)
                pts=[(x-.045,y,z+.005),(x-.045,y,z+.035)]
                pts += [(x+.045*math.cos(a),y,z+.035+.045*math.sin(a)) for a in [math.pi-i*math.pi/12 for i in range(13)]]
                pts.append((x+.045,y,z+.005))
                obj=self.tube("roof_lifting_eye_v05",pts,.008,"roof",sides=8)
                obj["body_v05_component"]="roof_lifting_eye"
        for x in (-.25,.70,1.55):
            self.rim("roof_access_gasket",rounded_rect(x,0,.715,1.70,.025,n=4),
                     rounded_rect(x,0,.693,1.678,.018,n=4),lambda u,v:(u,v,4.600),"black",.002,(0,0,1))
            for dx in (-.29,.29):
                for y in (-.74,.74):
                    self.cyl("roof_access_flush_screw",(x+dx,y,4.605),.010,.005,"spring_steel","Z")
                    self.box("roof_screw_drive",(x+dx,y,4.608),(.011,.0025,.002),"black")
        # Removable shoulder covers have small latch tabs along the eaves.
        for side in (-1,1):
            for x in (-8.95,-8.25,-3.15,-2.30,-.75,.8,4.05,5.1,6.25,8.3,9.05):
                z=3.998; y=side*(self.side_y(x,z)+.020)
                obj=self.box("shoulder_cover_latch",(x,y,z),(.055,.025,.032),"blue",.007)
                obj["body_v05_component"]="shoulder_latch"


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith("body_detail_"): del bpy.context.scene[key]
    build_body(lod,gen,BodyDetailBuilder)
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("transparent_pane")]
        inner=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("cab_interior")]
        gen.join_objects(inner,"cab_interior")
        for i,obj in enumerate(panes): obj.name=f"glazing_{i:02d}"
        bpy.context.scene["glazing_count"]=len(panes)
        bpy.context.scene["cab_openings"]=12
    counts=Counter(o.get("body_v05_component") for o in bpy.context.scene.objects if o.get("body_v05_component"))
    for name,count in counts.items(): bpy.context.scene["body_detail_"+name]=count
