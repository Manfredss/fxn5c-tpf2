"""Actual saved-mesh collision checks, including body/frame, not just leaf pairs."""
from pathlib import Path
import sys,json,math,hashlib
from collections import defaultdict
import bpy
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'runtime'))
from roof_revision_v24 import roof_half_width

def points(o):return [o.matrix_world@v.co for v in o.data.vertices]
def tree(objects,filter_face=lambda p:True):
    verts=[];polys=[];names=[]
    for o in objects:
        ps=points(o)
        for f in o.data.polygons:
            vs=[ps[i] for i in f.vertices]
            if not filter_face(vs):continue
            a=len(verts);verts.extend(vs);polys.append(tuple(range(a,len(verts))));names.append(o.name)
    return BVHTree.FromPolygons(verts,polys,epsilon=1e-8),names
def main():
    results=[]
    manifest=json.loads((ROOT/'manifest_v34.json').read_text())
    for jw in (False,True):
        if '--cr' in sys.argv and jw:continue
        style='fxn5c_jinwen' if jw else 'fxn5c'
        for lod in (0,1,2):
            if '--trial' in sys.argv and lod!=0:continue
            path=ROOT/(style+'_source.blend') if lod==0 else ROOT/'runtime'/f'final34_{style}_lod{lod}.blend'
            bpy.ops.wm.open_mainfile(filepath=str(path))
            objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.name.startswith('bounds|')]
            errors=[];checks=0
            from window_revision_v34 import ROOF_WINDOWS,SIDE_COLUMNS
            roles=lambda role:[o for o in objects if o.get('window30_role')==role]
            new_roof=roles('roof_window_proxy' if lod==2 else 'roof_window_back')
            assert len(new_roof)==(10 if lod==2 else 6)
            assert not any(o.name.startswith('shoulder_vent') and sum(p.y for p in points(o))>0 for o in objects)
            old_other=[o for o in objects if o.name.startswith('shoulder_vent_dark') and sum(p.y for p in points(o))<0]
            assert not old_other,'obsolete opposite-side windows remain'
            mains=[o for o in roles('main_window') if o.name.startswith('window30_side_back')]
            lows=[o for o in roles('low_window') if o.name.startswith('window30_side_back')]
            assert len(mains)==12 and len(lows)==2
            assert not any(o.name.startswith('auxiliary_grille') and sum(p.y for p in points(o))>0 for o in objects),'extra low grille at the reference left end'
            actual_centers=sorted(sum(p.x for p in points(o))/len(points(o)) for o in mains)
            assert max(abs(a-c) for a,c in zip(actual_centers,sorted(list(SIDE_COLUMNS)*2)))<2e-6
            number=next(o for o in objects if o.get('livery21_role')=='side_number' and o.get('livery21_side')==1) if lod<2 else None
            if number:
                assert max(p.x for o in mains for p in points(o))+.25<min(p.x for p in points(number)),'radiator bank overlaps side number'
            for o in roles('main_window')+roles('low_window'):
                if o.name.startswith('window30_side_fin'):
                    ps=points(o)
                    assert max(p.z for p in ps)-min(p.z for p in ps)>.80,'non-vertical radiator fin'
            if lod<2:
                t,n=__import__('roof_revision_v27').vent_basis(1)
                skins=[o for o in objects if o.name.startswith(('body_open_shell','trapezoid_roof_deck','roof28_vacated_bay_skin','carbody_sheet_joint'))]
                st,_=tree(skins)
                for side in (-1,1):
                    t,n=__import__('roof_revision_v27').vent_basis(side)
                    for x,w in ROOF_WINDOWS:
                        c=Vector((x,side*roof_half_width(4.125),4.125))
                        for u in (-w*.30,0,w*.30):
                            assert st.ray_cast(c+Vector((u,0,0))+n*.004,n,.2)[0] is None,'roof-window skin blockage'
                    for x in list(SIDE_COLUMNS)+[-7.61]:
                        for z in ((2.4,2.8) if x==-7.61 else (2.3,2.7,3.2,3.6)):
                            assert st.ray_cast(Vector((x,side*1.60,z)),Vector((0,side,0)),.2)[0] is None,'side-window skin blockage'
            # New banks must be centered on each roof rotor, and not retain
            # the old 4.1/4.84 m frame. Return walls connect frame to dark core.
            assert not any(o.name.startswith(('filter_','vertical_filter_')) for o in objects)
            banks=[o for o in objects if o.name.startswith('roof28_radiator_back')]
            assert len(banks)==4
            centers=sorted(round(sum(p.x for p in points(o))/len(points(o)),3) for o in banks)
            assert centers==[4.105,4.105,4.835,4.835]
            if lod<2:
                for o in objects:
                    if o.name.startswith('trapezoid_roof_shoulder_screw'):
                        ps=points(o);c=sum(ps,Vector())/len(ps)
                        assert not(-2.4<c.x<-1 and .24<abs(c.y)<1.30),'old screw suspended in exhaust opening'
                rails=[o for o in objects if o.get('roof28_role')=='radiator_support']
                assert len(rails)==16
                # Every vertical fin and web intersects a support rail at each
                # end, and the rails span the backing-to-frame depth.
                rb=[(Vector([min(p[i] for p in points(o)) for i in range(3)]),Vector([max(p[i] for p in points(o)) for i in range(3)])) for o in rails]
                for o in objects:
                    if not o.name.startswith(('roof28_radiator_fin','roof28_radiator_fin_web')):continue
                    ps=points(o);lo=Vector([min(p[i] for p in ps) for i in range(3)]);hi=Vector([max(p[i] for p in ps) for i in range(3)])
                    contacts=sum(all(lo[i]<=b[i]+1e-6 and hi[i]>=a[i]-1e-6 for i in range(3)) for a,b in rb)
                    assert contacts>=2,('unsupported radiator fin',o.name,contacts)
                hull=[o for o in objects if o.name.startswith(('body_open_shell','trapezoid_roof_deck'))]
                hulltree,_=tree(hull)
                for side in (-1,1):
                    for x in (4.105,4.835):
                        for z in (2.20,2.6,3.25,3.65):
                            assert hulltree.ray_cast(Vector((x,side*1.58,z)),Vector((0,side,0)),.25)[0] is None,('radiator shell blockage',x,side,z)
                    assert hulltree.ray_cast(Vector((-1.70,side*.76,4.32)),Vector((0,0,1)),.65)[0] is None,'exhaust shell blockage'
            covers=[o for o in objects if o.get('roof28_role')=='raised_cover']
            assert len(covers)==4
            from roof_revision_v29 import surface
            cover_checks=0
            for o in covers:
                ps=points(o)
                assert len(ps)==6
                for a,c in ((0,1),(5,2),(4,3)):
                    assert abs(ps[a].y-ps[c].y)<2e-6
                    assert abs(ps[a].z-ps[c].z)<2e-6,('fore/aft cover pitch',o.name)
                    cover_checks+=1
                for f in o.data.polygons:
                    vs=[ps[i] for i in f.vertices]
                    # Sample face interiors as well as corners, catching a
                    # single flat quad cutting through the roof crown fold.
                    for a in range(6):
                        for c in range(6):
                            u=a/5;v=c/5
                            q=(1-u)*(1-v)*vs[0]+u*(1-v)*vs[1]+u*v*vs[2]+(1-u)*v*vs[3]
                            assert abs(q.z-surface(q.y)-.033)<3e-6,('cover clearance',o.name,tuple(q))
                            cover_checks+=1
            if lod<2:
                pads=[o for o in objects if o.name.startswith('roof_eye_pad_v06') and o.get('roof28_fitting_reseated')]
                eyes=[o for o in objects if o.name.startswith('roof_lifting_eye_v06') and o.get('roof28_fitting_reseated')]
                assert len(pads)==len(eyes)==2
                for pad in pads:
                    ps=points(pad);c=sum(ps,Vector())/len(ps)
                    assert abs(min(p.z for p in ps)-(surface(c.y)+.033))<3e-6,'lifting-eye pad not seated'
                    eye=next(o for o in eyes if sum(p.y for p in points(o))*c.y>0)
                    assert abs(min(p.z for p in points(eye))-max(p.z for p in ps))<3e-6,'eye detached from pad'
            # All freshly generated fan end profiles exactly share the cab's
            # two slopes, not just a similar-looking rectangular projection.
            for o in objects:
                if o.get('roof27_role')=='fan_bay_end':
                    for p in points(o):assert abs(abs(p.y)-roof_half_width(p.z))<2e-6
            # Test intermediate points on shell triangles, not vertices alone:
            # a polygon joining across a fold would otherwise pass.
            samples=[]
            for o in objects:
                if not o.name.startswith(('body_open_shell','cab26_level_equipment_hood')):continue
                ps=points(o)
                for f in o.data.polygons:
                    vs=[ps[i] for i in f.vertices];c=sum(vs,Vector())/len(vs)
                    if not(3.951<c.z<4.649 and abs(c.x)<7.0 and abs(c.y)>1.1 and f.normal.z>.15):continue
                    # Aperture return walls are not exterior shoulder sheets.
                    if max(abs(abs(p.y)-roof_half_width(p.z)) for p in vs)<2e-4:
                        error=abs(abs(c.y)-roof_half_width(c.z));assert error<2e-4,('bridged fold',error)
                        samples.append(error)
            if lod==2:
                results.append(dict(style=style,lod=lod,visible_roof_windows=5,main_groups=3,main_columns=6,low_grilles=1,profile_samples=len(samples),level_cover_samples=cover_checks));continue
            leaves=[o for o in objects if o.get('roof26_animation_kind')=='louver']
            assert len(leaves)==(40 if lod==0 else 20)
            groups=defaultdict(list)
            for o in leaves:
                pivot=Vector(o['roof26_pivot']);groups[(round(pivot.x,2),1 if pivot.y>0 else -1)].append(o)
                n=Vector(o['roof27_mount_normal']);assert abs(n.dot(Vector(o['roof26_axis'])))<1e-8
            rays=0
            for (x,side),group in groups.items():
                fixed=[o for o in objects if not o.get('roof26_animation_kind') and
                       o.get('roof27_role')!='louver_hinge']
                near=lambda vs:any(abs(p.x-x)<.65 and 3.90<p.z<4.40 and p.y*side>1.15 for p in vs)
                fixed_tree,names=tree(fixed,near)
                for o in group:
                    pivot=Vector(o['roof26_pivot']);ps=points(o)
                    # Straight outward rays from the leaf axis must see no
                    # retained body skin. Deliberate rear wall is behind us.
                    n=Vector(o['roof27_mount_normal'])
                    for dx in (-.22,0,.22):
                        hit=fixed_tree.ray_cast(pivot+Vector((dx,0,0))+n*.004,n,.30)
                        assert hit[0] is None,('skin over aperture',o.name,hit,names[hit[2]])
                        rays+=1
                    for angle in range(0,33):
                        rot=Matrix.Rotation(math.radians(side*angle),3,'X')
                        posed=[pivot+rot@(p-pivot) for p in ps]
                        leaf_tree=BVHTree.FromPolygons(posed,[tuple(f.vertices) for f in o.data.polygons],epsilon=1e-8)
                        overlaps=leaf_tree.overlap(fixed_tree);checks+=1
                        if overlaps:errors.append(dict(leaf=o.name,angle=angle,hit=sorted(set(names[j] for _,j in overlaps))))
                # The combined leaf sweep must also avoid adjacent leaves.
                for angle in range(0,33):
                    ts=[]
                    for o in group:
                        pivot=Vector(o['roof26_pivot']);rot=Matrix.Rotation(math.radians(side*angle),3,'X')
                        ts.append(tree_pose(o,pivot,rot))
                    for a,c in zip(ts,ts[1:]):assert not a.overlap(c),('leaf-leaf collision',x,side,angle)
            # Check horizontal rotor surfaces against all nearby fixed roof
            # components, except intended axle-to-hub bearing interfaces.
            rotor_groups=defaultdict(list)
            for o in objects:
                if o.get('roof26_animation_kind')=='fan':rotor_groups[o['roof26_animation_group']].append(o)
            fan_checks=0
            for name,objs in rotor_groups.items():
                pivot=Vector(objs[0]['roof26_pivot'])
                fixed=[o for o in objects if not o.get('roof26_animation_kind') and
                       not o.name.startswith(('roof26_fan_shaft','roof26_fan_motor'))]
                near=lambda vs:any(abs(p.x-pivot.x)<.38 and 3.94<p.z<4.66 and -1.7<p.y<-.2 for p in vs)
                ft,names=tree(fixed,near)
                for angle in range(0,360,10):
                    rot=Matrix.Rotation(math.radians(angle),3,'Y')
                    for o in objs:
                        overlaps=tree_pose(o,pivot,rot).overlap(ft);fan_checks+=1
                        if overlaps:errors.append(dict(fan=o.name,angle=angle,hit=sorted(set(names[j] for _,j in overlaps))))
            result=dict(style=style,lod=lod,visible_roof_windows=5,main_columns=6,main_groups=3,low_grilles=1,profile_samples=len(samples),level_cover_samples=cover_checks,leaf_body_frame_samples=checks,
                aperture_rays=rays,rotor_body_guard_samples=fan_checks,errors=errors,
                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            from native_patch_v23 import decode
            correspondence=[]
            by_group=defaultdict(list)
            for o in objects:
                if o.get('roof26_animation_kind'):by_group[o['roof26_animation_group']].append(o)
            for part in manifest['animated']:
                if part['style']!=style or part['lod']!=lod:continue
                group=part['name'][len('fxn5c_v26_'):-len(f'_lod{lod}')]
                ps=[p for o in by_group[group] for p in points(o)]
                kd=KDTree(len(ps))
                for i,p in enumerate(ps):kd.insert(p,i)
                kd.balance();_,arrays,_,_=decode(ROOT/part['target'],part['materials'])
                error=max(kd.find(Vector(p)+Vector(part['pivot']))[2] for p in arrays['position'])
                assert error<3e-5,('native/source animation mismatch',part['name'],error)
                correspondence.append(dict(name=part['name'],max_error_m=error))
            result['animated_native_correspondence']=correspondence
            results.append(result)
            (ROOT/'roof_geometry_v34.json').write_text(json.dumps(dict(status='RUNNING',scenes=results),indent=2))
            assert not errors,errors[:5]
            print('GEOMETRY30_PASS',style,lod,checks,fan_checks,flush=True)
    (ROOT/'roof_geometry_v34.json').write_text(json.dumps(dict(status='PASS',scenes=results,
        engine_tested=False,scope='saved source mesh sampled collision and exterior profile audit'),indent=2))

def tree_pose(o,pivot,rot):
    ps=[pivot+rot@(p-pivot) for p in points(o)]
    return BVHTree.FromPolygons(ps,[tuple(f.vertices) for f in o.data.polygons],epsilon=1e-8)
if __name__=='__main__':main()
