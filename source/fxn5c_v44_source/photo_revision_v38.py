"""Scoped static refinements from five user-supplied in-service photographs.

All dimensions are visual fits, not manufacturer CAD. No source photo pixels
are used as textures. The v37 kinetic leaves, fans and running gear are kept.
"""
from pathlib import Path
import bpy
from mathutils import Vector
from geometry_v02 import Builder as BaseBody
from roof_cab_v26 import surface_z
from roof_revision_v24 import roof_half_width
from livery_revision_v21 import _split_attributes
from china_livery_v20 import KNOTS,paint_bands

BLUE_TOP=4.48
EXHAUST_SCALE=.53
CLOSE_FAN_PANELS=False  # User choice; do not infer from another bank's shutters.
PAINT_PREFIXES=('body_open_shell','trapezoid_roof_deck','roof24_distant',
    'cab26_level_equipment_hood','roof28_vacated_bay_skin','roof33_fan_join_skin',
    'roof25_panel_joint','roof27_guard_rib','roof27_guard_edge','roof27_fan_bay_end',
    'roof25_radiator_edge','roof25_radiator_divider','roof28_radiator_frame')
PART_PREFIXES=('roof28_exhaust_neck','roof28_exhaust_lip','roof28_exhaust_inner',
    'cab26_ac_pocket_end','window30_roof_blade','photo38_',
    'anti_climber_front_return_v12','anti_climber_web_v12')

def selected_objects():
    import front_photo_v38 as front
    names={o.name for o in front.selected_objects()}
    return [o for o in bpy.context.scene.objects if o.type=='MESH' and
        not o.get('roof26_animation_kind') and
        (o.name in names or o.name.startswith(PAINT_PREFIXES+PART_PREFIXES) or
         (CLOSE_FAN_PANELS and o.name.startswith(('roof28_radiator_fin','roof28_radiator_crossframe','roof28_radiator_back'))))]

def repaint_shoulder(o,b):
    """Split colour in existing faces, retaining UVs and loop normals."""
    old=o.data;keys=[Path(m.name).name for m in old.materials]
    if 'roof' not in keys:return 0
    tf=o.matrix_world;inv=tf.inverted();wp=[tf@v.co for v in old.vertices]
    if not wp or min(p.z for p in wp)>BLUE_TOP or max(p.z for p in wp)<4.24:return 0
    normals=[tuple(n.vector) for n in old.corner_normals]
    layers=list(old.uv_layers);verts=[tuple(v.co) for v in old.vertices]
    fs=[];mi=[];smooth=[];ns=[];uvs=[[] for _ in layers];mats=list(old.materials)
    for key in ('blue','light_blue'):
        if key not in keys:keys.append(key);mats.append(b.mat(key))
    changed=0
    def retain(f):
        fs.append(tuple(f.vertices));mi.append(f.material_index);smooth.append(f.use_smooth)
        ns.extend(normals[i] for i in f.loop_indices)
        for j,l in enumerate(layers):uvs[j].extend(tuple(l.data[i].uv) for i in f.loop_indices)
    for f in old.polygons:
        pts=[wp[i] for i in f.vertices]
        if keys[f.material_index]!='roof' or max(p.z for p in pts)<4.23999 or min(p.z for p in pts)>BLUE_TOP or min(abs(p.x) for p in pts)>9.18 or max(abs(p.y) for p in pts)<.75:
            retain(f);continue
        poly=[(*wp[vi],*[v for l in layers for v in l.data[li].uv],*normals[li]) for vi,li in zip(f.vertices,f.loop_indices)]
        parts=[poly]
        for plane in (lambda p:p[2]-4.24,lambda p:p[2]-BLUE_TOP,lambda p:p[0]-9.18,lambda p:p[0]+9.18):
            parts=[s for q in parts for s in _split_attributes(q,plane)]
        local=[]
        for q in parts:
            z=sum(p[2] for p in q)/len(q);x=sum(p[0] for p in q)/len(q)
            if 4.24-1e-6<z<BLUE_TOP+1e-6 and abs(x)<9.18:
                qparts=[q]
                # Only these cyan control spans can reach this high shoulder.
                # Dense lower-body gold-arch knots would needlessly tessellate
                # large remote roof panels, particularly the far LOD.
                for knot in [s*k for k in (3.0,3.8,4.6) for s in (-1,1)]:
                    if min(p[0] for p in q)<knot<max(p[0] for p in q):
                        qparts=[t for r in qparts for t in _split_attributes(r,lambda p,k=knot:p[0]-k)]
                for n in (2,3):qparts=[t for r in qparts for t in _split_attributes(r,lambda p,n=n:p[2]-paint_bands(p[0])[n])]
                local.extend(qparts)
            else:local.append(q)
        for q in local:
            c=sum((Vector(p[:3]) for p in q),Vector())/len(q)
            index=f.material_index
            if 4.24-1e-6<c.z<BLUE_TOP+1e-6 and abs(c.x)<9.18 and abs(c.y)>.75:
                cyan=paint_bands(c.x)[2:]
                index=keys.index('light_blue' if cyan[0]<c.z<cyan[1] else 'blue');changed+=1
            start=len(verts);verts.extend(tuple(inv@Vector(p[:3])) for p in q)
            fs.append(tuple(range(start,len(verts))));mi.append(index);smooth.append(f.use_smooth)
            for p in q:
                ns.append(tuple(Vector(p[-3:]).normalized()))
                for j in range(len(layers)):uvs[j].append(tuple(p[3+2*j:5+2*j]))
    if not changed:return 0
    mesh=bpy.data.meshes.new(old.name+'_photo38');mesh.from_pydata(verts,[],fs)
    for m in mats:mesh.materials.append(m)
    for f,i,s in zip(mesh.polygons,mi,smooth):f.material_index=i;f.use_smooth=s
    for layer,values in zip(layers,uvs):
        dest=mesh.uv_layers.new(name=layer.name)
        for uv,val in zip(dest.data,values):uv.uv=val
    mesh.update();mesh.normals_split_custom_set(ns);o.data=mesh
    o['photo38_role']='roof_shoulder_paint';return changed

def recolor(o,b,key):
    o.data.materials.clear();o.data.materials.append(b.mat(key))
    for f in o.data.polygons:f.material_index=0

def coamings(b,jw):
    paint='jw_roof' if jw else 'roof';made=[]
    # The 70-mm rim is sub-pixel at the far LOD. Keep the original silhouette
    # proxy there instead of exceeding its established 6000-triangle budget.
    if b.lod==2:return made
    # Two finite-thickness transverse edge ribs per cab. Their bottoms follow
    # the existing surface; the opening, aircon, floor and footprint stay put.
    for end in (-1,1):
        for x,sgn in ((8.14,-1),(9.14,1)):
            ya=[-1.02,-.60,.60,1.02]
            verts=[]
            for xx,dz in ((x+sgn*.14,0),(x,.070)):
                verts.extend((end*xx,y,surface_z(xx,y)+dz) for y in ya)
            # Lower ring is attached directly to the retained roof sheet.
            verts += [(end*xx,y,surface_z(xx,y)-.006) for xx in (x+sgn*.14,x) for y in ya]
            faces=[(i,i+1,5+i,4+i) for i in range(3)]
            faces += [(8+i,12+i,13+i,9+i) for i in range(3)]
            faces += [(i,8+i,9+i,i+1) for i in range(3)]
            faces += [(4+i,5+i,13+i,12+i) for i in range(3)]
            faces += [(0,4,12,8),(3,11,15,7)]
            o=BaseBody.poly(b,'photo38_ac_coaming',verts,faces,paint,solid=True)
            o['photo38_role']='attached_ac_opening_coaming';made.append(o.name)
    return made

def close_fan_panels(b,jw):
    made=[]
    # Do not remove the radiator core/fins: model the photographed closed
    # exterior covers in front of them, leaving the fitted recess intact.
    for side in (-1,1):
        for x in (4.105,4.835):
            for za,zb in ((2.074,2.912),(2.958,3.796)):
                x0,x1=x-.319,x+.319;y=side*1.662
                vs=[(u,y,z) for u,z in ((x0,za),(x1,za),(x1,zb),(x0,zb))]
                o=BaseBody.poly(b,'photo38_fan_bank_closed_panel',vs,[(0,1,2,3)],'blue',normal=(0,side,0))
                if jw:
                    from jinwen_livery_v20 import paint_mesh
                    from livery_revision_v21 import _repaint_side_mesh
                    paint_mesh(o,b.g);_repaint_side_mesh(o,b)
                else:
                    from china_livery_v20 import repaint
                    repaint(o,b)
                o['photo38_role']='closed_fan_bank_cover';made.append(o.name)
    return made

def apply(b,jw=False):
    import front_photo_v38 as front
    report=dict(lod=b.lod,jinwen=jw,photo_evidence='User five in-service FXN5C photos, received 2026-09-28',
                dimensions='visual fit only; profile retained',changed=[],shoulder_blue_top=BLUE_TOP if not jw else None)
    for o in list(selected_objects()):
        if not jw and o.name.startswith(PAINT_PREFIXES):
            n=repaint_shoulder(o,b)
            if n:report['changed'].append(dict(name=o.name,paint_faces=n))
        if o.name.startswith(('roof28_exhaust_neck','roof28_exhaust_lip','roof28_exhaust_inner')):
            inv=o.matrix_world.inverted()
            for v in o.data.vertices:
                p=o.matrix_world@v.co;p.z=4.27+(p.z-4.27)*EXHAUST_SCALE;v.co=inv@p
            o.data.update();o['photo38_role']='low_recessed_exhaust'
            if 'lip' in o.name:recolor(o,b,'exhaust_steel')
            report['changed'].append(dict(name=o.name,exhaust_height_scale=EXHAUST_SCALE))
        if o.name.startswith('window30_roof_blade'):
            recolor(o,b,'graphite');o['photo38_role']='dark_static_shoulder_louver'
            report['changed'].append(dict(name=o.name,paint='graphite'))
        if jw and o.name.startswith(('anti_climber_front_return_v12','anti_climber_web_v12')):
            recolor(o,b,'jw_white');report['changed'].append(dict(name=o.name,paint='jw_white'))
    report['coamings']=coamings(b,jw)
    report['closed_fan_bank']=close_fan_panels(b,jw) if CLOSE_FAN_PANELS else []
    report['front']=front.apply(b,jw)
    # Only new meshes need UV generation; retained UV layers are left intact.
    b.g.ensure_uvs();bpy.context.view_layer.update()
    report['v37_animations']='unchanged, including fixed-open large shutters'
    return report
