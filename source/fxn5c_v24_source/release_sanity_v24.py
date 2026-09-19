"""Independent archived-resource and evidence audit, not an engine test."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import argparse,ast,hashlib,json,struct,sys
from PIL import Image,ImageOps
_runtime=Path(__file__).resolve().parent/'runtime'
if (_runtime/'lupa').is_dir():sys.path.insert(0,str(_runtime))
from lupa import LuaRuntime
from package_release_v24 import (ROOT,OUT,HISTORICAL,REPORTS,PATCH_MANIFEST,SCENES,
    SOURCE_ENTRIES,DOCS,GAME_DOCS,STYLES,STEMS,MODEL_STEMS,REVIEW_IMAGES,BASE_GAME_MATERIALS)
ICON_SIZES={'models_small':(640,150),'models_20':(192,40)}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def plain(value):return {k:plain(v) for k,v in value.items()} if hasattr(value,'items') else value
def lua(raw):
    vm=LuaRuntime(register_eval=False);vm.execute('function _(s) return s end')
    vm.execute(raw.decode('utf-8'));return plain(vm.globals().data())
def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from walk(child)
    elif isinstance(value,list):
        for child in value:yield from walk(child)
def safe(name):
    p=Path(name)
    assert not p.is_absolute() and '..' not in p.parts and '\\' not in name,('unsafe',name)
    assert not any(t in name.lower() for t in ('/reference/','codex-clipboard','__pycache__'))
    if '/runtime/' in name.lower():
        assert '/runtime/patch_inputs_v24/' in name and (name.endswith('.msh') or name.endswith('.msh.blob')),name
    assert p.suffix.lower() not in {'.blend1','.dll','.pyd','.exe','.pyc','.ttf','.ttc','.otf','.woff','.woff2',
        '.webp','.jpeg','.bmp','.gif','.heic','.mp4','.pdf'},name
    assert not name.endswith('@2.tga') and not p.name.startswith('bogie_frame_lod'),name
    assert not name.endswith('.jpg') or name.endswith('/workshop_preview.jpg'),name

def resource_closure(z,base):
    names=set(z.namelist());needed=set();meshes=set();materials=set();external=set()
    for stem in MODEL_STEMS:
        name=base+f'res/models/model/vehicle/train/{stem}.mdl';assert name in names;needed.add(name)
        for node in walk(lua(z.read(name))):
            for field in ('mesh','skin'):
                if field in node:meshes.add(node[field])
            for field in ('materials','skinMaterials'):materials.update(node.get(field,{}).values())
    for ref in meshes:
        safe(ref)
        for suffix in ('','.blob'):
            name=base+'res/models/mesh/'+ref+suffix;assert name in names,('missing mesh',name);needed.add(name)
    for ref in materials:
        safe(ref);name=base+'res/models/material/'+ref
        if name not in names:
            assert ref in BASE_GAME_MATERIALS,('missing material',name);external.add(ref);continue
        needed.add(name)
        for node in walk(lua(z.read(name))):
            if 'fileName' in node:
                safe(node['fileName']);name=base+'res/textures/'+node['fileName']
                assert name in names,('missing texture',name);needed.add(name)
    actual={n for n in names if n.startswith(base+'res/models/') or n.startswith(base+'res/textures/models/')}
    assert needed==actual,('native closure',actual-needed,needed-actual)
    return dict(native_meshes=len(meshes),materials=len(materials),external=external)

def localized_mdl_checks(z,base):
    translations=lua(z.read(base+'strings.lua'));cases=0
    assert set(translations)=={'en','zh_CN'}
    for stem in MODEL_STEMS:
        raw=z.read(base+f'res/models/model/vehicle/train/{stem}.mdl')
        keys=lua(raw)['metadata']['description']
        for language,table in translations.items():
            calls=[]
            def translate(key):
                calls.append(key);return table[key]
            vm=LuaRuntime(register_eval=False);vm.globals()['_']=translate
            vm.execute(raw.decode('utf-8'));actual=plain(vm.globals().data())['metadata']['description']
            assert actual=={field:table[key] for field,key in keys.items()},('untranslated archived name',stem,language)
            assert sorted(calls)==sorted(keys.values()),('archived translation call cohort',stem,language)
            cases+=1
    assert cases==24
    return cases

def source_checks(z,prefix,hashes):
    names=set(z.namelist())
    def bound(name,h):
        safe(name);full=prefix+name
        assert full in names,('bound artifact absent',name)
        if full not in hashes:hashes[full]=digest(z.read(full))
        assert hashes[full]==h,('bound artifact changed',name)
    for n in tuple(SOURCE_ENTRIES)+tuple(DOCS)+tuple(REPORTS)+tuple(SCENES)+(PATCH_MANIFEST,):assert prefix+n in names,n
    for name in names:
        rel=name.removeprefix(prefix)
        if not rel.endswith('.py') or '/' in rel:continue
        for node in ast.walk(ast.parse(z.read(name).decode('utf-8-sig'))):
            modules=[a.name for a in node.names] if isinstance(node,ast.Import) else \
                [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for module in modules:
                local=module.split('.')[0]+'.py'
                if (ROOT/local).is_file():assert prefix+local in names,('unclosed local import',name,local)
    assert {n for n in names if n.endswith('.blend')}=={prefix+s+'_source.blend' for s in STYLES}
    assert sum(n.endswith('.fbx') for n in names)==6
    canonical={prefix+f'ui_canonical_v24/{stem}/{kind}.png' for stem in STEMS for kind in ICON_SIZES}
    assert {n for n in names if n.startswith(prefix+'ui_canonical_v24/')}==canonical
    for name in names:
        rel=name.removeprefix(prefix)
        if '/' not in rel and rel.endswith('.json'):assert rel in set(REPORTS)|set(SCENES)|{PATCH_MANIFEST},('old report',name)
    assert len(REPORTS)==21
    reports={n:json.loads(z.read(prefix+n)) for n in REPORTS}
    for name,report in reports.items():
        assert report['status']=='PASS',name
        for block in walk(report):
            for key in ('inputs_sha256','input_sha256','inputs'):
                values=block.get(key,{})
                if not isinstance(values,dict):continue
                for n,h in values.items():
                    assert isinstance(h,str) and len(h)==64,('invalid digest',name,key,n)
                    bound(n.replace('\\','/'),h)
    fleet=reports['validation_fleet_v24.json']
    assert len(fleet['models'])==10 and {r['variant'] for r in fleet['models']}==set(STEMS)
    for row in fleet['models']:assert row==reports[f"validation_{row['variant']}_v24.json"]
    catalogue=reports['catalogue_audit_v24.json']
    assert len(catalogue['vehicles'])==10 and len(catalogue['groups'])==2 and catalogue['lua_fixture_cases']==555
    loc=catalogue['runtime_localization']
    assert loc['localized_model_language_cases']==24 and loc['localized_description_fields']==48 and loc['identity_only_negative_controls']==24
    fbx=reports['fbx_audit_v24.json']['models']
    assert {(r['style'],r['lod']) for r in fbx}=={(s,l) for s in STYLES for l in (0,1,2)}
    assert all(r['triangles']>0 and r['exact_native_material_counts'] for r in fbx)
    sources=reports['audit_sources_v24.json']
    assert {r['file'] for r in sources['sources']}=={s+'_source.blend' for s in STYLES}
    assert sources['negative_controls_passed']==6
    for row in sources['sources']:
        bound(row['file'],row['source_sha256']);assert row['candidate_recipe_applied'] is False
    roof=reports['roof_audit_v24.json']
    assert roof['mode']=='actual_saved_sources_and_current_native_LOD0' and roof['candidate_recipe_applied_without_save'] is False
    assert len(roof['results'])==len(roof['native_checks'])==2
    for row in roof['native_checks']:
        assert len(row['all_glazing_checked'])==26 and row['new_roof_native_vertex_max_residual_m']<2e-5
        assert all(r['bidirectional_max_residual_m']<2e-5 for r in row['all_glazing_checked'])
    lamps=reports['light_audit_v24.json']
    assert len(lamps['models'])==10 and len(lamps['negative_controls'])==4 and lamps['engine_tested'] is False
    assert all(len(r['geometry'])==4 for r in lamps['models'])
    outputs=set()
    for label,count in (('cr',8),('jinwen',2)):
        report=reports[f'render_audit_v24_{label}_all.json']
        assert report['engine_playtest'] is False and report['style']==label and report['mode']=='all'
        bound('render_native_v24.py',report['script_sha256'])
        assert len(report['icons'])==count*2 and sum(r['kind']=='fleet_cab_number' for r in report['views'])==count
        basic={r['kind'] for r in report['views']}
        assert {'front_I','front_II','roof_front_I','roof_front_II','roof_side_I','roof_threequarter','front_marks_I','front_marks_II'}<=basic
        if label=='jinwen':assert 'blue_belt_gap' in basic
        for row in report['native_axle_measurements']:
            assert row['status']=='PASS' and all(p['alignment_error_m']<.00001 for p in row['rings'])
        for row in report['icons']+report['views']:
            bound(row['file'],row['sha256']);full=prefix+row['file'];assert full not in outputs;outputs.add(full)
            raw=z.read(full);assert len(raw)==row['bytes'] and list(Image.open(BytesIO(raw)).size)==row['size']
            state=row['conditional_lights'];assert len(state['visible_names'])==1
            assert len(state['all_lamp_names'])==6 and set(state['visible_names'])<=set(state['all_lamp_names'])
    actual={n for n in names if any(n.startswith(prefix+p) for p in ('preview_v24/','fleet_preview_v24/','ui_canonical_v24/','light_preview_v24/'))}
    assert actual==outputs,('render output cohort',actual-outputs,outputs-actual)
    review=reports['review_audit_v24.json']
    for row in review['outputs']:bound(row['file'],row['sha256'])
    assert {n for n in names if n.endswith('.png')}==outputs|{prefix+n for n in REVIEW_IMAGES},'unexpected source rasters'
    patch=json.loads(z.read(prefix+PATCH_MANIFEST))
    assert patch['status']=='BUILT_PENDING_AUDIT' and len(patch['patches'])==6
    assert {(r['style'],r['lod'],r['attachment']) for r in patch['patches']}=={(s,l,'body') for s in STYLES for l in (0,1,2)}
    proof={prefix+r[p]['file']+s for r in patch['patches'] for p in ('before','after') for s in ('','.blob')}
    assert len(proof)==24 and {n for n in names if '/runtime/' in n}==proof
    for row in patch['patches']:
        bound(row['target'],row['mesh_sha256']);bound(row['target']+'.blob',row['blob_sha256'])
        raw=z.read(prefix+row['target']+'.blob');desc=lua(z.read(prefix+row['target']))
        for attr,h in row['original_attribute_prefix_sha256'].items():
            field=desc['vertexAttr'][attr];size=row['original_vertices']*field['numComp']*4
            assert field['count']==size+row['added_vertices']*field['numComp']*4
            assert digest(raw[field['offset']:field['offset']+size])==h,('original attribute prefix changed',row['target'],attr)
    assert len(patch['panes'])==24 and len(patch['signage'])==20
    assert {(r['style'],r['lod'],r['name']) for r in patch['panes']}=={(s,l,f'glazing_{n:02d}') for s in STYLES for l in (0,1) for n in (0,1,2,7,8,9)}
    assert {(r['model'],r['lod']) for r in patch['signage']}=={(s,l) for s in STEMS for l in (0,1)}
    for alias,stem in (('native_scene.json','fxn5c'),('native_scene_jinwen.json','fxn5c_jinwen')):
        assert json.loads(z.read(prefix+alias))==json.loads(z.read(prefix+f'native_scene_{stem}.json'))
    for row in patch['panes']:
        bound(row['target'],row['mesh_sha256']);bound(row['target']+'.blob',row['blob_sha256'])
    for row in patch['sources']:bound(row['file'],row['sha256'])
    for n,h in patch['inputs_sha256'].items():bound(n,h)
    native=reports['audit_native_patch_v24.json']
    assert len(native['patches'])==6 and len(native['models'])==12 and len(native['negative_controls'])==4
    assert native['preservation']['count']==len(native['preservation']['unchanged_resources'])
    for n in native['preservation']['unchanged_resources']:assert native['inputs_sha256'][n]==native['baseline_sha256'][n]
    icons=reports['ui_icon_audit_v24.json']
    assert len(icons['icons'])==48 and icons['engine_playtest'] is False
    bound('ui_icons_v24.py',icons['script_sha256'])
    for row in icons['render_reports']:bound(row['file'],row['sha256'])
    for row in icons['icons']:
        bound(row['file'],row['sha256']);bound(row['canonical'],row['canonical_sha256'])
    return dict(current_reports=len(reports),source_dependency_closure=True,hash_bound_inputs_outputs=True,
        patch_proof_files=len(proof),native_attribute_prefixes=6,actual_render_outputs=len(outputs))

def icon_checks(z,base,prefix=None):
    expected={base+f'res/textures/ui/{kind}/vehicle/train/{stem}{suffix}.tga'
        for stem in MODEL_STEMS for kind in ICON_SIZES for suffix in ('','@2x')}
    assert {n for n in z.namelist() if n.startswith(base+'res/textures/ui/')}==expected
    for name in expected:
        raw=z.read(name);assert raw[0:3]==bytes((0,0,2)) and raw[16]==32 and raw[17]==0
        kind=name.removeprefix(base+'res/textures/ui/').split('/')[0]
        size=ICON_SIZES[kind] if '@2x' in name else tuple(v//2 for v in ICON_SIZES[kind])
        im=Image.open(BytesIO(raw)).convert('RGBA')
        assert im.size==size and struct.unpack('<HH',raw[12:16])==size and len(raw)==18+size[0]*size[1]*4
        assert raw[18:18+im.width*4]==im.crop((0,im.height-1,im.width,im.height)).tobytes('raw','BGRA')
        box=im.getchannel('A').getbbox();assert box and box[0]>0 and box[1]>0 and box[2]<im.width and box[3]<im.height
        if prefix:
            stem=Path(name).stem.removesuffix('@2x')
            stem={'fxn5c_menu_cr':'fxn5c','fxn5c_menu_jinwen':'fxn5c_jinwen'}.get(stem,stem)
            canonical=Image.open(BytesIO(z.read(prefix+f'ui_canonical_v24/{stem}/{kind}.png'))).convert('RGBA')
            if '@2x' not in name:canonical=canonical.resize(size,Image.Resampling.BOX)
            assert canonical.tobytes()==im.tobytes() and ImageOps.flip(canonical).tobytes()!=im.tobytes(),('icon orientation',name)
    return len(expected)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT)
    out=parser.parse_args().output.resolve()
    for n,h in HISTORICAL.items():assert digest((OUT/n).read_bytes())==h,('v23 changed',n)
    path=out/'FXN5C_v0.24_manifest.json';manifest=json.loads(path.read_text(encoding='utf-8'))
    assert manifest['historical_v23_sha256']==HISTORICAL and set(manifest['reports'])==set(REPORTS)
    assert {r['file'] for r in manifest['archives']}=={'FXN5C_TPF2_v0.24.zip','FXN5C_Source_v0.24.zip'}
    game_bytes={};results=[]
    for item in sorted(manifest['archives'],key=lambda r:'Source' in r['file']):
        archive=out/item['file'];assert archive.stat().st_size==item['bytes'] and digest(archive.read_bytes())==item['sha256']
        source='Source' in item['file'];prefix='FXN5C_Source_v0.24/' if source else ''
        base=prefix+('staging/' if source else '')+'codex_fxn5c_1/'
        with ZipFile(archive) as z:
            assert z.testzip() is None
            names=z.namelist();assert len(names)==len(set(names)) and all(n.startswith(prefix if source else base) for n in names)
            assert set(names)=={r['path'] for r in item['entries']};hashes={}
            for row in item['entries']:
                name=row['path'];safe(name);hashes[name]=digest(z.read(name));assert hashes[name]==row['sha256']
                local=(ROOT/row['source']).resolve();assert local.is_relative_to(ROOT.resolve()) and digest(local.read_bytes())==row['sha256']
                if not source:game_bytes[name]=hashes[name]
                elif name.startswith(base):assert game_bytes[name.removeprefix(prefix+'staging/')]==hashes[name],'source/game payload differs'
            assert lua(z.read(base+'mod.lua'))['info']['minorVersion']==24
            assert {n.removeprefix(base+'documents/') for n in names if n.startswith(base+'documents/')}==set(GAME_DOCS)
            native=resource_closure(z,base);assert native.pop('external')==set(manifest['external_base_game_materials'])
            localized=localized_mdl_checks(z,base)
            icons=icon_checks(z,base,prefix if source else None)
            detail=source_checks(z,prefix,hashes) if source else {}
            results.append(dict(file=item['file'],sha256=item['sha256'],files=len(names),crc_pass=True,
                native_reference_closure=True,current_source_bytes_match=True,ui_icons=icons,localized_model_language_cases=localized,**native,**detail))
    for n,h in HISTORICAL.items():assert digest((OUT/n).read_bytes())==h
    report=dict(status='PASS',archives=results,historical_v23_unchanged=True,
        scope='Archived bytes, current reports, native resource/import closure, retained attributes and upright icons; NOT engine runtime',
        game_installation_modified=False,game_verified=False,steam_uploaded=False)
    report_path=out/'FXN5C_v0.24_release_checks.json';report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest['status']='STATIC_PASS';manifest['independent_sanity']=dict(file=report_path.name,sha256=digest(report_path.read_bytes()),status='PASS')
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
