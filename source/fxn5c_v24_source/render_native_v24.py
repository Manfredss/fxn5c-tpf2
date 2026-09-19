"""Current native v24 readback views with resolved conditional-light states.

Run only after verify_native_v24.py completes. Registers the new moon-white
material before loading native geometry; every image hides five inactive native
light instances. Singleton duplicates are explicitly deduplicated for preview,
not asserted to be exclusive in the engine. No image is an in-game screenshot.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,sys
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen
from roster_v21 import ROSTER
from render_native import load_native
from render_native_v21 import setup,shot
from render_native_v23 import native_inputs
from audit_running_gear_v23 import audit_readback_axes
import light_revision_v24 as lamps

ICON_SPECS={'models_small':{'size':(640,150),'scale':28},
            'models_20':{'size':(192,40),'scale':36}}
ICON_CAMERA=(7,-60,14)
ICON_TARGET=(0,0,2.2)
LIGHT_REPRESENTATIVES=('0051','0096','7006')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def state(model,row,direction='fwd',position='singleton',lod=0):
    lamps.validate_configuration(model,row['number'])
    report=lamps.apply_native_preview(model,direction,position,lod)
    require_visible=0 if lod>=2 else 1
    assert len(report['visible_names'])==require_visible,report
    actual_names={o.name for o in bpy.context.scene.objects if o.name.startswith('light24_')}
    assert actual_names==set(report['all_lamp_names']),('stale native lamp cohort',actual_names,report)
    nodes={n['name']:n for n in lamps.flatten(model['lods'][lod]['node'])}
    bindings={}
    for name in report['all_lamp_names']:
        obj=bpy.data.objects[name]
        assert obj.hide_render==(name not in report['visible_names'])
        refs=nodes[name]['materials']
        actual=[m.name for m in obj.data.materials]
        expected=['/'+str(Path(ref).with_suffix('')).replace('\\','/') for ref in refs]
        assert actual==expected,('native lamp material alias',name,actual,expected)
        bindings[name]={'native_materials':refs,'readback_materials':actual}
    report['cohort_inventory_exact']=True
    report['native_material_bindings']=bindings
    report['model']=row['stem'];report['number']=row['number']
    report['leading_cab']='I (+X)' if direction=='fwd' else 'II (-X)'
    report['leading_inner_pattern']=lamps.pattern_for(row['number'])
    report['local_cab_expectation']={'leading_outer':'moon-white','leading_top':'moon-white',
        'leading_inner':lamps.pattern_for(row['number']),'trailing_inner':'red',
        'trailing_outer':'off','trailing_top':'off'}
    report['preview_policy']='Resolve actual railVehicle Parts IDs; deduplicate identical singleton instances only'
    return report


def output(path,kind,loc,scale,target,size,light_state,transparent=False,illumination='day'):
    shot(path,loc,scale,target,*size,transparent)
    assert path.is_file() and path.stat().st_size>256,('missing render',path)
    return {'file':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'bytes':path.stat().st_size,
        'kind':kind,'size':list(size),'camera':list(loc),'target':list(target),'orthographic_scale':scale,
        'transparent':transparent,'illumination':illumination,'conditional_lights':dict(light_state),
        'engine_playtest':False}


def view_specs(jinwen):
    # Frontal views have identical camera/target Y and Z: no roof slope is
    # inferred from an elevated oblique projection.
    views=[
        ('overall',(23,-33,12),26,(0,0,2.1),(1800,900)),
        ('side',(0,-32,2.30),25,(0,0,2.30),(2000,700)),
        ('side_opposite',(0,32,2.30),25,(0,0,2.30),(2000,700)),
        ('roof_side_I',(9.3,-25,4.02),5.6,(9.3,0,4.02),(1600,750)),
        ('roof_threequarter',(17,-13,8.0),6.1,(9.3,0,4.05),(1500,1000)),
    ]
    for end,label in ((1,'I'),(-1,'II')):
        views.extend([
            ('front_'+label,(end*25,0,2.65),5.3,(end*10.8,0,2.65),(1050,1250)),
            ('roof_front_'+label,(end*25,0,4.24),3.90,(end*10.8,0,4.24),(1600,700)),
            ('front_marks_'+label,(end*25,0,2.16),3.4,(end*10.8,0,2.16),(1600,760)),
        ])
    if jinwen:
        views.append(('blue_belt_gap',(25,0,1.99),2.2,(10.8,0,1.99),(1600,650)))
    return views


def directional_views(model,row):
    views=[]
    for direction in ('fwd','bwd'):
        current=state(model,row,direction)
        for end,label in ((1,'I'),(-1,'II')):
            role='leading' if end==(1 if direction=='fwd' else -1) else 'trailing'
            path=ROOT/'light_preview_v24'/row['stem']/f'{direction}_{label}.png'
            item=output(path,'directional_lamp_state',(end*25,0,2.67),4.75,
                        (end*10.8,0,2.67),(850,1000),current)
            item.update(visible_cab=label,visible_cab_role=role)
            views.append(item)
    # One legible dusk readback per pattern. Change scene illumination only,
    # never increase emission or turn the inactive gate instances back on.
    current=state(model,row,'fwd')
    ambient=bpy.context.scene.world.node_tree.nodes.get('Background').inputs['Strength']
    old=ambient.default_value;ambient.default_value=.07
    sources=[(o,o.data.energy) for o in bpy.context.scene.objects if o.type=='LIGHT']
    for obj,energy in sources:obj.data.energy=energy*.16
    try:
        item=output(ROOT/'light_preview_v24'/row['stem']/'dusk_fwd_I.png','dusk_lamp_state',
                    (25,0,2.67),4.75,(10.8,0,2.67),(850,1000),current,illumination='dusk')
        item.update(visible_cab='I',visible_cab_role='leading');views.append(item)
    finally:
        ambient.default_value=old
        for obj,energy in sources:obj.data.energy=energy
    return views


def main():
    modes=[name for name in ('icons','views','lights') if '--'+name+'-only' in sys.argv]
    assert len(modes)<=1,'Choose only one restricted mode'
    mode=modes[0] if modes else 'all'
    for jinwen in (False,True):
        if '--cr' in sys.argv and jinwen:continue
        if '--jinwen' in sys.argv and not jinwen:continue
        label='jinwen' if jinwen else 'cr'
        icons=[];views=[];inputs={};axes=[]
        for row in (r for r in ROSTER if r['jinwen']==jinwen):
            primary=row['number'] in ('0051','7006')
            light_case=row['number'] in LIGHT_REPRESENTATIVES
            if mode in ('views','lights') and not(primary or light_case):continue
            lamps.register_source_materials(gen)
            load_native(jinwen,row['stem']);setup()
            model=json.loads((ROOT/f'native_scene_{row["stem"]}.json').read_text(encoding='utf-8'))
            current=state(model,row)
            inputs.update(native_inputs(row['stem']))
            if primary:axes.append(dict(model=row['stem'],**audit_readback_axes(0)))
            if mode in ('all','icons'):
                for kind,spec in ICON_SPECS.items():
                    path=ROOT/'ui_canonical_v24'/row['stem']/(kind+'.png')
                    item=output(path,'canonical_purchase_icon',ICON_CAMERA,spec['scale'],ICON_TARGET,
                                spec['size'],current,True)
                    item.update(stem=row['stem'],number=row['number'],icon_kind=kind);icons.append(item)
                views.append(output(ROOT/'fleet_preview_v24'/(row['number']+'.png'),'fleet_cab_number',
                                    (9.5,-25,2.61),3.5,(9.5,0,2.61),(1200,800),current))
            if primary and mode in ('all','views'):
                for name,loc,scale,target,size in view_specs(jinwen):
                    views.append(output(ROOT/'preview_v24'/row['stem']/(name+'.png'),
                                        name,loc,scale,target,size,current))
            if light_case and mode in ('all','views','lights'):
                views.extend(directional_views(model,row))
            print('RENDERED_V24',row['stem'],mode,flush=True)
        if mode in ('all','views'):
            row=next(r for r in ROSTER if r['number']==('7006' if jinwen else '0051'))
            lamps.register_source_materials(gen)
            load_native(jinwen,row['stem'],lod_index=1)
            inputs.update(native_inputs(row['stem'],(1,)))
            model=json.loads((ROOT/f'native_scene_{row["stem"]}.json').read_text(encoding='utf-8'))
            state(model,row,lod=1)
            axes.append(dict(model=row['stem'],**audit_readback_axes(1)))
        for name in ('render_native_v24.py','render_native_v23.py','render_native_v21.py',
                     'render_native.py','light_revision_v24.py'):
            inputs[name]=sha(ROOT/name)
        report={'status':'PASS','kind':'native_readback_render','style':label,'mode':mode,
            'created_utc':datetime.now(timezone.utc).isoformat(),'engine_playtest':False,'inputs':inputs,
            'icons':icons,'views':views,'native_axle_measurements':axes,'script_sha256':sha(__file__),
            'conditional_light_policy':'Actual Parts IDs; singleton exact duplicate instances deduplicated only in preview'}
        (ROOT/f'render_audit_v24_{label}_{mode}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('RENDER_AUDIT_PASS',label,mode,len(icons),len(views),flush=True)


if __name__=='__main__':main()
