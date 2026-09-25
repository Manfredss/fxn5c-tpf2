"""Validated local candidate only; no installation, upload or publication."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import sys,json
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'fxn5c_v36_source';OUT=ROOT.parents[1]/'outputs'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from package_release_v21 import native_closure,dependencies
from native_patch_v23 import sha
from verify_native import read_lua
from animation_v26 import flatten_nodes

def archive(path,entries):
    assert not path.exists(),('refuse overwrite',path)
    assert len(entries)==len({name for _,name in entries})
    with ZipFile(path,'w',ZIP_DEFLATED,compresslevel=6) as z:
        for p,name in sorted(entries,key=lambda row:row[1]):
            assert p.is_file() and '..' not in Path(name).parts and not Path(name).is_absolute()
            z.write(p,name)
    with ZipFile(path) as z:assert z.testzip() is None
    return dict(file=path.name,bytes=path.stat().st_size,sha256=sha(path),entries=len(entries))

def media():
    folder=ROOT/'preview_v37/native/fxn5c';manifest=json.loads((folder/'render_manifest.json').read_text())
    assert len(manifest['frames'])==16
    frames=[Image.open(folder/r['file']).convert('RGB') for r in manifest['frames']]
    gif=OUT/'FXN5C_v0.37_roof_wave.gif'
    frames[0].save(gif,save_all=True,append_images=frames[1:],duration=50,loop=0)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',25)
    card=Image.new('RGB',(1600,1200),'#142333');draw=ImageDraw.Draw(card)
    draw.text((25,12),'FXN5C v0.37 · 大窗常开 / 小百叶9片、40°、0.8秒波浪',font=font,fill='white')
    draw.text((25,47),'最终原生资源离线回读；非游戏截图。风扇保持原样。',font=font,fill='#cad7df')
    for i,ms in enumerate((0,200,400,600)):
        x=25+(i%2)*800;y=120+(i//2)*360
        draw.text((x,y-30),f'{ms/1000:.1f} 秒',font=font,fill='white')
        frame=ImageOps.contain(Image.open(folder/f'wave_{ms:04}.png').convert('RGB'),(750,310))
        card.paste(frame,(x,y))
    draw.text((25,815),'大散热窗：固定打开55°，不再循环闭合',font=font,fill='white')
    for i,style in enumerate(('fxn5c','fxn5c_jinwen')):
        im=ImageOps.contain(Image.open(ROOT/f'preview_v37/native/{style}/big_open.png').convert('RGB'),(750,320))
        card.paste(im,(25+800*i,855))
    contact=OUT/'FXN5C_v0.37_wave_review.jpg';card.save(contact,quality=94)
    return [dict(file=p.name,sha256=sha(p)) for p in (gif,contact)]

def main():
    OUT.mkdir(exist_ok=True)
    names=('validation_v37.json','geometry_validation_v37.json','sourcekit_v37.json','options_validation_v37.json')
    reports={n:json.loads((ROOT/n).read_text()) for n in names};assert all(r['status']=='PASS' for r in reports.values())
    m=json.loads((ROOT/'manifest_v37.json').read_text());assert m['status']=='NATIVE_STATIC_PASS'
    assert m['validation_sha256']==sha(ROOT/'validation_v37.json')
    for p,digest in m['recipe_sha256'].items():assert sha(ROOT/p)==digest
    for row in m['sources']:assert sha(ROOT/row['file'])==row['sha256']
    for row in m['animated']+m['patches']:
        assert sha(ROOT/row['target'])==row['mesh_sha256']
        assert sha(str(ROOT/row['target'])+'.blob')==row['blob_sha256']
    for ref,digest in m['animation_files'].items():assert sha(ROOT/'staging/codex_fxn5c_1/res/models/animation'/ref)==digest
    for rel,digest in reports['options_validation_v37.json']['inputs_sha256'].items():assert sha(ROOT/rel)==digest
    for style in ('fxn5c','fxn5c_jinwen'):
        r=json.loads((ROOT/f'preview_v37/native/{style}/render_manifest.json').read_text())
        assert r['build_manifest_sha256']==sha(ROOT/'manifest_v37.json')
        assert r['native_model_sha256']==sha(ROOT/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
    media_rows=media()
    files,models,external=native_closure();mod=ROOT/'staging/codex_fxn5c_1';animations=set()
    for stem in models:
        model=read_lua(mod/f'res/models/model/vehicle/train/{stem}.mdl')
        for lod in model['lods']:
            for node in flatten_nodes(lod['node']):
                for a in node.get('animations',{}).values():
                    assert a['type']=='FILE_REF'
                    p=mod/'res/models/animation'/a['params']['id'];assert p.is_file();files.add(p);animations.add(p)
    assert len(animations)==27
    for folder in ('res/textures/ui','res/scripts','LICENSES'):
        files.update(p for p in (mod/folder).rglob('*') if p.is_file())
    files.update(p for p in mod.iterdir() if p.is_file())
    game_entries=[(p,'codex_fxn5c_1/'+p.relative_to(mod).as_posix()) for p in files]
    game_entries.append((ROOT/'README_V37.md','codex_fxn5c_1/README_V37.md'))
    # Prepare all source entries BEFORE emitting either ZIP, so missing source
    # inputs do not leave a half-complete release candidate pair.
    own={ROOT/p for p in dependencies(('build_v37.py','shutters_v37.py','verify_v37.py','audit_geometry_v37.py','normalize_sourcekit_v37.py',
          'audit_options_v37.py','preview_native_v37.py','package_v37.py'))}
    own.update(ROOT/p for p in ('README_V37.md','requirements.txt','manifest_v37.json','native_meshes.json',*names))
    own.update(ROOT/s['file'] for s in m['sources'])
    for p in m['patches']:
        for k in ('before','after'):own.update((ROOT/p[k],ROOT/(p[k]+'.blob')))
    own.update(ROOT/f'native_scene_{stem}.json' for stem in models)
    own.update(ROOT/p for p in ('native_scene.json','native_scene_jinwen.json'))
    for folder in ('staging','source_textures','preview_v37'):
        own.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
    baseline={BASE/p for p in ('manifest_v36.json','validation_v36.json','sourcekit_v36.json','README_V36.md',
        'wave_geometry_v36.json','options_validation_v36.json','native_meshes.json')}
    oldm=json.loads((BASE/'manifest_v36.json').read_text());baseline.update(BASE/s['file'] for s in oldm['sources'])
    for folder in ('staging','source_textures'):
        baseline.update(p for p in (BASE/folder).rglob('*') if p.is_file())
    entries=[(p,p.relative_to(ROOT.parent).as_posix()) for p in own|baseline]
    assert not any(p.suffix.lower() in ('.exe','.dll','.pyd','.ttf','.ttc','.otf','.blend1') for p,_ in entries)
    entrymap={name:p for p,name in entries}
    for root,report in ((ROOT,reports['sourcekit_v37.json']),(BASE,json.loads((BASE/'sourcekit_v36.json').read_text()))):
        for row in report['rows']:
            assert sha(root/row['file'])==row['sha256']
            for im in row['images']:assert im['path'] in entrymap and sha(entrymap[im['path']])==im['sha256']
    for p,_ in game_entries+entries:assert p.is_file(),p
    game=archive(OUT/'FXN5C_TPF2_v0.37_candidate.zip',game_entries)
    source=archive(OUT/'FXN5C_Source_v0.37_candidate.zip',entries)
    report=dict(status='PASS',game=game,source=source,media=media_rows,models=sorted(models),
        animation_files=len(animations),game_verified=False,installed=False,published=False,
        report_hashes={p:sha(ROOT/p) for p in names})
    (OUT/'FXN5C_v0.37_package_audit.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
