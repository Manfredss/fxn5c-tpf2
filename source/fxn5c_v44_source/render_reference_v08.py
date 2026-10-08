"""Same-camera, same-light comparison render. No photo warping or AI imagery."""
from pathlib import Path
import json
import sys
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))

def render(gen,name="reference_0051_v08"):
    scene=bpy.context.scene
    for obj in list(scene.objects):
        if obj.type in {"CAMERA","LIGHT"}: bpy.data.objects.remove(obj,do_unlink=True)
    for key in ("headlights_fwd","headlights_bwd","taillights_fwd","taillights_bwd"):
        bpy.data.objects[key].hide_render=True
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=2732; scene.render.resolution_y=1824
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGBA"
    scene.render.film_transparent=True
    scene.view_settings.view_transform="AgX"; scene.view_settings.look="AgX - Medium High Contrast"
    scene.world.use_nodes=True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value=(.55,.64,.80,1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value=.65
    for loc,energy,size in [((-15,-18,22),4200,12),((6,8,15),2400,10),((-12,4,7),1200,7)]:
        bpy.ops.object.light_add(type="AREA",location=loc)
        lamp=bpy.context.object; lamp.data.energy=energy; lamp.data.size=size
        gen.point_camera(lamp,(0,0,2))
    fit=json.loads((ROOT/"reference_camera_v08.json").read_text(encoding="utf-8"))
    bpy.ops.object.camera_add(); cam=bpy.context.object; scene.camera=cam
    cam.matrix_world=Matrix(fit["world_matrix"])
    cam.data.type="PERSP"; cam.data.lens=fit["lens_mm"]; cam.data.sensor_width=fit["sensor_width_mm"]
    cam.data.sensor_fit="HORIZONTAL"
    out=ROOT/"native_preview"; out.mkdir(exist_ok=True)
    scene.render.filepath=str(out/(name+".png")); bpy.ops.render.render(write_still=True)
    for key in ("headlights_fwd","headlights_bwd","taillights_fwd","taillights_bwd"):
        bpy.data.objects[key].hide_render=False

if __name__=="__main__":
    import generate_fxn5c as gen
    # Read-only legacy source; all output remains in the new v08 workspace.
    bpy.ops.wm.open_mainfile(filepath=str(ROOT.parent/"fxn5c_v07_source/fxn5c_source.blend"))
    render(gen,"reference_0051_v07_same_camera")
