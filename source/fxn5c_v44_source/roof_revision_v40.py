"""Photo-fitted static roof revision; no factory dimensions are asserted.

Replace the overlapping old roof sheets rather than blanketing their openings.
Retain the calibrated transverse profile, the fan/shutter animation domains,
both AC units, exhaust emitters, cab brow and v39 front-end work. LOD2 is a
strict no-op. All dimensions below are metres in the established body frame.
"""
from pathlib import Path
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody
from roof_revision_v29 import surface
from roof_revision_v24 import roof_half_width
from roof_cab_v26 import surface_z
from livery_revision_v21 import _split_attributes

KNEE=roof_half_width(4.65)
HOOD=(-3.9483,3.72,1.20)
END_HOOD=(5.22,6.94,1.20)
COVERS=((-0.72,.38),(.50,1.73))
SLOTS=((-2.40,-1.00,-1.30,-.24),(-2.40,-1.00,.24,1.30))
HOOD_RISE=.010
COVER_RISE=.024
RAD=(-7.20,-4.00,.14,1.30)
RAD_DEPTH=.065
REMOVED_PREFIX=('roof29_level_access_cover','roof28_cover_return','roof28_cover_edge',
    'trapezoid_roof_deck_v07','radiator_screen_crossframe','radiator_screen_sideframe',
    'radiator_coaming','radiator_well_bottom',
    'radiator_captive_tab','radiator_mesh_clamping_bridge_v08','radiator_long_grid_v12',
    'radiator_cross_grid_v12','radiator_mesh_fixing_v12','roof25_radiator_back',
    'roof25_radiator_return','roof25_radiator_edge','roof25_radiator_divider',
    'roof25_radiator_screw','roof25_radiator_grid_h','roof25_radiator_grid_v',
    'roof27_fan_crown','photo38_ac_coaming')
SHELL_PREFIX=('body_open_shell','roof28_vacated_bay_skin','roof33_fan_join_skin')
FITTING_PREFIX=('roof_eye_pad_v06','roof_lifting_eye_v06','roof_transverse_gasket_v07',
    'roof_recessed_pull_v07','roof_pull_handle_v07','trapezoid_roof_shoulder_screw')


def points(o):return [o.matrix_world@v.co for v in o.data.vertices]


def selected_objects():
    return [o for o in bpy.context.scene.objects if o.type=='MESH' and
        not o.get('roof26_animation_kind') and
        (o.name.startswith(REMOVED_PREFIX+SHELL_PREFIX+FITTING_PREFIX+('roof40_','roof28_exhaust_lip')))]


def _tag(o,role):
    o['roof40_role']=role;o['roof40_dimensions']='visual fit; not OEM dimensions'
    return o


def _drop(o,report):
    report['removed'].append(o.name);bpy.data.objects.remove(o,do_unlink=True)


def _slab(b,name,top,bottom,faces,mat,role):
    """Closed folded sheet, preserving every intentional profile break."""
    n=len(top);edges={}
    for face in faces:
        for i,a in enumerate(face):
            q=face[(i+1)%len(face)];key=tuple(sorted((a,q)))
            if key in edges:del edges[key]
            else:edges[key]=(a,q)
    allfaces=list(faces)+[tuple(i+n for i in reversed(f))for f in faces]
    allfaces += [(a,q,q+n,a+n)for a,q in edges.values()]
    return _tag(BaseBody.poly(b,name,top+bottom,allfaces,mat,solid=True),role)


def _folded_rect(b,name,x0,x1,y0,y1,top,bottom,mat,role):
    ys=sorted({y0,y1,*[y for y in (-KNEE,KNEE)if y0<y<y1]})
    verts=[(x,y,surface(y)+top)for x in (x0,x1)for y in ys]
    lower=[(x,y,surface(y)+bottom)for x in (x0,x1)for y in ys]
    n=len(ys);faces=[(i,i+1,n+i+1,n+i)for i in range(n-1)]
    return _slab(b,name,verts,lower,faces,mat,role)


def _clip_box(o,bounds):
    """Remove only the bounded legacy sheet, retaining UVs and corner normals.

    Old faces outside the scope retain their original vertices and attributes.
    It is intentionally not a blind Boolean through the body/cab interior.
    """
    old=o.data;tf=o.matrix_world;inv=tf.inverted();wp=points(o)
    if not wp or any(max(p[i]for p in wp)<a or min(p[i]for p in wp)>c for i,(a,c)in enumerate(bounds)):return 0
    layers=list(old.uv_layers);normals=[tuple(n.vector)for n in old.corner_normals]
    verts=[tuple(v.co)for v in old.vertices];faces=[];mi=[];smooth=[];ns=[];uvs=[[]for _ in layers]
    changed=0
    def retain(f):
        faces.append(tuple(f.vertices));mi.append(f.material_index);smooth.append(f.use_smooth)
        ns.extend(normals[i]for i in f.loop_indices)
        for k,l in enumerate(layers):uvs[k].extend(tuple(l.data[i].uv)for i in f.loop_indices)
    planes=[lambda p,i=i,a=a:p[i]-a for i,(lo,hi)in enumerate(bounds)for a in (lo,hi)]
    for f in old.polygons:
        ps=[wp[i]for i in f.vertices]
        if any(max(p[i]for p in ps)<=a+1e-7 or min(p[i]for p in ps)>=c-1e-7 for i,(a,c)in enumerate(bounds)):
            retain(f);continue
        poly=[(*wp[vi],*[n for l in layers for n in l.data[li].uv],*normals[li])for vi,li in zip(f.vertices,f.loop_indices)]
        parts=[poly]
        for plane in planes:parts=[q for part in parts for q in _split_attributes(part,plane)]
        for part in parts:
            center=[sum(v[i]for v in part)/len(part)for i in range(3)]
            if all(a+1e-7<center[i]<c-1e-7 for i,(a,c)in enumerate(bounds)):
                changed+=1;continue
            start=len(verts);verts.extend(tuple(inv@Vector(v[:3]))for v in part)
            faces.append(tuple(range(start,len(verts))));mi.append(f.material_index);smooth.append(f.use_smooth)
            for v in part:
                ns.append(tuple(Vector(v[-3:]).normalized()))
                for j in range(len(layers)):uvs[j].append(tuple(v[3+2*j:5+2*j]))
    if not changed:return 0
    mesh=bpy.data.meshes.new(old.name+'_roof40');mesh.from_pydata(verts,[],faces)
    for m in old.materials:mesh.materials.append(m)
    for f,i,s in zip(mesh.polygons,mi,smooth):f.material_index=i;f.use_smooth=s
    for layer,values in zip(layers,uvs):
        dest=mesh.uv_layers.new(name=layer.name)
        for uv,val in zip(dest.data,values):uv.uv=val
    mesh.update();mesh.normals_split_custom_set(ns);o.data=mesh
    _tag(o,'scoped_legacy_roof_aperture');return changed


def _old_rise(x):
    rows=((5.22,0),(5.40,.035),(6.1,.035),(6.30,.075),(6.55,.075),(6.94,0))
    for (a,h),(c,j)in zip(rows,rows[1:]):
        if a<=x<=c:return h+(j-h)*(x-a)/(c-a)
    return 0.


def _unpitch(o):
    inv=o.matrix_world.inverted();moved=set()
    old_normals=[tuple(n.vector)for n in o.data.corner_normals]
    for v in o.data.vertices:
        p=o.matrix_world@v.co;rise=_old_rise(p.x)
        if p.z>4.28 and rise:
            # Invert v29's clamped deformation exactly, including fittings
            # above the crown (which received a uniform offset).
            limit=4.65+rise
            p.z=p.z-rise if p.z>=limit else 4.28+(p.z-4.28)/(1+rise/.37)
            v.co=inv@p;moved.add(v.index)
    if moved:
        o.data.update()
        # Only faces whose vertex positions changed belong in the native
        # triangle delta. Never introduce normal-only edits elsewhere.
        normals=list(old_normals)
        for face in o.data.polygons:
            if any(i in moved for i in face.vertices):
                for li in face.loop_indices:normals[li]=(0,0,0)
        o.data.normals_split_custom_set(normals)
        _tag(o,'levelled_legacy_end_hood')
    return len(moved)


def _hood(b,jw,report):
    paint='jw_roof'if jw else'roof'
    # Grid subdivision follows actual apertures; no roof spans either pit.
    x0,x1,hw=HOOD;xs=(x0,-2.40,-1.00,x1);ys=(-hw,-.24,.24,hw)
    for a,c in zip(xs,xs[1:]):
        for ya,yb in zip(ys,ys[1:]):
            if a==-2.40 and ya!=-.24:continue
            _folded_rect(b,'roof40_continuous_equipment_hood',a,c,ya,yb,HOOD_RISE,-.008,paint,'continuous_equipment_hood')
    _folded_rect(b,'roof40_level_end_hood',*END_HOOD[:2],-END_HOOD[2],END_HOOD[2],HOOD_RISE,-.008,paint,'level_end_hood')
    # Local transverse ridge, with no longitudinal wedge. The installed
    # fittings stay on the same level hood rather than an invented X slope.
    _folded_rect(b,'roof40_low_transverse_rib',5.22,5.34,-1.20,1.20,.035,.006,paint,'low_transverse_rib')
    for a,c in COVERS:
        for side in(-1,1):
            ya,yb=sorted((side*.16,side*1.12))
            o=_folded_rect(b,'roof40_low_inspection_cover',a,c,ya,yb,COVER_RISE,HOOD_RISE-.002,paint,'inspection_cover')
            o['roof40_x_interval']=(a,c);o['roof40_side']=side
            # Four separate thin lids on the broad hood, not thick isolated
            # blocks. A small rear seam and two hinges describe their edges.
            _folded_rect(b,'roof40_cover_seal',a,c,ya,yb,HOOD_RISE+.003,HOOD_RISE,'graphite','cover_seal')
            for x in(a+.13,c-.13):
                y=side*.19
                _tag(BaseBody.box(b,'roof40_cover_hinge',(x,y,surface(y)+COVER_RISE+.004),(.075,.030,.012),paint),'cover_hinge')
    # Cap only the crown and a short conformal shoulder overlap. Its bottom
    # contacts the unchanged guard ribs; neither fan axis nor rotor is edited.
    _folded_rect(b,'roof40_fan_crown_transition',3.72,5.22,-.78,.78,.017,-.008,paint,'fan_crown_transition')
    report['cover_count']=4


def _exhaust(b,jw,report):
    paint='jw_roof'if jw else'roof'
    for o in bpy.context.scene.objects:
        if o.name.startswith('roof28_exhaust_lip'):
            o.data.materials.clear();o.data.materials.append(b.mat('spring_steel'))
            for f in o.data.polygons:f.material_index=0
            _tag(o,'visible_short_exhaust_lip')
    # Tiny raised perimeter follows the inherited cut edge. Original closed
    # recess floors, return walls and low hollow necks are all retained.
    for side in(-1,1):
        for x in(-2.40,-1.00):
            a,c=sorted((side*.24,side*1.30))
            _folded_rect(b,'roof40_exhaust_edge',x-.010,x+.010,a,c,.016,-.004,paint,'exhaust_edge')
    report['exhaust_emitter_positions_unchanged']=[(-1.70,-.76,4.4758),(-1.70,.76,4.4758)]
    report['exhaust_short_outlet_top']=4.4608


def _radiator(b,jw,report):
    a,c,inner,outer=RAD;paint='jw_blue'if jw else'blue'
    # Both banks contain a real recessed plenum with four returns and an
    # open screen above it. A blue narrow centre walkway separates the banks.
    _folded_rect(b,'roof40_radiator_center_walkway',a,c,-inner,inner,.013,-.080,paint,'radiator_center_walkway')
    for side in(-1,1):
        ya,yb=sorted((side*inner,side*outer))
        _folded_rect(b,'roof40_radiator_recess_back',a,c,ya,yb,-RAD_DEPTH,-RAD_DEPTH-.008,'grille_black','radiator_recess_back')
        for x in(a,c):
            _folded_rect(b,'roof40_radiator_end_return',x-.014,x+.014,ya,yb,.007,-RAD_DEPTH-.008,'graphite','radiator_end_return')
        for y in(ya,yb):
            _folded_rect(b,'roof40_radiator_long_return',a,c,y-.012,y+.012,.007,-RAD_DEPTH-.008,'graphite','radiator_long_return')
        # Six visually separate screened sections per bank. Their webs descend
        # to the back and therefore physically support the wire lattice.
        for i in range(7):
            x=a+(c-a)*i/6
            _folded_rect(b,'roof40_radiator_section_rib',x-.011,x+.011,ya,yb,.013,-RAD_DEPTH,'graphite','radiator_section_rib')
            if b.lod==0:
                for y in(ya+.045,yb-.045):
                    _tag(BaseBody.box(b,'roof40_radiator_captive_tab',(x,y,surface(y)+.020),(.055,.040,.014),'spring_steel'),'radiator_captive_tab')
        # Thin solid strips, not duplicate top and side cages. Near retains
        # visible wire depth; middle uses fewer bars to respect its budget.
        across=25 if b.lod==0 else 13
        along=81 if b.lod==0 else 37
        for i in range(across):
            y=ya+.018+(yb-ya-.036)*i/(across-1)
            _folded_rect(b,'roof40_radiator_long_wire',a+.012,c-.012,y-.0018,y+.0018,.008,.003,'graphite','radiator_wire')
        for i in range(along):
            x=a+.018+(c-a-.036)*i/(along-1)
            _folded_rect(b,'roof40_radiator_cross_wire',x-.0016,x+.0016,ya+.014,yb-.014,.011,.007,'graphite','radiator_wire')
    report['radiator_sections_per_bank']=6
    report['radiator_center_walkway_width']=2*inner


def _ac_rims(b,jw):
    # Cases and circular grilles already lie below the 4.65-m crown. Only
    # reduce the inherited 70-mm edge ramp to a modest 35-mm folded rim.
    paint='jw_roof'if jw else'roof'
    for end in(-1,1):
        for x,sgn in((8.14,-1),(9.14,1)):
            ya=(-1.02,-.60,.60,1.02);top=[];bottom=[]
            for xx,dz in((x+sgn*.10,0),(x,.035)):
                top.extend((end*xx,y,surface_z(xx,y)+dz)for y in ya)
                bottom.extend((end*xx,y,surface_z(xx,y)-.006)for y in ya)
            _slab(b,'roof40_ac_opening_rim',top,bottom,[(i,i+1,5+i,4+i)for i in range(3)],paint,'low_ac_opening_rim')


def audit_parameters():
    return dict(profile=[(y,surface(y))for y in(-1.65,-1.34,-1.20,-KNEE,0,KNEE,1.20,1.34,1.65)],
        continuous_hood=dict(x=HOOD[:2],half_width=HOOD[2],rise=HOOD_RISE),
        end_hood=dict(x=END_HOOD[:2],half_width=END_HOOD[2],longitudinal_rise=0),
        covers=[dict(x=(a,c),y=(s*.16,s*1.12),rise=COVER_RISE,
                     samples=[(x,s*y,surface(y)+COVER_RISE)for x in(a,c)for y in(.16,KNEE,1.12)])
                for a,c in COVERS for s in(-1,1)],
        exhaust_slots=SLOTS,exhaust_floor_z=4.270,exhaust_top_z=4.4608,
        radiator=dict(x=(RAD[0],RAD[1]),inner_y=RAD[2],outer_y=RAD[3],depth=RAD_DEPTH,sections=6),
        fan_crown=dict(x=(3.72,5.22),half_width=.78),
        source_photos=('02235294-f427-412a-83c3-375e57096e4a','cdd48826-0ab1-4573-a3d2-57c723f97adf'),
        limitations='Photo-fitted roof details, not measured sections; AC cases and all animation pivots unchanged.')


def check_scene(lod):
    """Read-only targeted validation for an already constructed final scene.

    This checks geometry, not game execution. Baseline fingerprints/pivot
    equality remain the integrating build's independent responsibility.
    """
    from collections import Counter
    import math
    from mathutils.bvhtree import BVHTree
    made=[o for o in bpy.context.scene.objects if o.type=='MESH'and o.name.startswith('roof40_')]
    if lod==2:
        assert not made,'far-LOD new roof geometry'
        return dict(status='SOURCE_STATIC_PASS',lod=lod,new_meshes=0,far_proxy='unchanged')
    def group(role):return [o for o in made if o.get('roof40_role')==role]
    def tree(objects):
        vs=[];fs=[]
        for o in objects:
            n=len(vs);vs.extend(points(o));fs.extend(tuple(n+i for i in f.vertices)for f in o.data.polygons)
        return BVHTree.FromPolygons(vs,fs)
    for o in made:
        assert not o.get('roof26_animation_kind') and not o.parent,(o.name,'unexpected animation/parent')
        edge=Counter(tuple(sorted((f.vertices[i],f.vertices[(i+1)%len(f.vertices)])))for f in o.data.polygons for i in range(len(f.vertices)))
        assert set(edge.values())=={2},(o.name,'open/nonmanifold new sheet')
        assert all(math.isfinite(c)for v in o.data.vertices for c in v.co),o.name
        assert all(f.area>1e-10 for f in o.data.polygons),(o.name,'zero area')
    assert len(group('inspection_cover'))==4
    # Every cover's two X ends have identical transverse coordinates/heights.
    for o in group('inspection_cover'):
        rows={}
        for p in points(o):rows.setdefault(round(p.y,5),{}).setdefault(round(p.x,5),[]).append(p.z)
        for xs in rows.values():
            assert len(xs)==2,o.name
            values=[sorted(v)for v in xs.values()]
            assert max(abs(a-b)for a,b in zip(*values))<1e-6,(o.name,'X slope')
        for p in points(o):
            d=p.z-surface(p.y)
            assert min(abs(d-COVER_RISE),abs(d-(HOOD_RISE-.002)))<1e-6,(o.name,'cover installation')
    hood=tree(group('continuous_equipment_hood'))
    floors=tree([o for o in bpy.context.scene.objects if o.name.startswith('roof28_exhaust_floor')])
    rays=[]
    for side in(-1,1):
        for x in(-2.30,-1.10):
            for y in(.35,1.10):
                origin=Vector((x,side*y,5.0));direction=Vector((0,0,-1))
                assert hood.ray_cast(origin,direction,.8)[0]is None,'hood caps exhaust pit'
                hit=floors.ray_cast(origin,direction,1.)[0]
                assert hit is not None and abs(hit.z-4.270)<1e-5,'exhaust floor missing'
                rays.append(dict(x=x,y=side*y,floor_z=hit.z))
    assert len(group('radiator_section_rib'))==14
    assert len(group('radiator_recess_back'))==2
    # New support webs end exactly on the new back sheet, not in mid-air.
    for o in group('radiator_section_rib'):
        ds=[p.z-surface(p.y)for p in points(o)]
        assert abs(min(ds)+RAD_DEPTH)<1e-6 and abs(max(ds)-.013)<1e-6,o.name
    for o in group('radiator_recess_back'):
        ds=[p.z-surface(p.y)for p in points(o)]
        assert abs(max(ds)+RAD_DEPTH)<1e-6,o.name
    # AC hardware highest point was already below the 4.65 crown.
    ac=[p.z for o in bpy.context.scene.objects if o.type=='MESH'and o.name.startswith(('cab_aircon_case_v06','cab_aircon_lid','ac_circular_lid_grille_rim'))for p in points(o)]
    assert ac and max(ac)<4.651
    assert not any(o.type=='MESH'and o.name.startswith(REMOVED_PREFIX)for o in bpy.context.scene.objects),'stale replaced roof geometry'
    return dict(status='SOURCE_STATIC_PASS',lod=lod,new_meshes=len(made),all_new_sheets_closed=True,
        inspection_covers=4,cover_longitudinal_rise=0,radiator_sections_per_bank=6,
        radiator_support_contact=True,exhaust_slot_rays=rays,retained_ac_max_z=max(ac),
        limitations='Not engine-tested; baseline animation/untouched-object checks are separate.')


def apply(b,jw=False):
    report=dict(lod=b.lod,jinwen=jw,removed=[],modified=[],audit=audit_parameters(),
        validation='source geometry only; no engine claim')
    if b.lod==2:
        report['distant_proxy']='strictly unchanged';return report
    assert not bpy.context.scene.get('roof40_applied')
    original=list(selected_objects())
    # Undo only the historically tagged local longitudinal pitch first.
    for o in original:
        if not o.name.startswith(REMOVED_PREFIX) and o.get('roof24_operation')=='v28_local_roof_sections':
            n=_unpitch(o)
            if n:report['modified'].append(dict(name=o.name,unpitched_vertices=n))
    kept=[o for o in original if not o.name.startswith(REMOVED_PREFIX)]
    for o in original:
        if o.name.startswith(REMOVED_PREFIX):_drop(o,report)
    for o in kept:
        if o.name.startswith(SHELL_PREFIX):
            for a,c,hw in(HOOD,END_HOOD):
                n=_clip_box(o,((a,c),(-hw,hw),(4.32,4.90)))
                if n:report['modified'].append(dict(name=o.name,hood_faces_removed=n))
            # Remove the old flat roof under the two replacement screens.
            n=_clip_box(o,((RAD[0],RAD[1]),(-RAD[3],RAD[3]),(4.24,4.90)))
            if n:report['modified'].append(dict(name=o.name,radiator_faces_removed=n))
        if o.name.startswith(FITTING_PREFIX):
            ps=points(o)
            if not ps:continue
            x=sum(p.x for p in ps)/len(ps);y=sum(p.y for p in ps)/len(ps)
            if abs(x-.10)<.12:
                o.location.z-=.009;_tag(o,'cover_fitting_reseated')
            elif END_HOOD[0]<x<END_HOOD[1] and abs(y)<1.20:
                o.location.z+=HOOD_RISE;_tag(o,'end_hood_fitting_reseated')
    _hood(b,jw,report);_exhaust(b,jw,report);_radiator(b,jw,report);_ac_rims(b,jw)
    b.g.ensure_uvs();bpy.context.view_layer.update();bpy.context.scene['roof40_applied']=True
    report['made']=[o.name for o in bpy.context.scene.objects if o.name.startswith('roof40_')]
    return report
