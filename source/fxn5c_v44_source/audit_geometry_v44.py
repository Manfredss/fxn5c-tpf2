"""Independent geometric checks of a saved v44 scene; never applies/saves it."""
import math
from collections import Counter
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import prototype_geometry_v44 as g
import prototype_profile_v43 as old
import prototype_head_v41 as head


def _tree(objects):
    vv=[];ff=[];names=[]
    for o in objects:
        off=len(vv);vv.extend(g.points(o));ff.extend(tuple(off+i for i in f.vertices)for f in o.data.polygons)
        names.extend(o.name for _ in o.data.polygons)
    assert ff,'no audit geometry'
    return BVHTree.FromPolygons(vv,ff),names


def _objects(prefix):return [o for o in bpy.context.scene.objects if o.type=='MESH'and o.name.startswith(prefix)]


def _closed(o):
    counts=Counter(tuple(sorted((a,b)))for f in o.data.polygons for a,b in zip(tuple(f.vertices),tuple(f.vertices)[1:]+tuple(f.vertices)[:1]))
    assert all(v==2 for v in counts.values()),('nonclosed component',o.name,Counter(counts.values()))


def check_saved_scene(lod,style=g.STYLE):
    if style!=g.STYLE:return dict(status='NOT_APPLICABLE',style=style)
    assert bpy.context.scene.get('geometry44_done')
    corners=_objects('proto41_head_wide_corner');ct,_=_tree(corners)
    errors=[];normal_errors=[];plane_rays=0
    for end in(-1,1):
        for side in(-1,1):
            expected_normal=Vector((end,.625*side,old.SLOPE)).normalized()
            for y in(1.27,1.33,1.40,1.51,1.62):
                for z in(2.67,2.9,3.2,3.5,3.85):
                    # An independent explicit plane, not the recipe mapper.
                    expected=old.X0-old.SLOPE*(z-2.62)-.625*(y-1.25)
                    h,n,fi,d=ct.ray_cast(Vector((end*11.3,side*y,z)),Vector((-end,0,0)),1.5)
                    assert h is not None,('missing planar cheek',end,side,y,z)
                    error=abs(abs(h.x)-expected);errors.append(error)
                    error_n=1-n.dot(expected_normal);normal_errors.append(error_n)
                    assert error<4e-6 and abs(error_n)<2e-5,('nonplanar actual cheek',end,side,y,z,error,error_n)
                    plane_rays+=1
    # Full adjacency, both end positions and both sides: unchanged upper cab,
    # new planar corners, and the real return onto the lower skirt boundary.
    side_tree,_=_tree(_objects('proto41_head_side_skin'))
    wing_tree,_=_tree(_objects('proto41_head_brow_wing'))
    brow_tree,_=_tree([o for o in _objects('proto41_head_brow')if 'wing' not in o.name])
    canopy_tree,_=_tree(_objects('roof24_front_folded_canopy'))
    cap_tree,_=_tree(_objects('geometry44_lower_corner_return'))
    joins=[]
    def touch(v,*trees):
        for tree in trees:
            _,_,_,distance=tree.find_nearest(Vector(v));joins.append(distance)
            assert distance<4e-6,('open adjacent boundary',v,distance)
    for end in(-1,1):
        for side in(-1,1):
            for t in(0,.1,.25,.5,.75,.9,1):
                z=2.62+1.33*t
                touch((end*g.surface_x(1.65,z),side*1.65,z),ct,side_tree)
                y=1.25+.4*t
                touch((end*g.surface_x(y,3.95),side*y,3.95),ct,wing_tree)
                touch((end*g.surface_x(y,1.58),side*y,1.58),ct,cap_tree)
                touch((end*old.surface_x(y,1.58),side*y,1.58),cap_tree)
                z=3.95+.33*t;y=1.65-.31*t
                x=(1-t)*old.surface_x(1.65,3.95)+t*old.surface_x(1.34,4.28)
                touch((end*x,side*y,z),wing_tree,canopy_tree)
                y=1.25+.09*t;z=4.02+.26*t
                touch((end*old.surface_x(y,z),side*y,z),wing_tree,brow_tree)
            for t in(0,.1,.15,.25,.5,.75,.9,1):
                z=4.28+.425*t;y=1.34-.60*t
                touch((end*old.surface_x(y,z),side*y,z),brow_tree,canopy_tree)
        for y in(-.74,-.5,-.25,0,.25,.5,.74):touch((end*10.44,y,4.705),brow_tree,canopy_tree)
    # Lower light discs retain longitudinal axes, original Y/Z and radius.
    optical_errors=[];light_disc_count=0;lamp_rays=0
    selected=g.selected_objects(style)
    opaque=[o for o in selected if not o.name.startswith(('glazing_','light24_'))]
    opaque+=_objects('proto41_head_front_skin')
    blockers,names=_tree(opaque)
    if lod<2:
        lenses=_objects('glazing_proto41_lower');assert len(lenses)==8
        for o in lenses:
            pp=g.points(o);cy=(min(v.y for v in pp)+max(v.y for v in pp))/2
            cz=(min(v.z for v in pp)+max(v.z for v in pp))/2;end=1 if pp[0].x>0 else-1
            assert min(abs(cz-z)for z in(2.025,2.325))<2e-6
            assert abs(abs(cy)-head.lower_y(cz))<2e-6
            x=g.surface_x(cy,cz)+.021
            optical_errors.extend(abs(abs(v.x)-x)for v in pp)
            assert max(abs(abs(v.x)-x)for v in pp)<3e-6,('lens no longer axial',o.name)
            for dy,dz in[(0,0)]+[(.082*math.cos(math.tau*i/12),.082*math.sin(math.tau*i/12))for i in range(12)]:
                h,n,fi,d=blockers.ray_cast(Vector((end*(x+.20),cy+dy,cz+dz)),Vector((-end,0,0)),.1999)
                assert h is None,('partly hidden lower lens',o.name,dy,dz,names[fi]if fi is not None else None)
                lamp_rays+=1
        for o in _objects('proto41_lower_lamp_adapter'):
            pp=g.points(o);n=len(pp)//4;cy=(min(v.y for v in pp)+max(v.y for v in pp))/2
            cz=(min(v.z for v in pp)+max(v.z for v in pp))/2
            for v in pp[:2*n]:assert abs(abs(v.x)-g.surface_x(cy,cz)-.012)<3e-6,('adapter front disconnected',o.name)
            for v in pp[2*n:]:assert abs(abs(v.x)-g.surface_x(v.y,v.z)+.008)<3e-6,('adapter rear not on shell',o.name)
            _closed(o)
        for o in _objects('light24_'):
            if o.name not in('light24_fwd','light24_bwd'):continue
            assert len(o.data.polygons)==10
            owners=Counter(i for f in o.data.polygons for i in f.vertices)
            assert all(n==1 for n in owners.values()),('shared emitter vertices',o.name)
            pp=g.points(o);top=lower=0
            for f in o.data.polygons:
                vertices=[pp[i]for i in f.vertices];c=sum(vertices,Vector())/len(vertices)
                if c.z>2.55:
                    top+=1
                    assert max(abs(abs(v.x)-old.front_x(v.z)+.102)for v in vertices)<3e-6
                    radius=.034
                    assert min(abs(c.y-y)for y in head.TOP_LAMPS)<2e-6 and abs(c.z-head.TOP_Z)<2e-6
                else:
                    lower+=1;radius=.066
                    assert abs(abs(c.y)-head.lower_y(c.z))<3e-6
                    assert min(abs(c.z-z)for z in(2.025,2.325))<2e-6
                    assert max(abs(abs(v.x)-g.surface_x(c.y,c.z)-.017)for v in vertices)<3e-6
                    assert max(v.x for v in vertices)-min(v.x for v in vertices)<2e-6
                assert max(abs(math.hypot(v.y-c.y,v.z-c.z)-radius)for v in vertices)<3e-6
                light_disc_count+=1
            assert top==4 and lower==6
    else:
        for o in _objects('proto41_lower_lamp_far_lens'):
            pp=g.points(o)
            assert max(abs(abs(v.x)-g.surface_x(v.y,v.z)-.015)for v in pp)<3e-6
            for v in pp:
                h,n,fi,d=blockers.ray_cast(Vector((v.x+(1 if v.x>0 else -1)*.10,v.y,v.z)),Vector((-1 if v.x>0 else 1,0,0)),.1001)
                assert h is not None and names[fi].startswith('proto41_lower_lamp_far_lens'),('far proxy hidden',o.name,names[fi]if fi is not None else None)
                lamp_rays+=1
    # Nose handles use the original circular tube under a rigid X-axis turn.
    grabs=_objects('nose_grab_v11_')if lod<2 else _objects('geometry44_far_nose_grab')
    assert len(grabs)==4
    axis_errors=[];mount_errors=[]
    front,_=_tree(_objects(('proto41_head_front_skin','proto41_front_black_below_window')))
    for o in grabs:
        _closed(o);pp=g.points(o);n=(20 if lod==0 else 12)if lod<2 else 6
        centers=[sum(pp[i:i+n],Vector())/n for i in range(0,len(pp),n)]
        end=1 if centers[0].x>0 else-1;side=1 if centers[0].y>0 else-1
        assert max(abs(c.y-side*.77)for c in centers)<2e-6,('inclined nose handle',o.name)
        middle=[c for c in centers if abs(abs(c.x)-11.087)<2e-6]
        assert len(middle)>=2
        axis_errors.append((middle[-1]-middle[0]).normalized().cross(Vector((0,0,1))).length)
        assert axis_errors[-1]<3e-6
        assert abs(centers[0].z-g.GRAB_Z[0])<2e-6 and abs(centers[-1].z-g.GRAB_Z[1])<2e-6
        for k,z in enumerate(g.GRAB_Z):
            name=f'grab_mount_v11_{end}_{side}_{k}'if lod<2 else f'geometry44_far_grab_mount_{end}_{side}_{k}'
            mount=bpy.data.objects[name];_closed(mount);mp=g.points(mount)
            assert abs((min(v.y for v in mp)+max(v.y for v in mp))/2-side*.77)<2e-6
            assert abs((min(v.z for v in mp)+max(v.z for v in mp))/2-z)<2e-6
            h,n,fi,d=front.ray_cast(Vector((end*11.10,side*.77,z)),Vector((-end,0,0)),.12)
            assert h is not None
            error=min(abs(v.x)for v in mp)-abs(h.x);mount_errors.append(error)
            assert -.0005<error<.001,('floating nose handle pad',name,error)
            assert min(abs(v.x)for v in mp)<abs(centers[0].x)<max(abs(v.x)for v in mp)+.001
    # Rebuilt black line must remain a narrow surface marking, not a floating
    # former line over the moved cheek or a buried chord through the side.
    support=old._surface_tree();seam_errors=[];seam_rays=0
    for o in _objects('profile43_side_seam'):
        st,_=_tree([o]);end=o['profile43_end'];side=o['profile43_side']
        for v in g.points(o):
            _,_,_,distance=support.find_nearest(v);seam_errors.append(distance)
            assert .0008<distance<.0015,('black line detached',o.name,distance)
        for x in(9.2,9.5,9.8,10.1,10.4,10.65):
            for dz,inside in((0,True),(-.005,True),(.005,True),(-.007,False),(.007,False)):
                h,n,fi,d=st.ray_cast(Vector((end*x,side*1.9,2.62+dz)),Vector((0,-side,0)),.35)
                assert (h is not None)==inside,('black line width/continuity',o.name,x,dz)
                seam_rays+=1
    return dict(status='PASS',style=style,lod=lod,real_plane_rays=plane_rays,
        max_cheek_plane_error=max(errors),max_cheek_normal_error=max(abs(x)for x in normal_errors),
        adjacency_samples=len(joins),max_adjacency_error=max(joins),lower_lens_clearance_rays=lamp_rays,
        independent_emitter_discs=light_disc_count,max_optical_axis_error=max(optical_errors,default=0),
        nose_grabs=4,maximum_grab_axis_error=max(axis_errors),mount_contact_offset_range=[min(mount_errors),max(mount_errors)],
        black_line_width_rays=seam_rays,black_line_skin_offset_range=[min(seam_errors),max(seam_errors)],
        lod2_optics='surface-fitted opaque proxies; no emitters'if lod==2 else'real axial discs and bored adapters',
        native_or_game_validation=False)
