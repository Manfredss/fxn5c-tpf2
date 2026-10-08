"""Execute actual Lua catalogue in lupa; optionally inspect all emitted MDLs.

--fixtures-only tests isolated generated mod/strings in a temporary directory.
Default mode reads staging, checks twelve native files, writes a JSON audit.
This checks definitions and Lua behavior, not rendering of the in-game UI.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
for runtime in (ROOT/'runtime',ROOT.parent/'fxn5c_v20_source/runtime'):
    if (runtime/'lupa').exists():sys.path.insert(0,str(runtime));break
from lupa import LuaRuntime
from roster_v21 import ROSTER,description_key,group_stem
from catalogue_v21 import GROUPS,MOD_ROOT,YEAR_KEY,write_catalogue


def plain(value):
    if hasattr(value,'items'):
        return {k:plain(v) for k,v in value.items()}
    return value


def read_lua(path):
    vm=LuaRuntime(register_eval=False)
    vm.execute('function _(s) return s end')
    vm.execute(path.read_text(encoding='utf-8'))
    return plain(vm.globals().data())


def runtime(mod_path,selection='missing'):
    vm=LuaRuntime(register_eval=False)
    vm.execute('''function _(s) return s end
      function getCurrentModId() return "codex_fxn5c_1" end
      callbacks = {}
      function addModifier(kind, fn) assert(kind == "loadModel"); table.insert(callbacks,fn) end
    ''')
    vm.execute(mod_path.read_text(encoding='utf-8'))
    mod=vm.globals().data()
    params=None
    if selection!='nil':
        entry={} if selection=='missing' else {YEAR_KEY:selection}
        params=vm.table_from({'codex_fxn5c_1':vm.table_from(entry)})
    mod['runFn'](vm.table(),params)
    return vm,mod


def apply(vm,filename,model):
    value=vm.table_from(model,recursive=True)
    before=plain(value)
    for _,fn in vm.globals().callbacks.items():
        result=fn(filename,value)
        assert vm.eval('function(a,b) return rawequal(a,b) end')(value,result)
        value=result
    return before,plain(value)


def fixture_model(year=2024):
    return {'metadata':{'availability':{'yearFrom':year,'yearTo':2044,'other':9},
        'transportVehicle':{'multipleUnitOnly':False,'carrier':'RAIL'},'untouched':'sentinel'},'version':1}


def audit_switch(target):
    expected=[r['stem'] for r in ROSTER]+list(GROUPS)
    cases=0
    for selection in ('nil','missing',0,1,2):
        vm,mod=runtime(target/'mod.lua',selection)
        info=plain(mod['info']);parameter=info['params'][1]
        assert info['minorVersion']==21
        assert parameter['key']==YEAR_KEY and parameter['uiType']=='COMBOBOX'
        assert parameter['defaultIndex']==0 and len(parameter['values'])==2
        assert len(vm.globals().callbacks)==(0 if selection==1 else 1)
        for stem in expected:
            relative=f'vehicle/train/{stem}.mdl'
            paths=[relative,'res/models/model/'+relative,
                   'mods/codex_fxn5c_1/res/models/model/'+relative,
                   'G:/SteamLibrary/steamapps/workshop/content/1066780/123456/res/models/model/'+relative]
            for path in paths+[p.replace('/','\\') for p in paths]:
                before,after=apply(vm,path,fixture_model(2025 if 'jinwen' in stem else 2024))
                want=json.loads(json.dumps(before))
                if selection!=1:want['metadata']['availability'].update(yearFrom=0,yearTo=0)
                assert after==want,(selection,path,before,after)
                cases+=1
        external=['vehicle/train/fxn5c_other.mdl','vehicle/train/not_fxn5c.mdl',
                  'vehicle/train/sub/fxn5c.mdl','vehicle/train/fxn5c.mdl.extra',
                  'vehicle/train/fxn5c.mdl/extra','vehicle/car/fxn5c.mdl','fxn5c.mdl',
                  'vehicle/train/fxn5c_7000.mdl','res/models/model/vehicle/train/fxn5c_7000.mdl',
                  'mods/another/res/models/model/vehicle/train/another_train.mdl',None,42]
        for path in external:
            before,after=apply(vm,path,fixture_model())
            assert after==before,(selection,'external mutation',path)
            cases+=1
        for model in ({},{'metadata':{}},{'metadata':{'availability':False}}):
            before,after=apply(vm,'vehicle/train/fxn5c.mdl',model)
            assert after==before
            cases+=1
    strings=read_lua(target/'strings.lua')
    assert set(strings)=={'en','zh_CN'} and set(strings['en'])==set(strings['zh_CN'])
    assert all(isinstance(v,str) and v for lang in strings.values() for v in lang.values())
    source=(target/'mod.lua').read_text(encoding='utf-8')
    keys=set(re.findall(r'_\("([^"\n]+)"\)',source))
    for row in ROSTER:
        keys.update(description_key(row)+suffix for suffix in ('_NAME','_DESC'))
    for key in GROUPS.values():keys.update(key+suffix for suffix in ('_NAME','_DESC'))
    for lang,values in strings.items():
        assert keys<=set(values),(lang,keys-set(values))
    for row in ROSTER:
        for lang in strings.values():assert row['number'] in lang[description_key(row)+'_NAME']
        assert row['depot'] in strings['zh_CN'][description_key(row)+'_NAME']
        assert '定制' in strings['zh_CN'][description_key(row)+'_DESC']
    return {'lua_fixture_cases':cases,'languages':list(strings),'translation_keys':len(strings['en']),
            'model_resource_whitelist_count':len(expected),'policy_default':0,'policy_keep':1,
            'modifiers_change_only_availability':True},strings


def audit_models(target,strings):
    model_dir=target/'res/models/model/vehicle/train'
    expected={r['stem'] for r in ROSTER}|set(GROUPS)
    actual={p.stem for p in model_dir.glob('*.mdl')}
    assert actual==expected,('catalogue model set',expected-actual,actual-expected)
    models={stem:read_lua(model_dir/(stem+'.mdl')) for stem in expected}
    rows=[]
    for row in ROSTER:
        stem=row['stem'];model=models[stem];meta=model['metadata']
        tv=meta['transportVehicle'];key=description_key(row)
        assert tv['groupFileName']=='vehicle/train/'+group_stem(row)+'.mdl'
        assert tv.get('multipleUnitOnly') is False
        assert meta['availability']['yearFrom']==(2025 if row['jinwen'] else 2024)
        assert meta['description']['name']==key+'_NAME'
        assert meta['description']['description']==key+'_DESC'
        for lang in strings.values():
            assert meta['description']['name'] in lang and meta['description']['description'] in lang
        rows.append({'stem':stem,'number':row['number'],'depot_custom':row['depot'],
                     'group':group_stem(row),'yearFrom':meta['availability']['yearFrom']})
    for stem,key in GROUPS.items():
        meta=models[stem]['metadata'];tv=meta['transportVehicle']
        assert tv['multipleUnitOnly'] is True
        assert not tv.get('groupFileName'),('recursive group header',stem)
        assert meta['description']=={'name':key+'_NAME','description':key+'_DESC'}
        assert meta['availability']['yearFrom']==(2025 if 'jinwen' in stem else 2024)
    # Number variants of each livery must share the already-audited rod resources.
    def skins(value):
        if not isinstance(value,dict):return []
        result=[value['skin']] if 'skin' in value else []
        for child in value.values():result.extend(skins(child))
        return sorted(result)
    for row in ROSTER:
        base='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        assert skins(models[row['stem']])==skins(models[base]),('different dynamic skin',row['stem'])
        assert len(skins(models[row['stem']]))==2
    return rows


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixtures-only',action='store_true')
    args=parser.parse_args()
    if args.fixtures_only:
        with tempfile.TemporaryDirectory(prefix='fxn5c_catalogue21_') as folder:
            target=write_catalogue(Path(folder))
            info,_=audit_switch(target)
        print(json.dumps({'status':'PASS_FIXTURES_ONLY','game_ui_verified':False,**info},ensure_ascii=False,indent=2))
        return
    info,strings=audit_switch(MOD_ROOT)
    rows=audit_models(MOD_ROOT,strings)
    inputs=[MOD_ROOT/'mod.lua',MOD_ROOT/'strings.lua']+list((MOD_ROOT/'res/models/model/vehicle/train').glob('*.mdl'))
    report={'status':'PASS','scope':'Lua definitions, translations, exact-ID modifier and native catalogue; NOT game UI test',
            'game_ui_verified':False,**info,'vehicles':rows,'groups':GROUPS,
            'inputs_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
    out=ROOT/'catalogue_audit_v21.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'models':len(rows),'groups':len(GROUPS),'report':str(out)},ensure_ascii=False))


if __name__=='__main__':main()
