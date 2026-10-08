"""Scoped exterior reconstruction from supplied 0021/0018/0029 and 0071 video.

Visible dimensions are fitted, not engineering claims. Keep cab transverse
folds, fan shafts and existing shutter hinges. Replace local exhaust geometry,
keep access covers level longitudinally, align side radiators to the fan bay.
"""
import bpy
from mathutils import Vector,Matrix
import math
from roof_revision_v24 import _clip_mesh,_edit,roof_half_width
from roof_revision_v27 import points,remove
from geometry_v02 import Builder as BaseBody
from geometry_v05 import split_polygon

def clip_scoped(o,planes,bounds,keep=lambda p:True):
    # Keep original vertex indices for untouched polygons. Rebuilding the
    # entire shell changed legacy cab ngon tessellation in Jinwen distant LOD.
    old=o.data;tf=o.matrix_world;inv=tf.inverted();ps=points(o)
    verts=[tuple(v.co) for v in old.vertices];faces=[];materials=[];smooth=[]
    for f in old.polygons:
        vs=[ps[i] for i in f.vertices]
        if any(max(p[i] for p in vs)<=a+1e-7 or min(p[i] for p in vs)>=b-1e-7 for i,(a,b) in enumerate(bounds)):
            faces.append(tuple(f.vertices));materials.append(f.material_index);smooth.append(f.use_smooth);continue
        parts=[[tuple(p) for p in vs]]
        for plane in planes:parts=[q for part in parts for q in split_polygon(part,plane)]
        for part in parts:
            if not keep(sum((Vector(p) for p in part),Vector())/len(part)):continue
            start=len(verts);verts.extend(tuple(inv@Vector(p)) for p in part)
            faces.append(tuple(range(start,len(verts))));materials.append(f.material_index);smooth.append(f.use_smooth)
    mesh=bpy.data.meshes.new(old.name+'_scoped28');mesh.from_pydata(verts,[],faces)
    for mat in old.materials:mesh.materials.append(mat)
    for f,m,s in zip(mesh.polygons,materials,smooth):f.material_index=m;f.use_smooth=s
    mesh.update();o.data=mesh

def tag(o,role):o['roof28_role']=role;return o

def add_radiator_supports(b):
    if b.lod==2:return
    assert not any(o.name.startswith('roof28_radiator_support') for o in bpy.context.scene.objects)
    for side in (-1,1):
        for x in (4.105,4.835):
            for z in (2.074,2.906,2.964,3.796):
                # Tie each fin's ends to the core and outer frame; all these
                # parts overlap the rail rather than hanging in the dark well.
                tag(BaseBody.box(b,'roof28_radiator_support',(x,side*1.625,z),(.650,.100,.016),'graphite'),'radiator_support')

def settle_fittings(b):
    if b.lod==2:return
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        if o.name.startswith('trapezoid_roof_shoulder_screw'):
            ps=points(o);c=sum(ps,Vector())/len(ps)
            if -2.40<c.x<-1.00 and .24<abs(c.y)<1.30:remove(o)
    for side in (-1,1):
        pads=[o for o in bpy.context.scene.objects if o.name.startswith('roof_eye_pad_v06')
              and abs(sum(p.x for p in points(o))/len(points(o))-.1)<.01
              and sum(p.y for p in points(o))*side>0]
        if not pads:continue
        pad=pads[0];ps=points(pad);c=sum(ps,Vector())/len(ps);anchor=Vector((c.x,c.y,min(p.z for p in ps)))
        lid_z=surface(c.y)+.008+.025
        new=Vector((c.x,c.y,lid_z))
        # No pitch around Y: the cover and its fittings are level along X.
        tf=Matrix.Translation(new)@Matrix.Translation(-anchor)
        eyes=[o for o in bpy.context.scene.objects if o.name.startswith('roof_lifting_eye_v06')
              and abs(sum(p.x for p in points(o))/len(points(o))-.1)<.01
              and sum(p.y for p in points(o))*side>0]
        for o in [pad]+eyes:o.matrix_world=tf@o.matrix_world;o['roof28_fitting_reseated']=True

def surface(y):
    y=abs(y)
    if y<=roof_half_width(4.65):return 4.65
    if y<=1.34:return 4.28+(1.34-y)*.425/.86
    return 3.95+(1.65-y)*.33/.31

def cutbox(o,x0,x1,y0,y1,z0,z1):
    ps=points(o)
    if not ps or any(max(p[i] for p in ps)<a or min(p[i] for p in ps)>b for i,(a,b) in enumerate(((x0,x1),(y0,y1),(z0,z1)))):return
    planes=[lambda p:p[0]-x0,lambda p:p[0]-x1,lambda p:p[1]-y0,lambda p:p[1]-y1,lambda p:p[2]-z0,lambda p:p[2]-z1]
    clip_scoped(o,planes,((x0,x1),(y0,y1),(z0,z1)),lambda p:not(x0+1e-7<p.x<x1-1e-7 and y0+1e-7<p.y<y1-1e-7 and z0+1e-7<p.z<z1-1e-7))

def radiators(b,jw,report):
    # Rebuild the tall bank at its reference-aligned station; move the roof bay
    # to it separately, instead of moving the bank toward the wrong roof station.
    prefixes=('filter_','vertical_filter_')
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(prefixes):report['removed'].append(o.name);remove(o)
    for side in (-1,1):
        for x in (4.105,4.835):
            # Rectangular painted-shell aperture, not a black patch over skin.
            for o in list(bpy.context.scene.objects):
                if b.lod<2 and o.name.startswith('body_open_shell'):
                    y0,y1=sorted((side*1.57,side*1.75))
                    cutbox(o,x-.325,x+.325,y0,y1,2.06,3.81)
            def panel(name,x0,x1,z0,z1,offset,mat='blue',painted=False):
                verts=[(u,side*(1.65+offset),z) for u,z in ((x0,z0),(x1,z0),(x1,z1),(x0,z1))]
                if painted:o=b.paint_mesh(name,side,[verts])
                else:o=b.poly(name,verts,[(0,1,2,3)],mat,normal=(0,side,0))
                tag(o,'side_radiator')
                if jw and painted:
                    from jinwen_livery_v20 import paint_mesh
                    paint_mesh(o,b.g)
                return o
            panel('roof28_radiator_back',x-.325,x+.325,2.06,3.81,.003 if b.lod==2 else -.068,'grille_black')
            if b.lod==2:
                panel('roof28_radiator_crossframe',x-.325,x+.325,2.922,2.948,.006,painted=True)
                continue
            for lo,hi in ((x-.348,x-.321),(x+.321,x+.348)):
                panel('roof28_radiator_frame',lo,hi,2.035,3.835,.020,painted=True)
            for z in (2.047,2.935,3.823):
                panel('roof28_radiator_crossframe',x-.348,x+.348,z-.013,z+.013,.020,painted=True)
            if b.lod==2:continue
            # Visible fine vertical fins, kept orthogonal to the side wall.
            count=32 if b.lod==0 else 16
            for z0,z1 in ((2.07,2.912),(2.958,3.80)):
                for i in range(count):
                    u=x-.308+i*.616/(count-1)
                    panel('roof28_radiator_fin',u-.0035,u+.0035,z0,z1,.008,painted=True)
                    tag(BaseBody.box(b,'roof28_radiator_fin_web',(u,side*1.637,(z0+z1)/2),(.005,.036,z1-z0),'graphite'),'radiator_web')
            # Returns join front frame to the recessed dark radiator core.
            for u in (x-.325,x+.325):
                tag(b.poly('roof28_radiator_return',[(u,side*y,z) for y,z in ((1.582,2.06),(1.67,2.06),(1.67,3.81),(1.582,3.81))],[(0,1,2,3)],'graphite',normal=(1,0,0)),'radiator_return')
    report['side_radiator_centers']=[4.105,4.835]

def align_fan_bay(b,jw,report):
    # 0018 full-side reference puts the twin bay over the tall bank, about
    # 30% of body length from that cab. The old bay was 1.62 m too far inward.
    moving=[]
    prefixes=('roof20_','roof26_shroud','roof26_fan','roof26_cage',
              'roof27_fan_','roof27_guard_','roof27_far_','roof27_distant_guard')
    for o in bpy.context.scene.objects:
        if o.name.startswith(prefixes):
            o.location.x+=1.62
            if o.get('roof26_animation_kind')=='fan':
                pivot=list(o['roof26_pivot']);pivot[0]+=1.62;o['roof26_pivot']=pivot
            moving.append(o.name)
    # Cut the destination roof completely, including overlapping older sheets.
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or o.name in moving or o.name.startswith(('bounds|','glazing_','light24_','cab_interior')):continue
        ps=points(o)
        if not ps:continue
        if o.name.startswith(('body_open_shell','trapezoid_roof_deck','roof24_distant')):
            for a,c in ((2.10,3.60),(3.72,5.22)):cutbox(o,a,c,-2,2,3.95,5.0)
        elif min(p.x for p in ps)>3.72 and max(p.x for p in ps)<5.22 and min(p.z for p in ps)>3.95:
            report['removed'].append(o.name);remove(o)
    # Close the vacated bay with a continuous cab-derived two-slope panel.
    profile=[(-roof_half_width(z),z) for z in (3.95,4.24,4.28,4.65)]
    profile += [(roof_half_width(z),z) for z in (4.65,4.28,4.24,3.95)]
    for (y,z),(v,w) in zip(profile,profile[1:]):
        ps=[(2.10,y,z),(3.60,y,z),(3.60,v,w),(2.10,v,w)]
        mat='jw_roof' if jw else ('blue' if max(z,w)<=4.24 else 'roof')
        tag(b.poly('roof28_vacated_bay_skin',ps,[(0,1,2,3)],mat,normal=(0,1 if y>0 else -1,1)),'vacated_bay_skin')
    report['fan_bay_shift_x']=1.62;report['fan_bay_interval']=[3.72,5.22]

def exhaust(b,jw,report):
    old=('lateral_exhaust','exhaust_pocket','exhaust_rim','folded_exhaust','segmented_folded_mouth')
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(old):report['removed'].append(o.name);remove(o)
    paint='jw_roof' if jw else 'roof'
    x0,x1=-2.40,-1.00
    if b.lod==2:
        # Distant proxy follows the existing shoulder, without the sub-pixel
        # inner duct and return walls. Detailed LODs keep actual cut openings.
        for side in (-1,1):
            vs=[(x,side*y,surface(y)+.003) for x,y in ((-2.10,.61),(-1.30,.61),(-1.30,.91),(-2.10,.91))]
            tag(b.poly('roof28_distant_exhaust',vs,[(0,1,2,3)],'grille_black',normal=(0,side,1)),'distant_exhaust')
        report['exhaust_emitter_z']=4.675
        return
    shells=[o for o in bpy.context.scene.objects if o.name.startswith(('body_open_shell','trapezoid_roof_deck','roof24_distant_center_roof'))]
    for side in (-1,1):
        for o in shells:
            ya,yb=sorted((side*.24,side*1.30));cutbox(o,x0,x1,ya,yb,4.265,5.)
        def p(x,y,z):return(x,side*y,z)
        def sheet(name,ps,mat=paint,role='exhaust_well'):
            return tag(b.poly(name,ps,[tuple(range(len(ps)))],mat,normal=(0,side,1)),role)
        # Roof cut follows the shoulder to a visibly lowered floor. All walls
        # terminate on the retained roof edges; nothing floats over the shell.
        sheet('roof28_exhaust_floor',[p(x0,.24,4.27),p(x1,.24,4.27),p(x1,1.30,4.27),p(x0,1.30,4.27)],'grille_black')
        for x in (x0,x1):
            sheet('roof28_exhaust_end',[p(x,.24,4.27),p(x,1.30,4.27),p(x,1.30,surface(1.30)),p(x,.591,4.65),p(x,.24,4.65)])
        for y in (.24,1.30):
            sheet('roof28_exhaust_return',[p(x0,y,4.27),p(x1,y,4.27),p(x1,y,surface(y)),p(x0,y,surface(y))])
        # Open rectangular outlet with an outward rising mouth, not a flush
        # oval insert. Physical routing below the pocket is intentionally absent.
        a,c=-2.10,-1.30;ya,yb=.61,.91
        ring=[p(a,ya,4.58),p(c,ya,4.58),p(c,yb,4.63),p(a,yb,4.63)]
        low=[p(a,ya,4.27),p(c,ya,4.27),p(c,yb,4.27),p(a,yb,4.27)]
        inner=[p(a+.024,ya+.024,4.584),p(c-.024,ya+.024,4.584),p(c-.024,yb-.024,4.626),p(a+.024,yb-.024,4.626)]
        for i in range(4):
            j=(i+1)%4
            sheet('roof28_exhaust_neck',[low[i],low[j],ring[j],ring[i]],'exhaust_steel','exhaust_neck')
            sheet('roof28_exhaust_lip',[ring[i],ring[j],inner[j],inner[i]],'spring_steel','exhaust_lip')
            sheet('roof28_exhaust_inner',[inner[i],inner[j],(inner[j][0],inner[j][1],4.31),(inner[i][0],inner[i][1],4.31)],'grille_black','exhaust_inner')
    report['exhaust_emitter_z']=4.675

def covers(b,jw,report):
    # User correction: the long edges are parallel to the vehicle side, not
    # fore/aft wedges. Only the transverse roof profile changes their height.
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(('roof_lid_','roof25_shoulder_service_lid','roof25_lid_gasket')):
            report['removed'].append(o.name);remove(o)
    paint='jw_roof' if jw else 'roof'
    for x0,x1 in ((-.72,.38),(.50,1.73)):
        for side in (-1,1):
            def p(x,y,z):return(x,side*y,z)
            # Include the crown/shoulder fold; bridging it with one quad would
            # sink the middle of the panel through the underlying roof skin.
            knee=roof_half_width(4.65)
            outline=((x0,.16),(x1,.16),(x1,knee),(x1,1.12),(x0,1.12),(x0,knee))
            footprint=[p(x,y,surface(y)) for x,y in outline]
            lid=[Vector(v)+Vector((0,0,.033)) for v in footprint]
            tag(b.poly('roof29_level_access_cover',lid,[(0,1,2,5),(5,2,3,4)],paint,normal=(0,side,1)),'raised_cover')
            if b.lod==2:continue
            for i in range(len(lid)):
                j=(i+1)%len(lid)
                tag(b.poly('roof28_cover_return',[footprint[i],footprint[j],lid[j],lid[i]],[(0,1,2,3)],'graphite' if i==4 else paint,normal=(0,side,1)),'cover_return')
            if b.lod<2:
                tag(b.tube('roof28_cover_edge',lid+[lid[0]],.006,'spring_steel',sides=4),'cover_edge')
    report['access_cover_longitudinal_rise_m']=0.0
    # Raise only local removable roof sections, with short ramp transitions at
    # their ends. Preserve the two-slope cab, AC pockets and fan guard unchanged.
    if b.lod==2:return
    rows=[(5.22,0),(5.40,.035),(6.1,.035),(6.30,.075),(6.55,.075),(6.94,0)]
    def dz(x):
        if x<rows[0][0] or x>rows[-1][0]:return 0.
        for (a,h),(c,j) in zip(rows,rows[1:]):
            if a<=x<=c:return h+(j-h)*(x-a)/(c-a)
        return 0.
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or o.name.startswith(('roof27_','roof28_','bounds|','glazing_','light24_','cab_interior')):continue
        ps=points(o)
        if not ps or max(p.x for p in ps)<5.22 or min(p.x for p in ps)>6.94 or max(p.z for p in ps)<4.28:continue
        if o.name.startswith(('body_open_shell','trapezoid_roof_deck','roof24_distant')):
            clip_scoped(o,[lambda p,x=x:p[0]-x for x,_ in rows]+[lambda p:p[2]-4.28],((5.22,6.94),(-2,2),(4.28,5)))
        _edit(o,lambda p:(p.x,p.y,p.z+dz(p.x)*max(0,min(1,(p.z-4.28)/.37))),'v28_local_roof_sections')
    report['roof_local_heights']=rows

def apply(b,jw=False):
    assert not bpy.context.scene.get('roof28_applied')
    report=dict(lod=b.lod,jinwen=jw,removed=[],dimensions='visual estimates from references')
    align_fan_bay(b,jw,report);radiators(b,jw,report);add_radiator_supports(b);exhaust(b,jw,report);covers(b,jw,report);settle_fittings(b)
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();b.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['roof28_applied']=True
    return report
