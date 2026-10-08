"""Isolated prototype profile/paint/relief delta on the audited v43 candidate."""
from pathlib import Path
from copy import deepcopy
import json, os, shutil, sys
import bpy
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v43_source'
MOD=ROOT/'staging/codex_fxn5c_1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
import generate_fxn5c as gen
import export_tpf2 as exporter
import prototype_geometry_v44 as profile
from geometry_v20 import ProductionBuilder15
from build_release_v24 import body_items,lua_literal,normalize_empty,walk
from build_v39 import matrices,attachment as previous_attachment
from build_v38 import fingerprint
from native_patch_v23 import patch,sha
from roof_revision_v24 import sanitize_after_export
from snapshot_v42 import clean_snapshot
from verify_native import read_lua

STYLE='fxn5c_prototype_0001'
MODULES=(profile,)


def baseline_source(lod):
    return BASE/(STYLE+'_source.blend') if lod==0 else BASE/'runtime'/f'final43_{STYLE}_lod{lod}.blend'


def attachment(obj):
    if obj.get('light24_emitter'):
        direction=obj['light24_direction']
        assert direction in ('fwd','bwd')
        return 'light24_front_'+direction
    return previous_attachment(obj)


def selected(nodes,style=STYLE):
    assert style==STYLE
    pool={o.name:o for module in MODULES for o in module.selected_objects(style)}
    allowed={o.name for o,_ in body_items()}
    groups={}
    for name,obj in sorted(pool.items()):
        role=attachment(obj)
        assert obj.type=='MESH' and not obj.get('roof26_animation_kind'),name
        assert not obj.get('connection_role') and not obj.get('livery21_variable'),name
        assert role in nodes and nodes[role][0].get('mesh'),(name,role)
        assert role not in ('b1','b2'),'Prototype cab work must not modify running gear'
        if role=='body':assert name in allowed,('not body mesh',name)
        groups.setdefault(role,[]).append(obj)
    return groups


def snapshot(style,lod,phase,role,objects,world):
    folder=ROOT/'runtime/patch44'/style;folder.mkdir(parents=True,exist_ok=True)
    exporter.MESH_DIR=str(folder);name=f'{role}_{phase}_lod{lod}'
    inv=world.inverted()
    mats,_,_=exporter.export_mesh(name,[(o,inv@o.matrix_world)for o in objects])
    path=folder/(name+'.msh')
    return path,clean_snapshot(path,mats)


def save(path):
    for image in bpy.data.images:
        if image.source!='FILE' or not image.filepath:continue
        origin=Path(bpy.path.abspath(image.filepath)).resolve()
        if not origin.is_file():
            assert image.packed_file is not None,('missing image',image.name,image.filepath)
            continue
        dest=ROOT/'source_textures'/origin.name
        if dest.exists():assert sha(dest)==sha(origin),('texture collision',dest)
        else:shutil.copyfile(origin,dest)
        image.filepath='//'+os.path.relpath(dest,path.parent).replace('\\','/')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=False)


def main():
    old=json.loads((BASE/'manifest_v43.json').read_text(encoding='utf8'))
    assert old['status']=='NATIVE_STATIC_PASS'
    model_path=BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{STYLE}.mdl'
    model=read_lua(model_path)
    other_refs=set()
    for p in (model_path.parent).glob('*.mdl'):
        if p==model_path:continue
        other_refs.update(n['mesh']for n in walk(read_lua(p))if n.get('mesh'))
    patches=[];sources=[];changes=[]
    for lod in range(3):
        source=baseline_source(lod)
        bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
        builder=ProductionBuilder15(lod,gen);nodes=matrices(model['lods'][lod]['node'])
        groups=selected(nodes);names={o.name for objs in groups.values()for o in objs}
        before_names={r:[o.name for o in objs]for r,objs in groups.items()}
        untouched={o.name:fingerprint(o)for o in bpy.context.scene.objects if o.type=='MESH' and o.name not in names}
        before={r:snapshot(STYLE,lod,'before',r,objs,nodes[r][1])for r,objs in groups.items()}
        reports={k:m.apply(builder,STYLE)for k,m in zip(('geometry',),MODULES)}
        bpy.context.view_layer.update();gen.ensure_uvs()
        groups=selected(nodes)
        assert set(groups)==set(before),('attachment inventory changed',lod,set(groups),set(before))
        for name,digest in untouched.items():
            assert name in bpy.data.objects and fingerprint(bpy.data.objects[name])==digest,('out of scope source change',lod,name)
        after_names={o.name for objs in groups.values()for o in objs}
        newly_added={o.name for o in bpy.context.scene.objects if o.type=='MESH'}-set(untouched)-names
        assert newly_added<=after_names,('unexported new object',newly_added-after_names)
        for role,objs in groups.items():
            bp,bm=before[role];ap,am=snapshot(STYLE,lod,'after',role,objs,nodes[role][1])
            node,world=nodes[role];ref=node['mesh']
            assert ref not in other_refs,('shared production mesh cannot be patched',ref)
            rel='staging/codex_fxn5c_1/res/models/mesh/'+ref
            assert ref not in {r['mesh_ref']for r in patches},('duplicate patch',ref)
            proof=patch(BASE/rel,bp,ap,ROOT/rel,node['materials'],bm,am)
            proof['zero_area_cleanup']=sanitize_after_export(ROOT/rel)
            proof.update(mesh_sha256=sha(ROOT/rel),blob_sha256=sha(str(ROOT/rel)+'.blob'))
            patches.append(dict(style=STYLE,lod=lod,attachment=role,target=rel,mesh_ref=ref,
                before=bp.relative_to(ROOT).as_posix(),after=ap.relative_to(ROOT).as_posix(),
                before_materials=bm,after_materials=am,baseline_materials=node['materials'],
                selected_before=before_names[role],selected_after=[o.name for o in objs],
                native_world_matrix=[list(r)for r in world],**proof))
            print('BUILD44_PATCH',lod,role,proof['removed_triangles'],proof['added_triangles'],flush=True)
        out=ROOT/(STYLE+'_source.blend')if lod==0 else ROOT/'runtime'/f'final44_{STYLE}_lod{lod}.blend'
        save(out)
        sources.append(dict(style=STYLE,lod=lod,file=out.relative_to(ROOT).as_posix(),sha256=sha(out),
            baseline_version='0.43',baseline=source.relative_to(BASE).as_posix(),baseline_sha256=sha(source)))
        changes.append(dict(style=STYLE,lod=lod,report=reports,untouched_source_meshes=len(untouched)))
    by_ref={r['mesh_ref']:r for r in patches}
    for level in model['lods']:
        for node in walk(level['node']):
            if node.get('mesh')in by_ref:node['materials']=by_ref[node['mesh']]['materials']
    literal=lua_literal(model)
    for value in model['metadata']['description'].values():
        token=lua_literal(value);assert literal.count(token)==1
        literal=literal.replace(token,'_('+token+')',1)
    target=ROOT/model_path.relative_to(BASE)
    target.write_text('function data()\nreturn '+literal+'\nend\n',encoding='utf8')
    assert read_lua(target)==normalize_empty(model)
    text=(BASE/'staging/codex_fxn5c_1/mod.lua').read_text(encoding='utf8')
    assert text.count('minorVersion = 43')==1
    (MOD/'mod.lua').write_text(text.replace('minorVersion = 43','minorVersion = 44'),encoding='utf8')
    lines=(BASE/'staging/codex_fxn5c_1/strings.lua').read_text(encoding='utf8').splitlines(keepends=True)
    for i,line in enumerate(lines):
        if 'MOD_NAME ='in line:lines[i]=line.replace('v0.43','v0.44')
        elif 'MOD_DESC = "'in line:
            note=('v0.44 原型车候选：修正原型车单平面过渡斜面与垂直前扶手，全车号购买图标统一整车侧视及轨道展示，补齐原型车TGA图标。未游戏实测。'if'复兴5C'in line else
                  'v0.44 prototype candidate: planar cab transition bevels and upright front handrails; catalog-wide side-view icons with rail display and prototype TGA icons. Not engine-tested.')
            lines[i]=line.replace('MOD_DESC = "','MOD_DESC = "'+note+'\\n\\n',1)
    (MOD/'strings.lua').write_text(''.join(lines),encoding='utf8')
    recipe=('build_v44.py','prototype_geometry_v44.py')
    manifest=dict(status='BUILT_PENDING_AUDIT',baseline_version='0.43',
        baseline_manifest_sha256=sha(BASE/'manifest_v43.json'),patches=patches,shared_patches=[],
        sources=sources,changes=changes,models=deepcopy(old['models']),assets=[],material_bindings=[],
        animated=deepcopy(old['animated']),animation_files=deepcopy(old['animation_files']),
        placeholders=deepcopy(old.get('placeholders',[])),recipe_sha256={p:sha(ROOT/p)for p in recipe},
        static_only=True,metadata_change_scope='none',game_verified=False,model_editor_verified=False,installed=False,published=False)
    (ROOT/'manifest_v44.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
    print('BUILD44_PASS',len(patches),len(sources),flush=True)


if __name__=='__main__':
    assert __debug__
    main()

