"""Jinwen exterior correction against user drawings 2 and logo 4.

Only the Jinwen variants are changed here. The left-facing cab in drawing 2 is
the opposite physical end to the game shot: grilles, tanks and louvers are not
mirrored to mimic that viewing direction. X/Z roof and blue/white/red boundary
stations from v21 are retained. The missing white lower fascia is painted on,
and made flush with, the existing side member: no floating billboard is added.
"""
from pathlib import Path
import bpy
from mathutils import Vector,geometry
from lettering_v20 import fitted_text
from jwr_vector_v23 import JWR_REFERENCE_CONTOURS

DEPOT_FONT=Path('C:/Windows/Fonts/simsun.ttc')
DEPOT_WIDTH=.78
DEPOT_HEIGHT=.146
DEPOT_Z=3.695
DECAL_OFFSET=.0007
CAB_LOGO_WIDTH=.70
CAB_LOGO_Z=2.181
LOWER_LOGO_WIDTH=.36
LOWER_LOGO_Z=1.53
GAUGE_X=.19
LOGO_RIGHT_OFFSET=.34
FASCIA_Y=1.65
REFERENCE_BOUNDS=(89.5,160.5,550.5,479.5)


def bounds(obj):
    ps=[obj.matrix_world@v.co for v in obj.data.vertices]
    return [[min(p[i] for p in ps),max(p[i] for p in ps)] for i in range(3)]


def _material(obj,b,key):
    obj.data.materials.clear();obj.data.materials.append(b.mat(key))
    for face in obj.data.polygons:face.material_index=0


def _triangle_area(a,b,c):
    return abs((b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x))*.5


def _reference_triangles(group):
    loops=[[Vector((x,y,0)) for x,y in loop] for loop in group['contours']]
    def signed_area(loop):
        return sum(a.x*b.y-b.x*a.y for a,b in zip(loop,loop[1:]+loop[:1]))*.5
    def inside(p,loop):
        hit=False
        for a,b in zip(loop,loop[1:]+loop[:1]):
            if (a.y>p.y)!=(b.y>p.y) and p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x:
                hit=not hit
        return hit
    # Blender scanfill can connect separate contours whose bounding boxes
    # overlap (e.g. independent strokes of Chinese characters). Tessellate
    # each connected island with only its own clockwise hole loops.
    outer=[p for p in loops if signed_area(p)>0]
    holes=[p for p in loops if signed_area(p)<0]
    triangles=[]
    assigned=0
    for perimeter in outer:
        inner=[p for p in holes if inside(p[0],perimeter)]
        assigned+=len(inner)
        island=[perimeter]+inner
        flat=[p for loop in island for p in loop]
        triangles.extend(tuple(flat[i] for i in tri) for tri in geometry.tessellate_polygon(island))
    assert assigned==len(holes),('Unassigned logo counters',group['name'])
    signed=sum(sum(a.x*b.y-b.x*a.y for a,b in zip(loop,loop[1:]+loop[:1]))*.5 for loop in loops)
    triangle_area=sum(_triangle_area(*tri) for tri in triangles)
    assert abs(abs(signed)-triangle_area)<.2,('JWR contours lost holes',group['name'],signed,triangle_area)
    return triangles


def _mark(b,name,x,side,z,width):
    """Full lockup, including authentic custom Chinese and English outlines."""
    lowx,lowy,highx,highy=REFERENCE_BOUNDS
    scale=width/(highx-lowx);cx=(lowx+highx)/2;cy=(lowy+highy)/2
    result=[]
    for group in JWR_REFERENCE_CONTOURS:
        # Beyond the LOD1 transition these rows are below a screen pixel.
        # Preserve cab symbol + Chinese, and lower fascia symbol; LOD0 always
        # contains the complete six 3-row lockups from the supplied reference.
        if b.lod==1 and (group['name']=='en' or (name.startswith('jw23_lower') and group['name']=='cn')):
            continue
        verts=[];faces=[]
        for tri in _reference_triangles(group):
            face=[]
            for p in tri:
                xx=x-side*(p.x-cx)*scale
                zz=z-(p.y-cy)*scale
                face.append(len(verts))
                yy=FASCIA_Y if name.startswith('jw23_lower') else b.side_y(xx,zz)
                verts.append((xx,side*(yy+DECAL_OFFSET),zz))
            faces.append(tuple(face))
        obj=b.poly(name+'_'+group['name'],verts,faces,'jw_blue',normal=(0,side,0))
        obj['livery23_fixed_branding']=True
        obj['livery23_role']='full_JWR_lockup_'+group['name']
        obj['livery23_reference']='User supplied logo figure 4; silhouette and letter outlines'
        obj['livery23_side']=side
        obj['livery23_offset']=DECAL_OFFSET
        obj['livery23_lockup_width']=width
        result.append(obj)
    return result


def paint_geometry(b):
    """Call before common filler seating, so it can inspect the corrected host."""
    changed=[]
    sill=bpy.data.objects.get('chassis_sill') or bpy.data.objects.get('distant_chassis')
    if sill is None:raise AssertionError('Expected editable chassis_sill/distant_chassis geometry')
    if not sill.get('livery23_flush_fascia'):
        tf=sill.matrix_world.copy();inv=tf.inverted()
        before=bounds(sill)
        moved=0
        old_y=1.59 if sill.name=='distant_chassis' else 1.61
        for v in sill.data.vertices:
            p=tf@v.co
            if abs(abs(p.y)-old_y)<2e-5:
                p.y=FASCIA_Y if p.y>0 else -FASCIA_Y
                v.co=inv@p;moved+=1
        assert moved>=8,('No sill side skin vertices',moved)
        # Inner aperture returns keep their X/Z stations; white fascia meets
        # the body sheet, not a new overlaid plate spanning the bogie opening.
        white_index=len(sill.data.materials)
        sill.data.materials.append(b.mat('jw_white'))
        white_faces=0
        for face in sill.data.polygons:
            ys=[(tf@sill.data.vertices[i].co).y for i in face.vertices]
            if max(ys)-min(ys)<1e-5 and abs(abs(ys[0])-FASCIA_Y)<1e-5:
                face.material_index=white_index;white_faces+=1
        assert white_faces>=2
        sill.data.update()
        sill['livery23_flush_fascia']=True
        sill['livery23_before_bounds']=str(before)
        sill['livery23_moved_outer_vertices']=moved
        sill['livery23_white_exterior_faces']=white_faces
        changed.append(sill.name)
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        # Maintenance markings on the now-white exterior must remain visible.
        # Actual running gear, springs, reservoir cans and cupboards stay gray.
        if obj.name.startswith(('body_technical_stencil','body_jacking_label')):
            _material(obj,b,'graphite')
            obj['livery23_contrast_on_white']=True
            changed.append(obj.name)
    return changed


def apply(b,jinwen=False):
    """Postprocess a v22 source, or the equivalent unmerged rebuilt LOD scene.

    Does not touch livery21 variable-number tags or invoke numbering again.
    Returns explicit replacement geometry inventories for native-delta export.
    """
    if not jinwen:return {'jinwen':False,'changed':[],'deleted':[],'added':[]}
    changed=paint_geometry(b)
    deleted=[]
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('jinwen_depot','jinwen_jwr_logo_v19','jinwen_cab_operator','jw23_')):
            deleted.append(obj.name);bpy.data.objects.remove(obj,do_unlink=True)
    added=[]
    if b.lod<2:
        if not DEPOT_FONT.is_file():raise FileNotFoundError(DEPOT_FONT)
        for side in (-1,1):
            # Center the white-band label over the reading-order title block,
            # rather than leaving physical X=.30 unchanged on the far side.
            obj=fitted_text(b,'jw23_depot_'+str(side),'金温·温段',-side*.30,
                            side,DEPOT_Z,DEPOT_WIDTH,DEPOT_HEIGHT,'jw_blue',DEPOT_FONT)
            for v in obj.data.vertices:
                v.co.y=side*(b.side_y(v.co.x,v.co.z)+DECAL_OFFSET)
            obj.data.update()
            obj['livery23_fixed_branding']=True
            obj['livery23_role']='top_depot_simsun'
            obj['livery23_side']=side
            obj['livery23_offset']=DECAL_OFFSET
            added.append(obj.name)
            for end in (-1,1):
                added.extend(o.name for o in _mark(b,f'jw23_cab_{end}_{side}',end*10.0,side,CAB_LOGO_Z,CAB_LOGO_WIDTH))
            x=GAUGE_X-side*LOGO_RIGHT_OFFSET
            added.extend(o.name for o in _mark(b,f'jw23_lower_{side}',x,side,LOWER_LOGO_Z,LOWER_LOGO_WIDTH))
    b.g.ensure_uvs()
    bpy.context.view_layer.update()
    bpy.context.scene['livery23_lod']=b.lod
    return {'jinwen':True,'changed':changed,'deleted':deleted,'added':added,
            'white_fascia_y':FASCIA_Y,'decal_offset':DECAL_OFFSET,
            'logo_reference_proportions':[461,319],
            'orientation':'asymmetric mechanical stations retained; text reads outward on both sides'}
