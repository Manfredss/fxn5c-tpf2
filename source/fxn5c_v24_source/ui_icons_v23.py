"""Encode and independently decode actual v23 native-readback icon masters.

Preserves native resource names and descriptor 0 bottom-origin BGRA layout.
No inherited v21/v22 image is accepted as a substitute for a current render.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,struct
from PIL import Image,ImageOps
from roster_v21 import ROSTER,group_stem

ROOT=Path(__file__).resolve().parent
SIZES={'models_small':(640,150),'models_20':(192,40)}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tga_bytes(im):
    im=im.convert('RGBA')
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,im.width,im.height,32,0)
    return header+im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw','BGRA')


def render_evidence():
    icons={};reports=[]
    for style in ('cr','jinwen'):
        candidates=[ROOT/f'render_audit_v23_{style}_{mode}.json' for mode in ('all','icons')]
        candidates=[p for p in candidates if p.is_file()]
        assert candidates,('render report missing',style)
        path=max(candidates,key=lambda p:p.stat().st_mtime)
        report=json.loads(path.read_text(encoding='utf-8'))
        assert report['status']=='PASS' and report['engine_playtest'] is False
        for name,digest in report['inputs'].items():assert sha(ROOT/name)==digest,('stale native render',name)
        for row in report['icons']:
            assert sha(ROOT/row['file'])==row['sha256'],('altered canonical render',row['file'])
            icons[(row['stem'],row['icon_kind'])]=row
        reports.append({'file':path.relative_to(ROOT).as_posix(),'sha256':sha(path)})
    assert len(icons)==20,('canonical icon inventory',len(icons))
    return icons,reports


def main():
    evidence,reports=render_evidence()
    report={'status':'RUNNING','icons':[],'engine_playtest':False,'render_reports':reports,
            'created_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(__file__)}
    for row in ROSTER:
        stems=[row['stem']]
        if row['number'] in ('0051','7006'):stems.append(group_stem(row))
        for kind,size in SIZES.items():
            canonical=ROOT/evidence[(row['stem'],kind)]['file']
            full=Image.open(canonical).convert('RGBA')
            assert full.size==size,('canonical dimensions',canonical,full.size,size)
            for factor in (1,2):
                im=full if factor==2 else full.resize((size[0]//2,size[1]//2),Image.Resampling.BOX)
                box=im.getchannel('A').getbbox()
                assert box and box[0]>0 and box[1]>0 and box[2]<im.width and box[3]<im.height,('clipped icon',row,kind,box)
                for stem in stems:
                    suffix='@2x' if factor==2 else ''
                    path=ROOT/'staging/codex_fxn5c_1/res/textures/ui'/kind/'vehicle/train'/(stem+suffix+'.tga')
                    path.parent.mkdir(parents=True,exist_ok=True)
                    raw=tga_bytes(im);path.write_bytes(raw)
                    assert raw[2]==2 and raw[16]==32 and raw[17]==0
                    assert len(raw)==18+im.width*im.height*4
                    decoded=Image.open(path).convert('RGBA')
                    assert decoded.size==im.size and decoded.tobytes()==im.tobytes(),('orientation/alpha mismatch',path)
                    assert raw[18:18+im.width*4]==im.crop((0,im.height-1,im.width,im.height)).tobytes('raw','BGRA')
                    assert decoded.tobytes()!=ImageOps.flip(im).tobytes(),('vertically symmetric/empty test image',path)
                    report['icons'].append({'file':path.relative_to(ROOT).as_posix(),'size':list(im.size),
                        'sha256':sha(path),'canonical_sha256':sha(canonical),'canonical':canonical.relative_to(ROOT).as_posix(),
                        'bounds':box,'descriptor':0,'pixel_order':'BGRA bottom scanline first','DPI_factor':factor})
    assert len(report['icons'])==48
    report['status']='PASS'
    (ROOT/'ui_icon_audit_v23.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('48 v23 bottom-origin icons PASS',flush=True)


if __name__=='__main__':main()
