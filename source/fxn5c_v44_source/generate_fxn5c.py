import bpy
import math
import os
import sys
from mathutils import Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
FBX_DIR = os.path.join(ROOT, "fbx_import", "vehicle-train-fxn5c")
PREVIEW_DIR = os.path.join(ROOT, "preview")
SOURCE_BLEND = os.path.join(ROOT, "fxn5c_source.blend")

LENGTH = 22.4
WIDTH = 3.30
HEIGHT = 4.65
WHEEL_RADIUS = 0.625
BOGIE_CENTERS = (6.70, -6.70)
AXLE_OFFSETS = (1.80, 0.0, -1.80)

MATERIAL_SPECS = {
    "blue": ((0.012, 0.075, 0.30, 1.0), 0.36, 0.12),
    "light_blue": ((0.012, 0.23, 0.52, 1.0), 0.38, 0.08),
    "yellow": ((0.95, 0.55, 0.015, 1.0), 0.42, 0.05),
    "dark": ((0.035, 0.045, 0.055, 1.0), 0.62, 0.20),
    "black": ((0.008, 0.012, 0.016, 1.0), 0.55, 0.0),
    "metal": ((0.24, 0.27, 0.29, 1.0), 0.32, 0.65),
    "white": ((0.88, 0.90, 0.88, 1.0), 0.42, 0.0),
    "glass_transparent": ((0.09, 0.23, 0.36, 1.0), 0.20, 0.40),
    "roof": ((0.055, 0.065, 0.085, 1.0), 0.68, 0.12),
    "graphite": ((0.074, 0.083, 0.091, 1.0), 0.69, 0.32),
    "spring_steel": ((0.105, 0.115, 0.125, 1.0), 0.46, 0.52),
    "wheel_steel": ((0.22, 0.235, 0.25, 1.0), 0.25, 0.78),
    "ochre": ((0.20, 0.12, 0.045, 1.0), 0.72, 0.12),
}
from materials_v04 import MATERIALS, TRANSPARENT, EMISSIVE
MATERIAL_SPECS = MATERIALS


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        if datablocks is not bpy.data.materials:
            for block in list(datablocks):
                if block.users == 0:
                    datablocks.remove(block)


def material(short_name):
    full_name = f"/vehicle/train/fxn5c/{short_name}"
    mat = bpy.data.materials.get(full_name)
    if mat:
        return mat
    color, roughness, metallic = MATERIAL_SPECS.get(short_name,((1,1,1,1),.5,0))
    mat = bpy.data.materials.new(full_name)
    mat.use_nodes = True
    mat.diffuse_color = color
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        output = next((n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if output is None:
            output = mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if short_name in TRANSPARENT:
        bsdf.inputs["Alpha"].default_value = color[3]
        bsdf.inputs["IOR"].default_value = 1.45
        # Alpha-blended reflective panes match the game's transparency model.
        # Avoid presenting Blender-only refraction as an engine capability.
        mat.surface_render_method = "BLENDED"
        mat.use_transparency_overlap = True
    elif short_name in EMISSIVE:
        color,strength=EMISSIVE[short_name]
        bsdf.inputs["Base Color"].default_value=color
        bsdf.inputs["Emission Color"].default_value=color
        bsdf.inputs["Emission Strength"].default_value=strength
    else:
        texture_dir=os.path.join(ROOT,"staging","codex_fxn5c_1","res","textures","models","vehicle","train","fxn5c")
        for suffix,input_name,color_space in (("_surface","Base Color","sRGB"),("_rough","Roughness","Non-Color")):
            path=os.path.join(texture_dir,short_name+suffix+".tga")
            if os.path.isfile(path):
                node=mat.node_tree.nodes.new("ShaderNodeTexImage")
                node.image=bpy.data.images.load(path,check_existing=True)
                node.image.colorspace_settings.name=color_space
                mat.node_tree.links.new(node.outputs["Color"],bsdf.inputs[input_name])
    return mat


def emissive_material(name, color, strength=12.0):
    path = f"/vehicle/train/emissive/{name}"
    mat = bpy.data.materials.get(path)
    if mat:
        return mat
    mat = bpy.data.materials.new(path)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        output = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
        if output is None:
            output = nodes.new('ShaderNodeOutputMaterial')
        mat.node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Emission Color"].default_value = color
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def assign_material(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def apply_bevel(obj, width=0.05, segments=2):
    if width <= 0:
        return
    bevel = obj.modifiers.new("edge_softening", "BEVEL")
    bevel.width = width
    bevel.segments = segments
    bevel.limit_method = "ANGLE"
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=bevel.name)


def add_box(name, loc, dims, mat, bevel=0.03, rotation=(0.0, 0.0, 0.0), parent=None):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    assign_material(obj, mat)
    apply_bevel(obj, bevel, 2 if bevel > 0.025 else 1)
    if parent:
        obj.parent = parent
    return obj


def add_cylinder(name, loc, radius, depth, mat, vertices=20, rotation=(math.pi / 2, 0.0, 0.0), parent=None, bevel=0.0):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    assign_material(obj, mat)
    if bevel:
        apply_bevel(obj, bevel, 1)
    if parent:
        obj.parent = parent
    return obj


def join_objects(objects, name, parent=None):
    objects = [obj for obj in objects if obj and obj.name in bpy.data.objects]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    if parent:
        result.parent = parent
    return result


def add_metadata_locators():
    # Importer consumes these nodes into mdl metadata.
    bounds = add_box("bounds|bounding_box", (0, 0, HEIGHT / 2), (LENGTH + 1.0, WIDTH + 0.08, HEIGHT), material("dark"), 0)
    bounds.display_type = "WIRE"
    bounds.hide_render = True
    smoke = bpy.data.objects.new("exhaust|emitter_smoke", None)
    smoke.location = (-1.70, 0, 4.73)
    smoke.scale = (1.0, 1.0, 1.8)
    bpy.context.collection.objects.link(smoke)
    for sign in (-1, 1):
        seat = bpy.data.objects.new(f"driver_{sign}|seat_crew_driving_upright", None)
        seat.location = (sign * 9.78, -sign * 0.48, 2.30)
        seat.rotation_euler[2] = 0 if sign > 0 else math.pi
        bpy.context.collection.objects.link(seat)


def ensure_uvs():
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.data.polygons:
            continue
        if not obj.data.uv_layers:
            uv_layer = obj.data.uv_layers.new(name="UVMap")
            for loop in obj.data.loops:
                co = obj.data.vertices[loop.vertex_index].co
                uv_layer.data[loop.index].uv = (co.x * 0.071 + 0.5, co.z * 0.14 + co.y * 0.03)
        # Preserve per-face shading flags set by precision mechanical primitives.


def build_model(lod):
    from geometry_v20 import build
    clear_scene()
    for key in MATERIAL_SPECS:
        material(key)
    build(lod, sys.modules[__name__])
    add_metadata_locators()
    ensure_uvs()
    bpy.context.view_layer.update()


def export_fbx(lod):
    os.makedirs(FBX_DIR, exist_ok=True)
    path = os.path.join(FBX_DIR, f"fxn5c_lod{lod}.fbx")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in bpy.context.scene.objects:
        if obj.type in {"MESH", "EMPTY"}:
            obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH", "EMPTY"},
        use_mesh_modifiers=True,
        apply_unit_scale=True,
        bake_space_transform=False,
        axis_forward="-Z",
        axis_up="Y",
        add_leaf_bones=False,
        path_mode="AUTO",
        embed_textures=False,
    )
    return path


def point_camera(camera, target=(0, 0, 2.0)):
    direction = Vector(target) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_preview():
    from render_v14 import render_preview as render_new
    return render_new(sys.modules[__name__])


def render_preview_v03():
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1800
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world.color = (0.20, 0.23, 0.30)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.image_settings.color_mode = "RGBA"

    bpy.ops.object.camera_add(location=(25, -33, 16))
    camera = bpy.context.object
    point_camera(camera, (0.5, 0, 2.05))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 25.5
    scene.camera = camera

    for loc, energy, size in [((4, -10, 15), 3300, 10), ((-9, 5, 10), 2200, 8), ((14, 4, 9), 1800, 6)]:
        bpy.ops.object.light_add(type="AREA", location=loc)
        light = bpy.context.object
        light.data.energy = energy
        light.data.shape = "DISK"
        light.data.size = size
        point_camera(light, (0, 0, 2))
    bpy.ops.object.light_add(type="AREA", location=(3,-8,2.8))
    fill=bpy.context.object
    fill.data.energy=650
    fill.data.size=8
    point_camera(fill,(3,0,1.0))

    ground = add_box("preview_ground", (0, 0, -0.24), (200, 200, 0.18), material("roof"), 0.02)
    # Presentation rails use 1.435 m between the inner railhead edges.
    rails = []
    for sy in (-0.7525, 0.7525):
        rails.append(add_box("preview_rail", (0, sy, -.045), (27,.07,.09), material("metal"),.012))
    # Only one end lit in presentation, consistent with forward travel.
    for name in ("headlights_bwd", "taillights_bwd"):
        bpy.data.objects[name].hide_render = True
    scene.render.filepath = os.path.join(PREVIEW_DIR, "fxn5c_playable_preview.png")
    bpy.ops.render.render(write_still=True)
    for name, loc, scale, target in [
        ("front",(32,-.001,4.2),10.0,(10.0,0,2.35)),
        ("side",(0,-38,5),25,(0,0,2.20)),
        ("roof",(17,21,27),25,(0,0,2.25)),
        ("bogie",(10,-13,4.0),7.7,(6.7,0,1.05)),
        ("underframe",(-2,-15,2.8),9,(0,0,.96)),
    ]:
        camera.location=loc
        camera.data.ortho_scale=scale
        point_camera(camera,target)
        scene.render.filepath=os.path.join(PREVIEW_DIR,f"fxn5c_{name}_v03.png")
        bpy.ops.render.render(write_still=True)
    for name in ("headlights_bwd", "taillights_bwd"):
        bpy.data.objects[name].hide_render = False
    for rail in rails:
        bpy.data.objects.remove(rail,do_unlink=True)
    bpy.data.objects.remove(ground, do_unlink=True)
    camera.location=(25,-33,16)
    camera.data.ortho_scale=25.5
    point_camera(camera,(.5,0,2.05))


def main():
    sys.path.insert(0, ROOT)
    for lod in (0, 1, 2):
        build_model(lod)
        export_fbx(lod)
        if lod == 0:
            render_preview()
            bpy.ops.wm.save_as_mainfile(filepath=SOURCE_BLEND)
    print("FXN5C source generated")
    print("FBX_DIR=" + FBX_DIR)
    print("SOURCE_BLEND=" + SOURCE_BLEND)


if __name__ == "__main__":
    main()
