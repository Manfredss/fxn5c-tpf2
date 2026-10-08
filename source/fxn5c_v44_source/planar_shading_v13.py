"""Assign explicit geometric loop normals on manufactured sheet meshes.

In Blender 5.2, zero-valued custom normals can retain interpolated vertex
directions after boolean/bevel operations even when polygon.use_smooth=False.
Native export already uses triangle normals for these tagged objects; editable
source rendering must use the same planar shading rather than relying on zero
as a request to recompute the appropriate per-face direction.
"""
import bpy

def apply_planar_normals():
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or not obj.name.startswith(('body_open_shell_v07','cab_continuous_low_hood_v13')):
            continue
        mesh=obj.data
        for face in mesh.polygons:face.use_smooth=False
        mesh.update()
        normals=[None]*len(mesh.loops)
        for face in mesh.polygons:
            normal=tuple(face.normal)
            for index in face.loop_indices:normals[index]=normal
        mesh.normals_split_custom_set(normals)
        mesh.update()
        obj['explicit_planar_shading_v13']=True
