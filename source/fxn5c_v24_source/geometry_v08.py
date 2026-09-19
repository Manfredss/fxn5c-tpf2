"""v0.8 evidence-led mechanical corrections. Original photo-estimated geometry.

Primary exterior: 0051 original, 5464 x 3648, 4084470 0.smil, CC BY 4.0.
Cross-check: same author's 0050 original; TrainNets Yang Li close-ups 08–11.
No manufacturer dimension drawing is available. No third-party mesh is used.
"""
import math
from collections import Counter
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody, build as build_body
from geometry_v03 import DetailBuilder
from geometry_v04 import rounded_rect
from geometry_v05 import split_polygon
from geometry_v06 import chamfer_polygon
from geometry_v07 import SilhouetteBuilder


def reposition_nose_grabs():
    """P01 places each grab inboard of the inner white lamp, not across its lens."""
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.name.startswith(("nose_grab_", "grab_mount")):
            continue
        if not obj.get("v08_inboard_grab"):
            center = sum((obj.matrix_world @ v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
            assert abs(center.x) > 10.8 and 1.7 < center.z < 2.4, (obj.name, center)
            obj.location.y -= .25 * (1 if center.y > 0 else -1)
            obj["v08_inboard_grab"] = True
        count += 1
    bpy.context.view_layer.update()
    return count


class EvidenceBuilder(SilhouetteBuilder):
    def __init__(self, lod, gen):
        super().__init__(lod, gen)
        self.evidence_counts = Counter()

    def evidence(self, obj, name):
        obj["detail_v08_component"] = name
        self.evidence_counts[name] += 1
        return obj

    def small_box(self, name, loc, dims, mat="graphite", bevel=.003, parent=None):
        obj = BaseBody.box(self, name, loc, dims, mat, parent=parent)
        if bevel:
            self.bevel(obj, min(bevel, min(dims)*.27), 1 if self.lod else 2)
        return obj

    def lamp_housings(self, end):
        # Shared trapezoid glazing sits OUTSIDE two separately recessed reflectors.
        outer = chamfer_polygon([(-.294,4.108),(.294,4.108),(.369,4.415),(-.369,4.415)],.014)
        inner = chamfer_polygon([(-.274,4.129),(.274,4.129),(.344,4.394),(-.344,4.394)],.012)
        self.sheet("shared_headlamp_backpan_v08", outer,
                   lambda y,z:(end*(self.front_x(z)+.012),y,z),"graphite",.035,(end,0,0))
        self.evidence(self.rim("shared_headlamp_bezel_v08",outer,inner,
                      lambda y,z:(end*(self.front_x(z)+.079),y,z),"spring_steel",.059,(end,0,0)),"shared_headlamp_bezel")
        self.evidence(self.glass("shared_headlamp_cover_v08",inner,
                      lambda y,z:(end*(self.front_x(z)+.073),y,z),(end,0,0),"lamp_glass"),"shared_headlamp_cover")
        for side in (-1,1):
            # 0051 original: OUTER marker is higher, INNER white running lamp lower.
            for y,z,r in ((side*1.32,2.055,.088),(side*1.03,1.97,.085),(side*.15,4.27,.093)):
                circle=lambda rad:[(y+rad*math.cos(a*math.tau/48),z+rad*math.sin(a*math.tau/48)) for a in range(48)]
                self.sheet("lamp_recessed_bucket_v08",circle(r*1.26),
                           lambda u,v:(end*(self.front_x(v)+.014),u,v),"black",.045,(end,0,0))
                self.rim("lamp_retaining_ring_v08",circle(r*1.22),circle(r),
                         lambda u,v:(end*(self.front_x(v)+.042),u,v),"metal",.028,(end,0,0))
                self.sheet("lamp_reflector_v08",circle(r*.96),
                           lambda u,v:(end*(self.front_x(v)+.027),u,v),"metal",axis=(end,0,0))
                self.glass("lamp_lens_v08",circle(r*.99),
                           lambda u,v:(end*(self.front_x(v)+.053),u,v),(end,0,0),"lamp_glass")
                if self.lod==0:
                    for a in (45,135,225,315):
                        t=math.radians(a)
                        self.bolt("lamp_ring_screw_v08",(end*(self.front_x(z)+.063),y+r*1.11*math.cos(t),z+r*1.11*math.sin(t)),.006,"X")

    def cabs(self):
        super().cabs()
        if self.lod == 0:
            count = reposition_nose_grabs()
            assert count == 12, count
            self.evidence_counts["inboard_nose_grab_parts"] = count
        for obj in list(bpy.context.scene.objects):
            if obj.name.startswith(("brow_vent", "front_sun_visor")):
                bpy.data.objects.remove(obj,do_unlink=True)
        for end in (-1,1):
            for side in (-1,1):
                corners=[(.47,4.105),(1.15,4.105),(.51,4.390)]
                outer=[(side*y,z) for y,z in chamfer_polygon(corners,.022)]
                inner=[(side*y,z) for y,z in chamfer_polygon([(.487,4.121),(1.095,4.121),(.521,4.365)],.012)]
                self.sheet("brow_vent_recess_v08",inner,lambda y,z:(end*(self.front_x(z)+.018),y,z),"grille_black",axis=(end,0,0))
                self.evidence(self.rim("brow_vent_flush_rim_v08",outer,inner,
                              lambda y,z:(end*(self.front_x(z)+.023),y,z),"roof",.010,(end,0,0)),"flush_brow_vent")
                for i in range(21 if self.lod==0 else 11):
                    z=4.128+i*.225/(20 if self.lod==0 else 10)
                    y0=.487+(z-4.121)*(.521-.487)/(.365-.121)
                    y1=1.095+(z-4.121)*(.521-1.095)/(.365-.121)
                    if y1-y0<.035: continue
                    self.front("brow_recessed_flat_slat_v08",end,
                               [(side*y0,z),(side*y1,z),(side*y1,z+.006),(side*y0,z+.006)],"roof",.024)
                self.front_rect("front_sun_visor_v08",end,side*.590,3.770,.950,.205,"cab_lining",-.055)
                if self.lod==0:
                    self.front_rod("sunblind_roller_v08",end,(side*.12,3.882),(side*1.06,3.882),.012,"graphite",-.065)
            self.front_rect("brow_horizontal_joint_v08",end,0,4.015,2.76,.009,"black",.025)

    def lights(self):
        groups={k:[] for k in ("headlights_fwd","taillights_fwd","headlights_bwd","taillights_bwd")}
        for end in (-1,1):
            head="headlights_fwd" if end==1 else "headlights_bwd"
            tail="taillights_bwd" if end==1 else "taillights_fwd"
            for side in (-1,1):
                for name,y,z,r,mat in ((head,side*1.03,1.97,.070,"lamp_white"),
                                      (tail,side*1.32,2.055,.073,"lamp_red"),
                                      (head,side*.15,4.27,.078,"lamp_white")):
                    circle=[(y+r*math.cos(a*math.tau/32),z+r*math.sin(a*math.tau/32)) for a in range(32)]
                    groups[name].append(self.sheet("lamp_emitter_v08",circle,
                                  lambda u,v,e=end:(e*(self.front_x(v)+.037),u,v),mat,axis=(end,0,0)))
        for name,objects in groups.items(): self.g.join_objects(objects,name)
        self.evidence_counts["corrected_directional_light_groups"] = 4

    def coupler(self,end):
        super().coupler(end)
        # Remove inherited flat diagonal stripes only at the current end.
        for obj in list(bpy.context.scene.objects):
            if obj.name.startswith("pilot_warning"):
                if sum((obj.matrix_world@v.co).x for v in obj.data.vertices)*end>0:
                    bpy.data.objects.remove(obj,do_unlink=True)
        for side in (-1,1):
            # Two plate facets meet at a protruding centre fold. Width/angle estimated.
            panel=[(0,.270),(side*1.10,.270),(side*.93,.655),(0,.655)]
            mapping=lambda y,z:(end*(11.165+.155*(.655-z)/.385-.025*abs(y)),y,z)
            self.evidence(self.sheet("folded_pilot_toe_v08",panel,mapping,"grille_black",.022,(end,0,0)),"folded_pilot_toe")
            pieces=[[(y,z,0) for y,z in panel]]
            for k in range(1,10):
                boundary=k*.165
                pieces=[q for p in pieces for q in split_polygon(p,lambda v,c=boundary:v[1]+side*v[0]*.82-c)]
            for poly in pieces:
                cy=sum(p[0] for p in poly)/len(poly); cz=sum(p[1] for p in poly)/len(poly)
                if int((cz+side*cy*.82)/.165)%2:
                    self.poly("pilot_chevron_paint_v08",[(mapping(y,z)[0]+end*.002,y,z) for y,z,_ in poly],
                              [tuple(range(len(poly)))],"yellow",normal=(end,0,0))
        if self.lod==0:
            for side in (-1,1):
                for y,z in ((side*.96,.68),(side*.70,.57),(side*1.16,.51)):
                    self.bolt("pilot_flush_fastener_v08",(end*11.160,y,z),.013,"X")

    def profile(self,name,xz,y,depth,mat="graphite",parent=None):
        if name=="axlebox_cradle" and self.lod<2:
            x=(min(p[0] for p in xz)+max(p[0] for p in xz))/2
            contour=[(x-.61,.625),(x-.61,.540),(x-.53,.514),(x+.53,.514),(x+.61,.540),(x+.61,.625),
                     (x+.27,.67),(x+.20,.862),(x-.20,.862),(x-.27,.67)]
            obj=DetailBuilder.profile(self,name,contour,y,depth,mat,parent)
            for dx in (-.425,.425):
                cutter=BaseBody.box(self,"cradle_slot_cutter_v08",(x+dx,y,.570),(.133,depth+.20,.047),"black",parent=parent)
                # Both objects have the same parent, so local reference coordinates agree.
                self.bevel(cutter,.016,3 if self.lod==0 else 1)
                self.cut(obj,cutter)
            self.bevel(obj,.006,2 if self.lod==0 else 1)
            return self.evidence(obj,"slotted_axlebox_cradle")
        if name=="traction_arm" and self.lod<2:
            a=xz[0][0]; b=xz[2][0]; mid=(a+b)/2
            xz=[(a,.945),(a,1.105),(mid,1.072),(b,1.062),(b,.965),(mid,.997)]
        return super().profile(name,xz,y,depth,mat,parent)

    def box(self,name,loc,dims,mat="dark",bevel=0,parent=None):
        if name in {"bogie_terminal_box","terminal_lid"} and self.lod<2:
            x,y,z=loc; side=1 if y>0 else -1
            w=.565 if name=="bogie_terminal_box" else .536
            top=z+.213; bottom=z-.212
            outline=[(x-w/2,top),(x+w/2,top),(x+w/2,bottom+.095),
                     (x+.125,bottom+.095),(x+.125,bottom),(x-w/2+.018,bottom)]
            obj=DetailBuilder.profile(self,name,outline,y,dims[1],mat,parent)
            self.bevel(obj,.008,2 if self.lod==0 else 1)
            if name=="terminal_lid":
                parts=[obj]
                for xx in (x-w/2+.065,x+w/2-.065):
                    parts.append(self.small_box("sandbox_cover_hinge_v08",(xx,y+side*.025,top-.014),(.065,.026,.043),"spring_steel",parent=parent))
                # Thin folded return around the stepped lid; not an oversized round box.
                points=[(xx,y+side*.017,zz) for xx,zz in outline+[outline[0]]]
                parts.append(self.tube("sandbox_folded_lip_v08",points,.006,"spring_steel",parent,sides=6))
                obj=self.g.join_objects(parts,name,parent)
                self.evidence(obj,"stepped_bogie_equipment_lid")
            return obj
        if name in {"radiator_fan_hub","concealed_fan_blade","recessed_fan_shroud"}:
            mat="grille_black"
        return super().box(name,loc,dims,mat,bevel,parent)

    def helix(self,name,center,radius,height,wire,turns,parent):
        if self.lod: return super().helix(name,center,radius,height,wire,turns,parent)
        # Flatten the end turns against the seats, retaining five visible turns.
        points=[]; n=round(turns*24)
        for i in range(n+1):
            t=i/n; a=t*turns*math.tau
            zt=max(0,min(1,(t-.07)/.86))
            points.append((center[0]+radius*math.cos(a),center[1]+radius*math.sin(a),center[2]-height/2+height*zt))
        return self.evidence(self.tube(name,points,.031,"cast_steel",parent,sides=10),"seated_primary_coil")

    def roof(self):
        super().roof()
        # Darker recessed fan cavity and robust mesh match the original, not shiny exposed discs.
        for obj in list(bpy.context.scene.objects):
            if obj.name.startswith(("concealed_fan_blade","radiator_fan_hub","recessed_fan_shroud","radiator_screen_")):
                if obj.type=="MESH":
                    obj.data.materials.clear(); obj.data.materials.append(self.mat("grille_black"))
                    for face in obj.data.polygons: face.material_index=0
            if obj.name.startswith("recessed_oval_exhaust_duct"):
                obj.data.materials.clear(); obj.data.materials.append(self.mat("exhaust_steel"))
                for face in obj.data.polygons: face.material_index=0
        from roof_details_v07 import capsule, EXHAUST_OUTLETS
        for x,y,_ in EXHAUST_OUTLETS:
            # Saw-tooth / segmented mouth visible in both 0050 and 0051 originals.
            # Hidden internal duct route and exact number of teeth are NOT established.
            outline=capsule(x,y,.795,.344,10 if self.lod==0 else 6)
            count=len(outline); verts=[]; faces=[]
            for i,(u,v) in enumerate(outline):
                nxt=outline[(i+1)%count]
                for t,z in ((0,4.598),(.0,4.633),(.63,4.633),(.64,4.610),(1,4.610),(1,4.598)):
                    verts.append((u+(nxt[0]-u)*t,v+(nxt[1]-v)*t,z))
                faces.append(tuple(range(i*6,i*6+6)))
            tooth=self.poly("segmented_exhaust_lip_v08",verts,faces,"exhaust_steel",normal=(0,0,1))
            # Actual thickness so edges do not vanish when viewed from the other side.
            mod=tooth.modifiers.new("thin_mouth_steel","SOLIDIFY"); mod.thickness=.005
            bpy.context.view_layer.objects.active=tooth; bpy.ops.object.modifier_apply(modifier=mod.name)
            self.evidence(tooth,"segmented_exhaust_lip")
        for x in (-6.96,-6.30,-5.62,-4.94,-4.24):
            for y in (-1.05,1.05):
                self.small_box("radiator_mesh_clamping_bridge_v08",(x,y,4.602),(.085,.054,.014),"roof")


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(("body_detail_","refinement_","silhouette_","evidence_")): del bpy.context.scene[key]
    # Capture the builder's counters even though bogie subparts are joined for export.
    holder=[]
    class TrackedBuilder(EvidenceBuilder):
        def __init__(self,*args):
            super().__init__(*args); holder.append(self)
    build_body(lod,gen,TrackedBuilder)
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("transparent_pane")]
        inner=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("cab_interior")]
        gen.join_objects(inner,"cab_interior")
        for i,obj in enumerate(panes): obj.name=f"glazing_{i:02d}"
        bpy.context.scene["glazing_count"]=len(panes)
        bpy.context.scene["cab_openings"]=12
    for tag,prefix in (("body_v05_component","body_detail_"),("detail_v06_component","refinement_"),("detail_v07_component","silhouette_")):
        for name,count in Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag)).items():
            bpy.context.scene[prefix+name]=count
    for name,count in holder[0].evidence_counts.items(): bpy.context.scene["evidence_"+name]=count
