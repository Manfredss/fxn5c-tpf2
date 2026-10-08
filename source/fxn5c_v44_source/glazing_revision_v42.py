"""Photo-fit recessed front window assembly, shared by three FXN5C styles.

Production corner/gray-panel boundaries are de-raked; prototype head facets
are retained. All original object transforms and independent glazing names
remain unchanged. Millimetre dimensions are visual estimates, not OEM data.
"""
import math
import bpy
from mathutils import Vector
from mathutils.geometry import delaunay_2d_cdt
from collections import Counter
from geometry_v07 import SilhouetteBuilder
from glazing_revision_v39 import rectangle_loop
from prototype_head_v41 import front_x as proto_x,_front_loop as proto_loop
from livery_revision_v21 import _split_attributes

PREFIX='glass42_'
PANES=('glazing_14','glazing_15','glazing_16','glazing_17')
DETAILS=('parked_wiper','wiper_drive','wiper_pull','wiper_service','surround_recessed_screw',
         'front_sun_visor','sunblind_roller')
PRODUCTION=('angular_glazing_reveal','angular_windscreen_bead','angular_windscreen_gasket',
            'angular_windshield_surround','straight_centre_mullion','mullion_metal_bead','distant_windows')
PROTOTYPE=('proto41_windscreen_reveal','proto41_windscreen_rubber','proto41_front_window_proxy')
BAY_DEPTH=.035
PANE_DEPTH=.058


def _prototype(style):
    assert style in ('fxn5c','fxn5c_jinwen','fxn5c_prototype_0001'),style
    return style=='fxn5c_prototype_0001'


def _points(o):return [o.matrix_world@v.co for v in o.data.vertices]


def selected_objects(style):
    proto=_prototype(style);result=[]
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        selected=o.name.startswith(PREFIX)
        selected |= o.name.startswith(DETAILS)
        if proto:
            selected |= o.name.startswith(PROTOTYPE+('glazing_proto41_front',))
            if o.name.startswith('proto41_head_front_skin'):
                pts=_points(o);selected |= max(p.z for p in pts)>2.60
        else:
            selected |= o.name in PANES or o.name=='body_open_shell_v07' or o.name.startswith(PRODUCTION)
        if selected:
            assert not o.get('livery21_variable') and not o.get('light24_emitter'),o.name
            result.append(o)
    return result


def _rewrite(o,planes,gate,mapper=None,discard=None):
    """Scoped polygon split retaining original UVs, materials and normals."""
    old=o.data;wp=_points(o);tf=o.matrix_world;inv=tf.inverted()
    uv_layers=list(old.uv_layers);normals=[tuple(n.vector) for n in old.corner_normals]
    vertices=[tuple(v.co) for v in old.vertices];faces=[];mats=[];smooth=[];ns=[];uvs=[[] for _ in uv_layers]
    modified=0
    def retain(f):
        faces.append(tuple(f.vertices));mats.append(f.material_index);smooth.append(f.use_smooth)
        ns.extend(normals[li] for li in f.loop_indices)
        for i,layer in enumerate(uv_layers):uvs[i].extend(tuple(layer.data[li].uv) for li in f.loop_indices)
    for f in old.polygons:
        ps=[wp[i] for i in f.vertices]
        if not gate(ps):retain(f);continue
        poly=[(*wp[vi],*[x for layer in uv_layers for x in layer.data[li].uv],*normals[li]) for vi,li in zip(f.vertices,f.loop_indices)]
        parts=[poly]
        for plane in planes:
            parts=[part for p in parts for part in (_split_attributes(p,plane) if gate([Vector(q[:3]) for q in p]) else [p])]
        for part in parts:
            center=tuple(sum(p[i] for p in part)/len(part) for i in range(3))
            if discard and discard(center):modified+=1;continue
            transformed=[Vector(mapper(p[:3])) if mapper else Vector(p[:3]) for p in part]
            moved=any((q-Vector(p[:3])).length>1e-8 for p,q in zip(part,transformed))
            first=len(vertices);vertices.extend(tuple(inv@p) for p in transformed)
            faces.append(tuple(range(first,len(vertices))));mats.append(f.material_index);smooth.append(f.use_smooth)
            for p in part:
                ns.append((0,0,0) if moved else tuple(Vector(p[-3:]).normalized()))
                for i in range(len(uv_layers)):uvs[i].append(tuple(p[3+2*i:5+2*i]))
            modified+=int(moved or len(parts)>1)
    mesh=bpy.data.meshes.new(old.name+'_window42');mesh.from_pydata(vertices,[],faces)
    for m in old.materials:mesh.materials.append(m)
    for f,m,s in zip(mesh.polygons,mats,smooth):f.material_index=m;f.use_smooth=s
    for layer,values in zip(uv_layers,uvs):
        dst=mesh.uv_layers.new(name=layer.name)
        for uv,value in zip(dst.data,values):uv.uv=value
    mesh.update();mesh.normals_split_custom_set(ns);o.data=mesh
    return modified


def _corner_map(p):
    x,y,z=p;u=abs(y)
    if not 2.55<z<4.02001 or u<=1.335:return p
    d=abs(x)-SilhouetteBuilder.front_x(z)
    if d<=-.270001:return p
    depth_weight=max(0,min(1,(d+.27)/.03))
    height_weight=max(0,min(1,(z-2.55)/.085))
    old=SilhouetteBuilder.front_half(z)
    if u<=old:
        target=1.335+(u-1.335)*(.095/(old-1.335))
        dx=0
    else:
        target=1.43+(u-old)*(.22/(1.65-old))
        # The current v40 shell's actual corner ends at Y=1.65 and has
        # X setback 0.3*(Y-front_half), unlike the historical v07 helper.
        dx=.3*((u-old)-(target-1.43))
    weight=depth_weight*height_weight
    return (x+(1 if x>0 else -1)*dx*weight,y+(1 if y>0 else -1)*(target-u)*weight,z)


def _production_corners(o):
    planes=[]
    for end in (-1,1):
        planes.extend(lambda p,e=end,d=d:e*p[0]-SilhouetteBuilder.front_x(p[2])-d for d in (-.27,-.24))
    planes.extend(lambda p,z=z:p[2]-z for z in (2.55,2.635,4.02))
    planes += [lambda p,s=s:s*p[1]-1.335 for s in (-1,1)]
    planes += [lambda p,s=s:s*p[1]-SilhouetteBuilder.front_half(p[2]) for s in (-1,1)]
    def gate(ps):
        return (min(p.z for p in ps)<4.020001 and max(p.z for p in ps)>2.550001
                and max(abs(p.y) for p in ps)>1.335001
                and max(abs(p.x)-SilhouetteBuilder.front_x(p.z) for p in ps)>-.270001)
    return _rewrite(o,planes,gate,_corner_map)


def _clip_bay(o,end,half,z0,z1,front_x):
    bounds=((min(front_x(z0),front_x(z1))-.16,max(front_x(z0),front_x(z1))+.09),(-half,half),(z0,z1))
    def inside(p):return all(a+1e-7<(end*p[0] if i==0 else p[i])<b-1e-7 for i,(a,b) in enumerate(bounds))
    planes=[lambda p,i=i,v=v:(end*p[0] if i==0 else p[i])-v for i,(a,b) in enumerate(bounds) for v in (a,b)]
    def gate(ps):
        return not any(max((end*p.x if i==0 else p[i]) for p in ps)<=a+1e-7 or min((end*p.x if i==0 else p[i]) for p in ps)>=b-1e-7 for i,(a,b) in enumerate(bounds))
    return _rewrite(o,planes,gate,discard=inside)


def _tag(o,role,end):
    o['glazing42_role']=role;o['glazing42_end']=end
    return o


def _inside_loop(p,loop):
    inside=False
    for a,b in zip(loop,loop[1:]+loop[:1]):
        if (a[1]>p[1])!=(b[1]>p[1]) and p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def _bay(builder,style,end,half,z0,z1,front_x):
    proto=_prototype(style)
    outer=[(-half,z0),(half,z0),(half,z1),(-half,z1)]
    loops=[outer]+[(proto_loop(s,.023) if proto else rectangle_loop(s,.022)) for s in (-1,1)]
    vertices=[];edges=[]
    for loop in loops:
        first=len(vertices);vertices.extend(Vector(p) for p in loop)
        edges.extend((first+i,first+(i+1)%len(loop)) for i in range(len(loop)))
    # Preserve the accepted Jinwen blue/roof split without adding coplanar ink.
    if style=='fxn5c_jinwen':
        first=len(vertices);vertices.extend((Vector((-half,3.95)),Vector((half,3.95))));edges.append((first,first+1))
    points,_,triangles,*_=delaunay_2d_cdt(vertices,edges,[],0,1e-7)
    front=[]
    for face in triangles:
        c=sum((points[i] for i in face),Vector((0,0)))/len(face)
        if _inside_loop(c,outer) and not any(_inside_loop(c,hole) for hole in loops[1:]):front.append(tuple(face))
    verts=[(end*(front_x(p.y)-BAY_DEPTH),p.x,p.y) for p in points]
    faces=list(front)
    if builder.lod<2:
        n=len(verts);verts += [(x-end*.06,y,z) for x,y,z in verts]
        faces += [tuple(n+i for i in reversed(f)) for f in front]
        boundary=Counter(tuple(sorted((a,b))) for f in front for a,b in zip(f,f[1:]+f[:1]))
        faces += [(a,b,b+n,a+n) for (a,b),count in boundary.items() if count==1]
    mat='graphite' if proto else 'jw_blue' if style=='fxn5c_jinwen' else 'roof'
    obj=builder.poly(f'{PREFIX}recess_panel_{end:+d}',verts,faces,mat,solid=builder.lod<2,normal=(end,0,0))
    if style=='fxn5c_jinwen':
        obj.data.materials.append(builder.mat('jw_roof'))
        for f in obj.data.polygons:
            if sum(obj.data.vertices[i].co.z for i in f.vertices)/len(f.vertices)>=3.95-1e-6:f.material_index=1
    _tag(obj,'recess_panel',end)
    # Four real visible return walls join the original body at depth zero to
    # the recessed panel. These are geometry, not dark decals over the hole.
    vv=[(end*front_x(z),y,z) for y,z in outer]+[(end*(front_x(z)-BAY_DEPTH),y,z) for y,z in outer]
    fs=[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)]
    returns=builder.poly(f'{PREFIX}bay_returns_{end:+d}',vv,fs,mat)
    _tag(returns,'bay_returns',end)
    return obj,returns


def _shift(o,delta):
    inv=o.matrix_world.inverted()
    for v in o.data.vertices:
        p=o.matrix_world@v.co;d=delta(p) if callable(delta) else delta
        p.x+=(1 if p.x>0 else -1)*d;v.co=inv@p
    o.data.update()
    if callable(delta):o.data.normals_split_custom_set([(0,0,0)]*len(o.data.loops))


def _far_apply(builder,style):
    """Opaque distant windows: old hull topology, real shallow deformation.

    No true cabin aperture is claimed at LOD2. The solid pane proxies remain
    12 mm proud of the recessed hull, hence 23 mm behind the former face.
    """
    proto=_prototype(style);fx=proto_x if proto else SilhouetteBuilder.front_x
    before=selected_objects(style);shifted=[]
    shells=[o for o in before if o.name.startswith('proto41_head_front_skin') or o.name=='body_open_shell_v07']
    for o in shells:
        normals=[n.vector.copy() for n in o.data.corner_normals]
        inv=o.matrix_world.inverted();changed=set()
        for v in o.data.vertices:
            p=o.matrix_world@v.co;q=Vector(p)
            if 2.54999<=p.z<=4.02001:
                depth=abs(p.x)-fx(p.z)
                if proto:
                    if depth>-.15:q.x-=(1 if p.x>0 else -1)*BAY_DEPTH
                elif depth>-.270001:
                    q=Vector(_corner_map(p))
                    old=SilhouetteBuilder.front_half(p.z)
                    w=max(0,min(1,(1.65-abs(p.y))/(1.65-old)))
                    q.x-=(1 if p.x>0 else -1)*BAY_DEPTH*w
            if (q-p).length>1e-8:v.co=inv@q;changed.add(v.index)
        o.data.update()
        for f in o.data.polygons:
            if any(i in changed for i in f.vertices):
                for i in f.loop_indices:normals[i]=f.normal.copy()
        o.data.normals_split_custom_set(normals)
        shifted.append(dict(name=o.name,vertices=len(changed),topology_unchanged=True))
    for o in before:
        if o in shells:continue
        if o.name.startswith(('distant_windows','proto41_front_window_proxy')):
            depth=sum(abs(p.x)-fx(p.z) for p in _points(o))/len(o.data.vertices)
            _shift(o,-.023-depth);shifted.append(dict(name=o.name,proxy_depth=.023))
    # A flat material land is the existing hull's distant gray-panel proxy.
    # It sits 1 mm ahead of the recessed hull, never occluding the panes.
    half,z0,z1=(1.21,2.62,4.01) if proto else (1.335,2.56,3.985)
    for end in (-1,1):
        levels=[z0,3.95,z1] if style=='fxn5c_jinwen' else [z0,z1]
        verts=[(end*(fx(z)-.034),y,z) for z in levels for y in (-half,half)]
        faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(len(levels)-1)]
        mat='graphite' if proto else 'jw_blue' if style=='fxn5c_jinwen' else 'roof'
        o=builder.poly(f'{PREFIX}far_panel_{end:+d}',verts,faces,mat,normal=(end,0,0))
        if style=='fxn5c_jinwen':
            o.data.materials.append(builder.mat('jw_roof'));o.data.polygons[-1].material_index=1
        _tag(o,'simplified_recess_panel',end)
        uv=o.data.uv_layers.new(name='UVMap')
        for li in o.data.loops:
            p=o.data.vertices[li.vertex_index].co;uv.data[li.index].uv=((p.y+1.7)/3.4,p.z/4.7)
        if proto:
            # Prototype front skins are independent of the fixed wide cheeks.
            # Join their displaced perimeter to the unchanged original seams.
            outer=[(-1.25,2.55),(1.25,2.55),(1.25,4.02),(-1.25,4.02)]
            vv=[(end*fx(z),y,z) for y,z in outer]+[(end*(fx(z)-BAY_DEPTH),y,z) for y,z in outer]
            fs=[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)]
            wall=builder.poly(f'{PREFIX}far_proto_returns_{end:+d}',vv,fs,'graphite')
            _tag(wall,'far_physical_perimeter_returns',end)
            uv=wall.data.uv_layers.new(name='UVMap')
            for li in wall.data.loops:
                p=wall.data.vertices[li.vertex_index].co;uv.data[li.index].uv=((p.y+1.7)/3.4,p.z/4.7)
    bpy.context.view_layer.update();bpy.context.scene['glazing42_done']=True
    return dict(style=style,lod=2,selected_before=[o.name for o in before],shifted=shifted,
                panel_depth=.035,visible_panel_depth=.034,glass_depth=.023,
                bay_half_width=half,bay_z=[z0,z1],far_simplified_solid_proxy=True,
                no_new_shell_topology=True,prototype_perimeter_return_triangles=16 if proto else 0,photo_fit_not_surveyed=True)


def apply(builder,style):
    proto=_prototype(style);front_x=proto_x if proto else SilhouetteBuilder.front_x
    assert not bpy.context.scene.get('glazing42_done'),'apply once to baseline'
    if builder.lod==2:return _far_apply(builder,style)
    before=selected_objects(style);old_names=[o.name for o in before];removed=[];shifted=[]
    if not proto:_production_corners(bpy.data.objects['body_open_shell_v07'])
    half,z0,z1=(1.21,2.62,4.01) if proto else (1.335,2.56,3.985)
    shells=[o for o in before if (o.name.startswith('proto41_head_front_skin') if proto else o.name=='body_open_shell_v07')]
    for end in (-1,1):
        for o in shells:_clip_bay(o,end,half,z0,z1,front_x)
        _bay(builder,style,end,half,z0,z1,front_x)
    for o in before:
        if o in shells:continue
        if o.name.startswith('angular_windshield_surround'):
            removed.append(o.name);bpy.data.objects.remove(o,do_unlink=True);continue
        if o.name in PANES or o.name.startswith(('glazing_proto41_front','distant_windows','proto41_front_window_proxy')):
            points=_points(o);old=sum(abs(p.x)-front_x(p.z) for p in points)/len(points)
            delta=-PANE_DEPTH-old
        elif o.name.startswith(('front_sun_visor','sunblind_roller')):delta=-.07
        elif o.name.startswith(('straight_centre_mullion','mullion_metal_bead')):delta=-.054
        elif o.name.startswith('parked_wiper_arm'):
            delta=lambda p:-.084-.022*max(0,min(1,(p.z-2.72)/.115))
        elif o.name.startswith('parked_wiper_spine'):delta=-.111
        elif o.name.startswith('parked_wiper_rubber'):delta=-.106
        elif o.name.startswith('wiper_drive'):delta=-.084
        elif o.name.startswith(('wiper_service','wiper_pull')):delta=-.054
        else:delta=-.060
        _shift(o,delta);shifted.append(dict(name=o.name,delta_x_abs='anchor-to-blade variable -.084..-.106' if callable(delta) else delta))
    new=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name.startswith(PREFIX)]
    for o in new:
        uv=o.data.uv_layers.new(name='UVMap')
        for li in o.data.loops:
            p=o.data.vertices[li.vertex_index].co;uv.data[li.index].uv=((p.y+1.7)/3.4,p.z/4.7)
    bpy.context.view_layer.update();bpy.context.scene['glazing42_done']=True
    return dict(style=style,lod=builder.lod,selected_before=old_names,removed=removed,shifted=shifted,
                new_objects=[o.name for o in new],bay_half_width=half,bay_z=[z0,z1],
                panel_depth=BAY_DEPTH,glass_depth=PANE_DEPTH,production_parallel_corner_z=[2.635,4.02] if not proto else None,
                photo_fit_not_surveyed=True)
