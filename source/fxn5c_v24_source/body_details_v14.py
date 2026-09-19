"""Production-car visible details, photo estimates; not factory dimensions.

0051/0050 original photographs establish horizontal radiator shutters, a pair
of vertically ribbed double-height filters, rectangular roof screens and inset
exhausts. Do not transplant the red 0001 prototype's side-facing roof fans.
"""
import math
import bpy
from geometry_v02 import Builder as BaseBody


def tag(obj, value):
    obj['detail_v12_component'] = value
    return obj


def remove(prefixes):
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(prefixes):
            bpy.data.objects.remove(obj, do_unlink=True)


def small(b,name,loc,dims,mat='roof'):
    return BaseBody.box(b,name,loc,dims,mat)


def vertical_filter(b,side,x):
    """Two separate inset filter panels in one tall removable frame."""
    z=2.91; w=.71; h=1.74
    b.side_rect('filter_shadow_v12',side,x,z,w-.018,h-.018,'grille_black',.005)
    b.panel_ring('filter_gasket_v12',side,x,z,w+.012,h+.012,.012,'black',.008)
    tag(b.panel_ring('filter_outer_frame_v12',side,x,z,w,h,.027,'blue',.026),'vertical_filter_bank')
    for cz in (2.477,3.343):
        b.panel_ring('filter_half_frame_v12',side,x,cz,w-.058,.827,.018,'blue',.028)
        polygons=[]; count=35 if b.lod==0 else 17
        for i in range(count):
            xx=x-(w-.118)/2+i*(w-.118)/(count-1)
            # Narrow folded fins: genuine relief, the gap remains visible.
            for a,da,c,dc in ((-.005,.012,0,.027),(0,.027,.006,.013)):
                polygons.append([(xx+a,side*(1.65+da),cz-.386),(xx+c,side*(1.65+dc),cz-.386),
                                 (xx+c,side*(1.65+dc),cz+.386),(xx+a,side*(1.65+da),cz+.386)])
        tag(b.paint_mesh('vertical_filter_fins_v12',side,polygons),'vertical_filter_insert')
    b.painted_panel('filter_divider_v12',side,x,z,w-.035,.033,.032,.004)
    if b.lod==0:
        for zz in (2.15,3.66):
            for dx in (-.29,.29): b.flush_screw('filter_frame_screw_v12',x+dx,side,zz,.031,.006)
        for zz in (2.45,3.30):
            b.cyl('filter_hinge_v12',(x-.359,side*1.681,zz),.008,.055,'blue','Z')


def refine_roof(b):
    """Retain independently located roof modules, refine their visible skin."""
    remove(('radiator_screen_wire','radiator_screen_crosswire'))
    # Less open than v11's wire fence; keep the cooling fans in their dark well.
    for obj in bpy.context.scene.objects:
        if obj.name.startswith(('concealed_fan_blade','radiator_fan_hub','recessed_fan_shroud')):
            obj.location.z-=.052
            obj.data.materials.clear(); obj.data.materials.append(b.mat('grille_black'))
            for face in obj.data.polygons: face.material_index=0
    nx,ny=(107,73) if b.lod==0 else (54,37)
    for i in range(nx):
        small(b,'radiator_long_grid_v12',(-7.18+i*3.16/(nx-1),0,4.582),(.009,2.14,.007),'graphite')
    for i in range(ny):
        small(b,'radiator_cross_grid_v12',(-5.60,-1.07+i*2.14/(ny-1),4.588),(3.16,.008,.006),'graphite')
    for x in (-6.99,-6.51,-6.03,-5.55,-5.07,-4.59,-4.22):
        for y in (-.91,.91):
            tag(small(b,'radiator_mesh_fixing_v12',(x,y,4.596),(.058,.032,.012),'metal'),'radiator_grid_fixing')
    # The wide cross-shoulder grille has an inset light-coloured stack under
    # the guard mesh, visible in the originals. It is not a black roof plate.
    from roof_details_v07 import vent_z
    for side in (-1,1):
        for i in range(26 if b.lod==0 else 13):
            x=2.16+i*1.38/(25 if b.lod==0 else 12)
            ys=(side*1.07,side*1.50)
            b.poly('crossvent_inset_fin_v12',[(x-.007,y,vent_z(y)-.017) for y in ys]+
                   [(x+.007,y,vent_z(y)-.017) for y in reversed(ys)],[(0,1,2,3)],'metal',normal=(0,side,1))
    # Replace the smoothly rolled lip, not the proven deck holes. Both retained
    # mouths remain explicitly a cross-view reconstruction, not surveyed CAD.
    remove(('recessed_oval_exhaust_duct','exhaust_rolled_mouth_edge','segmented_exhaust_lip_v08'))
    from roof_details_v07 import EXHAUST_OUTLETS
    for x,y,_ in EXHAUST_OUTLETS:
        loop=[(-.38,-.085),(-.285,-.165),(.205,-.165),(.365,-.080),
              (.385,.075),(.240,.158),(-.225,.158),(-.395,.055)]
        outer=[(x+u,y+v) for u,v in loop]
        inner=[(x+u*.91,y+v*.82) for u,v in loop]
        obj=b.rim('folded_exhaust_duct_v12',outer,inner,lambda u,v:(u,v,4.605),'exhaust_steel',.098,(0,0,1))
        tag(obj,'faceted_exhaust_duct')
        vertices=[]; faces=[]
        # Unequal flat lips, instead of a smooth circular/capsule nozzle.
        for i,(p,q) in enumerate(zip(outer,outer[1:]+outer[:1])):
            segs=max(1,round(math.dist(p,q)/.14)); start=len(vertices)
            for j in range(segs):
                for t,z in ((j/segs,4.600),(j/segs,4.634),((j+.62)/segs,4.634),
                            ((j+.64)/segs,4.612),((j+1)/segs,4.612),((j+1)/segs,4.600)):
                    vertices.append((p[0]+(q[0]-p[0])*t,p[1]+(q[1]-p[1])*t,z))
                faces.append(tuple(range(start+j*6,start+(j+1)*6)))
        obj=b.poly('segmented_folded_mouth_v12',vertices,faces,'exhaust_steel',normal=(0,0,1))
        mod=obj.modifiers.new('sheet_thickness','SOLIDIFY'); mod.thickness=.005
        bpy.context.view_layer.objects.active=obj; bpy.ops.object.modifier_apply(modifier=mod.name)
        tag(obj,'segmented_exhaust_mouth')
        b.evidence_counts['segmented_exhaust_lip']+=0  # inherited two replaced, counted once
    roof_lids(b)


def roof_lids(b):
    """0050/0051 and 0047/0064/0067 show two adjacent long hatches, not three."""
    remove(('roof_access_base_v07','roof_access_lid_v07','roof_access_hinge_v07',
            'roof_access_flush_lock_v07','roof_access_lock_slot_v07','roof_lid_v12',
            'roof_lid_base_v12','roof_lid_hinge_v12','roof_lid_lock_v12','roof_lid_slot_v12'))
    for x in (.03,1.18):
        small(b,'roof_lid_base_v12',(x,0,4.649),(1.128,1.75,.018),'black')
        obj=small(b,'roof_lid_v12',(x,0,4.666),(1.107,1.728,.023),'roof')
        b.bevel(obj,.005,1)
        b.feature(obj,'roof_access_lid')
        tag(obj,'paired_roof_access_lid')
        if b.lod==0:
            for y in (-.58,.58):
                b.cyl('roof_lid_hinge_v12',(x-.552,y,4.681),.011,.100,'spring_steel','Y')
                b.cyl('roof_lid_lock_v12',(x+.47,y,4.681),.010,.005,'spring_steel','Z')
                small(b,'roof_lid_slot_v12',(x+.47,y,4.684),(.014,.0025,.002),'black')


def refine_front_hardware(b):
    remove(('anti_climber_folded_shelf','anti_climber_vertical_web','thin_anti_climber_shelf_v12',
            'anti_climber_front_return_v12','anti_climber_web_v12','wiper_service_plate_v12',
            'wiper_pull_return_v12','wiper_service_pull_v12','outboard_oblique_joint_v12',
            'cab_hazard_stencil_v12','cab_hazard_lightning_v12'))
    from nose_shell_v14 import corner_x,front_half
    for end in (-1,1):
        # Three thin horizontal anti-climbing shelves and three narrow webs.
        # P01/P0060 show thin plate edges, not thick solid stair blocks.
        for side in (-1,1):
            for z in (1.592,1.676,1.765):
                tag(small(b,'thin_anti_climber_shelf_v12',(end*11.096,side*.64,z),(.106,.95,.010),'spring_steel'),'thin_anticlimber_shelf')
                small(b,'anti_climber_front_return_v12',(end*11.151,side*.64,z-.005),(.009,.95,.015),'graphite')
            for y in (.23,.64,1.07):
                small(b,'anti_climber_web_v12',(end*11.091,side*y,1.675),(.095,.012,.187),'graphite')
        if b.lod==0:
            for side in (-1,1):
                # Follow the actual oblique shell with a restrained panel seam,
                # completing the inner-low / outer-high boundary seen on 0060.
                pts=[]
                for i in range(13):
                    z=2.285
                    y=front_half(2.285)+(1.645-front_half(2.285))*i/12
                    pts.append((end*(corner_x(y,z)+.002),side*y,z))
                # A flush sheet joint, not a proud pipe: the real crease is
                # already part of the shell topology at this height.
                verts=[]
                for x,y,z in pts:
                    verts.extend(((x,y,z-.00065),(x,y,z+.00065)))
                b.poly('outboard_oblique_joint_v12',verts,
                       [(2*i,2*i+2,2*i+3,2*i+1) for i in range(len(pts)-1)],
                       'graphite',normal=(end,side,0))
                for label,z in (('电化区段',2.492),('禁止攀登',2.378)):
                    obj=b.text('cab_hazard_stencil_v12',label,(end*11.05,side*1.562,z),.035,
                               (math.pi/2,0,end*math.pi/2),'white',True)
                    for vertex in obj.data.vertices:
                        point=obj.matrix_world@vertex.co
                        point.x=end*(corner_x(point.y,point.z)+.0015)
                        vertex.co=obj.matrix_world.inverted()@point
                # Explicit paint outline avoids the font's missing U+26A1 box.
                bolt=[(-.004,.026),(.012,.026),(.001,.005),(.012,.005),
                      (-.010,-.026),(-.003,-.003),(-.013,-.003)]
                points=[]
                for dy,dz in bolt:
                    y=side*(1.562+dy); z=2.442+dz
                    points.append((end*(corner_x(y,z)+.0017),y,z))
                b.poly('cab_hazard_lightning_v12',points,[tuple(range(len(points)))],
                       'white',normal=(end,side,0))
                # Low recessed pull under each wiper drive, seen on 0051/0060.
                y=side*.23; z=2.661
                b.front_rect('wiper_service_plate_v12',end,y,2.707,.275,.161,'roof',.024)
                for dy in (-.079,.079):
                    b.front_rod('wiper_pull_return_v12',end,(y+dy,z),(y+dy,z+.027),.006,'black',.053)
                b.front_rod('wiper_service_pull_v12',end,(y-.079,z+.027),(y+.079,z+.027),.006,'black',.053)


def windshield_lower_surround(b):
    """Photo-derived lower mask extent; keep the verified glass openings intact."""
    from geometry_v06 import chamfer_polygon
    remove(('angular_windshield_surround',))
    for end in (-1,1):
        outer=chamfer_polygon([(-1.392,2.560),(1.392,2.560),(1.335,3.985),(-1.335,3.985)],.020)
        inner=chamfer_polygon([(-1.224,2.784),(1.224,2.784),(1.141,3.919),(-1.141,3.919)],.012)
        obj=b.rim('angular_windshield_surround',outer,inner,
            lambda y,z,e=end:(e*(b.front_x(z)+.016),y,z),'roof',.035,(end,0,0))
        b.feature(obj,'angular_surround')
        tag(obj,'extended_lower_windshield_surround')
