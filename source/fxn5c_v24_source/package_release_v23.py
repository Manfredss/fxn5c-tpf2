"""Hash-gated current v23 archives. Does not deploy to a game installation."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import argparse
import hashlib
import json
import shutil
import package_release_v21 as core
from roster_v21 import ROSTER

ROOT=Path(__file__).resolve().parent
MOD=ROOT/'staging/codex_fxn5c_1'
OUT=ROOT.parents[1]/'outputs'
STEMS=tuple(r['stem'] for r in ROSTER)
MODEL_STEMS=STEMS+('fxn5c_menu_cr','fxn5c_menu_jinwen')
STYLES=('fxn5c','fxn5c_jinwen')
HISTORICAL={
 'FXN5C_TPF2_v0.22.zip':'d8f9598d5e34af64ee29954f30e6d926e976fd73c5036fa04e94f522e0021b85',
 'FXN5C_Source_v0.22.zip':'952c2851bc0ffb3e063041d190c835f2548cff1c55364712e8e447d8a0f647e4',
}
REPORTS=('validation_fleet_v23.json',)+tuple(f'validation_{s}_v23.json' for s in STEMS)+(
 'catalogue_audit_v23.json','audit_native_patch_v23.json','audit_sources_v23.json','fbx_audit_v23.json',
 'render_audit_v23_cr_all.json','render_audit_v23_jinwen_all.json','ui_icon_audit_v23.json','clearance_audit_v23.json')
PATCH_MANIFEST='native_patch_manifest_v23.json'
SCENES=tuple(f'native_scene_{s}.json' for s in STEMS)+('native_scene.json','native_scene_jinwen.json','native_meshes.json')
SOURCE_ENTRIES=('build_release_v23.py','prepare_scene_v23.py','native_patch_v23.py',
 'running_gear_revision_v23.py','body_revision_v23.py','livery_revision_v23.py','jwr_vector_v23.py',
 'verify_native_v23.py','audit_native_patch_v23.py','audit_sources_v23.py','audit_catalogue_v23.py',
 'fbx_native_v23.py','audit_fbx_v23.py','render_native_v23.py','ui_icons_v23.py','make_review_v23.py',
 'package_release_v23.py','release_sanity_v23.py','audit_clearance_v23.py')
DOCS=('README_V23.md','SOURCE_README_V23.md','ATTRIBUTION_V23.md')
GAME_DOCS=('ATTRIBUTION_V23.md',)
BASE_GAME_MATERIALS=core.BASE_GAME_MATERIALS
require=core.require
sha=core.sha
under_root=core.under_root

def check_history():
    for n,h in HISTORICAL.items():require(sha(OUT/n)==h,('historical v22 archive changed',n))

def bind(hashes,name,digest):
    name=name.replace('\\','/')
    require(sha(under_root(name))==digest,('stale bound input',name))
    require(name not in hashes or hashes[name]==digest,('inconsistent input evidence',name))
    hashes[name]=digest

def audits():
    reports={};hashes={};pictures=set()
    for name in REPORTS:
        report=json.loads(under_root(name).read_text(encoding='utf-8'))
        require(report.get('status')=='PASS',('incomplete audit',name))
        reports[name]=report
        for block in core.walk(report):
            for field in ('inputs_sha256','input_sha256'):
                for n,h in block.get(field,{}).items():bind(hashes,n,h)
        if name.startswith('render_'):
            require(report['script_sha256']==sha(ROOT/'render_native_v23.py'),'stale renderer')
            for n,h in report['inputs'].items():bind(hashes,n,h)
            for item in report['icons']+report['views']:
                bind(hashes,item['file'],item['sha256']);pictures.add(item['file'])
        if name=='ui_icon_audit_v23.json':
            require(report['script_sha256']==sha(ROOT/'ui_icons_v23.py'),'stale encoder')
            for item in report['icons']:
                bind(hashes,item['file'],item['sha256'])
                bind(hashes,item['canonical'],item['canonical_sha256'])
            for item in report['render_reports']:require(sha(under_root(item['file']))==item['sha256'],'stale render report binding')
    fleet=reports['validation_fleet_v23.json']
    require(len(fleet['models'])==10 and {r['variant'] for r in fleet['models']}==set(STEMS),'fleet cohort')
    for row in fleet['models']:require(row==reports[f"validation_{row['variant']}_v23.json"],'fleet report mismatch')
    require(len(reports['catalogue_audit_v23.json']['vehicles'])==10,'catalogue cohort')
    require(len(reports['audit_native_patch_v23.json']['patches'])==18,'patch cohort')
    sources=reports['audit_sources_v23.json']
    require(len(sources['sources'])==2 and sources['native_bearing_rings_measured']==80 and sources['negative_controls_passed']==18,'geometry audit cohort')
    fbx=reports['fbx_audit_v23.json']['models']
    require({(r['style'],r['lod']) for r in fbx}=={(s,l) for s in STYLES for l in (0,1,2)},'six current FBXs required')
    require(all(r['exact_native_material_counts'] for r in fbx),'FBX native mismatch')
    require(len(reports['ui_icon_audit_v23.json']['icons'])==48,'48 TGA icons required')
    clearance=reports['clearance_audit_v23.json']
    require(len(clearance['styles'])==2 and all(not r['new_contact_role_pairs'] for r in clearance['styles']),'new selected gear/body contacts')
    for row in clearance['styles']:
        require({(p['bogie'],p['degrees']) for p in row['current']['poses']}=={(b,d) for b in (1,2) for d in (-10,-5,0,5,10)},'bounded angle cohort')
    require(len([n for n in pictures if n.startswith('ui_canonical_v23/')])==20,'20 current masters required')
    return reports,hashes,pictures

def assert_safe_name(name):
    p=Path(name);low=name.lower()
    require(not p.is_absolute() and '..' not in p.parts and '\\' not in name,('unsafe entry',name))
    require(not any(t in low for t in ('/reference/','codex-clipboard','__pycache__')),('reference/cache entry',name))
    if '/runtime/' in low:
        require('/runtime/patch_inputs/' in low and (name.endswith('.msh') or name.endswith('.msh.blob')),('runtime binary or cache',name))
    require(p.suffix.lower() not in {'.blend1','.pyd','.dll','.ttf','.ttc','.otf','.webp','.jpeg','.mp4','.pdf'},('forbidden asset',name))
    require(p.suffix.lower()!='.jpg' or name.endswith('/workshop_preview.jpg'),('reference photo',name))
    require(not name.endswith('@2.tga') and not p.name.startswith('bogie_frame_lod'),('obsolete asset',name))

def prepare_entries():
    require(core.ROOT==ROOT and core.MOD==MOD,'closure helper root')
    native,models,external=core.native_closure()
    reports,hashes,pictures=audits()
    manifest=json.loads(under_root(PATCH_MANIFEST).read_text(encoding='utf-8'))
    require(manifest['status']=='BUILT_PENDING_AUDIT' and len(manifest['patches'])==18,'build cohort')
    for row in manifest['sources']:require(sha(under_root(row['file']))==row['sha256'],'source changed since build')
    proof=set()
    for row in manifest['patches']:
        for field in ('before','after'):
            proof.update(row[field]['file']+suffix for suffix in ('','.blob'))
        require(sha(under_root(row['target']))==row['mesh_sha256'],'stale mesh')
        require(sha(under_root(row['target']+'.blob'))==row['blob_sha256'],'stale blob')
    require(len(proof)==72,'72 source-delta proof files')
    for path in native:require(path.relative_to(ROOT).as_posix() in hashes,('unbound native input',str(path)))
    for stem in STEMS:
        require(core.json_to_lua(json.loads(under_root(f'native_scene_{stem}.json').read_text(encoding='utf-8')))==models[stem],('stale native scene',stem))
    latest=max(under_root(r['target']+'.blob').stat().st_mtime_ns for r in manifest['patches'])
    require(all(under_root(n).stat().st_mtime_ns>=latest for n in pictures),'preview predates build')
    require(under_root('review_v23.png').stat().st_mtime_ns>=max(under_root(n).stat().st_mtime_ns for n in pictures if n.startswith('preview_')),'stale review')
    for name in ('image_00.tga','workshop_preview.jpg'):
        require((MOD/name).stat().st_mtime_ns>=latest,('stale cover',name))
    require((MOD/'workshop_preview.jpg').stat().st_size<1024*1024,'cover >1MiB')
    icons=[under_root(i['file']) for i in reports['ui_icon_audit_v23.json']['icons']]
    game=[(p,'codex_fxn5c_1/'+p.relative_to(MOD).as_posix()) for p in list(native)+icons]
    game.extend((MOD/n,'codex_fxn5c_1/'+n) for n in ('mod.lua','strings.lua','image_00.tga','workshop_preview.jpg'))
    game.append((ROOT/'README_V23.md','codex_fxn5c_1/README.md'))
    game.extend((ROOT/n,'codex_fxn5c_1/documents/'+n) for n in GAME_DOCS)
    sources=core.dependencies(SOURCE_ENTRIES)|set(DOCS)|set(REPORTS)|set(SCENES)|pictures|proof|{
        PATCH_MANIFEST,'review_v23.png','requirements.txt','model_editor_settings.example.lua',
        'fxn5c_source.blend','fxn5c_jinwen_source.blend','assets/China_Railways.svg','assets/China_Railways_SOURCE.md'}
    sources.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'source_textures').rglob('*') if p.is_file())
    fbx=list((ROOT/'fbx_import').rglob('*.fbx'));require(len(fbx)==6,'six FBXs')
    sources.update(p.relative_to(ROOT).as_posix() for p in fbx)
    prefix='FXN5C_Source_v0.23/'
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
    args=parser.parse_args();check_history()
    game,source,external=prepare_entries()
    if args.check_inputs:print(json.dumps(dict(status='INPUTS_PASS',game_files=len(game),source_files=len(source))));return
    OUT.mkdir(parents=True,exist_ok=True)
    archives=[archive(OUT/'FXN5C_TPF2_v0.23.zip',game),archive(OUT/'FXN5C_Source_v0.23.zip',source)]
    for record in archives:
        for item in record['entries']:require(sha(under_root(item['source']))==item['sha256'],'input changed after archive')
    check_history()
    shutil.copy2(ROOT/'review_v23.png',OUT/'FXN5C_v0.23_review.png')
    shutil.copy2(ROOT/'README_V23.md',OUT/'FXN5C_v0.23_安装与说明.md')
    manifest=dict(status='PACKAGED_PENDING_INDEPENDENT_SANITY',archives=archives,reports=list(REPORTS),
        historical_v22_sha256=HISTORICAL,external_base_game_materials=sorted(external),
        evidence_scope='Selected geometry, native delta, fleet, current render and icon bytes; not in-game playtest',
        game_verified=False,game_installation_modified=False,steam_uploaded=False)
    (OUT/'FXN5C_v0.23_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in r.items() if k!='entries'} for r in archives],indent=2))

if __name__=='__main__':main()
