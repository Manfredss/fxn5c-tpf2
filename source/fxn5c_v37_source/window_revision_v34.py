"""User-directed bilateral window layout and horizontal-X radiator shutters.

Start from immutable final v33 scenes. 7009 video at 25.676 s confirms the
horizontal visible blades; 55 degrees / 12 seconds are display approximations.
"""
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody
from window_revision_v30 import ROOF_WINDOWS,SIDE_COLUMNS,MAIN_WIDTH,Z0,Z1,center
from roof_revision_v29 import cutbox
from roof_revision_v27 import remove,vent_basis
from roof_revision_v24 import roof_half_width
from china_livery_v20 import repaint
from jinwen_livery_v20 import paint_mesh as jw_paint
from livery_revision_v21 import _repaint_side_mesh

ROW_COUNTS={0:13,1:7}  # Per half, across all six columns at a common X axis.
PIVOT_Y=1.663
MAX_ANGLE=55
PERIOD=12000

def mirror(o):
    ps=[o.matrix_world@v.co for v in o.data.vertices]
    mesh=bpy.data.meshes.new(o.data.name+'_mirror34')
    mesh.from_pydata([(p.x,-p.y,p.z) for p in ps],[],[tuple(reversed(f.vertices)) for f in o.data.polygons])
    for m in o.data.materials:mesh.materials.append(m)
    for f,old in zip(mesh.polygons,o.data.polygons):f.material_index=old.material_index;f.use_smooth=False
    mesh.update();new=bpy.data.objects.new(o.name+'_other34',mesh);bpy.context.collection.objects.link(new)
    for k,v in o.items():new[k]=v
    new['window34_mirror_of']=o.name;new['window34_side']=-1;o['window34_side']=1
    return new

def leaf(b,jw,x,side,z,h,row):
    # Top-edge pivot: the bottom of each horizontal leaf lifts outward/up.
    x0,x1=x-MAIN_WIDTH/2+.016,x+MAIN_WIDTH/2-.016
    y=side*PIVOT_Y;depth=.004;z0,z1=z-h,z
    vs=[(u,y+side*d,zz) for u,d,zz in ((x0,0,z0),(x1,0,z0),(x1,0,z1),(x0,0,z1),
                                      (x0,-depth,z0),(x1,-depth,z0),(x1,-depth,z1),(x0,-depth,z1))]
    o=BaseBody.poly(b,'window34_radiator_leaf',vs,[(0,1,2,3),(7,6,5,4),(0,4,5,1),
                      (1,5,6,2),(2,6,7,3),(3,7,4,0)],'graphite',solid=True)
    o.data.materials.append(b.mat('blue'))
    for f in o.data.polygons:
        if f.normal.y*side>.5:f.material_index=1
    if jw:jw_paint(o,b.g);_repaint_side_mesh(o,b)
    else:repaint(o,b)
    o['window34_role']='radiator_leaf';o['window34_side']=side;o['window34_column']=x
    o['roof26_animation_kind']='side_louver'
    o['roof26_animation_group']=f'louver_side_{"p" if side>0 else "m"}_{row:02}'
    o['roof26_pivot']=(-4.845,y,z);o['roof26_axis']=(1,0,0);o['roof26_direction']=side
    return o

def apply(b,jw=False):
    assert not bpy.context.scene.get('windows34_applied')
    removed=[];mirrored=[]
    # Remove the superseded opposite-side banks and the old extra low grille.
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        c=center(o)
        old=c.y<-.8 and ((o.name.startswith(('louver_','folded_louver','small_access','access_panel_screw','fastener_drive_slot'))
            and -8.3<c.x<-2.5 and 1.97<c.z<3.9) or o.name.startswith('shoulder_vent') or
            (o.name.startswith('auxiliary_grille') and 6.8<c.x<7.8))
        # Replace only large-bank vertical fins; keep low grilles and fan-bank
        # vertical radiator fins, which are different structures in the video.
        new=o.get('window30_role')=='main_window' and o.name.startswith(('window30_side_fin','window30_side_support'))
        distant=b.lod==2 and o.get('window30_role')=='main_window' and o.name.startswith('window30_side_divider')
        if old or new or distant:removed.append(o.name);remove(o)
    originals=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('window30_role') and center(o).y>0]
    for o in originals:mirrored.append(mirror(o).name)
    if b.lod<2:
        skins=[o for o in bpy.context.scene.objects if o.name.startswith(('body_open_shell','carbody_sheet_joint'))]
        for x,w,za,zb in [(x,MAIN_WIDTH,Z0,Z1) for x in SIDE_COLUMNS]+[(-7.61,1.15,2.15,3.01)]:
            for o in skins:cutbox(o,x-w/2,x+w/2,-1.76,-1.57,za,zb)
        tangent,_=vent_basis(-1)
        for x,w in ROOF_WINDOWS:
            for o in list(bpy.context.scene.objects):
                if o.name.startswith(('body_open_shell','trapezoid_roof_deck','roof28_vacated_bay_skin')):
                    cutbox(o,x-w/2,x+w/2,-1.80,-1.20,4.125-.176*tangent.z,4.125+.176*tangent.z)
        mid=(Z0+Z1)/2;row=0
        for za,zb in ((Z0+.014,mid-.015),(mid+.015,Z1-.014)):
            pitch=(zb-za)/ROW_COUNTS[b.lod]
            for i in range(ROW_COUNTS[b.lod]):
                z=za+(i+1)*pitch-.003;h=pitch-.006
                for side in (-1,1):
                    for x in SIDE_COLUMNS:
                        leaf(b,jw,x,side,z,h,row)
                        # A shaft bridges leaf ends to the fixed side jambs.
                        shaft=BaseBody.box(b,'window34_radiator_hinge',(x,side*(PIVOT_Y-.002),z),
                                         (MAIN_WIDTH+.008,.004,.004),'graphite')
                        shaft['window34_role']='radiator_hinge';shaft['window34_side']=side
                row+=1
        # Four returns per bank, actual solid rails, hide the car interior in
        # open poses and connect the recess to its fixed painted jamb.
        for side in (-1,1):
            for x in SIDE_COLUMNS:
                for xx in (x-MAIN_WIDTH/2+.004,x+MAIN_WIDTH/2-.004):
                    o=BaseBody.box(b,'window34_radiator_jamb',(xx,side*1.630,(Z0+Z1)/2),(.008,.078,Z1-Z0),'graphite')
                    o['window34_role']='radiator_jamb';o['window34_side']=side
                for zz in (Z0+.004,Z1-.004):
                    o=BaseBody.box(b,'window34_radiator_sill',(x,side*1.630,zz),(MAIN_WIDTH,.078,.008),'graphite')
                    o['window34_role']='radiator_sill';o['window34_side']=side
    from planar_shading_v13 import apply_planar_normals
    apply_planar_normals();b.g.ensure_uvs();bpy.context.view_layer.update()
    bpy.context.scene['windows34_applied']=True
    return dict(lod=b.lod,jinwen=jw,removed=removed,mirrored=mirrored,
        user_authority='both sides use repaired +Y window dimensions/positions/counts',
        evidence='BV1muMA6GEov at 25.676 s: horizontal blades; motion direction user-specified',
        approximate_animation=dict(axis='X',max_degrees=MAX_ANGLE,period_ms=PERIOD),
        static_low_grille_and_fan_bank_retained=True)
