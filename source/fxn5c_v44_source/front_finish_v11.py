"""Photo-estimated front paint spacing and slimmer returned grab rails.

Only nose lettering/grab objects are replaced. Badge, shell, lamps and steps
are untouched. Dimensions are modeling estimates, not surveyed factory values.
Windows fonts are converted immediately to meshes; no font files are shipped.
Run inside Blender with -- --trial for isolated source-scene preview PNGs only.
"""
from collections import Counter
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

PAINT_OFFSET = .0016
GRIP_RADIUS = .012
GRIP_OFFSET = .047
BEND_RADIUS = .026
LETTER_INBOARD_FACTOR = .88
NUMBER_MIN_Z = 1.792
NUMBER_MAX_Z = 1.9208-.012
NUMBER_BASE_Z = 1.83
NUMBER_FONT_SIZE = .20
FUXING_BASE_Z = 2.12
FUXING_FONT_SIZE = .24
FONT_PATHS = {True:Path("C:/Windows/Fonts/simkai.ttf"), False:Path("C:/Windows/Fonts/arialbd.ttf")}
OLD_PREFIXES = ("nose_number", "nose_fuxing", "nose_grab_", "grab_mount", "front_finish_v11_")


def _glyph_geometry(value, size, chinese, resolution):
    """Return local text vertices/faces without changing scene selections."""
    path = FONT_PATHS[chinese]
    if not path.is_file():
        raise FileNotFoundError(f"Required original Windows font unavailable: {path}")
    font = bpy.data.fonts.load(str(path),check_existing=True)
    curve = bpy.data.curves.new("front_finish_v11_glyph_curve","FONT")
    curve.body = value
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.resolution_u = resolution
    curve.extrude = 0
    curve.bevel_depth = 0
    curve.font = font
    temporary = bpy.data.objects.new("front_finish_v11_glyph_temporary",curve)
    bpy.context.collection.objects.link(temporary)
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(temporary.evaluated_get(depsgraph),depsgraph=depsgraph)
    try:
        vertices = [tuple(v.co) for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]
    finally:
        bpy.data.meshes.remove(mesh)
        bpy.data.objects.remove(temporary,do_unlink=True)
        if curve.users == 0:
            bpy.data.curves.remove(curve)
        if font.users == 0:
            bpy.data.fonts.remove(font)
    if not vertices or not faces:
        raise ValueError(f"Font did not produce mesh geometry for {value!r}")
    return vertices,faces


def _paint(b,name,value,size,zbase,end,center_u=None,chinese=False,scale=1.0):
    raw,faces = _glyph_geometry(value,size,chinese,16 if b.lod == 0 else 8)
    shift = 0.0
    if center_u is not None:
        shift = center_u-(min(p[0] for p in raw)+max(p[0] for p in raw))/2*scale
    vertices = []
    for u,v,_ in raw:
        z = zbase+v*scale
        vertices.append((end*(b.front_x(z)+PAINT_OFFSET),end*(u*scale+shift),z))
    obj = b.poly(name,vertices,faces,"white",normal=(end,0,0))
    obj["front11_component"] = "nose_paint"
    obj["front11_text"] = value
    obj["front11_end"] = end
    obj["front11_font_size"] = size
    obj["front11_uniform_outline_scale"] = scale
    obj["front11_paint_offset_m"] = PAINT_OFFSET
    return obj


def _original_letter_centers():
    vertices,_ = _glyph_geometry("复       兴",FUXING_FONT_SIZE,True,16)
    left = [p[0] for p in vertices if p[0] < 0]
    right = [p[0] for p in vertices if p[0] > 0]
    if not left or not right:
        raise ValueError("Legacy spaced front text did not separate around its centre")
    return ((min(left)+max(left))/2,(min(right)+max(right))/2)


def _number_placement():
    raw,_ = _glyph_geometry("FXN5C 0051",NUMBER_FONT_SIZE,False,16)
    low,high = min(p[1] for p in raw),max(p[1] for p in raw)
    available = NUMBER_MAX_Z-NUMBER_MIN_Z
    scale = min(1.0,available/(high-low))
    base = max(NUMBER_BASE_Z,NUMBER_MIN_Z-low*scale)
    assert base+high*scale <= NUMBER_MAX_Z+1e-7
    return base,scale,(base+low*scale,base+high*scale)


def _anchors(end,side):
    # v0.8 moved the original .96/1.08 positions inboard by .25 m. Verified
    # against preserved source mount centres; no new lateral/height guess here.
    return (Vector((end*11.04,side*.71,1.80)),Vector((end*11.04,side*.83,2.34)))


def _returned_grip(b,end,side):
    lower,upper = _anchors(end,side)
    normal = Vector((end,0,0))
    direction = (upper-lower).normalized()
    length = (upper-lower).length
    binormal = normal.cross(direction).normalized()
    elbow_steps = 10 if b.lod == 0 else 6
    cross_steps = 20 if b.lod == 0 else 12
    stem_offset = GRIP_OFFSET-BEND_RADIUS
    centers = [lower+normal*.0075]
    for i in range(elbow_steps+1):
        t = i/elbow_steps*math.pi/2
        centers.append(lower+normal*(stem_offset+BEND_RADIUS*math.sin(t))+
                       direction*(BEND_RADIUS*(1-math.cos(t))))
    # Tangent-aligned straight grip between two quarter-circle elbows.
    for i in range(elbow_steps+1):
        t = i/elbow_steps*math.pi/2
        centers.append(lower+normal*(stem_offset+BEND_RADIUS*math.cos(t))+
                       direction*(length-BEND_RADIUS+BEND_RADIUS*math.sin(t)))
    centers.append(upper+normal*.0075)
    vertices = []
    for i,center in enumerate(centers):
        tangent = (centers[min(i+1,len(centers)-1)]-centers[max(0,i-1)]).normalized()
        across = tangent.cross(binormal).normalized()
        for j in range(cross_steps):
            angle = math.tau*j/cross_steps
            vertices.append(tuple(center+GRIP_RADIUS*(math.cos(angle)*binormal+math.sin(angle)*across)))
    faces = []
    for i in range(len(centers)-1):
        for j in range(cross_steps):
            k = (j+1)%cross_steps
            faces.append((i*cross_steps+j,i*cross_steps+k,(i+1)*cross_steps+k,(i+1)*cross_steps+j))
    faces += [tuple(range(cross_steps-1,-1,-1)),tuple((len(centers)-1)*cross_steps+j for j in range(cross_steps))]
    obj = b.poly(f"nose_grab_v11_{end}_{side}",vertices,faces,"metal",solid=True)
    for polygon in obj.data.polygons[:-2]:
        polygon.use_smooth = True
    obj["front11_component"] = "returned_nose_grip"
    obj["front11_grip_radius_m"] = GRIP_RADIUS
    obj["front11_lower_anchor_yz"] = [side*.71,1.80]
    obj["front11_upper_anchor_yz"] = [side*.83,2.34]
    obj["front11_straight_axis_offset_m"] = GRIP_OFFSET
    obj["v08_inboard_grab"] = True
    return obj,direction,binormal


def _mount(b,end,side,anchor,direction,binormal,index):
    normal = Vector((end,0,0))
    segments = 32 if b.lod == 0 else 20
    vertices = []
    # 40 x 36 mm shallow oval, with a real rounded edge rather than the former
    # 80 mm flat cylinder. The low point remains above the grey-band top.
    for offset,factor in ((.0005,.88),(.002,1.0),(.0055,1.0),(.008,.86)):
        for j in range(segments):
            t = j/segments*math.tau
            p = anchor+normal*offset+factor*(direction*(.020*math.cos(t))+binormal*(.018*math.sin(t)))
            vertices.append(tuple(p))
    faces = [tuple(range(segments-1,-1,-1))]
    for ring in range(3):
        for j in range(segments):
            k = (j+1)%segments
            faces.append((ring*segments+j,ring*segments+k,(ring+1)*segments+k,(ring+1)*segments+j))
    faces.append(tuple(3*segments+j for j in range(segments)))
    obj = b.poly(f"grab_mount_v11_{end}_{side}_{index}",vertices,faces,"metal",solid=True)
    for polygon in obj.data.polygons[1:-1]:
        polygon.use_smooth = True
    obj["front11_component"] = "oval_grab_mount"
    obj["front11_anchor_yz"] = [anchor.y,anchor.z]
    obj["v08_inboard_grab"] = True
    # One small, separately visible hex bolt on the outward end of each pad.
    center = anchor+direction*((-1 if index == 0 else 1)*.014)+normal*.010
    bolt_vertices = []
    for offset in (-.002,.002):
        for j in range(6):
            t = j*math.tau/6
            bolt_vertices.append(tuple(center+normal*offset+.004*(math.cos(t)*direction+math.sin(t)*binormal)))
    bolt_faces = [tuple(range(5,-1,-1)),tuple(range(6,12))]
    bolt_faces += [(j,(j+1)%6,(j+1)%6+6,j+6) for j in range(6)]
    bolt = b.poly(f"front_finish_v11_mount_bolt_{end}_{side}_{index}",bolt_vertices,bolt_faces,"spring_steel",solid=True)
    bolt["front11_component"] = "grab_mount_hex_bolt"
    return obj,bolt


def make_front_finish(b):
    """Idempotent nose-only finish, LOD0/1; call after inherited cabs/markings."""
    if b.lod >= 2:
        return []
    # Prepare font geometry first, so a missing local font never erases the old
    # scene's text before a clear actionable failure.
    centers = _original_letter_centers()
    number_base,number_scale,number_bounds = _number_placement()
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(OLD_PREFIXES):
            bpy.data.objects.remove(obj,do_unlink=True)
    created = []
    for end in (-1,1):
        for character,center in zip("复兴",centers):
            obj = _paint(b,f"nose_fuxing_v11_{end}_{character}",character,FUXING_FONT_SIZE,FUXING_BASE_Z,
                         end,center_u=center*LETTER_INBOARD_FACTOR,chinese=True)
            obj["front11_original_glyph_center_u"] = center
            obj["front11_glyph_center_u"] = center*LETTER_INBOARD_FACTOR
            created.append(obj)
        obj = _paint(b,f"nose_number_v11_{end}","FXN5C 0051",NUMBER_FONT_SIZE,number_base,end,scale=number_scale)
        obj["front11_gray_band_clearance_m"] = number_bounds[0]-1.78
        obj["front11_emblem_base_clearance_m"] = 1.9208-number_bounds[1]
        obj["front11_number_upshift_m"] = number_base-NUMBER_BASE_Z
        created.append(obj)
        for side in (-1,1):
            grip,direction,binormal = _returned_grip(b,end,side)
            created.append(grip)
            for index,anchor in enumerate(_anchors(end,side)):
                created.extend(_mount(b,end,side,anchor,direction,binormal,index))
    assert Counter(o["front11_component"] for o in created) == {
        "nose_paint":6,"returned_nose_grip":4,"oval_grab_mount":8,"grab_mount_hex_bolt":8}
    bpy.context.view_layer.update()
    return created


def _trial(source,output):
    """Read-only production input; preview images/reports go only to trial dir."""
    root = Path(__file__).resolve().parent
    sys.path.insert(0,str(root))
    import generate_fxn5c as gen
    from geometry_v10 import CornerBuilder
    bpy.ops.wm.open_mainfile(filepath=str(source))
    b = CornerBuilder(0,gen)
    first = make_front_finish(b)
    positions = sorted(tuple(round(c,7) for c in v.co) for o in first for v in o.data.vertices)
    created = make_front_finish(b)
    second = sorted(tuple(round(c,7) for c in v.co) for o in created for v in o.data.vertices)
    assert positions == second, "Front finish must be idempotent"
    for o in created:
        if o["front11_component"] == "nose_paint":
            end = o["front11_end"]
            assert max(abs(end*v.co.x-b.front_x(v.co.z)-PAINT_OFFSET) for v in o.data.vertices)<1e-6
        else:
            # A broad independent clearance witness: all grab hardware remains
            # well inboard of the white/red lower lamp assemblies.
            assert max(abs(v.co.y) for v in o.data.vertices)<.86
            assert min(abs(v.co.x)-11.04 for v in o.data.vertices)>.00049
    report = {
        "status":"PASS","scope":"isolated source-scene finish trial, not native export or game test",
        "counts":dict(Counter(o["front11_component"] for o in created)),
        "glyph_center_u_before":list(_original_letter_centers()),
        "glyph_center_u_after":[x*LETTER_INBOARD_FACTOR for x in _original_letter_centers()],
        "number_placement":_number_placement(),
        "grip_radius_m":GRIP_RADIUS,
        "grip_anchor_yz_positive_side":[[.71,1.80],[.83,2.34]],
        "paint_offset_m":PAINT_OFFSET,
        "dimensions":"photo-estimated; not manufacturer measurements",
    }
    output.mkdir(parents=True,exist_ok=True)
    (output/"front_finish_trial.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    scene = bpy.context.scene
    for obj in list(scene.objects):
        if obj.type in {"LIGHT","CAMERA"}:
            bpy.data.objects.remove(obj,do_unlink=True)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 2000
    scene.render.resolution_y = 1400
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (.30,.37,.48,1)
    background.inputs["Strength"].default_value = .40
    for location,energy,size in [((14,-9,9),1800,7),((15,6,7),1600,6),((9,0,6),500,5)]:
        bpy.ops.object.light_add(type="AREA",location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        gen.point_camera(light,(11,0,2.1))
    for name in ("headlights_bwd","taillights_bwd"):
        if name in bpy.data.objects:
            bpy.data.objects[name].hide_render = True
    bpy.ops.object.camera_add(location=(20,0,2.2))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    scene.camera = camera
    for label,location,scale,target in (
        ("front_finish_front",(20,0,2.2),3.1,(11.04,0,2.12)),
        ("front_finish_threequarter",(16,-7,4.3),3.45,(11.04,-.10,2.15)),
    ):
        camera.location = location
        camera.data.ortho_scale = scale
        gen.point_camera(camera,target)
        scene.render.filepath = str(output/(label+".png"))
        bpy.ops.render.render(write_still=True)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    print("Trial images only; production .blend and staging were not written.",flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial",action="store_true")
    root = Path(__file__).resolve().parent
    parser.add_argument("--source",type=Path,default=root/"fxn5c_source.blend")
    parser.add_argument("--output",type=Path,default=root.parent/"reference/v11/front_finish_trial")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.trial:
        _trial(args.source,args.output)
