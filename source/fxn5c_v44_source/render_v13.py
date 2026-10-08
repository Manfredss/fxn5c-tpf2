from render_v04 import render_preview as render_base
from render_v11 import FRONT_VIEWS

EXTRA=[
    ('cab_side_ortho',(9.7,-20,3.35),4.5,(9.7,0,3.35)),
    ('cab_chamfer',(15,-7,4.6),3.8,(10.20,-.8,3.40)),
    ('cab_roof',(13,-8,11),5.7,(8.85,0,4.40)),
    ('side_opposite',(0,35,4.5),25,(0,0,2.2)),
    ('filter_detail',(4.5,-12,4),4.4,(4.5,-1.65,3.02)),
    ('roof_top',(0,0,30),24,(0,0,2.3)),
    ('roof_detail',(-3,-7,13),8.6,(-2,0,4.2)),
]

def render_preview(gen): return render_base(gen,'v13',FRONT_VIEWS+EXTRA)

