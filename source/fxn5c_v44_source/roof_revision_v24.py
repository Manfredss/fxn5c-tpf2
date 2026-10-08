"""Photo-fitted two-fold upper section, with rigid equipment reseating.

The section coordinates are reconstruction estimates, not manufacturer data.
Only upper body/roof geometry is changed. Wheelsets, underframe and windscreen
glazing are out of scope. Call on an editable v23 baseline, before light emitters.
"""
from pathlib import Path
import math
import bpy
import bmesh
from mathutils import Vector
from geometry_v02 import Builder as BaseBody
from geometry_v05 import split_polygon

EAVE_Z, KNEE_Z, CROWN_Z = 3.95, 4.28, 4.705
EAVE_Y, KNEE_Y, CROWN_Y = 1.65, 1.34, .48
GRAY_Z = 4.24
UPPER_LAMP_Z = 4.43
CAB_FRONT_STATION = 9.18
AC_DROP = .070


def roof_half_width(z):
    if z <= EAVE_Z:return EAVE_Y
    if z <= KNEE_Z:return EAVE_Y+(KNEE_Y-EAVE_Y)*(z-EAVE_Z)/(KNEE_Z-EAVE_Z)
    if z <= CROWN_Z:return KNEE_Y+(CROWN_Y-KNEE_Y)*(z-KNEE_Z)/(CROWN_Z-KNEE_Z)
    return CROWN_Y


def roof_z(y):
    y=abs(y)
    if y <= CROWN_Y:return CROWN_Z
    if y <= KNEE_Y:return CROWN_Z-(y-CROWN_Y)*(CROWN_Z-KNEE_Z)/(KNEE_Y-CROWN_Y)
    return KNEE_Z-(y-KNEE_Y)*(KNEE_Z-EAVE_Z)/(EAVE_Y-KNEE_Y)


def upper_front_x(z):
    # Preserve the old brow/glass joint and its fore-aft inclination.
    # The new actual front face continues to the crown instead of terminating
    # at Z4.48 below the separate, broad legacy hood.
    return BaseBody.front_x(z)


def upper_lamp_point(y,z,offset=0.0,end=1):
    return (end*(upper_front_x(z)+offset),y,z)


def upper_emitter_point(builder,end,side,u,v):
    return upper_lamp_point(side*.15+u,UPPER_LAMP_Z+v,-.090,end)


def _old_width(z):
    rows=((3.95,1.65),(4.48,1.15),(4.65,1.04),(4.705,.90))
    for a,c in zip(rows,rows[1:]):
        if z<=c[0]:return a[1]+(c[1]-a[1])*(z-a[0])/(c[0]-a[0])
    return .90


def _structural_point(p):
    p=Vector(p)
    if p.z>EAVE_Z:
        p.y*=roof_half_width(p.z)/_old_width(p.z)
    return p


def _world_vertices(obj):return [obj.matrix_world@v.co for v in obj.data.vertices]


def _edit(obj,mapper,tag):
    inv=obj.matrix_world.inverted()
    for vertex in obj.data.vertices:vertex.co=inv@Vector(mapper(obj.matrix_world@vertex.co))
    obj.data.update();obj['roof24_operation']=tag


def _rebuild(obj,rows):
    old=obj.data; inv=obj.matrix_world.inverted()
    verts=[];faces=[];indices=[];smooth=[]
    for points,idx,sm in rows:
        if len(points)<3:continue
        start=len(verts);verts.extend(tuple(inv@Vector(p)) for p in points)
        faces.append(tuple(range(start,len(verts))));indices.append(idx);smooth.append(sm)
    mesh=bpy.data.meshes.new(old.name+'_roof24')
    mesh.from_pydata(verts,[],faces)
    for m in old.materials:mesh.materials.append(m)
    for face,idx,sm in zip(mesh.polygons,indices,smooth):face.material_index=idx;face.use_smooth=sm
    mesh.update();obj.data=mesh


def _clip_mesh(obj,planes,keep=lambda p:True,roof_only=False):
    rows=[];tf=obj.matrix_world
    for face in obj.data.polygons:
        parts=[[tuple(tf@obj.data.vertices[i].co) for i in face.vertices]]
        for plane in planes:
            parts=[q for p in parts for q in
                   ([p] if roof_only and max(v[2] for v in p)<=EAVE_Z+1e-7 else split_polygon(p,plane))]
        for points in parts:
            center=sum((Vector(p) for p in points),Vector())/len(points)
            if keep(center):rows.append((points,face.material_index,face.use_smooth))
    _rebuild(obj,rows)


def _compact(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
    bmesh.ops.dissolve_limit(bm,angle_limit=1e-5,verts=list(bm.verts),edges=list(bm.edges),
        use_dissolve_boundaries=False,delimit={'MATERIAL','NORMAL'})
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free();obj.data.update()


def _color_upper(obj,b,jw):
    keys=[Path(m.name).name for m in obj.data.materials]
    paint={'blue','light_blue','roof','jw_roof','jw_white','jw_blue'}
    if not any(k in paint for k in keys):return
    # Clip actual faces; no separate paint strip or floating overlay.
    _clip_mesh(obj,[lambda p:p[2]-EAVE_Z,lambda p:p[2]-GRAY_Z])
    roof=b.mat('jw_roof' if jw else 'roof');blue=b.mat('blue')
    for mat in (roof,blue):
        if mat.name not in [m.name for m in obj.data.materials]:obj.data.materials.append(mat)
    inds={m.name:i for i,m in enumerate(obj.data.materials)}
    tf=obj.matrix_world
    for face in obj.data.polygons:
        if keys[face.material_index] not in paint:continue
        c=sum((tf@obj.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
        if c.z<EAVE_Z-1e-6:continue
        # The forward brow is dark gray on CR; its lower roof-side strip stays blue.
        front=abs(c.x)>upper_front_x(c.z)-.04
        if jw or c.z>=GRAY_Z-1e-7 or front:face.material_index=inds[roof.name]
        elif keys[face.material_index] != 'light_blue':face.material_index=inds[blue.name]
    obj['roof24_gray_boundary']=GRAY_Z


def _section():
    return [(-EAVE_Y,EAVE_Z),(-KNEE_Y,KNEE_Z),(-CROWN_Y,CROWN_Z),
            (CROWN_Y,CROWN_Z),(KNEE_Y,KNEE_Z),(EAVE_Y,EAVE_Z)]


def _front_canopy(b,end,jw):
    """Two folds reach the actual front face, including its original corner inset."""
    section=_section(); back=[];front=[]
    for y,z in section:
        back.append((end*CAB_FRONT_STATION,y,z))
        # At the eave the old four-sided nose corner is retained exactly.
        x=upper_front_x(z)
        if z==EAVE_Z:x-=.30*(abs(y)-b.front_half(z))
        front.append((end*x,y,z))
    points=back+front
    n=len(section)
    faces=[(i,i+1,n+i+1,n+i) for i in range(n-1)]
    obj=b.poly('roof24_front_folded_canopy',points,faces,'jw_roof' if jw else 'roof',normal=(0,0,1))
    obj['roof24_operation']='new_front_canopy';obj['roof24_end']=end
    _color_upper(obj,b,jw)
    # Front face keeps the old eave/nose corner vertices below the first fold.
    face_points=[(end*upper_front_x(EAVE_Z),-b.front_half(EAVE_Z),EAVE_Z),front[0]]+front[1:-1]+[
        front[-1],(end*upper_front_x(EAVE_Z),b.front_half(EAVE_Z),EAVE_Z)]
    brow=b.poly('roof24_full_height_brow',face_points,[tuple(range(len(face_points)))],
                'jw_roof' if jw else 'roof',normal=(end,0,0))
    brow['roof24_operation']='new_full_height_front_face';brow['roof24_end']=end
    # A real front equipment-bay bulkhead joins the retained Z4.48 shell to
    # this raised cab cap. Without it the AC-pocket edge is an open slit.
    rear_z=4.65 if b.lod>=2 else 4.48
    y48=roof_half_width(rear_z)
    bulkhead=b.poly('roof24_ac_front_bulkhead',[(end*CAB_FRONT_STATION,y,z) for y,z in
        [(-y48,rear_z),(-CROWN_Y,CROWN_Z),(CROWN_Y,CROWN_Z),(y48,rear_z)]],
        [(0,1,2,3)],'jw_roof' if jw else 'roof',normal=(-end,0,0))
    bulkhead['roof24_operation']='attached_ac_bay_bulkhead'
    # The lamp is an actual aperture in the new face, with the retained cavity
    # return joining its cut edge. It is not a dark decal painted on solid skin.
    from front_details_v10 import TOP_INNER
    from geometry_v06 import chamfer_polygon
    loop=chamfer_polygon([(y,z+UPPER_LAMP_Z-4.27) for y,z in TOP_INNER],.010)
    cutter=b.sheet('roof24_lamp_cutter',loop,
        lambda y,z:upper_lamp_point(y,z,.16,end),'black',.5,(end,0,0))
    b.cut(brow,cutter)
    return [obj,brow]


def _fan_map(p,side):
    from jinwen_roof_v20 import basis
    center,oldv,oldn=basis(side)
    newv=Vector((0,side*(KNEE_Y-CROWN_Y),KNEE_Z-CROWN_Z)).normalized()
    newn=Vector((0,side*(CROWN_Z-KNEE_Z),KNEE_Y-CROWN_Y)).normalized()
    target=Vector((0,side*(KNEE_Y+CROWN_Y)/2,(KNEE_Z+CROWN_Z)/2))
    relative=Vector(p)-center
    return target+Vector((relative.x,0,0))+newv*relative.dot(oldv)+newn*relative.dot(oldn)


def _fan_skin(b,jw):
    # Replace only the short existing aperture bay so its edges follow the
    # rigidly rotated fan guard, rather than leaving the old warped hole behind.
    section=_section();n=len(section)
    verts=[(x,y,z) for x in (2.10,3.60) for y,z in section]
    obj=b.poly('roof24_shoulder_fan_skin',verts,[(i,i+1,n+i+1,n+i) for i in range(n-1)],
        'jw_roof' if jw else 'roof',normal=(0,0,1))
    obj['roof24_operation']='new_fan_bay_skin'
    from jinwen_roof_v20 import basis,rectangle
    for side in (-1,1):
        center,slope,normal=basis(side);center.x=2.85
        loop=rectangle(.711,.338)
        cutter=b.sheet('roof24_fan_aperture',loop,
            lambda u,v:tuple(_fan_map(center+Vector((u,0,0))+slope*v+normal*.15,side)),
            'black',.65,Vector((0,side*(CROWN_Z-KNEE_Z),KNEE_Y-CROWN_Y)).normalized())
        b.cut(obj,cutter)
    _color_upper(obj,b,jw)
    return obj


def _upper_fixture_point(p):
    old=Vector(p);end=1 if old.x>0 else -1
    off=abs(old.x)-BaseBody.front_x(old.z)
    return Vector(upper_lamp_point(old.y,old.z+UPPER_LAMP_Z-4.27,off,end))


def sanitize_after_export(path):
    """Omit exact-zero export triangles without reevaluating source ngons.

    AFTER snapshots only. All position/UV/normal/tangent bytes and every valid
    triangle's original corner indices/order are retained exactly. No epsilon
    or native-audit exception is used; the before snapshot remains immutable.
    The source scene is untouched, including its non-rendering zero-area caps.
    """
    import hashlib
    import numpy as np
    from verify_native import read_lua
    from native_merge_v22 import lua_literal
    path=Path(path);blob_path=Path(str(path)+'.blob')
    desc=read_lua(path);raw=blob_path.read_bytes()
    position=desc['vertexAttr']['position']
    points=np.frombuffer(raw,dtype='<f4',offset=position['offset'],count=position['count']//4).reshape(-1,3).astype(np.float64)
    prefix_size=max(a['offset']+a['count'] for a in desc['vertexAttr'].values())
    new=bytearray(raw[:prefix_size]);removed=0;kept_count=0;slots=[]
    for slot,sub in enumerate(desc['subMeshes']):
        attr=sub['indices']['position']
        indices=np.frombuffer(raw,dtype='<u4',offset=attr['offset'],count=attr['count']//4).reshape(-1,3)
        p=points[indices];cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
        dead=np.all(cross==0,axis=1);valid=indices[~dead]
        assert len(valid)>0,('zero-only material slot requires explicit material remap',path,slot)
        for stream in sub['indices'].values():
            encoded=np.frombuffer(raw,dtype='<u4',offset=stream['offset'],count=stream['count']//4).reshape(-1,3)
            assert np.array_equal(encoded,indices),('unexpected independent corner-index stream',path,slot)
        offset=len(new);data=valid.astype('<u4').tobytes();new.extend(data)
        for stream in sub['indices'].values():stream['offset']=offset;stream['count']=len(data)
        count=int(dead.sum());removed+=count;kept_count+=len(valid)
        slots.append({'slot':slot,'removed_strict_zero_triangles':count,'valid_triangles':len(valid),
                      'valid_original_index_bytes_sha256':hashlib.sha256(data).hexdigest()})
    assert bytes(new[:prefix_size])==raw[:prefix_size]
    path.write_text('function data()\nreturn '+lua_literal(desc)+'\nend\n',encoding='utf8')
    blob_path.write_bytes(new)
    return {'removed_triangles':removed,'removed_strict_zero_triangles':removed,'triangles':kept_count,
            'attribute_prefix_sha256':hashlib.sha256(raw[:prefix_size]).hexdigest(),
            'original_attribute_bytes_unchanged':True,'source_scene_modified':False,'slots':slots}


def apply(b,jinwen=False):
    if bpy.context.scene.get('roof24_applied'):raise RuntimeError('roof v24 may only apply once')
    originals=list(bpy.context.scene.objects)
    report={'lod':b.lod,'jinwen':jinwen,'section_yz':_section(),'gray_z':GRAY_Z,
            'upper_lamp_z':UPPER_LAMP_Z,'ac_rigid_drop':AC_DROP,'changed_glazing':[],
            'rigid_fan_parts':[],'changed_objects':[],'removed_objects':[]}
    shell=next(o for o in originals if o.name.startswith('body_open_shell_v07'))
    # Split only authorised front/fan roof patches away from the retained body.
    planes=[lambda p:p[2]-EAVE_Z,lambda p:p[0]-CAB_FRONT_STATION,
            lambda p:p[0]+CAB_FRONT_STATION]
    if b.lod<2:planes += [lambda p:p[0]-2.10,lambda p:p[0]-3.60]
    _clip_mesh(shell,planes,lambda p:not(p.z>EAVE_Z+1e-7 and
       (b.lod>=2 or abs(p.x)>CAB_FRONT_STATION+1e-7 or 2.10+1e-7<p.x<3.60-1e-7)),roof_only=True)
    fixture=('flush_upper_lamp_gasket','upper_lamp_cavity_back','shared_lamp_cover',
             'concave_upper_reflector','upper_reflector_retainer','upper_inner_optic')
    ac=('cab_roof_well_floor','cab_aircon_','ac_','roof_ac_conduit')
    radiator_rigid=('recessed_fan_shroud','radiator_fan_hub','concealed_fan_blade')
    skipped=('bounds|','headlights_','taillights_')
    for obj in originals:
        if obj.type!='MESH' or obj.name.startswith(skipped):continue
        pts=_world_vertices(obj)
        if not pts or max(p.z for p in pts)<EAVE_Z-1e-7:continue
        if obj.name.startswith('grey_brow_'):
            report['removed_objects'].append(obj.name);bpy.data.objects.remove(obj,do_unlink=True);continue
        upper_glass=obj.name.startswith('glazing_') and min(p.z for p in pts)>4.05
        if obj.name.startswith(fixture) or upper_glass:
            _edit(obj,_upper_fixture_point,'upper_fixture_reseat')
            if upper_glass:report['changed_glazing'].append(obj.name)
        elif obj.name.startswith(('brow_vent_','brow_recessed_flat_slat')):
            def brow_map(p):
                end=1 if p.x>0 else -1
                off=abs(p.x)-BaseBody.front_x(p.z)
                return upper_lamp_point(p.y*.90,p.z+.14,off,end)
            _edit(obj,brow_map,'brow_grille_reseat')
        elif obj.name.startswith('roof20_'):
            if obj.name.startswith('roof20_flat_crown'):
                report['removed_objects'].append(obj.name);bpy.data.objects.remove(obj,do_unlink=True);continue
            side=-1 if sum(p.y for p in pts)<0 else 1
            _edit(obj,lambda p,s=side:_fan_map(p,s),'rigid_fan_bay_rotation')
            _color_upper(obj,b,jinwen)
            report['rigid_fan_parts'].append(obj.name)
        elif obj.name.startswith(ac):
            _edit(obj,lambda p:Vector(p)-Vector((0,0,AC_DROP)),'rigid_ac_bay_reseat')
        elif obj.name.startswith(radiator_rigid):
            # These circular horizontal rotors already fit the new envelope.
            obj['roof24_operation']='radiator_rotor_unchanged';continue
        else:
            if obj.name.startswith('cab_continuous_low_hood_v13'):
                _clip_mesh(obj,[lambda p:p[0]-CAB_FRONT_STATION,lambda p:p[0]+CAB_FRONT_STATION],
                           lambda p:abs(p.x)<=CAB_FRONT_STATION+1e-7)
                _compact(obj)
            _edit(obj,_structural_point,'upper_structural_section')
            if obj.name.startswith('cab_continuous_low_hood_v13'):_compact(obj)
            if not obj.name.startswith(('glazing_','brow_horizontal_joint')):_color_upper(obj,b,jinwen)
        report['changed_objects'].append(obj.name)
    for end in (-1,1):_front_canopy(b,end,jinwen)
    if b.lod>=2:
        ytop=roof_half_width(4.65)
        section=[(-EAVE_Y,EAVE_Z),(-KNEE_Y,KNEE_Z),(-ytop,4.65),
                 (ytop,4.65),(KNEE_Y,KNEE_Z),(EAVE_Y,EAVE_Z)]
        verts=[(x,y,z) for x in (-CAB_FRONT_STATION,CAB_FRONT_STATION) for y,z in section]
        distant=b.poly('roof24_distant_center_roof',verts,
            [(i,i+1,6+i+1,6+i) for i in range(5)],'jw_roof' if jinwen else 'roof',normal=(0,0,1))
        _color_upper(distant,b,jinwen)
    if b.lod<2:
        # Complete AC bays moved rigidly downward. Open their new occupied
        # volume in the original shell; the retained metal floor overlaps the
        # cut by15mm per side and supports the unchanged case proportions.
        for end in (-1,1):
            cutter=BaseBody.box(b,'roof24_ac_shell_clearance',
                (end*8.65,0,4.76),(1.06,2.02,.72),'black')
            b.cut(shell,cutter)
    if b.lod<2:_fan_skin(b,jinwen)
    # Existing upper sheets are deliberately flat shaded after topology edits.
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();b.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['roof24_applied']=True
    bpy.context.scene['roof24_section_estimated']=True
    bpy.context.scene['roof24_gray_boundary']=GRAY_Z
    bpy.context.scene['roof24_upper_lamp_z']=UPPER_LAMP_Z
    return report
