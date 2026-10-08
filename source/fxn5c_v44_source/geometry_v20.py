"""Preserved v14 body, rebuilt photo-referenced v19 running gear."""
from collections import Counter
import bpy
from geometry_v14 import ProductionBuilder14, FEATURE_TAGS
from geometry_v02 import build as build_body
from bogie_details_v20 import build_bogie


class ProductionBuilder15(ProductionBuilder14):
    def bogie(self, index, center):
        return build_bogie(self, index, center)


def build(lod, gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(tuple(p for _, p in FEATURE_TAGS) + ('evidence_', 'bogie15_', 'jinwen','china19_','livery19_')):
            del bpy.context.scene[key]
    holders = []
    class Tracked(ProductionBuilder15):
        def __init__(self, *args):
            super().__init__(*args)
            holders.append(self)
    build_body(lod, gen, Tracked)
    from body_bogie_connection_v20 import apply as build_connections
    build_connections(holders[0])
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals()
    if lod < 2:
        panes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('transparent_pane')]
        inner = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('cab_interior')]
        gen.join_objects(inner, 'cab_interior')
        for i, obj in enumerate(panes):
            obj.name = f'glazing_{i:02d}'
        bpy.context.scene['glazing_count'] = len(panes)
        bpy.context.scene['cab_openings'] = 12
    for tag, prefix in FEATURE_TAGS:
        for name, count in Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag)).items():
            bpy.context.scene[prefix + name] = count
    for name, count in holders[0].evidence_counts.items():
        bpy.context.scene['evidence_' + name] = count
