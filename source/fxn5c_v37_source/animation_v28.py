"""Native FILE_REF matrix animation; no KEYFRAME Euler-axis assumptions.

Format: official Resource Types / .ani, and vanilla EMD SD40 g1.ani.
Matrices are column-major node-local offsets; mesh is pivot-local and node
transf supplies translation once. Sampling is illustrative, not an engine test.
"""
import math
from pathlib import Path
from animation_v26 import _base_node, _multiply_matrix

def matrix(axis,angle):
    c,s=math.cos(angle),math.sin(angle)
    if axis=='X':return [1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1]
    if axis=='Y':return [c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1]
    raise ValueError(axis)

def curve(kind,direction):
    period=1500 if kind=='fan' else 3200
    times=list(range(0,period+1,50))
    angles=[direction*(2*math.pi*t/period if kind=='fan' else
            math.radians(16)*(1-math.cos(2*math.pi*t/period))) for t in times]
    return dict(times=times,transfs=[matrix('Y' if kind=='fan' else 'X',a) for a in angles])

def make_node(part,root):
    node,_=_base_node(part['mesh'],part['materials'],part['pivot'],part['name'],True)
    kind=part['kind'];direction=part['direction']
    ref=f'vehicle/train/fxn5c_v28/{kind}_{"p" if direction>0 else "m"}.ani'
    from build_release_v24 import lua_literal
    path=Path(root)/'staging/codex_fxn5c_1/res/models/animation'/ref
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text('function data()\nreturn '+lua_literal(curve(kind,direction))+'\nend\n',encoding='utf8')
    node['animations']={'forever':{'type':'FILE_REF','params':{'id':ref}}}
    return node

def sample(node,ms,root):
    from verify_native import read_lua
    from mathutils import Matrix,Quaternion
    data=read_lua(Path(root)/'staging/codex_fxn5c_1/res/models/animation'/node['animations']['forever']['params']['id'])
    t=ms%data['times'][-1]
    for i,(a,b) in enumerate(zip(data['times'],data['times'][1:])):
        if a<=t<=b:
            matrices=[Matrix([[v[c*4+r] for c in range(4)] for r in range(4)]) for v in data['transfs'][i:i+2]]
            q=matrices[0].to_quaternion().slerp(matrices[1].to_quaternion(),(t-a)/(b-a))
            m=q.to_matrix().to_4x4()
            return _multiply_matrix(node['transf'],[m[r][c] for c in range(4) for r in range(4)])
    raise AssertionError(t)
