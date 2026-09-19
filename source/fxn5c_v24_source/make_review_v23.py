"""Arrange current native-readback renders; never alter reference photos."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from make_review_v21 import font,panel
from ui_icons_v23 import tga_bytes
ROOT=Path(__file__).resolve().parent
MOD=ROOT/'staging/codex_fxn5c_1'

def main():
    board=Image.new('RGB',(2200,2040),'#edf1f5');d=ImageDraw.Draw(board)
    d.text((32,20),'FXN5C v0.23 | 轴承对中 · 安装关系 · 金温标识',font=font(42),fill='#172c3d')
    d.text((34,85),'由本版游戏资源回读渲染；不是游戏截图，尚未完成游戏内实测。',font=font(25),fill='#506577')
    panel(board,ROOT/'preview_v23/fxn5c_jinwen/side.png',(30,135,2140,620))
    d.text((34,758),'金温侧视：宋体配属、完整 JWR 标识、白色外侧底边；保留设备的 I／II 端位置。',font=font(25),fill='#172c3d')
    rows=[('fxn5c','bearing_coaxial','轴承、轴箱与轮轴对中'),
          ('fxn5c_jinwen','filler_gauge_logo','加油口左上移／油位窗支撑／右侧完整标识'),
          ('fxn5c','bogie_boxes_springs','连带修正弹簧托架、减振器与小箱安装'),
          ('fxn5c_jinwen','cab_full_logo','重建标识轮廓，司机室车号适度加粗')]
    for i,(style,name,label) in enumerate(rows):
        x=30+(i%2)*1090;y=822+(i//2)*555
        d.text((x,y),label,font=font(24),fill='#172c3d')
        panel(board,ROOT/'preview_v23'/style/(name+'.png'),(x,y+43,1050,480))
    d.text((34,1965),'连接杆仍为双端蒙皮近似；本版没有宣称全车隐藏部件或任意曲线净空均已认证。',font=font(24),fill='#984d27')
    board.save(ROOT/'review_v23.png')
    hero=Image.new('RGB',(1024,1024),'#e3e9ef')
    for i,style in enumerate(('fxn5c','fxn5c_jinwen')):
        panel(hero,ROOT/'preview_v23'/style/'overall.png',(0,i*512,1024,512))
    ImageDraw.Draw(hero).text((20,12),'FXN5C | v0.23',font=font(35),fill='#172c3d')
    hero.save(MOD/'workshop_preview.jpg',quality=90,optimize=True)
    small=ImageOps.contain(hero.convert('RGBA'),(320,180),Image.Resampling.LANCZOS)
    cover=Image.new('RGBA',(320,180),'#e3e9ef');cover.alpha_composite(small,((320-small.width)//2,(180-small.height)//2))
    ImageDraw.Draw(cover).text((7,5),'FXN5C v0.23',font=font(18),fill='#172c3d')
    (MOD/'image_00.tga').write_bytes(tga_bytes(cover))
    print('v23 review and covers ready')

if __name__=='__main__':main()
