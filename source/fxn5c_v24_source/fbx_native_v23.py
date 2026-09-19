"""Six static interchange FBXs from verified native resources; not a skin rig."""
from pathlib import Path
import sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen
import render_native

def main():
    for jw in (False,True):
        for lod in (0,1,2):
            render_native.load_native(jw,lod_index=lod)
            # FBX material bindings are per geometry. Make shared wheel
            # geometry private so interchange never aliases different slots.
            for obj in bpy.context.scene.objects:
                if obj.type=='MESH' and obj.data.users>1:obj.data=obj.data.copy()
            gen.FBX_DIR=str(ROOT/('fbx_import/vehicle-train-fxn5c-jinwen' if jw else 'fbx_import/vehicle-train-fxn5c'))
            gen.export_fbx(lod)
            print('NATIVE FBX',jw,lod,flush=True)

if __name__=='__main__':main()
