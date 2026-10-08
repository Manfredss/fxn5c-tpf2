"""Scoped v38->v39 windows, horn recesses and inboard sandbox delta.

Retains every node transform, all wheelsets, linkage skins, lamps and roof
animations. Mesh snapshots are expressed in each EXISTING native node frame.
"""
from pathlib import Path
from copy import deepcopy
import json,sys,hashlib,os,shutil
import bpy
import numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v38_source'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
import generate_fxn5c as gen
import export_tpf2 as exporter
from geometry_v20 import ProductionBuilder15
import glazing_revision_v39 as glazing
import horn_revision_v39 as horns
import sandbox_revision_v39 as sand
from build_release_v24 import body_items,lua_literal,normalize_empty,walk
from native_patch_v23 import patch,sha
from roof_revision_v24 import sanitize_after_export
from verify_native import read_lua
from build_v38 import fingerprint


def matrices(node,parent=None,result=None):
    if parent is None:parent=Matrix.Identity(4)
    if result is None:result={}
    t=node.get('transf',[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1])
    world=parent@Matrix([[t[c*4+r] for c in range(4)] for r in range(4)])
    result[node['name']]=(node,world)
    for child in node.get('children',[]):matrices(child,world,result)
    return result


def attachment(obj):
    if obj.name.startswith('glazing_'):return obj.name
    p=obj
    while p:
        if p.name in ('b1_grp','b2_grp'):return p.name[:2]
        p=p.parent
    return 'body'


def selected(nodes):
    pool={o.name:o for mod in (glazing,horns,sand) for o in mod.selected_objects()}
    allowed_body={o.name for o,_ in body_items()}
    groups={}
    for name,o in sorted(pool.items()):
        assert o.type=='MESH' and not o.get('roof26_animation_kind'),name
        role=attachment(o)
        assert role in nodes and nodes[role][0].get('mesh'),('no existing mesh owner',name,role)
        if role=='body':assert name in allowed_body,('not body mesh',name)
        assert not o.get('connection_role') and not o.get('livery21_variable') and not o.get('light24_emitter'),name
        groups.setdefault(role,[]).append(o)
    return groups


def snapshot(style,lod,phase,role,objects,world):
    folder=ROOT/'runtime/patch39'/style;folder.mkdir(parents=True,exist_ok=True)
    exporter.MESH_DIR=str(folder)
    name=f'{role}_{phase}_lod{lod}';inv=world.inverted()
    mats,_,_=exporter.export_mesh(name,[(o,inv@o.matrix_world) for o in objects])
    path=folder/(name+'.msh');sanitize_after_export(path)
    return path,mats


def save(path):
    # New procedural materials may load a texture from the native staging
    # tree with an absolute filepath. Relocate that dependency into the
    # source texture library before saving; never bind a distributed scene
    # to this workstation or silently replace a different existing image.
    for image in bpy.data.images:
        if image.source!='FILE' or not image.filepath or image.filepath.startswith('//'):
            continue
        origin=Path(bpy.path.abspath(image.filepath)).resolve()
        assert origin.is_relative_to(ROOT) and origin.is_file(),('unexpected image dependency',origin)
        destination=ROOT/'source_textures'/origin.name
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():assert sha(destination)==sha(origin),('source texture collision',destination)
        else:shutil.copyfile(origin,destination)
        image.filepath='//'+os.path.relpath(destination,path.parent).replace('\\','/')
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=False)


def main():
    old=json.loads((BASE/'manifest_v38.json').read_text(encoding='utf8'))
    assert old['status']=='NATIVE_STATIC_PASS'
    patches=[];changes=[];sources=[]
    for jw in (False,True):
        style='fxn5c_jinwen' if jw else 'fxn5c'
        model=read_lua(BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
        for lod in (0,1,2):
            source=BASE/(style+'_source.blend') if lod==0 else BASE/'runtime'/f'final38_{style}_lod{lod}.blend'
            bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
            b=ProductionBuilder15(lod,gen);nodes=matrices(model['lods'][lod]['node'])
            before_groups=selected(nodes)
            before_group_names={role:[o.name for o in objects] for role,objects in before_groups.items()}
            before_names={o.name for objects in before_groups.values() for o in objects}
            untouched={o.name:fingerprint(o) for o in bpy.context.scene.objects if o.type=='MESH' and o.name not in before_names}
            previous={role:snapshot(style,lod,'before',role,objects,nodes[role][1]) for role,objects in before_groups.items()}
            report=dict(glazing=glazing.apply(b,jw),horns=horns.apply(b,jw),sandboxes=sand.apply(b,jw))
            bpy.context.view_layer.update();gen.ensure_uvs()
            after_groups=selected(nodes)
            after_names={o.name for objects in after_groups.values() for o in objects}
            assert before_groups.keys()==after_groups.keys(),('attachment set changed',before_groups.keys(),after_groups.keys())
            for name,digest in untouched.items():
                obj=bpy.data.objects.get(name)
                assert obj is not None and fingerprint(obj)==digest,('out of scope source change',name)
            new_names={o.name for o in bpy.context.scene.objects if o.type=='MESH'}-set(untouched)-before_names
            assert new_names<=after_names,('unexported new objects',sorted(new_names-after_names))
            for role,objects in after_groups.items():
                before,bm=previous[role]
                after,am=snapshot(style,lod,'after',role,objects,nodes[role][1])
                node=nodes[role][0];ref=node['mesh'];rel='staging/codex_fxn5c_1/res/models/mesh/'+ref
                proof=patch(BASE/rel,before,after,ROOT/rel,node['materials'],bm,am)
                proof['zero_area_cleanup']=sanitize_after_export(ROOT/rel)
                proof['mesh_sha256']=sha(ROOT/rel);proof['blob_sha256']=sha(str(ROOT/rel)+'.blob')
                patches.append(dict(style=style,lod=lod,attachment=role,target=rel,mesh_ref=ref,
                    before=before.relative_to(ROOT).as_posix(),after=after.relative_to(ROOT).as_posix(),
                    before_materials=bm,after_materials=am,baseline_materials=node['materials'],
                    selected_before=before_group_names[role],selected_after=[o.name for o in objects],
                    native_world_matrix=[list(r) for r in nodes[role][1]],**proof))
                print('BUILD39_PATCH',style,lod,role,proof['removed_triangles'],proof['added_triangles'],flush=True)
            out=ROOT/(style+'_source.blend') if lod==0 else ROOT/'runtime'/f'final39_{style}_lod{lod}.blend'
            save(out)
            sources.append(dict(file=out.relative_to(ROOT).as_posix(),sha256=sha(out),
                                baseline=source.relative_to(BASE).as_posix(),baseline_sha256=sha(source)))
            changes.append(dict(style=style,lod=lod,report=report,untouched_source_meshes=len(untouched)))
    by_ref={p['mesh_ref']:p for p in patches};models=[]
    for path in sorted((BASE/'staging/codex_fxn5c_1/res/models/model/vehicle/train').glob('*.mdl')):
        model=read_lua(path)
        for lod in model['lods']:
            for node in walk(lod['node']):
                if node.get('mesh') in by_ref:
                    row=by_ref[node['mesh']];assert node['name']==row['attachment']
                    node['materials']=row['materials']
        literal=lua_literal(model)
        for value in model['metadata']['description'].values():
            token=lua_literal(value);assert literal.count(token)==1
            literal=literal.replace(token,'_('+token+')',1)
        target=ROOT/path.relative_to(BASE)
        target.write_text('function data()\nreturn '+literal+'\nend\n',encoding='utf8')
        assert read_lua(target)==normalize_empty(model);models.append(path.stem)
    assert len(models)==12
    mod=ROOT/'staging/codex_fxn5c_1'
    text=(BASE/'staging/codex_fxn5c_1/mod.lua').read_text(encoding='utf8')
    assert text.count('minorVersion = 38')==1
    (mod/'mod.lua').write_text(text.replace('minorVersion = 38','minorVersion = 39'),encoding='utf8')
    lines=(BASE/'staging/codex_fxn5c_1/strings.lua').read_text(encoding='utf8').splitlines(keepends=True)
    for i,line in enumerate(lines):
        if 'MOD_NAME =' in line:lines[i]=line.replace('v0.38','v0.39')
        elif 'MOD_DESC = "' in line:
            note=('v0.39 候选：矩形前挡风玻璃与开口、带内部喇叭的三角罩、转向架内端砂箱；保留既有涂装与百叶动画。未游戏实测。' if '复兴5C' in line else
                  'v0.39 candidate: rectangular windscreens and apertures, recessed horns behind triangular covers, inboard bogie sandboxes. Existing liveries and shutters retained. Not engine-tested.')
            lines[i]=line.replace('MOD_DESC = "','MOD_DESC = "'+note+'\\n\\n',1)
    (mod/'strings.lua').write_text(''.join(lines),encoding='utf8')
    recipe=('build_v39.py','glazing_revision_v39.py','horn_revision_v39.py','sandbox_revision_v39.py')
    manifest=dict(status='BUILT_PENDING_AUDIT',baseline_version='0.38',patches=patches,changes=changes,sources=sources,models=models,
        animated=deepcopy(old['animated']),animation_files=deepcopy(old['animation_files']),placeholders=deepcopy(old.get('placeholders',[])),
        baseline_manifest_sha256=sha(BASE/'manifest_v38.json'),recipe_sha256={p:sha(ROOT/p) for p in recipe},
        static_only=True,metadata_change_scope='none',game_verified=False,model_editor_verified=False,installed=False,published=False)
    (ROOT/'manifest_v39.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
    print('BUILD39_PASS',len(models),len(patches),len(manifest['animated']),flush=True)


if __name__=='__main__':main()
