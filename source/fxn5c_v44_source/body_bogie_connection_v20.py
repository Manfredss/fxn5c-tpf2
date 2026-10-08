"""Visible body/bogie linkage reconstruction, NOT a verified mechanical CAD model.

TrainNets yl04/09/10 and BV1W8FNzMEGd at 24.604/32.933 seconds.
Separate the body downstand, longitudinal member and transverse projecting arm.
The exporter assembles native dual-end skinning from these neutral meshes.
The shaft deforms; this is visual following, not rigid mechanical IK.
All hidden dimensions and the far-side mirror are explicitly estimates.
"""
import math
import bpy
from mathutils import Vector
from bogie_details_v20 import Batch

A_OFFSET = .54
B_OFFSET = -.70
PIVOT_OFFSET = -.84
LINK_Y = 1.54
LINK_Z = .70
HOLE_Z = 1.08
HOLE_RADIUS = .077


def anchors(center, side):
    end = 1 if center > 0 else -1
    return ((center+end*A_OFFSET, side*LINK_Y, LINK_Z),
            (center+end*B_OFFSET, side*LINK_Y, LINK_Z),
            (center+end*PIVOT_OFFSET, side*1.16, LINK_Z+.02))


def mark(obj, role, index, side, a, b, pivot):
    obj['connection_role'] = role
    obj['connection_bogie'] = index
    obj['connection_side'] = side
    obj['conn_anchor_A_world'] = list(a)
    obj['conn_anchor_B_world'] = list(b)
    obj['conn_pivot_world'] = list(pivot)
    obj['estimated_dimensions'] = True
    obj['connection_evidence'] = 'FXN5C yl04/09/10; BV1W8FNzMEGd 24.604s/32.933s'
    obj['dynamic_approximation'] = 'neutral editable component; exporter assembles dual-end visual skin, not rigid IK'
    if role == 'longitudinal_rod':
        obj['conn_rod_end_A_world'] = list(a)
        obj['conn_rod_end_B_world'] = list(b)


def cut_aperture(obj, x, side, lod):
    bpy.ops.mesh.primitive_cylinder_add(vertices=32 if lod==0 else 20,
        radius=HOLE_RADIUS, depth=.70, location=(x,side*1.51,HOLE_Z),
        rotation=(math.pi/2,0,0))
    cutter=bpy.context.object
    cutter.name='temporary_conn17_hole_cutter'
    cutter.data.materials.append(obj.data.materials[0])
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('conn17_actual_aperture','BOOLEAN')
    mod.operation='DIFFERENCE'; mod.solver='EXACT'; mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    obj['cut17_holes'] = int(obj.get('cut17_holes',0))+1


def body_bracket(builder, index, center, side, a, b, pivot):
    x=a[0]
    end=1 if center>0 else -1
    m=Batch(builder)
    # t increases toward the engine room. The real lower sill has an asymmetric
    # re-entrant shelf on that side of A; it is NOT a rectangular plate pasted
    # onto a uniform low skirt. One extruded outline avoids the old vertical
    # seams and offset face. Outer Y=1.610 meets the retained chassis sill.
    t0=-(2.84-A_OFFSET); t1=2.84+A_OFFSET
    lower=[(t0,1.260),(t0+.15,1.180),(-.220,1.180),
           (-.220,.885),(-.180,.845),(-.145,.825),(-.112,.640),
           (-.064,.615),(.064,.615),(.112,.640),(.150,.845),
           (.210,.875),(.245,1.015),(.305,1.045),(.660,1.045),
           (.720,1.070),(.770,1.120),(.780,1.180),
           (t1-.15,1.180),(t1,1.260)]
    outline=[(x-end*t,z) for t,z in [(t0,1.374),(t1,1.374)]+list(reversed(lower))]
    m.profile('body_downstand_plate',outline,side*1.575,.070,'graphite')
    m.counts['body_bogie_sill_lower_return']=1
    m.counts['asymmetric_inward_sill_shelf']=1
    # A shallow pressed reinforcement and small pin; no long separate paddle.
    reinforcement=[(-.144,.821),(.144,.821),(.103,.654),(.058,.632),
                   (-.058,.632),(-.103,.654)]
    m.profile('body_A_pressed_cheek',[(x-end*t,z) for t,z in reinforcement],
              side*1.614,.008,'spring_steel')
    m.cyl('body_A_outer_endplate',(x,side*1.621,LINK_Z),.073,.016,'cast_steel','Y',24)
    m.cyl('body_A_pin',(x,side*1.567,LINK_Z),.026,.150,'spring_steel','Y',12)
    m.box('body_A_lock_plate',(x,side*1.637,LINK_Z-.022),(.069,.008,.021),'spring_steel',.003)
    m.cyl('body_A_pin_head',(x,side*1.643,LINK_Z),.022,.012,'metal','Y',6)
    name=f'conn17_body_A_b{index}_s{"p" if side>0 else "m"}'
    obj=m.finish(name,None)
    cut_aperture(obj,x,side,builder.lod)
    rim=Batch(builder)
    rim.annulus('body_aperture_lip',(x,side*1.617,HOLE_Z),HOLE_RADIUS,.098,.014,
                0,math.tau,'spring_steel',32 if builder.lod==0 else 20)
    ring=rim.finish('conn17_temporary_ring',None)
    # Join only this bracket and its aperture lip, retaining the semantic object.
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True); ring.select_set(True); bpy.context.view_layer.objects.active=obj
    bpy.ops.object.join()
    mark(obj,'body_bracket',index,side,a,b,pivot)
    obj['conn_aperture_center_world']=[x,side*1.617,HOLE_Z]
    obj['conn_aperture_radius']=HOLE_RADIUS
    obj['conn19_inward_shelf']=True
    obj['conn19_contour_basis']='yl10/yl04 wheel-circle normalized side projection; heights estimated'
    obj['component_body_aperture_lip']=1
    return obj


def longitudinal_member(builder,index,side,a,b,pivot):
    m=Batch(builder)
    va,vb=Vector(a),Vector(b)
    direction=(vb-va).normalized(); length=(vb-va).length
    # A turned nonuniform section, no claim that it is a telescoping cylinder.
    stations=[(.045,.032),(.16,.032),(.205,.041),(.27,.052),
              (.91,.052),(1.02,.059),(1.095,.059),(length-.068,.044)]
    n=24 if builder.lod==0 else 12
    u=Vector((0,1,0)); v=direction.cross(u).normalized()
    verts=[]
    for dist,r in stations:
        c=va+direction*dist
        verts.extend(tuple(c+r*(math.cos(j*math.tau/n)*u+math.sin(j*math.tau/n)*v)) for j in range(n))
    faces=[(k*n+j,k*n+(j+1)%n,(k+1)*n+(j+1)%n,(k+1)*n+j)
           for k in range(len(stations)-1) for j in range(n)]
    smooth=[True]*len(faces)
    faces += [tuple(range(n-1,-1,-1)),tuple((len(stations)-1)*n+j for j in range(n))]
    m.add('longitudinal_round_member',verts,faces,'cast_steel',smooth+[False,False])
    m.cyl('rod_A_eye',a,.074,.061,'cast_steel','Y',24 if builder.lod==0 else 12)
    # Orthogonal B-eye silhouette observed at the projecting arm, not a second
    # large vertical drum on the same longitudinal frame beam.
    m.cyl('rod_B_eye',b,.106,.046,'cast_steel','Z',24 if builder.lod==0 else 12)
    m.tube('rod_B_neck',[tuple(vb-direction*.12),b],.045,'cast_steel',n)
    name=f'conn17_rod_b{index}_s{"p" if side>0 else "m"}'
    obj=m.finish(name,None)
    mark(obj,'longitudinal_rod',index,side,a,b,pivot)
    return obj


def projecting_arm(builder,index,center,side,a,b,pivot):
    end=1 if center>0 else -1
    m=Batch(builder)
    # World anchors are documented; mesh vertices here belong to bN_grp.
    bx=b[0]-center; px=pivot[0]-center
    plan=[(px-.143,side*1.105),(px+.143,side*1.105),
          (bx+.094,side*1.35),(bx+.115,side*1.525),
          (bx-.115,side*1.565),(bx-.094,side*1.35)]
    dz=LINK_Z-1.02
    verts=[(x,y,z+dz) for z in (.923,1.000) for x,y in plan]
    count=len(plan)
    faces=[tuple(range(count-1,-1,-1)),tuple(range(count,2*count))]
    faces += [(i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count)]
    m.add('transverse_projecting_cast_arm',verts,faces,'cast_steel')
    m.cyl('arm_frame_pivot',(px,side*1.16,1.042+dz),.137,.198,'cast_steel','Z',24)
    # Keep the upper mount at the unchanged frame while lowering the arm.
    m.box('arm_frame_mount',(px,side*1.16,1.201+dz+.05),(.31,.29,.302),'graphite',.023)
    m.cyl('arm_frame_pivot_cap',(px,side*1.16,1.146+dz),.142,.023,'spring_steel','Z',24)
    m.cyl('arm_B_lower_seat',(bx,side*LINK_Y,.973+dz),.127,.036,'cast_steel','Z',24)
    m.cyl('arm_B_lower_interface',(bx,side*LINK_Y,.993+dz),.110,.006,'black','Z',24)
    m.cyl('arm_B_upper_interface',(bx,side*LINK_Y,1.046+dz),.110,.006,'black','Z',24)
    m.cyl('arm_B_upper_cap',(bx,side*LINK_Y,1.065+dz),.130,.032,'spring_steel','Z',24)
    m.cyl('arm_B_pin',(bx,side*LINK_Y,1.026+dz),.022,.145,'spring_steel','Z',12)
    if builder.lod==0:
        m.cyl('arm_B_pin_head',(bx,side*LINK_Y,1.111+dz),.031,.018,'metal','Z',6)
        m.cyl('arm_pivot_pin_head',(px,side*1.16,1.181+dz),.035,.020,'metal','Z',6)
    obj=m.finish(f'conn17_arm_B_b{index}_s{"p" if side>0 else "m"}',bpy.data.objects[f'b{index}_grp'])
    mark(obj,'bogie_arm',index,side,a,b,pivot)
    return obj


def apply(builder):
    if builder.lod>=2:
        return
    assert not any(o.get('connection_role') for o in bpy.context.scene.objects),'connection pass applied twice'
    # Replace the old pasted black lifting discs. The corrected aperture moves
    # with the downstand, towards the cab, rather than staying over the axle.
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('lifting_recess','lifting_rim','lifting_hole')):
            bpy.data.objects.remove(obj,do_unlink=True)
    sill=bpy.data.objects.get('chassis_sill')
    assert sill is not None,'expected preserved chassis sill'
    for index,center in enumerate(builder.g.BOGIE_CENTERS,1):
        for side in (-1,1):
            a,b,pivot=anchors(center,side)
            body_bracket(builder,index,center,side,a,b,pivot)
            # New hole lies below the original continuous sill; do not leave
            # the v17 high hole in that band or cut a second fictitious hole.
            longitudinal_member(builder,index,side,a,b,pivot)
            projecting_arm(builder,index,center,side,a,b,pivot)
    bpy.context.scene['connection17_components']=12
    bpy.context.scene['connection17_native_motion']='v19 exporter assembles native two-end skin follow; shaft deforms; game test pending'
    bpy.context.view_layer.update()
    builder.g.ensure_uvs()
