"""Encode all thirteen actual MDLs as 52 upright bottom-origin RGBA TGAs.

Run only after final native verification AND final render_v44 icon reports.
Replaces the obsolete prototype PNG pair with four engine-requested TGAs.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,struct
from PIL import Image
from roster_v21 import ROSTER
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent/'fxn5c_v43_source'
UI=ROOT/'staging/codex_fxn5c_1/res/textures/ui'
STEM='fxn5c_prototype_0001'
STEMS=sorted([r['stem']for r in ROSTER]+['fxn5c_menu_cr','fxn5c_menu_jinwen',STEM])
SIZES={'models_small':(178,56),'models_20':(64,20)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def rel(path):return Path(path).relative_to(ROOT).as_posix()


def tga_bytes(image):
    """Type 2, RGBA32, descriptor 8: alpha8, bottom-left origin, no RLE."""
    assert image.mode=='RGBA'
    w,h=image.size
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,w,h,32,8)
    payload=image.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw','BGRA')
    return header+payload


def bounds_ok(image,label):
    bounds=image.getchannel('A').getbbox()
    assert bounds and bounds[0]>0 and bounds[1]>0 and bounds[2]<image.width and bounds[3]<image.height,('Clipped icon',label,bounds,image.size)
    assert image.getchannel('A').getextrema()==(0,255),('Missing transparency or fully opaque pixels',label)
    return list(bounds)


def audit_tga(path,image):
    raw=path.read_bytes();w,h=image.size
    fields=struct.unpack('<BBBHHBHHHHBB',raw[:18])
    assert fields==(0,0,2,0,0,0,0,0,w,h,32,8),('Wrong TGA header',str(path),fields)
    assert len(raw)==18+w*h*4
    assert raw[18:18+w*4]==image.crop((0,h-1,w,h)).tobytes('raw','BGRA'),'First encoded row must be bottom image row'
    assert raw[-w*4:]==image.crop((0,0,w,1)).tobytes('raw','BGRA'),'Last encoded row must be top image row'
    decoded=Image.open(path).convert('RGBA')
    assert decoded.size==image.size and decoded.tobytes()==image.tobytes(),('TGA orientation/pixel mismatch',str(path))
    return dict(type=2,bits_per_pixel=32,descriptor=8,origin='bottom-left',compression='none',
                decoded_rgba_pixel_exact=True,first_raw_scanline_matches_bottom=True)


def main():
    proof=load(ROOT/'validation_v44.json');manifest_path=ROOT/'manifest_v44.json';manifest=load(manifest_path)
    assert proof['status']=='PASS'and manifest['status']=='NATIVE_STATIC_PASS'
    assert manifest['validation_sha256']==sha(ROOT/'validation_v44.json')
    assert len(STEMS)==13 and len(set(STEMS))==13
    prepared=[];render_reports=[]
    # Validate every final native input and every source before touching assets.
    for stem in STEMS:
        audit_path=ROOT/f'render_audit_v44_{stem}_lod0_icons.json';evidence=load(audit_path)
        assert evidence['status']=='PASS'and evidence['kind']=='native_resource_blender_reconstruction'
        assert evidence['stem']==stem and evidence['lod']==0 and evidence['engine_playtest']is False
        assert len(evidence['icons'])==2 and{r['icon_kind']for r in evidence['icons']}==set(SIZES)
        for name in(f'native_scene_{stem}.json','native_meshes.json'):
            assert evidence['inputs'][name]==proof['render_inputs_sha256'][name]
        for name,digest in evidence['inputs'].items():
            assert not name.endswith('.blend'),'Icons must derive from native resources'
            path=(ROOT/name).resolve();assert path.is_relative_to(ROOT)
            assert sha(path)==digest,('Stale icon render',name)
        render_reports.append(dict(file=rel(audit_path),sha256=sha(audit_path),stem=stem))
        for row in evidence['icons']:
            kind=row['icon_kind'];source=ROOT/row['file'];size=SIZES[kind]
            assert sha(source)==row['sha256']
            assert(row['width'],row['height'])==(size[0]*2,size[1]*2)
            lights=row['conditional_lights']
            assert lights['direction']=='fwd'and lights['position']=='singleton'and len(lights['visible_names'])==1
            camera=row['camera_audit'];stage=row['stage']
            assert camera['projection']=='ORTHO'and camera['parallel_to_track']and camera['positive_x_at_screen_right']
            assert abs(row['camera'][0]-row['target'][0])<1e-8 and abs(row['camera'][2]-row['target'][2])<1e-8
            assert stage['original_generated_stage']and not stage['third_party_assets']and not stage['exported_to_game_geometry']
            master=Image.open(source).convert('RGBA');assert master.size==(size[0]*2,size[1]*2)
            for density,suffix in((1,''),(2,'@2x')):
                image=master if density==2 else master.resize(size,Image.Resampling.BOX)
                bounds=bounds_ok(image,(stem,kind,density))
                path=UI/kind/'vehicle/train'/(stem+suffix+'.tga')
                prepared.append((path,image,dict(file=rel(path),width=image.width,height=image.height,
                    stem=stem,kind=kind,density=density,canonical=rel(source),canonical_sha256=sha(source),
                    bounds=bounds,format='TGA',camera_audit=camera)))
    assert len(prepared)==52 and len({str(r[0])for r in prepared})==52
    added=sorted(rel(UI/k/'vehicle/train'/(STEM+s+'.tga'))for k in SIZES for s in('','@2x'))
    removed=sorted(rel(UI/k/'vehicle/train'/(STEM+'.png'))for k in SIZES)
    previous=[];deleted=[]
    for path,image,row in prepared:
        if path.is_file():previous.append(dict(file=rel(path),sha256=sha(path)))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tga_bytes(image))
        row.update(sha256=sha(path),encoding_audit=audit_tga(path,image))
    # Exact authorized obsolete files only; originals remain in read-only v43.
    for name in removed:
        path=ROOT/name
        if path.is_file():
            recovery=BASE/name
            assert recovery.is_file()and sha(recovery)==sha(path),('Unexpected modified prototype PNG',name)
            deleted.append(dict(file=name,sha256=sha(path),recoverable_baseline='../fxn5c_v43_source/'+name))
            path.unlink()
    rows=sorted([row for _,_,row in prepared],key=lambda r:r['file'])
    assert len(list(UI.rglob('*.tga')))==52
    assert not list(UI.rglob('*.png')),'Obsolete PNG icons remain'
    report=dict(status='PASS',created_utc=datetime.now(timezone.utc).isoformat(),icons=rows,
        render_reports=render_reports,script_sha256=sha(__file__),previous_icons=previous,
        ui_inventory_changes=dict(added=added,removed=removed),deleted_files=deleted,
        engine_playtest=False,model_editor=False,
        orientation='Level side-profile native reconstruction; every TGA decodes pixel-exactly upright from explicit bottom-origin BGRA32 scanlines.',
        geometry_stage='Original procedural rail display exists only in icon pixels, never game geometry.',
        canonical_sizes={k:[v[0]*2,v[1]*2]for k,v in SIZES.items()})
    report_path=ROOT/'ui_icon_audit_v44.json';report_path.write_text(json.dumps(report,indent=2),encoding='utf8')
    manifest['ui_artifacts']=[{key:r[key]for key in('file','sha256','width','height')}for r in rows]
    manifest['ui_inventory_changes']=dict(added=added,removed=removed)
    manifest['ui_icon_audit_sha256']=sha(report_path)
    manifest_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
    print('UI44_PASS 52 type2 RGBA32 bottom-origin TGAs; 13 actual models; 4 prototype TGAs added; 2 obsolete PNGs removed',flush=True)


if __name__=='__main__':main()
