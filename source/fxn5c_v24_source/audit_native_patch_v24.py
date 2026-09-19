"""Independent native delta/retention check; no builder/patcher invocation."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import hashlib,json,sys
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
BASE=ROOT.parent/'fxn5c_v23_source'
RES=Path('staging/codex_fxn5c_1/res')
from audit_native_patch_v23 import decode,assert_patch,negative_controls
from verify_native import read_lua
from roster_v21 import ROSTER
from package_release_v21 import native_closure

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def require(value,detail):
    if not value:raise AssertionError(detail)
def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)

def audit_tessellation(proof,old):
    a=np.asarray(proof['source_patch_vertices'],dtype=float)
    b=np.asarray(proof['native_patch_vertices'],dtype=float)
    require(a.shape==(5,3,3) and b.shape==(3,3,3),'bounded roof calibration')
    actual=old['attrs']['position'][np.asarray(proof['native_vertex_indices'])].astype(float)
    require(np.array_equal(actual,b),'calibration did not use actual native vertices')
    def perimeter(tris):
        edges=Counter((tuple(p[i]),tuple(p[(i+1)%3])) for p in tris for i in range(3))
        return edges-Counter({(y,x):n for (x,y),n in edges.items()})
    require(perimeter(a)==perimeter(b) and len(perimeter(a))==5,'oriented perimeter drift')
    cross_a=np.cross(a[:,1]-a[:,0],a[:,2]-a[:,0]);cross_b=np.cross(b[:,1]-b[:,0],b[:,2]-b[:,0])
    area_a=float(np.linalg.norm(cross_a,axis=1).sum()*.5)
    area_b=float(np.linalg.norm(cross_b,axis=1).sum()*.5)
    require(abs(area_a-area_b)<1e-10 and abs(area_a-1.02982084157059)<1e-10,'calibration area')
    normals=np.concatenate((cross_a,cross_b));normals/=np.linalg.norm(normals,axis=1)[:,None]
    require(float((normals@normals.T).min())>.99999999999,'calibration winding')
    require(float(np.abs((np.concatenate((a,b))-a[0,0])@normals[0]).max())<5e-7,'calibration coplanarity')
    return dict(status='PASS',source_triangles=5,native_triangles=3,oriented_perimeter_identical=True,
                source_area_m2=area_a,native_area_m2=area_b,tolerance_not_relaxed=True)

def main():
    mf=ROOT/'native_patch_manifest_v24.json';manifest=json.loads(mf.read_text(encoding='utf-8'))
    records=manifest['patches']
    require(len(records)==6 and {(r['style'],r['lod']) for r in records}=={(s,l) for s in ('fxn5c','fxn5c_jinwen') for l in (0,1,2)},'six body deltas')
    report=dict(status='RUNNING',patches=[],models=[],inputs_sha256={},baseline_sha256={},game_verified=False)
    def bind(path):
        path=Path(path);report['inputs_sha256'][path.relative_to(ROOT).as_posix()]=sha(path)
    for row in records:
        relative=(RES/'models/mesh'/row['mesh_ref']).as_posix()
        require(row['attachment']=='body' and row['target']==relative,'only body patches allowed')
        require((ROOT/row['baseline']).resolve()==(BASE/relative).resolve(),'wrong v23 baseline')
        old=decode(BASE/relative,row['baseline_materials'])
        before=decode(ROOT/row['before']['file'],row['before']['materials'])
        after=decode(ROOT/row['after']['file'],row['after']['materials'])
        current=decode(ROOT/relative,row['materials'])
        clean=row['after']['export_sanitization']
        require(clean['source_scene_modified'] is False and clean['original_attribute_bytes_unchanged'] is True,'export-only cleanup contract')
        path=ROOT/row['after']['file'];desc=read_lua(path);raw=Path(str(path)+'.blob').read_bytes()
        prefix=max(a['offset']+a['count'] for a in desc['vertexAttr'].values())
        require(hashlib.sha256(raw[:prefix]).hexdigest()==clean['attribute_prefix_sha256'],'sanitizer changed its input attributes')
        require(clean['triangles']==len(after['rows'])==row['after']['triangles'],'sanitized count')
        for slot,sub in enumerate(desc['subMeshes']):
            field=sub['indices']['position'];data=raw[field['offset']:field['offset']+field['count']]
            require(hashlib.sha256(data).hexdigest()==clean['slots'][slot]['valid_original_index_bytes_sha256'],'valid export index bytes changed')
            ids=np.frombuffer(data,dtype='<u4').reshape(-1,3);p=after['attrs']['position'][ids].astype(float)
            require(not np.all(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])==0,axis=1).any(),'zero-area triangle survived AFTER sanitizer')
        if row['style']=='fxn5c_jinwen' and row['lod']==2:
            entry=next(c for c in manifest['scene_changes'] if c['style']==row['style'] and c['lod']==2)
            report['baseline_tessellation']=audit_tessellation(entry['changes']['baseline_tessellation'],old)
        result=assert_patch(old,before,after,current,relative)
        for key in ('removed_triangles','added_triangles','retained_triangles','original_vertices','added_vertices'):
            require(result[key]==row[key],('stale delta count',relative,key))
        require(sha(ROOT/relative)==row['mesh_sha256'] and sha(ROOT/(relative+'.blob'))==row['blob_sha256'],'stale body hash')
        if not report.get('negative_controls') and result['added_triangles']:
            report['negative_controls']=negative_controls(old,before,after,current)
        report['patches'].append(dict(target=relative,export_sanitization=clean,**result))
        for name in (relative,row['before']['file'],row['after']['file']):
            bind(ROOT/name);bind(ROOT/(name+'.blob'))
        for suffix in ('','.blob'):report['baseline_sha256'][relative+suffix]=sha(BASE/(relative+suffix))
    by_ref={r['mesh_ref']:r for r in records}
    row_by_stem={r['stem']:r for r in ROSTER}
    row_by_stem.update(fxn5c_menu_cr=ROSTER[0],fxn5c_menu_jinwen=next(r for r in ROSTER if r['jinwen']))
    legacy={'headlights_fwd','headlights_bwd','taillights_fwd','taillights_bwd'}
    pane_records={(r['style'],r['lod'],r['name']):r for r in manifest['panes']}
    for stem,row in row_by_stem.items():
        relative=RES/f'models/model/vehicle/train/{stem}.mdl'
        actual=read_lua(ROOT/relative);old=read_lua(BASE/relative);expected=deepcopy(old)
        # Normalize explicitly permitted changes, then compare the rest of the
        # complete model: all transforms, wheel/skin children and metadata.
        normalized=deepcopy(actual)
        style='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        for lod,(a,e) in enumerate(zip(normalized['lods'],expected['lods'])):
            a['node']['children']=[n for n in a['node']['children'] if not n['name'].startswith('light24_')]
            e['node']['children']=[n for n in e['node']['children'] if n['name'] not in legacy]
            for node in walk(a['node']):
                if node.get('mesh') in by_ref:
                    record=by_ref[node['mesh']]
                    require(node['materials']==record['materials'],'body material mismatch')
                    node['materials']=record['baseline_materials']
                key=(style,lod,node['name'])
                if key in pane_records:
                    record=pane_records[key]
                    require(node['mesh']==record['mesh_ref'] and node['transf']==record['transf'] and node['materials']==record['materials'],'upper glazing mismatch')
                    prior=next(n for n in walk(e['node']) if n['name']==node['name'])
                    node['transf']=prior['transf'];node['materials']=prior['materials']
            config=normalized['metadata']['railVehicle']['configs'][lod]
            prior=expected['metadata']['railVehicle']['configs'][lod]
            for position in ('front','inner','back'):
                for direction in ('Forward','Backward'):
                    field=position+direction+'Parts';config[field]=prior[field]
        require(normalized==expected,('unapproved model change',stem))
        bind(ROOT/relative);report['baseline_sha256'][relative.as_posix()]=sha(BASE/relative)
        report['models'].append(dict(stem=stem,unrelated_model_hierarchy_and_metadata_unchanged=True))
    native,_,_=native_closure()
    allowed={r['target']+suffix for r in records+manifest['panes'] for suffix in ('','.blob')}
    for row in ROSTER:
        style='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        for lod in (0,1):
            allowed.update((RES/f'models/mesh/vehicle/train/{style}/signage_{row["number"]}_lod{lod}.msh').as_posix()+suffix for suffix in ('','.blob'))
    allowed.update((RES/f'models/model/vehicle/train/{stem}.mdl').as_posix() for stem in row_by_stem)
    for style in ('fxn5c','fxn5c_jinwen'):
        for lod in (0,1):
            for direction in ('fwd','bwd'):
                allowed.update((RES/f'models/mesh/vehicle/train/{style}/light24_{direction}_lod{lod}.msh').as_posix()+suffix for suffix in ('','.blob'))
    allowed.update(((RES/'models/material/vehicle/train/fxn5c/lamp_moon_v24.mtl').as_posix(),(RES/'textures/models/vehicle/train/fxn5c/lamp_moon_v24.tga').as_posix()))
    unchanged=[]
    for path in sorted(native):
        relative=path.relative_to(ROOT).as_posix();bind(path)
        if relative not in allowed:
            require((BASE/relative).is_file() and path.read_bytes()==(BASE/relative).read_bytes(),('changed unrelated resource',relative))
            unchanged.append(relative)
            report['baseline_sha256'][relative]=sha(BASE/relative)
    require(any('bogie_frame' in n for n in unchanged) and any('connection_rods' in n for n in unchanged),'missing gear preservation')
    report['preservation']=dict(unchanged_resources=unchanged,count=len(unchanged),entire_bogie_wheel_and_rod_resources_retained=True)
    for row in manifest['panes']:
        require(sha(ROOT/row['target'])==row['mesh_sha256'] and sha(ROOT/(row['target']+'.blob'))==row['blob_sha256'],'stale pane')
    for row in manifest['sources']:
        require(sha(ROOT/row['file'])==row['sha256'],'source hash differs');bind(ROOT/row['file'])
    for n,h in manifest['inputs_sha256'].items():require(sha(ROOT/n)==h,('build code changed',n));bind(ROOT/n)
    bind(mf);bind(Path(__file__));bind(ROOT/'audit_native_patch_v23.py')
    report['status']='PASS';report['scope']='Six actual body deltas, permitted upper panes/lighting/numbering, and byte-retained v23 running gear; not engine runtime'
    (ROOT/'audit_native_patch_v24.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('V24_NATIVE_DELTA_PASS',len(unchanged),flush=True)

if __name__=='__main__':main()
