"""v13 planar windshield chamfers, forward cab windows and open-bay roof hoods."""
from collections import Counter
import bpy
from geometry_v02 import build as build_body
from geometry_v11 import EvidenceBuilder11, FEATURE_TAGS as OLD_TAGS
from geometry_v09 import FrontBuilder
from geometry_v07 import SilhouetteBuilder
from front_details_v10 import replace_pilot_coupler
from body_details_v14 import vertical_filter,refine_roof,refine_front_hardware,windshield_lower_surround
from nose_shell_v14 import hull,front_half,side_y,belt
from cab_details_v14 import rebuild_side_cab
from front_lamps_v14 import make_lamps
from nose_panels_v14 import make_lamp_panels


class ProductionBuilder14(EvidenceBuilder11):
    front_half=staticmethod(front_half)
    side_y=staticmethod(side_y)

    def hull(self): hull(self)

    def lamp_housings(self,end): make_lamps(self,end)

    def coupler(self,end):
        SilhouetteBuilder.coupler(self,end)
        replace_pilot_coupler(self,end)

    def service_door(self,side,x): vertical_filter(self,side,x)

    def cabs(self):
        # Skip v10's obsolete lower belt and v11's detached corner patches.
        FrontBuilder.cabs(self)
        rebuild_side_cab(self)
        belt(self)
        # Inboard upper seams remain shallow skin detail, independent of the
        # outboard continuous land. Their outer edge follows the new front_half.
        make_lamp_panels(self)
        refine_front_hardware(self)
        windshield_lower_surround(self)

    def roof(self):
        super().roof()
        refine_roof(self)
        from roof_cab_v13 import replace_cab_hoods
        replace_cab_hoods(self)


FEATURE_TAGS=OLD_TAGS+(('detail_v12_component','production12_'),('detail_v13_component','silhouette13_'))


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(tuple(p for _,p in FEATURE_TAGS)+('evidence_',)): del bpy.context.scene[key]
    holders=[]
    class Tracked(ProductionBuilder14):
        def __init__(self,*args): super().__init__(*args); holders.append(self)
    build_body(lod,gen,Tracked)
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals()
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('transparent_pane')]
        inner=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('cab_interior')]
        gen.join_objects(inner,'cab_interior')
        for i,o in enumerate(panes): o.name=f'glazing_{i:02d}'
        bpy.context.scene['glazing_count']=len(panes); bpy.context.scene['cab_openings']=12
    for tag,prefix in FEATURE_TAGS:
        for name,count in Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag)).items():
            bpy.context.scene[prefix+name]=count
    for name,count in holders[0].evidence_counts.items(): bpy.context.scene['evidence_'+name]=count
