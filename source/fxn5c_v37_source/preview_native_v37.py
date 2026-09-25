"""Actual native animation readback; not a game or Model Editor screenshot."""
from pathlib import Path
import sys,json
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
import generate_fxn5c as gen
from render_native_v21 import setup,shot
from render_native import load_native
from animation_v26 import flatten_nodes
from animation_v28 import sample
from native_patch_v23 import sha
from verify_native import read_lua

def main():
    jw='--jinwen' in sys.argv;style='fxn5c_jinwen' if jw else 'fxn5c'
    import light_revision_v24 as lamps
    lamps.register_source_materials(gen);load_native(jw,style)
    model=json.loads((ROOT/f'native_scene_{style}.json').read_text());culling={}
    for n in flatten_nodes(model['lods'][0]['node']):
        for ref in n.get('materials',[]):
            path=ROOT/'staging/codex_fxn5c_1/res/models/material'/ref
            if not path.exists():continue
            name=Path(ref).stem.removesuffix('_skin19')
            mat=bpy.data.materials.get('/vehicle/train/fxn5c/'+name) or bpy.data.materials.get('/vehicle/train/emissive/'+name)
            assert mat is not None
            enabled=not read_lua(path)['params'].get('two_sided',{}).get('twoSided',False)
            mat.use_backface_culling=enabled;culling[name]=enabled
    lamps.apply_native_preview(model,'fwd','singleton',0)
    moving=[n for n in flatten_nodes(model['lods'][0]['node']) if n.get('animations',{}).get('forever')]
    def pose(ms):
        for n in moving:
            tf=sample(n,ms,ROOT)
            bpy.data.objects[n['name']].matrix_local=Matrix([[tf[c*4+r] for c in range(4)] for r in range(4)])
        bpy.context.view_layer.update()
    setup();out=ROOT/'preview_v37/native'/style
    for ms in (0,200,400,600):
        pose(ms);shot(out/f'wave_{ms:04}.png',(8.2,-6,7),1.05,(7.60,-1.52,4.115),1000,740)
    pose(200)
    shot(out/'opposite.png',(-8.35,6,7),1.05,(-7.75,1.52,4.115),1000,740)
    shot(out/'context.png',(9,-9,6.5),3.7,(7.25,-.8,3.9),1300,850)
    shot(out/'big_open.png',(-7.8,9,4.5),4.8,(-4.9,1.65,2.95),1500,800)
    shot(out/'big_other_open.png',(-7.8,-9,4.5),4.8,(-4.9,-1.65,2.95),1500,800)
    frames=[]
    if '--motion' in sys.argv:
        for i in range(16):
            pose(i*50);name=f'wave_frames/{i:02}.png'
            shot(out/name,(8.2,-6,7),1.05,(7.60,-1.52,4.115),760,560)
            frames.append(dict(file=name,time_ms=i*50,duration_ms=50))
    (out/'render_manifest.json').write_text(json.dumps(dict(style=style,frames=frames,
        native_model_sha256=sha(ROOT/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl'),
        build_manifest_sha256=sha(ROOT/'manifest_v37.json'),backface_culling=culling,
        period_ms=800,engine_playtest=False),indent=2))
if __name__=='__main__':main()
