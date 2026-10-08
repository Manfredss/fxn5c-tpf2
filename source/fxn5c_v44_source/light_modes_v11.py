"""Direction-switched FXN5C lamp emitters, independent of fixture position names.

Observed video evidence: FXN5C 0053 has white inboard lower lamps at 00:05.09
of BV1W8FNzMEGd; FXN5C 0018 has red inboard lower lamps at 00:35.65 of
BV1XjxNeoEzr. These are different locomotives. Applying their arrangement to
the model of 0051 is a cross-unit modelling inference, NOT a verification of
0051's wiring or of an actual red/white combined optical unit.

The four existing TPF2 direction/event groups are preserved. White and red
emitters share the inboard lens position but belong to mutually selected
direction groups; do not show both direction modes in a preview at once.
Outboard fixtures retain their geometry/glass but have no default emitter:
the observed gray/bright reflections do not establish an auxiliary-light
switching mode. The recessed upper white emitters remain unchanged from v10.
"""

from front_details_v10 import circle, lower_mapper


def make_emitters(b):
    """Create the four names expected by ``export_tpf2.LIGHT_NAMES``."""
    # Keep the exporter names without importing it (it imports the generator).
    groups = {name: [] for name in (
        "headlights_fwd", "taillights_fwd", "headlights_bwd", "taillights_bwd"
    )}
    for end in (-1, 1):
        head = "headlights_fwd" if end == 1 else "headlights_bwd"
        tail = "taillights_bwd" if end == 1 else "taillights_fwd"
        normal = (end, 0, 0)
        for side in (-1, 1):
            # Reuse v10's INBOARD location only, not its obsolete color mapping:
            # centre (end * 11.04, side * 1.24, 2.02), offset outward by .020 m.
            mapper = lower_mapper(end, side, "white", .020)
            for color, node in (("white", head), ("red", tail)):
                obj = b.sheet(
                    "inboard_lower_" + color + "_emitter_v11",
                    circle(.068, 32), mapper, "lamp_" + color, axis=normal,
                )
                groups[node].append(obj)

            obj = b.sheet(
                "recessed_top_emitter_v11", circle(.038, 32),
                lambda u, v: (
                    end * (b.front_x(4.27 + v) - .090),
                    side * .15 + u,
                    4.27 + v,
                ),
                "lamp_white", axis=normal,
            )
            groups[head].append(obj)

    for name, objects in groups.items():
        b.g.join_objects(objects, name)
