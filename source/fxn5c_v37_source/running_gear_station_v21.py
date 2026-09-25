"""Photo-fit bogie station correction; axle pitch is not altered.

TrainNets yl04/yl10: nose-to-step already matches, nose-to-outer axle was
about 0.30 m too short. 6.40 m is a visual fit, not a manufacturer dimension.
"""
import bpy
from mathutils import Vector,Matrix

BOGIE_CENTER = 6.40
AXLE_PITCH = 1.80
RESERVOIR_SHIFT = -.65
CABINET_RIGHT_START = .44
CABINET_OLD_END = 2.66
CABINET_NEW_END = 2.01
FUEL_POSITIVE_END = 2.00

CABINET_PARTS = ('body_equipment_case','equipment_lid_v05','equipment_flush_handle',
    'equipment_handle_recess','equipment_hasp_pin','equipment_hasps','equipment_lid_screw',
    'equipment_pressed_vent','equipment_vent_shadow')
TANK_PARTS = ('air_reservoir','reservoir_domed_end','reservoir_strap','reservoir_drain')


def _bounds(obj):
    points=[obj.matrix_world@v.co for v in obj.data.vertices]
    return [(min(p[i] for p in points),max(p[i] for p in points)) for i in range(3)]


def _central_equipment():
    """Move a complete reservoir assembly; keep radius, mutual spacing and Y.

    The neighbouring right-hand cabinet partition is shortened uniformly, not
    only its last door. No carbody paint or upper-body geometry participates.
    """
    factor=(CABINET_NEW_END-CABINET_RIGHT_START)/(CABINET_OLD_END-CABINET_RIGHT_START)
    affine=Matrix.Diagonal((factor,1,1,1))
    affine.translation.x=CABINET_RIGHT_START*(1-factor)
    counts={'cabinet_parts':0,'tank_parts':0,'header_parts':0,'airline_vertices':0}
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        name=obj.name
        if name.startswith(CABINET_PARTS):
            bounds=_bounds(obj)
            if bounds[0][0]>.42 and bounds[0][1]<2.70:
                if obj.parent:raise RuntimeError('Unexpected cabinet parent: '+name)
                obj.matrix_world=affine@obj.matrix_world
                obj['station21_cabinet_partition']=True;counts['cabinet_parts']+=1
        elif name.startswith(TANK_PARTS):
            if obj.parent:raise RuntimeError('Unexpected tank parent: '+name)
            obj.location.x+=RESERVOIR_SHIFT
            obj['station21_reservoir_shift']=RESERVOIR_SHIFT;counts['tank_parts']+=1
        elif name.startswith('equipment20_'):
            # v20 equipment20 is exclusively the complete reservoir exterior
            # assembly: heads, welds, bosses, plugs, brackets and visible pipes.
            if obj.parent:raise RuntimeError('Unexpected reservoir fitting parent: '+name)
            obj.location.x+=RESERVOIR_SHIFT
            obj['station21_reservoir_shift']=RESERVOIR_SHIFT;counts['header_parts']+=1
        elif name.startswith('underframe_airline'):
            # The main line stays fixed over the central cabinet. Blend only
            # its final segment from X2.7 to X3.7 into the shifted header.
            matrix=obj.matrix_world.copy();inverse=matrix.inverted()
            for vertex in obj.data.vertices:
                p=matrix@vertex.co
                amount=max(0.,min(1.,(p.x-2.7)))
                if amount:
                    p.x+=RESERVOIR_SHIFT*amount;vertex.co=inverse@p;counts['airline_vertices']+=1
            obj['station21_airline_end_shift']=RESERVOIR_SHIFT
        elif name=='main_fuel_tank':
            # The separately modeled tank formerly ended at X2.20, inside
            # the shifted first reservoir. Shorten only its positive end;
            # keep the opposite end, width, height and nominal bevel intact.
            matrix=obj.matrix_world.copy();inverse=matrix.inverted()
            for vertex in obj.data.vertices:
                p=matrix@vertex.co
                if p.x>1.60:
                    p.x=1.60+(p.x-1.60)*(FUEL_POSITIVE_END-1.60)/.60
                    vertex.co=inverse@p
            obj['station21_fuel_positive_end']=FUEL_POSITIVE_END
    if bpy.data.objects.get('air_reservoir'):
        if counts['cabinet_parts']<12 or counts['tank_parts']<6 or counts['header_parts']<10:
            raise RuntimeError('Incomplete central equipment assembly: '+str(counts))
    return counts


def apply():
    # Scene properties survive gen.clear_scene(); only actual newly-created
    # bogie objects establish whether the current geometry was corrected.
    if any(bpy.data.objects[f'b{i}_grp'].get('station21_corrected') for i in (1,2)):
        raise RuntimeError('Bogie station correction must run once per scene')
    for index, sign in ((1,1),(2,-1)):
        group = bpy.data.objects[f'b{index}_grp']
        delta = sign*BOGIE_CENTER-group.matrix_world.translation.x
        matrix = group.matrix_world.copy(); matrix.translation.x += delta
        group.matrix_world = matrix
        group['station21_corrected']=True
        for obj in bpy.context.scene.objects:
            if obj.get('connection_bogie') != index:
                continue
            if obj.parent is None:
                obj.location.x += delta
            for key in list(obj.keys()):
                if key.startswith('conn_') and key.endswith('_world'):
                    point = list(obj[key]); point[0] += delta; obj[key] = point
    counts=_central_equipment()
    bpy.context.view_layer.update()
    bpy.context.scene['station21_applied'] = True
    bpy.context.scene['station21_bogie_center'] = BOGIE_CENTER
    bpy.context.scene['station21_dimension_status'] = 'photo-fit estimate; no factory dimension drawing'
    return counts
