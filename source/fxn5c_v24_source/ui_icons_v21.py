"""Encode native-style bottom-origin uncompressed BGRA TGA; audit actual bytes."""
from pathlib import Path
import hashlib,json,struct
from PIL import Image,ImageChops,ImageOps
from roster_v21 import ROSTER,group_stem
ROOT=Path(__file__).resolve().parent


def tga_bytes(im):
    im=im.convert('RGBA')
    # Vanilla TPF2 UI: type 2, 32 bit, descriptor 0. Reverse rows in payload,
    # not merely the flag; both strict readers and game UI then see upright.
    header=struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,im.width,im.height,32,0)
    return header+im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw','BGRA')


def main():
    report={'status':'RUNNING','icons':[],'engine_playtest':False}
    for row in ROSTER:
        stems=[row['stem']]
        if row['number'] in ('0051','7006'):stems.append(group_stem(row))
        for kind in ('models_small','models_20'):
            canonical=ROOT/'ui_canonical'/row['stem']/(kind+'.png')
            full=Image.open(canonical).convert('RGBA')
            for factor in (1,2):
                # The 2x render is already antialiased. Area averaging avoids
                # Lanczos ringing that created stray nonzero alpha at row 0.
                im=full if factor==2 else full.resize((full.width//2,full.height//2),Image.Resampling.BOX)
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
                    assert decoded.tobytes()==im.tobytes(),('orientation/alpha mismatch',path)
                    # Independent raw scanline check: first payload row is bottom.
                    assert raw[18:18+im.width*4]==im.crop((0,im.height-1,im.width,im.height)).tobytes('raw','BGRA')
                    assert decoded.tobytes()!=ImageOps.flip(im).tobytes(),('vertically symmetric/empty test image',path)
                    report['icons'].append({'file':path.relative_to(ROOT).as_posix(),'size':im.size,'sha256':hashlib.sha256(raw).hexdigest(),'canonical_sha256':hashlib.sha256(canonical.read_bytes()).hexdigest(),'canonical':canonical.relative_to(ROOT).as_posix(),'bounds':box})
    assert len(report['icons'])==48
    report['status']='PASS'
    (ROOT/'ui_icon_audit_v21.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('48 bottom-origin icons PASS')


if __name__=='__main__':main()
