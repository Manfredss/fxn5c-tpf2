"""Inner-end sandboxes, confirmed by user; outer-end cases stay unchanged.

Uses the existing fitted chamfered silhouette and hangers. Lid, hopper outlet
and route are visual reconstruction, not manufacturer pipework dimensions.
"""
from collections import Counter
from pathlib import Path
import bpy
from bogie_details_v20 import Batch
from bogie_equipment_v21 import _case, _key


def selected_objects():
    # Distant bogies have no detailed boxes and remain byte-for-byte intact.
    return [o for o in bpy.context.scene.objects if o.name in ('b1','b2')
            and o.type=='MESH' and o.get('equipment21_applied')]


def old_parts(b,end,cab_x,inner_x):
    m=Batch(b)
    for side in (-1,1):
        _case(m,end,side,False,cab_x,inner_x)
        if b.lod==0:
            sign=-end
            m.tube('sand_pipe',[(sign*2.67,side*1.205,1.15),(sign*2.69,side*1.205,.82),
                    (sign*2.56,side*.98,.39),(sign*2.43,side*.75,.15)],.019,'black',8)
            m.box('sand_pipe_anchor',(sign*2.68,side*1.20,.82),(.08,.09,.06))
    return m


def new_parts(b,end,inner_x):
    m=Batch(b)
    for side in (-1,1):
        def p(u,y,z):return (end*(-inner_x+u),side*y,z)
        outline=[(-.295,.790),(-.168,.650),(.168,.650),(.295,.790),(.295,1.095),(-.295,1.095)]
        shape=[(end*(-inner_x+u),z) for u,z in outline]
        m.profile('sand39_hopper_case',shape,side*1.34,.25,'graphite')
        # Keep the photo-fit shaped front removable lid, without pretending
        # that the old generic electrical lead identifies the subsystem.
        m.profile('sand39_shaped_front_lid',shape,side*1.475,.021,'spring_steel')
        inset=[(end*(-inner_x+u*.953),.680+(z-.680)*.952) for u,z in outline]
        m.profile('sand39_lid_field',inset,side*1.491,.014,'graphite')
        for u in (-.177,.177):
            m.box('sand39_existing_mount',p(u,1.267,1.128),(.05,.26,.10),'graphite',.007)
        m.box('sand39_filler_seal',p(0,1.34,1.098),(.37,.204,.010),'black',.012)
        m.box('sand39_filler_lid',p(0,1.34,1.110),(.39,.218,.018),'graphite',.015)
        # A small seated hinge and latch; no floating labels or oversized cap.
        m.cyl('sand39_filler_hinge',p(-.17,1.34,1.118),.012,.145,'spring_steel','Y',10 if b.lod==0 else 6)
        m.box('sand39_filler_latch',p(.155,1.34,1.125),(.056,.040,.018),'spring_steel',.005)
        if b.lod==0:
            for u in (-.230,.230):
                m.cyl('sand39_lid_fastener',p(u,1.508,1.046),.011,.010,'metal',segments=6)
        m.cyl('sand39_hopper_neck',p(0,1.34,.630),.044,.065,'graphite','Z',12 if b.lod==0 else 8)
        m.cyl('sand39_metering_collar',p(0,1.34,.597),.048,.027,'cast_steel','Z',12 if b.lod==0 else 8)
        # All coordinates stay in the bogie frame: no carbody-to-bogie cable.
        # Nozzle stops ahead of the inboard wheel, near the existing rail line.
        path=[p(0,1.34,.592),p(-.040,1.32,.525),p(-.120,1.12,.355),
              (-end*2.49,side*.83,.205),(-end*2.43,side*.75,.150)]
        m.tube('sand39_delivery_pipe',path,.020,'black',8 if b.lod==0 else 6)
        m.cyl('sand39_outlet_clamp',p(0,1.34,.578),.027,.024,'spring_steel','Z',10 if b.lod==0 else 6)
        m.box('sand39_pipe_clip',p(-.040,1.318,.525),(.063,.049,.049),'graphite',.006)
    return m


def replace(obj,b,end,jw):
    old=obj.data
    inner_x=float(obj['equipment21_inboard_x']);cab_x=float(obj['equipment21_cab_x'])
    prior=old_parts(b,end,cab_x,inner_x)
    keys=Counter(_key([prior.v[i] for i in f]) for f in prior.f)
    kept=[];removed=[]
    for f in old.polygons:
        key=_key([old.vertices[i].co for i in f.vertices])
        if keys[key]:keys[key]-=1;removed.append(f.index)
        else:kept.append(f)
    assert not sum(keys.values()),('inner sandbox exact source face lookup failed',obj.name,sum(keys.values()))
    batch=new_parts(b,end,inner_x)
    temp=batch.finish('_sand39_new_only',None);new=temp.data
    oldnorm=[tuple(n.vector) for n in old.corner_normals]
    newnorm=[tuple(n.vector) for n in new.corner_normals]
    # Keep all old vertex indices stable; only the explicitly selected old
    # polygons are removed. This also leaves historical axle role ranges valid
    # for vertex-based inspection (polygon roles are recorded as historical).
    n=len(old.vertices)
    verts=[tuple(v.co) for v in old.vertices]+[tuple(v.co) for v in new.vertices]
    faces=[tuple(f.vertices) for f in kept]+[tuple(n+i for i in f.vertices) for f in new.polygons]
    mesh=bpy.data.meshes.new(obj.name+'_sand39');mesh.from_pydata(verts,[],faces)
    mats=list(old.materials);indices=[]
    mapping={'graphite':'jw_frame','spring_steel':'jw_frame','cast_steel':'jw_spring'} if jw else {}
    for mat in new.materials:
        key=Path(mat.name).name;actual=b.mat(mapping.get(key,key))
        if actual not in mats:mats.append(actual)
        indices.append(mats.index(actual))
    for mat in mats:mesh.materials.append(mat)
    vals=[(f.material_index,f.use_smooth) for f in kept]+[(indices[f.material_index],f.use_smooth) for f in new.polygons]
    for f,(mi,smooth) in zip(mesh.polygons,vals):f.material_index=mi;f.use_smooth=smooth
    oldloops=[i for f in kept for i in f.loop_indices]
    for layer in old.uv_layers:
        dest=mesh.uv_layers.new(name=layer.name)
        for i,j in enumerate(oldloops):dest.data[i].uv=layer.data[j].uv
        for loop in list(mesh.loops)[len(oldloops):]:
            co=mesh.vertices[loop.vertex_index].co;dest.data[loop.index].uv=(co.x*.071+.5,co.z*.14+co.y*.03)
    mesh.update();mesh.normals_split_custom_set([oldnorm[i] for i in oldloops]+newnorm)
    obj.data=mesh;bpy.data.objects.remove(temp,do_unlink=True)
    obj['sandbox39_inboard_only']=True;obj['sandbox39_count']=2
    obj['sandbox39_estimated_details']='Lid/outlet/pipe photo-fit; inner-end ownership user-confirmed'
    obj['gear23_polygon_roles_historical']=True
    obj['sandbox39_new_vertex_start']=n
    return dict(name=obj.name,end=end,inner_local_x=-end*inner_x,world_x=obj.parent.location.x-end*inner_x,
                cases=2,removed_polygons=len(removed),new_components=dict(batch.counts),
                preserved_outer_case=True,minimum_nozzle_z=.130,attachment=obj.parent.name)


def apply(b,jw=False):
    if b.lod==2:return dict(lod=2,status='retained distant bogie proxy')
    out=[replace(bpy.data.objects[f'b{i}'],b,end,jw) for i,end in ((1,1),(2,-1))]
    bpy.context.view_layer.update();return dict(lod=b.lod,jinwen=jw,rows=out)
