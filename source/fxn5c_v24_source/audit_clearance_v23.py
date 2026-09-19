"""Bounded v22/v23 corrected-running-gear to fixed-body angle comparison.

This excludes intentional same-bogie joints, wheels, and flexible connecting
rods. It tests actual triangle surfaces at 0/+/-5/+/-10 degrees. It is not
continuous motion, suspension-travel, route, physics or gameplay validation.
No source, native resource or existing report is modified.
"""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,math,sys
import bpy
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v22_source'
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen
from geometry_v20 import ProductionBuilder15
from running_gear_revision_v23 import recipe,apply as apply_gear


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bounds(points):return [(min(p[k] for p in points),max(p[k] for p in points)) for k in range(3)]


def intersects(a,b):return all(aa[0]<=bb[1]+1e-7 and bb[0]<=aa[1]+1e-7 for aa,bb in zip(a,b))


def fixed_body():
    records=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj.get('connection_role')=='longitudinal_rod':continue
        if obj.name.startswith(('bounds|','collision|')) or obj.hide_render:continue
        parent=obj;moving=False
        while parent:
            if parent.name in ('b1_grp','b2_grp'):moving=True;break
            parent=parent.parent
        if moving:continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        bb=bounds(points)
        # Revised moving parts occupy Z .403..1.192. Filter broadly enough to
        # include every possible fixed-body triangle at those heights.
        if bb[2][0]>1.35 or bb[2][1]<.35:continue
        obj.data.calc_loop_triangles()
        tris=[tuple(t.vertices) for t in obj.data.loop_triangles]
        records.append({'name':obj.name,'bounds':bb,'tree':BVHTree.FromPolygons(points,tris,all_triangles=True,epsilon=1e-7)})
    return records


def moving_geometry(index,current):
    if current:
        obj=bpy.data.objects[f'b{index}']
        roles=json.loads(obj['gear23_axle_roles'])
    else:
        batch=recipe(ProductionBuilder15(0,gen))
        obj=batch.finish('_clearance23_legacy_recipe',None)
        roles=batch.parts
    role_by_polygon={i:r['role'] for r in roles for i in range(r['polygon_start'],r['polygon_start']+r['polygon_count'])}
    obj.data.calc_loop_triangles()
    triangles=[t for t in obj.data.loop_triangles if t.polygon_index in role_by_polygon]
    points=[v.co.copy() for v in obj.data.vertices]
    tris=[tuple(t.vertices) for t in triangles]
    labels=[role_by_polygon[t.polygon_index] for t in triangles]
    if not current:bpy.data.objects.remove(obj,do_unlink=True)
    return points,tris,labels


def check(source,current,jinwen=False,candidate=False):
    bpy.ops.wm.open_mainfile(filepath=str(source))
    if candidate:
        apply_gear(ProductionBuilder15(0,gen),jinwen)
    fixed=fixed_body();rows=[]
    for index in (1,2):
        points,tris,roles=moving_geometry(index,current)
        used=sorted({i for t in tris for i in t})
        group=bpy.data.objects[f'b{index}_grp']
        for angle in (-10,-5,0,5,10):
            transform=group.matrix_world@Matrix.Rotation(math.radians(angle),4,'Z')
            moved=[transform@p for p in points];bb=bounds([moved[i] for i in used])
            tree=BVHTree.FromPolygons(moved,tris,all_triangles=True,epsilon=1e-7)
            tested=0;contacts=[]
            for body in fixed:
                if not intersects(bb,body['bounds']):continue
                tested+=1
                hits=tree.overlap(body['tree'])
                if hits:
                    counts=Counter(roles[i] for i,j in hits)
                    contacts.append({'body':body['name'],'triangle_pairs':len(hits),'roles':dict(counts)})
            rows.append({'bogie':index,'degrees':angle,'fixed_meshes_tested':tested,'contacts':contacts,
                         'moving_triangles':len(tris)})
    return {'source':str(source),'source_sha256':sha(source),'candidate_recipe_applied_without_save':candidate,
            'fixed_underframe_meshes':len(fixed),'poses':rows}


def main():
    styles=[]
    candidate='--candidate' in sys.argv
    for style in ('fxn5c','fxn5c_jinwen'):
        baseline=check(BASE/f'{style}_source.blend',False)
        current=check((BASE if candidate else ROOT)/f'{style}_source.blend',True,'jinwen' in style,candidate)
        new=[]
        for old,row in zip(baseline['poses'],current['poses']):
            known={(c['body'],r) for c in old['contacts'] for r in c['roles']}
            for contact in row['contacts']:
                for role,count in contact['roles'].items():
                    if (contact['body'],role) not in known:
                        new.append({'bogie':row['bogie'],'degrees':row['degrees'],'body':contact['body'],'role':role,'triangle_pairs':count})
        styles.append({'style':style,'baseline':baseline,'current':current,'new_contact_role_pairs':new})
        print('CLEARANCE23',style,'new',len(new),flush=True)
    report={'status':'PASS' if all(not s['new_contact_role_pairs'] for s in styles) else 'REVIEW_REQUIRED',
        'created_utc':datetime.now(timezone.utc).isoformat(),'styles':styles,
        'script_sha256':sha(__file__),'engine_playtest':False,
        'gear_recipe_sha256':sha(ROOT/'running_gear_revision_v23.py'),
        'inputs_sha256':{path.relative_to(ROOT).as_posix():sha(path) for path in
            (ROOT/'audit_clearance_v23.py',ROOT/'running_gear_revision_v23.py',
             ROOT/'fxn5c_source.blend',ROOT/'fxn5c_jinwen_source.blend')},
        'baseline_sha256':{'../fxn5c_v22_source/'+path.name:sha(path) for path in
            (BASE/'fxn5c_source.blend',BASE/'fxn5c_jinwen_source.blend')},
        'scope':'revised axlebox/carrier/coils/guides/dampers/pockets/inner bearings versus fixed body only',
        'exclusions':['same-bogie mounting overlaps','v21 equipment boxes unchanged this pass','v22 auxiliary case pose unchanged except tiny lid seating','dynamic connecting rods and +/-15 degree known stress boundary'],
        'limitations':'Discrete surface-intersection comparison, not continuous-volume clearance or suspension-travel certification.'}
    target=ROOT/('gear23_candidate_clearance.json' if candidate else 'clearance_audit_v23.json')
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('CLEARANCE23_STATUS',report['status'],flush=True)


if __name__=='__main__':main()
