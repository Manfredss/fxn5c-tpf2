"""Read the two final saved sources without rerunning the candidate recipe."""
from pathlib import Path
import hashlib,json,sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from audit_front_v24 import audit_scene,negative_controls,geometry_hash,material_triangles

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    rows=[];inputs={};baseline={}
    for jw,style in ((False,'fxn5c'),(True,'fxn5c_jinwen')):
        old=ROOT.parent/'fxn5c_v23_source'/(style+'_source.blend')
        bpy.ops.wm.open_mainfile(filepath=str(old))
        side={o.name:geometry_hash(o) for o in bpy.context.scene.objects
              if o.get('livery21_variable') and o.get('livery21_role')!='nose_number'}
        red=material_triangles(bpy.data.objects['body_open_shell_v07'],'jw_red')
        baseline[style+'_source.blend']=sha(old)
        path=ROOT/(style+'_source.blend')
        bpy.ops.wm.open_mainfile(filepath=str(path))
        result=audit_scene(jw,0)
        assert side=={name:geometry_hash(bpy.data.objects[name]) for name in side},'side signage changed'
        assert red==material_triangles(bpy.data.objects['body_open_shell_v07'],'jw_red'),'red face surfaces changed'
        faults=negative_controls(jw,0)
        rows.append(dict(file=path.name,source_sha256=sha(path),front=result,
            negative_controls=faults,side_signage_unchanged=True,red_surfaces_unchanged=True,
            candidate_recipe_applied=False))
        inputs[path.name]=sha(path)
    for name in ('audit_sources_v24.py','audit_front_v24.py','front_revision_v24.py','native_patch_manifest_v24.json'):
        inputs[name]=sha(ROOT/name)
    report=dict(status='PASS',sources=rows,inputs_sha256=inputs,baseline_sha256=baseline,
        negative_controls_passed=sum(len(r['negative_controls']) for r in rows),
        scope='Final saved source front marks/support rays/material boundaries and unchanged side marks; native correspondence covered by independent native delta audit',
        game_verified=False)
    (ROOT/'audit_sources_v24.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('FINAL_FRONT_SOURCES_PASS',flush=True)

if __name__=='__main__':main()
