"""v44 incremental planar cheeks and vertical nose grabs, input v43 only.

Dimensions are photograph fits. The cab/front plane, upper head, optical Y/Z,
existing object transforms, material resources and runtime metadata stay fixed.
"""
import math
import bpy
from mathutils import Vector,Matrix
import prototype_profile_v43 as previous
import prototype_head_v41 as head
from glazing_revision_v42 import _rewrite

STYLE='fxn5c_prototype_0001'
PREFIX='geometry44_'
HALF=1.25
OUTER=1.65
SETBACK=.25
SLOPE=SETBACK/(OUTER-HALF)
GRAB_Y=.77
GRAB_CENTER_Z=2.07
GRAB_LENGTH=math.hypot(.12,.54)
GRAB_Z=(GRAB_CENTER_Z-GRAB_LENGTH/2,GRAB_CENTER_Z+GRAB_LENGTH/2)
SKIN_PREFIX=('proto41_head_wide_corner','proto41_head_side_skin','proto41_vertical_lamp_panel',
             'proto41_front_yellow_u','nose_grey_belt','cab_hazard')
OPTIC_PREFIX=('proto41_lower_lamp_','glazing_proto41_lower')
GRAB_PREFIX=('nose_grab_v11_','grab_mount_v11_','front_finish_v11_mount_bolt_')


def points(o):return [o.matrix_world@v.co for v in o.data.vertices]


def surface_x(y,z):
    return previous.front_x(z)-SLOPE*max(0,min(OUTER-HALF,abs(y)-HALF))


def _change(y,z):return surface_x(y,z)-previous.surface_x(y,z)


def selected_objects(style=STYLE):
    if style!=STYLE:return []
    out=[]
    for o in bpy.context.scene.objects:
        if o.type!='MESH':continue
        if o.name.startswith(SKIN_PREFIX+OPTIC_PREFIX+GRAB_PREFIX+(PREFIX,'profile43_')) or o.name in('light24_fwd','light24_bwd'):
            out.append(o)
    return out


def _modify(o,mapper,normal_rotation=None):
    inv=o.matrix_world.inverted();old=points(o)
    ns=[n.vector.copy()for n in o.data.corner_normals]
    changed=set();max_move=0
    for v,p in zip(o.data.vertices,old):
        q=Vector(mapper(p,v.index));d=(q-p).length
        if d>1e-9:v.co=inv@q;changed.add(v.index);max_move=max(max_move,d)
    o.data.update()
    for f in o.data.polygons:
        if not any(i in changed for i in f.vertices):continue
        for li in f.loop_indices:
            if normal_rotation is not None:
                nw=o.matrix_world.to_3x3().inverted().transposed()@ns[li]
                ns[li]=(o.matrix_world.to_3x3().transposed()@normal_rotation@nw).normalized()
            elif not f.use_smooth:ns[li]=f.normal.copy()
    o.data.normals_split_custom_set(ns)
    return dict(name=o.name,changed_vertices=len(changed),maximum_move=max_move)


def _skin(o):
    side=o.name.startswith('proto41_head_side_skin')
    if o.name.startswith('proto41_vertical_lamp_panel'):
        _rewrite(o,[lambda q:q[1]-HALF,lambda q:q[1]+HALF],lambda pp:True)
    def mapper(p,i):
        d=_change(p.y,p.z)
        if side:
            depth=abs(p.x)-previous.surface_x(p.y,p.z)
            d*=max(0,min(1,(depth+.18)/.10))
        return (p.x+(1 if p.x>0 else-1)*d,p.y,p.z)
    return _modify(o,mapper)


def _optic(o):
    pp=points(o);cy=(min(v.y for v in pp)+max(v.y for v in pp))/2
    cz=(min(v.z for v in pp)+max(v.z for v in pp))/2
    end=1 if sum(v.x for v in pp)>0 else-1
    d=_change(cy,cz)
    if o.name.startswith('proto41_lower_lamp_adapter'):
        # Front annulus stays normal to the unchanged longitudinal optical
        # axis; rear annulus meets the now planar lamp pocket at every point.
        n=len(pp)//4
        def mapper(p,i):
            dx=d if i<2*n else _change(p.y,p.z)
            return (p.x+end*dx,p.y,p.z)
        return _modify(o,mapper)
    if o.name.startswith(('proto41_lower_lamp_far_rim','proto41_lower_lamp_far_lens')):
        # Far has no bored cavity or emitter: keep the existing surface-fitted
        # opaque proxy policy so the solid panel cannot hide half its disc.
        return _modify(o,lambda p,i:(p.x+end*_change(p.y,p.z),p.y,p.z))
    return _modify(o,lambda p,i:(p.x+end*d,p.y,p.z))


def _lights(o):
    # Source light meshes contain independent discs for both travel ends.
    # Shift only lower discs; keep top discs and all condition metadata exact.
    delta={};pp=points(o)
    for f in o.data.polygons:
        center=sum((pp[i]for i in f.vertices),Vector())/len(f.vertices)
        if center.z>2.55:continue
        d=(1 if center.x>0 else-1)*_change(center.y,center.z)
        for vi in f.vertices:delta[vi]=d
    return _modify(o,lambda p,i:(p.x+delta.get(i,0),p.y,p.z))


def _grab(o):
    pp=points(o);side=1 if sum(p.y for p in pp)>0 else-1
    center=Vector((0,side*GRAB_Y,GRAB_CENTER_Z))
    rotation=Matrix.Rotation(math.atan2(side*.12,.54),3,'X')
    return _modify(o,lambda p,i:center+rotation@(p-center),rotation)


def _mesh(b,name,verts,faces,mat):
    o=b.poly(name,verts,faces,mat)
    uv=o.data.uv_layers.new(name='UVMap')
    for li in o.data.loops:
        p=o.data.vertices[li.vertex_index].co;uv.data[li.index].uv=((p.x+p.y)/5,p.z/5)
    return o


def _bottom_returns(b):
    names=[]
    for end in(-1,1):
        for side in(-1,1):
            # Close the newly recessed corner down onto the inherited lower
            # nose/skirt boundary without displacing that established skirt.
            vertices=[(end*surface_x(HALF,1.58),side*HALF,1.58),
                (end*previous.surface_x(OUTER,1.58),side*OUTER,1.58),
                (end*surface_x(OUTER,1.58),side*OUTER,1.58)]
            o=_mesh(b,f'{PREFIX}lower_corner_return_{end}_{side}',vertices,[(0,1,2)],'graphite')
            names.append(o.name)
    return names


def _far_grabs(b):
    made=[]
    for end in(-1,1):
        for side in(-1,1):
            low,high=GRAB_Z
            centers=[Vector((end*x,side*GRAB_Y,z))for x,z in((11.0475,low),(11.087,low+.026),(11.087,high-.026),(11.0475,high))]
            vv=[];ff=[];n=6
            for i,c in enumerate(centers):
                tangent=(centers[min(i+1,3)]-centers[max(0,i-1)]).normalized()
                a=Vector((0,1,0));d=tangent.cross(a).normalized()
                for j in range(n):vv.append(tuple(c+.012*(a*math.cos(math.tau*j/n)+d*math.sin(math.tau*j/n))))
            for i in range(3):
                for j in range(n):ff.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
            ff.extend([tuple(range(n-1,-1,-1)),tuple(range(3*n,4*n))])
            made.append(_mesh(b,f'{PREFIX}far_nose_grab_{end}_{side}',vv,ff,'metal').name)
            for k,z in enumerate(GRAB_Z):
                vv=[(end*(11.04+x),side*GRAB_Y+y,z+dz)for x in(.0005,.008)for y,dz in((-.018,-.020),(.018,-.020),(.018,.020),(-.018,.020))]
                ff=[(3,2,1,0),(4,5,6,7)]+[(i,(i+1)%4,(i+1)%4+4,i+4)for i in range(4)]
                made.append(_mesh(b,f'{PREFIX}far_grab_mount_{end}_{side}_{k}',vv,ff,'metal').name)
    return made


def _refresh_seams(b):
    # Reuse only the pure surface-strip builders, never the v43 apply recipe.
    # Replace data on each existing object: names, parents, metadata and native
    # attachment matching stay unchanged.
    tree=previous._surface_tree();changed=[]
    for end in(-1,1):
        name=f'profile43_front_seam_{end:+d}';old=bpy.data.objects[name]
        new=previous._front_seam(b,end);old.data=new.data;bpy.data.objects.remove(new,do_unlink=True);changed.append(name)
        for side in(-1,1):
            name=f'profile43_side_seam_{end:+d}_{side:+d}';old=bpy.data.objects[name]
            new=previous._side_seam(b,end,side,tree);old.data=new.data;bpy.data.objects.remove(new,do_unlink=True);changed.append(name)
    return changed


def apply(builder,style=STYLE):
    if style!=STYLE:return dict(status='NOT_APPLICABLE',style=style)
    assert bpy.context.scene.get('profile43_done'),'input must be the final v43 source'
    assert not bpy.context.scene.get('geometry44_done'),'apply once to v43'
    selected=selected_objects(style);before=[o.name for o in selected];changes=[]
    for o in selected:
        if o.name.startswith('profile43_'):continue
        if o.name.startswith(GRAB_PREFIX):changes.append(_grab(o))
        elif o.name.startswith(OPTIC_PREFIX):changes.append(_optic(o))
        elif o.name in('light24_fwd','light24_bwd'):changes.append(_lights(o))
        elif o.name.startswith(SKIN_PREFIX):changes.append(_skin(o))
    bpy.context.view_layer.update()
    made=_bottom_returns(builder)
    if builder.lod==2:made+=_far_grabs(builder)
    seams=_refresh_seams(builder)
    bpy.context.view_layer.update();bpy.context.scene['geometry44_done']=True
    return dict(status='PASS',style=style,lod=builder.lod,selected_before=before,
        selected_after=[o.name for o in selected_objects(style)],changes=changes,new_objects=made,seams_reseated=seams,
        cheek_plane=dict(setback=SETBACK,inner_y=HALF,outer_y=OUTER,x_slope_per_abs_y=-SLOPE),
        grabs=dict(y=GRAB_Y,z=list(GRAB_Z),direction=[0,0,1],radius=.012),
        protected='v43 front/upper profile, glazing and lights Y/Z, metadata, parents/transforms, production variants',
        reference_fit_not_factory_dimensions=True)
