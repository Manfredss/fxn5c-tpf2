"""Reconstruct editable baseline scenes; preserve the released v22 directory."""
from pathlib import Path
import shutil
import sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
BASE=ROOT.parent/'fxn5c_v22_source'
import generate_fxn5c as gen
from geometry_v20 import ProductionBuilder15
from china_livery_v20 import apply as china
from jinwen_livery_v20 import apply as jinwen
from roof_equipment_v20 import apply as roof
from bogie_equipment_v21 import apply as equipment
from running_gear_station_v21 import apply as station
from livery_revision_v21 import apply as livery
from body_equipment_v22 import apply as body22
from bogie_details_v22 import apply as bogie22


def rebase_textures():
    folder=Path('staging/codex_fxn5c_1/res/textures/models/vehicle/train/fxn5c')
    for image in bpy.data.images:
        if image.source!='FILE':continue
        name=Path(image.filepath).name
        path=ROOT/folder/name
        if not path.exists():
            path=ROOT/'source_textures'/name
            if not path.exists():
                candidates=(BASE/'source_textures'/name,BASE/folder/name)
                old=next((p for p in candidates if p.is_file()),None)
                assert old,('missing source texture',name)
                path.parent.mkdir(exist_ok=True);shutil.copy2(old,path)
        image.filepath=str(path)


def prepare(lod,jw):
    name='fxn5c_jinwen' if jw else 'fxn5c'
    cache=ROOT/'runtime'/f'baseline23_{name}_lod{lod}.blend'
    if lod==0:
        bpy.ops.wm.open_mainfile(filepath=str(BASE/(name+'_source.blend')))
    elif cache.exists():
        bpy.ops.wm.open_mainfile(filepath=str(cache))
    else:
        for key in list(bpy.context.scene.keys()):del bpy.context.scene[key]
        gen.build_model(lod)
        b=ProductionBuilder15(lod,gen)
        china(b)
        if jw:jinwen(b)
        roof(b,jw);equipment(b);station()
        livery(b,jw,'7006' if jw else '0051','金温 温段' if jw else '上局沪段')
        body22(b,jw);bogie22(b,jw)
        bpy.context.view_layer.update()
        bpy.ops.wm.save_as_mainfile(filepath=str(cache))
    rebase_textures()
    return ProductionBuilder15(lod,gen)


if __name__=='__main__':
    for lod in (1,2):
        for jw in (False,True):
            prepare(lod,jw);print('BASELINE23 READY',lod,jw,flush=True)
