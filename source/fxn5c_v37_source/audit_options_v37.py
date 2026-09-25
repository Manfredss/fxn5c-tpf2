"""Execute the final packaged Lua modifier on all 12 actual native MDLs.

72 real resource cases = 12 models x 2 year policies x 3 motion modes.
Additional whitelist, path alias and nil/default input cases run in memory.
This executes Lua callbacks, not the game's animation/rendering engine.
"""
from pathlib import Path
from copy import deepcopy
import sys,json,hashlib
ROOT=Path(__file__).resolve().parent;MOD=ROOT/'staging/codex_fxn5c_1';RES=MOD/'res'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from lupa import LuaRuntime
from verify_native import plain


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def nodes(root):
    yield root
    for child in root.get('children',[]):yield from nodes(child)


def expected_result(model,policy,mode):
    expected=deepcopy(model)
    if policy==0:expected['metadata']['availability']={'yearFrom':0,'yearTo':0}
    for lod in expected['lods']:
        for n in nodes(lod['node']):
            if ((mode in (1,2) and n['name'].startswith('fxn5c_v26_louver_')) or
                (mode==2 and n['name'].startswith('fxn5c_v26_fan_'))):
                n.get('animations',{}).pop('forever',None)
    return expected


def main():
    lua=LuaRuntime(register_eval=False)
    lua.globals().package.path=(RES/'scripts/?.lua').as_posix()
    lua.execute('''
        function _(s) return s end
        function getCurrentModId() return "fxn5c_actual_test" end
        function addModifier(category, callback)
            assert(category=="loadModel")
            testCallback=callback
        end
    ''')
    lua.execute((MOD/'mod.lua').read_text(encoding='utf8'))
    config=lua.globals().data()
    files=sorted((RES/'models/model/vehicle/train').glob('*.mdl'));assert len(files)==12
    source={p.name:p.read_text(encoding='utf8') for p in files}
    original={}
    for p in files:
        lua.execute(source[p.name]);original[p.name]=plain(lua.globals().data())
    report=[];aliases=0;foreign_cases=0
    for policy in (0,1):
        for mode in (0,1,2):
            preferences=lua.table_from({'fxn5c_actual_test':dict(
                codex_fxn5c_year_policy=policy,codex_fxn5c_roof_animation=mode)},recursive=True)
            config.runFn(lua.table(),preferences);callback=lua.globals().testCallback
            for p in files:
                lua.execute(source[p.name]);model=lua.globals().data()
                result=plain(callback('vehicle/train/'+p.name,model))
                expected=expected_result(original[p.name],policy,mode)
                assert result==expected,('actual modifier mismatch',p.name,policy,mode)
                counts={'fan':0,'louver':0}
                for lod in result['lods']:
                    for n in nodes(lod['node']):
                        if n.get('animations',{}).get('forever'):
                            if n['name'].startswith('fxn5c_v26_fan_'):counts['fan']+=1
                            if n['name'].startswith('fxn5c_v26_louver_'):counts['louver']+=1
                assert counts=={'fan':4 if mode<2 else 0,'louver':52 if mode==0 else 0}
                # Always-open radiator transforms must survive all modes.
                fixed=[n for l in result['lods'] for n in nodes(l['node']) if n['name'].startswith('fxn5c_v26_louver_side_')]
                assert len(fixed)==80 and all(not n.get('animations') for n in fixed)
                import math
                assert all(abs(abs(math.degrees(math.atan2(n['transf'][6],n['transf'][5])))-55)<1e-5 for n in fixed)
                report.append(dict(model=p.name,year_policy=policy,motion_mode=mode,
                    active_forever_nodes=counts,geometry_hierarchy_other_metadata_exact=True))
                # Exercise the actual Steam/mod-directory filename forms,
                # not just a synthetic require() override or fake model.
                for alias in ('res/models/model/vehicle/train/'+p.name,
                              'C:\\mods\\codex_fxn5c_1\\res\\models\\model\\vehicle\\train\\'+p.name):
                    native=lua.globals().data()
                    assert plain(callback(alias,native))==expected
                    aliases+=1
            p=files[0]
            for foreign in ('fxn5c.mdl','vehicle/train/fxn5c_extra.mdl','vehicle/train/notfxn5c.mdl',
                'vehicle/train/foreign/fxn5c.mdl','vehicle/train/FXN5C.mdl',
                'res/models/model/vehicle/train/fxn5c_other.mdl'):
                lua.execute(source[p.name]);native=lua.globals().data()
                assert plain(callback(foreign,native))==original[p.name],('foreign model mutated',foreign)
                foreign_cases+=1
            for malformed in (None,False,'not a model'):
                assert callback('vehicle/train/'+p.name,malformed)==malformed
    # The absence of saved preferences must use all animation + ignore years.
    config.runFn(lua.table(),None);callback=lua.globals().testCallback
    for p in files:
        lua.execute(source[p.name]);native=lua.globals().data()
        assert plain(callback('vehicle/train/'+p.name,native))==expected_result(original[p.name],0,0)
    parameters=plain(config.info.params)
    motion=next(p for p in parameters if p['key']=='codex_fxn5c_roof_animation')
    assert motion['defaultIndex']==0 and len(motion['values'])==3
    lua.execute((MOD/'strings.lua').read_text(encoding='utf8'));translations=plain(lua.globals().data())
    for lang in ('en','zh_CN'):
        assert lang in translations
        for key in [motion['name'],motion['tooltip'],*motion['values']]:
            assert translations[lang].get(key),('missing option translation',lang,key)
    inputs=files+[MOD/'mod.lua',RES/'scripts/fxn5c_animation_v26.lua',MOD/'strings.lua']
    result=dict(status='PASS',actual_model_cases=len(report),cases=report,resource_path_alias_cases=aliases,
        validator_sha256=sha(Path(__file__)),
        foreign_resource_unchanged_cases=foreign_cases,nil_preferences_cases=len(files),
        method='Actual final mod.lua require/module and 12 final MDL tables executed by Lua; independent expected field-level comparison',
        inputs_sha256={p.relative_to(ROOT).as_posix():sha(p) for p in inputs},
        limitations='Load-time Lua behavior only; native animation engine, Model Editor and game not executed',
        model_editor_verified=False,game_verified=False)
    (ROOT/'options_validation_v37.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('OPTIONS26_PASS',len(report),aliases,foreign_cases,flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        (ROOT/'options_validation_v37.json').write_text(json.dumps(dict(status='FAIL',error=repr(error),game_verified=False),indent=2),encoding='utf8')
        raise
