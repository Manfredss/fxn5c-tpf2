"""Daylight and low-light QA, using native-equivalent alpha/emissive materials.

No Blender-only headlight spotlights are used. These renders do not certify the
game's transparency sorting or illumination on scenery.
"""
import os
import math
import bpy
from mathutils import Vector

def render_preview(gen,version="v04",extra_views=()):
    os.makedirs(gen.PREVIEW_DIR,exist_ok=True)
    scene=bpy.context.scene
    # A saved source already has the previous QA rig. Reuse of that scene must
    # not stack duplicate area lights or exhaust EEVEE's shadow pool.
    for obj in list(scene.objects):
        if obj.type in {"LIGHT","CAMERA"}:
            bpy.data.objects.remove(obj,do_unlink=True)
    original=set(scene.objects)
    scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=2200; scene.render.resolution_y=1300
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.render.image_settings.color_mode="RGBA"
    scene.view_settings.view_transform="AgX"
    scene.view_settings.look="AgX - Medium High Contrast"
    world=scene.world
    world.use_nodes=True
    bg=world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(.30,.37,.48,1)
    bg.inputs["Strength"].default_value=.40
    scene.render.film_transparent=False
    bpy.ops.object.camera_add(location=(22,-32,11))
    cam=bpy.context.object; cam.data.type="ORTHO"; cam.data.ortho_scale=25.5
    gen.point_camera(cam,(.4,0,2.10)); scene.camera=cam
    lamps=[]
    for loc,energy,size in [((4,-9,11),1750,9),((-8,6,10),2500,8),((14,3,8),1200,6),((9,-8,4.3),350,6)]:
        bpy.ops.object.light_add(type="AREA",location=loc)
        obj=bpy.context.object; obj.data.energy=energy; obj.data.size=size
        gen.point_camera(obj,(3,0,2)); lamps.append(obj)
    # Real material highlights on a floor, not an artificially lit railway beam.
    ground=gen.add_box("qa_ground",(0,0,-.25),(120,120,.12),gen.material("cab_floor"))
    for y in (-.7525,.7525):
        gen.add_box("qa_rail",(0,y,-.045),(28,.070,.09),gen.material("metal"),.01)
    for x in range(-13,14):
        gen.add_box("qa_sleeper",(x,0,-.105),(.23,2.40,.08),gen.material("roof"),.018)
    for name in ("headlights_bwd","taillights_bwd"):
        bpy.data.objects[name].hide_render=True
    def shot(name,loc,scale,target):
        cam.location=loc; cam.data.ortho_scale=scale; gen.point_camera(cam,target)
        scene.render.filepath=os.path.join(gen.PREVIEW_DIR,name)
        bpy.ops.render.render(write_still=True)
    shot("fxn5c_playable_preview.png",(22,-32,11),25.5,(.4,0,2.1))
    for tag,loc,scale,target in [
        ("cab",(17,-9,5.4),5.65,(9.4,0,2.95)),
        ("glass",(16,-1.5,4.0),3.50,(10.0,0,3.22)),
        ("bogie",(9.8,-12,2.9),7.0,(6.7,0,1.0)),
        ("roof",(17,20,25),24.5,(0,0,2.3)),
        ("side",(0,-35,4.5),25,(0,0,2.2)),
        ("underframe",(-2,-14,2.6),8.7,(0,0,.93))]:
        shot(f"fxn5c_{tag}_{version}.png",loc,scale,target)
    for tag,loc,scale,target in extra_views:
        shot(f"fxn5c_{tag}_{version}.png",loc,scale,target)
    # The cabin close-up is a QA view, not a manufacturer-accurate cockpit claim.
    saved_cam=(cam.location.copy(),cam.data.ortho_scale)
    shot(f"fxn5c_cab_interior_{version}.png",(9.7,-.01,3.70),2.80,(9.3,0,2.35))
    # Low ambient presentation uses only the modeled emissive lamps, plus subtle
    # general scene lighting. No spot/point lamp adds a fake headlight beam.
    bg.inputs["Strength"].default_value=.05
    for light in lamps:
        light.data.energy*=.18
    tree=bpy.data.node_groups.new("FXN5C_Lamp_QA_Compositor","CompositorNodeTree")
    scene.compositing_node_group=tree
    tree.interface.new_socket(name="Image",in_out="OUTPUT",socket_type="NodeSocketColor")
    source=tree.nodes.new("CompositorNodeRLayers")
    glare=tree.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value="Fog Glow"
    glare.inputs["Quality"].default_value="High"
    glare.inputs["Strength"].default_value=.40
    output=tree.nodes.new("NodeGroupOutput")
    tree.links.new(source.outputs["Image"],glare.inputs["Image"])
    tree.links.new(glare.outputs["Image"],output.inputs["Image"])
    shot(f"fxn5c_lights_forward_{version}.png",(19,-8,5.8),8.4,(9.0,0,2.7))
    for name in ("headlights_fwd","taillights_fwd"):
        bpy.data.objects[name].hide_render=True
    for name in ("headlights_bwd","taillights_bwd"):
        bpy.data.objects[name].hide_render=False
    shot(f"fxn5c_lights_reverse_{version}.png",(19,-8,5.8),8.4,(9.0,0,2.7))
    scene.compositing_node_group=None
    bg.inputs["Strength"].default_value=.40
    for light in lamps:
        light.data.energy/=.18
    for obj in set(scene.objects)-original:
        if obj not in lamps:
            bpy.data.objects.remove(obj,do_unlink=True)
    for name in ("headlights_fwd","taillights_fwd","headlights_bwd","taillights_bwd"):
        bpy.data.objects[name].hide_render=False
    # Preserve a useful camera and daylight setup in the editable .blend.
    bpy.ops.object.camera_add(location=(22,-32,11))
    scene.camera=bpy.context.object; scene.camera.data.type="ORTHO"; scene.camera.data.ortho_scale=25.5
    gen.point_camera(scene.camera,(.4,0,2.1))
