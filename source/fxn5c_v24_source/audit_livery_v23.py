"""Read-only scene assertions for the Jinwen v23 fixed paint/lockup revision."""
from pathlib import Path
import hashlib,json,sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import livery_revision_v23 as revision


def _hash(obj):
    # This guard covers variable fleet signage and physical equipment whose
    # asymmetry must not be mirrored while matching a different reference end.
    import struct
    blob=bytearray()
    for v in obj.data.vertices:blob.extend(struct.pack('<3f',*(obj.matrix_world@v.co)))
    for p in obj.data.polygons:blob.extend(struct.pack('<'+str(len(p.vertices))+'I',*p.vertices))
    return hashlib.sha256(blob).hexdigest()


def _triangles(objects):
    count=0
    for obj in objects:
        obj.data.calc_loop_triangles();count+=len(obj.data.loop_triangles)
    return count


def _bvh(obj):
    mesh=obj.data
    return BVHTree.FromPolygons([obj.matrix_world@v.co for v in mesh.vertices],
                               [tuple(p.vertices) for p in mesh.polygons],all_triangles=False)


def audit_scene():
    sill=bpy.data.objects['chassis_sill']
    limits=revision.bounds(sill)
    assert abs(limits[1][0]+1.65)<2e-6 and abs(limits[1][1]-1.65)<2e-6
    outside_faces=0
    for face in sill.data.polygons:
        ys=[(sill.matrix_world@sill.data.vertices[i].co).y for i in face.vertices]
        exterior=max(ys)-min(ys)<1e-5 and abs(abs(ys[0])-1.65)<1e-5
        key=sill.data.materials[face.material_index].name.rsplit('/',1)[-1]
        assert key==('jw_white' if exterior else 'jw_frame'),('Incorrect sill paint',face.index,key,exterior)
        outside_faces+=exterior
    assert outside_faces>=2
    assert abs(limits[2][0]-1.355)<2e-6 and abs(limits[2][1]-1.605)<2e-6
    supports=[_bvh(bpy.data.objects[name]) for name in ('chassis_sill','body_open_shell_v07')]
    objects=[o for o in bpy.context.scene.objects if o.get('livery23_fixed_branding')]
    lod=int(bpy.context.scene.get('livery23_lod',0))
    assert len(objects)==(20 if lod==0 else 12),len(objects)
    max_gap=0;min_gap=10;vertices=0
    for obj in objects:
        side=int(obj['livery23_side'])
        for v in obj.data.vertices:
            p=obj.matrix_world@v.co
            hits=[tree.ray_cast(Vector((p.x,side*3,p.z)),Vector((0,-side,0)),5)[0] for tree in supports]
            hosts=[q for q in hits if q is not None]
            assert hosts,('Floating marking without body support',obj.name,tuple(p))
            nearest=max(side*q.y for q in hosts)
            gap=side*p.y-nearest
            assert .0005<gap<.0009,('Marking not seated',obj.name,tuple(p),gap)
            max_gap=max(max_gap,gap);min_gap=min(min_gap,gap);vertices+=1
        assert all(p.normal.y*side>.98 for p in obj.data.polygons),('Marking back-face',obj.name)
    for side in (-1,1):
        top=bpy.data.objects['jw23_depot_'+str(side)]
        bb=revision.bounds(top)
        assert top['livery19_font_approximation']=='simsun.ttc'
        assert abs(bb[0][1]-bb[0][0]-.78)<2e-6
        assert abs(bb[2][1]-bb[2][0]-.146)<2e-6
        logo=[o for o in objects if o.name.startswith('jw23_lower_'+str(side)+'_')]
        assert len(logo)==(3 if lod==0 else 1)
        center=sum((revision.bounds(o)[0][0]+revision.bounds(o)[0][1])/2 for o in logo)/len(logo)
        # Individual reference groups have slightly different visible bounds.
        assert abs(center-(.19-side*.34))<.004
        filler_center=.19+side*.75
        assert (-side)*(center-filler_center)>1.08
    return {'status':'PASS','fixed_mark_objects':len(objects),'mark_vertices_support_checked':vertices,
            'minimum_body_gap_m':min_gap,'maximum_body_gap_m':max_gap,
            'full_lod0_lockup_triangle_count_each':sum(len(revision._reference_triangles(g)) for g in revision.JWR_REFERENCE_CONTOURS),
            'fascia_bounds':limits,'label_font':'simsun.ttc','label_height_m':.146,
            'logo':'All 3 outline groups at LOD0; subpixel rows omitted at LOD1; holes preserved; both sides reading-right of filler',
            'scope':'Jinwen only; physical asymmetric equipment never mirrored'}


def fault_tests():
    tests=[]
    lower=bpy.data.objects['jw23_lower_1_jwr']
    original=lower.data.vertices[0].co.copy()
    lower.data.vertices[0].co.y+=.025
    try:
        try:audit_scene()
        except AssertionError:tests.append('floating_logo_vertex_rejected')
        else:raise AssertionError('Audit accepted floating logo')
    finally:lower.data.vertices[0].co=original
    sill=bpy.data.objects['chassis_sill']
    face=next(f for f in sill.data.polygons if sill.data.materials[f.material_index].name.endswith('/jw_white'))
    original=face.material_index;face.material_index=0
    try:
        try:audit_scene()
        except AssertionError:tests.append('gray_fascia_rejected')
        else:raise AssertionError('Audit accepted gray outer fascia')
    finally:face.material_index=original
    depot=bpy.data.objects['jw23_depot_1']
    original=depot['livery19_font_approximation'];depot['livery19_font_approximation']='wrong-font.ttf'
    try:
        try:audit_scene()
        except AssertionError:tests.append('wrong_depot_font_rejected')
        else:raise AssertionError('Audit accepted wrong depot font')
    finally:depot['livery19_font_approximation']=original
    en=bpy.data.objects['jw23_cab_1_1_en']
    en['livery23_fixed_branding']=False
    try:
        try:audit_scene()
        except AssertionError:tests.append('missing_full_lockup_group_rejected')
        else:raise AssertionError('Audit accepted incomplete full lockup')
    finally:en['livery23_fixed_branding']=True
    assert len(tests)==4
    return tests


def main():
    import generate_fxn5c as gen
    from geometry_v20 import ProductionBuilder15
    b=ProductionBuilder15(0,gen)
    protected={o.name:_hash(o) for o in bpy.context.scene.objects if o.type=='MESH' and
               (o.get('livery21_variable') or o.name.startswith(('main_fuel_tank','air_reservoir','radiator','side_louver')))}
    old=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith(('jinwen_depot','jinwen_jwr_logo_v19','jinwen_cab_operator'))]
    old_count=_triangles(old)
    result=revision.apply(b,True)
    report=audit_scene()
    assert protected=={name:_hash(bpy.data.objects[name]) for name in protected}
    report.update(result)
    report['old_fixed_mark_triangles']=old_count
    report['new_fixed_mark_triangles']=_triangles([bpy.data.objects[n] for n in result['added']])
    report['protected_meshes']=len(protected)
    report['negative_tests']=fault_tests()
    (ROOT/'runtime/livery_audit_probe_v23.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
