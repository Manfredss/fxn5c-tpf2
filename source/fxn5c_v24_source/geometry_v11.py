"""Evidence-led v11 emblem, inboard lamp modes and shallow nose panels."""
from collections import Counter
import bpy
from geometry_v02 import build as build_body
from geometry_v10 import CornerBuilder
from emblem_v11 import make_emblems
from nose_panels_v11 import make_lamp_panels
from light_modes_v11 import make_emitters
from front_finish_v11 import make_front_finish


class EvidenceBuilder11(CornerBuilder):
    def markings(self):
        super().markings()
        make_emblems(self)
        for obj in make_front_finish(self):
            obj['front_v11_component']=obj['front11_component']

    def cabs(self):
        super().cabs()
        make_lamp_panels(self)

    def lights(self):
        make_emitters(self)
        self.evidence_counts['corrected_directional_light_groups']=4


FEATURE_TAGS=(('body_v05_component','body_detail_'),('detail_v06_component','refinement_'),
              ('detail_v07_component','silhouette_'),('front_v09_component','front09_'),
              ('front_v10_component','front10_'),('emblem_v11_component','emblem11_'),
              ('front_v11_component','front11_'))


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(tuple(prefix for _,prefix in FEATURE_TAGS)+('evidence_',)):
            del bpy.context.scene[key]
    holders=[]
    class Tracked(EvidenceBuilder11):
        def __init__(self,*args): super().__init__(*args); holders.append(self)
    build_body(lod,gen,Tracked)
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
