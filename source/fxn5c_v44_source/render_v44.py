"""Final-native previews and thirteen level side-profile purchase icons.

The small original rail display is generated here and exists only in preview
pixels. No game stage, source blend or third-party rail asset is imported.
These are Blender reconstructions, not Model Editor or game screenshots.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,re,sys
import bpy
from mathutils import Matrix,Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
import generate_fxn5c as gen
import prototype_livery_v41 as paint
import waist_revision_v42 as waist
import light_revision_v24 as lamps
from render_native import load_native
from render_native_v21 import setup,shot
from animation_v26 import flatten_nodes
from animation_v28 import sample
from roster_v21 import ROSTER

MOD=ROOT/'staging/codex_fxn5c_1';RES=MOD/'res'
OUT=ROOT.parents[1]/'outputs/FXN5C_v0.44_preview/native'
STEMS={'cr':'fxn5c_0081','jw':'fxn5c_jinwen','prototype':'fxn5c_prototype_0001'}
ALL_ICONS=[r['stem']for r in ROSTER]+['fxn5c_menu_cr','fxn5c_menu_jinwen',STEMS['prototype']]
# Canonicals are the actual @2x purchase sizes, not unrelated large previews.
ICON_SPECS={'models_small':((356,112),25.6,3.33),'models_20':((128,40),25.6,3.20)}
HELPERS=('render_v44.py','render_native.py','render_native_v21.py','generate_fxn5c.py','materials_v04.py',
         'prototype_livery_v41.py','waist_revision_v42.py','light_revision_v24.py','animation_v26.py','animation_v28.py','roster_v21.py')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def relative(path):return Path(os.path.relpath(Path(path).resolve(),ROOT)).as_posix()


def ready(stem):
    manifest=load(ROOT/'manifest_v44.json');proof=load(ROOT/'validation_v44.json')
    assert manifest['status']=='NATIVE_STATIC_PASS' and proof['status']=='PASS','Final native verification not complete'
    assert manifest['validation_sha256']==sha(ROOT/'validation_v44.json'),'Native verification/manifest mismatch'
    for name in('native_scene_'+stem+'.json','native_meshes.json'):
        assert proof['render_inputs_sha256'][name]==sha(ROOT/name),('stale readback JSON',name)
    return proof


def register():
    paint.register_materials(gen);lamps.register_source_materials(gen)
    gen.MATERIAL_SPECS[waist.KEY]=waist.SPEC;gen.material(waist.KEY)


def evidence(stem,lod,proof):
    scene=ROOT/f'native_scene_{stem}.json';model=load(scene)
    files={scene,ROOT/'native_meshes.json',RES/'models/model/vehicle/train'/(stem+'.mdl')}
    external=[]
    for node in flatten_nodes(model['lods'][lod]['node']):
        for field in('mesh','skin'):
            if field in node:
                path=RES/'models/mesh'/node[field];files.update((path,Path(str(path)+'.blob')))
        for field in('materials','skinMaterials'):
            for ref in node.get(field,[]):
                path=RES/'models/material'/ref
                if not path.is_file():external.append(ref);continue
                files.add(path)
                for ref in re.findall(r'fileName\s*=\s*"([^"]+)"',path.read_text(encoding='utf8')):
                    files.add(RES/'textures'/ref)
        for animation in node.get('animations',{}).values():
            if animation.get('type')=='FILE_REF':files.add(RES/'models/animation'/animation['params']['id'])
    for image in bpy.data.images:
        if image.source=='FILE' and image.filepath:
            path=Path(bpy.path.abspath(image.filepath)).resolve()
            if path.is_file()and path.is_relative_to(ROOT):files.add(path)
    native={relative(p):sha(p)for p in sorted(files)}
    expected=proof['inputs_sha256']
    for name,digest in native.items():
        if name in expected:assert digest==expected[name],('native input changed after verification',name)
    for name in HELPERS:native[name]=sha(ROOT/name)
    return native,sorted(set(external))


def prepare(stem,lod):
    proof=ready(stem);register();load_native('jinwen' in stem,stem,lod)
    model=load(ROOT/f'native_scene_{stem}.json')
    state=lamps.apply_native_preview(model,'fwd','singleton',lod)
    assert len(state['visible_names'])==(0 if lod==2 else 1)
    for node in flatten_nodes(model['lods'][lod]['node']):
        if node.get('animations',{}).get('forever'):
            tf=sample(node,200,ROOT)
            bpy.data.objects[node['name']].matrix_local=Matrix([[tf[c*4+r]for c in range(4)]for r in range(4)])
    setup();inputs,external=evidence(stem,lod,proof)
    return state,inputs,external


def views():
    return [
        ('front',(35,0,2.45),5.4,(10.65,0,2.45),1150,1200),
        ('cab_side',(9.25,-25,3.28),4.8,(9.25,0,3.28),1600,1000),
        ('cab_corner',(19,-13,7.8),5.7,(9.5,-.25,3),1400,1100),
        ('front_three_quarter',(30,-36,15),25,(0,0,2.3),1650,1050),
        ('side',(0,-40,2.5),24.6,(0,0,2.5),1900,560),
        ('side_opposite',(0,40,2.5),24.6,(0,0,2.5),1900,560),
        ('lettering_oblique_m',(-6.3,-4.1,3.15),1.90,(-1.55,-1.65,2.79),1400,1000),
        ('lettering_oblique_p',(6.3,4.1,3.15),1.90,(1.55,1.65,2.79),1400,1000),
    ]


def display_material(name,color,metallic=0):
    mat=bpy.data.materials.new(name);mat.use_nodes=True
    mat.node_tree.nodes.clear()
    bsdf=mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled');output=mat.node_tree.nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(bsdf.outputs['BSDF'],output.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=.68;bsdf.inputs['Metallic'].default_value=metallic
    return mat


def display_box(name,center,scale,material):
    bpy.ops.mesh.primitive_cube_add(size=1,location=center)
    o=bpy.context.object;o.name='v44_display_'+name;o.scale=scale;o.data.materials.append(material)
    return o


def icon_stage():
    """Original geometrical rail-and-tie silhouette; railhead contact plane Z=0."""
    rail=display_material('v44_display_rail',(.17,.19,.20),.38)
    head=display_material('v44_display_railhead',(.35,.37,.37),.48)
    sleeper=display_material('v44_display_sleeper',(.14,.115,.085))
    for side in(-1,1):
        y=side*.7175
        display_box(f'railhead_{side}',(0,y,-.012),(24,.067,.024),head)
        display_box(f'railweb_{side}',(0,y,-.072),(24,.019,.096),rail)
        display_box(f'railfoot_{side}',(0,y,-.130),(24,.13,.020),rail)
    for i in range(40):
        display_box(f'sleeper_{i:02}',(-11.7+i*.6,0,-.1775),(.18,2.4,.075),sleeper)
    # Fairly broad frontal fill keeps dark wheels readable at 64-pixel width.
    bpy.ops.object.light_add(type='AREA',location=(0,-14,5))
    o=bpy.context.object;o.name='v44_icon_side_fill';o.data.energy=1900;o.data.size=18
    gen.point_camera(o,(0,0,2))
    return dict(original_generated_stage=True,third_party_assets=False,railhead_z=0,
                gauge_m=1.435,rail_length_m=24,sleepers=40,sleeper_pitch_m=.6,
                bounds=[[-12,-1.2,-.215],[12,1.2,0]],exported_to_game_geometry=False)


def raking_lights():
    for obj in bpy.data.objects:
        if obj.type=='LIGHT':obj.data.energy*=.18
    bpy.ops.object.light_add(type='AREA',location=(13,-9,6.5))
    o=bpy.context.object;o.name='v44_geometry_raking';o.data.energy=1600;o.data.size=3
    gen.point_camera(o,(9.9,0,3.2))


def level_camera_audit():
    scene=bpy.context.scene;cam=scene.camera
    points=[world_to_camera_view(scene,cam,Vector((x,0,0)))for x in(-12,12)]
    assert cam.data.type=='ORTHO'
    assert abs(points[0].y-points[1].y)<1e-6,('Rail not horizontal',points)
    assert points[0].x<points[1].x,'Side profile unexpectedly mirrored'
    return dict(projection='ORTHO',parallel_to_track=True,roll_degrees=0,side='negative_y',
                rail_end_screen_y=[float(p.y)for p in points],positive_x_at_screen_right=True,
                model_scale_changed=False,model_pose_changed=False)


def output(path,name,loc,scale,target,size,state,transparent=False):
    shot(path,loc,scale,target,*size,transparent)
    assert path.is_file()and path.stat().st_size>256
    return dict(file=relative(path),sha256=sha(path),name=name,width=size[0],height=size[1],
                camera=list(loc),target=list(target),orthographic_scale=scale,transparent=transparent,
                conditional_lights=dict(state),animation_sample_ms=200,engine_playtest=False)


def render(stem,lod,names=None,raking=False,icons=False):
    assert not icons or(lod==0 and not raking)
    state,inputs,external=prepare(stem,lod)
    rows=[];mode='icons'if icons else'raking'if raking else'views'
    if icons:
        stage=icon_stage()
        for kind,(size,scale,height)in ICON_SPECS.items():
            path=ROOT/'ui_canonical_v44'/stem/(kind+'.png')
            row=output(path,kind,(0,-40,height),scale,(0,0,height),size,state,True)
            row.update(stem=stem,icon_kind=kind,stage=stage,camera_audit=level_camera_audit());rows.append(row)
    else:
        if raking:raking_lights()
        specs=views();assert not names or set(names)<={r[0]for r in specs},('unknown views',names)
        target=OUT/stem/f'lod{lod}'
        if raking:target=target/'raking'
        for name,loc,scale,aim,w,h in specs:
            if names and name not in names:continue
            rows.append(output(target/(name+'.png'),name,loc,scale,aim,(w,h),state))
    report_path=ROOT/f'render_audit_v44_{stem}_lod{lod}_{mode}.json'
    if report_path.is_file():
        old=load(report_path)
        if old.get('inputs')==inputs:
            for row in old.get('icons'if icons else'views',[]):
                path=ROOT/row['file']
                if row['name']not in{r['name']for r in rows}and path.is_file()and sha(path)==row['sha256']:rows.append(row)
    report=dict(status='PASS',kind='native_resource_blender_reconstruction',stem=stem,lod=lod,mode=mode,
        generated_utc=datetime.now(timezone.utc).isoformat(),inputs=inputs,external_material_refs=external,
        icons=rows if icons else[],views=[]if icons else rows,engine_playtest=False,model_editor=False,
        material_limitation='Native geometry/material bindings reconstructed in Blender; not the game renderer.',script_sha256=sha(__file__))
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print('RENDER44_PASS',stem,lod,mode,len(rows),flush=True)


def main():
    args=sys.argv[sys.argv.index('--')+1:]if'--'in sys.argv else[]
    p=argparse.ArgumentParser();p.add_argument('--style',choices=('all','cr','jw','prototype'),default='prototype')
    p.add_argument('--stem',choices=ALL_ICONS);p.add_argument('--lod',type=int,choices=(0,1,2),default=0)
    p.add_argument('--views',nargs='+');p.add_argument('--raking',action='store_true');p.add_argument('--icons',action='store_true')
    a=p.parse_args(args)
    if a.icons:assert not a.views and not a.raking and a.lod==0
    if a.stem:stems=[a.stem]
    elif a.icons:
        stems=ALL_ICONS if a.style=='all'else[s for s in ALL_ICONS if
            ('prototype' in s if a.style=='prototype'else'jinwen'in s if a.style=='jw'else'jinwen'not in s and'prototype'not in s)]
    else:stems=list(STEMS.values())if a.style=='all'else[STEMS[a.style]]
    for stem in stems:render(stem,a.lod,a.views,a.raking,a.icons)


if __name__=='__main__':main()
