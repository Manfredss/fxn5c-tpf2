"""Independent v26 native deltas, preserved fleet and scoped animation checks.

No generator assertions are accepted as proof. Native geometry is independently
decoded, keyframes are interpreted here, and all original node IDs are compared
with v25. A CPU sweep is NOT a Model Editor/game execution test.
"""
from pathlib import Path
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import sys,json,math
import numpy as np
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'fxn5c_v25_source'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from verify_native import read_lua,plain
from verify_native_v24 import SharedResources,check_model,common_topology,flatten,IDENTITY
from roster_v21 import ROSTER,group_stem
from native_patch_v23 import decode,sha
RES=ROOT/'staging/codex_fxn5c_1/res'
PREFIX='fxn5c_v26_'


class Resources26(SharedResources):
    def table(self,path):
        path=Path(path)
        if path==RES.parent/'mod.lua' and path not in self.lua:
            # Execute the actual local options dependency rather than stub
            # require() out. Legacy readers did not need Lua package.path.
            from lupa import LuaRuntime
            lua=LuaRuntime(register_eval=False)
            lua.globals().package.path=(RES/'scripts/?.lua').as_posix()
            lua.execute('function _(s) return s end')
            lua.execute(path.read_text(encoding='utf8'))
            self.lua[path]=plain(lua.globals().data())
            self.inputs[path.relative_to(ROOT).as_posix()]=sha(path)
            helper=RES/'scripts/fxn5c_animation_v26.lua'
            self.inputs[helper.relative_to(ROOT).as_posix()]=sha(helper)
            parameters=self.lua[path]['info']['params']
            motion=next(p for p in parameters if p['key']=='codex_fxn5c_roof_animation')
            assert motion['defaultIndex']==0 and len(motion['values'])==3
        return super().table(path)


def clean_model(model,strip_animation=False):
    result=deepcopy(model)
    for lod in result['lods']:
        if strip_animation:
            lod['node']['children']=[n for n in lod['node']['children'] if not n['name'].startswith(PREFIX)]
        for n,_,_ in flatten(lod['node'])[0]:
            if n['name']=='body':n['materials']=[]
    return result


def zero_triangles(arrays,records):
    ids=np.asarray([r[2] for r in records]);pts=arrays['position'][ids].astype(float)
    dead=np.all(np.cross(pts[:,1]-pts[:,0],pts[:,2]-pts[:,0])==0,axis=1)
    return Counter(r[0] for r,d in zip(records,dead) if d)


def rotate(points,axis,degrees):
    a=math.radians(degrees);c,s=math.cos(a),math.sin(a)
    if axis==0:r=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    else:r=np.array([[c,0,s],[0,1,0],[-s,0,c]])
    return points@r.T


def validate_animation_node(node,part,shared,model):
    assert node['name']==part['name'] and node['mesh']==part['mesh']
    assert node['materials']==part['materials']
    assert part.get('mesh_local') is True,('expected mesh-local export',part['name'])
    pivot=np.asarray(part['pivot'],float)
    tf=np.asarray(node['transf'],float)
    expected=np.asarray(IDENTITY,float);expected[12:15]=pivot
    assert np.max(np.abs(tf-expected))<1e-7,('pivot translation mismatch',node['name'])
    assert not node.get('children') and 'skin' not in node
    assert set(node['animations'])=={'forever'}
    animation=node['animations']['forever']
    assert animation['type']=='KEYFRAME' and animation['forward'] is True
    assert animation['params']['origin']==[0,0,0],('double pivot offset',node['name'])
    frames=animation['params']['keyframes'];times=[f['time'] for f in frames]
    assert times[0]==0 and all(b>a for a,b in zip(times,times[1:]))
    assert all(f['transl']==[0,0,0] for f in frames)
    axis=1 if part['kind']=='fan' else 0
    angles=[]
    for f in frames:
        assert len(f['rot'])==3 and all(math.isfinite(x) for x in f['rot'])
        assert all(v==0 for i,v in enumerate(f['rot']) if i!=axis),('non-hinge rotation',node['name'])
        angles.append(f['rot'][axis])
    if part['kind']=='fan':
        assert len(frames)==5 and angles[0]==0 and abs(angles[-1])==360
        sign=1 if angles[-1]>0 else -1
        assert angles==[sign*a for a in (0,90,180,270,360)]
        assert all(times[i]*4==times[-1]*i for i in range(5))
        sweep=list(range(0,361,15))
    else:
        assert part['kind']=='louver' and len(frames)==6
        assert angles[0]==angles[1]==angles[-2]==angles[-1]==0
        assert angles[2]==angles[3] and 0<abs(angles[2])<=45
        sweep=np.linspace(0,angles[2],13)
    mesh=shared.meshes[part['mesh']]
    assert len(part['materials'])==mesh['submeshes'] and mesh['triangles']==part['triangles']
    assert 'jointWeights' not in mesh['attributes']
    for material in node['materials']:shared.material(material)
    points=mesh['attributes']['position'].astype(float)
    low=np.full(3,np.inf);high=np.full(3,-np.inf)
    for angle in sweep:
        world=rotate(points,axis,angle)+pivot
        low=np.minimum(low,world.min(axis=0));high=np.maximum(high,world.max(axis=0))
    assert np.all(low>=np.asarray(model['boundingInfo']['bbMin'])-1e-4)
    assert np.all(high<=np.asarray(model['boundingInfo']['bbMax'])+1e-4)
    if part['kind']=='fan':
        # Bounding disk also covers every intermediate angle, not only frames.
        radius=np.hypot(points[:,0],points[:,2]).max()
        assert radius<.279-1e-4,('rotor intersects shroud',node['name'],radius)
        assert pivot[0]-radius>2.10 and pivot[0]+radius<3.60
        assert pivot[2]-radius>3.95 and pivot[2]+radius<4.65
        assert low[1]>-1.65 and high[1]<-.99
    else:
        assert abs(pivot[0])>7 and abs(pivot[1])>1
        assert low[2]>3.95 and high[2]<4.30,('louver leaves mounting region',node['name'])
    shared.referenced_meshes.add(part['mesh'])
    return dict(name=node['name'],kind=part['kind'],axis='XYZ'[axis],period_ms=times[-1],
                angle_range_degrees=[min(angles),max(angles)],samples=len(sweep),
                swept_min=low.tolist(),swept_max=high.tolist(),engine_executed=False)


def main():
    manifest=json.loads((ROOT/'manifest_v26.json').read_text())
    for recipe,digest in manifest['recipe_sha256'].items():
        assert sha(ROOT/recipe)==digest,('recipe changed after build',recipe)
    assert {(r['style'],r['lod']) for r in manifest['patches']}=={
        (s,l) for s in ('fxn5c','fxn5c_jinwen') for l in (0,1,2)},'incomplete six body patches'
    animated=manifest['animated'];assert animated,'no native motion resources'
    targets={r['target'] for r in manifest['patches']+animated}
    expected=targets|{p+'.blob' for p in targets}
    # Existing non-body resources may not change. New motion meshes and their
    # explicit option script are allowed; nothing else is silently exempt.
    added_scripts={'staging/codex_fxn5c_1/res/scripts/fxn5c_animation_v26.lua'}
    baseline_files={p.relative_to(BASE).as_posix() for p in (BASE/'staging/codex_fxn5c_1/res').rglob('*') if p.is_file()}
    current_files={p.relative_to(ROOT).as_posix() for p in RES.rglob('*') if p.is_file()}
    assert baseline_files<=current_files,('existing resources removed',baseline_files-current_files)
    assert current_files-baseline_files<=expected|added_scripts,('undeclared new resources',current_files-baseline_files-expected-added_scripts)
    preserved=[]
    for rel in sorted(baseline_files):
        if rel in expected or rel.endswith('.mdl'):continue
        assert sha(ROOT/rel)==sha(BASE/rel),('unrelated resource changed',rel)
        preserved.append(rel)
    deltas=[]
    for row in manifest['patches']:
        assert sha(ROOT/row['target'])==row['mesh_sha256']
        assert sha(str(ROOT/row['target'])+'.blob')==row['blob_sha256']
        _,old_arrays,_,old=decode(BASE/row['target'],row['baseline_materials'])
        _,_,_,before=decode(ROOT/row['before'],row['before_materials'])
        _,_,_,after=decode(ROOT/row['after'],row['after_materials'])
        _,arrays,_,actual=decode(ROOT/row['target'],row['materials'])
        oc=Counter(r[0] for r in old);bc=Counter(r[0] for r in before);ac=Counter(r[0] for r in after)
        inherited_zero=zero_triangles(old_arrays,old)
        assert Counter(r[0] for r in actual)==(oc-(bc-ac)+(ac-bc))-inherited_zero,('native triangle delta mismatch',row['target'])
        assert not zero_triangles(arrays,actual),('zero-area output triangle',row['target'])
        for key,values in old_arrays.items():
            assert arrays[key][:len(values)].tobytes()==values.tobytes(),('original attribute prefix changed',key)
        for change,source,mats in ((bc-ac,ROOT/row['before'],row['before_materials']),
                                   (ac-bc,ROOT/row['after'],row['after_materials'])):
            _,at,_,rr=decode(source,mats)
            for key,slot,tri in rr:
                if change[key]:assert at['position'][tri,2].min()>3.88,('non-roof delta',row['target'])
        deltas.append(dict(style=row['style'],lod=row['lod'],triangles=len(actual),
            removed=sum((bc-ac).values()),added=sum((ac-bc).values()),degenerate_triangles=0))
    for part in animated:
        assert sha(ROOT/part['target'])==part['mesh_sha256']
        assert sha(str(ROOT/part['target'])+'.blob')==part['blob_sha256']
        _,a,_,records=decode(ROOT/part['target'],part['materials'])
        assert len(records)==part['triangles'] and not zero_triangles(a,records)
    shared=Resources26();shared.load();models={};reports=[]
    assert len(ROSTER)==len({r['stem'] for r in ROSTER})==10
    for row in ROSTER:
        style='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        path=RES/f'models/model/vehicle/train/{row["stem"]}.mdl'
        model=shared.table(path)
        old=read_lua(BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{row["stem"]}.mdl')
        assert clean_model(model,True)==clean_model(old),('unintended hierarchy/metadata edit',row['stem'])
        # Run all old wheel/signage/light checks against unchanged original
        # nodes. They enforce signage-last; appended animation nodes are then
        # audited independently, including exact append position and bounds.
        legacy=deepcopy(model)
        for lod in legacy['lods']:
            lod['node']['children']=[n for n in lod['node']['children'] if not n['name'].startswith(PREFIX)]
        shared.lua[path]=legacy
        try:_,report=check_model(row,shared)
        finally:shared.lua[path]=model
        animation_reports=[]
        for index,lod in enumerate(model['lods']):
            original=old['lods'][index]['node']['children'];nodes=lod['node']['children']
            appended=nodes[len(original):]
            expected_parts=[p for p in animated if p['style']==style and p['lod']==index]
            assert [n['name'] for n in appended]==[p['name'] for p in expected_parts],('animation node append order',row['stem'],index)
            assert all(not n['name'].startswith(PREFIX) for n in nodes[:len(original)])
            assert len(flatten(lod['node'])[0])==len(flatten(old['lods'][index]['node'])[0])+len(appended)
            for n,p in zip(appended,expected_parts):animation_reports.append(validate_animation_node(n,p,shared,model))
            full_triangles=report['lods'][index]['instanced_triangles']+sum(p['triangles'] for p in expected_parts)
            assert full_triangles<(500000,220000,6000)[index],('full-model polygon budget',index,full_triangles)
            report['lods'][index]['instanced_triangles_with_animation']=full_triangles
        assert Counter(p['kind'] for p in animated if p['style']==style and p['lod']==0)['fan']==2
        assert not [p for p in animated if p['style']==style and p['lod']==2]
        report['animations']=animation_reports
        report['actual_geometry_audit_replacements']={
            'roof':'roof_geometry_v26.json: selected saved-source geometry and mounting tests',
            'native':'verify_v26.py: independent body delta, motion schema and sampled sweep',
            'unaffected':'v25 byte preservation and explicit unchanged hierarchy, not new game proof'}
        models[row['stem']]=model;reports.append(report)
        print('FLEET26_PASS',row['stem'],flush=True)
    for style in (False,True):
        templates=[common_topology(models[r['stem']]) for r in ROSTER if r['jinwen']==style]
        assert all(t==templates[0] for t in templates)
        row=next(r for r in ROSTER if r['jinwen']==style)
        group=read_lua(RES/f'models/model/vehicle/train/{group_stem(row)}.mdl')
        assert group['lods']==models[row['stem']]['lods'],'group preview mismatch'
        oldgroup=read_lua(BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{group_stem(row)}.mdl')
        assert clean_model(group,True)==clean_model(oldgroup),'unintended group metadata/hierarchy edit'
        assert group['metadata']['transportVehicle']['multipleUnitOnly'] is True
        assert group['metadata']['transportVehicle']['groupFileName']==''
    for stem,model in models.items():(ROOT/f'native_scene_{stem}.json').write_text(json.dumps(model),encoding='utf8')
    (ROOT/'native_scene.json').write_text(json.dumps(models['fxn5c']),encoding='utf8')
    (ROOT/'native_scene_jinwen.json').write_text(json.dumps(models['fxn5c_jinwen']),encoding='utf8')
    (ROOT/'native_meshes.json').write_text(json.dumps(shared.descriptors),encoding='utf8')
    result=dict(status='PASS',generated_utc=datetime.now(timezone.utc).isoformat(),models=reports,
        validator_sha256=sha(Path(__file__)),baseline_manifest_sha256=sha(BASE/'manifest_v25.json'),
        patches=deltas,animated_resources=len(animated),preserved_resources=len(preserved),
        inputs_sha256=shared.inputs,geometry_scope='roof body delta, local animated fan/louver meshes, preserved original hierarchy',
        limitations='CPU rigid sweeps and static resource checks only; no measured thermal control, engine animation or game playtest',
        game_verified=False,model_editor_verified=False,game_installation_modified=False)
    (ROOT/'validation_v26.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    manifest['status']='NATIVE_STATIC_PASS';manifest['validation_sha256']=sha(ROOT/'validation_v26.json')
    (ROOT/'manifest_v26.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    print('VERIFY26_PASS',len(models),len(deltas),len(animated),len(preserved),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        (ROOT/'validation_v26.json').write_text(json.dumps(dict(status='FAIL',error=repr(error),game_verified=False),indent=2),encoding='utf8')
        raise
