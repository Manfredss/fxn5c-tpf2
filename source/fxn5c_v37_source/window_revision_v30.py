"""Photo-mapped windows on the reference-visible (+Y) side only.

0019 reference viewed from its large-radiator/cab end. X+ appears on the left.
Visual fitted dimensions, not surveyed measurements. Hidden -Y side retained.
"""
import bpy
from mathutils import Vector
from roof_revision_v29 import apply as previous_apply,cutbox,clip_scoped,surface
from roof_revision_v27 import points,remove,vent_basis
from roof_revision_v24 import roof_half_width
from geometry_v02 import Builder as BaseBody
from geometry_v05 import split_polygon

ROOF_WINDOWS=((3.40,.28),(1.90,.34),(-1.70,1.05))
MAIN_WIDTH=.545
SIDE_COLUMNS=tuple(c+d for c in (-3.525,-4.845,-6.165) for d in (-.2925,.2925))
Z0,Z1=2.04,3.82

def tag(o,role):o['window30_role']=role;return o

def center(o):
    ps=points(o);return sum(ps,Vector())/len(ps)

def poly(b,name,vs,mat,role,jw=False,paint=False,normal=(0,1,0)):
    if not paint:o=b.poly(name,vs,[tuple(range(len(vs)))],mat,normal=normal)
    elif jw:o=b.poly(name,vs,[tuple(range(len(vs)))],'jw_roof' if min(p[2] for p in vs)>3.95 else 'jw_white',normal=normal)
    else:
        pieces=split_polygon(vs,lambda p:p[2]-4.24) if min(p[2] for p in vs)>3.95 else [vs]
        vertices=[];faces=[];mats=[]
        for piece in pieces:
            a=len(vertices);vertices.extend(piece);faces.append(tuple(range(a,len(vertices))))
            mats.append('roof' if sum(p[2] for p in piece)/len(piece)>4.24 else 'blue')
        o=b.poly(name,vertices,faces,'blue',normal=normal)
        o.data.materials.append(b.mat('roof'))
        for f,m in zip(o.data.polygons,mats):f.material_index=int(m=='roof')
    return tag(o,role)

def roof_windows(b,jw,report):
    for o in list(bpy.context.scene.objects):
        if o.name.startswith('shoulder_vent') and center(o).y>0:
            report['removed'].append(o.name);remove(o)
    t,n=vent_basis(1);z=4.125;half_t=.176
    for x,w in ROOF_WINDOWS:
        c=Vector((x,roof_half_width(z),z))
        def p(u,v,d=0):return tuple(c+Vector((u,0,0))+t*v+n*d)
        hx=w/2
        if b.lod==2:
            poly(b,'window30_roof_proxy',[p(-hx,-half_t,.004),p(hx,-half_t,.004),p(hx,half_t,.004),p(-hx,half_t,.004)],'grille_black','roof_window_proxy')
            continue
        # A genuine recess, including the skin added when the v28 fan bay moved.
        za,zb=z-half_t*t.z,z+half_t*t.z
        for o in list(bpy.context.scene.objects):
            if o.name.startswith(('body_open_shell','trapezoid_roof_deck','roof28_vacated_bay_skin')):
                cutbox(o,x-hx,x+hx,1.20,1.80,za,zb)
        coords=((-hx,-half_t),(hx,-half_t),(hx,half_t),(-hx,half_t))
        poly(b,'window30_roof_back',[p(u,v,-.043) for u,v in coords],'grille_black','roof_window_back')
        for i,(u,v) in enumerate(coords):
            a,d=coords[(i+1)%4]
            poly(b,'window30_roof_return',[p(u,v,-.043),p(a,d,-.043),p(a,d,.004),p(u,v,.004)],'graphite','roof_window_return')
        outer=((-hx-.018,-half_t-.017),(hx+.018,-half_t-.017),(hx+.018,half_t+.017),(-hx-.018,half_t+.017))
        for i in range(4):
            j=(i+1)%4
            poly(b,'window30_roof_frame',[p(*outer[i],.006),p(*outer[j],.006),p(*coords[j],.006),p(*coords[i],.006)],'blue','roof_window_frame',jw,True,n)
        count=9 if b.lod==0 else 5
        step=2*(half_t-.010)/count
        for i in range(count):
            v=-half_t+.010+step*(i+.5)
            poly(b,'window30_roof_blade',[p(-hx+.012,v-step*.35,.004),p(hx-.012,v-step*.35,.004),p(hx-.012,v+step*.35,-.020),p(-hx+.012,v+step*.35,-.020)],'blue','roof_window_blade',jw,True,n)
        # Slats terminate in connected side rails, not unsupported in the well.
        for sign in (-1,1):
            u=sign*(hx-.012)
            poly(b,'window30_roof_rail',[p(u,-half_t,-.043),p(u,half_t,-.043),p(u,half_t,.007),p(u,-half_t,.007)],'graphite','roof_window_rail')
    if b.lod==2:
        # Preserve the same five-window layout at distance; the two animated
        # near-cab openings have no individual animated leaves at this LOD.
        for x in (-7.75,7.60):
            c=Vector((x,roof_half_width(4.115),4.115))
            q=lambda u,v:tuple(c+Vector((u,0,0))+t*v+n*.004)
            poly(b,'window30_cab_proxy',[q(-.28,-.185),q(.28,-.185),q(.28,.185),q(-.28,.185)],'grille_black','roof_window_proxy')
    report['roof_visible_count']=5
    report['roof_window_relocated_centers']=[list(r) for r in ROOF_WINDOWS]

def side_panel(b,jw,x,w,z0,z1,role,split=True):
    def panel(name,a,c,d,e,y,mat='graphite',paint=False):
        vs=[(a,y,d),(c,y,d),(c,y,e),(a,y,e)]
        if paint:
            o=b.paint_mesh(name,1,[vs])
            if jw:
                from jinwen_livery_v20 import paint_mesh
                paint_mesh(o,b.g)
            return tag(o,role)
        return poly(b,name,vs,mat,role)
    half=w/2
    if b.lod<2:
        for o in list(bpy.context.scene.objects):
            if o.name.startswith(('body_open_shell','carbody_sheet_joint')):cutbox(o,x-half,x+half,1.57,1.76,z0,z1)
    back_y=1.655 if b.lod==2 else 1.593
    panel('window30_side_back',x-half,x+half,z0,z1,back_y,'grille_black')
    middle=(z0+z1)/2
    if b.lod==2:
        if split:panel('window30_side_divider',x-half,x+half,middle-.009,middle+.009,1.660,paint=True)
        return
    frame=.014
    for a,c in ((x-half-frame,x-half),(x+half,x+half+frame)):
        panel('window30_side_frame',a,c,z0-frame,z1+frame,1.673,paint=True)
    for zz in ((z0,z1,middle) if split else (z0,z1)):
        panel('window30_side_crossframe',x-half-frame,x+half+frame,zz-frame/2,zz+frame/2,1.673,paint=True)
    for xx in (x-half,x+half):
        poly(b,'window30_side_return',[(xx,1.593,z0),(xx,1.673,z0),(xx,1.673,z1),(xx,1.593,z1)],'graphite',role)
    spans=((z0+.014,middle-.015),(middle+.015,z1-.014)) if split else ((z0+.014,z1-.014),)
    count=(30 if b.lod==0 else 15) if split else (52 if b.lod==0 else 26)
    for za,zb in spans:
        for i in range(count):
            u=x-half+.014+i*(w-.028)/(count-1)
            panel('window30_side_fin',u-.003,u+.003,za,zb,1.661,paint=True)
            # Thin folded returns show real depth behind the painted edge.
            poly(b,'window30_side_fin_web',[(u-.003,1.661,za),(u+.003,1.613,za),(u+.003,1.613,zb),(u-.003,1.661,zb)],'graphite',role)
        for zz in (za,zb):
            tag(BaseBody.box(b,'window30_side_support',(x,1.634,zz),(w,.083,.012),'graphite'),role)

def side_windows(b,jw,report):
    names=('louver_','folded_louver_blades','small_access_gap_v05','small_access_skin_v05')
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        c=center(o)
        if c.y<1.5:continue
        selected=o.name.startswith(names) and -8.30<c.x<-2.50 and 1.97<c.z<3.90
        selected|=o.name.startswith('fastener_drive_slot') and -6.85<c.x<-2.50 and 2.0<c.z<3.85
        # The reference's clear blue panel between the left cab and the tall
        # pair has no low grille. Do not leave this old extra opposite-end unit.
        selected|=o.name.startswith('auxiliary_grille') and 6.8<c.x<7.8
        if selected:report['removed'].append(o.name);remove(o)
    for x in SIDE_COLUMNS:side_panel(b,jw,x,MAIN_WIDTH,Z0,Z1,'main_window')
    side_panel(b,jw,-7.61,1.15,2.15,3.01,'low_window',False)
    report['main_groups']=3;report['main_columns']=6;report['main_half_panels']=12
    report['low_grille']=dict(x=-7.61,width=1.15,z0=2.15,z1=3.01)

def apply(b,jw=False):
    report=previous_apply(b,jw)
    report['reference30']='User 0019 photograph: visible +Y side, X+ on image left'
    roof_windows(b,jw,report);side_windows(b,jw,report)
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();b.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['windows30_applied']=True
    return report
