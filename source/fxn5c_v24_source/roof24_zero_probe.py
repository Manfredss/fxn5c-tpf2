from pathlib import Path
from collections import Counter
import sys,json,hashlib,shutil
import bpy,numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from prepare_scene_v24 import prepare
from roof_revision_v24 import apply
from build_release_v24 import body_items
import export_tpf2 as export

def zeros():
    rows=[]
    for obj,_ in body_items():
        obj.data.calc_loop_triangles()
        for tri in obj.data.loop_triangles:
            p=np.asarray([tuple(obj.matrix_world@obj.data.vertices[i].co) for i in tri.vertices],dtype=np.float32).astype(np.float64)
            if np.any(np.cross(p[1]-p[0],p[2]-p[0])):continue
            rows.append({'object':obj.name,'face':tri.polygon_index,'positions':p.tolist(),
                'material':obj.data.materials[tri.material_index].name,'operation':obj.get('roof24_operation','')})
    return rows

def main():
    if '--six' in sys.argv:return six()
    from front_revision_v24 import apply_common
    before=[];after=[];front=[]
    b=prepare(0,False);before=zeros();apply(b,False);after=zeros();apply_common(b,False);front=zeros()
    for label,rows in [('before',before),('roof',after),('front',front)]:
        print(label,len(rows),dict(Counter(r['object'] for r in rows)),flush=True)
    (ROOT/'runtime/roof24_zero_diagnostic.json').write_text(json.dumps({'before':before,'roof':after,'front':front},indent=2),encoding='utf8')

def six():
    from front_revision_v24 import apply_common
    from audit_native_patch_v23 import decode,choose_delta_rows
    from audit_native_patch_v23 import assert_patch
    from native_patch_v23 import patch
    manifest=json.loads((ROOT/'native_patch_manifest_v24.json').read_text(encoding='utf8'))
    result=[]
    def strict_rows(data):
        good=Counter();dead=0
        for key,slot,ids in data['rows']:
            pp=data['attrs']['position'][list(ids)]
            p=pp.astype(np.float64)
            if not np.cross(p[1]-p[0],p[2]-p[0]).any():dead+=1;continue
            bits=pp.astype('<f4').tobytes()
            good[(key[0],min(bits,bits[12:]+bits[:12],bits[24:]+bits[:24]))]+=1
        return good,dead
    for row in manifest['patches']:
        lod=row['lod'];jw=row['jinwen'];style=row['style']
        name=f'after_lod{lod}'
        path=ROOT/'runtime/roof24_zero_proof'/style/(name+'.msh')
        path.parent.mkdir(parents=True,exist_ok=True)
        for suffix in ('','.blob'):shutil.copy2(str(ROOT/row['after']['file'])+suffix,str(path)+suffix)
        from roof_revision_v24 import sanitize_after_export
        report=sanitize_after_export(path)
        materials=row['after']['materials']
        after=decode(path,materials)
        prior=decode(ROOT/row['before']['file'],row['before']['materials'])
        oldafter=decode(ROOT/row['after']['file'],row['after']['materials'])
        oldnative=decode((ROOT/row['baseline']).resolve(),row['baseline_materials'])
        removed_keys=Counter(k for k,_,_ in prior['rows'])-Counter(k for k,_,_ in after['rows'])
        absent=removed_keys-Counter(k for k,_,_ in oldnative['rows'])
        assert not absent,('sanitizer requested removal absent from baseline native',style,lod,sum(absent.values()))
        good0,zero0=strict_rows(oldafter);good1,zero1=strict_rows(after)
        missing=good0-good1;extra=good1-good0
        assert not missing and not extra,('valid position/material triangles altered by export sanitizer',style,lod)
        for attr in oldafter['rawattrs']:
            assert after['rawattrs'][attr]==oldafter['rawattrs'][attr],('source export attribute bytes changed',style,lod,attr)
        if missing or extra:
            changed={'missing':[(k[0],np.frombuffer(k[1],dtype='<f4').reshape(3,3).tolist(),v) for k,v in missing.items()],
                     'extra':[(k[0],np.frombuffer(k[1],dtype='<f4').reshape(3,3).tolist(),v) for k,v in extra.items()]}
            (ROOT/'runtime'/f'roof24_zero_difference_{style}_lod{lod}.json').write_text(json.dumps(changed,indent=2),encoding='utf8')
            print('POSITIVE_RETESS',style,lod,sum(missing.values()),sum(extra.values()),flush=True)
        # Blender may select a different diagonal for the same near-collinear
        # compacted hood ngon. Compare actual oriented surfaces independently.
        surface={}
        if missing or extra:
            aa=[np.frombuffer(k[1],dtype='<f4').astype(float).reshape(3,3) for k,count in missing.items() for _ in range(count)]
            bb=[np.frombuffer(k[1],dtype='<f4').astype(float).reshape(3,3) for k,count in extra.items() for _ in range(count)]
            def metrics(tris):
                cross=np.cross(np.array(tris)[:,1]-np.array(tris)[:,0],np.array(tris)[:,2]-np.array(tris)[:,0])
                return np.linalg.norm(cross,axis=1).sum()/2,cross.sum(axis=0)/2
            area0,orient0=metrics(aa);area1,orient1=metrics(bb)
            def distance(tris,target):
                tree=BVHTree.FromPolygons([Vector(p) for t in target for p in t],[(i*3,i*3+1,i*3+2) for i in range(len(target))],all_triangles=True)
                samples=[p for t in tris for p in list(t)+[t.mean(axis=0),(t[0]+t[1])/2,(t[1]+t[2])/2,(t[2]+t[0])/2]]
                return max(tree.find_nearest(Vector(p))[3] for p in samples)
            residual=max(distance(aa,bb),distance(bb,aa))
            assert residual<2e-5,('retessellation surface moved',style,lod,residual)
            assert abs(area0-area1)<1e-6 and np.linalg.norm(orient0-orient1)<1e-6,('retessellation area/winding changed',style,lod,area0,area1,orient0,orient1)
            surface={'sampled_surface_max_error_m':residual,'area_before_m2':area0,'area_after_m2':area1,
                     'signed_area_vector_error_m2':float(np.linalg.norm(orient0-orient1))}
        added=Counter(k for k,_,_ in after['rows'])-Counter(k for k,_,_ in prior['rows'])
        additions=choose_delta_rows(after['rows'],added,True)
        dead=0
        for _,_,ids in additions:
            p=after['attrs']['position'][list(ids)].astype(np.float64)
            dead+=int(not np.cross(p[1]-p[0],p[2]-p[0]).any())
        assert dead==0,('new strictly zero-area candidate additions',style,lod,dead)
        target=path.with_name(f'patched_lod{lod}.msh')
        patched=patch((ROOT/row['baseline']).resolve(),ROOT/row['before']['file'],path,target,
            row['baseline_materials'],row['before']['materials'],materials)
        current=decode(target,patched['materials'])
        native_proof=assert_patch(oldnative,prior,after,current,style+str(lod))
        item={'style':style,'lod':lod,'before_zero_count':zero0,'after_zero_count':zero1,
            'positive_triangle_exact_float32_multiset_unchanged':not(missing or extra),'positive_triangles':sum(good1.values()),
            'coplanar_retessellation_surface_proof':surface,
            'added_triangles':len(additions),'added_zero_area':dead,'export_sanitization':report,
            'full_native_patch_and_independent_audit':native_proof}
        result.append(item);print('ZERO24_PASS',style,lod,'removed',zero0-zero1,'positive',sum(good1.values()),flush=True)
    (ROOT/'runtime/roof24_zero_audit.json').write_text(json.dumps({'status':'PASS','results':result,
        'module_sha256':hashlib.sha256((ROOT/'roof_revision_v24.py').read_bytes()).hexdigest()},indent=2),encoding='utf8')

if __name__=='__main__':main()
