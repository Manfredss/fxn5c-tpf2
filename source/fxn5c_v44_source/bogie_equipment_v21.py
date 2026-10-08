"""Replace ONLY the old four identical bogie equipment boxes.

Photo-fit visible housings, not factory engineering dimensions. The cab-end
housing is a stepped rectangular case; the centre-of-locomotive end is a
shallower case with two chamfered lower corners. Both bogies have the same
cab/inboard relationship, not the same +X/-X relationship.

This pass never translates a bogie, axle, connection or carbody. The caller
owns longitudinal stationing. Original equipment faces are identified by an
exact recipe-derived polygon signature, not by deleting a broad spatial box.
"""
from collections import Counter
from pathlib import Path
import bpy
from bogie_details_v20 import Batch, _equipment

CAB_BOX_X = 2.51
INBOARD_BOX_X = 2.49


def _key(points):
    return tuple(sorted(tuple(round(float(v), 6) for v in p) for p in points))


def _legacy_keys(builder):
    batch = Batch(builder)
    for side in (-1, 1):
        for x in (-2.56, 2.56):
            _equipment(batch, x, side)
    return Counter(_key([batch.v[i] for i in face]) for face in batch.f)


def _case(m, end, side, cab, cab_x=CAB_BOX_X, inboard_x=INBOARD_BOX_X):
    # u is positive towards the nearest cab, irrespective of bogie number.
    centre = cab_x if cab else -inboard_x
    width = .64 if cab else .59
    if cab:
        # Low folded step is on the INBOARD half (towards the axle), not on
        # the nose-facing side as in the v20 generic box.
        outline = [(-.32,.46),(.065,.46),(.065,.620),(.32,.620),
                   (.32,1.095),(-.32,1.095)]
    else:
        outline = [(-.295,.790),(-.168,.650),(.168,.650),(.295,.790),
                   (.295,1.095),(-.295,1.095)]
    shape = [(end*(centre+u), z) for u,z in outline]
    def point(u,y,z):return (end*(centre+u),side*y,z)
    m.profile('equipment21_cab_case' if cab else 'equipment21_inboard_case',
              shape,side*1.34,.25,'graphite')
    m.profile('equipment21_cab_lid' if cab else 'equipment21_inboard_lid',
              shape,side*1.475,.021,'spring_steel')
    inset = [(end*(centre+u*.953), .680+(z-.680)*.952) for u,z in outline]
    m.profile('equipment21_lid_field',inset,side*1.491,.014,'graphite')
    # The visible lid fastening is a short upper hinge, not a repeated full
    # panel of imaginary rivets. Small seams disappear at LOD1.
    m.box('equipment21_upper_hinge',point(0,1.510,1.073),(.115,.025,.028),'spring_steel',.004)
    for u in (-width*.30,width*.30):
        m.box('equipment21_mount',point(u,1.267,1.128),(.050,.260,.100),'graphite',.007)
    if cab:
        m.box('equipment21_step_recess',point(-.129,1.510,.566),(.336,.013,.109),'black',.004)
        m.box('equipment21_folded_step',point(-.129,1.531,.504),(.362,.066,.018),'spring_steel')
    if m.b.lod==0:
        for u in (-width*.39,width*.39):
            m.cyl('equipment21_lid_screw',point(u,1.508,1.046),.011,.010,'metal',segments=6)
        m.box('equipment21_small_plate',point(.18 if cab else -.16,1.512,1.057),(.066,.007,.023),'metal')
    # A short exposed top lead returns to the existing bogie air-main region.
    # Do not invent the concealed continuation or identify the case subsystem.
    lead_u = .12 if cab else -.12
    points=[point(lead_u,1.301,1.195),point(lead_u,1.410,1.195),
            point(lead_u-.10,1.460,1.153),point(-width*.42,1.460,1.153),
            point(-width*.42,1.415,1.080)]
    m.tube('equipment21_top_lead',points,.012,'spring_steel',8 if not m.b.lod else 6)
    m.cyl('equipment21_top_union',point(-width*.42,1.415,1.095),.022,.041,
          'graphite',axis='Z',segments=8)


def _replace(obj,builder,end,cab_x,inboard_x):
    old=obj.data
    targets=_legacy_keys(builder)
    kept=[];removed=[]
    for face in old.polygons:
        key=_key([old.vertices[i].co for i in face.vertices])
        if targets[key]:
            targets[key]-=1;removed.append(face.index)
        else:kept.append(face)
    missing=sum(targets.values())
    if missing:
        raise RuntimeError(f'{obj.name}: {missing} legacy equipment faces not found; refusing broad deletion')
    before=sum(len(face.vertices)-2 for face in old.polygons if face.index in set(removed))
    batch=Batch(builder)
    for side in (-1,1):
        _case(batch,end,side,True,cab_x,inboard_x)
        _case(batch,end,side,False,cab_x,inboard_x)
    # Finish only the new components to establish their proper smooth normals.
    addition=batch.finish('_equipment21_temporary',None)
    new=addition.data
    old_normals=[tuple(n.vector) for n in old.corner_normals]
    new_normals=[tuple(n.vector) for n in new.corner_normals]
    retained=sorted({i for f in kept for i in f.vertices})
    lookup={i:j for j,i in enumerate(retained)}
    verts=[tuple(old.vertices[i].co) for i in retained]+[tuple(v.co) for v in new.vertices]
    faces=[tuple(lookup[i] for i in f.vertices) for f in kept]
    faces += [tuple(len(retained)+i for i in f.vertices) for f in new.polygons]
    mats=list(old.materials)
    jinwen=any(Path(mat.name).name=='jw_frame' for mat in old.materials)
    mapping={'graphite':'jw_frame','spring_steel':'jw_frame','cast_steel':'jw_spring'} if jinwen else {}
    extra_indices=[]
    for mat in new.materials:
        key=Path(mat.name).name
        actual=builder.mat(mapping.get(key,key))
        if actual not in mats:mats.append(actual)
        extra_indices.append(mats.index(actual))
    mesh=bpy.data.meshes.new(obj.name+'_equipment21_mesh')
    mesh.from_pydata(verts,[],faces);mesh.update()
    for mat in mats:mesh.materials.append(mat)
    originals=[(f.material_index,f.use_smooth) for f in kept]
    originals += [(extra_indices[f.material_index],f.use_smooth) for f in new.polygons]
    for f,(mi,smooth) in zip(mesh.polygons,originals):
        f.material_index=mi;f.use_smooth=smooth
    old_loops=[i for f in kept for i in f.loop_indices]
    for old_layer in old.uv_layers:
        layer=mesh.uv_layers.new(name=old_layer.name)
        for i,j in enumerate(old_loops):layer.data[i].uv=old_layer.data[j].uv
        for loop in list(mesh.loops)[len(old_loops):]:
            co=mesh.vertices[loop.vertex_index].co
            layer.data[loop.index].uv=(co.x*.071+.5,co.z*.14+co.y*.03)
    mesh.normals_split_custom_set([old_normals[i] for i in old_loops]+new_normals)
    obj.data=mesh
    bpy.data.objects.remove(addition,do_unlink=True)
    if new.users==0:bpy.data.meshes.remove(new)
    obj['equipment21_applied']=True
    obj['equipment21_cab_direction']=end
    obj['equipment21_cab_x']=cab_x
    obj['equipment21_inboard_x']=inboard_x
    obj['equipment21_removed_triangles']=before
    obj['equipment21_removed_polygons']=len(removed)
    obj['equipment21_cab_cases']=2
    obj['equipment21_inboard_cases']=2
    mesh.calc_loop_triangles()
    obj['triangles_v21']=len(mesh.loop_triangles)
    return {'name':obj.name,'removed_polygons':len(removed),
            'removed_triangles':before,'triangles':len(mesh.loop_triangles),
            'cab_direction':end,'cab_local_x':end*cab_x,
            'inboard_local_x':-end*inboard_x}


def apply(builder,cab_x=CAB_BOX_X,inboard_x=INBOARD_BOX_X):
    """LOD0 saved-source and LOD1 procedural compatible; distant LOD unchanged."""
    if builder.lod>=2:return []
    results=[]
    for index,end in ((1,1),(2,-1)):
        obj=bpy.data.objects[f'b{index}']
        if obj.get('equipment21_applied'):
            if obj.get('equipment21_cab_x')!=cab_x or obj.get('equipment21_inboard_x')!=inboard_x:
                raise RuntimeError('Reapply changed equipment parameters only to an untouched source')
            continue
        results.append(_replace(obj,builder,end,cab_x,inboard_x))
    bpy.context.view_layer.update()
    return results
