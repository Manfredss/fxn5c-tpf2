"""Package audited v44 prototype candidates; never install or publish."""
from pathlib import Path,PurePosixPath
import sys,json
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v43_source'
MOD=ROOT/'staging/codex_fxn5c_1';OUT=ROOT.parents[1]/'outputs'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from package_v40 import prepare,archive,dependencies,safe_file,sha,walk
from verify_native import read_lua
from verify_v41 import EXTERNAL


def load(path):return json.loads(Path(path).read_text(encoding='utf8'))


def prepare_source(entries,ui):
    # Extend the inherited asset policy ONLY for the 26 hash-audited icon
    # masters. Reference photos, arbitrary images and runtime payloads remain
    # subject to the unmodified historical prepare() policy.
    expected={ROOT.name+'/'+r['canonical']:safe_file(ROOT,r['canonical'])for r in ui['icons']}
    assert len(expected)==26
    general=[];masters=[]
    for path,name in entries:
        name=PurePosixPath(name).as_posix()
        if name not in expected:
            general.append((path,name));continue
        path=Path(path)
        assert path.is_file() and not path.is_symlink() and path.resolve()==expected[name].resolve()
        assert path.suffix.lower()=='.png' and name.startswith(ROOT.name+'/ui_canonical_v44/')
        assert not PurePosixPath(name).is_absolute() and '..'not in PurePosixPath(name).parts
        masters.append(dict(path=path,name=name,sha256=sha(path)))
    assert {r['name']for r in masters}==set(expected) and len(masters)==26
    result=sorted(prepare(general)+masters,key=lambda r:r['name'])
    assert len({r['name'].casefold()for r in result})==len(result),'Duplicate archive path'
    return result


def main():
    names=['FXN5C_TPF2_v0.44_candidate.zip','FXN5C_Source_v0.44_prototype_candidate.zip','FXN5C_v0.44_package_audit.json']
    assert all(not(OUT/n).exists()for n in names),'Refuse to overwrite existing candidate outputs'
    m=load(ROOT/'manifest_v44.json');native=load(ROOT/'validation_v44.json');source=load(ROOT/'source_validation_v44.json')
    assert m['status']=='NATIVE_STATIC_PASS' and native['status']==source['status']=='PASS'
    assert native['ui_verified'] and len(m['ui_artifacts'])==52
    assert native['models']==13 and native['variants']==11 and source['source_count']==3
    assert native['production_models_byte_exact'] and native['production_resources_byte_exact_except_ui']
    assert m['validation_sha256']==sha(ROOT/'validation_v44.json')
    assert m['baseline_manifest_sha256']==sha(BASE/'manifest_v43.json')
    assert not any(m[k]for k in ('game_verified','model_editor_verified','installed','published'))
    assert native['validator_sha256']==sha(ROOT/'verify_v44.py')
    assert source['verifier_sha256']==sha(ROOT/'audit_source_v44.py')
    for table in (m['recipe_sha256'],native['inputs_sha256'],native['render_inputs_sha256'],native['helper_sha256'],source['helper_sha256']):
        for name,digest in table.items():assert sha(safe_file(ROOT,name))==digest,('stale input',name)
    ui=load(ROOT/'ui_icon_audit_v44.json')
    assert ui['status']=='PASS' and ui['script_sha256']==sha(ROOT/'ui_icons_v44.py')
    assert m['ui_icon_audit_sha256']==sha(ROOT/'ui_icon_audit_v44.json')
    assert len(ui['icons'])==52 and len(ui['render_reports'])==13
    assert [{k:r[k]for k in('file','sha256','width','height')}for r in ui['icons']]==m['ui_artifacts']
    assert ui['ui_inventory_changes']==m['ui_inventory_changes']
    for row in ui['icons']:
        assert row['encoding_audit']['decoded_rgba_pixel_exact'] and row['encoding_audit']['first_raw_scanline_matches_bottom']
        assert row['camera_audit']['parallel_to_track'] and row['camera_audit']['positive_x_at_screen_right']
        assert sha(safe_file(ROOT,row['canonical']))==row['canonical_sha256']
    for row in ui['render_reports']:
        path=safe_file(ROOT,row['file']);assert sha(path)==row['sha256']
        rendering=load(path)
        assert rendering['status']=='PASS' and rendering['script_sha256']==sha(ROOT/'render_v44.py')
        assert len(rendering['icons'])==2 and rendering['stem']==row['stem'] and rendering['lod']==0
        for name,digest in rendering['inputs'].items():assert sha(safe_file(ROOT,name))==digest,('stale icon native/render input',name)
        for icon in rendering['icons']:
            assert sha(safe_file(ROOT,icon['file']))==icon['sha256']
            assert icon['stage']['original_generated_stage'] and not icon['stage']['third_party_assets']
    old_files={p.relative_to(BASE).as_posix()for p in (BASE/'staging').rglob('*')if p.is_file()}
    current_files={p.relative_to(ROOT).as_posix()for p in (ROOT/'staging').rglob('*')if p.is_file()}
    added,removed=(set(m['ui_inventory_changes'][k])for k in ('added','removed'))
    assert native['ui_inventory_changes']=={k:sorted(m['ui_inventory_changes'][k])for k in ('added','removed')}
    assert (old_files-removed)|added==current_files,('staging inventory changed after verification',((old_files-removed)|added)^current_files)
    mutable={r['target']+suffix for r in m['patches']for suffix in ('','.blob')}
    mutable.update(r['file']for r in m['ui_artifacts'])
    mutable.update('staging/codex_fxn5c_1/'+p for p in ('mod.lua','strings.lua','res/models/model/vehicle/train/fxn5c_prototype_0001.mdl'))
    assert set(native['preserved_paths'])==old_files-mutable-removed
    for relative in native['preserved_paths']:
        assert sha(safe_file(ROOT,relative))==sha(safe_file(BASE,relative)),('protected native file changed',relative)
    assert {r['file']:r['sha256']for r in source['scenes']}=={r['file']:r['sha256']for r in m['sources']}
    assert source['manifest_sha256']==sha(ROOT/'manifest_v44.json'),'Final source audit is stale'
    for scene in source['scenes']:
        for snap in scene['snapshot_reexports']:
            assert sha(safe_file(ROOT,snap['snapshot']))==snap['snapshot_sha256']
            assert sha(safe_file(ROOT,snap['snapshot']+'.blob'))==snap['snapshot_blob_sha256']
    portable=load(ROOT/'sourcekit_validation_v44.json')
    assert portable['status']=='PASS' and portable['scene_count']==6 and not portable['issues']
    expected_manifests={'../fxn5c_v43_source/manifest_v43.json':sha(BASE/'manifest_v43.json'),'manifest_v44.json':sha(ROOT/'manifest_v44.json')}
    assert {r['file']:r['sha256']for r in portable['manifest_records']}==expected_manifests
    expected_scenes={p['file']:p['sha256_before']for s in source['scenes']for p in (s['portability'],s['baseline_portability'])}
    assert {p['file']:p['sha256_before']for p in portable['scenes']}==expected_scenes
    assert all(p['unchanged']and p['sha256_before']==p['sha256_after']and not p['issues']for p in portable['scenes'])
    for row in m['sources']:
        assert sha(safe_file(ROOT,row['file']))==row['sha256']
        assert sha(safe_file(BASE,row['baseline']))==row['baseline_sha256']
    for row in m['patches']+m['animated']:
        assert sha(safe_file(ROOT,row['target']))==row['mesh_sha256']
        assert sha(safe_file(ROOT,row['target']+'.blob'))==row['blob_sha256']
    for row in m['assets']+m['ui_artifacts']:
        assert sha(safe_file(ROOT,row['file']))==row['sha256']
    res=MOD/'res';files=set();materials=set();meshes=set();animations=set()
    models=sorted((res/'models/model/vehicle/train').glob('*.mdl'));assert len(models)==13
    for path in models:
        files.add(path)
        for n in walk(read_lua(path)):
            meshes.update(n[k]for k in ('mesh','skin')if n.get(k))
            for k in ('materials','skinMaterials'):materials.update(n.get(k,[]))
            for animation in n.get('animations',{}).values():
                assert animation['type']=='FILE_REF';animations.add(animation['params']['id'])
    for ref in meshes:files.update((safe_file(res/'models/mesh',ref),safe_file(res/'models/mesh',ref+'.blob')))
    for ref in materials:
        path=res/'models/material'/ref
        if not path.exists():assert ref in EXTERNAL;continue
        files.add(path)
        for n in walk(read_lua(path)):
            if n.get('fileName'):files.add(safe_file(res/'textures',n['fileName']))
    for ref in animations:files.add(safe_file(res/'models/animation',ref))
    assert len(animations)==27
    for folder in ('res/textures/ui','res/scripts','LICENSES'):
        files.update(p for p in (MOD/folder).rglob('*')if p.is_file())
    files.update(p for p in MOD.iterdir()if p.is_file())
    game=[(p,'codex_fxn5c_1/'+p.relative_to(MOD).as_posix())for p in files]
    game.append((ROOT/'README_V44.md','codex_fxn5c_1/README_V44.md'))
    scripts,external=dependencies(['build_v44.py','verify_v44.py','audit_source_v44.py','render_v44.py','ui_icons_v44.py','package_v44.py'])
    own={ROOT/n for n in scripts}|{ROOT/n for n in ('README_V44.md','requirements.txt','manifest_v44.json','validation_v44.json','source_validation_v44.json','sourcekit_validation_v44.json')}
    own.update(ROOT/n for n in native['render_inputs_sha256'])
    own.update(ROOT/r['file']for r in m['sources'])
    own.update(ROOT/r['canonical']for r in ui['icons'])
    for row in m['patches']:
        for k in ('before','after'):own.update((ROOT/row[k],ROOT/(row[k]+'.blob')))
    for pattern in ('render_audit_v44*.json','ui_icon_audit_v44*.json'):
        own.update(ROOT.glob(pattern))
    old={BASE/'manifest_v43.json',BASE/'README_V43.md'}
    old.update(BASE/r['baseline']for r in m['sources'])
    for root,collection in ((ROOT,own),(BASE,old)):
        for folder in ('staging','source_textures'):
            collection.update(p for p in (root/folder).rglob('*')if p.is_file())
    combined=own|old
    for scene in source['scenes']:
        for portability in (scene['portability'],scene['baseline_portability']):
            assert not portability['issues'] and portability['unchanged']
            for im in portability['images']:
                if not im['resolved_exists']:continue
                path=safe_file(ROOT.parent,im['resolved_target'])
                assert any(path.is_relative_to(root)for root in (ROOT,BASE))
                assert sha(path)==im['resolved_sha256']
                combined.add(path)
    source_entries=[(p,p.relative_to(ROOT.parent).as_posix())for p in combined]
    game_entries,source_entries=prepare(game),prepare_source(source_entries,ui)
    gr=archive(OUT/names[0],game_entries);sr=archive(OUT/names[1],source_entries)
    report=dict(status='PASS',version='0.44',game=gr,source=sr,models=13,variants=11,
        source_scenes=3,baseline_scenes=3,source_scope='prototype incremental sources; production editable scenes remain in v42 full SourceKit',
        animation_files=len(animations),scripts=sorted(scripts),external_python_modules=sorted(external),
        native_report_sha256=sha(ROOT/'validation_v44.json'),source_report_sha256=sha(ROOT/'source_validation_v44.json'),
        manifest_sha256=sha(ROOT/'manifest_v44.json'),package_script_sha256=sha(Path(__file__)),
        clean_extracted_rebuild_verified=False,game_verified=False,model_editor_verified=False,installed=False,published=False)
    with(OUT/names[2]).open('x',encoding='utf8')as stream:json.dump(report,stream,indent=2,ensure_ascii=False)
    print(json.dumps({k:({i:v for i,v in value.items()if i!='members'}if k in ('game','source')else value)
        for k,value in report.items()if k in ('status','game','source','installed','published')},indent=2),flush=True)


if __name__=='__main__':
    assert __debug__
    main()

