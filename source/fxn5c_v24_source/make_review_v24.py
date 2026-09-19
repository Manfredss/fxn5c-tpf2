"""Review boards composed only from verified-current native v24 readbacks."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from PIL import Image,ImageDraw,ImageOps
from make_review_v21 import font,panel
from ui_icons_v24 import tga_bytes
from roster_v21 import ROSTER
ROOT=Path(__file__).resolve().parent
MOD=ROOT/'staging/codex_fxn5c_1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evidence():
    rows={};inputs={}
    for style in ('cr','jinwen'):
        candidates=[ROOT/f'render_audit_v24_{style}_{mode}.json' for mode in ('all','views')]
        candidates=[p for p in candidates if p.is_file()]
        assert candidates,('missing current views',style)
        path=max(candidates,key=lambda p:p.stat().st_mtime)
        data=json.loads(path.read_text(encoding='utf-8'))
        assert data['status']=='PASS' and data['engine_playtest'] is False
        inputs[path.relative_to(ROOT).as_posix()]=sha(path)
        for name,digest in data['inputs'].items():assert sha(ROOT/name)==digest,('stale readback input',name)
        for item in data['views']:
            assert sha(ROOT/item['file'])==item['sha256'],('altered view',item['file'])
            assert len(item['conditional_lights']['visible_names'])==1,('invalid all-gates-on preview',item['file'])
            rows[item['file']]=item;inputs[item['file']]=item['sha256']
    return rows,inputs


def new_board(size,title,subtitle):
    board=Image.new('RGB',size,'#edf1f5');draw=ImageDraw.Draw(board)
    draw.text((32,22),title,font=font(42),fill='#172c3d')
    draw.text((34,84),subtitle,font=font(24),fill='#506577')
    return board,draw


def labelled(board,draw,rows,rel,box,label):
    assert rel in rows,('view not covered by current render evidence',rel)
    x,y,w,h=box
    draw.text((x,y),label,font=font(24),fill='#172c3d')
    panel(board,ROOT/rel,(x,y+40,w,h-40))


def main():
    rows,inputs=evidence();outputs=[]
    board,d=new_board((2400,2290),'FXN5C v0.24 | 车顶肩线 · 前端标识 · 金温色带',
        '当前游戏资源回读渲染，不是游戏截图。正视图为同高度正交相机；下列默认前进、单机预览。')
    for i,(stem,label) in enumerate((('fxn5c','国铁蓝 · 0051'),('fxn5c_jinwen','金温铁路 · 7006'))):
        labelled(board,d,rows,f'preview_v24/{stem}/overall.png',(30+i*1190,145,1150,470),label)
    for i,(stem,end,label) in enumerate((('fxn5c','I','国铁 I 端 · 当前前端'),('fxn5c','II','国铁 II 端 · 当前后端'),
                                         ('fxn5c_jinwen','I','金温 I 端 · 当前前端'),('fxn5c_jinwen','II','金温 II 端 · 当前后端'))):
        labelled(board,d,rows,f'preview_v24/{stem}/front_{end}.png',(30+i*592,660,562,740),label)
    labelled(board,d,rows,'preview_v24/fxn5c_jinwen/roof_threequarter.png',(30,1450,1150,650),'双肩斜面与顶部轮廓 · 三维视角核对')
    labelled(board,d,rows,'preview_v24/fxn5c_jinwen/front_marks_I.png',(1220,1450,1150,650),'标识上移；蓝带中央断开，红带连续')
    d.text((34,2185),'灯光按当前原生 Parts 索引选取；单机的同色重叠实例仅在预览中去重，未断言游戏中的分类互斥。',font=font(23),fill='#984d27')
    path=ROOT/'review_v24.png';board.save(path);outputs.append(path)

    roof,rd=new_board((2400,1660),'FXN5C v0.24 | 车顶外形正交对照',
        '列顺序：正面同高正交／侧面同高正交／三维视角。保留 I、II 端不同的设备布局。')
    for row,(stem,label) in enumerate((('fxn5c','国铁蓝'),('fxn5c_jinwen','金温铁路'))):
        for col,(name,caption) in enumerate((('roof_front_I','I 端正视'),('roof_side_I','I 端侧视'),('roof_threequarter','立体轮廓'))):
            labelled(roof,rd,rows,f'preview_v24/{stem}/{name}.png',(30+col*795,145+row*715,765,650),label+' · '+caption)
    path=ROOT/'roof_review_v24.png';roof.save(path);outputs.append(path)

    lamps,ld=new_board((2400,2270),'FXN5C v0.24 | 灯组随行驶方向切换',
        '各图均单独应用原生灯光配置：前端外侧月白、内侧按车号；后端仅内侧红灯，反向时前后交换。')
    columns=(('fwd','I','前进 · I 端前端'),('fwd','II','前进 · II 端后端'),
             ('bwd','I','后退 · I 端后端'),('bwd','II','后退 · II 端前端'))
    reps=(('fxn5c','0051 · 前端内侧白'),('fxn5c_0096','0096 · 前端内侧红'),('fxn5c_jinwen','7006 · 前端内侧白'))
    for row,(stem,label) in enumerate(reps):
        y=145+row*670
        ld.text((32,y),label,font=font(29),fill='#172c3d')
        for col,(direction,end,caption) in enumerate(columns):
            labelled(lamps,ld,rows,f'light_preview_v24/{stem}/{direction}_{end}.png',
                     (30+col*592,y+44,562,590),caption)
    ld.text((34,2205),'这是原生资源的可见状态模拟，并非 Transport Fever 2 内的灯光逻辑实测。',font=font(24),fill='#984d27')
    path=ROOT/'light_review_v24.png';lamps.save(path);outputs.append(path)

    dusk,dd=new_board((2400,1290),'FXN5C v0.24 | 同一灯组的傍晚预览',
        '仅降低环境照明；不修改原生灯具颜色、发光强度或启用额外灯组。')
    for i,(stem,label) in enumerate(reps):
        labelled(dusk,dd,rows,f'light_preview_v24/{stem}/dusk_fwd_I.png',(30+795*i,145,765,1030),label+' · 前进 I 端')
    path=ROOT/'light_dusk_v24.png';dusk.save(path);outputs.append(path)

    # Full-fleet board is available only after icon/all mode also rendered its
    # individual cab closeups; don't silently use inherited v23 pictures.
    fleet_files=[f'fleet_preview_v24/{row["number"]}.png' for row in ROSTER]
    if all(name in rows for name in fleet_files):
        fleet,fd=new_board((2400,1080),'FXN5C v0.24 | 十车号与配属标识',
            '配属按用户要求定制；前灯内侧颜色固定分配，不作为实车设备履历证明。')
        for i,row in enumerate(ROSTER):
            labelled(fleet,fd,rows,f'fleet_preview_v24/{row["number"]}.png',
                     (24+(i%5)*474,145+(i//5)*436,450,404),row['number']+' · '+row['depot'])
        path=ROOT/'fleet_review_v24.png';fleet.save(path);outputs.append(path)
    hero=Image.new('RGB',(1024,1024),'#e3e9ef')
    for i,stem in enumerate(('fxn5c','fxn5c_jinwen')):
        panel(hero,ROOT/f'preview_v24/{stem}/overall.png',(0,i*512,1024,512))
    ImageDraw.Draw(hero).text((20,12),'FXN5C | v0.24',font=font(35),fill='#172c3d')
    path=MOD/'workshop_preview.jpg';hero.save(path,quality=90,optimize=True);outputs.append(path)
    small=ImageOps.contain(hero.convert('RGBA'),(320,180),Image.Resampling.LANCZOS)
    cover=Image.new('RGBA',(320,180),'#e3e9ef');cover.alpha_composite(small,((320-small.width)//2,(180-small.height)//2))
    ImageDraw.Draw(cover).text((7,5),'FXN5C v0.24',font=font(18),fill='#172c3d')
    path=MOD/'image_00.tga';path.write_bytes(tga_bytes(cover));outputs.append(path)
    inputs['make_review_v24.py']=sha(__file__)
    report={'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'engine_playtest':False,
            'inputs':inputs,'outputs':[{'file':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in outputs]}
    (ROOT/'review_audit_v24.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('v24 current front/roof/light/fleet review boards and package covers ready',flush=True)


if __name__=='__main__':main()
