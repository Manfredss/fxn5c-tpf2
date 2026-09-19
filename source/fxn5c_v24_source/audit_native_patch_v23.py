"""Independent byte/triangle audit of targeted v23 native edits.

Does not import the production patcher. A 10 micrometre oriented position key
locates source differences; retained native indices and all original attribute
bytes are then checked exactly. No game installation or files are modified.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,sys
import numpy as np

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v22_source'
MOD=Path('staging/codex_fxn5c_1')
RES=MOD/'res'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from verify_native import read_lua
from roster_v21 import ROSTER

ATTRS={'position':3,'uv0':2,'normal':3,'tangent':4}
STYLES=('fxn5c','fxn5c_jinwen')


def require(ok,message):
    if not ok:raise AssertionError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path,materials):
    path=Path(path);desc=read_lua(path);raw=Path(str(path)+'.blob').read_bytes()
    require(set(desc['vertexAttr'])==set(ATTRS),('patch contains skin/unexpected attributes',path))
    require(len(desc['subMeshes'])==len(materials),('material arity',path))
    attrs,rawattrs={},{}
    for key,arity in ATTRS.items():
        a=desc['vertexAttr'][key];offset,size=a['offset'],a['count']
        require(a['numComp']==arity and size>0 and size%(4*arity)==0 and offset%4==0
                and 0<=offset<=len(raw)-size,('attribute layout',path,key))
        rawattrs[key]=raw[offset:offset+size]
        attrs[key]=np.frombuffer(rawattrs[key],dtype='<f4').reshape(-1,arity)
        require(np.isfinite(attrs[key]).all(),('nonfinite attribute',path,key))
    count=len(attrs['position'])
    require(all(len(v)==count for v in attrs.values()),('attribute counts',path))
    rows=[]
    for slot,(sub,material) in enumerate(zip(desc['subMeshes'],materials)):
        require(set(sub['indices'])==set(ATTRS),('index streams',path))
        streams=[]
        for key in ATTRS:
            a=sub['indices'][key];size,offset=a['count'],a['offset']
            require(size>0 and size%12==0 and offset%4==0 and 0<=offset<=len(raw)-size,('index layout',path,key))
            indices=np.frombuffer(raw,dtype='<u4',count=size//4,offset=offset).reshape(-1,3)
            require(indices.max()<count,('out-of-range index',path,key))
            streams.append(indices)
        require(all(np.array_equal(v,streams[0]) for v in streams[1:]),('different attribute corner indices',path))
        indices=streams[0]
        quantized=np.rint(attrs['position'][indices].astype(np.float64)*100000).astype('<i4').tobytes()
        for index,start in zip(indices,range(0,len(quantized),36)):
            b=quantized[start:start+36]
            canonical=min(b,b[12:]+b[:12],b[24:]+b[:24])
            rows.append(((material,canonical),slot,tuple(int(i) for i in index)))
    return {'attrs':attrs,'rawattrs':rawattrs,'rows':rows,'materials':list(materials),'vertices':count}


def choose_delta_rows(rows,counts,select):
    remain=counts.copy();selected=[]
    for row in rows:
        marked=remain[row[0]]>0
        if marked:remain[row[0]]-=1
        if marked==select:selected.append(row)
    require(not any(remain.values()),'requested delta triangles absent')
    return selected


def assert_patch(old,before,after,current,label):
    original=Counter(k for k,_,_ in old['rows'])
    prior=Counter(k for k,_,_ in before['rows'])
    latest=Counter(k for k,_,_ in after['rows'])
    removed=prior-latest;added=latest-prior
    require(not (removed-original),('source deletion absent from baseline',label))
    surviving=choose_delta_rows(old['rows'],removed,False)
    additions=choose_delta_rows(after['rows'],added,True)
    expected=(original-removed)+added
    require(Counter(k for k,_,_ in current['rows'])==expected,('target geometry/material delta mismatch',label))
    old_n=old['vertices'];new_n=len(additions)*3
    require(current['vertices']==old_n+new_n,('target vertex count',label))
    append_indices=np.asarray([i for _,_,tri in additions for i in tri],dtype=np.int64)
    for attr in ATTRS:
        expected_bytes=old['rawattrs'][attr]+after['attrs'][attr][append_indices].astype('<f4').tobytes()
        require(current['rawattrs'][attr]==expected_bytes,('original prefix or appended raw attribute differs',label,attr))
    # Surviving triplets must still index the exact old vertex numbers in the
    # same material/submesh order. Matching geometric bounds is insufficient.
    actual_old=[(key[0],ids) for key,slot,ids in current['rows'] if max(ids)<old_n]
    expected_old=[(key[0],ids) for key,slot,ids in surviving]
    require(actual_old==expected_old,('retained native index order/values changed',label))
    actual_new=Counter((key[0],ids) for key,slot,ids in current['rows'] if min(ids)>=old_n)
    expected_new=Counter((key[0],(old_n+3*i,old_n+3*i+1,old_n+3*i+2))
                         for i,(key,slot,ids) in enumerate(additions))
    require(actual_new==expected_new,('new triangles use incorrect appended vertices',label))
    require(len(actual_old)+sum(actual_new.values())==len(current['rows']),('mixed old/new vertex triangle',label))
    if len(append_indices):
        p=after['attrs']['position'][append_indices].astype(np.float64).reshape(-1,3,3)
        crosses=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
        dead=np.all(crosses==0,axis=1)
        require(not dead.any(),('new strictly zero-area triangles',label,int(dead.sum())))
    return {'retained_triangles':len(surviving),'removed_triangles':sum(removed.values()),
            'added_triangles':len(additions),'original_vertices':old_n,'added_vertices':new_n,
            'original_raw_attributes_identical':True,'retained_indices_identical':True,
            'appended_attributes_equal_actual_after_snapshot':True}


def negative_controls(old,before,after,current):
    found=[]
    def trial(name,bad):
        try:assert_patch(old,before,after,bad,name)
        except AssertionError:found.append(name)
        else:raise AssertionError('negative control escaped: '+name)
    bad=dict(current);bad['rawattrs']=dict(current['rawattrs'])
    raw=bytearray(bad['rawattrs']['position']);raw[0]^=1;bad['rawattrs']['position']=bytes(raw)
    trial('changed_original_position_byte',bad)
    bad=dict(current);bad['rows']=current['rows'][:-1]
    trial('missing_target_triangle',bad)
    bad=dict(current);bad['rows']=list(current['rows'])
    key,slot,ids=bad['rows'][0];bad['rows'][0]=(key,slot,(ids[1],ids[2],ids[0]))
    trial('retained_index_triplet_rotated',bad)
    bad=dict(current);bad['rawattrs']=dict(current['rawattrs'])
    raw=bytearray(bad['rawattrs']['uv0']);raw[-1]^=1;bad['rawattrs']['uv0']=bytes(raw)
    trial('changed_appended_uv_byte',bad)
    return found


def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)


def models_and_unchanged_files(records,manifest,report):
    by_ref={r['mesh_ref']:r for r in records}
    require(len(by_ref)==len(records),'duplicate patched mesh reference')
    model_dir=RES/'models/model/vehicle/train'
    names={r['stem']+'.mdl' for r in ROSTER}|{'fxn5c_menu_cr.mdl','fxn5c_menu_jinwen.mdl'}
    require({p.name for p in (ROOT/model_dir).glob('*.mdl')}==names,'unexpected model inventory')
    report['models']=[]
    for name in sorted(names):
        old=read_lua(BASE/model_dir/name);actual=read_lua(ROOT/model_dir/name)
        expected=deepcopy(old);changed=[]
        for lod in expected['lods']:
            for node in walk(lod['node']):
                ref=node.get('mesh')
                if ref in by_ref:
                    row=by_ref[ref]
                    require(node['materials']==row['baseline_materials'],('baseline model material mismatch',name,ref))
                    node['materials']=row['materials'];changed.append(ref)
        require(actual==expected,('model changed outside targeted material slots',name))
        report['models'].append({'name':name,'unchanged_hierarchy_metadata_transforms_skin_bindings':True,
                                  'updated_material_resources':changed})
        for root,key in ((ROOT,'inputs_sha256'),(BASE,'baseline_sha256')):
            report[key][(model_dir/name).as_posix()]=sha(root/model_dir/name)
    allowed={r['target'] for r in records}|{r['target']+'.blob' for r in records}
    allowed|={(model_dir/name).as_posix() for name in names}
    expected_signs={(r['stem'],lod) for r in ROSTER for lod in (0,1)}
    require({(r['model'],r['lod']) for r in manifest['signage']}==expected_signs and len(manifest['signage'])==20,
            'ten vehicles times two actual signage resources required')
    for row in ROSTER:
        style='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        for lod in (0,1):
            ref=RES/f'models/mesh/vehicle/train/{style}/signage_{row["number"]}_lod{lod}.msh'
            allowed.update((ref.as_posix(),ref.as_posix()+'.blob'))
    now={p.relative_to(ROOT).as_posix():p for p in (ROOT/RES).rglob('*') if p.is_file()}
    old={p.relative_to(BASE).as_posix():p for p in (BASE/RES).rglob('*') if p.is_file()}
    require(set(now)==set(old),('resource inventory changed',sorted(set(now)-set(old)),sorted(set(old)-set(now))))
    unchanged=[];icons=[]
    for name,path in sorted(now.items()):
        if '/textures/ui/' in name:
            icons.append(name);continue
        report['inputs_sha256'][name]=sha(path)
        report['baseline_sha256'][name]=sha(old[name])
        if name in allowed:continue
        require(path.read_bytes()==old[name].read_bytes(),('unapproved native resource changed',name))
        unchanged.append(name)
    require(len(icons)==48,'expected 48 UI thumbnails; orientation audited separately')
    critical=[n for n in unchanged if any(k in n for k in ('wheelset_lod','connection_rods_lod','conn17_',
                'glazing_','cab_interior','headlights_','taillights_'))]
    require(critical and any('wheelset_lod' in n for n in critical)
            and any('connection_rods_lod' in n for n in critical),'missing critical preserved resources')
    report['preservation']={'unchanged_resource_count':len(unchanged),'unchanged_resources':unchanged,
        'critical_wheel_rod_cab_glass_light_resources':critical,'ui_icon_files_audited_separately':len(icons),
        'scope':'entire native resource inventory except explicit patched meshes, variable signage, model material slots and regenerated UI icons'}


def main():
    manifest_path=ROOT/'native_patch_manifest_v23.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    records=manifest['patches']
    expected={(style,lod,part) for style in STYLES for lod in (0,1,2) for part in ('body','b1','b2')}
    require({(r['style'],r['lod'],r['attachment']) for r in records}==expected and len(records)==18,
            'two styles times three LODs times body/b1/b2 requires18 patches')
    report={'status':'RUNNING','created_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'independent current native patch bytes/indices and preserved hierarchy; not game runtime',
        'inputs_sha256':{},'baseline_sha256':{},'patches':[],'negative_controls':[]}
    for row in records:
        style,lod,part=row['style'],row['lod'],row['attachment']
        mesh_name='body' if part=='body' else 'bogie_frame_'+part
        ref=f'vehicle/train/{style}/{mesh_name}_lod{lod}.msh'
        relative=(RES/'models/mesh'/ref).as_posix()
        require(row['mesh_ref']==ref and row['target']==relative,('patch target outside whitelist',row['target']))
        require((ROOT/row['baseline']).resolve()==(BASE/relative).resolve(),('wrong immutable baseline',relative))
        for phase in ('before','after'):
            expected_path=f'runtime/patch_inputs/{style}/{part}_{phase}_lod{lod}.msh'
            require(row[phase]['file']==expected_path,('snapshot path outside build namespace',relative,phase))
        old=decode(BASE/relative,row['baseline_materials'])
        before=decode(ROOT/row['before']['file'],row['before']['materials'])
        after=decode(ROOT/row['after']['file'],row['after']['materials'])
        current=decode(ROOT/relative,row['materials'])
        result=assert_patch(old,before,after,current,relative)
        for field in ('retained_triangles','removed_triangles','added_triangles','original_vertices','added_vertices'):
            require(result[field]==row[field],('stale patch count',relative,field))
        require(abs(row['position_key_tolerance_m']-.00001)<1e-12,'unsupported source match quantization')
        require(row['mesh_sha256']==sha(ROOT/relative) and row['blob_sha256']==sha(str(ROOT/relative)+'.blob'),
                ('stale target hash',relative))
        require(row['original_attribute_prefix_sha256']=={key:hashlib.sha256(v).hexdigest() for key,v in old['rawattrs'].items()},
                ('stale original attribute hash',relative))
        if not report['negative_controls'] and result['added_triangles']:
            report['negative_controls']=negative_controls(old,before,after,current)
        report['patches'].append({'target':relative,**result})
        for path in (ROOT/row['before']['file'],ROOT/row['after']['file'],ROOT/relative):
            for file in (path,Path(str(path)+'.blob')):
                report['inputs_sha256'][file.relative_to(ROOT).as_posix()]=sha(file)
        for path in (BASE/relative,Path(str(BASE/relative)+'.blob')):
            report['baseline_sha256'][path.relative_to(BASE).as_posix()]=sha(path)
        print('NATIVE_PATCH23_PASS',style,lod,part,result['removed_triangles'],result['added_triangles'],flush=True)
    models_and_unchanged_files(records,manifest,report)
    for path,digest in manifest['inputs_sha256'].items():
        require(sha(ROOT/path)==digest,('build script changed since native build',path))
        report['inputs_sha256'][path]=digest
    for row in manifest['sources']:
        require(sha(ROOT/row['file'])==row['sha256'],('source changed since native build',row['file']))
        report['inputs_sha256'][row['file']]=row['sha256']
    for name in ('audit_native_patch_v23.py','native_patch_manifest_v23.json','verify_native.py','roster_v21.py'):
        report['inputs_sha256'][name]=sha(ROOT/name)
    report['status']='PASS'
    (ROOT/'audit_native_patch_v23.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('v23 native patch audit PASS:18 deltas,12 models,4 negative controls',flush=True)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        (ROOT/'audit_native_patch_v23.json').write_text(json.dumps({'status':'FAIL','error':f'{type(exc).__name__}: {exc}'},indent=2),encoding='utf-8')
        raise
