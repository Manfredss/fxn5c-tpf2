"""Independent post-build source geometry and native bearing-axis audit.

Run with Blender after build_release_v23.py and verify_native_v23.py. This
script opens the two final saved sources; it never reapplies model revisions,
never saves a blend, and checks that injected faults leave scene geometry and
source bytes unchanged. Native circles are measured from actual exported mesh
vertices after loading the evaluated model hierarchy, not from recipe tags.

The source checks cover named corrected parts, not every hidden locomotive
component. LOD1 pre-integration probes are separated from current exported
native evidence. Nothing here is an in-game runtime certification.
"""
from array import array
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,sys
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'runtime'))
REPORT=ROOT/'audit_sources_v23.json'
INPUTS=(
    'running_gear_revision_v23.py','body_revision_v23.py','livery_revision_v23.py',
    'jwr_vector_v23.py','audit_running_gear_v23.py','audit_body_v23.py',
    'audit_livery_v23.py','audit_sources_v23.py',
    'fxn5c_source.blend','fxn5c_jinwen_source.blend',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,message):
    if not ok:raise AssertionError(message)


def counts():
    """Actual scene-object totals, not game-only triangle budget counts."""
    objects=list(bpy.context.scene.objects)
    meshes=[o for o in objects if o.type=='MESH']
    triangles=0
    for obj in meshes:
        obj.data.calc_loop_triangles();triangles+=len(obj.data.loop_triangles)
    return {'objects_by_type':dict(sorted(Counter(o.type for o in objects).items())),
            'mesh_objects':len(meshes),'unique_mesh_datablocks':len({o.data.as_pointer() for o in meshes}),
            'object_instanced_vertices':sum(len(o.data.vertices) for o in meshes),
            'object_instanced_polygons':sum(len(o.data.polygons) for o in meshes),
            'object_instanced_triangles':triangles,
            'scope':'All objects present in the saved scene, including source bounds/lights; not native vehicle triangle counts'}


def geometry_fingerprint():
    """Fault tests may modify memory briefly; prove positions/faces restore."""
    h=hashlib.sha256()
    for obj in sorted(bpy.context.scene.objects,key=lambda o:o.name):
        h.update(obj.name.encode('utf-8'));h.update(obj.type.encode('ascii'))
        h.update(array('f',(v for row in obj.matrix_world for v in row)).tobytes())
        if obj.type!='MESH':continue
        mesh=obj.data
        pos=array('f',[0.0])*(3*len(mesh.vertices));mesh.vertices.foreach_get('co',pos)
        loops=array('i',[0])*len(mesh.loops);mesh.loops.foreach_get('vertex_index',loops)
        sizes=array('i',[0])*len(mesh.polygons);mesh.polygons.foreach_get('loop_total',sizes)
        mats=array('i',[0])*len(mesh.polygons);mesh.polygons.foreach_get('material_index',mats)
        for values in (pos,loops,sizes,mats):h.update(values.tobytes())
        for mat in mesh.materials:h.update(mat.name.encode('utf-8'))
    return h.hexdigest()


def source_audits():
    import audit_running_gear_v23 as gear
    import audit_body_v23 as body
    import audit_livery_v23 as livery
    rows=[]
    for jinwen in (False,True):
        name='fxn5c_jinwen_source.blend' if jinwen else 'fxn5c_source.blend'
        path=ROOT/name
        bpy.ops.wm.open_mainfile(filepath=str(path))
        before=geometry_fingerprint()
        row={'file':name,'source_sha256':sha(path),'actual_scene_counts':counts()}
        print('SOURCE23 geometry',name,flush=True)
        row['running_gear']=gear.audit_scene(lod=0,strict_support=True)
        row['body_mounts_and_numbers']=body.audit_scene(jinwen,0)
        # number_checks is already called inside body.audit_scene; retain its
        # explicit returned measurements without calling it a second time.
        row['cab_number_checks']=row['body_mounts_and_numbers']['cab_numbers']
        if jinwen:row['jinwen_livery']=livery.audit_scene()
        print('SOURCE23 fault controls',name,flush=True)
        row['negative_controls']={'running_gear':gear.negative_controls(0),
                                  'body':body.negative_controls(jinwen)}
        if jinwen:row['negative_controls']['livery']=livery.fault_tests()
        require(len(row['negative_controls']['running_gear'])==3,'three gear controls required')
        require(len(row['negative_controls']['body'])==4,'four body controls required')
        if jinwen:require(len(row['negative_controls']['livery'])==4,'four livery controls required')
        require(before==geometry_fingerprint(),('Fault controls failed to restore scene geometry',name))
        require(row['source_sha256']==sha(path),('Saved source changed during read-only audit',name))
        row['fault_geometry_restored']=True;row['source_bytes_unchanged']=True
        row['status']='PASS';rows.append(row)
        print('SOURCE23 PASS',name,flush=True)
    return rows


def _walk(node):
    yield node
    for child in node.get('children',[]):yield from _walk(child)


def native_axis_audits(inputs):
    import render_native
    from audit_running_gear_v23 import audit_readback_axes
    for name in ('render_native.py','native_meshes.json','verify_native_v23.py'):
        inputs[name]=sha(ROOT/name)
    rows=[]
    for jinwen in (False,True):
        stem='fxn5c_jinwen' if jinwen else 'fxn5c'
        scene_name='native_scene_'+stem+'.json'
        inputs[scene_name]=sha(ROOT/scene_name)
        mdl='staging/codex_fxn5c_1/res/models/model/vehicle/train/'+stem+'.mdl'
        inputs[mdl]=sha(ROOT/mdl)
        scene=json.loads((ROOT/scene_name).read_text(encoding='utf-8'))
        for lod in (0,1):
            print('SOURCE23 native independent circle fit',stem,'LOD',lod,flush=True)
            # The reader enforces fresh descriptors relative to all meshes
            # and MDLs. No application of source revision functions occurs.
            render_native.load_native(jinwen,model_stem=stem,lod_index=lod)
            row=audit_readback_axes(lod)
            row['model']=stem;row['current_export']=True
            row['scope']='Two style representatives; actual exported circles and wheels at LOD0/LOD1, not in-game motion'
            referenced=[]
            for node in _walk(scene['lods'][lod]['node']):
                if node['name'] not in {'b1','b2','w1','w2','w3','w4','w5','w6'}:continue
                mesh='staging/codex_fxn5c_1/res/models/mesh/'+node['mesh']
                for filename in (mesh,mesh+'.blob'):
                    inputs[filename]=sha(ROOT/filename);referenced.append(filename)
            require(len(referenced)==16,('Native axle resource inventory',stem,lod))
            row['resource_files']=sorted(set(referenced));rows.append(row)
    return rows


def prior_lod1_probes():
    path=ROOT/'runtime/body23_joint_test.json'
    if not path.is_file():
        return {'available':False,'scope':'No historical probe report available; no LOD1 source claim'}
    report=json.loads(path.read_text(encoding='utf-8'))
    cases=[row for row in report.get('cases',[]) if row.get('lod')==1]
    return {'available':True,'file':path.relative_to(ROOT).as_posix(),'sha256':sha(path),
            'evidence_stage':'Historical pre-integration probe, NOT final-source or final-native certification',
            'cases':[{'lod':row['lod'],'jinwen':row['jinwen'],'recorded_status':row['status'],
                      'cab_number_measurements':row.get('cab_numbers',[]),
                      'selected_mounts_measured':len(row.get('selected_v22_mounts',[]))} for row in cases],
            'scope':'Prior joint body/livery LOD1 scene probes only; current native axes are tested separately above'}


def main():
    report={'status':'RUNNING','generated_utc':datetime.now(timezone.utc).isoformat(),
            'game_verified':False,'inputs_sha256':{},'sources':[],'native_axes':[],
            'scope':'Selected corrected source parts and current native axle/bearing axes; not every hidden part or engine behavior'}
    try:
        initial={name:sha(ROOT/name) for name in INPUTS}
        if '--native-only' in sys.argv:
            previous=json.loads(REPORT.read_text(encoding='utf-8'))
            require(previous['status']=='SOURCE_PASS_PENDING_NATIVE','Native-only needs a completed source-only pass')
            require(len(previous['sources'])==2,'Two cached source cases required')
            require(all(previous['inputs_sha256'].get(name)==value for name,value in initial.items()),
                    'Source-only evidence is stale; rerun source checks')
            report['sources']=previous['sources']
            report['source_audit_utc']=previous['generated_utc']
        report['inputs_sha256'].update(initial)
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        if '--native-only' not in sys.argv:report['sources']=source_audits()
        report['prior_lod1_probes']=prior_lod1_probes()
        require(initial=={name:sha(ROOT/name) for name in INPUTS},'Audit inputs changed while checking')
        report['negative_controls_passed']=sum(sum(len(v) for v in row['negative_controls'].values()) for row in report['sources'])
        require(report['negative_controls_passed']==18,'Expected 18 injected-fault controls')
        if '--source-only' in sys.argv:
            report['status']='SOURCE_PASS_PENDING_NATIVE'
            print('v23 source checks PASS; current native independent checks still pending',flush=True)
            return
        report['native_axes']=native_axis_audits(report['inputs_sha256'])
        report['native_bearing_rings_measured']=sum(len(row['rings']) for row in report['native_axes'])
        require(report['native_bearing_rings_measured']==80,'Expected 80 native bearing ring fits')
        report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL';report['error']=repr(exc)
        raise
    finally:
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('v23 final-source audit PASS: 2 saved scenes, 18 negative controls, 80 native bearing rings',flush=True)


if __name__=='__main__':main()
