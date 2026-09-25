"""Photo-fitted signage, converted to paint-like native mesh outlines.

STXinwei is a locally installed visual approximation, not a claim to identify
the factory's font. No font binary is included. The JWR outline is reconstructed
from the user-provided 202 x 70 logo's blue silhouette, with its grey drop shadow
excluded. It is a trademark depiction, not an invented generic wave.
"""
import math
from pathlib import Path
import bpy
from mathutils import Vector

FUXING_HEIGHT = .84
FUXING_WIDTH = 1.94
FUXING_CENTER_Z = 2.79
NUMBER_HEIGHT = .43
NUMBER_WIDTH = 2.76
NUMBER_CENTER_Z = 2.64
WEIBEI_FONT = Path('C:/Windows/Fonts/STXINWEI.TTF')
LATIN_FONT = Path('C:/Windows/Fonts/arialbd.ttf')
CHINESE_SANS_FONT = Path('C:/Windows/Fonts/msyhbd.ttc')

# Pixel-space connected J-W-R outer boundary; X 8.5..186.5, Y 5.5..63.5.
# One simple polygon: the return inside the R is an open notch, not a hole.
JWR_OUTLINE = [
    (134,63.5),(126,61.5),(121.5,57),(107,32.5),(90,60.5),
    (83,63.5),(74,61.5),(68.5,55),(67,20.5),(47.5,54),(41,60.5),
    (34,63.5),(20,61.5),(11.5,54),(8.5,45),(9.5,34),(13.5,27),
    (18,23.5),(25.5,34),(21.5,39),(21.5,45),(26,49.5),(31,50.5),
    (38.5,43),(56.5,11),(62,6.5),(70,5.5),(76,8.5),(80.5,15),
    (82,47.5),(95.5,23),(101,18.5),(108,17.5),(117.5,23),
    (133,48.5),(133.5,15),(137,9.5),(145,5.5),(171,5.5),
    (178,8.5),(185.5,18),(186.5,28),(183.5,36),(175.5,43),
    (186.5,62),(171,62.5),(152.5,31),(153,29.5),(170,29.5),
    (173.5,26),(172.5,21),(170,19.5),(147,19.5),(146.5,53),(140,61.5),
]


def jwr_outline(lod=0):
    """Round sampled curved shoulders; keep the W valleys/R leg corners crisp."""
    if lod>0:return JWR_OUTLINE
    sharp={(107,32.5),(67,20.5),(18,23.5),(25.5,34),(82,47.5),
           (133,48.5),(175.5,43),(186.5,62),(171,62.5),(152.5,31),
           (153,29.5),(147,19.5)}
    points=[]
    for i,xy in enumerate(JWR_OUTLINE):
        p=Vector(xy)
        if xy in sharp:
            points.append(p);continue
        before=Vector(JWR_OUTLINE[i-1]);after=Vector(JWR_OUTLINE[(i+1)%len(JWR_OUTLINE)])
        trim=min(2.5,(before-p).length*.28,(after-p).length*.28)
        a=p+(before-p).normalized()*trim;b=p+(after-p).normalized()*trim
        for j in range(5):
            t=j/4
            points.append((1-t)**2*a+2*(1-t)*t*p+t*t*b)
    # Keep the supplied graphic's visible 178:58 proportion exactly.
    lo=Vector((min(p.x for p in points),min(p.y for p in points)))
    hi=Vector((max(p.x for p in points),max(p.y for p in points)))
    return [(8.5+(p.x-lo.x)*178/(hi.x-lo.x),5.5+(p.y-lo.y)*58/(hi.y-lo.y)) for p in points]


def fitted_text(b, name, value, x, side, z, width, height, key, font=LATIN_FONT):
    """Fit the visible outline, not Blender font em-size, to metric dimensions."""
    if not font.exists():
        raise RuntimeError(f'Required outline source font unavailable: {font}')
    bpy.ops.object.text_add()
    obj = bpy.context.object
    obj.name = name
    obj.data.body = value
    obj.data.font = bpy.data.fonts.load(str(font), check_existing=True)
    obj.data.size = 1
    obj.data.space_character = 1.04
    obj.data.resolution_u = 4 if b.lod == 0 else 2
    obj.data.extrude = 0
    obj.data.materials.append(b.mat(key))
    bpy.ops.object.convert(target='MESH')
    low = Vector((min(v.co.x for v in obj.data.vertices), min(v.co.y for v in obj.data.vertices), 0))
    high = Vector((max(v.co.x for v in obj.data.vertices), max(v.co.y for v in obj.data.vertices), 0))
    center = (low + high) / 2
    direction = -side
    for v in obj.data.vertices:
        xx = x + direction * (v.co.x-center.x) * width / (high.x-low.x)
        zz = z + (v.co.y-center.y) * height / (high.y-low.y)
        v.co = (xx, side*(b.side_y(xx,zz)+.010), zz)
    # XY to XZ with direction=-side already maps the +Z font normal outward.
    obj.data.update()
    obj['livery19_text'] = value
    obj['livery19_height'] = height
    obj['livery19_width'] = width
    obj['livery19_font_approximation'] = font.name
    return obj


def side_titles(b, number='0051', jinwen=False):
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(('side_fuxing', 'side_number', 'jinwen_side_number')):
            bpy.data.objects.remove(obj, do_unlink=True)
    if b.lod == 2:
        return
    for side in (-1,1):
        direction = -side
        fitted_text(b, 'side_fuxing', '复 兴', direction*-1.55, side,
                    FUXING_CENTER_Z, FUXING_WIDTH, FUXING_HEIGHT, 'yellow', WEIBEI_FONT)
        fitted_text(b, 'jinwen_side_number' if jinwen else 'side_number',
                    'FXN5C '+number, direction*1.24, side, NUMBER_CENTER_Z,
                    NUMBER_WIDTH, NUMBER_HEIGHT, 'white')


def jwr_mark(b, x, side, z, width=.70):
    height = width*58/178
    direction = -side
    vertices=[]
    for px,py in jwr_outline(b.lod):
        xx=x+direction*(px-97.5)*width/178
        zz=z+(34.5-py)*height/58
        vertices.append((xx,side*(b.side_y(xx,zz)+.011),zz))
    obj=b.poly('jinwen_jwr_logo_v19',vertices,[tuple(range(len(vertices)))],
               'jw_blue',normal=(0,side,0))
    obj['livery19_logo']='Connected JWR, reconstructed from supplied blue silhouette'
    obj['livery19_width']=width
    obj['livery19_height']=height
    return obj


def jinwen_cab_sign(b,x,side):
    fitted_text(b,'jinwen_cab_number','FXN5C 7006',x,side,2.515,.89,.155,'jw_red')
    jwr_mark(b,x,side,2.290,.72)
    fitted_text(b,'jinwen_cab_operator','金温铁路',x,side,2.070,.73,.122,'jw_blue',CHINESE_SANS_FONT)
    fitted_text(b,'jinwen_cab_operator_latin','JINWEN RAILWAY',x,side,1.976,.72,.042,'jw_blue')
