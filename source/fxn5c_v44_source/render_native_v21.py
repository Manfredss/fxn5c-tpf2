"""Read-back previews and canonical upright PNG UI renders, not game captures."""
from pathlib import Path
import math,sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen
from roster_v21 import ROSTER
from render_native import load_native,update_skin_pose
from render_v04 import render_preview


def setup():
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGBA'
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    scene.world.use_nodes=True
    bg=scene.world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value=(.30,.37,.48,1)
    bg.inputs['Strength'].default_value=.40
    for loc,energy,size in [((4,-9,11),1750,9),((-8,6,10),2500,8),((14,3,8),1200,6),((9,-8,4.3),350,6)]:
        bpy.ops.object.light_add(type='AREA',location=loc)
        lamp=bpy.context.object;lamp.data.energy=energy;lamp.data.size=size
        gen.point_camera(lamp,(3,0,2))
    bpy.ops.object.camera_add()
    scene.camera=bpy.context.object;scene.camera.data.type='ORTHO'


def shot(path,loc,scale,target,width=1600,height=1000,transparent=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    s=bpy.context.scene;s.render.film_transparent=transparent
    s.render.resolution_x=width;s.render.resolution_y=height
    s.camera.location=loc;s.camera.data.ortho_scale=scale
    gen.point_camera(s.camera,target);s.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)


def main():
    icons='--icons-only' in sys.argv
    selected=[r for r in ROSTER if ('--cr' not in sys.argv or not r['jinwen']) and ('--jinwen' not in sys.argv or r['jinwen'])]
    for row in selected:
        if not icons and row['number'] not in ('0051','7006'):continue
        load_native(row['jinwen'],row['stem'])
        setup()
        if icons:
            out=ROOT/'ui_canonical'/row['stem']
            shot(out/'models_small.png',(7,-60,14),28,(0,0,2.2),640,150,True)
            shot(out/'models_20.png',(7,-60,14),36,(0,0,2.2),192,40,True)
            shot(ROOT/'fleet_preview'/(row['number']+'.png'),(9.4,-22,3.0),4.0,(9.4,0,3.0),1000,700)
        else:
            folder=ROOT/('native_preview_jinwen' if row['jinwen'] else 'native_preview')
            gen.PREVIEW_DIR=str(folder)
            extra=[('bogie_side',(6.4,-20,1.02),6.7,(6.4,0,1.02)),
                   ('body_connection',(7.6,-8,1.8),2.7,(6.5,-1.3,1.05)),
                   ('bogie_low',(4.5,-7,.82),4.8,(6.4,-.9,.95)),
                   ('front',(24,-.1,3.0),5.2,(10.7,0,2.6)),
                   ('side_opposite',(0,35,4.5),25,(0,0,2.2)),
                   ('roof_fans',(4.5,-10,5.25),3.8,(2.85,-.4,4.35)),
                   ('roof_opposite',(5,10,8),4.0,(2.85,0,4.3)),
                   ('reservoirs',(3.3,-8,1.8),2.7,(2.9,0,.98)),
                   ('cab_full_side',(9.2,-22,3.07),4.9,(9.2,0,3.07))]
            render_preview(gen,'v21',extra)
            for deg in (0,5,15):
                bpy.data.objects['b1_grp'].rotation_euler.z=math.radians(deg)
                bpy.data.objects['b2_grp'].rotation_euler.z=-math.radians(deg)
                update_skin_pose()
                shot(folder/f'fxn5c_link_yaw_p{deg:02}_v21.png',(8.5,-7.5,3.1),3.6,(6.35,-1.4,.94))
        print('RENDERED',row['stem'],flush=True)


if __name__=='__main__':main()
