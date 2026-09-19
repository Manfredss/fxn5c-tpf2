"""Independent geometric axle alignment and attachment tests for v23.

The axes are measured from real mesh coordinates, not scene counters. Source
part ranges only select polygons; native callers must separately compare the
emitted triangle/material surface with the audited source/readback geometry.
Connectivity is bounded to the corrected bearing/suspension parts and v22
fittings. It is not a certification of every concealed locomotive subsystem.
"""
from collections import Counter
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def require(ok,message):
    if not ok:raise AssertionError(message)


def _geometry(obj,faces):
    ids=sorted({i for f in faces for i in f.vertices});index={v:i for i,v in enumerate(ids)}
    points=[obj.data.vertices[i].co.copy() for i in ids]
    polygons=[tuple(index[i] for i in p.vertices) for p in faces]
    return {'points':points,'polygons':polygons,
            'bounds':[(min(p[k] for p in points),max(p[k] for p in points)) for k in range(3)],
            'tree':BVHTree.FromPolygons(points,polygons,all_triangles=False,epsilon=2e-6)}


def _parts(obj,property_name):
    rows=[]
    for row in json.loads(obj[property_name]):
        start=row['polygon_start'];stop=start+row['polygon_count']
        rows.append(dict(role=row['role'],**_geometry(obj,list(obj.data.polygons)[start:stop])))
    return rows


def _mid(row):return tuple((a+b)*.5 for a,b in row['bounds'])


def _touch(a,b):
    if any(aa[1]<bb[0]-2e-6 or bb[1]<aa[0]-2e-6 for aa,bb in zip(a['bounds'],b['bounds'])):return False
    if a['tree'].overlap(b['tree']):return True
    # Nested closed mechanical solids also attach without intersecting their
    # outer surfaces. Ray-parity check several genuine vertices, not AABBs.
    direction=Vector((.91231,.33459,.23617)).normalized()
    for left,right in ((a,b),(b,a)):
        for point in left['points'][::max(1,len(left['points'])//8)]:
            nearest=right['tree'].find_nearest(point)
            if nearest[0] is not None and nearest[3]<2e-6:return True
            origin=point.copy();hits=0
            for _ in range(100):
                hit,normal,index,distance=right['tree'].ray_cast(origin,direction,20)
                if hit is None:break
                hits+=1;origin=hit+direction*1e-5
            if hits%2:return True
    return False


def audit_scene(lod=0,strict_support=True):
    results=[]
    for index in (1,2):
        frame=bpy.data.objects[f'b{index}'];parent=frame.parent
        require(parent is not None,('missing actual bogie parent',index))
        parts=_parts(frame,'gear23_axle_roles')
        sleeve=bpy.data.objects.get(f'bogie22_details_b{index}') or frame
        parts+=_parts(sleeve,'gear23_sleeve_roles')
        if sleeve.get('bogie22_roles_json'):
            for row in json.loads(sleeve['bogie22_roles_json']):
                if row['role'].startswith('damper_'):continue
                start=row['first_polygon'];stop=start+row['polygon_count']
                parts.append(dict(role=row['role'],**_geometry(sleeve,list(sleeve.data.polygons)[start:stop])))
        # Actual wheelset running circle midpoint is .625. No radius inferred
        # from the bearing recipe, and no object label alone can pass this.
        wheel_axes=[]
        for ordinal,x in enumerate((1.8,0,-1.8),1):
            wheel=bpy.data.objects[f'w{(index-1)*3+ordinal}']
            transform=parent.matrix_world.inverted()@wheel.matrix_world
            used={i for p in wheel.data.polygons for i in p.vertices}
            points=[transform@wheel.data.vertices[i].co for i in used]
            axis_x=(min(p.x for p in points)+max(p.x for p in points))/2
            axis_z=(min(p.z for p in points)+max(p.z for p in points))/2
            require(abs(axis_x-x)<2e-6 and abs(axis_z-.625)<2e-6,('wheel axis changed',index,ordinal,axis_x,axis_z))
            wheel_axes.append((axis_x,axis_z))
        covers=[p for p in parts if p['role']=='axlebox_cover']
        inner=[p for p in parts if p['role']=='coaxial_inner_bearing']
        require(len(covers)==4 and len(inner)==6,('bearing inventory',index))
        measured=[]
        for part in covers+inner:
            x,y,z=_mid(part);axis=min(wheel_axes,key=lambda v:abs(v[0]-x))
            error=math.hypot(x-axis[0],z-axis[1]);require(error<2e-6,('bearing not coaxial',index,part['role'],x,z,error))
            # Cylinder end rings must have equal radial distance in X/Z and
            # be parallel to actual axle Y, rather than merely a matching box.
            radii=[math.hypot(p.x-x,p.z-z) for p in part['points']]
            require(max(radii)-min(radii)<2e-6,('bearing not an axle-axis cylinder',index,part['role']))
            measured.append({'role':part['role'],'x':x,'y':y,'z':z,'axis_error_m':error})
        # The retained upper frame is a spatial root. Select its real beam
        # polygons at |Y| 1.015..1.265; do not use the entire batched object as
        # one arbitrary connected root (it contains separate small details).
        root_faces=[]; corrected_faces=set()
        for prop in frame.keys():
            if prop.startswith('gear23_') and prop.endswith('_roles'):
                for row in json.loads(frame[prop]):
                    corrected_faces.update(range(row['polygon_start'],row['polygon_start']+row['polygon_count']))
        for p in frame.data.polygons:
            if p.index in corrected_faces:continue
            points=[frame.data.vertices[i].co for i in p.vertices]
            if all(1.010<abs(v.y)<1.310 and 1.03<v.z<1.1951 for v in points):root_faces.append(p)
        require(len(root_faces)>50,('missing retained root beam',index))
        roots=[dict(role='retained_upper_frame',**_geometry(frame,root_faces))]
        # Axle sleeves have real overlap with the independently positioned
        # wheel axles, so wheel axles are a second legitimate bearing root.
        for ordinal in range(1,4):
            wheel=bpy.data.objects[f'w{(index-1)*3+ordinal}']
            transform=parent.matrix_world.inverted()@wheel.matrix_world
            used={i for p in wheel.data.polygons for i in p.vertices}
            points=[transform@wheel.data.vertices[i].co for i in used]
            # Cylinder axle runs to |Y|1.08, well outside wheel disc |Y|.86.
            ids=[p for p in points if .90<abs(p.y)<1.09]
            require(ids,('missing true axle endpoints',index,ordinal))
        vertices=[p for row in parts for p in row['points']]
        reached=set(); queue=[]
        for i,part in enumerate(parts):
            if any(_touch(part,root) for root in roots):reached.add(i);queue.append(i)
        while queue:
            i=queue.pop()
            for j,other in enumerate(parts):
                if j not in reached and _touch(parts[i],other):reached.add(j);queue.append(j)
        detached=[{'role':part['role'],'centre':_mid(part)} for i,part in enumerate(parts) if i not in reached]
        if strict_support:require(not detached,('unsupported corrected components',index,detached))
        results.append({'bogie':index,'wheel_axes':wheel_axes,'bearings':measured,
                        'corrected_component_solids':len(parts),'frame_connected_solids':len(reached),
                        'detached':detached,'method':'triangle intersection or closed-solid ray parity; 2 micron contact tolerance'})
    return {'status':'PASS' if all(not r['detached'] for r in results) else 'FAIL','lod':lod,'bogies':results,
            'scope':'corrected bearing/carrier/spring/guide/damper and v22 auxiliary solids; no complete-vehicle mechanical certification'}


def negative_controls(lod=0):
    """Reject a displaced cover, a floating case plate and a moved wheel."""
    trials=[]
    frame=bpy.data.objects['b1']
    cover=next(r for r in json.loads(frame['gear23_axle_roles']) if r['role']=='axlebox_cover')
    auxiliary=bpy.data.objects.get('bogie22_details_b1') or frame
    plate=next(r for r in json.loads(auxiliary['gear23_auxiliary_roles']) if r['role']=='auxiliary_lid_field')
    for name,obj,row,axis,shift in (('cover_axis_offset',frame,cover,2,.015),
        ('floating_auxiliary_lid',auxiliary,plate,1,-.10),
        ('wheel_axis_offset',bpy.data.objects['w1'],None,2,.015)):
        faces=list(obj.data.polygons) if row is None else list(obj.data.polygons)[row['polygon_start']:row['polygon_start']+row['polygon_count']]
        ids=sorted({i for p in faces for i in p.vertices})
        old={i:obj.data.vertices[i].co.copy() for i in ids}
        try:
            delta=Vector((0,0,0));delta[axis]=shift
            if row is None:
                # Saved wheel meshes inherit primitive orientation. Offset
                # in actual bogie Z, not arbitrarily in mesh-local Z (which
                # is the axle direction for the saved cylinder object).
                delta=(frame.parent.matrix_world.inverted()@obj.matrix_world).to_3x3().inverted()@delta
            for i in ids:obj.data.vertices[i].co+=delta
            obj.data.update()
            try:audit_scene(lod)
            except AssertionError:trials.append(name)
            else:raise AssertionError('negative control escaped: '+name)
        finally:
            for i,co in old.items():obj.data.vertices[i].co=co
            obj.data.update()
    return trials


def audit_readback_axes(lod=0):
    """Measure exported/readback meshes without recipe tags or role ranges.

    Fit circles to the real bearing end rings, then compare them with the
    emitted wheel surfaces in each actual bogie coordinate frame. This can
    run directly after render_native.load_native(..., lod_index=lod).
    """
    import numpy as np
    rows=[]
    for index in (1,2):
        frame=bpy.data.objects[f'b{index}'];group=bpy.data.objects[f'b{index}_grp']
        transform=group.matrix_world.inverted()@frame.matrix_world
        used={i for p in frame.data.polygons for i in p.vertices}
        points=np.asarray([tuple(transform@frame.data.vertices[i].co) for i in used])
        for ordinal,x in enumerate((1.8,0,-1.8),1):
            wheel=bpy.data.objects[f'w{(index-1)*3+ordinal}']
            wt=group.matrix_world.inverted()@wheel.matrix_world
            used={i for p in wheel.data.polygons for i in p.vertices}
            wp=np.asarray([tuple(wt@wheel.data.vertices[i].co) for i in used])
            axis=(wp[:,[0,2]].min(axis=0)+wp[:,[0,2]].max(axis=0))*.5
            require(np.max(np.abs(axis-np.array([x,.625])))<2e-6,('native wheel axis',index,ordinal,axis.tolist()))
            for side in (-1,1):
                roles=[('inner_bearing',1.210,.102)]
                if abs(x)>.01:roles.append(('outer_cover',1.355,.086))
                for role,y,radius in roles:
                    p=points[(np.abs(points[:,1]-side*y)<2e-6)&(np.abs(points[:,0]-x)<radius+.001)&
                             (points[:,2]>.35)&(points[:,2]<.86)][:,[0,2]]
                    p=np.unique(np.round(p,7),axis=0)
                    require(len(p)>=10,('missing native bearing end ring',index,x,side,role,len(p)))
                    # x²+z² = 2cx*x + 2cz*z + r²-cx²-cz²
                    a=np.column_stack((2*p[:,0],2*p[:,1],np.ones(len(p))))
                    fit=np.linalg.lstsq(a,np.einsum('ij,ij->i',p,p),rcond=None)[0]
                    centre=fit[:2];measured=np.sqrt(fit[2]+np.dot(centre,centre))
                    residual=np.max(np.abs(np.linalg.norm(p-centre,axis=1)-measured))
                    require(residual<2e-6 and abs(measured-radius)<2e-6,('native ring not circular',index,role,residual,measured))
                    error=np.linalg.norm(centre-axis)
                    require(error<2e-6,('native bearing/wheel misalignment',index,x,side,role,float(error)))
                    rows.append({'bogie':index,'axle':ordinal,'side':side,'role':role,
                                 'fitted_centre_xz':centre.tolist(),'wheel_axis_xz':axis.tolist(),
                                 'alignment_error_m':float(error),'circle_residual_m':float(residual)})
    return {'status':'PASS','lod':lod,'rings':rows,'method':'tag-free least-squares circle fitting of referenced emitted vertices'}


if __name__=='__main__':
    ROOT=Path(__file__).resolve().parent
    results=[]
    for style in ('fxn5c','fxn5c_jinwen'):
        source=ROOT/f'gear23_{style}_probe.blend'
        bpy.ops.wm.open_mainfile(filepath=str(source))
        result=audit_scene(strict_support=False);result['style']=style
        print('GEAR23_AUDIT',json.dumps(result),flush=True);results.append(result)
    (ROOT/'gear23_probe_audit.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
