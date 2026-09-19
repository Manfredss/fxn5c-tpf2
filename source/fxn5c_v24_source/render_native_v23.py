"""Native-readback v23 review views and upright purchase-icon masters.

Run verify_native_v23.py first. These are Blender reconstructions of current
game resources, not screenshots or evidence of an in-game playtest.
Examples: Blender --background --python render_native_v23.py -- --jinwen
          Blender --background --python render_native_v23.py -- --icons-only
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import json
import re
import sys

import bpy

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen
from roster_v21 import ROSTER
from render_native import load_native
from render_native_v21 import setup,shot
from audit_running_gear_v23 import audit_readback_axes

MOD=ROOT/'staging/codex_fxn5c_1'
# @2x canonical masters; ordinary DPI is generated with exact 2x2 area means.
ICON_SPECS={
    'models_small':{'size':(640,150),'scale':28},
    'models_20':{'size':(192,40),'scale':36},
}
ICON_CAMERA=(7,-60,14)
ICON_TARGET=(0,0,2.2)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)


def native_inputs(stem,lods=(0,)):
    scene=ROOT/f'native_scene_{stem}.json'
    data=json.loads(scene.read_text(encoding='utf-8'))
    paths={MOD/f'res/models/model/vehicle/train/{stem}.mdl',scene,ROOT/'native_meshes.json'}
    for lod in lods:
        for node in walk(data['lods'][lod]['node']):
            for kind in ('mesh','skin'):
                if kind in node:
                    path=MOD/'res/models/mesh'/node[kind]
                    paths.update((path,Path(str(path)+'.blob')))
            for field in ('materials','skinMaterials'):
                for material in node.get(field,[]):
                    path=MOD/'res/models/material'/material;paths.add(path)
                    for reference in re.findall(r'fileName\s*=\s*"([^"]+)"',path.read_text(encoding='utf-8')):
                        texture=MOD/'res/textures'/reference
                        if texture.is_file():paths.add(texture)
    return {path.relative_to(ROOT).as_posix():sha(path) for path in sorted(paths)}


def output_row(path,kind,loc,scale,target,size,transparent=False):
    shot(path,loc,scale,target,*size,transparent)
    assert path.is_file() and path.stat().st_size>256,('missing render',path)
    return {'file':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,
            'kind':kind,'size':list(size),'camera':list(loc),'target':list(target),
            'orthographic_scale':scale,'transparent':transparent,'engine_playtest':False}


def view_specs(jinwen):
    # Horizontal I/II cab views are labelled by physical +X/-X end, never by
    # which way an oblique camera happens to show the locomotive facing.
    common=[
        ('overall',(23,-33,12),26,(0,0,2.1),(1800,900)),
        ('side',(0,-32,2.30),25,(0,0,2.30),(2000,700)),
        ('side_opposite',(0,32,2.30),25,(0,0,2.30),(2000,700)),
        ('cab_I_broadside',(9.20,-30,2.80),5.3,(9.20,0,2.80),(1500,1000)),
        ('cab_II_broadside',(-9.20,-30,2.80),5.3,(-9.20,0,2.80),(1500,1000)),
        ('bogie_side',(6.4,-20,1.02),6.7,(6.4,0,1.02),(1900,900)),
        ('bogie_opposite_end',(-6.4,-20,1.02),6.7,(-6.4,0,1.02),(1900,900)),
        ('bearing_coaxial',(8.2,-12,.84),2.25,(8.2,-1.3,.84),(1500,1100)),
        ('bogie_boxes_springs',(7.4,-10,1.25),3.2,(7.7,-1.1,1.04),(1500,1050)),
        ('cabinet_gap',(-2.88,-14,1.02),2.65,(-2.88,0,1.02),(1400,950)),
        ('front_plumbing',(11,-9,1.65),3.4,(9.95,-.8,1.11),(1400,950)),
        ('central_fascia',(0,-25,1.55),8.4,(0,0,1.55),(1900,850)),
        ('filler_gauge_logo',(.13,-15,1.17),2.65,(.13,0,1.17),(1700,1100)),
        ('filler_gauge_logo_opposite',(.4,15,1.17),2.65,(.4,0,1.17),(1700,1100)),
    ]
    if jinwen:
        common.extend([
            ('simsun_depot',(.3,-20,3.67),2.15,(.3,0,3.67),(1500,700)),
            ('cab_full_logo',(10.0,-22,2.19),1.36,(10.0,0,2.19),(1300,1000)),
        ])
    return common


def main():
    only_icons='--icons-only' in sys.argv;only_views='--views-only' in sys.argv
    assert not(only_icons and only_views),'Choose a single restricted mode'
    for jinwen in (False,True):
        if '--cr' in sys.argv and jinwen:continue
        if '--jinwen' in sys.argv and not jinwen:continue
        label='jinwen' if jinwen else 'cr'
        rows=[r for r in ROSTER if r['jinwen']==jinwen]
        icons=[];views=[];inputs={};axes=[]
        for row in rows:
            primary=row['number'] in ('0051','7006')
            if only_views and not primary:continue
            load_native(jinwen,row['stem']);setup()
            inputs.update(native_inputs(row['stem']))
            if primary:
                # Refuse a cosmetically convincing render if actual emitted
                # wheel/bearing end rings are still on different axes.
                axes.append(dict(model=row['stem'],**audit_readback_axes(0)))
            if not only_views:
                for kind,spec in ICON_SPECS.items():
                    path=ROOT/'ui_canonical_v23'/row['stem']/(kind+'.png')
                    rendered=output_row(path,'canonical_purchase_icon',ICON_CAMERA,spec['scale'],ICON_TARGET,spec['size'],True)
                    rendered.update(stem=row['stem'],number=row['number'],icon_kind=kind)
                    icons.append(rendered)
                path=ROOT/'fleet_preview_v23'/(row['number']+'.png')
                views.append(output_row(path,'fleet_cab_number',(9.5,-25,2.61),3.5,(9.5,0,2.61),(1200,800)))
            if primary:
                if not only_icons:
                    for name,loc,scale,target,size in view_specs(jinwen):
                        views.append(output_row(ROOT/'preview_v23'/row['stem']/(name+'.png'),name,loc,scale,target,size))
            print('RENDERED_V23',row['stem'],flush=True)
        if not only_icons:
            stem='fxn5c_jinwen' if jinwen else 'fxn5c'
            load_native(jinwen,stem,lod_index=1)
            inputs.update(native_inputs(stem,(1,)))
            axes.append(dict(model=stem,**audit_readback_axes(1)))
        mode='icons' if only_icons else 'views' if only_views else 'all'
        report={'status':'PASS','kind':'native_readback_render','style':label,'mode':mode,
            'created_utc':datetime.now(timezone.utc).isoformat(),'engine_playtest':False,
            'inputs':inputs,'icons':icons,'views':views,'native_axle_measurements':axes,
            'script_sha256':sha(__file__)}
        (ROOT/f'render_audit_v23_{label}_{mode}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('RENDER_AUDIT_PASS',label,mode,len(icons),len(views),flush=True)


if __name__=='__main__':main()
