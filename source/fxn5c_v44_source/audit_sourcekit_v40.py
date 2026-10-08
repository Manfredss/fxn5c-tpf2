"""Read-only portability inspection of all six v40 and six v39 scenes.

Never packs, rebases or saves a scene. This is dependency inspection, not a
clean-extract full rebuild. Run with Blender --background --disable-autoexec.
"""
from pathlib import Path
import hashlib
import json
import re
import bpy

ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v39_source'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def is_absolute(path):
    return bool(re.match(r'^[A-Za-z]:[/\\]',path) or path.startswith('\\\\') or
                (path.startswith('/') and not path.startswith('//')))


def label(path):
    path=Path(path).resolve()
    return path.relative_to(ROOT.parent).as_posix() if path.is_relative_to(ROOT.parent) else str(path)


def resolved(path,library=None):
    return Path(bpy.path.abspath(path,library=library)).resolve() if path else None


def packed_payloads(image):
    if image.packed_file:
        return [hashlib.sha256(bytes(image.packed_file.data)).hexdigest()]
    return [hashlib.sha256(bytes(item.packed_file.data)).hexdigest() for item in image.packed_files]


def inspect_scene(path,owner,expected):
    before=sha(path)
    assert before==expected,('Scene hash no longer matches build manifest',path)
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)
    issues=[];warnings=[];images=[]
    for image in bpy.data.images:
        raw=image.filepath
        packed=packed_payloads(image)
        target=resolved(raw,image.library)
        exists=bool(target and target.is_file())
        relative=raw.startswith('//') or (bool(raw) and not is_absolute(raw))
        in_textures=bool(target and target.is_relative_to(owner/'source_textures'))
        disk_sha=sha(target) if exists else None
        item={'name':image.name,'users':image.users,'source':image.source,
              'filepath':raw,'relative':relative,'packed':bool(packed),
              'packed_payload_sha256':packed,'resolved_target':label(target) if target else None,
              'resolved_exists':exists,'resolved_in_own_source_textures':in_textures,
              'resolved_sha256':disk_sha,'matching_packed_and_external_bytes':disk_sha in packed if packed and disk_sha else None}
        images.append(item)
        if image.source in ('GENERATED','VIEWER'):continue
        if not packed and not (relative and exists and in_textures):
            issues.append({'type':'nonportable_external_image','image':image.name,'path':raw})
        if is_absolute(raw):
            (warnings if packed else issues).append({'type':'absolute_image_path_packed' if packed else 'absolute_image_path',
                                                     'image':image.name,'path':raw})
        if packed and exists and disk_sha not in packed:
            issues.append({'type':'packed_external_payload_mismatch','image':image.name})

    fonts=[]
    for font in bpy.data.fonts:
        raw=font.filepath;external=bool(raw and raw!='<builtin>')
        packed=bool(font.packed_file)
        target=resolved(raw) if external else None
        fonts.append({'name':font.name,'users':font.users,'filepath':raw,'external':external,'packed':packed})
        # Do not claim a scene is clean by simply embedding a system font;
        # this project distributes converted glyph meshes, not font binaries.
        if external:
            issues.append({'type':'external_font_datablock','font':font.name,'path':raw,'packed':packed})
    libraries=[]
    for library in bpy.data.libraries:
        raw=library.filepath;target=resolved(raw)
        item={'name':library.name,'filepath':raw,'exists':bool(target and target.is_file()),
              'relative':raw.startswith('//'),'packed':bool(library.packed_file)}
        libraries.append(item)
        # Package plan contains no external library trees. Raise rather than
        # infer that a coincidentally present local file will be distributed.
        issues.append({'type':'linked_library_requires_package_mapping',**item})

    others=[]
    for collection_name in ('sounds','movieclips','cache_files','volumes'):
        for block in getattr(bpy.data,collection_name,[]):
            raw=getattr(block,'filepath','')
            if not raw:continue
            target=resolved(raw,getattr(block,'library',None))
            packed=bool(getattr(block,'packed_file',None))
            item={'collection':collection_name,'name':block.name,'filepath':raw,'packed':packed,
                  'exists':bool(target and target.is_file()),'absolute':is_absolute(raw)}
            others.append(item)
            if not packed:issues.append({'type':'other_external_dependency_requires_mapping',**item})
    texts=[{'name':t.name,'filepath':t.filepath,'use_module':t.use_module} for t in bpy.data.texts]
    for item in texts:
        if is_absolute(item['filepath']):
            warnings.append({'type':'embedded_text_retains_absolute_source_label',**item})
    # Blender's own dependency enumeration catches external paths not exposed
    # above (for example simulation caches); packed resources are excluded.
    enumerated=[]
    for raw in bpy.utils.blend_paths(absolute=False,packed=False,local=True):
        target=resolved(raw)
        item={'filepath':raw,'absolute':is_absolute(raw),'exists':bool(target and target.is_file()),
              'resolved_target':label(target) if target else None,
              'resolved_in_own_source_textures':bool(target and target.is_relative_to(owner/'source_textures'))}
        enumerated.append(item)
        if item['absolute'] or not item['exists'] or not item['resolved_in_own_source_textures']:
            issues.append({'type':'unpacked_dependency_not_portable',**item})
    after=sha(path)
    assert after==before,('Scene changed during read-only audit',path)
    return {'file':label(path),'sha256_before':before,'sha256_after':after,
            'manifest_sha256_expected':expected,'unchanged':True,'images':images,
            'fonts':fonts,'font_objects':[o.name for o in bpy.data.objects if o.type=='FONT'],
            'linked_libraries':libraries,'other_external_dependencies':others,'text_blocks':texts,
            'blender_unpacked_dependency_enumeration':enumerated,'issues':issues,'warnings':warnings}


def main():
    records=[];manifests=[]
    for owner,version in ((ROOT,40),(BASE,39)):
        path=owner/f'manifest_v{version}.json'
        manifest=json.loads(path.read_text(encoding='utf8'))
        manifests.append({'file':label(path),'sha256':sha(path),'status_at_inspection':manifest['status']})
        entries=manifest['sources']
        assert len(entries)==6,(version,len(entries))
        for entry in entries:
            scene=owner/entry['file']
            records.append(inspect_scene(scene,owner,entry['sha256']))
            print('SOURCEKIT40_SCENE',version,entry['file'],'issues',len(records[-1]['issues']),flush=True)
    issues=[{'file':r['file'],**item} for r in records for item in r['issues']]
    warnings=[{'file':r['file'],**item} for r in records for item in r['warnings']]
    report={'status':'PASS' if not issues else 'FAIL','scope':'Read-only dependency inspection of six v40 and six v39 scenes',
            'clean_extract_rebuild_tested':False,'source_files_modified':False,
            'manifest_records':manifests,'scenes':records,'issues':issues,'warnings':warnings,
            'scene_count':len(records),'required_sibling_layout':['fxn5c_v40_source','fxn5c_v39_source'],
            'required_texture_directories':['fxn5c_v40_source/source_textures','fxn5c_v39_source/source_textures']}
    (ROOT/'sourcekit_validation_v40.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf8')
    print('SOURCEKIT40',report['status'],'scenes',len(records),'issues',len(issues),'warnings',len(warnings),flush=True)
    assert not issues,issues[:4]


if __name__=='__main__':main()
