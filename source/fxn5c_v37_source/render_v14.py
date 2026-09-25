from render_v04 import render_preview as render_base
from render_v11 import FRONT_VIEWS
from render_v13 import EXTRA

V14_VIEWS=[
    ('cab_full_side',(9.2,-22,3.07),4.9,(9.2,0,3.07)),
    ('cab_side_other',(-9.2,22,3.07),4.9,(-9.2,0,3.07)),
    ('lamp_fold_ortho',(20,-9,2.40),3.3,(10.8,-.95,2.16)),
]

def render_preview(gen): return render_base(gen,'v14',FRONT_VIEWS+EXTRA+V14_VIEWS)
