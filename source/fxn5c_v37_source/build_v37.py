"""Scoped hinge delta + replacement roof leaves; all other geometry retained."""
from pathlib import Path
from copy import deepcopy
from collections import defaultdict
import sys,json,math
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'fxn5c_v36_source'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
import generate_fxn5c as gen
import export_tpf2 as exporter
from geometry_v20 import ProductionBuilder15
from shutters_v37 import apply,hinges
from native_patch_v23 import sha,patch
from verify_native import read_lua
from roof_revision_v24 import sanitize_after_export
from build_release_v24 import lua_literal,walk
from animation_v28 import matrix
from animation_v26 import _base_node

def export(name,objects,folder,pivot=None):
    folder.mkdir(parents=True,exist_ok=True);exporter.MESH_DIR=str(folder)
    inv=Matrix.Translation(Vector(pivot)).inverted() if pivot is not None else Matrix.Identity(4)
    mats,_,_=exporter.export_mesh(name,[(o,inv@o.matrix_world) for o in objects])
    path=folder/(name+'.msh');cleanup=sanitize_after_export(path)
    return path,mats,cleanup

def save(path):
    # Source files in the baseline already have local relative image paths.
    # Saving with remapping disabled makes identical relative paths resolve in
    # this candidate's copied texture folders, not the older working directory.
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=False)

def main():
    old=json.loads((BASE/'manifest_v36.json').read_text());parts=[deepcopy(p) for p in old['animated'] if p['kind']!='louver']
    patches=[];sources=[];changes=[]
    for jw in (False,True):
        style='fxn5c_jinwen' if jw else 'fxn5c'
        model=read_lua(BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
        for lod in (0,1,2):
            src=BASE/(style+'_source.blend') if lod==0 else BASE/'runtime'/f'final34_{style}_lod{lod}.blend'
            bpy.ops.wm.open_mainfile(filepath=str(src),load_ui=False,use_scripts=False)
            b=ProductionBuilder15(lod,gen);folder=ROOT/'runtime/hinges37'/style
            if lod<2:before,bm,_=export(f'before_lod{lod}',hinges(),folder)
            changes.append(dict(style=style,lod=lod,**apply(b,jw)))
            if lod<2:
                after,am,_=export(f'after_lod{lod}',hinges(),folder)
                body=next(n for n in walk(model['lods'][lod]['node']) if n['name']=='body')
                rel='staging/codex_fxn5c_1/res/models/mesh/'+body['mesh']
                proof=patch(BASE/rel,before,after,ROOT/rel,body['materials'],bm,am)
                proof['zero_area_cleanup']=sanitize_after_export(ROOT/rel)
                proof['mesh_sha256']=sha(ROOT/rel);proof['blob_sha256']=sha(str(ROOT/rel)+'.blob')
                patches.append(dict(style=style,lod=lod,target=rel,mesh_ref=body['mesh'],before=before.relative_to(ROOT).as_posix(),
                    after=after.relative_to(ROOT).as_posix(),before_materials=bm,after_materials=am,baseline_materials=body['materials'],**proof))
                for o in list(bpy.context.scene.objects):
                    if o.get('roof26_animation_kind')!='louver':continue
                    pivot=list(o['roof26_pivot']);name='fxn5c_v26_'+o['roof26_animation_group']+f'_lod{lod}'
                    p,mats,clean=export(name,[o],ROOT/f'staging/codex_fxn5c_1/res/models/mesh/vehicle/train/{style}',pivot)
                    parts.append(dict(style=style,lod=lod,kind='louver',name=name,mesh=f'vehicle/train/{style}/{name}.msh',
                        materials=mats,pivot=pivot,mesh_local=True,direction=o['roof26_direction'],target=p.relative_to(ROOT).as_posix(),
                        mesh_sha256=sha(p),blob_sha256=sha(str(p)+'.blob'),triangles=clean['triangles']))
            out=ROOT/(style+'_source.blend') if lod==0 else ROOT/'runtime'/f'final37_{style}_lod{lod}.blend'
            save(out);sources.append(dict(file=out.relative_to(ROOT).as_posix(),sha256=sha(out)))
            print('BUILD37_SCENE',style,lod,flush=True)
    groups=defaultdict(list)
    for p in parts:
        if p['kind']=='louver':groups[(p['style'],p['lod'],p['pivot'][0],p['direction'])].append(p)
        if p['kind']=='side_louver':p['fixed_degrees']=55
    animation_files={}
    for (style,lod,x,side),group in groups.items():
        z0=min(p['pivot'][2] for p in groups[(style,0,x,side)]);z1=max(p['pivot'][2] for p in groups[(style,0,x,side)])
        for i,p in enumerate(sorted(group,key=lambda p:-p['pivot'][2])):
            delay=480*(z1-p['pivot'][2])/(z1-z0);times=list(range(0,801,25))
            data=dict(times=times,transfs=[matrix('X',side*math.radians(20)*(1-math.cos(2*math.pi*(t-delay)/800))) for t in times])
            ref=f'vehicle/train/fxn5c_v37/roof_{"p" if side>0 else "m"}_lod{lod}_row{i:02}.ani'
            dest=ROOT/'staging/codex_fxn5c_1/res/models/animation'/ref;dest.parent.mkdir(parents=True,exist_ok=True)
            text='function data()\nreturn '+lua_literal(data)+'\nend\n'
            if ref in animation_files:assert dest.read_text()==text
            else:dest.write_text(text,encoding='utf8');animation_files[ref]=sha(dest)
            p['animation_ref']=ref;p['delay_ms']=delay
    byref={p['mesh_ref']:p for p in patches};models=[];placeholders=[]
    for path in (BASE/'staging/codex_fxn5c_1/res/models/model/vehicle/train').glob('*.mdl'):
        model=read_lua(path);style='fxn5c_jinwen' if 'jinwen' in path.stem else 'fxn5c'
        for lod,row in enumerate(model['lods']):
            lookup={p['name']:p for p in parts if p['style']==style and p['lod']==lod}
            for n in walk(row['node']):
                if n.get('mesh') in byref:n['materials']=byref[n['mesh']]['materials']
                if n.get('name','').startswith('fxn5c_v26_louver_side_'):
                    p=lookup[n['name']];tf=Matrix.Translation(Vector(p['pivot']))@Matrix.Rotation(math.radians(55*p['direction']),4,'X')
                    n['transf']=[tf[r][c] for c in range(4) for r in range(4)];n.pop('animations',None)
                elif n.get('name','').startswith('fxn5c_v26_louver_'):
                    if n['name'] in lookup:
                        p=lookup[n['name']];replacement,_=_base_node(p['mesh'],p['materials'],p['pivot'],p['name'],True)
                        replacement['animations']={'forever':{'type':'FILE_REF','params':{'id':p['animation_ref']}}}
                        n.clear();n.update(replacement)
                    else:
                        name=n['name'];tf=n['transf'];n.clear();n.update(name=name,transf=tf,children=[])
                        placeholders.append(dict(model=path.stem,lod=lod,name=name))
        s=lua_literal(model)
        for v in model['metadata']['description'].values():
            token=lua_literal(v);assert s.count(token)==1;s=s.replace(token,'_('+token+')',1)
        (ROOT/path.relative_to(BASE)).write_text('function data()\nreturn '+s+'\nend\n',encoding='utf8');models.append(path.stem)
    mod=ROOT/'staging/codex_fxn5c_1'
    text=(BASE/'staging/codex_fxn5c_1/mod.lua').read_text();assert text.count('minorVersion = 36')==1
    (mod/'mod.lua').write_text(text.replace('minorVersion = 36','minorVersion = 37'),encoding='utf8')
    lines=(BASE/'staging/codex_fxn5c_1/strings.lua').read_text(encoding='utf8').splitlines(keepends=True)
    for i,line in enumerate(lines):
        if 'MOD_NAME =' in line:lines[i]=line.replace('v0.36','v0.37')
        elif 'MOD_DESC = "' in line:
            note=('v0.37 候选：大散热窗固定打开55°；车顶小百叶近景9片、更大叶片、40°开度，保持0.8秒波浪。未游戏实测。' if '复兴5C' in line else 'v0.37 candidate: large shutters held at 55 degrees; roof shutters use nine larger near-detail blades and a 40-degree, 0.8 s wave. Not engine-tested.')
            lines[i]=line.replace('MOD_DESC = "','MOD_DESC = "'+note+'\\n\\n',1)
        elif 'FXN5C_ROOF_ANIMATION_TOOLTIP =' in line:
            tip=('风扇持续旋转；车顶小百叶波浪开合。大散热窗始终打开，所有动画选项均保留此姿态。展示动画，非温控模拟；改选项后重载存档。' if '风扇' in line else 'Fans rotate and roof shutters wave. Large shutters stay open in every mode. Display only, not thermal control; reload after changing options.')
            lines[i]='    FXN5C_ROOF_ANIMATION_TOOLTIP = '+lua_literal(tip)+',\n'
    (mod/'strings.lua').write_text(''.join(lines),encoding='utf8')
    manifest=dict(status='BUILT_PENDING_AUDIT',baseline_version='0.36',animated=parts,patches=patches,sources=sources,changes=changes,
        models=models,placeholders=placeholders,animation_files=animation_files,
        recipe_sha256={p:sha(ROOT/p) for p in ('build_v37.py','shutters_v37.py')},game_verified=False,installed=False,published=False)
    (ROOT/'manifest_v37.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('BUILD37_PASS',len(models),len(parts),len(animation_files))
if __name__=='__main__':main()
