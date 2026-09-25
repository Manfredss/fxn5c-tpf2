"""Full saved-source scope, native/source correspondence and actual pose collisions."""
from pathlib import Path
from collections import defaultdict
import sys,json,math,hashlib
import bpy,numpy as np
from mathutils import Vector,Matrix
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'fxn5c_v36_source'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from audit_roof_v34 import points,tree,tree_pose
from animation_v26 import flatten_nodes
from verify_native import read_lua
from native_patch_v23 import sha,decode

def sig(o):
    m=o.data;co=np.empty(len(m.vertices)*3,dtype=np.float32);m.vertices.foreach_get('co',co)
    face=[(tuple(f.vertices),f.material_index,f.use_smooth) for f in m.polygons]
    uv=[]
    for layer in m.uv_layers:
        vals=np.empty(len(layer.data)*2,dtype=np.float32);layer.data.foreach_get('uv',vals);uv.append(vals.tobytes().hex())
    return hashlib.sha256(co.tobytes()+json.dumps((face,[x.name for x in m.materials],uv)).encode()).hexdigest()

def main():
    m=json.loads((ROOT/'manifest_v37.json').read_text());results=[]
    for src in m['sources']:
        path=ROOT/src['file'];lod=0 if path.name.endswith('_source.blend') else int(path.stem[-1]);style='fxn5c_jinwen' if 'jinwen' in path.name else 'fxn5c'
        oldpath=BASE/(style+'_source.blend') if lod==0 else BASE/'runtime'/f'final34_{style}_lod{lod}.blend'
        bpy.ops.wm.open_mainfile(filepath=str(oldpath),use_scripts=False,load_ui=False)
        old={}
        for o in bpy.context.scene.objects:
            if o.type!='MESH' or o.get('roof26_animation_kind')=='louver' or o.get('roof27_role')=='louver_hinge':continue
            old[o.name]=(sig(o),o.matrix_world.copy(),o.get('roof26_animation_kind'),list(o.get('roof26_pivot',(0,0,0))),o.get('roof26_direction',1))
        bpy.ops.wm.open_mainfile(filepath=str(path),use_scripts=False,load_ui=False)
        objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];kept=0;bigcount=0
        for name,(digest,tf,kind,pivot,side) in old.items():
            o=bpy.data.objects[name];assert sig(o)==digest,('unrelated source mesh/UV/material edit',name)
            expected=Matrix.Translation(Vector(pivot))@Matrix.Rotation(math.radians(side*55),4,'X')@Matrix.Translation(-Vector(pivot))@tf if kind=='side_louver' else tf
            assert max(abs(a-b) for ar,br in zip(expected,o.matrix_world) for a,b in zip(ar,br))<2e-6,(name,kind)
            kept+=1;bigcount+=kind=='side_louver'
        assert bigcount==(312 if lod==0 else 168 if lod==1 else 0)
        model=read_lua(ROOT/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
        nodes={n['name']:n for n in flatten_nodes(model['lods'][lod]['node'])}
        parts=[p for p in m['animated'] if p['style']==style and p['lod']==lod]
        grouped=defaultdict(list)
        for o in objs:
            if o.get('roof26_animation_kind'):grouped[o['roof26_animation_group']].append(o)
        max_error=0
        for p in parts:
            key=p['name'][len('fxn5c_v26_'):-len(f'_lod{lod}')];ps=[q for o in grouped[key] for q in points(o)]
            kd=KDTree(len(ps))
            for i,q in enumerate(ps):kd.insert(q,i)
            kd.balance();_,arr,_,_=decode(ROOT/p['target'],p['materials'])
            tf=Matrix([[nodes[p['name']]['transf'][c*4+r] for c in range(4)] for r in range(4)])
            err=max(kd.find(tf@Vector(q))[2] for q in arr['position']);assert err<3e-5,(p['name'],err);max_error=max(max_error,err)
        if lod==2:
            results.append(dict(style=style,lod=lod,unchanged_meshes=kept,source_sha256=sha(path)));continue
        leaves=[o for o in objs if o.get('roof26_animation_kind')=='louver'];assert len(leaves)==(36 if lod==0 else 16)
        assert len([o for o in objs if o.get('roof27_role')=='louver_hinge'])==len(leaves)*2
        groups=defaultdict(list);curves={};errors=[];checks=0;neighbor_checks=0
        for o in leaves:
            t=Vector(o['roof27_mount_tangent']);p=Vector(o['roof26_pivot']);q=points(o)
            height=max((v-p).dot(t) for v in q)-min((v-p).dot(t) for v in q)
            assert abs(height-(.340/(9 if lod==0 else 4)-.005))<2e-6
            name='fxn5c_v26_'+o['roof26_animation_group']+f'_lod{lod}';n=nodes[name]
            ani=read_lua(ROOT/'staging/codex_fxn5c_1/res/models/animation'/n['animations']['forever']['params']['id'])
            curves[o.name]=[Matrix([[v[c*4+r] for c in range(3)] for r in range(3)]).to_quaternion() for v in ani['transfs']]
            groups[(round(p.x,2),1 if p.y>0 else -1)].append(o)
        for (x,side),group in groups.items():
            group.sort(key=lambda o:o['roof26_pivot'][2])
            fixed=[o for o in objs if not o.get('roof26_animation_kind') and o.get('roof27_role')!='louver_hinge' and not o.name.startswith('bounds|')]
            ft,names=tree(fixed,lambda vs:any(abs(p.x-x)<.65 and 3.90<p.z<4.40 and p.y*side>1.15 for p in vs))
            for tm in range(0,800,5):
                idx=tm//25;alpha=(tm%25)/25;posed=[]
                for o in group:
                    qs=curves[o.name];rot=qs[idx].slerp(qs[idx+1],alpha).to_matrix();lt=tree_pose(o,Vector(o['roof26_pivot']),rot);posed.append(lt)
                    hits=lt.overlap(ft);checks+=1
                    if hits:errors.append(dict(time=tm,name=o.name,fixed=sorted(set(names[j] for _,j in hits))))
                for a,b in zip(posed,posed[1:]):
                    neighbor_checks+=1
                    if a.overlap(b):errors.append(dict(time=tm,bank=(x,side),neighbor=True))
        # Big blades are already saved in their permanent open pose. Hinge
        # interfaces are deliberate contact; frames, jambs and other blades aren't.
        big=[o for o in objs if o.get('roof26_animation_kind')=='side_louver'];banks=defaultdict(list);bigchecks=0
        for o in big:banks[(o['window34_side'],round(o['window34_column'],4))].append(o)
        for (side,x),group in banks.items():
            fixed=[o for o in objs if not o.get('roof26_animation_kind') and o.get('window34_role')!='radiator_hinge' and not o.name.startswith('bounds|')]
            ft,names=tree(fixed,lambda vs:any(abs(p.x-x)<.34 and p.y*side>1.50 and 1.95<p.z<3.92 for p in vs))
            group.sort(key=lambda o:o['roof26_pivot'][2]);trees=[]
            for o in group:
                lt,_=tree([o]);trees.append(lt);hits=lt.overlap(ft);bigchecks+=1
                if hits:errors.append(dict(large=o.name,fixed=sorted(set(names[j] for _,j in hits))))
            for a,b in zip(trees,trees[1:]):assert not a.overlap(b)
            for z in (2.2,2.6,3.2,3.7):assert ft.ray_cast(Vector((x,side*1.75,z)),Vector((0,-side,0)),.3)[0] is not None
        results.append(dict(style=style,lod=lod,unchanged_meshes=kept,roof_blades=len(leaves),fixed_big_blades=bigcount,
            native_source_max_error_m=max_error,small_body_frame_samples=checks,small_neighbor_samples=neighbor_checks,
            large_static_checks=bigchecks,errors=errors,source_sha256=sha(path)))
        (ROOT/'geometry_validation_v37.json').write_text(json.dumps(dict(status='RUNNING',rows=results),indent=2))
        assert not errors,errors[:8]
        print('GEOMETRY37_PASS',style,lod,checks,neighbor_checks,bigchecks,flush=True)
    (ROOT/'geometry_validation_v37.json').write_text(json.dumps(dict(status='PASS',rows=results,
        hinge_design_contact_excluded=True,engine_tested=False),indent=2))
if __name__=='__main__':main()
