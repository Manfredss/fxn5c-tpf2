"""Targeted body/gear/signage correction, preserving native hierarchy & wheels."""
from pathlib import Path
import json
import re
import sys
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
BASE=ROOT.parent/'fxn5c_v22_source'
MOD=ROOT/'staging/codex_fxn5c_1'
import generate_fxn5c as gen
import export_tpf2 as export
from prepare_scene_v23 import prepare,rebase_textures
from running_gear_revision_v23 import apply as gear
from livery_revision_v23 import apply as livery
from body_revision_v23 import apply_common,apply_number_weight
from livery_revision_v21 import _replace_signage
from roster_v21 import ROSTER
from native_patch_v23 import patch,set_model_materials,sha
from verify_native import read_lua
import build_release_v20 as source_helpers
source_helpers.rebase_textures=rebase_textures


def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)


def ancestor_bogie(obj):
    parent=obj.parent
    while parent:
        if parent.name in ('b1_grp','b2_grp'):return parent.name[:2]
        parent=parent.parent
    return None


def items(attachment):
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and '|bounding_box' not in o.name and not o.name.startswith('bounds|')]
    if attachment=='body':
        selected=[o for o in objects if not ancestor_bogie(o) and not o.get('connection_role')
            and not o.get('livery21_variable') and o.name not in export.LIGHT_NAMES
            and o.name!='cab_interior' and not o.name.startswith('glazing_')]
        return [(o,o.matrix_world.copy()) for o in sorted(selected,key=lambda o:o.name)]
    group=bpy.data.objects[attachment+'_grp'];inverse=group.matrix_world.inverted()
    selected=[o for o in objects if ancestor_bogie(o)==attachment
        and not re.fullmatch(r'w[1-6]',o.name) and not o.get('connection_role')]
    assert bpy.data.objects[attachment] in selected
    return [(o,inverse@o.matrix_world) for o in sorted(selected,key=lambda o:o.name)]


def snapshot(style,lod,phase):
    result={}
    export.MESH_DIR=str(ROOT/'runtime/patch_inputs'/style)
    for part in ('body','b1','b2'):
        filename=f'{part}_{phase}_lod{lod}'
        mats,verts,tris=export.export_mesh(filename,items(part))
        result[part]={'file':f'runtime/patch_inputs/{style}/{filename}.msh','materials':mats,'triangles':tris}
    return result


def main():
    records=[];sources=[];scene_checks=[];signage=[]
    for jw in (False,True):
        style='fxn5c_jinwen' if jw else 'fxn5c'
        baseline=read_lua(BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
        rows=[r for r in ROSTER if r['jinwen']==jw]
        for lod in (0,1,2):
            b=prepare(lod,jw)
            prior=snapshot(style,lod,'before')
            changes={'gear':gear(b,jw),'livery':livery(b,jw),'body':apply_common(b,jw)}
            bpy.context.view_layer.update();gen.ensure_uvs()
            current=snapshot(style,lod,'after')
            nodes={n['name']:n for n in walk(baseline['lods'][lod]['node'])}
            for part in ('body','b1','b2'):
                ref=nodes[part]['mesh'];relative='staging/codex_fxn5c_1/res/models/mesh/'+ref
                proof=patch(BASE/relative,ROOT/prior[part]['file'],ROOT/current[part]['file'],ROOT/relative,
                            nodes[part]['materials'],prior[part]['materials'],current[part]['materials'])
                records.append(dict(style=style,jinwen=jw,lod=lod,attachment=part,mesh_ref=ref,target=relative,
                    baseline='../fxn5c_v22_source/'+relative,before=prior[part],after=current[part],
                    baseline_materials=nodes[part]['materials'],**proof))
                print('PATCHED',style,lod,part,proof['removed_triangles'],proof['added_triangles'],flush=True)
            for index,row in enumerate(rows):
                _replace_signage(b,jw,row['number'],row['depot'])
                if lod<2:apply_number_weight(b)
                export.select_vehicle(row)
                signs=export.export_signage(lod)
                if signs:signage.append(dict(model=row['stem'],number=row['number'],lod=lod,**signs))
                if index==0:
                    if lod==0:
                        source_helpers.save_source(ROOT/(style+'_source.blend'))
                        sources.append({'file':style+'_source.blend','sha256':sha(ROOT/(style+'_source.blend'))})
                    gen.FBX_DIR=str(ROOT/('fbx_import/vehicle-train-fxn5c-jinwen' if jw else 'fbx_import/vehicle-train-fxn5c'))
                    gen.export_fbx(lod)
            scene_checks.append(dict(style=style,lod=lod,changes=changes))
    model_dir=MOD/'res/models/model/vehicle/train'
    for path in (BASE/'staging/codex_fxn5c_1/res/models/model/vehicle/train').glob('*.mdl'):
        text=path.read_text(encoding='utf-8')
        for record in records:
            if '"'+record['mesh_ref']+'"' in text:
                text=set_model_materials(text,record['mesh_ref'],record['baseline_materials'],record['materials'])
        # Signage keeps its material slots: do not alter native node indices.
        (model_dir/path.name).write_text(text,encoding='utf-8',newline='\n')
    for filename in ('mod.lua','strings.lua'):
        value=(BASE/'staging/codex_fxn5c_1'/filename).read_text(encoding='utf-8')
        (MOD/filename).write_text(value.replace('v0.22','v0.23').replace('minorVersion = 22','minorVersion = 23'),encoding='utf-8',newline='\n')
    inputs=('running_gear_revision_v23.py','livery_revision_v23.py','jwr_vector_v23.py','body_revision_v23.py',
            'native_patch_v23.py','build_release_v23.py','prepare_scene_v23.py')
    report={'status':'BUILT_PENDING_AUDIT','patches':records,'sources':sources,'signage':signage,
            'scene_changes':scene_checks,'inputs_sha256':{n:sha(ROOT/n) for n in inputs},
            'scope':'Targeted source delta; native skin hierarchy, wheel axes and vehicle identities retained',
            'game_verified':False}
    (ROOT/'native_patch_manifest_v23.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('v23 build complete',flush=True)


if __name__=='__main__':main()
