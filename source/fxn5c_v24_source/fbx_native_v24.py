"""Six STATIC forward-state native readback FBXs, not an animated train rig.

The shipping native .mdl retains six visibility cases. FBX is an interchange
snapshot only: apply actual frontForwardParts, delete the five inactive lamp
instances, then export without animation. Never export all conditional lamps.
"""
from pathlib import Path
import json
import sys

import bpy

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import generate_fxn5c as gen
import render_native
from light_revision_v24 import register_source_materials, apply_native_preview


def export_static(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in bpy.context.scene.objects:
        assert obj.type != 'ARMATURE', ('unexpected animation rig in static interchange', obj.name)
        if obj.type in {'MESH', 'EMPTY'}:
            obj.hide_set(False)
            obj.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True, object_types={'MESH', 'EMPTY'},
        use_mesh_modifiers=True, apply_unit_scale=True, bake_space_transform=False,
        axis_forward='-Z', axis_up='Y', add_leaf_bones=False,
        path_mode='AUTO', embed_textures=False, bake_anim=False,
    )


def main():
    for jw in (False, True):
        style = 'fxn5c_jinwen' if jw else 'fxn5c'
        model = json.loads((ROOT / ('native_scene_' + style + '.json')).read_text(encoding='utf-8'))
        for lod in (0, 1, 2):
            register_source_materials(gen)
            render_native.load_native(jw, model_stem=style, lod_index=lod)
            state = apply_native_preview(model, direction='fwd', position='front', lod=lod)
            inactive = set(state['all_lamp_names']) - set(state['visible_names'])
            assert len(inactive) == (5 if lod < 2 else 0)
            for name in sorted(inactive):
                obj = bpy.data.objects[name]
                assert not obj.children, ('conditional light unexpectedly owns another object', name)
                bpy.data.objects.remove(obj, do_unlink=True)
            # FBX material bindings are per geometry. Privatize shared native
            # wheel meshes so interchange cannot alias different material slots.
            for obj in bpy.context.scene.objects:
                if obj.type == 'MESH' and obj.data.users > 1:
                    obj.data = obj.data.copy()
            folder = 'vehicle-train-fxn5c-jinwen' if jw else 'vehicle-train-fxn5c'
            path = ROOT / 'fbx_import' / folder / ('fxn5c_lod' + str(lod) + '.fbx')
            export_static(path)
            print('STATIC_FORWARD_NATIVE_FBX', style, lod, 'active', state['visible_names'],
                  'removed_inactive', sorted(inactive), flush=True)


if __name__ == '__main__':
    main()
