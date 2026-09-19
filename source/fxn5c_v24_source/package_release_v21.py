"""Package only the v21 native reference closure and fresh audit/source artefacts.

Never cleans staging, changes a game installation, or ships reference media.
Run after build, all audits, rendering, icons and make_review_v21.py.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import ast
import hashlib
import json
import shutil
import sys

ROOT=Path(__file__).resolve().parent
MOD=ROOT/'staging/codex_fxn5c_1'
OUT=ROOT.parents[1]/'outputs'
for runtime in (ROOT/'runtime',ROOT.parent/'fxn5c_v20_source/runtime'):
    if (runtime/'lupa').exists():sys.path.insert(0,str(runtime));break
from audit_catalogue_v21 import read_lua
from roster_v21 import ROSTER
from catalogue_v21 import GROUPS

STEMS=tuple(r['stem'] for r in ROSTER)
MODEL_STEMS=STEMS+tuple(GROUPS)
BASES=('fxn5c','fxn5c_jinwen')
HISTORICAL={
    'FXN5C_TPF2_v0.20.zip':'3e125c166d0e3555e79b5d2b297476ba17be63af7e1e6b60a23a9b966a96a884',
    'FXN5C_Source_v0.20.zip':'053a81e4ef1dd85aca03ccd24071159e5d8f4f298a88b6cc20004a1ad50385bb',
}
RETAINED_PREFIXES=('cab_aperture_audit','roof_geometry_audit','front_geometry_audit',
                   'emblem_geometry_audit','detail_geometry_audit','source_inspection')
REPORTS=('validation_fleet_v21.json',)+tuple(f'validation_{s}_v21.json' for s in STEMS)+(
    'catalogue_audit_v21.json','livery_build_audit_v21.json','livery_source_audit_v21.json','bogie_equipment_audit_v21.json',
    'roof_equipment_audit_v21.json','dynamic_skin_audit_v21.json',
    'retained_resources_audit_v21.json','ui_icon_audit_v21.json')+tuple(
    f'{p}_{v}.json' for v in ('v21','jinwen_v21') for p in RETAINED_PREFIXES)
CONNECTION_MANIFESTS=tuple(f'connection_manifest_v21_{s}.json' for s in STEMS)
SCENES=tuple(f'native_scene_{s}.json' for s in STEMS)+('native_scene.json','native_scene_jinwen.json','native_meshes.json')
REQUIRED_VIEWS=('fxn5c_playable_preview.png',)+tuple(f'fxn5c_{tag}_v21.png' for tag in (
    'cab','glass','bogie','roof','side','underframe','bogie_side','body_connection','bogie_low',
    'front','side_opposite','roof_fans','roof_opposite','reservoirs','cab_full_side','cab_interior',
    'lights_forward','lights_reverse','link_yaw_p00','link_yaw_p05','link_yaw_p15'))
SOURCE_ENTRIES=('build_release_v21.py','verify_native_v21.py','audit_catalogue_v21.py',
    'dynamic_audit_v21.py','dynamic_feasibility_v21.py','audit_bogie_equipment_v21.py',
    'audit_roof_equipment_v21.py','audit_retained_v21.py','audit_retained_resources_v21.py',
    'render_native_v21.py','ui_icons_v21.py','make_review_v21.py','package_release_v21.py',
    'release_sanity_v21.py','generate_textures_v04.py','test_livery_revision_v21.py',
    'repair_livery_source_v21.py')
DOCS=('README_V21.md','SOURCE_README_V21.md','ATTRIBUTION_V21.md','dynamic_research_v21.md')
BASE_GAME_MATERIALS={'vehicle/train/emissive/train_all_lights.mtl','vehicle/train/emissive/train_red_lights.mtl'}


def require(ok,detail):
    if not ok:raise AssertionError(detail)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def under_root(relative):
    p=(ROOT/relative).resolve()
    require(p.is_relative_to(ROOT.resolve()),('input escapes source root',relative))
    require(p.is_file(),('missing input',relative))
    return p


def safe_ref(base,relative):
    require(isinstance(relative,str) and '\\' not in relative,('invalid resource path',relative))
    p=(base/relative).resolve()
    require(p.is_relative_to(base.resolve()),('resource escapes folder',relative))
    return p


def walk(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from walk(child)
    elif isinstance(value,list):
        for child in value:yield from walk(child)


def native_closure():
    """Actual MDL references only; no stale frame/QA-rest mesh globbing."""
    res=MOD/'res';files=set();external=set();models={};mesh_refs=set();material_refs=set()
    for stem in MODEL_STEMS:
        p=res/f'models/model/vehicle/train/{stem}.mdl'
        require(p.is_file(),('missing model',stem));files.add(p)
        model=read_lua(p);models[stem]=model
        for node in walk(model):
            for key in ('mesh','skin'):
                if key in node:mesh_refs.add(node[key])
            for key in ('materials','skinMaterials'):
                material_refs.update(node.get(key,{}).values())
    for ref in mesh_refs:
        p=safe_ref(res/'models/mesh',ref)
        require(p.is_file() and Path(str(p)+'.blob').is_file(),('missing mesh/blob',ref))
        files.update((p,Path(str(p)+'.blob')))
    for ref in material_refs:
        p=safe_ref(res/'models/material',ref)
        if not p.is_file():
            require(ref in BASE_GAME_MATERIALS,('missing material',ref));external.add(ref);continue
        files.add(p)
        for record in walk(read_lua(p)):
            if 'fileName' not in record:continue
            texture=safe_ref(res/'textures',record['fileName'])
            require(texture.is_file(),('missing texture',record['fileName']));files.add(texture)
    return files,models,external


def dependencies(entrypoints=SOURCE_ENTRIES):
    pending=list(entrypoints);result=set()
    while pending:
        name=pending.pop()
        if name in result:continue
        path=under_root(name);result.add(name)
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            modules=[a.name for a in node.names] if isinstance(node,ast.Import) else \
                    [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for module in modules:
                local=module.split('.')[0]+'.py'
                if (ROOT/local).is_file():pending.append(local)
    return result


def check_history():
    for name,digest in HISTORICAL.items():
        require(sha(OUT/name)==digest,('historical v20 archive changed',name))


def report_hashes(report):
    result={}
    for block in walk(report):
        for key in ('inputs_sha256','input_sha256'):
            for relative,digest in block.get(key,{}).items():
                require(relative not in result or result[relative]==digest,('inconsistent input hash',relative))
                result[relative]=digest
    return result


def validate_livery_source_evidence(report):
    """Require final saved sources and both current LOD0 body pairs, not old scenes."""
    require(report.get('status')=='PASS','final livery source report failed')
    require(report.get('producer')=='repair_livery_source_v21.py','unexpected final livery evidence producer')
    repair=report.get('repair',{})
    require(repair.get('position_material_uv_oriented_triangle_multiset_equal') is True,
            'livery repair did not preserve valid oriented position/material/UV surfaces')
    require(repair.get('strict_non_degenerate_triangles_unchanged',0)>0,
            'livery repair did not compare any valid triangles')
    require(repair.get('historical_build_report_not_rewritten') is True,
            'livery repair rewrote historical construction evidence')
    expected={'fxn5c':('0051','fxn5c_source.blend'),
              'fxn5c_jinwen':('7006','fxn5c_jinwen_source.blend')}
    variants=report.get('variants',[])
    require(len(variants)==2 and {r.get('model') for r in variants}==set(expected),
            'final livery source report must contain both distinct base sources')
    hashes=report.get('inputs_sha256',{})
    required={'livery_revision_v21.py','audit_livery_revision_v21.py','repair_livery_source_v21.py'}
    for row in variants:
        number,source=expected[row['model']]
        require(row.get('number')==number and row.get('source')==source,
                ('wrong current livery source identity',row['model']))
        require(row.get('audit_scene',{}).get('status')=='PASS',
                ('current source scene livery check failed',row['model']))
        required.add(source)
        prefix=f'staging/codex_fxn5c_1/res/models/mesh/vehicle/train/{row["model"]}/body_lod0.msh'
        required.update((prefix,prefix+'.blob'))
    require(required<=set(hashes),('final source evidence missing required hashes',sorted(required-set(hashes))))
    for relative,digest in hashes.items():
        require(sha(under_root(relative))==digest,('final source/body changed after livery audit',relative))
    for key in ('protected_files_sha256','changed_files_after_sha256'):
        require(repair.get(key),('repair evidence lacks current-file hashes',key))
        for relative,digest in repair[key].items():
            require(sha(under_root(relative))==digest,('repair current-file evidence changed',key,relative))
    require(repair.get('protected_files_unchanged')==len(repair['protected_files_sha256']),
            'repair protected-file count mismatch')
    return required


def audit_inputs(native_files,models):
    latest=max(p.stat().st_mtime_ns for p in native_files)
    writer={name:'verify_native_v21.py' for name in REPORTS if name.startswith('validation_')}
    writer.update({
        'catalogue_audit_v21.json':'audit_catalogue_v21.py','livery_build_audit_v21.json':'build_release_v21.py',
        'livery_source_audit_v21.json':'repair_livery_source_v21.py',
        'bogie_equipment_audit_v21.json':'audit_bogie_equipment_v21.py',
        'roof_equipment_audit_v21.json':'audit_roof_equipment_v21.py',
        'dynamic_skin_audit_v21.json':'dynamic_audit_v21.py',
        'retained_resources_audit_v21.json':'audit_retained_resources_v21.py',
        'ui_icon_audit_v21.json':'ui_icons_v21.py'})
    checked={};reports={}
    for name in REPORTS:
        path=under_root(name);report=json.loads(path.read_text(encoding='utf-8'))
        require(report.get('status')=='PASS',('audit failed',name))
        if name=='livery_build_audit_v21.json':
            # This is the 30-scene evidence captured DURING the build, before
            # post-build topology cleanup. Its 30 model/LOD PASS rows are checked
            # below, but its timestamp does NOT certify the final saved sources.
            # The separate livery_source audit binds both final .blend/body pairs
            # with hashes. Never touch this old evidence to make it look current.
            pass
        else:
            require(path.stat().st_mtime_ns>=latest,('audit predates native build',name))
            producer=writer.get(name,'audit_retained_v21.py')
            writer_latest=max(under_root(n).stat().st_mtime_ns for n in dependencies((producer,)))
            require(path.stat().st_mtime_ns>=writer_latest,('auditor/dependency changed after report',name))
        for relative,digest in report_hashes(report).items():
            current=under_root(relative)
            if relative not in checked:checked[relative]=sha(current)
            actual=checked[relative]
            require(actual==digest,('audited input changed',name,relative))
        reports[name]=report
    fleet=reports['validation_fleet_v21.json']
    require({r['variant'] for r in fleet['models']}==set(STEMS),'incomplete fleet audit')
    for row in fleet['models']:
        require(row==reports[f'validation_{row["variant"]}_v21.json'],('fleet/model report mismatch',row['variant']))
    livery=reports['livery_build_audit_v21.json']['scenes']
    require(len(livery)==30 and {(r['model'],r['lod']) for r in livery}=={(s,l) for s in STEMS for l in (0,1,2)},'incomplete livery scenes')
    require(all(r['status']=='PASS' for r in livery),'failed livery scene')
    validate_livery_source_evidence(reports['livery_source_audit_v21.json'])
    for name in ('bogie_equipment_audit_v21.json','roof_equipment_audit_v21.json'):
        variants=reports[name]['variants']
        require({r['model'] for r in variants}==set(BASES),('incomplete variants',name))
        for row in variants:
            require(row['status']=='PASS',(name,row['model']))
            tests=row['mutation_tests']
            require(tests['status']=='PASS' and tests['caught']==len(tests['cases'])>0 and all(c['caught'] for c in tests['cases']),('mutation gate',name))
    dynamic=reports['dynamic_skin_audit_v21.json']
    require({r['model'] for r in dynamic['variants']}==set(BASES),'incomplete dynamic audit')
    require(all(r['game_verified'] is False and r['rigid_mechanism_solved'] is False for r in dynamic['variants']),'overclaimed dynamic result')
    for stem in STEMS:
        manifest=json.loads(under_root(f'connection_manifest_v21_{stem}.json').read_text(encoding='utf-8'))
        require(manifest['model_stem']==stem,('wrong connection manifest',stem))
        scene=under_root(f'native_scene_{stem}.json')
        # Lua arrays are one-indexed in this reader; JSON arrays need normalization.
        require(json_to_lua(json.loads(scene.read_text(encoding='utf-8')))==models[stem],('stale native scene',stem))
    for name,stem in (('native_scene.json','fxn5c'),('native_scene_jinwen.json','fxn5c_jinwen')):
        require(json_to_lua(json.loads(under_root(name).read_text(encoding='utf-8')))==models[stem],('stale native scene alias',name))
    require(under_root('native_meshes.json').stat().st_mtime_ns>=latest,'stale mesh descriptors')
    icons=reports['ui_icon_audit_v21.json']['icons'];required_icons=set(icon_paths())
    require({item['file'] for item in icons}==required_icons and len(icons)==48,'incomplete exact UI icon inventory')
    for item in icons:
        p=under_root(item['file']);canonical=under_root(item['canonical'])
        require(sha(p)==item['sha256'] and sha(canonical)==item['canonical_sha256'],('icon/canonical changed',item['file']))
        raw=p.read_bytes();require(raw[2]==2 and raw[16]==32 and raw[17]==0,('wrong TGA type/origin',item['file']))
        require((ROOT/'ui_icon_audit_v21.json').stat().st_mtime_ns>=p.stat().st_mtime_ns,'stale icon audit')
        require(canonical.stat().st_mtime_ns>=latest,('stale canonical render',item['canonical']))
    return latest,reports


def json_to_lua(value):
    if isinstance(value,list):return {i+1:json_to_lua(v) for i,v in enumerate(value)}
    if isinstance(value,dict):return {k:json_to_lua(v) for k,v in value.items()}
    return value


def icon_paths():
    return [f'staging/codex_fxn5c_1/res/textures/ui/{kind}/vehicle/train/{stem}{suffix}.tga'
            for stem in MODEL_STEMS for kind in ('models_small','models_20') for suffix in ('','@2x')]


def view_paths():
    return [f'{folder}/{name}' for folder in ('native_preview','native_preview_jinwen') for name in REQUIRED_VIEWS]+[
        f'fleet_preview/{r["number"]}.png' for r in ROSTER]+[
        f'ui_canonical/{s}/{kind}.png' for s in STEMS for kind in ('models_small','models_20')]


def assert_safe_name(name):
    p=Path(name);lower=name.lower()
    require(not p.is_absolute() and '..' not in p.parts,('unsafe archive target',name))
    require(not any(token in lower for token in ('/reference/','/runtime/','codex-clipboard','__pycache__')),('unwanted research/runtime file',name))
    require(p.suffix.lower() not in {'.blend1','.ttf','.ttc','.otf','.pyd','.dll','.webp','.jpeg','.mp4','.pdf'},('forbidden asset',name))
    require(p.suffix.lower()!='.jpg' or name.endswith('/workshop_preview.jpg'),('photograph not allowed',name))
    require(not name.endswith('@2.tga'),('obsolete UI suffix',name))
    require(not p.name.startswith('bogie_frame_lod'),('obsolete shared frame',name))


def prepare_entries():
    native,models,external=native_closure()
    latest,reports=audit_inputs(native,models)
    views=view_paths()+['review_v21.png','fleet_review_v21.png']
    for name in views:
        p=under_root(name);require(p.stat().st_mtime_ns>=latest,('stale render',name))
    require((ROOT/'review_v21.png').stat().st_mtime_ns>=max(under_root(n).stat().st_mtime_ns for n in view_paths() if n.startswith('native_preview')),'review predates previews')
    require((ROOT/'fleet_review_v21.png').stat().st_mtime_ns>=max(under_root(n).stat().st_mtime_ns for n in view_paths() if n.startswith('fleet_preview/')),'fleet review predates cab views')
    media=[MOD/'image_00.tga',MOD/'workshop_preview.jpg']
    for p in media:require(p.is_file() and p.stat().st_mtime_ns>=latest,('stale/missing cover',p))
    require(media[1].stat().st_size<1024*1024,'Steam cover exceeds 1MiB')
    mod_entries=[(p,'codex_fxn5c_1/'+p.relative_to(MOD).as_posix()) for p in native]
    mod_entries += [(under_root(n),'codex_fxn5c_1/'+Path(n).relative_to('staging/codex_fxn5c_1').as_posix()) for n in icon_paths()]
    mod_entries += [(MOD/n,'codex_fxn5c_1/'+n) for n in ('mod.lua','strings.lua','image_00.tga','workshop_preview.jpg')]
    mod_entries += [(ROOT/'README_V21.md','codex_fxn5c_1/README.md'),(ROOT/'ATTRIBUTION_V21.md','codex_fxn5c_1/documents/ATTRIBUTION_V21.md'),
                    (ROOT/'dynamic_research_v21.md','codex_fxn5c_1/documents/dynamic_research_v21.md')]
    mod_entries += [(ROOT/n,'codex_fxn5c_1/documents/'+n) for n in REPORTS]
    source_files=dependencies()|set(DOCS)|set(REPORTS)|set(CONNECTION_MANIFESTS)|set(SCENES)|set(views)|{
        'requirements.txt','model_editor_settings.example.lua','assets/China_Railways.svg','assets/China_Railways_SOURCE.md',
        'fxn5c_source.blend','fxn5c_jinwen_source.blend'}
    fbx=sorted((ROOT/'fbx_import').rglob('*.fbx'));require(len(fbx)==6,'six current FBX required')
    for p in fbx:
        style='fxn5c_jinwen' if p.parent.name.endswith('-jinwen') else 'fxn5c'
        lod=int(p.stem[-1]);require(lod in (0,1,2),('unexpected FBX',p))
        body=MOD/f'res/models/mesh/vehicle/train/{style}/body_lod{lod}.msh.blob'
        require(p.stat().st_mtime_ns>=body.stat().st_mtime_ns,('FBX predates current body export',p))
        source_files.add(p.relative_to(ROOT).as_posix())
    for style in BASES:
        body=MOD/f'res/models/mesh/vehicle/train/{style}/body_lod0.msh.blob'
        require((ROOT/(style+'_source.blend')).stat().st_mtime_ns>=body.stat().st_mtime_ns,('stale editable source',style))
    prefix='FXN5C_Source_v0.21/'
    source_entries=[(under_root(n),prefix+n) for n in source_files]+[(p,prefix+'staging/'+n) for p,n in mod_entries]
    for entries in (mod_entries,source_entries):
        names=[n for _,n in entries];require(len(names)==len(set(names)),'duplicate archive names')
        for p,n in entries:require(p.is_file(),('missing packaged source',p));assert_safe_name(n)
    return mod_entries,source_entries,external


def archive(path,entries):
    temp=path.with_suffix('.zip.tmp')
    inventory=[]
    with ZipFile(temp,'w',ZIP_DEFLATED,compresslevel=9) as z:
        for source,target in sorted(entries,key=lambda x:x[1]):
            digest=sha(source);z.write(source,target)
            inventory.append({'path':target,'source':source.relative_to(ROOT).as_posix(),'sha256':digest})
    with ZipFile(temp) as z:
        require(z.testzip() is None,('ZIP CRC failure',path))
        for item in inventory:
            require(hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256'],('source changed during archive',item['path']))
    temp.replace(path)
    return {'file':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'entries':inventory}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    check_history()
    game,source,external=prepare_entries()
    archives=[archive(out/'FXN5C_TPF2_v0.21.zip',game),archive(out/'FXN5C_Source_v0.21.zip',source)]
    # Detect any concurrent rebuild affecting a source after it was compressed.
    for item in archives:
        for entry in item['entries']:require(sha(under_root(entry['source']))==entry['sha256'],('post-pack source changed',entry['source']))
    check_history()
    for name in ('review_v21.png','fleet_review_v21.png'):
        shutil.copy2(ROOT/name,out/('FXN5C_v0.21_'+name))
    shutil.copy2(ROOT/'README_V21.md',out/'FXN5C_v0.21_安装与说明.md')
    manifest={'status':'PACKAGED_PENDING_INDEPENDENT_SANITY','historical_v20_sha256':HISTORICAL,
        'reports':list(REPORTS),'external_base_game_materials':sorted(external),'archives':archives,
        'livery_build_evidence_scope':'30 source-scene checks captured during build, before possible topology cleanup; only their complete model/LOD coverage and PASS statuses are used. Current base-source livery checks and current source/body hashes are in livery_source_audit_v21; final fleet bytes and markings are gated by validation_fleet_v21 and ten vehicle reports.',
        'game_installation_modified':False,'steam_uploaded':False,'game_verified':False}
    (out/'FXN5C_v0.21_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:v for k,v in item.items() if k!='entries'} for item in archives],indent=2))


if __name__=='__main__':main()
