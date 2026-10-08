"""Two-variant source/FBX/native build. Never modifies a previous release."""
from pathlib import Path
import json
import sys
import bpy

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generate_fxn5c as gen
import export_tpf2 as export
from geometry_v20 import ProductionBuilder15
from bogie_details_v20 import rebuild_saved_bogies
from jinwen_livery_v20 import apply as apply_jinwen
from china_livery_v20 import apply as apply_china
from roof_equipment_v20 import apply as apply_equipment


def snapshot(lod):
    names = {'silhouette':'silhouette_', 'refinements':'refinement_',
             'body_details':'body_detail_', 'evidence':'evidence_',
             'front09':'front09_', 'front10':'front10_', 'emblem11':'emblem11_',
             'front11':'front11_', 'production12':'production12_', 'silhouette13':'silhouette13_'}
    record = {'lod':lod, **{name:{k:int(v) for k,v in bpy.context.scene.items() if k.startswith(prefix)}
                              for name,prefix in names.items()}}
    record['frames'] = [{k:int(v) for k,v in bpy.data.objects[f'b{i}'].items()
                         if k.startswith('component_')} for i in (1,2)]
    return record


def rebase_textures():
    folder = ROOT/'staging/codex_fxn5c_1/res/textures/models/vehicle/train/fxn5c'
    for image in bpy.data.images:
        if image.source == 'FILE':
            path = folder/Path(image.filepath).name
            if not path.exists():
                raise RuntimeError(f'Missing project texture: {path}')
            image.filepath = str(path)


def save_source(path):
    from source_hygiene_v13 import clean_fonts
    for o in list(bpy.context.scene.objects):
        if o.type in {'LIGHT','CAMERA'}:
            bpy.data.objects.remove(o,do_unlink=True)
    bpy.ops.object.camera_add(location=(22,-32,11))
    cam=bpy.context.object
    cam.data.type='ORTHO'; cam.data.ortho_scale=25.5
    gen.point_camera(cam,(0,0,2.1)); bpy.context.scene.camera=cam
    for name in export.LIGHT_NAMES:
        bpy.data.objects[name].hide_render=False
    clean_fonts()
    rebase_textures()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))


def main():
    results = {False:[], True:[]}
    features=[]
    for lod in (0,1,2):
        old = ROOT.parent/'fxn5c_v19_source/fxn5c_source.blend'
        if lod == 0 and '--full' not in sys.argv and old.exists():
            # Preserve v19 livery, linkage and every unrelated component.
            bpy.ops.wm.open_mainfile(filepath=str(old))
            rebase_textures()
        else:
            gen.build_model(lod)
            apply_china(ProductionBuilder15(lod,gen))
        # The Jinwen conversion must start from the pre-equipment CR scene,
        # never recolour or duplicate the new equipment pass.
        base=ROOT/'runtime'/f'v20_cr_lod{lod}_base.blend'
        base.parent.mkdir(exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(base))
        apply_equipment(ProductionBuilder15(lod,gen),False)
        bpy.context.scene['livery']='China Railway FXN5C 0051'
        features.append(snapshot(lod))
        export.select_variant(False)
        results[False].append(export.export_lod(lod,rebuild=False))
        gen.FBX_DIR=str(ROOT/'fbx_import/vehicle-train-fxn5c')
        gen.export_fbx(lod)
        if lod == 0:
            save_source(ROOT/'fxn5c_source.blend')
        print(f'BUILT CR LOD{lod}',flush=True)
        old_jw=ROOT.parent/'fxn5c_v19_source/fxn5c_jinwen_source.blend'
        if lod==0 and '--full' not in sys.argv and old_jw.exists():
            bpy.ops.wm.open_mainfile(filepath=str(old_jw));rebase_textures()
        else:
            bpy.ops.wm.open_mainfile(filepath=str(base))
            apply_jinwen(ProductionBuilder15(lod,gen))
        apply_equipment(ProductionBuilder15(lod,gen),True)
        export.select_variant(True)
        results[True].append(export.export_lod(lod,rebuild=False))
        gen.FBX_DIR=str(ROOT/'fbx_import/vehicle-train-fxn5c-jinwen')
        gen.export_fbx(lod)
        if lod == 0:
            save_source(ROOT/'fxn5c_jinwen_source.blend')
        print(f'BUILT JINWEN LOD{lod}',flush=True)
    for jinwen in (False,True):
        export.select_variant(jinwen)
        export.write_model(results[jinwen])
    if '--full' not in sys.argv and (ROOT.parent/'fxn5c_v19_source').exists():
        from preserve_native_uv_v20 import preserve
        print('Retained baseline cab UVs:', preserve(ROOT,ROOT.parent/'fxn5c_v19_source'),flush=True)
    (ROOT/'geometry_features_v20.json').write_text(json.dumps(features,indent=2),encoding='utf-8')
    print('v0.20 dual-livery native/source/FBX build complete',flush=True)


if __name__ == '__main__':
    main()
