"""Photo/drawing fitted continuous prototype windshield rake and cab seam.

The immutable v42 source is the input. Geometry is remapped in world space;
original object transforms, UVs, material slots and light metadata stay intact.
All dimensions below are visual estimates rather than manufacturer CAD.
"""
import bpy,math
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
import prototype_head_v41 as old
from glazing_revision_v42 import _rewrite
from livery_revision_v21 import _split_attributes

STYLE='fxn5c_prototype_0001'
PREFIX='profile43_'
Z0=2.62
Z1=4.705
X0=old.front_x(Z0)
X1=10.44
SLOPE=(X0-X1)/(Z1-Z0)
SEAM_WIDTH=.012
SEAM_OFFSET=.0012
CHEEK_SETBACK=.25
FRONT_PREFIX=('proto41_head_front_skin','proto41_head_wide_corner','proto41_head_brow',
 'proto41_windscreen','proto41_front_window_proxy','proto41_horn','proto41_top_',
 'proto41_upper_reflector','horn39_','glazing_proto41_front','glazing_proto41_top_cover',
 'glass42_','parked_wiper','wiper_drive','wiper_pull','wiper_service','surround_recessed_screw',
 'front_sun_visor','sunblind_roller')
BLEND_PREFIX=('proto41_head_side_skin','roof24_front_folded_canopy')


def front_x(z):
    return old.front_x(z) if z<=Z0 else X0-SLOPE*(z-Z0)


def surface_x(y,z):
    if z<=Z0:return abs(old.point(1,y,z)[0])
    t=max(0,min(1,(abs(y)-old.FRONT_HALF)/.4))
    q=max(0,min(1,(z-Z0)/(3.95-Z0)))
    setback=t*(old.corner_setback(Z0)+(CHEEK_SETBACK-old.corner_setback(Z0))*q)
    return front_x(z)-setback


def _points(o):return [o.matrix_world@v.co for v in o.data.vertices]


def selected_objects(style=STYLE):
    if style!=STYLE:return []
    result=[]
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        if o.name.startswith(PREFIX):result.append(o);continue
        if o.name.startswith(FRONT_PREFIX+BLEND_PREFIX) or o.name in ('light24_fwd','light24_bwd'):
            if max(p.z for p in _points(o))>Z0+1e-5:result.append(o)
    return result


def _delta(p,blend=False):
    if p.z<=Z0:return 0.
    base=abs(old.point(1,p.y,p.z)[0])
    delta=surface_x(p.y,p.z)-base
    if blend:
        # Only the front edge of the side skin/canopy moves. The existing
        # side-glass holes, door edge and rear canopy seam remain exact.
        depth=abs(p.x)-base
        delta*=max(0,min(1,(depth+.18)/.10))
    return delta


def _shift_mesh(o,lod):
    blend=o.name.startswith(BLEND_PREFIX)
    canopy=o.name.startswith('roof24_front_folded_canopy')
    if canopy:
        samples=sorted(set((round(v.z,6),round(abs(v.x),6))for v in _points(o)if abs(v.x)>9.2))
        def original_canopy_front(z):
            for(a,x),(b,y)in zip(samples,samples[1:]):
                if z<=b+1e-6:return x+(y-x)*(z-a)/(b-a)
            return samples[-1][1]
    if (o.name.startswith('proto41_head_brow') and not o.name.startswith('proto41_head_brow_wing')) or canopy:
        # Preserve a true planar central brow at distance as well. Without
        # these crease cuts, the coarse six-sided face triangulates across
        # independently displaced cheek vertices and sags inside the plane.
        _rewrite(o,[lambda q:q[1]-old.FRONT_HALF,lambda q:q[1]+old.FRONT_HALF],lambda pp:True)
    if o.name.startswith(('proto41_head_front_skin','proto41_head_wide_corner','proto41_head_side_skin')):
        _rewrite(o,[lambda p:p[2]-Z0],lambda pp:min(p.z for p in pp)<Z0-1e-7 and max(p.z for p in pp)>Z0+1e-7)
    normals=[n.vector.copy() for n in o.data.corner_normals];original_points=_points(o)
    inv=o.matrix_world.inverted();changed=set();maximum=0
    for v in o.data.vertices:
        p=o.matrix_world@v.co;d=_delta(p,blend)
        if canopy and abs(p.x)>9.18001:
            # The inherited canopy edge was not coincident with its wing:
            # -56 mm at the eave and +53 mm at the colour fold. Seat the
            # original front edge on the wing's true shared straight edge.
            if p.z<=4.28001:
                t=max(0,min(1,(p.z-3.95)/.33))
                wanted=(1-t)*surface_x(1.65,3.95)+t*surface_x(1.34,4.28)
            else:wanted=surface_x(old._brow_width(p.z),p.z)
            previous=original_canopy_front(p.z)
            weight=max(0,min(1,(abs(p.x)-9.18)/(previous-9.18)))
            d=(wanted-previous)*weight
        if abs(d)>1e-9:
            p.x+=(1 if p.x>0 else -1)*d;v.co=inv@p;changed.add(v.index);maximum=max(maximum,abs(d))
    o.data.update()
    for f in o.data.polygons:
        if any(i in changed for i in f.vertices):
            # The affine/sheared surface geometry supplies the new normals;
            # unmodified corners (including every lower lamp) stay exact.
            for li in f.loop_indices:
                if f.use_smooth:
                    point=original_points[o.data.loops[li].vertex_index];gradient=[]
                    for axis in range(3):
                        a=point.copy();c=point.copy();a[axis]-=1e-5;c[axis]+=1e-5
                        gradient.append(((1 if c.x>0 else -1)*_delta(c,blend)-(1 if a.x>0 else -1)*_delta(a,blend))/2e-5)
                    jac=Matrix(((1+gradient[0],gradient[1],gradient[2]),(0,1,0),(0,0,1)))
                    world_normal=o.matrix_world.to_3x3().inverted().transposed()@normals[li]
                    normals[li]=(o.matrix_world.to_3x3().transposed()@jac.inverted().transposed()@world_normal).normalized()
                else:normals[li]=f.normal.copy()
    o.data.normals_split_custom_set(normals)
    return dict(name=o.name,vertices_moved=len(changed),max_abs_x_change=maximum)


def _mesh(builder,name,verts,faces,role):
    obj=builder.poly(name,verts,faces,'black')
    obj['profile43_role']=role;obj['profile43_width_m']=SEAM_WIDTH;obj['profile43_offset_m']=SEAM_OFFSET
    uv=obj.data.uv_layers.new(name='UVMap')
    for li in obj.data.loops:
        p=obj.data.vertices[li.vertex_index].co;uv.data[li.index].uv=((p.x+p.y)/5,p.z/5)
    return obj


def _front_seam(builder,end):
    """Copy only the narrow exposed surface band, including actual returns."""
    verts=[];faces=[]
    sources=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith(
        ('proto41_head_front_skin','proto41_head_wide_corner','glass42_recess_panel','glass42_bay_returns','glass42_far_panel','glass42_far_proto_returns'))]
    for o in sources:
        pp=_points(o)
        if max(p.x*end for p in pp)<10:continue
        normal_matrix=o.matrix_world.to_3x3().inverted().transposed()
        for f in o.data.polygons:
            n=(normal_matrix@f.normal).normalized()
            is_return=o.name.startswith(('glass42_bay_returns','glass42_far_proto_returns'))
            if n.x*end<.2 and not is_return:continue
            poly=[tuple(pp[i]) for i in f.vertices]
            if min(p[2] for p in poly)>Z0+SEAM_WIDTH/2 or max(p[2] for p in poly)<Z0-SEAM_WIDTH/2:continue
            pieces=[poly]
            for z in (Z0-SEAM_WIDTH/2,Z0+SEAM_WIDTH/2):
                pieces=[q for p in pieces for q in _split_attributes(p,lambda v,z=z:v[2]-z)]
            for p in pieces:
                cz=sum(v[2] for v in p)/len(p)
                if not Z0-SEAM_WIDTH/2-1e-7<=cz<=Z0+SEAM_WIDTH/2+1e-7:continue
                first=len(verts);verts.extend(tuple(Vector(v)+n*SEAM_OFFSET) for v in p)
                faces.append(tuple(range(first,len(verts))))
    assert faces,('front seam empty',end)
    return _mesh(builder,f'{PREFIX}front_seam_{end:+d}',verts,faces,'thin_surface_front_seam')


def _surface_tree():
    sources=[o for o in bpy.context.scene.objects if o.type=='MESH' and (o.name=='body_open_shell_v07' or
             o.name.startswith(('proto41_head_side_skin','proto41_head_wide_corner','proto41_head_shoulder_connection','roof24_front_folded_canopy')))]
    verts=[];faces=[]
    for o in sources:
        off=len(verts);verts.extend(_points(o));faces.extend(tuple(off+i for i in f.vertices) for f in o.data.polygons)
    return BVHTree.FromPolygons(verts,faces)


def _side_path(lod):
    pts=[Vector((9.08,Z0))]
    a,b,c=Vector((9.08,Z0)),Vector((8.84,Z0)),Vector((8.69,2.90))
    n=8 if lod==0 else 5 if lod==1 else 3
    pts += [(1-t)**2*a+2*(1-t)*t*b+t*t*c for t in [i/n for i in range(1,n+1)]]
    pts += [Vector((8.30,3.85)),Vector((8.28,3.922))]
    return pts


def _side_seam(builder,end,side,tree):
    path=_side_path(builder.lod);vertices=[];faces=[];mount_errors=[]
    for i,p in enumerate(path):
        t0=(p-path[i-1]).normalized() if i else (path[1]-p).normalized()
        t1=(path[i+1]-p).normalized() if i+1<len(path) else t0
        n0,n1=Vector((-t0.y,t0.x)),Vector((-t1.y,t1.x))
        offset=(n0+n1)*(SEAM_WIDTH/2/max(1+n0.dot(n1),.1))
        for q in (p-offset,p+offset):
            hit,normal,face,dist=tree.ray_cast(Vector((end*q.x,side*2.0,q.y)),Vector((0,-side,0)),.8)
            assert hit is not None,('side seam missing supporting skin',end,side,tuple(q))
            if normal.y*side<0:normal=-normal
            vertices.append(tuple(hit+normal*SEAM_OFFSET));mount_errors.append(SEAM_OFFSET)
        if i:faces.append((2*i-2,2*i-1,2*i+1,2*i))
    # Copy the long horizontal part from its actual side polygons. A single
    # ray-fitted chord from the bevel to the flat wall sinks into that wall.
    for o in bpy.context.scene.objects:
        if o.type!='MESH' or not o.name.startswith('proto41_head_side_skin'):continue
        pp=_points(o)
        if max(v.x*end for v in pp)<9 or max(v.y*side for v in pp)<1.6:continue
        nm=o.matrix_world.to_3x3().inverted().transposed()
        for f in o.data.polygons:
            normal=(nm@f.normal).normalized()
            if normal.y*side<.8:continue
            pieces=[[tuple(pp[i]) for i in f.vertices]]
            for plane in (lambda v:v[2]-Z0+SEAM_WIDTH/2,lambda v:v[2]-Z0-SEAM_WIDTH/2,lambda v:end*v[0]-9.08):
                pieces=[q for poly in pieces for q in _split_attributes(poly,plane)]
            for poly in pieces:
                center=sum((Vector(v)for v in poly),Vector())/len(poly)
                if center.x*end<9.08-1e-7 or not Z0-SEAM_WIDTH/2-1e-7<=center.z<=Z0+SEAM_WIDTH/2+1e-7:continue
                off=len(vertices);vertices.extend(tuple(Vector(v)+normal*SEAM_OFFSET)for v in poly)
                faces.append(tuple(range(off,len(vertices))))
    obj=_mesh(builder,f'{PREFIX}side_seam_{end:+d}_{side:+d}',vertices,faces,'thin_surface_cab_seam')
    obj['profile43_end']=end;obj['profile43_side']=side
    return obj


def apply(builder,style=STYLE):
    if style!=STYLE:return dict(status='NOT_APPLICABLE',style=style)
    assert not bpy.context.scene.get('profile43_done'),'apply only once to immutable v42 baseline'
    before=selected_objects(style);changes=[_shift_mesh(o,builder.lod) for o in before]
    bpy.context.view_layer.update()
    tree=_surface_tree()
    for end in (-1,1):
        _front_seam(builder,end)
        for side in (-1,1):_side_seam(builder,end,side,tree)
    bpy.context.view_layer.update();bpy.context.scene['profile43_done']=True
    return dict(status='PASS',lod=builder.lod,style=style,changes=changes,
                selected_before=[o.name for o in before],selected_after=[o.name for o in selected_objects(style)],
                straight_profile=dict(z0=Z0,x0=X0,z1=Z1,x1=X1,slope=SLOPE),
                pane_recess_preserved=True,transforms_and_light_metadata_unchanged=True,
                seam_width_m=SEAM_WIDTH,seam_offset_m=SEAM_OFFSET,photo_fitted_not_oem=True)
