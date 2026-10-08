"""Shared linear PBR values; geometry and native textures use the same palette."""
MATERIALS = {
    "blue": ((.009,.052,.235,1),.31,.15),
    "light_blue": ((.011,.20,.44,1),.34,.10),
    "yellow": ((.96,.57,.017,1),.36,.12),
    "dark": ((.025,.032,.041,1),.62,.25),
    "black": ((.006,.009,.013,1),.58,.0),
    "metal": ((.26,.29,.31,1),.28,.78),
    "white": ((.83,.85,.81,1),.41,.0),
    "roof": ((.041,.048,.060,1),.61,.23),
    "graphite": ((.048,.057,.063,1),.63,.36),
    "spring_steel": ((.063,.073,.081,1),.43,.58),
    "wheel_steel": ((.22,.235,.25,1),.25,.78),
    "ochre": ((.14,.10,.055,1),.68,.30),
    "glass_transparent": ((.26,.39,.40,.18),.10,.0),
    "lamp_glass": ((.60,.66,.66,.14),.08,.0),
    "cab_lining": ((.46,.48,.43,1),.76,.0),
    "cab_floor": ((.038,.044,.042,1),.89,.0),
    "console": ((.18,.235,.225,1),.62,.04),
    "seat_fabric": ((.035,.055,.075,1),.92,.0),
    "screen": ((.020,.090,.125,1),.26,.05),
    "screen_mark": ((.32,.67,.52,1),.45,.0),
    "red_paint": ((.46,.021,.012,1),.46,.12),
    "insulator": ((.045,.028,.018,1),.51,.0),
    "coupler_steel": ((.12,.095,.07,1),.62,.65),
    "cast_steel": ((.045,.049,.050,1),.72,.22),
    "grille_black": ((.007,.009,.011,1),.80,.10),
    "exhaust_steel": ((.058,.050,.041,1),.79,.32),
    "jw_white": ((.78,.79,.75,1),.44,.08),
    # v21: illustration-side target is royal blue, not the previous cyan-blue.
    # Photo lighting varies; this is a visual match, not an OEM paint standard.
    "jw_blue": ((.001,.12,.68,1),.37,.12),
    "jw_red": ((.52,.010,.048,1),.43,.06),
    "jw_roof": ((.25,.30,.34,1),.66,.20),
    "jw_frame": ((.18,.23,.255,1),.66,.32),
    "jw_spring": ((.12,.15,.16,1),.61,.38),
}
TRANSPARENT={"glass_transparent","lamp_glass"}
EMISSIVE={"lamp_white":((1,.84,.60,1),9.0),"lamp_red":((1,.009,.003,1),7.0)}
