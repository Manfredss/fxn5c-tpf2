"""Independent v23 ZIP bytes, resource closure and hash-bound evidence audit."""
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO
import argparse,ast,hashlib,json,struct
from PIL import Image,ImageOps
from lupa import LuaRuntime
from package_release_v23 import (ROOT,OUT,HISTORICAL,REPORTS,PATCH_MANIFEST,SCENES,
    SOURCE_ENTRIES,DOCS,GAME_DOCS,STYLES,STEMS,MODEL_STEMS,BASE_GAME_MATERIALS)

EXPECTED_VIEWS=('overall','side','side_opposite','cab_I_broadside','cab_II_broadside',
    'bogie_side','bogie_opposite_end','bearing_coaxial','bogie_boxes_springs',
    'cabinet_gap','front_plumbing','central_fascia','filler_gauge_logo','filler_gauge_logo_opposite')
ICON_SIZES={'models_small':(640,150),'models_20':(192,40)}


def digest(raw):return hashlib.sha256(raw).hexdigest()


def plain(value):
    return {k:plain(v) for k,v in value.items()} if hasattr(value,'items') else value


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
    path=Path(name)
    assert not path.is_absolute() and '..' not in path.parts and '\\' not in name,('unsafe ZIP name',name)
    assert not any(token in name.lower() for token in ('/reference/','codex-clipboard','__pycache__'))
    if '/runtime/' in name.lower():
        assert '/runtime/patch_inputs/' in name and (name.endswith('.msh') or name.endswith('.msh.blob')),name
    assert path.suffix.lower() not in {'.blend1','.pyd','.dll','.exe','.ttf','.ttc','.otf','.woff','.woff2',
        '.webp','.jpeg','.bmp','.gif','.heic','.mp4','.pdf','.pyc'},name
    assert not name.endswith('@2.tga') and not path.name.startswith('bogie_frame_lod'),name
    assert not name.endswith('.jpg') or name.endswith('/workshop_preview.jpg'),name


def resource_closure(z,base):
    names=set(z.namelist());needed=set();meshes=set();materials=set();external=set()
    for stem in MODEL_STEMS:
        name=base+f'res/models/model/vehicle/train/{stem}.mdl';assert name in names;needed.add(name)
        for node in walk(lua(z.read(name))):
            for field in ('mesh','skin'):
                if field in node:meshes.add(node[field])
            for field in ('materials','skinMaterials'):materials.update(node.get(field,{}).values())
    for mesh in meshes:
        safe(mesh)
        for suffix in ('','.blob'):
            name=base+'res/models/mesh/'+mesh+suffix;assert name in names,('missing mesh',name);needed.add(name)
    for material in materials:
        safe(material);name=base+'res/models/material/'+material
        if name not in names:
            assert material in BASE_GAME_MATERIALS,('missing material',name);external.add(material);continue
        needed.add(name)
        for node in walk(lua(z.read(name))):
            if 'fileName' in node:
                safe(node['fileName']);texture=base+'res/textures/'+node['fileName']
                assert texture in names,('missing texture',texture);needed.add(texture)
    actual={name for name in names if name.startswith(base+'res/models/') or name.startswith(base+'res/textures/models/')}
    assert needed==actual,('native closure differs',actual-needed,needed-actual)
    return dict(native_meshes=len(meshes),materials=len(materials),external=external)


def source_checks(z,prefix,hashes):
    names=set(z.namelist())
    def bound(name,h):
        safe(name);full=prefix+name
        assert full in names,('audited input/output absent from archive',name)
        if full not in hashes:hashes[full]=digest(z.read(full))
        assert hashes[full]==h,('archive audited input/output changed',name)
    for name in tuple(SOURCE_ENTRIES)+tuple(DOCS)+tuple(REPORTS)+tuple(SCENES)+(PATCH_MANIFEST,):
        assert prefix+name in names,('missing source artifact',name)
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
    canonical_names={prefix+f'ui_canonical_v23/{stem}/{kind}.png' for stem in STEMS for kind in ICON_SIZES}
    assert {n for n in names if n.startswith(prefix+'ui_canonical_v23/')}==canonical_names
    for name in names:
        rel=name.removeprefix(prefix)
        if '/' not in rel and rel.endswith('.json'):
            assert rel in set(REPORTS)|set(SCENES)|{PATCH_MANIFEST},('obsolete/unexpected report',name)
    assert len(REPORTS)==19,('expected current nineteen-report gate',len(REPORTS))
    reports={name:json.loads(z.read(prefix+name)) for name in REPORTS}
    for name,report in reports.items():
        assert report['status']=='PASS',name
        for block in walk(report):
            for key in ('inputs_sha256','input_sha256','inputs'):
                values=block.get(key,{})
                if not isinstance(values,dict):continue
                for rel,h in values.items():
                    assert isinstance(h,str) and len(h)==64,('invalid input digest',name,key,rel)
                    bound(rel.replace('\\','/'),h)
    fleet=reports['validation_fleet_v23.json']
    assert len(fleet['models'])==10 and {r['variant'] for r in fleet['models']}==set(STEMS)
    for row in fleet['models']:assert row==reports[f"validation_{row['variant']}_v23.json"]
    catalogue=reports['catalogue_audit_v23.json']
    assert len(catalogue['vehicles'])==10 and len(catalogue['groups'])==2 and catalogue['lua_fixture_cases']==555
    fbx=reports['fbx_audit_v23.json']
    assert len(fbx['models'])==6 and {(r['style'],r['lod']) for r in fbx['models']}=={(s,l) for s in STYLES for l in (0,1,2)}
    assert all(r['triangles']>0 and r['exact_native_material_counts'] is True for r in fbx['models'])
    sources=reports['audit_sources_v23.json']
    assert {r['file'] for r in sources['sources']}=={s+'_source.blend' for s in STYLES}
    for row in sources['sources']:bound(row['file'],row['source_sha256'])
    clearance=reports['clearance_audit_v23.json']
    assert clearance['engine_playtest'] is False and len(clearance['styles'])==2
    assert {r['style'] for r in clearance['styles']}==set(STYLES)
    bound('audit_clearance_v23.py',clearance['script_sha256'])
    bound('running_gear_revision_v23.py',clearance['gear_recipe_sha256'])
    for style in clearance['styles']:
        assert style['new_contact_role_pairs']==[]
        current,baseline=style['current'],style['baseline']
        assert current['candidate_recipe_applied_without_save'] is False,('not a saved-source clearance check',style['style'])
        source=style['style']+'_source.blend'
        bound(source,current['source_sha256'])
        assert clearance['inputs_sha256'][source]==current['source_sha256']
        assert baseline['source_sha256'] in clearance['baseline_sha256'].values()
        poses={(b,a) for b in (1,2) for a in (-10,-5,0,5,10)}
        for phase in (current,baseline):
            assert len(phase['poses'])==10 and {(p['bogie'],p['degrees']) for p in phase['poses']}==poses
        old={(p['bogie'],p['degrees']):p for p in baseline['poses']}
        for pose in current['poses']:
            assert pose['moving_triangles']>0 and pose['fixed_meshes_tested']>0
            existing={(c['body'],role) for c in old[(pose['bogie'],pose['degrees'])]['contacts'] for role in c['roles']}
            actual={(c['body'],role) for c in pose['contacts'] for role in c['roles']}
            assert not actual-existing,('unreported new selected-role contact',style['style'],pose['bogie'],pose['degrees'],actual-existing)

    output_names=set();render_report_paths=set()
    for style,label,count in (('fxn5c','cr',8),('fxn5c_jinwen','jinwen',2)):
        report_name=f'render_audit_v23_{label}_all.json';render_report_paths.add(report_name)
        report=reports[report_name]
        assert report['engine_playtest'] is False and report['style']==label and report['mode']=='all'
        bound('render_native_v23.py',report['script_sha256'])
        expected_views=set(EXPECTED_VIEWS)|({'simsun_depot','cab_full_logo'} if label=='jinwen' else set())
        real_views=[r for r in report['views'] if r['kind']!='fleet_cab_number']
        assert {r['kind'] for r in real_views}==expected_views and len(real_views)==len(expected_views)
        assert len(report['icons'])==count*2 and sum(r['kind']=='fleet_cab_number' for r in report['views'])==count
        assert {(r['model'],r['lod']) for r in report['native_axle_measurements']}=={(style,0),(style,1)}
        for row in report['native_axle_measurements']:
            assert row['status']=='PASS' and all(p['alignment_error_m']<.00001 for p in row['rings'])
        for row in report['icons']+report['views']:
            bound(row['file'],row['sha256']);full=prefix+row['file']
            assert full not in output_names,('duplicate render output',full);output_names.add(full)
            raw=z.read(full);assert len(raw)==row['bytes']
            im=Image.open(BytesIO(raw));assert list(im.size)==row['size']
    assert {n for n in names if any(n.startswith(prefix+p) for p in ('preview_v23/','fleet_preview_v23/','ui_canonical_v23/'))}==output_names
    assert len(output_names)==60,('expected thirty detail views,ten fleet views,twenty icon masters',len(output_names))
    assert prefix+'review_v23.png' in names
    allowed_png=output_names|{prefix+'review_v23.png'}
    assert {n for n in names if n.endswith('.png')}==allowed_png,('unexpected raster/reference images in source ZIP',
        {n for n in names if n.endswith('.png')}-allowed_png)

    patch=json.loads(z.read(prefix+PATCH_MANIFEST))
    assert patch['status']=='BUILT_PENDING_AUDIT' and len(patch['patches'])==18
    expected_patches={(s,l,p) for s in STYLES for l in (0,1,2) for p in ('body','b1','b2')}
    assert {(r['style'],r['lod'],r['attachment']) for r in patch['patches']}==expected_patches
    proof_files={prefix+r[phase]['file']+suffix for r in patch['patches'] for phase in ('before','after') for suffix in ('','.blob')}
    assert len(proof_files)==72 and {n for n in names if '/runtime/' in n}==proof_files
    for row in patch['patches']:
        bound(row['target'],row['mesh_sha256']);bound(row['target']+'.blob',row['blob_sha256'])
        raw=z.read(prefix+row['target']+'.blob');descriptor=lua(z.read(prefix+row['target']))
        for attr,h in row['original_attribute_prefix_sha256'].items():
            field=descriptor['vertexAttr'][attr];size=row['original_vertices']*field['numComp']*4
            assert size<=field['count'] and field['offset']+field['count']<=len(raw)
            assert digest(raw[field['offset']:field['offset']+size])==h,('retained original prefix differs',row['target'],attr)
            assert field['count']==size+row['added_vertices']*field['numComp']*4,('unexpected append length',row['target'],attr)
    for row in patch['sources']:bound(row['file'],row['sha256'])
    for name,h in patch['inputs_sha256'].items():bound(name,h)
    native=reports['audit_native_patch_v23.json']
    assert len(native['patches'])==18 and len(native['models'])==12 and len(native['negative_controls'])==4
    assert native['preservation']['unchanged_resource_count']==len(native['preservation']['unchanged_resources'])
    for rel in native['preservation']['unchanged_resources']:
        assert native['inputs_sha256'][rel]==native['baseline_sha256'][rel],('unaltered resource proof differs',rel)
    icon_report=reports['ui_icon_audit_v23.json']
    assert len(icon_report['icons'])==48 and icon_report['engine_playtest'] is False
    bound('ui_icons_v23.py',icon_report['script_sha256'])
    assert {r['file'] for r in icon_report['render_reports']}==render_report_paths
    for row in icon_report['render_reports']:bound(row['file'],row['sha256'])
    for row in icon_report['icons']:
        bound(row['file'],row['sha256']);bound(row['canonical'],row['canonical_sha256'])
    return dict(current_reports=len(reports),source_dependency_closure=True,hash_bound_inputs_outputs=True,
                patch_proof_files=len(proof_files),native_attribute_prefixes=18,actual_render_outputs=len(output_names),
                selected_geometry_clearance_comparisons=20)


def icon_checks(z,base,prefix=None):
    names=set(z.namelist())
    expected={base+f'res/textures/ui/{kind}/vehicle/train/{stem}{suffix}.tga'
        for stem in MODEL_STEMS for kind in ICON_SIZES for suffix in ('','@2x')}
    assert {n for n in names if n.startswith(base+'res/textures/ui/')}==expected
    for name in expected:
        raw=z.read(name);assert raw[0:3]==bytes((0,0,2)) and raw[16]==32 and raw[17]==0,('TGA encoding',name)
        kind=name.removeprefix(base+'res/textures/ui/').split('/')[0]
        size=ICON_SIZES[kind] if '@2x' in name else tuple(v//2 for v in ICON_SIZES[kind])
        im=Image.open(BytesIO(raw)).convert('RGBA')
        assert im.size==size and struct.unpack('<HH',raw[12:16])==size and len(raw)==18+size[0]*size[1]*4,('TGA dimensions/payload length',name)
        assert raw[18:18+im.width*4]==im.crop((0,im.height-1,im.width,im.height)).tobytes('raw','BGRA'),('physical bottom scanline',name)
        box=im.getchannel('A').getbbox()
        assert box and box[0]>0 and box[1]>0 and box[2]<im.width and box[3]<im.height,('clipped/empty icon',name)
        if prefix:
            stem=Path(name).stem.removesuffix('@2x')
            if stem=='fxn5c_menu_cr':stem='fxn5c'
            if stem=='fxn5c_menu_jinwen':stem='fxn5c_jinwen'
            canonical=Image.open(BytesIO(z.read(prefix+f'ui_canonical_v23/{stem}/{kind}.png'))).convert('RGBA')
            if '@2x' not in name:canonical=canonical.resize(size,Image.Resampling.BOX)
            assert canonical.size==im.size and canonical.tobytes()==im.tobytes(),('upright canonical mismatch',name)
            assert ImageOps.flip(canonical).tobytes()!=im.tobytes(),('vertical flip negative control ineffective',name)
    return len(expected)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=OUT)
    out=parser.parse_args().output.resolve()
    for name,h in HISTORICAL.items():assert digest((OUT/name).read_bytes())==h,('historical v22 changed',name)
    manifest_path=out/'FXN5C_v0.23_manifest.json';manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['historical_v22_sha256']==HISTORICAL and set(manifest['reports'])==set(REPORTS)
    assert {r['file'] for r in manifest['archives']}=={'FXN5C_TPF2_v0.23.zip','FXN5C_Source_v0.23.zip'}
    game_bytes={};results=[]
    for item in sorted(manifest['archives'],key=lambda r:'Source' in r['file']):
        path=out/item['file'];assert path.stat().st_size==item['bytes'] and digest(path.read_bytes())==item['sha256']
        source='Source' in item['file'];prefix='FXN5C_Source_v0.23/' if source else ''
        base=prefix+('staging/' if source else '')+'codex_fxn5c_1/'
        with ZipFile(path) as z:
            assert z.testzip() is None
            names=z.namelist();assert len(names)==len(set(names))
            assert all(n.startswith(prefix if source else base) for n in names)
            assert set(names)=={e['path'] for e in item['entries']}
            hashes={}
            for entry in item['entries']:
                name=entry['path'];safe(name);raw=z.read(name);hashes[name]=digest(raw)
                assert hashes[name]==entry['sha256'],('archived bytes mismatch',name)
                local=(ROOT/entry['source']).resolve();assert local.is_relative_to(ROOT.resolve())
                assert local.is_file() and digest(local.read_bytes())==entry['sha256'],('archive/current source mismatch',name)
                if not source:game_bytes[name]=hashes[name]
                elif name.startswith(base):
                    assert game_bytes[name.removeprefix(prefix+'staging/')]==hashes[name],('source/game payload mismatch',name)
            assert lua(z.read(base+'mod.lua'))['info']['minorVersion']==23
            docs={n.removeprefix(base+'documents/') for n in names if n.startswith(base+'documents/')}
            assert docs==set(GAME_DOCS),('obsolete/unexpected game documentation',docs)
            native=resource_closure(z,base);assert native.pop('external')==set(manifest['external_base_game_materials'])
            icon_count=icon_checks(z,base,prefix if source else None)
            detail=source_checks(z,prefix,hashes) if source else {}
            results.append(dict(file=item['file'],sha256=item['sha256'],files=len(names),crc_pass=True,
                native_reference_closure=True,current_source_bytes_match=True,ui_icons=icon_count,**native,**detail))
    for name,h in HISTORICAL.items():assert digest((OUT/name).read_bytes())==h,('historical v22 changed during sanity',name)
    report=dict(status='PASS',archives=results,historical_v22_unchanged=True,
        scope='Archived bytes, hash-bound current reports/render outputs, resource/import closure, retained attributes and upright icons; NOT game runtime.',
        game_installation_modified=False,game_verified=False,steam_uploaded=False)
    report_path=out/'FXN5C_v0.23_release_checks.json'
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest['status']='STATIC_PASS'
    manifest['independent_sanity']={'file':report_path.name,'sha256':digest(report_path.read_bytes()),'status':'PASS'}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
