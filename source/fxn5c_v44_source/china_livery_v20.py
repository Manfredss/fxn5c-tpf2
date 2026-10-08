"""Reprojected CR blue/cyan/gold paint on actual folded body polygons.

Control curves are photo estimates, not a dimensional livery drawing. Existing
holes and sheet locations are retained; no opaque overlay crosses louvers.
"""
from pathlib import Path
import math
import bpy
import bmesh
from mathutils import Vector
from geometry_v05 import split_polygon, lerp_table
from lettering_v20 import side_titles

PAINT_KEYS=('blue','light_blue','yellow')


def control_bands(x):
    x=abs(x)
    # A shallow continuous arch, tapering to zero at both ends. The preceding
    # version used a higher segmented chevron with an exaggerated centre hump.
    if x<=8.35:
        arch=max(0,1-(x/8.35)**2)
        gold_low=1.655+.330*arch
        gold_high=gold_low+.148*arch**.55
    else:
        gold_low=gold_high=-10
    # Cyan climbs gently past the cab door, then steepens into the roof shoulder.
    table=((3.00,4.70,4.70),(3.80,4.09,4.32),(4.60,3.80,4.09),(5.60,3.48,3.78),
           (6.60,3.21,3.49),(7.60,3.00,3.235),(8.60,2.82,3.015),
           (9.60,2.665,2.825),(10.78,2.53,2.65))
    if x<3.00 or x>10.78:
        cyan_low=cyan_high=10
    else:
        cyan_low=lerp_table(x,[(a,b) for a,b,c in table])
        cyan_high=lerp_table(x,[(a,c) for a,b,c in table])
    return gold_low,gold_high,cyan_low,cyan_high


# Piecewise-linear clipping creates smooth-looking curves without distorting
# sheet metal. Include exact cyan/control endpoints and more points on the arch.
KNOTS=sorted(set([round(i*.35,6) for i in range(24)]+[3.00,3.80,4.60,5.60,6.60,7.60,8.35,8.60,9.60,10.78]))
TABLE=[(x,*control_bands(x)) for x in KNOTS]


def paint_bands(x):
    x=abs(x)
    return tuple(lerp_table(x,[(row[0],row[i+1]) for row in TABLE]) for i in range(4))


def paint_at(x,y,z):
    gold_lo,gold_hi,cyan_lo,cyan_hi=control_bands(x)
    if abs(y)<1.20 or abs(x)>10.78:
        return 'blue'
    if gold_lo<z<gold_hi:
        return 'yellow'
    if cyan_lo<z<cyan_hi:
        return 'light_blue'
    return 'blue'


def compact_distant_paint(mesh):
    """Remove coplanar clipping diagonals while retaining every color boundary."""
    bm=bmesh.new();bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
    bmesh.ops.dissolve_limit(bm,angle_limit=1e-5,verts=list(bm.verts),edges=list(bm.edges),
                           use_dissolve_boundaries=False,delimit={'MATERIAL','NORMAL'})
    bm.to_mesh(mesh);bm.free();mesh.update()


def repaint(obj,b):
    mesh=obj.data
    keys=[Path(m.name).name for m in mesh.materials]
    if not any(k in PAINT_KEYS for k in keys):
        return
    mesh.calc_loop_triangles()
    tf=obj.matrix_world.copy(); inv=tf.inverted()
    materials=list(mesh.materials)
    indices={m.name:i for i,m in enumerate(materials)}
    for key in PAINT_KEYS:
        material=b.mat(key)
        if material.name not in indices:
            indices[material.name]=len(materials); materials.append(material)
    material_indices={key:indices[b.mat(key).name] for key in PAINT_KEYS}
    vertices=[]; polygons=[]; face_materials=[]; smooth=[]
    for tri in mesh.loop_triangles:
        points=[tuple(tf@mesh.vertices[i].co) for i in tri.vertices]
        painted=keys[tri.material_index] in PAINT_KEYS
        # Longitudinal paint should not wrap onto the broad nose or interior.
        is_side=(max(abs(p[1]) for p in points)>1.20 and min(abs(p[0]) for p in points)<10.78
                 and min(p[2] for p in points)>=1.575)
        pieces=[points]
        if painted and is_side:
            lo=min(p[0] for p in points); hi=max(p[0] for p in points)
            knots=KNOTS if b.lod<2 else [0,3.00,3.80,4.60,6.60,8.35,8.60,9.60,10.78]
            for x in [0]+[sign*k for k in knots for sign in (-1,1) if k]:
                if lo<x<hi:
                    pieces=[q for p in pieces for q in split_polygon(p,lambda v,x=x:v[0]-x)]
            clipped=[]
            for piece in pieces:
                xx=sum(p[0] for p in piece)/len(piece)
                # Within a knot interval each band is a plane, so clipping is exact.
                local=[piece]
                for i in range(4):
                    if (i<2 and abs(xx)>8.35) or (i>=2 and not 3.00<=abs(xx)<=10.78):
                        continue
                    local=[q for p in local for q in split_polygon(p,lambda v,i=i:v[2]-paint_bands(v[0])[i])]
                clipped.extend(local)
            pieces=clipped
        for points in pieces:
            center=sum((Vector(p) for p in points),Vector())/len(points)
            key=paint_at(*center) if painted and is_side else None
            idx=material_indices[key] if key else tri.material_index
            start=len(vertices);vertices.extend(tuple(inv@Vector(p)) for p in points)
            polygons.append(tuple(range(start,len(vertices))))
            face_materials.append(idx);smooth.append(mesh.polygons[tri.polygon_index].use_smooth)
    result=bpy.data.meshes.new(mesh.name+'_CR19')
    result.from_pydata(vertices,[],polygons)
    for material in materials:result.materials.append(material)
    for face,idx,sm in zip(result.polygons,face_materials,smooth):
        face.material_index=idx;face.use_smooth=sm
    result.update()
    if b.lod==2:compact_distant_paint(result)
    obj.data=result
    obj['livery19_paint_split']=True


def apply(b):
    assert not bpy.context.scene.get('china19_applied'),'Apply once to a clean CR scene'
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('cyan_sweep','gold_sweep')):
            bpy.data.objects.remove(obj,do_unlink=True)
    for obj in list(bpy.context.scene.objects):
        if obj.type!='MESH' or obj.name.startswith(('bounds|','railway_emblem','side_fuxing',
                'side_number','cab_number','cab_depot','nose_fuxing','nose_number',
                'sill_warning','cock_coloured_lever',
                'central_plough_yellow','pilot_chevron','pilot_warning')):
            continue
        repaint(obj,b)
    side_titles(b)
    # Splitting a previously tagged sheet mesh replaces its custom loop-normal
    # datablock. Reapply explicit per-face normals on the new topology; retaining
    # the old object tag alone does not retain actual planar shading in Blender.
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals()
    b.g.ensure_uvs()
    bpy.context.scene['china19_applied']=True
    bpy.context.scene['livery19_evidence']='Photo-fit cyan curves, shallow gold arch, visible-metric STXinwei outline approximation'
    bpy.context.view_layer.update()
