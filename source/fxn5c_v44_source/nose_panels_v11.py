"""Photo-constrained shallow inboard lamp panels, not surveyed shell geometry.

0051, 0060 and 0010 show an oblique seam above the inboard lower light. The
seam's presence is supported; its exact depths below are modeling estimates.
The underlying v10 corner/outer lamp mount is deliberately not certified here.
"""
import bpy
from nose_profile_v10 import front_half


def make_lamp_panels(b):
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('inboard_folded_skin_v11','inboard_oblique_joint_v11')):
            bpy.data.objects.remove(obj,do_unlink=True)
    if b.lod>=2: return
    for end in (-1,1):
        for side in (-1,1):
            # A thin folded skin, rising from the handle-side boundary to the
            # corner boundary. The light aperture is NOT covered by an overlay:
            # all points stay behind the existing .020-m emitter plane.
            points=[(end*11.0405,side*1.070,1.785),
                    (end*11.045,side*b.front_half(1.785),1.785),
                    (end*11.042,side*b.front_half(2.285),2.285),
                    (end*11.042,side*1.103,2.195)]
            obj=b.poly('inboard_folded_skin_v11',points,[(0,1,2),(0,2,3)],'blue',normal=(end,0,0))
            mod=obj.modifiers.new('thin_folded_panel','SOLIDIFY'); mod.thickness=.003
            bpy.context.view_layer.objects.active=obj
            bpy.ops.object.modifier_apply(modifier=mod.name)
            obj['front_v11_component']='inboard_folded_panel'
            b.rod('inboard_oblique_joint_v11',
                  (end*11.044,side*1.103,2.195),
                  (end*11.044,side*b.front_half(2.285),2.285),.0016,'graphite')
