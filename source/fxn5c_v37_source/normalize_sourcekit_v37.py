"""Reuse exact-payload/path-only normalizer on v28-owned files only."""
from pathlib import Path
import sys,json,os,hashlib
import bpy
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent/'fxn5c_v36_source'
sys.path.insert(0,str(ROOT))
import normalize_sourcekit_v26 as norm
from native_patch_v23 import sha
norm.ROOT=ROOT;norm.BASE=BASE;norm.WORK=ROOT.parent
bpy.context.preferences.filepaths.save_version=0
included={p.resolve() for folder in ('staging','source_textures') for p in (ROOT/folder).rglob('*') if p.is_file()}
payload_files={sha(p):p for p in included if p.suffix.lower() in ('.png','.tga','.dds','.jpg')}
files=[ROOT/'fxn5c_source.blend',ROOT/'fxn5c_jinwen_source.blend']
files+=sorted((ROOT/'runtime').glob('final37_*.blend'))
files+=sorted((ROOT/'runtime').glob('baseline37_*.blend'))
rows=[]
for path in files:
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    assert not bpy.data.libraries
    assert not any(f.filepath and f.filepath!='<builtin>' for f in bpy.data.fonts)
    changes=[];images=[]
    for im in bpy.data.images:
        if im.source!='FILE':continue
        was_packed=bool(im.packed_file)
        target=Path(bpy.path.abspath(im.filepath)).resolve()
        if not was_packed:
            assert target.is_file(),('missing image',target)
            im.pack()
        payload=hashlib.sha256(bytes(im.packed_file.data)).hexdigest()
        if payload in payload_files:target=payload_files[payload]
        assert target.is_relative_to(ROOT) or target.is_relative_to(BASE),('external image dependency',target)
        assert target.is_file() and sha(target)==payload,('image does not match packed payload',target)
        if not im.filepath.startswith('//') or not was_packed or Path(bpy.path.abspath(im.filepath)).resolve()!=target:
            changes.append((im,im.filepath,'//'+os.path.relpath(target,path.parent).replace('\\','/')))
        images.append(dict(name=im.name,path=target.relative_to(ROOT.parent).as_posix(),sha256=payload,packed=True))
    if changes:
        # Only scenes with actual absolute references are rewritten. Sign the
        # active mesh data and transforms, not thousands of irrelevant RNA UI
        # fields, and ensure save/reopen does not change this geometry.
        def signature():
            meshes={o.data.name:o.data for o in bpy.context.scene.objects if o.type=='MESH'}
            return norm.digest(dict(meshes={n:norm.mesh_signature(m) for n,m in meshes.items()},
                objects={o.name:dict(matrix=norm.plain(o.matrix_world),parent=o.parent.name if o.parent else None,
                    data=o.data.name if o.data else None,tags=norm.plain(dict(o.items()))) for o in bpy.context.scene.objects}))
        before=signature()
        for im,old,new in changes:im.filepath=new
        bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=False)
        bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
        assert signature()==before,('path-only rewrite changed geometry',path)
    rows.append(dict(file=path.relative_to(ROOT).as_posix(),sha256=sha(path),
        relative_packed_images=len(images),absolute_paths_repaired=len(changes),images=images))
    (ROOT/'sourcekit_v37.json').write_text(json.dumps(dict(status='RUNNING',rows=rows),indent=2))
    print('NORMALIZED27',path.name,flush=True)
manifest=json.loads((ROOT/'manifest_v37.json').read_text())
for row in manifest['sources']:row['sha256']=sha(ROOT/row['file'])
(ROOT/'manifest_v37.json').write_text(json.dumps(manifest,indent=2))
(ROOT/'sourcekit_v37.json').write_text(json.dumps(dict(status='PASS',rows=rows,
    geometry_uv_material_transform_tags_preserved=True,baseline_v26_unchanged=True),indent=2))
