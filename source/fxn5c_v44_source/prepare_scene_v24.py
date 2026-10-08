"""Reconstruct immutable v23 scenes before the roof/front/lamp revision."""
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
BASE=ROOT.parent/'fxn5c_v23_source'
import generate_fxn5c as gen
from geometry_v20 import ProductionBuilder15
from prepare_scene_v23 import prepare as prepare_v22,rebase_textures
from running_gear_revision_v23 import apply as gear23
from livery_revision_v23 import apply as livery23
from body_revision_v23 import apply_common as body23,apply_number_weight
from livery_revision_v21 import _replace_signage

def prepare(lod,jw):
    style='fxn5c_jinwen' if jw else 'fxn5c'
    cache=ROOT/'runtime'/f'baseline24_{style}_lod{lod}.blend'
    if lod==0:
        bpy.ops.wm.open_mainfile(filepath=str(BASE/(style+'_source.blend')))
    elif cache.is_file():
        bpy.ops.wm.open_mainfile(filepath=str(cache))
    else:
        # v23 used a checked triangle delta over this exact editable v22
        # baseline. Its already released corrections are reapplied unchanged.
        previous_cache=BASE/'runtime'/f'baseline23_{style}_lod{lod}.blend'
        if previous_cache.exists():
            bpy.ops.wm.open_mainfile(filepath=str(previous_cache))
            b=ProductionBuilder15(lod,gen)
        else:
            b=prepare_v22(lod,jw)
        gear23(b,jw);livery23(b,jw);body23(b,jw)
        _replace_signage(b,jw,'7006' if jw else '0051','金温 温段' if jw else '上局沪段')
        if lod<2:apply_number_weight(b)
        bpy.context.view_layer.update();rebase_textures()
        bpy.ops.wm.save_as_mainfile(filepath=str(cache))
    rebase_textures()
    builder=ProductionBuilder15(lod,gen)
    from baseline_tessellation_v24 import apply as align_tessellation
    builder.baseline24_tessellation=align_tessellation(builder,jw)
    return builder

if __name__=='__main__':
    for lod in (1,2):
        for jw in (False,True):
            prepare(lod,jw);print('BASELINE24_READY',lod,jw,flush=True)
