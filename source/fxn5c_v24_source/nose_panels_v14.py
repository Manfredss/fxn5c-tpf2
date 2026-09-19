"""Flush oblique inboard lamp-panel joint, with no raised rod or false recess."""
import bpy

def make_lamp_panels(b):
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('inboard_folded_skin_v11','inboard_oblique_joint_v11')):
            bpy.data.objects.remove(obj,do_unlink=True)
    if b.lod>=2: return
    for end in (-1,1):
        for side in (-1,1):
            a=(1.103,2.195); c=(b.front_half(2.285),2.285)
            pts=[(end*11.0406,side*y,z+d) for y,z,d in
                 ((a[0],a[1],-.0007),(c[0],c[1],-.0007),
                  (c[0],c[1],.0007),(a[0],a[1],.0007))]
            obj=b.poly('inboard_folded_skin_v11',pts,[(0,1,2,3)],'graphite',normal=(end,0,0))
            # Historical tag retained for dependency-compatible feature counts.
            obj['front_v11_component']='inboard_folded_panel'

