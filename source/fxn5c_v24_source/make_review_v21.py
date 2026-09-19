"""Contact sheets of current native readbacks; no source photographs included."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
from roster_v21 import ROSTER
from ui_icons_v21 import tga_bytes
ROOT=Path(__file__).resolve().parent
MOD=ROOT/'staging/codex_fxn5c_1'


def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',size)


def panel(board,path,box):
    x,y,w,h=box
    tile=Image.new('RGB',(w,h),'#e3e9ef')
    im=ImageOps.contain(Image.open(path).convert('RGB'),(w,h),Image.Resampling.LANCZOS)
    tile.paste(im,((w-im.width)//2,(h-im.height)//2));board.paste(tile,(x,y))


def main():
    board=Image.new('RGB',(2400,1580),'#edf1f5');d=ImageDraw.Draw(board)
    d.text((32,20),'FXN5C v0.21 | 国铁与金温 · 设备位置与涂装修订',font=font(43),fill='#172c3d')
    d.text((34,84),'原生模型回读后的 Blender 渲染；不是游戏截图。10 个定制车号，共享两套基型。',font=font(25),fill='#506577')
    shots=[('native_preview','fxn5c_playable_preview.png','国铁蓝 · 0051',32,145),
           ('native_preview_jinwen','fxn5c_playable_preview.png','金温铁路 · 7006',1215,145),
           ('native_preview','fxn5c_bogie_side_v21.png','国铁 · 门下箱体、内端斜底箱及三轴站位',32,808),
           ('native_preview_jinwen','fxn5c_bogie_side_v21.png','金温 · 同结构不同走行部配色',1215,808)]
    for folder,name,title,x,y in shots:
        d.text((x,y),title,font=font(28),fill='#172c3d')
        panel(board,ROOT/folder/name,(x,y+48,1153,585))
    d.text((34,1490),'连接杆仍为蒙皮双端跟随，会弯曲／伸缩；没有声称完成刚性机构或当前版本游戏内验证。',font=font(24),fill='#984d27')
    board.save(ROOT/'review_v21.png')
    fleet=Image.new('RGB',(2400,1080),'#edf1f5');fd=ImageDraw.Draw(fleet)
    fd.text((28,22),'FXN5C v0.21 | 十车号与配属标识',font=font(42),fill='#172c3d')
    fd.text((30,84),'配属按用户要求定制，不作为真实车辆履历认证；购买列表分国铁、金温两组。',font=font(24),fill='#506577')
    for i,row in enumerate(ROSTER):
        x=24+(i%5)*474;y=150+(i//5)*436
        fd.text((x,y),row['number']+' · '+row['depot'],font=font(24),fill='#172c3d')
        panel(fleet,ROOT/'fleet_preview'/(row['number']+'.png'),(x,y+42,450,360))
    fd.text((30,1030),'各图来自独立原生模型；字样网格独立，其余结构按涂装共享。',font=font(23),fill='#506577')
    fleet.save(ROOT/'fleet_review_v21.png')
    hero=Image.new('RGB',(1024,1024),'#e3e9ef')
    for i,folder in enumerate(('native_preview','native_preview_jinwen')):
        panel(hero,ROOT/folder/'fxn5c_playable_preview.png',(0,i*512,1024,512))
    hd=ImageDraw.Draw(hero)
    hd.text((20,12),'FXN5C | v0.21',font=font(35),fill='#172c3d')
    hd.text((20,523),'国铁／金温 · 10 个车号',font=font(31),fill='#172c3d')
    hero.save(MOD/'workshop_preview.jpg',quality=90,optimize=True)
    small=ImageOps.contain(Image.open(ROOT/'native_preview/fxn5c_playable_preview.png').convert('RGBA'),(320,180),Image.Resampling.LANCZOS)
    cover=Image.new('RGBA',(320,180),'#e3e9ef');cover.alpha_composite(small,((320-small.width)//2,(180-small.height)//2))
    ImageDraw.Draw(cover).text((7,5),'FXN5C v0.21',font=font(18),fill='#172c3d')
    (MOD/'image_00.tga').write_bytes(tga_bytes(cover))
    assert (MOD/'workshop_preview.jpg').stat().st_size<1024*1024
    print('Current review_v21.png, fleet_review_v21.png and package covers written.')


if __name__=='__main__':main()
