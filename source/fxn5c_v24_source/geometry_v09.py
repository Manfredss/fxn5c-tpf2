"""v09 scope: front fixtures, real upper-light recess, plough/treads and Janney head."""
from collections import Counter
import bpy
from geometry_v02 import build as build_body
from geometry_v07 import SilhouetteBuilder
from geometry_v08 import EvidenceBuilder
from front_details_v09 import make_lamps, make_emitters, replace_pilot_coupler


class FrontBuilder(EvidenceBuilder):
    def __init__(self,lod,gen):
        super().__init__(lod,gen)
        self.front_counts=Counter()

    def tag(self,obj,name):
        obj["front_v09_component"]=name
        self.front_counts[name]+=1
        return obj

    def lamp_housings(self,end):
        make_lamps(self,end)

    def coupler(self,end):
        SilhouetteBuilder.coupler(self,end)
        replace_pilot_coupler(self,end)

    def lights(self):
        make_emitters(self)
        self.evidence_counts["corrected_directional_light_groups"]=4


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(("body_detail_","refinement_","silhouette_","evidence_","front09_")):
            del bpy.context.scene[key]
    holder=[]
    class Tracked(FrontBuilder):
        def __init__(self,*args):
            super().__init__(*args); holder.append(self)
    build_body(lod,gen,Tracked)
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("transparent_pane")]
        inner=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("cab_interior")]
        gen.join_objects(inner,"cab_interior")
        for i,obj in enumerate(panes): obj.name=f"glazing_{i:02d}"
        bpy.context.scene["glazing_count"]=len(panes); bpy.context.scene["cab_openings"]=12
    for tag,prefix in (("body_v05_component","body_detail_"),("detail_v06_component","refinement_"),
                       ("detail_v07_component","silhouette_"),("front_v09_component","front09_")):
        for name,count in Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag)).items():
            bpy.context.scene[prefix+name]=count
    for name,count in holder[0].evidence_counts.items(): bpy.context.scene["evidence_"+name]=count
