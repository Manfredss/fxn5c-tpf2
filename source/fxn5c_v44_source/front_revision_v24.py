"""Raise existing nose emblems/text and interrupt only Jinwen's blue belt.

The shared +100 mm is a visual fit to the supplied frontal drawings, not a
factory dimension. Existing glyph size, lateral spacing, individual surface
relief and geometry are preserved. The blue band is split inside actual front
skin polygons, preserving UVs/normals; no floating white mask is introduced.
The lower red belt and all side markings/stripes remain untouched.
"""
from pathlib import Path
import bpy
from mathutils import Vector
from livery_revision_v21 import _split_attributes

SHIFT_Z=.10
BLUE_Z=(1.865,1.925)
BLUE_GAP_HALF_WIDTH=.55


def _raise_mark(obj,b):
    if obj.get('front24_shifted'):
        return False
    end=int(obj.get('emblem_end',obj.get('front11_end',obj.get('livery21_end',0))))
    assert end in (-1,1),(obj.name,'unresolved front end')
    transform=obj.matrix_world.copy();inverse=transform.inverted()
    points=[transform@v.co for v in obj.data.vertices]
    old_bounds=[min(p.z for p in points),max(p.z for p in points)]
    offsets=[]
    for vertex,p in zip(obj.data.vertices,points):
        offset=end*p.x-b.front_x(p.z)
        assert 0<offset<.01,('Front marking not seated before translation',obj.name,offset)
        offsets.append(offset)
        p.z+=SHIFT_Z
        p.x=end*(b.front_x(p.z)+offset)
        vertex.co=inverse@p
    obj.data.update()
    obj['front24_shifted']=True
    obj['front24_shift_z_m']=SHIFT_Z
    obj['front24_old_z_bounds']=old_bounds
    obj['front24_original_relief_range']=[min(offsets),max(offsets)]
    if obj.get('emblem_end'):
        obj['emblem_center_z_m']=float(obj['emblem_center_z_m'])+SHIFT_Z
    return True


def _break_blue(obj,b):
    if obj.get('front24_blue_band_split'):return False
    old=obj.data
    keys=[Path(mat.name).name for mat in old.materials]
    if 'jw_blue' not in keys:return False
    transform=obj.matrix_world.copy();inverse=transform.inverted()
    world=[transform@v.co for v in old.vertices]
    normals=[tuple(n.vector) for n in old.corner_normals]
    layers=list(old.uv_layers)
    vertices=[tuple(v.co) for v in old.vertices]
    faces=[];indices=[];flags=[];new_normals=[];uvs=[[] for _ in layers]
    mats=list(old.materials)
    white=keys.index('jw_white') if 'jw_white' in keys else len(mats)
    if white==len(mats):mats.append(b.mat('jw_white'))
    changed=0
    def retain(face):
        faces.append(tuple(face.vertices));indices.append(face.material_index);flags.append(face.use_smooth)
        new_normals.extend(normals[i] for i in face.loop_indices)
        for j,layer in enumerate(layers):uvs[j].extend(tuple(layer.data[i].uv) for i in face.loop_indices)
    for face in old.polygons:
        points=[world[i] for i in face.vertices]
        lo,hi=min(p.z for p in points),max(p.z for p in points)
        front=all(abs(abs(p.x)-b.front_x(p.z))<2e-5 for p in points)
        eligible=(keys[face.material_index]=='jw_blue' and front
                  and max(p.y for p in points)>-BLUE_GAP_HALF_WIDTH
                  and min(p.y for p in points)<BLUE_GAP_HALF_WIDTH
                  and hi>BLUE_Z[0]+1e-6 and lo<BLUE_Z[1]-1e-6)
        if not eligible:
            retain(face);continue
        # The inherited livery already clips both horizontal band borders.
        # Reject a changed baseline instead of spreading white beyond them.
        assert lo>=BLUE_Z[0]-2e-6 and hi<=BLUE_Z[1]+2e-6,('Unexpected blue belt extent',obj.name,lo,hi)
        polygon=[]
        for vertex_id,loop_id in zip(face.vertices,face.loop_indices):
            attrs=[c for layer in layers for c in layer.data[loop_id].uv]
            polygon.append((*world[vertex_id],*attrs,*normals[loop_id]))
        pieces=[polygon]
        for boundary in (-BLUE_GAP_HALF_WIDTH,BLUE_GAP_HALF_WIDTH):
            pieces=[part for piece in pieces for part in _split_attributes(piece,lambda p,boundary=boundary:p[1]-boundary)]
        for piece in pieces:
            start=len(vertices);vertices.extend(tuple(inverse@Vector(p[:3])) for p in piece)
            faces.append(tuple(range(start,len(vertices))))
            middle=sum(p[1] for p in piece)/len(piece)
            indices.append(white if abs(middle)<BLUE_GAP_HALF_WIDTH else face.material_index)
            flags.append(face.use_smooth)
            for p in piece:
                for j in range(len(layers)):uvs[j].append(tuple(p[3+2*j:5+2*j]))
                normal=Vector(p[-3:]);new_normals.append(tuple(normal.normalized()))
        changed+=1
    if not changed:return False
    mesh=bpy.data.meshes.new(old.name+'_front24_blue_gap')
    mesh.from_pydata(vertices,[],faces)
    for mat in mats:mesh.materials.append(mat)
    for face,index,smooth in zip(mesh.polygons,indices,flags):face.material_index=index;face.use_smooth=smooth
    for source,values in zip(layers,uvs):
        target=mesh.uv_layers.new(name=source.name)
        for entry,value in zip(target.data,values):entry.uv=value
    mesh.update();mesh.normals_split_custom_set(new_normals);mesh.update()
    obj.data=mesh
    obj['front24_blue_band_split']=True
    obj['front24_changed_blue_faces']=changed
    obj['front24_blue_center_gap_width']=2*BLUE_GAP_HALF_WIDTH
    return True


def apply_common(b,jinwen=False):
    """Call once after preparing the v23 baseline, before fleet-number passes."""
    if b.lod>=2:return {'lod':b.lod,'changed':[],'scope':'No subpixel nose markings/bands at LOD2'}
    marks=[o for o in bpy.context.scene.objects if o.type=='MESH' and
           (o.name.startswith('railway_emblem_v11_') or o.name.startswith('nose_fuxing_v11_'))]
    assert len(marks)==8,('Expected 4 emblem pieces and 4 front Chinese glyphs',len(marks))
    changed=[obj.name for obj in marks if _raise_mark(obj,b)]
    paint=[]
    if jinwen:
        for obj in list(bpy.context.scene.objects):
            if obj.type=='MESH' and _break_blue(obj,b):paint.append(obj.name)
        assert paint or any(o.get('front24_blue_band_split') for o in bpy.context.scene.objects),'No Jinwen blue front belt found'
    bpy.context.view_layer.update()
    return {'lod':b.lod,'jinwen':jinwen,'changed':changed+paint,'shift_z_m':SHIFT_Z,
            'blue_belt_repainted_objects':paint,'blue_center_gap_y':[-BLUE_GAP_HALF_WIDTH,BLUE_GAP_HALF_WIDTH],
            'red_belt':'unchanged continuous inherited paint','side_signage':'untouched'}


def apply_number(b):
    """Call after each livery21 _replace_signage fleet pass; changes noses only."""
    if b.lod>=2:return []
    numbers=[o for o in bpy.context.scene.objects if o.get('livery21_role')=='nose_number']
    assert len(numbers)==2,('Expected two variable nose-number objects',len(numbers))
    changed=[o.name for o in numbers if _raise_mark(o,b)]
    bpy.context.view_layer.update()
    return changed
