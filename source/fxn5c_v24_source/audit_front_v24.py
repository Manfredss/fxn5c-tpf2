"""Independent current nose geometry/paint tests, not an in-game playtest."""
from pathlib import Path
import json,hashlib,struct,sys
from collections import Counter
from functools import lru_cache
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def expected_glyph_z(text,chinese,lod):
    from front_finish_v11 import _glyph_geometry,_number_placement,NUMBER_FONT_SIZE,FUXING_FONT_SIZE,FUXING_BASE_Z
    size=FUXING_FONT_SIZE if chinese else NUMBER_FONT_SIZE
    raw,_=_glyph_geometry(text,size,chinese,16 if lod==0 else 8)
    base,scale=(FUXING_BASE_Z,1.) if chinese else _number_placement()[:2]
    return base+min(p[1] for p in raw)*scale+.10,base+max(p[1] for p in raw)*scale+.10


def require(condition,message):
    if not condition:raise AssertionError(message)


def world_points(obj):return [obj.matrix_world@v.co for v in obj.data.vertices]


def bounds(objects):
    ps=[p for obj in objects for p in world_points(obj)]
    return [[min(p[i] for p in ps),max(p[i] for p in ps)] for i in range(3)]


def _body_tree():
    obj=bpy.data.objects['body_open_shell_v07']
    return obj,BVHTree.FromPolygons(world_points(obj),[tuple(p.vertices) for p in obj.data.polygons])


def paint_at(obj,tree,end,y,z):
    hit,normal,index,distance=tree.ray_cast(Vector((end*12,y,z)),Vector((-end,0,0)),2)
    require(hit is not None,('Missing actual nose skin',end,y,z))
    return obj.data.materials[obj.data.polygons[index].material_index].name.rsplit('/',1)[-1]


def audit_scene(jinwen=False,lod=0):
    if lod>=2:
        return {'status':'PASS','lod':lod,'scope':'Fine nose markings/bands omitted at distant LOD2; no close-detail claim'}
    host,tree=_body_tree();rows=[]
    for end in (-1,1):
        emblems=[o for o in bpy.context.scene.objects if o.get('emblem_end')==end]
        glyphs=[o for o in bpy.context.scene.objects if o.name.startswith('nose_fuxing_v11_') and o.get('front11_end')==end]
        nums=[o for o in bpy.context.scene.objects if o.get('livery21_role')=='nose_number' and o.get('livery21_end')==end]
        require(len(emblems)==2 and len(glyphs)==2 and len(nums)==1,('nose inventory',end,len(emblems),len(glyphs),len(nums)))
        eb=bounds(emblems);nb=bounds(nums)
        require(abs(eb[2][0]-2.0208)<3e-6 and abs(eb[2][1]-2.4992)<3e-6,('emblem not raised 100mm',end,eb))
        require(abs(eb[1][1]-eb[1][0]-.416)<3e-6,('emblem size changed',end))
        number_z=expected_glyph_z(nums[0]['livery21_text'],False,lod)
        require(max(abs(a-b) for a,b in zip(nb[2],number_z))<3e-6,('nose number height',end,nb,number_z))
        for obj in glyphs:
            reference=expected_glyph_z(obj['front11_text'],True,lod)
            actual=bounds([obj])[2]
            require(max(abs(a-b) for a,b in zip(reference,actual))<8e-6,('front character height',obj.name,actual))
        max_contact_error=0
        for obj in emblems+glyphs+nums:
            expected=.0015 if obj in emblems else .0016
            for p in world_points(obj):
                hit,normal,index,distance=tree.ray_cast(Vector((end*12,p.y,p.z)),Vector((-end,0,0)),2)
                require(hit is not None,('Unsupported marking',obj.name,tuple(p)))
                gap=end*(p.x-hit.x)
                require(abs(gap-expected)<2e-6,('Front relief changed/floating',obj.name,gap,expected))
                max_contact_error=max(max_contact_error,abs(gap-expected))
            require(all((obj.matrix_world.to_3x3()@f.normal).x*end>.999 for f in obj.data.polygons),
                    ('Backward front face',obj.name))
        rows.append({'end':end,'emblem_bounds':eb,'number_bounds':nb,
                     'emblem_number_vertical_gap_m':eb[2][0]-nb[2][1],
                     'max_relief_error_m':max_contact_error,'number':nums[0]['livery21_text']})
    paint=[]
    if jinwen:
        for end in (-1,1):
            for y in (-1.44,-1.2,-.75,-.56,-.54,-.2,0,.2,.54,.56,.75,1.2,1.44):
                for z in (1.869,1.895,1.921):
                    expected='jw_white' if abs(y)<.55 else 'jw_blue'
                    actual=paint_at(host,tree,end,y,z)
                    require(actual==expected,('Blue band gap / outboard segment',end,y,z,actual,expected))
                    paint.append({'end':end,'y':y,'z':z,'material':actual})
                for z in (1.777,1.801,1.824):
                    actual=paint_at(host,tree,end,y,z)
                    require(actual=='jw_red',('Red band not continuous',end,y,z,actual))
                    paint.append({'end':end,'y':y,'z':z,'material':actual})
    return {'status':'PASS','lod':lod,'jinwen':jinwen,'front_ends':rows,'paint_samples':paint,
            'scope':'Actual nose marking geometry, body support rays and paint-material boundaries on both ends'}


def negative_controls(jinwen=False,lod=0):
    trials=[]
    def moved(name,obj,axis,amount):
        old=[v.co.copy() for v in obj.data.vertices]
        try:
            for v in obj.data.vertices:v.co[axis]+=amount
            obj.data.update()
            try:audit_scene(jinwen,lod)
            except AssertionError:trials.append(name)
            else:raise AssertionError('Front audit accepted fault: '+name)
        finally:
            for v,p in zip(obj.data.vertices,old):v.co=p
            obj.data.update()
    emblem=next(o for o in bpy.context.scene.objects if o.get('emblem_end')==1)
    number=next(o for o in bpy.context.scene.objects if o.get('livery21_role')=='nose_number')
    moved('emblem_wrong_height',emblem,2,-.02)
    moved('number_floating_off_skin',number,0,.025)
    if jinwen:
        host,tree=_body_tree()
        hit,normal,index,distance=tree.ray_cast(Vector((12,0,1.895)),Vector((-1,0,0)),2)
        face=host.data.polygons[index];old=face.material_index
        blue=next(i for i,m in enumerate(host.data.materials) if m.name.endswith('/jw_blue'))
        face.material_index=blue
        try:
            try:audit_scene(jinwen,lod)
            except AssertionError:trials.append('continuous_blue_center_rejected')
            else:raise AssertionError('Front audit accepted continuous central blue')
        finally:face.material_index=old
        hit,normal,index,distance=tree.ray_cast(Vector((12,0,1.801)),Vector((-1,0,0)),2)
        face=host.data.polygons[index];old=face.material_index
        face.material_index=blue
        try:
            try:audit_scene(jinwen,lod)
            except AssertionError:trials.append('broken_red_center_rejected')
            else:raise AssertionError('Front audit accepted broken lower red')
        finally:face.material_index=old
    return trials


def geometry_hash(obj):
    h=hashlib.sha256()
    for v in obj.data.vertices:h.update(struct.pack('<3f',*(obj.matrix_world@v.co)))
    for face in obj.data.polygons:
        h.update(struct.pack('<'+str(len(face.vertices))+'I',*face.vertices))
    return h.hexdigest()


def material_triangles(obj,key):
    obj.data.calc_loop_triangles();result=Counter()
    for tri in obj.data.loop_triangles:
        if not obj.data.materials[tri.material_index].name.endswith('/'+key):continue
        coords=[tuple(round(c,7) for c in obj.matrix_world@obj.data.vertices[i].co) for i in tri.vertices]
        # Cyclic index rotations preserve winding; reversal does not.
        result[min(tuple(coords[i:]+coords[:i]) for i in range(3))]+=1
    return result


def main():
    sys.path.insert(0,str(ROOT))
    from prepare_scene_v24 import prepare
    from front_revision_v24 import apply_common,apply_number
    from livery_revision_v21 import _replace_signage
    from roster_v21 import ROSTER
    report={'status':'RUNNING','cases':[],'fleet_cases':[],'inputs_sha256':{}}
    for jinwen in (False,True):
        for lod in (0,1,2):
            b=prepare(lod,jinwen)
            side={o.name:geometry_hash(o) for o in bpy.context.scene.objects if o.get('livery21_variable') and o.get('livery21_role')!='nose_number'}
            shell=bpy.data.objects['body_open_shell_v07'];shell.data.calc_loop_triangles();before=len(shell.data.loop_triangles)
            red=material_triangles(shell,'jw_red')
            apply_common(b,jinwen);apply_number(b)
            row=audit_scene(jinwen,lod)
            if lod<2:row['negative_controls']=negative_controls(jinwen,lod)
            require(red==material_triangles(shell,'jw_red'),'Front edit changed red paint surface')
            require(side=={name:geometry_hash(bpy.data.objects[name]) for name in side},'Front edit changed side markings')
            shell.data.calc_loop_triangles();row['body_triangle_delta']=len(shell.data.loop_triangles)-before
            row['side_markings_unchanged']=True;row['red_surface_unchanged']=True
            # Calling again must not move marks a second time.
            first={o.name:geometry_hash(o) for o in bpy.context.scene.objects if o.get('front24_shifted')}
            apply_common(b,jinwen);apply_number(b)
            require(first=={name:geometry_hash(bpy.data.objects[name]) for name in first},'Front revision not idempotent')
            report['cases'].append(row)
            if lod<2:
                for vehicle in (v for v in ROSTER if v['jinwen']==jinwen):
                    _replace_signage(b,jinwen,vehicle['number'],vehicle['depot']);apply_number(b)
                    result=audit_scene(jinwen,lod)
                    report['fleet_cases'].append({'stem':vehicle['stem'],'lod':lod,'status':result['status'],
                                                  'front_ends':result['front_ends']})
            print('FRONT24 PROBE PASS',jinwen,lod,row['body_triangle_delta'],flush=True)
    for name in ('front_revision_v24.py','audit_front_v24.py'):
        report['inputs_sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    report['status']='PASS';report['scope']='Pre-build probe only; final sources and native resource readback need current-build audit'
    (ROOT/'runtime/front24_probe_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
