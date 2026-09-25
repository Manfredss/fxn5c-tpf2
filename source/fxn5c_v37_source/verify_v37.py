"""Independent native scope, mesh deltas, hierarchy, poses, curves and budgets."""
from pathlib import Path
from collections import Counter,defaultdict
from copy import deepcopy
import sys,json,math
import numpy as np
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'fxn5c_v36_source'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from verify_native import read_lua
from native_patch_v23 import decode,sha
from verify_v26 import Resources26,zero_triangles
from verify_native_v24 import check_model,flatten,common_topology
from roster_v21 import ROSTER,group_stem

def main():
    m=json.loads((ROOT/'manifest_v37.json').read_text());assert len(m['patches'])==4 and len(m['animated'])==272
    for p,h in m['recipe_sha256'].items():assert sha(ROOT/p)==h
    modified={p['target'] for p in m['patches']+[p for p in m['animated'] if p['kind']=='louver']}
    modified|={p+'.blob' for p in list(modified)}
    preserved=0
    for p in (BASE/'staging/codex_fxn5c_1/res').rglob('*'):
        if not p.is_file():continue
        rel=p.relative_to(BASE).as_posix();assert (ROOT/rel).is_file()
        if rel not in modified and p.suffix!='.mdl':assert sha(p)==sha(ROOT/rel),rel;preserved+=1
    for r in m['patches']:
        assert sha(ROOT/r['target'])==r['mesh_sha256'] and sha(str(ROOT/r['target'])+'.blob')==r['blob_sha256']
        _,old,_,ot=decode(BASE/r['target'],r['baseline_materials']);_,_,_,bt=decode(ROOT/r['before'],r['before_materials'])
        _,_,_,at=decode(ROOT/r['after'],r['after_materials']);_,new,_,nt=decode(ROOT/r['target'],r['materials'])
        oc,bc,ac=[Counter(t[0] for t in ts) for ts in (ot,bt,at)]
        assert Counter(t[0] for t in nt)==(oc-(bc-ac)+(ac-bc))-zero_triangles(old,ot)
        for key,a in old.items():assert a.tobytes()==new[key][:len(a)].tobytes()
        for rel,mats in ((r['before'],r['before_materials']),(r['after'],r['after_materials'])):
            _,arr,_,rows=decode(ROOT/rel,mats)
            for _,_,ids in rows:
                ps=arr['position'][ids];assert ps[:,2].min()>3.96 and ps[:,2].max()<4.26
                assert np.abs(ps[:,0]).min()>7.2 and np.abs(ps[:,0]).max()<8.1
    resources=Resources26();resources.load();models={};summaries=[];matrix_samples=0
    for row in ROSTER:
        path=ROOT/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{row["stem"]}.mdl'
        model=read_lua(path);old=read_lua(BASE/path.relative_to(ROOT));expected=deepcopy(old)
        style='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        legacy=deepcopy(model)
        for lod in legacy['lods']:lod['node']['children']=[n for n in lod['node']['children'] if not n['name'].startswith('fxn5c_v26_')]
        resources.lua[path]=legacy
        try:_,legacy_report=check_model(row,resources)
        finally:resources.lua[path]=model
        for lod,(a,b) in enumerate(zip(expected['lods'],model['lods'])):
            oldnodes=flatten(a['node'])[0];newnodes=flatten(b['node'])[0]
            assert [n['name'] for n,_,_ in oldnodes]==[n['name'] for n,_,_ in newnodes]
            parts={p['name']:p for p in m['animated'] if p['style']==style and p['lod']==lod}
            roof_groups=defaultdict(list);placeholder_count=0
            for (o,_,_),(n,_,_) in zip(oldnodes,newnodes):
                if n['name']=='body':o['materials']=n['materials']
                if not n['name'].startswith('fxn5c_v26_'):continue
                if n['name'] not in parts:
                    assert n==dict(name=o['name'],transf=o['transf'],children={}),n
                    assert n['name'].startswith('fxn5c_v26_louver_');o.clear();o.update(n);placeholder_count+=1;continue
                part=parts[n['name']];mesh=resources.meshes[n['mesh']]
                if part['kind']=='louver':
                    o.clear();o.update(n)
                    assert n['mesh']==part['mesh'] and n['materials']==part['materials']
                    assert n['transf'][12:15]==part['pivot']
                    ref=n['animations']['forever']['params']['id'];assert ref==part['animation_ref']
                    frames=read_lua(ROOT/'staging/codex_fxn5c_1/res/models/animation'/ref)
                    assert frames['times']==list(range(0,801,25)) and len(frames['transfs'])==33
                    assert np.allclose(frames['transfs'][0],frames['transfs'][-1])
                    roof_groups[(part['pivot'][0],part['direction'])].append((part,frames))
                    transforms=[np.asarray(n['transf']).reshape(4,4,order='F')@np.asarray(raw).reshape(4,4,order='F') for raw in frames['transfs']]
                elif part['kind']=='side_louver':
                    tf=np.eye(4);angle=math.radians(55*part['direction']);c,s=math.cos(angle),math.sin(angle)
                    tf[1:3,1:3]=[[c,-s],[s,c]];tf[:3,3]=part['pivot']
                    assert np.allclose(np.asarray(n['transf']).reshape(4,4,order='F'),tf,atol=1e-7) and not n.get('animations')
                    o['transf']=n['transf'];o.pop('animations',None);transforms=[tf]
                else:
                    assert n==o;transforms=[np.asarray(n['transf']).reshape(4,4,order='F')]
                for tf in transforms:
                    ps=mesh['attributes']['position']@tf[:3,:3].T+tf[:3,3]
                    assert np.all(ps.min(0)>=np.asarray(model['boundingInfo']['bbMin'])-1e-4)
                    assert np.all(ps.max(0)<=np.asarray(model['boundingInfo']['bbMax'])+1e-4)
                resources.referenced_meshes.add(n['mesh'])
            assert placeholder_count==(4 if lod<2 else 0)
            for (_,side),group in roof_groups.items():
                assert len(group)==(9 if lod==0 else 4)
                group.sort(key=lambda r:-r[0]['pivot'][2]);delays=[]
                for p,c in group:
                    delays.append(p['delay_ms'])
                    for t,raw in zip(c['times'],c['transfs']):
                        tf=np.asarray(raw).reshape(4,4,order='F');r=tf[:3,:3]
                        assert np.allclose(r.T@r,np.eye(3)) and np.allclose(r[:,0],[1,0,0]) and np.allclose(tf[:3,3],0)
                        angle=math.degrees(math.atan2(r[2,1],r[1,1]))*side
                        assert abs(angle-20*(1-math.cos(2*math.pi*(t-p['delay_ms'])/800)))<1e-8
                        assert -.00001<=angle<=40.00001;matrix_samples+=1
                assert all(b>a for a,b in zip(delays,delays[1:]))
            count=legacy_report['lods'][lod]['instanced_triangles']+sum(p['triangles'] for p in parts.values())
            assert count<(500000,220000,6000)[lod]
        assert expected==model,('unrelated model fields',row['stem'])
        models[row['stem']]=model;summaries.append(dict(stem=row['stem'],lods=legacy_report['lods']))
    for jw in (False,True):
        rows=[r for r in ROSTER if r['jinwen']==jw];tops=[common_topology(models[r['stem']]) for r in rows];assert all(t==tops[0] for t in tops)
        stem=group_stem(rows[0]);p=ROOT/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{stem}.mdl';model=read_lua(p)
        assert model['lods']==models[rows[0]['stem']]['lods'];models[stem]=model
    for stem,model in models.items():(ROOT/f'native_scene_{stem}.json').write_text(json.dumps(model),encoding='utf8')
    (ROOT/'native_scene.json').write_text(json.dumps(models['fxn5c']),encoding='utf8')
    (ROOT/'native_scene_jinwen.json').write_text(json.dumps(models['fxn5c_jinwen']),encoding='utf8')
    (ROOT/'native_meshes.json').write_text(json.dumps(resources.descriptors),encoding='utf8')
    result=dict(status='PASS',models=12,preserved_resources=preserved,static_large_shutters_per_style=80,
        roof_blades_per_window={'lod0':9,'lod1':4},placeholder_nodes_preserve_ids=True,curve_samples=matrix_samples,
        hinge_body_delta_only=True,models_report=summaries,game_verified=False)
    (ROOT/'validation_v37.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    m['status']='NATIVE_STATIC_PASS';m['validation_sha256']=sha(ROOT/'validation_v37.json')
    (ROOT/'manifest_v37.json').write_text(json.dumps(m,indent=2),encoding='utf8')
    print('VERIFY37_PASS',preserved,matrix_samples)
if __name__=='__main__':main()
