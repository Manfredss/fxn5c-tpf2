"""v0.10: lower cab corner shell, forward-facing outer lamps, seated adapters."""
from collections import Counter
import bpy
from geometry_v02 import build as build_body
from geometry_v09 import FrontBuilder
from nose_profile_v10 import front_half, corner_width, rebuild_grey_belt
from front_details_v10 import make_lamps, make_emitters


class CornerBuilder(FrontBuilder):
    front_half=staticmethod(front_half)
    corner_width=staticmethod(corner_width)

    def hull(self):
        super().hull()
        shell=bpy.data.objects.get('body_open_shell_v07')
        if shell: shell['front_v10_component']='variable_lower_corner_shell'

    def lamp_housings(self,end): make_lamps(self,end)

    def lights(self):
        make_emitters(self)
        self.evidence_counts['corrected_directional_light_groups']=4

    def cabs(self):
        super().cabs()
        rebuild_grey_belt(self)


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(('body_detail_','refinement_','silhouette_','evidence_','front09_','front10_')):
            del bpy.context.scene[key]
    holders=[]
    class Tracked(CornerBuilder):
        def __init__(self,*args): super().__init__(*args); holders.append(self)
    build_body(lod,gen,Tracked)
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('transparent_pane')]
        inner=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('cab_interior')]
        gen.join_objects(inner,'cab_interior')
        for i,o in enumerate(panes): o.name=f'glazing_{i:02d}'
        bpy.context.scene['glazing_count']=len(panes); bpy.context.scene['cab_openings']=12
    for tag,prefix in (('body_v05_component','body_detail_'),('detail_v06_component','refinement_'),
                       ('detail_v07_component','silhouette_'),('front_v09_component','front09_'),
                       ('front_v10_component','front10_')):
        for name,count in Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag)).items():
            bpy.context.scene[prefix+name]=count
    for name,count in holders[0].evidence_counts.items(): bpy.context.scene['evidence_'+name]=count
