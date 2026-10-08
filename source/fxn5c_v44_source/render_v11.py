"""Front-only review cameras plus basic glass, running gear and light regression."""
from render_v04 import render_preview as render_base

FRONT_VIEWS=[
    ("emblem_front",(20,0,2.16),1.05,(11.04,0,2.16)),
    ("emblem_oblique",(14,-2,2.65),1.10,(11.04,0,2.16)),
    ("corner_profile",(11.8,-8,2.18),1.35,(10.97,-1.37,2.10)),
    ("lamp_axes_front",(20,0,2.04),3.65,(11.04,0,2.04)),
    ("nose_fold",(15,-7,3.20),2.30,(10.68,-1.25,2.08)),
    ("front_straight",(25,0,2.4),8.4,(10.6,0,2.4)),
    ("front_threequarter",(17,-9,5.8),5.7,(10.0,0,2.65)),
    ("front_opposite",(-17,-9,5.8),5.7,(-10.0,0,2.65)),
    ("corner_lamps",(15,-8,2.65),2.9,(10.6,-.55,2.12)),
    ("headlamp_recess",(15,-2.9,4.9),1.55,(10.18,0,4.27)),
    ("pilot_plan",(14,-4,6),3.9,(11.25,0,.90)),
    ("coupler_detail",(13.4,-1.8,2.0),1.28,(11.38,0,1.035)),
    ("coupler_other_side",(13.4,1.8,1.7),1.28,(11.38,0,1.035)),
    ("coupler_top",(11.6,0,5),1.05,(11.37,0,1.02)),
    ("pilot_side",(11.9,-8,1.10),2.0,(11.08,0,.74)),
]

def render_preview(gen):
    return render_base(gen,"v11",FRONT_VIEWS)
