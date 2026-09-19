"""Hash-gated v24 archives; no installation or publishing."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse,hashlib,json,shutil
import package_release_v21 as core
from roster_v21 import ROSTER
ROOT=Path(__file__).resolve().parent
MOD=ROOT/'staging/codex_fxn5c_1'
OUT=ROOT.parents[1]/'outputs'
STEMS=tuple(r['stem'] for r in ROSTER)
MODEL_STEMS=STEMS+('fxn5c_menu_cr','fxn5c_menu_jinwen')
STYLES=('fxn5c','fxn5c_jinwen')
HISTORICAL={
 'FXN5C_TPF2_v0.23.zip':'093c0965e29b1577d5ba7d6d8b8813d35a4841b66e862149dd939b54bd6b88b9',
 'FXN5C_Source_v0.23.zip':'027102d0e224bebb124cc95b99ce0274a625845076c3742fc09adc73cd9a5b6e'}
REPORTS=('validation_fleet_v24.json',)+tuple(f'validation_{s}_v24.json' for s in STEMS)+(
 'catalogue_audit_v24.json','audit_native_patch_v24.json','audit_sources_v24.json',
 'roof_audit_v24.json','light_audit_v24.json','fbx_audit_v24.json',
 'render_audit_v24_cr_all.json','render_audit_v24_jinwen_all.json',
 'ui_icon_audit_v24.json','review_audit_v24.json')
PATCH_MANIFEST='native_patch_manifest_v24.json'
SCENES=tuple(f'native_scene_{s}.json' for s in STEMS)+('native_scene.json','native_scene_jinwen.json','native_meshes.json')
SOURCE_ENTRIES=('build_release_v24.py','prepare_scene_v24.py','roof_revision_v24.py',
 'front_revision_v24.py','light_revision_v24.py','verify_native_v24.py','audit_native_patch_v24.py',
 'audit_sources_v24.py','audit_front_v24.py','audit_roof_v24.py','audit_lights_v24.py','audit_catalogue_v24.py',
 'fbx_native_v24.py','audit_fbx_v24.py','render_native_v24.py','ui_icons_v24.py','make_review_v24.py',
 'package_release_v24.py','release_sanity_v24.py')
DOCS=('README_V24.md','SOURCE_README_V24.md','ATTRIBUTION_V24.md')
GAME_DOCS=('ATTRIBUTION_V24.md',)
REVIEW_IMAGES=('review_v24.png','roof_review_v24.png','light_review_v24.png','light_dusk_v24.png','fleet_review_v24.png')
BASE_GAME_MATERIALS=core.BASE_GAME_MATERIALS
require=core.require;sha=core.sha;under_root=core.under_root

def check_history():
    for name,h in HISTORICAL.items():require(sha(OUT/name)==h,('v23 archive changed',name))

def bind(hashes,name,digest):
    name=name.replace('\\','/')
    require(sha(under_root(name))==digest,('stale bound input',name))
    require(name not in hashes or hashes[name]==digest,('inconsistent evidence',name))
    hashes[name]=digest

def audits():
    reports={};hashes={};pictures=set()
    for name in REPORTS:
        report=json.loads(under_root(name).read_text(encoding='utf-8'))
        require(report.get('status')=='PASS',('incomplete audit',name));reports[name]=report
        for block in core.walk(report):
            for field in ('inputs_sha256','input_sha256','inputs'):
                values=block.get(field,{})
                if isinstance(values,dict):
                    for n,h in values.items():bind(hashes,n,h)
        if name.startswith('render_'):
            require(report['script_sha256']==sha(ROOT/'render_native_v24.py'),'stale renderer')
            for row in report['icons']+report['views']:
                bind(hashes,row['file'],row['sha256']);pictures.add(row['file'])
        if name=='ui_icon_audit_v24.json':
            require(report['script_sha256']==sha(ROOT/'ui_icons_v24.py'),'stale icon encoder')
            for row in report['icons']:
                bind(hashes,row['file'],row['sha256']);bind(hashes,row['canonical'],row['canonical_sha256'])
            for row in report['render_reports']:bind(hashes,row['file'],row['sha256'])
        if name=='review_audit_v24.json':
            for row in report['outputs']:bind(hashes,row['file'],row['sha256'])
    fleet=reports['validation_fleet_v24.json']
    require(len(fleet['models'])==10 and {r['variant'] for r in fleet['models']}==set(STEMS),'fleet cohort')
    for row in fleet['models']:require(row==reports[f"validation_{row['variant']}_v24.json"],'fleet report mismatch')
    require(len(reports['catalogue_audit_v24.json']['vehicles'])==10,'catalogue cohort')
    loc=reports['catalogue_audit_v24.json']['runtime_localization']
    require(loc['localized_model_language_cases']==24 and loc['localized_description_fields']==48 and loc['identity_only_negative_controls']==24,'actual localized menu fields required')
    require(len(reports['audit_native_patch_v24.json']['patches'])==6,'body delta cohort')
    sources=reports['audit_sources_v24.json']
    require(len(sources['sources'])==2 and sources['negative_controls_passed']==6,'saved front source cohort')
    roof=reports['roof_audit_v24.json']
    require(roof['mode']=='actual_saved_sources_and_current_native_LOD0' and roof['candidate_recipe_applied_without_save'] is False,'final roof evidence required')
    require(len(roof['results'])==len(roof['native_checks'])==2 and all(len(r['all_glazing_checked'])==26 for r in roof['native_checks']),'all final roof panes')
    lights=reports['light_audit_v24.json']
    require(len(lights['models'])==10 and len(lights['negative_controls'])==4,'native light evidence cohort')
    require(all(len(r['geometry'])==4 for r in lights['models']),'both directions and detailed LODs')
    fbx=reports['fbx_audit_v24.json']['models']
    require({(r['style'],r['lod']) for r in fbx}=={(s,l) for s in STYLES for l in (0,1,2)},'six current FBXs')
    require(all(r['exact_native_material_counts'] for r in fbx),'FBX readback mismatch')
    require(len(reports['ui_icon_audit_v24.json']['icons'])==48,'48 icons')
    require(len([n for n in pictures if n.startswith('ui_canonical_v24/')])==20,'20 current masters')
    return reports,hashes,pictures

def assert_safe_name(name):
    p=Path(name);low=name.lower()
    require(not p.is_absolute() and '..' not in p.parts and '\\' not in name,('unsafe entry',name))
    require(not any(t in low for t in ('/reference/','codex-clipboard','__pycache__')),('reference/cache entry',name))
    if '/runtime/' in low:
        require('/runtime/patch_inputs_v24/' in low and (name.endswith('.msh') or name.endswith('.msh.blob')),('runtime binary/cache',name))
    require(p.suffix.lower() not in {'.blend1','.pyd','.dll','.exe','.pyc','.ttf','.ttc','.otf','.woff','.woff2','.webp','.jpeg','.mp4','.pdf'},('forbidden asset',name))
    require(p.suffix.lower()!='.jpg' or name.endswith('/workshop_preview.jpg'),('reference photo',name))
    require(not name.endswith('@2.tga') and not p.name.startswith('bogie_frame_lod'),('obsolete asset',name))

def prepare_entries():
    require(core.ROOT==ROOT and core.MOD==MOD,'closure helper root')
    native,models,external=core.native_closure()
    reports,hashes,pictures=audits()
    manifest=json.loads(under_root(PATCH_MANIFEST).read_text(encoding='utf-8'))
    require(manifest['status']=='BUILT_PENDING_AUDIT' and len(manifest['patches'])==6,'build cohort')
    require(len(manifest['panes'])==24 and len(manifest['signage'])==20,'optics/signage cohort')
    require({(r['style'],r['lod'],r['name']) for r in manifest['panes']}==
            {(s,l,f'glazing_{n:02d}') for s in STYLES for l in (0,1) for n in (0,1,2,7,8,9)},'upper pane identities')
    require({(r['model'],r['lod']) for r in manifest['signage']}=={(s,l) for s in STEMS for l in (0,1)},'signage identities')
    for row in manifest['sources']:require(sha(under_root(row['file']))==row['sha256'],'source changed since build')
    proof=set()
    for row in manifest['patches']:
        for phase in ('before','after'):proof.update(row[phase]['file']+s for s in ('','.blob'))
    require(len(proof)==24,'24 source-delta proof files')
    for row in manifest['patches']+manifest['panes']:
        require(sha(under_root(row['target']))==row['mesh_sha256'],'stale mesh')
        require(sha(under_root(row['target']+'.blob'))==row['blob_sha256'],'stale blob')
    for path in native:require(path.relative_to(ROOT).as_posix() in hashes,('unbound native input',str(path)))
    for stem in STEMS:
        require(core.json_to_lua(json.loads(under_root(f'native_scene_{stem}.json').read_text(encoding='utf-8')))==models[stem],('stale native scene',stem))
    for alias,stem in (('native_scene.json','fxn5c'),('native_scene_jinwen.json','fxn5c_jinwen')):
        require(core.json_to_lua(json.loads(under_root(alias).read_text(encoding='utf-8')))==models[stem],('stale native scene alias',alias))
    latest=max(p.stat().st_mtime_ns for p in native)
    require(all(under_root(n).stat().st_mtime_ns>=latest for n in pictures),'preview predates native build')
    for name in REVIEW_IMAGES:require(under_root(name).stat().st_mtime_ns>=latest,('stale review',name))
    for name in ('image_00.tga','workshop_preview.jpg'):require((MOD/name).stat().st_mtime_ns>=latest,('stale cover',name))
    require((MOD/'workshop_preview.jpg').stat().st_size<1024*1024,'cover >1MiB')
    icons=[under_root(i['file']) for i in reports['ui_icon_audit_v24.json']['icons']]
    game=[(p,'codex_fxn5c_1/'+p.relative_to(MOD).as_posix()) for p in list(native)+icons]
    game.extend((MOD/n,'codex_fxn5c_1/'+n) for n in ('mod.lua','strings.lua','image_00.tga','workshop_preview.jpg'))
    game.append((ROOT/'README_V24.md','codex_fxn5c_1/README.md'))
    game.extend((ROOT/n,'codex_fxn5c_1/documents/'+n) for n in GAME_DOCS)
    sources=core.dependencies(SOURCE_ENTRIES)|set(DOCS)|set(REPORTS)|set(SCENES)|pictures|proof|set(REVIEW_IMAGES)|{
        PATCH_MANIFEST,'requirements.txt','model_editor_settings.example.lua','fxn5c_source.blend','fxn5c_jinwen_source.blend',
        'assets/China_Railways.svg','assets/China_Railways_SOURCE.md'}
    sources.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'source_textures').rglob('*') if p.is_file())
    fbx=list((ROOT/'fbx_import').rglob('*.fbx'));require(len(fbx)==6,'six FBXs')
    sources.update(p.relative_to(ROOT).as_posix() for p in fbx)
    prefix='FXN5C_Source_v0.24/'
    source=[(under_root(n),prefix+n) for n in sources]+[(p,prefix+'staging/'+n) for p,n in game]
    included={p.relative_to(ROOT).as_posix() for p,_ in source}
    require(set(hashes)<=included,('audited inputs absent',sorted(set(hashes)-included)))
    for entries in (game,source):
        require(len(entries)==len({n for _,n in entries}),'duplicate entries')
        for path,name in entries:require(path.is_file(),('missing input',str(path)));assert_safe_name(name)
    return game,source,external

def archive(path,entries):
    temporary=path.with_suffix('.zip.tmp');inventory=[]
    with ZipFile(temporary,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for source,target in sorted(entries,key=lambda p:p[1]):
            h=sha(source);z.write(source,target)
            inventory.append(dict(path=target,source=source.relative_to(ROOT).as_posix(),sha256=h))
    with ZipFile(temporary) as z:
        require(z.testzip() is None,('bad CRC',path.name))
        for item in inventory:require(hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256'],('changed during archive',item['path']))
    temporary.replace(path)
    return dict(file=path.name,bytes=path.stat().st_size,sha256=sha(path),entries=inventory)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check-inputs',action='store_true')
    args=parser.parse_args();check_history();game,source,external=prepare_entries()
    if args.check_inputs:print(json.dumps(dict(status='INPUTS_PASS',game_files=len(game),source_files=len(source))));return
    OUT.mkdir(parents=True,exist_ok=True)
    archives=[archive(OUT/'FXN5C_TPF2_v0.24.zip',game),archive(OUT/'FXN5C_Source_v0.24.zip',source)]
    for record in archives:
        for row in record['entries']:require(sha(under_root(row['source']))==row['sha256'],'input changed after archive')
    check_history()
    for name in REVIEW_IMAGES:shutil.copy2(ROOT/name,OUT/('FXN5C_v0.24_'+name.replace('_v24','')))
    shutil.copy2(ROOT/'README_V24.md',OUT/'FXN5C_v0.24_安装与说明.md')
    manifest=dict(status='PACKAGED_PENDING_INDEPENDENT_SANITY',archives=archives,reports=list(REPORTS),
        historical_v23_sha256=HISTORICAL,external_base_game_materials=sorted(external),
        evidence_scope='Current native body/panes/light cases, saved geometry, fleet, renders and icon bytes; no engine playtest',
        game_verified=False,game_installation_modified=False,steam_uploaded=False)
    (OUT/'FXN5C_v0.24_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k!='entries'} for r in archives],indent=2))

if __name__=='__main__':main()
