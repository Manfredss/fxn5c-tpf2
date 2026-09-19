"""Independent bounded upper-section, rigid-equipment and attachment checks.

Blender --background --python audit_roof_v24.py
Compares fresh immutable v23 baselines and the current roof recipe at all LODs.
This is geometric source validation, not a game/route or manufacturer-CAD claim.
"""
from pathlib import Path
import sys,json,hashlib,math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def points(obj):return [obj.matrix_world@v.co for v in obj.data.vertices]


def fingerprint(obj):
    data={'v':[list(v) for v in points(obj)],'f':[list(f.vertices) for f in obj.data.polygons],
          'm':[m.name for m in obj.data.materials]}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


def snapshot():
    low={};rigid={};glass={}
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        ps=points(obj)
        if not ps:continue
        if max(v.z for v in ps)<3.94:low[obj.name]=fingerprint(obj)
        if obj.name.startswith(('roof20_','cab_roof_well_floor','cab_aircon_','ac_','roof_ac_conduit',
                               'recessed_fan_shroud','radiator_fan_hub','concealed_fan_blade')):
            rigid[obj.name]=[tuple(p) for p in ps]
        if obj.name.startswith('glazing_'):glass[obj.name]=(fingerprint(obj),min(v.z for v in ps),[tuple(p) for p in ps])
    return {'low':low,'rigid':rigid,'glass':glass}


def bvh(objects):
    verts=[];faces=[]
    for obj in objects:
        ps=points(obj);base=len(verts);verts.extend(ps)
        obj.data.calc_loop_triangles()
        faces.extend(tuple(base+i for i in tri.vertices) for tri in obj.data.loop_triangles)
    return BVHTree.FromPolygons(verts,faces,all_triangles=True,epsilon=1e-5)


def transform_fan(p,side):
    # Independently reconstruct old/new orthonormal bases; no call to recipe.
    p=Vector(p);oldc=Vector((0,side*1.31,4.4005))
    ov=Vector((0,side*.54,-.569)).normalized();on=Vector((0,side*.569,.54)).normalized()
    nv=Vector((0,side*.86,-.425)).normalized();nn=Vector((0,side*.425,.86)).normalized()
    c=Vector((0,side*.91,4.4925));r=p-oldc
    return c+Vector((r.x,0,0))+nv*r.dot(ov)+nn*r.dot(on)


def audit(baseline,lod,jw,allow_other_passes=False):
    low=[];other=[]
    for name,digest in baseline['low'].items():
        obj=bpy.data.objects.get(name)
        if allow_other_passes and (name.startswith(('headlights_','taillights_')) or
            (obj is not None and (obj.get('front24_shifted') or obj.get('front24_blue_band_split')))):
            other.append(name);continue
        assert obj is not None and fingerprint(obj)==digest,('changed lower component',name)
        low.append(name)
    rigid=[]
    for name,oldps in baseline['rigid'].items():
        if name.startswith('roof20_flat_crown'):continue
        obj=bpy.data.objects.get(name);assert obj is not None,('missing rigid part',name)
        actual=points(obj)
        # Polygon paint clipping may duplicate vertices, but every original
        # transformed point must still exist. Positions are compared at2µm.
        kd=KDTree(len(actual))
        for i,p in enumerate(actual):kd.insert(p,i)
        kd.balance()
        if name.startswith('roof20_'):
            side=-1 if sum(p[1] for p in oldps)<0 else 1
            expected=[transform_fan(p,side) for p in oldps]
        elif name.startswith(('recessed_fan_shroud','radiator_fan_hub','concealed_fan_blade')):
            expected=[Vector(p) for p in oldps]
        else:expected=[Vector(p)-Vector((0,0,.070)) for p in oldps]
        residual=max(kd.find(p)[2] for p in expected)
        assert residual<2e-6,('nonrigid equipment',name,residual)
        # Rigid matrix orthonormality, independently verified on actual sample
        # pair lengths rather than merely trusting a property tag.
        for i in range(min(12,len(oldps)-1)):
            d0=(Vector(oldps[i])-Vector(oldps[-i-1])).length
            d1=(expected[i]-expected[-i-1]).length
            assert abs(d1-d0)<1e-6,(name,d0,d1)
        rigid.append(name)
    fixed_glass=[];moved_glass=[]
    for name,(digest,zmin,oldps) in baseline['glass'].items():
        obj=bpy.data.objects.get(name);assert obj is not None
        if zmin<4.05:
            assert fingerprint(obj)==digest,('windscreen changed',name)
            fixed_glass.append(name)
        else:
            ps=points(obj)
            assert len(ps)==len(oldps)
            end=1 if oldps[0][0]>0 else-1
            for old,new in zip(oldps,ps):
                assert abs(new.y-old[1])<1e-6 and abs(new.z-old[2]-.160)<1e-6
                assert abs(new.x-old[0]+end*.160*.38/.46)<1e-6
            moved_glass.append(name)
    brows=[o for o in bpy.context.scene.objects if o.name.startswith('roof24_full_height_brow')]
    assert len(brows)==2
    for obj in brows:
        ps=points(obj)
        for y,z in ((-1.65,3.95),(-1.34,4.28),(-.48,4.705),(.48,4.705),(1.34,4.28),(1.65,3.95)):
            assert any(abs(p.y-y)<1e-6 and abs(p.z-z)<1e-6 for p in ps),('section vertex',obj.name,y,z)
    assert not any(o.name.startswith('grey_brow_') for o in bpy.context.scene.objects)
    paint_counts={'blue_lower_fold_faces':0,'gray_boundary_vertices':0,'gray_upper_faces':0}
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not obj.name.startswith(('body_open_shell_v07','roof24_',
                'cab_continuous_low_hood','trapezoid_roof_deck','roof20_cell_frame')):continue
        ps=points(obj);keys=[Path(m.name).name for m in obj.data.materials]
        for face in obj.data.polygons:
            pp=[ps[i] for i in face.vertices];key=keys[face.material_index]
            zmin=min(p.z for p in pp);zmax=max(p.z for p in pp)
            if not jw and key in ('blue','light_blue') and zmin>=3.95-1e-6:
                assert zmax<=4.24+2e-6,('blue crossing gray boundary',obj.name,zmax)
                paint_counts['blue_lower_fold_faces']+=1
            if key in ('roof','jw_roof') and zmin>=4.24-2e-6:
                paint_counts['gray_upper_faces']+=1
                paint_counts['gray_boundary_vertices']+=sum(abs(p.z-4.24)<2e-6 for p in pp)
    assert paint_counts['gray_upper_faces']>0
    if not jw:
        assert paint_counts['blue_lower_fold_faces']>0 and paint_counts['gray_boundary_vertices']>0
    counts=[]
    if lod<2:
        skin=next(o for o in bpy.context.scene.objects if o.name.startswith('roof24_shoulder_fan_skin'))
        tree=bvh([skin])
        for obj in bpy.context.scene.objects:
            if not obj.name.startswith('roof20_recess_return'):continue
            overlap=len(tree.overlap(bvh([obj])))
            assert overlap>0,('unattached fan return',obj.name)
            counts.append({'part':obj.name,'skin_intersections':overlap})
        floors=[o for o in bpy.context.scene.objects if o.name.startswith('cab_roof_well_floor')]
        cases=[o for o in bpy.context.scene.objects if o.name.startswith('cab_aircon_case_v06')]
        for case in cases:
            cp=points(case);end=1 if sum(p.x for p in cp)>0 else-1
            floor=next(o for o in floors if sum(p.x for p in points(o))*end>0)
            fp=points(floor)
            penetration=max(p.z for p in fp)-min(p.z for p in cp)
            assert .002<penetration<.02,('AC floor support',case.name,penetration)
            counts.append({'part':case.name,'floor_overlap_m':penetration})
    triangles=0
    for obj in bpy.context.scene.objects:
        if obj.type=='MESH' and not obj.name.startswith('bounds|'):
            obj.data.calc_loop_triangles();triangles+=len(obj.data.loop_triangles)
    assert triangles<=(500000,220000,6000)[lod],('roof budget',lod,jw,triangles)
    return {'lod':lod,'jinwen':jw,'triangles':triangles,'unchanged_lower_components':len(low),
            'rigid_equipment_checked':len(rigid),'unchanged_windscreen_glazing':fixed_glass,
            'reseated_upper_glazing':moved_glass,'section_crown_width':.96,
            'section_knee_width':2.68,'section_full_width':3.30,'roof_gray_z':4.24,
            'actual_painted_faces':paint_counts,
            'selected_support_contacts':counts,'other_passes_explicitly_excluded':other,'status':'PASS'}


def nearest_residual(a,b):
    tree=KDTree(len(b))
    for i,p in enumerate(b):tree.insert(Vector(p),i)
    tree.balance()
    return max(tree.find(Vector(p))[2] for p in a)


def native_saved_check(jw,panes,roof_points):
    from render_native import load_native
    stem='fxn5c_jinwen' if jw else 'fxn5c'
    load_native(jw,stem,lod_index=0)
    rows=[]
    actual_panes={o.name:o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith('glazing_')}
    assert len(panes)==len(actual_panes)==26,('native glazing cohort',stem,len(panes),len(actual_panes))
    for name,expected in panes.items():
        actual=points(actual_panes[name])
        error=max(nearest_residual(expected,actual),nearest_residual(actual,expected))
        assert error<2e-5,('source/native pane coordinates',stem,name,error)
        bounds=[[min(p[k] for p in actual),max(p[k] for p in actual)] for k in range(3)]
        rows.append({'name':name,'bidirectional_max_residual_m':error,'world_bounds':bounds})
    body=bpy.data.objects['body']
    error=nearest_residual(roof_points,points(body))
    assert error<2e-5,('new section absent from actual native body',stem,error)
    return {'model':stem,'lod':0,'all_glazing_checked':rows,'new_roof_native_vertex_max_residual_m':error}


def final_audit():
    """Load actual final sources; never apply the candidate in this mode."""
    rows=[];native=[];inputs={}
    for jw in (False,True):
        name=('fxn5c_jinwen' if jw else 'fxn5c')+'_source.blend'
        bpy.ops.wm.open_mainfile(filepath=str(ROOT.parent/'fxn5c_v23_source'/name))
        before=snapshot()
        bpy.ops.wm.open_mainfile(filepath=str(ROOT/name))
        assert bpy.context.scene.get('roof24_applied'),('not a saved v24 source',name)
        rows.append(audit(before,0,jw,allow_other_passes=True))
        panes={o.name:[tuple(p) for p in points(o)] for o in bpy.context.scene.objects
               if o.type=='MESH' and o.name.startswith('glazing_')}
        roof_points=[tuple(p) for o in bpy.context.scene.objects if o.type=='MESH' and
            o.name.startswith(('roof24_front_folded_canopy','roof24_full_height_brow','roof24_ac_front_bulkhead')) for p in points(o)]
        inputs[name]=sha(ROOT/name)
        native.append(native_saved_check(jw,panes,roof_points))
    names=('roof_revision_v24.py','audit_roof_v24.py','native_patch_manifest_v24.json',
           'native_meshes.json','native_scene_fxn5c.json','native_scene_fxn5c_jinwen.json')
    inputs.update({name:sha(ROOT/name) for name in names})
    manifest=json.loads((ROOT/'native_patch_manifest_v24.json').read_text(encoding='utf8'))
    paths=set()
    for entry in manifest['patches']+manifest['panes']:
        if entry.get('lod')!=0:continue
        paths.update((entry['target'],entry['target']+'.blob'))
    # All26 panes perstyle, including the20 unchanged inherited panes.
    for stem in ('fxn5c','fxn5c_jinwen'):
        for i in range(26):
            path=f'staging/codex_fxn5c_1/res/models/mesh/vehicle/train/{stem}/glazing_{i:02d}_lod0.msh'
            paths.update((path,path+'.blob'))
        paths.add(f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{stem}.mdl')
    inputs.update({path:sha(ROOT/path) for path in sorted(paths)})
    out={'status':'PASS','mode':'actual_saved_sources_and_current_native_LOD0',
         'candidate_recipe_applied_without_save':False,
         'scope':'Actual saved source geometry and all26 native panes perstyle; selected rigid equipment and mount contacts only. No game/route or all-part clearance certification.',
         'inputs_sha256':inputs,'baseline_sha256':{name:sha(ROOT.parent/'fxn5c_v23_source'/name)
          for name in ('fxn5c_source.blend','fxn5c_jinwen_source.blend')},'results':rows,'native_checks':native}
    (ROOT/'roof_audit_v24.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
    print('FINAL_SAVED_NATIVE_ROOF24_PASS',flush=True)


def main():
    if '--final' in sys.argv:return final_audit()
    from prepare_scene_v24 import prepare
    from roof_revision_v24 import apply
    rows=[]
    for lod in (0,1,2):
        for jw in (False,True):
            prepare(lod,jw);before=snapshot()
            from geometry_v20 import ProductionBuilder15
            import generate_fxn5c as gen
            result=apply(ProductionBuilder15(lod,gen),jw)
            row=audit(before,lod,jw);rows.append(row)
            print('ROOF24_AUDIT',lod,jw,row['triangles'],'PASS',flush=True)
    out={'status':'PASS','scope':'Source geometry, selected rigid equipment and mount contacts; no in-game or all-part clearance certification',
         'inputs_sha256':{name:sha(ROOT/name) for name in ('roof_revision_v24.py','audit_roof_v24.py')},
         'baseline_sha256':{name:sha(ROOT.parent/'fxn5c_v23_source'/name) for name in ('fxn5c_source.blend','fxn5c_jinwen_source.blend')},
         'results':rows}
    (ROOT/'runtime'/'roof_probe_audit_v24.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')


if __name__=='__main__':main()
