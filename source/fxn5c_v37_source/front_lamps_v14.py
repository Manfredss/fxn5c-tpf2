"""Forward optics seated directly in the new continuous shallow nose land."""
import math
import bpy
from mathutils import Vector
from front_details_v10 import circle, make_upper_lamps
from nose_shell_v14 import corner_x


def lower_frame(end,side,kind):
    return Vector((end*(11.04 if kind=='white' else 10.990),side*(1.24 if kind=='white' else 1.53),
                   2.02 if kind=='white' else 2.055)),Vector((0,side,0)),Vector((end,0,0))


def mapper(end,side,kind,offset):
    p,u,n=lower_frame(end,side,kind)
    return lambda a,b:tuple(p+u*a+Vector((0,0,b))+n*offset)


def lower_lamps(b,end):
    for side in (-1,1):
        for kind in ('white','red'):
            base,_,normal=lower_frame(end,side,kind)
            if kind=='red':
                shell=bpy.data.objects['body_open_shell_v07']
                cutter=b.sheet('outer_bore_v12',circle(.112,64 if b.lod==0 else 32),
                    lambda u,v:(end*11.15,base.y+side*u,base.z+v),'black',.45,(end,0,0))
                b.cut(shell,cutter)
                n=64 if b.lod==0 else 32
                skin=[(end*(corner_x(base.y+side*u,base.z+v)+.001),base.y+side*u,base.z+v) for u,v in circle(.114,n)]
                seat=[mapper(end,side,kind,.002)(u,v) for u,v in circle(.109,n)]
                obj=b.poly('compact_lamp_skin_return_v12',skin+seat,
                    [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)],'blue',normal=(end,0,0))
                # Retain sharp surface normals: no inflated blue torus/cylinder.
                obj['detail_v12_component']='compact_outer_lamp_return'
            b.sheet('lower_lamp_back_v12',circle(.106),mapper(end,side,kind,.003),'graphite',.006,normal)
            rim=b.rim('lower_lamp_bezel_v12',circle(.109),circle(.086),mapper(end,side,kind,.028),'metal',.026,normal)
            b.tag(rim,'front_white_fixture' if kind=='white' else 'corner_red_fixture')
            b.sheet('lower_reflector_v12',circle(.085),mapper(end,side,kind,.012),'metal',axis=normal)
            b.glass('lower_lamp_lens_v12',circle(.085),mapper(end,side,kind,.030),normal,'lamp_glass')
            if b.lod==0:
                for a in (45,135,225,315):
                    u=.098*math.cos(math.radians(a)); v=.098*math.sin(math.radians(a))
                    p=Vector(mapper(end,side,kind,.029)(u,v))
                    b.rod('lower_bezel_screw_v12',p,p+normal*.003,.0035,'spring_steel')
                if kind=='red':
                    for rr in (.030,.048,.066,.080):
                        b.rim('aux_optic_annulus_v12',circle(rr,40),circle(rr-.0015,40),mapper(end,side,kind,.016),'spring_steel',.001,normal)
                    for i in range(16):
                        a=i*math.tau/16
                        b.rod('aux_optic_radial_v12',mapper(end,side,kind,.017)(.022*math.cos(a),.022*math.sin(a)),
                              mapper(end,side,kind,.017)(.078*math.cos(a),.078*math.sin(a)),.0008,'metal')


def make_lamps(b,end):
    make_upper_lamps(b,end)
    lower_lamps(b,end)
