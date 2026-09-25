"""Native Transport Fever 2 dual-end *visual* skinning, not rigid linkage IK.

The game's shipped skinning shader decodes each float influence as
int(value) + fractionalWeight * (1/.999).  Bone IDs are the local DFS
indices beneath the node carrying ``skin``.  The rest transforms are bound
by the engine, as in its cow, windsock and bridge models.  No custom
shader, timer animation, fake bogie, or singular bind matrix is used.
"""
from pathlib import Path
import math
import struct

SKIN_NODE = "running_gear_skin"
WEIGHT_SUM = .999
A_RIGID_ZONE = .080
B_RIGID_ZONE = .125
SKELETON = [SKIN_NODE]
for _i in (1, 2):
    SKELETON += [f"b{_i}_grp", f"b{_i}"]
    SKELETON += [f"w{j}" for j in range((_i-1)*3+1, _i*3+1)]
    SKELETON += [f"conn17_arm_B_b{_i}_s{s}" for s in ("m", "p")]
BOGIE_JOINTS = {i: SKELETON.index(f"b{i}_grp") for i in (1, 2)}
assert len(SKELETON) == 15 and max(BOGIE_JOINTS.values()) < 40


def weight_at(point, a, b):
    d = [b[k]-a[k] for k in range(3)]
    length = math.sqrt(sum(x*x for x in d))
    dist = sum((point[k]-a[k])*d[k] for k in range(3))/length
    return max(0., min(1., (dist-A_RIGID_ZONE)/(length-A_RIGID_ZONE-B_RIGID_ZONE)))


def pack_weight(w, bogie):
    """Four float channels, two distinct joints plus rounding compensation."""
    joint = BOGIE_JOINTS[bogie]
    # Correct the *stored float32* fractional total, not just Python doubles.
    # Otherwise bone 8+.999 loses ~4e-7 total weight, which produces visible
    # world-coordinate drift far from map origin. Tiny rounding compensation
    # goes to the body joint and is far below an eye's geometric tolerance.
    f32=lambda x: struct.unpack('<f',struct.pack('<f',x))[0]
    w=max(0.,min(1.,w))
    encoded_b=f32(joint+w*WEIGHT_SUM) if w else 0.
    actual_b=encoded_b-math.floor(encoded_b)
    remaining=WEIGHT_SUM-actual_b
    encoded_a=f32(max(0.,remaining))
    if encoded_a>remaining:
        bits=struct.unpack('<I',struct.pack('<f',encoded_a))[0]
        encoded_a=struct.unpack('<f',struct.pack('<I',bits-1))[0]
    correction=f32(max(0.,remaining-encoded_a))
    return (encoded_a,encoded_b,correction,0.)


def annotate_source():
    """Call before saving a Blender source; runtime follows native skin data."""
    import bpy
    for obj in bpy.context.scene.objects:
        if obj.get('connection_role'):
            obj['dynamic_approximation'] = 'native dual-end skinning visual approximation; body A fixed, B arm bogie-owned; not rigid IK'
        if obj.get('connection_role') == 'longitudinal_rod':
            obj['dynamic_approximation'] = 'native dual-end skinning; shaft bends/changes length; not rigid IK'
            obj['native_skin_node'] = SKIN_NODE
            obj['native_A_rigid_zone'] = A_RIGID_ZONE
            obj['native_B_rigid_zone'] = B_RIGID_ZONE
    bpy.context.scene['connection17_native_motion'] = 'native dual-end skinning visual approximation; game curve test pending'


def export_rod_skin(exporter, connections, exported, lod):
    """Export only our original rod meshes; retain independent rest meshes for QA."""
    from mathutils import Matrix
    rods = [obj for obj in connections if obj.get('connection_role') == 'longitudinal_rod']
    assert len(rods) == 4
    specs = {}
    for obj in rods:
        specs[obj.name] = {
            'A': list(obj['conn_anchor_A_world']),
            'B': list(obj['conn_anchor_B_world']),
            'bogie': int(obj['connection_bogie']),
            'side': int(obj['connection_side']),
            'body_joint': 0,
            'bogie_joint': BOGIE_JOINTS[int(obj['connection_bogie'])],
            'A_rigid_zone_m': A_RIGID_ZONE,
            'B_rigid_zone_m': B_RIGID_ZONE,
            'weight_profile': 'clamped-linear-shaft; full rigid endpoint eye zones',
        }

    def weights(p):
        # Rods inhabit four disjoint body quadrants, not ambiguous nearest parts.
        matches = [s for s in specs.values() if s['A'][0]*p[0] > 0 and s['side']*p[1] > 0]
        assert len(matches) == 1
        s = matches[0]
        return pack_weight(weight_at(p, s['A'], s['B']), s['bogie'])

    def skin_material(ref):
        path = Path(exporter.MOD_ROOT)/'res/models/material'/ref
        txt = path.read_text(encoding='utf-8')
        assert '"PHYSICAL_NRML_MAP"' in txt, (ref, 'unsupported source material')
        newpath = path.with_stem(path.stem+'_skin19')
        newpath.write_text(txt.replace('"PHYSICAL_NRML_MAP"', '"SKINNING_PHYS_NRML_MAP"'), encoding='utf-8')
        return newpath.relative_to(Path(exporter.MOD_ROOT)/'res/models/material').as_posix()

    name = f'connection_rods_lod{lod}'
    mats, vertices, triangles = exporter.export_mesh(name,
        [(obj, obj.matrix_world.copy()) for obj in rods], weights, skin_material)
    annotate_source()
    return {'mesh_name': name, 'materials': mats, 'vertices': vertices,
            'triangles': triangles, 'skeleton_local_dfs': SKELETON,
            'skeleton_node': SKIN_NODE, 'native_skinning': True,
            'rigid_mechanical_IK': False, 'engine_playtest': False,
            'rods': specs}
