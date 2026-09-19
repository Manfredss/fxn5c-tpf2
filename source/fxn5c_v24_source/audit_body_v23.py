"""Independent selected-mount/lettering audit; not whole-train clearance."""
import hashlib
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT=Path(__file__).resolve().parent
_GLYPH_AREA={}


def require(ok, msg):
    if not ok:raise AssertionError(msg)


def points(obj):
    return [obj.matrix_world@v.co for v in obj.data.vertices]


def bounds(obj):
    p=points(obj)
    return [[min(v[i] for v in p),max(v[i] for v in p)] for i in range(3)]


def pick(prefix, side):
    objs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith(prefix)
          and sum(bounds(o)[1])*side>0]
    require(len(objs)==1,('expected single side part',prefix,side,len(objs)))
    return objs[0]


def tree(objects):
    verts,faces=[],[]
    for obj in objects:
        base=len(verts);verts.extend(points(obj))
        faces.extend(tuple(base+i for i in f.vertices) for f in obj.data.polygons)
    return BVHTree.FromPolygons(verts,faces)


def surface_y(bvh,x,z,side):
    hit,normal,index,distance=bvh.ray_cast(Vector((x,side*3,z)),Vector((0,-side,0)),4)
    require(hit is not None,('unbacked location',x,z,side))
    return abs(hit.y)


def overlap(a,b):
    aa,bb=bounds(a),bounds(b)
    return [min(aa[i][1],bb[i][1])-max(aa[i][0],bb[i][0]) for i in range(3)]


def plain_glyph_area(value,width,height,resolution):
    """Independent zero-offset Arial Bold baseline at the same footprint."""
    key=(value,round(width,5),round(height,5),resolution)
    if key in _GLYPH_AREA:return _GLYPH_AREA[key]
    bpy.ops.object.text_add();obj=bpy.context.object;curve=obj.data
    curve.body=value;curve.size=1;curve.space_character=1.04;curve.offset=0
    curve.resolution_u=resolution
    curve.font=bpy.data.fonts.load('C:/Windows/Fonts/arialbd.ttf',check_existing=True)
    bpy.ops.object.convert(target='MESH')
    p=[v.co for v in obj.data.vertices]
    w=max(v.x for v in p)-min(v.x for v in p)
    h=max(v.y for v in p)-min(v.y for v in p)
    area=sum(f.area for f in obj.data.polygons)*width*height/(w*h)
    mesh=obj.data;bpy.data.objects.remove(obj,do_unlink=True)
    if mesh.users==0:bpy.data.meshes.remove(mesh)
    _GLYPH_AREA[key]=area
    return area


def number_checks(jinwen=False,lod=0):
    host=tree([bpy.data.objects['body_open_shell_v07'],bpy.data.objects['chassis_sill']])
    rows=[]
    nums=[o for o in bpy.context.scene.objects if o.get('livery21_role')=='cab_number']
    require(len(nums)==4,'four cab numbers required')
    for obj in nums:
        box=bounds(obj);side=int(obj['livery21_side']);end=int(obj['livery21_end'])
        expected=(end*(10.0 if jinwen else 9.84),2.515 if jinwen else 2.355,
                  .96 if jinwen else 1.00,.155 if jinwen else .148)
        actual=(sum(box[0])/2,sum(box[2])/2,box[0][1]-box[0][0],box[2][1]-box[2][0])
        require(max(abs(a-b) for a,b in zip(actual,expected))<3e-5,('cab footprint changed',obj.name,actual))
        gaps=[abs(p.y)-surface_y(host,p.x,p.z,side) for p in points(obj)]
        require(min(gaps)>.00045 and max(gaps)<.00095,('floating/embedded cab number',obj.name,min(gaps),max(gaps)))
        obj.data.calc_loop_triangles()
        area=sum((obj.data.vertices[t.vertices[1]].co-obj.data.vertices[t.vertices[0]].co).cross(
             obj.data.vertices[t.vertices[2]].co-obj.data.vertices[t.vertices[0]].co).length*.5 for t in obj.data.loop_triangles)
        require(area>0,('empty cab glyph area',obj.name))
        ratio=area/plain_glyph_area(obj['livery21_text'],actual[2],actual[3],4 if lod==0 else 2)
        require(1.07<ratio<1.16,('number stroke weight outside slight-bold target',obj.name,ratio))
        require(abs(obj.get('body23_number_outline_offset',0)-.006)<1e-8,('missing stroke revision',obj.name))
        rows.append({'name':obj.name,'text':obj['livery21_text'],'footprint':actual,
                     'glyph_area_m2':area,'area_ratio_vs_plain_bold_font':ratio,'max_host_clearance_m':max(gaps)})
    ends=[o for o in bpy.context.scene.objects if o.get('livery21_role')=='cab_end']
    require(len(ends)==4,'I/II marks lost')
    for obj in ends:
        require(obj['livery21_text']==('I' if obj['livery21_end']>0 else 'II'),('wrong end',obj.name))
        side=int(obj['livery21_side'])
        gaps=[abs(p.y)-surface_y(host,p.x,p.z,side) for p in points(obj)]
        require(min(gaps)>.00045 and max(gaps)<.00095,('floating end mark',obj.name))
    return rows


def v22_selected_contacts():
    """Measure actual per-part ranges, not only advertised component bounds."""
    checks=[]
    sill=bpy.data.objects['chassis_sill']; sb=bounds(sill);actual_sill=tree([sill])
    for obj in bpy.context.scene.objects:
        if not obj.name.startswith(('body22_gap_','body22_nose_')):continue
        entries=json.loads(obj['v22_components'])
        parts={}
        for entry in entries:
            a,b=entry['vertex_range'];p=[obj.matrix_world@obj.data.vertices[i].co for i in range(a,b)]
            box=[[min(v[i] for v in p),max(v[i] for v in p)] for i in range(3)]
            parts.setdefault(entry['id'],[]).append(box)
        for key in ('stack_sill_mount','gap_sill_mount','nose_pipe_sill_shoe','nose_pipe_support_web'):
            for p in parts.get(key,[]):
                penetration=[min(p[i][1],sb[i][1])-max(p[i][0],sb[i][0]) for i in range(3)]
                require(min(penetration)>0,('unsupported v22 selected bracket',obj.name,key,penetration))
                origin=Vector((sum(p[0])/2,sum(p[1])/2,1.30))
                hit,normal,index,distance=actual_sill.ray_cast(origin,Vector((0,0,1)),.4)
                require(hit is not None and p[2][0]<hit.z<p[2][1],('bracket does not penetrate actual sill surface',obj.name,key))
                checks.append({'mesh':obj.name,'component':key,'sill_overlap_xyz_m':penetration,'sill_ray_hit_z':hit.z})
    require(len(checks)==16,('selected v22 body mounts inventory',len(checks)))
    return checks


def audit_scene(jinwen=False,lod=0):
    if lod>=2:return {'status':'PASS','lod':lod,'scope':'no close-detail revision at LOD2'}
    result={'status':'RUNNING','lod':lod,'jinwen':jinwen,'fillers':[],'gauges':[],
            'scope':'selected body mounts and cab markings only; not all-parts or game motion certification'}
    if lod==0:
        host=tree([bpy.data.objects['body_open_shell_v07'],bpy.data.objects['chassis_sill']])
        tank=bpy.data.objects['main_fuel_tank']
        for side in (-1,1):
            cap=pick('fuel_cap_v05',side);neck=pick('fuel_neck_recess_v05',side)
            collar=pick('fuel_mount_collar_v23',side);gauge=pick('fuel_level_gauge_dark',side)
            mount=pick('fuel_gauge_mount_v23',side)
            cb=bounds(cap);gb=bounds(gauge);nb=bounds(neck)
            cap_x=sum(cb[0])/2;gauge_x=sum(gb[0])/2;z=sum(cb[2])/2
            require(abs((cap_x-gauge_x)*side-.75)<2e-5,('wrong reading-side filler offset',side,cap_x,gauge_x))
            require(abs(z-1.55)<2e-5,('filler height',side,z))
            rear=min(abs(x) for x in bounds(collar)[1]);front=max(abs(x) for x in bounds(collar)[1])
            support_y=surface_y(host,cap_x,1.50,side)
            require(rear<support_y-.005 and front>support_y,('floating collar',side,rear,front,support_y))
            require(min(overlap(neck,collar))>0,('fuel neck not touching collar',side))
            for a,b in ((neck,pick('fuel_neck_rim_v05',side)),(pick('fuel_neck_rim_v05',side),cap),
                        (cap,pick('fuel_cap_crossbar',side))):
                require(min(overlap(a,b))>0,('separated fuel neck chain',a.name,b.name))
            require(min(overlap(mount,tank))>.005,('gauge housing not connected to fuel tank',side,overlap(mount,tank)))
            mb=bounds(mount);gauge_gap=min(abs(y) for y in gb[1])-max(abs(y) for y in mb[1])
            require(.0003<gauge_gap<.0009,('floating/embedded sight gauge',side,gauge_gap))
            bezel=pick('fuel_level_gauge_bezel',side)
            screws=[o for o in bpy.context.scene.objects if o.name.startswith('gauge_mount_screw')
                    and sum(bounds(o)[1])*side>0]
            require(len(screws)==2,('missing gauge screws',side))
            for screw in screws:
                require(min(overlap(screw,bezel))>0,('unseated gauge screw',screw.name))
            labels=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith(('fuel_label_v05','fuel_warning_'))
                    and sum(bounds(o)[1])*side>0]
            require(len(labels)==5,('fuel label inventory',side,len(labels)))
            for label in labels:
                gaps=[abs(p.y)-surface_y(host,p.x,p.z,side) for p in points(label)]
                require(min(gaps)>.00045 and max(gaps)<.00105,('unseated fuel label',label.name,min(gaps),max(gaps)))
            result['fillers'].append({'side':side,'x':cap_x,'z':z,'collar_rear_y_abs':rear,
                                      'actual_host_y_abs':support_y,'cap_chain_connected':True})
            result['gauges'].append({'side':side,'paint_gap_m':gauge_gap,'tank_overlap_m':overlap(mount,tank)})
    result['cab_numbers']=number_checks(jinwen,lod)
    result['selected_v22_mounts']=v22_selected_contacts()
    result['status']='PASS'
    return result


def negative_controls(jinwen=False):
    caught=[]
    def move_bad(name,obj,delta):
        old=obj.location.copy();obj.location+=Vector(delta);bpy.context.view_layer.update()
        try:
            try:audit_scene(jinwen,0)
            except AssertionError:caught.append(name)
            else:raise AssertionError('Negative control escaped: '+name)
        finally:obj.location=old;bpy.context.view_layer.update()
    move_bad('filler_no_longer_left',pick('fuel_cap_v05',1),(.06,0,0))
    move_bad('detached_collar',pick('fuel_mount_collar_v23',1),(0,.09,0))
    move_bad('floating_gauge_housing',pick('fuel_gauge_mount_v23',1),(0,.40,0))
    number=next(o for o in bpy.context.scene.objects if o.get('livery21_role')=='cab_number')
    move_bad('floating_cab_number',number,(0,.03*number['livery21_side'],0))
    return caught


def main():
    report={'status':'RUNNING','sources':[],'inputs_sha256':{}}
    for jinwen in (False,True):
        path=ROOT/('fxn5c_jinwen_source.blend' if jinwen else 'fxn5c_source.blend')
        bpy.ops.wm.open_mainfile(filepath=str(path))
        row=audit_scene(jinwen,0);row['negative_controls']=negative_controls(jinwen)
        report['sources'].append(row)
        report['inputs_sha256'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('body_revision_v23.py','audit_body_v23.py'):
        report['inputs_sha256'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    report['status']='PASS'
    (ROOT/'audit_body_v23.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('v23 common body audit PASS: two source scenes and eight negative controls')


if __name__=='__main__':main()
