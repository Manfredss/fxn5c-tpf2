from pathlib import Path
import sys, json, argparse
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from prepare_scene_v24 import prepare
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
parser=argparse.ArgumentParser();parser.add_argument('--lod',type=int,default=1);parser.add_argument('--cr',action='store_true');parser.add_argument('--apply',action='store_true');parser.add_argument('--save',action='store_true');parser.add_argument('--render',action='store_true')
opts=parser.parse_args(args)
b=prepare(opts.lod,not opts.cr)
if opts.apply:
    from roof_revision_v24 import apply
    report=apply(b,not opts.cr)
    (ROOT/'runtime'/f'roof24_apply_{"cr" if opts.cr else "jw"}_lod{opts.lod}.json').write_text(json.dumps(report,indent=2),encoding='utf8')
rows=[]
for obj in bpy.context.scene.objects:
    if obj.type!='MESH':continue
    pts=[obj.matrix_world@v.co for v in obj.data.vertices]
    if not pts or max(p.z for p in pts)<3.95:continue
    if not any(s in obj.name for s in ('roof','hood','brow','lamp','reflector','optic','antenna','aerial','ac_','aircon','radiator','exhaust','glazing','body_open')):continue
    obj.data.calc_loop_triangles()
    rows.append({'name':obj.name,'tri':len(obj.data.loop_triangles),'min':[round(min(p[k] for p in pts),5) for k in range(3)],'max':[round(max(p[k] for p in pts),5) for k in range(3)],'mats':[m.name for m in obj.data.materials]})
(ROOT/'runtime'/'roof24_probe.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
print('ROOF24_PROBE',len(rows),sum(r['tri'] for r in rows))
total=0
for obj in bpy.context.scene.objects:
    if obj.type=='MESH' and not obj.name.startswith('bounds|'):
        obj.data.calc_loop_triangles();total+=len(obj.data.loop_triangles)
print('TOTAL_TRIANGLES',total,flush=True)
if opts.save:
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'runtime'/f'roof24_probe_{"cr" if opts.cr else "jw"}_lod{opts.lod}.blend'))
if opts.render:
    from render_native_v21 import setup,shot
    for obj in bpy.context.scene.objects:
        if obj.type in ('LIGHT','CAMERA'):bpy.data.objects.remove(obj,do_unlink=True)
        elif obj.name.startswith('bounds|'):obj.hide_render=True
    setup()
    for name,loc,target,scale,size in [
        ('front',(35,0,3.8),(10,0,3.8),4.0,(1100,800)),
        ('side',(0,-40,4.2),(0,0,4.2),24,(2000,600)),
        ('cab',(9,-25,4.15),(9,0,4.15),4.2,(1300,800)),
        ('roof',(14,-14,11),(7.2,0,4.25),9,(1500,1100))]:
        shot(ROOT/'runtime'/f'roof24_{"cr" if opts.cr else "jw"}_{name}.png',loc,scale,target,*size)
