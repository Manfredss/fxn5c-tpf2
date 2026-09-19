"""Build native Transport Fever 2 mesh/model resources from the procedural FXN5C scene.

Run with Blender in background mode.  The exporter intentionally duplicates triangle
corners, which makes the binary layout simple and robust for this first playable build.
"""

from collections import OrderedDict
import os
import re
import struct
import sys
import json

import bpy
from mathutils import Matrix, Vector


ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import generate_fxn5c as gen  # noqa: E402


MOD_ROOT = os.path.join(ROOT, "staging", "codex_fxn5c_1")
MESH_DIR = os.path.join(MOD_ROOT, "res", "models", "mesh", "vehicle", "train", "fxn5c")
MODEL_DIR = os.path.join(MOD_ROOT, "res", "models", "model", "vehicle", "train")
IDENTITY = Matrix.Identity(4)
LIGHT_NAMES = ("headlights_fwd", "taillights_fwd", "headlights_bwd", "taillights_bwd")
RESOURCE_KEY = "fxn5c"
MODEL_STEM = "fxn5c"
DESCRIPTION_KEY = "VEHICLE_FXN5C"
VEHICLE_NUMBER = '0051'
AVAILABILITY_YEAR = 2024
GROUP_FILE = ''
CONNECTION_ROLES = {"body_A": "body_bracket", "rod": "longitudinal_rod", "arm_B": "bogie_arm"}
CONNECTION_PATTERN = re.compile(r"conn17_(body_A|rod|arm_B)_b([12])_s([pm])")


def connection_objects(objects, lod):
    """Reject unclassified/merged connection objects before body baking."""
    result = []
    for obj in objects:
        if not obj.name.startswith("conn17_") and not obj.get("connection_role"):
            continue
        match = CONNECTION_PATTERN.fullmatch(obj.name)
        if not match:
            raise RuntimeError("Invalid v19 connection object: " + obj.name)
        part, bogie, side = match.groups()
        bogie = int(bogie)
        expected_parent = f"b{bogie}_grp" if part == "arm_B" else "RootNode"
        actual_parent = obj.parent.name if obj.parent else "RootNode"
        if (obj.get("connection_role") != CONNECTION_ROLES[part]
                or obj.get("connection_bogie") != bogie
                or obj.get("connection_side") != (1 if side == "p" else -1)
                or actual_parent != expected_parent):
            raise RuntimeError(f"Invalid role/parent metadata for {obj.name}: {actual_parent}")
        result.append(obj)
    expected = {f"conn17_{part}_b{bogie}_s{side}"
                for part in CONNECTION_ROLES for bogie in (1, 2) for side in ("p", "m")} if lod < 2 else set()
    if {obj.name for obj in result} != expected:
        raise RuntimeError(f"LOD{lod}: connection names mismatch: {[o.name for o in result]}")
    return sorted(result, key=lambda obj: obj.name)


def select_variant(jinwen=False):
    global RESOURCE_KEY, MODEL_STEM, DESCRIPTION_KEY, MESH_DIR
    RESOURCE_KEY = "fxn5c_jinwen" if jinwen else "fxn5c"
    MODEL_STEM = RESOURCE_KEY
    DESCRIPTION_KEY = "VEHICLE_FXN5C_JINWEN" if jinwen else "VEHICLE_FXN5C"
    MESH_DIR = os.path.join(MOD_ROOT, "res", "models", "mesh", "vehicle", "train", RESOURCE_KEY)


def select_vehicle(row):
    global MODEL_STEM, DESCRIPTION_KEY, VEHICLE_NUMBER, AVAILABILITY_YEAR, GROUP_FILE
    from roster_v21 import description_key, group_stem
    select_variant(row['jinwen'])
    MODEL_STEM = row['stem']; DESCRIPTION_KEY = description_key(row)
    VEHICLE_NUMBER = row['number']; AVAILABILITY_YEAR = 2025 if row['jinwen'] else 2024
    GROUP_FILE = 'vehicle/train/'+group_stem(row)+'.mdl'


def export_signage(lod):
    if lod >= 2:
        return None
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.get('livery21_variable')]
    if not objects:
        raise RuntimeError('Missing v21 variable vehicle markings')
    name = f'signage_{VEHICLE_NUMBER}_lod{lod}'
    mats, vertices, triangles = export_mesh(name, [(o,o.matrix_world.copy()) for o in sorted(objects,key=lambda o:o.name)])
    return dict(mesh_name=name,materials=mats,vertices=vertices,triangles=triangles)


def fmt_number(value):
    value = float(value)
    if abs(value) < 1.0e-8:
        value = 0.0
    return f"{value:.8g}"


def tf_matrix(matrix):
    # Transport Fever stores transforms as a column-major flattened 4x4 matrix.
    values = [matrix[row][col] for col in range(4) for row in range(4)]
    return "{ " + ", ".join(fmt_number(value) for value in values) + ", }"


def material_path(material):
    if material is None:
        return "vehicle/train/fxn5c/dark.mtl"
    name = material.name.lstrip("/")
    return name if name.endswith(".mtl") else name + ".mtl"


def mesh_geometry(items):
    """Return one shared attribute store and one index list per material."""
    positions = []
    uv0 = []
    normals = []
    tangents = []
    groups = OrderedDict()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    for obj, transform in items:
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            has_tangents=False
            if mesh.uv_layers.active:
                try:
                    mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
                    has_tangents=True
                except RuntimeError:
                    pass
            normal_matrix = transform.to_3x3().inverted().transposed()
            uv_data = mesh.uv_layers.active.data if mesh.uv_layers.active else None
            for tri in mesh.loop_triangles:
                mat_index = tri.material_index
                material = mesh.materials[mat_index] if mat_index < len(mesh.materials) else None
                mat = material_path(material)
                indices = groups.setdefault(mat, [])

                tri_positions = [transform @ mesh.vertices[mesh.loops[loop].vertex_index].co for loop in tri.loops]
                normal = (tri_positions[1] - tri_positions[0]).cross(tri_positions[2] - tri_positions[0])
                if normal.length_squared < 1.0e-16:
                    normal = Vector((0.0, 0.0, 1.0))
                else:
                    normal.normalize()
                reference = Vector((0.0, 0.0, 1.0)) if abs(normal.z) < 0.92 else Vector((0.0, 1.0, 0.0))
                tangent = reference.cross(normal)
                if tangent.length_squared < 1.0e-16:
                    tangent = Vector((1.0, 0.0, 0.0))
                else:
                    tangent.normalize()

                for corner, loop in enumerate(tri.loops):
                    # Keep the smooth per-corner normals of turned wheels, coils
                    # and pipes. Flat faces retain their geometric normals.
                    if obj.get('explicit_planar_shading_v13'):
                        normal=normal_matrix@tri.normal
                    else:
                        normal = normal_matrix @ mesh.corner_normals[loop].vector
                    if normal.length_squared < 1.0e-16:
                        normal = Vector((0, 0, 1))
                    normal.normalize()
                    reference = Vector((0, 0, 1)) if abs(normal.z) < .92 else Vector((0, 1, 0))
                    tangent = reference.cross(normal).normalized()
                    handedness=1.0
                    if has_tangents:
                        candidate=transform.to_3x3() @ mesh.loops[loop].tangent
                        candidate-=normal*candidate.dot(normal)
                        if candidate.length_squared>1e-12:
                            # Reconstruct via cross products to avoid amplifying
                            # float32 cancellation on nearly parallel UV tangents.
                            bitangent=normal.cross(candidate)
                            if bitangent.length_squared>1e-12:
                                tangent=bitangent.cross(normal).normalized()
                            handedness=mesh.loops[loop].bitangent_sign
                    index = len(positions)
                    positions.append(tuple(tri_positions[corner]))
                    if uv_data:
                        uv = uv_data[loop].uv
                        uv0.append((float(uv.x), float(uv.y)))
                    else:
                        uv0.append((0.5, 0.5))
                    normals.append(tuple(normal))
                    tangents.append((float(tangent.x), float(tangent.y), float(tangent.z), float(handedness)))
                    indices.append(index)
        finally:
            eval_obj.to_mesh_clear()

    if not positions:
        raise RuntimeError("No triangles were available for export")
    return positions, uv0, normals, tangents, groups


def pack_vectors(vectors, components):
    output = bytearray()
    pattern = "<" + "f" * components
    for vector in vectors:
        output.extend(struct.pack(pattern, *vector))
    return output


def export_mesh(filename, items, joint_weights=None, material_mapper=None):
    positions, uv0, normals, tangents, groups = mesh_geometry(items)
    if material_mapper:
        groups = OrderedDict((material_mapper(mat), indices) for mat, indices in groups.items())

    position_blob = pack_vectors(positions, 3)
    uv_blob = pack_vectors(uv0, 2)
    normal_blob = pack_vectors(normals, 3)
    tangent_blob = pack_vectors(tangents, 4)
    joint_blob = b""
    if joint_weights is not None:
        weights = [joint_weights(p) for p in positions]
        joint_blob = pack_vectors(weights, 4)
    blob = bytearray(position_blob + uv_blob + normal_blob + tangent_blob + joint_blob)

    submeshes = []
    index_offset = len(blob)
    for mat, indices in groups.items():
        index_blob = bytearray()
        for index in indices:
            index_blob.extend(struct.pack("<I", index))
        count = len(index_blob)
        blob.extend(index_blob)
        submeshes.append((mat, count, index_offset))
        index_offset += count

    position_offset = 0
    uv_offset = len(position_blob)
    normal_offset = uv_offset + len(uv_blob)
    tangent_offset = normal_offset + len(normal_blob)

    lines = ["function data()", "return {", "  subMeshes = {"]
    for _, count, offset in submeshes:
        lines.extend([
            "    {",
            "      indices = {",
            f"        normal = {{ count = {count}, offset = {offset}, }},",
            f"        position = {{ count = {count}, offset = {offset}, }},",
            f"        tangent = {{ count = {count}, offset = {offset}, }},",
            f"        uv0 = {{ count = {count}, offset = {offset}, }},",
            *([f"        jointWeights = {{ count = {count}, offset = {offset}, }},"] if joint_blob else []),
            "      },",
            "    },",
        ])
    lines.extend([
        "  },",
        "  vertexAttr = {",
        f"    normal = {{ count = {len(normal_blob)}, numComp = 3, offset = {normal_offset}, }},",
        f"    position = {{ count = {len(position_blob)}, numComp = 3, offset = {position_offset}, }},",
        f"    tangent = {{ count = {len(tangent_blob)}, numComp = 4, offset = {tangent_offset}, }},",
        f"    uv0 = {{ count = {len(uv_blob)}, numComp = 2, offset = {uv_offset}, }},",
        *([f"    jointWeights = {{ count = {len(joint_blob)}, numComp = 4, offset = {tangent_offset + len(tangent_blob)}, }},"] if joint_blob else []),
        "  },",
        "}",
        "end",
        "",
    ])

    os.makedirs(MESH_DIR, exist_ok=True)
    msh_path = os.path.join(MESH_DIR, filename + ".msh")
    with open(msh_path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines))
    with open(msh_path + ".blob", "wb") as stream:
        stream.write(blob)
    return list(groups.keys()), len(positions), sum(len(indices) // 3 for indices in groups.values())


def mesh_node(name, mesh, materials, transform=IDENTITY, indent="        "):
    mats = " ".join(f'"{path}",' for path in materials)
    return "\n".join([
        indent + "{",
        indent + f"  materials = {{ {mats} }},",
        indent + f'  mesh = "vehicle/train/{RESOURCE_KEY}/{mesh}.msh",',
        indent + f'  name = "{name}",',
        indent + f"  transf = {tf_matrix(transform)},",
        indent + "},",
    ])


def group_node(name, children, transform=IDENTITY, indent="        "):
    return "\n".join([
        indent + "{",
        indent + "  children = {",
        *children,
        indent + "  },",
        indent + f'  name = "{name}",',
        indent + f"  transf = {tf_matrix(transform)},",
        indent + "},",
    ])


def export_lod(lod, rebuild=True):
    if rebuild:
        gen.build_model(lod)
    objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and "|bounding_box" not in obj.name]
    wheels = {obj.name: obj for obj in objects if re.fullmatch(r"w[1-6]", obj.name)}
    frames = [bpy.data.objects[f"b{i}"] for i in (1, 2)]
    lights = {name: bpy.data.objects.get(name) for name in LIGHT_NAMES}
    extra = [obj for obj in objects if obj.name == "cab_interior" or obj.name.startswith("glazing_")]
    connections = connection_objects(objects, lod)
    variable = {o for o in objects if o.get('livery21_variable')}
    excluded = set(wheels.values()) | set(frames) | set(extra) | set(connections) | variable | {obj for obj in lights.values() if obj is not None}
    body_objects = [obj for obj in objects if obj not in excluded]

    body_materials, body_vertices, body_triangles = export_mesh(
        f"body_lod{lod}", [(obj, obj.matrix_world.copy()) for obj in body_objects]
    )
    result = {
        "body_materials": body_materials,
        "body_vertices": body_vertices,
        "body_triangles": body_triangles,
        "wheel_materials": None,
        "wheel_transforms": [],
        "bogie_transforms": [],
        "light_materials": {},
        "frame_materials": None,
        "extra_meshes": [],
        "connections": [],
        "signage": export_signage(lod),
        "frame_variants": [],
    }

    if True:  # All LODs now retain six wheelsets and two independently pivoting frames.
        if len(wheels) != 6:
            raise RuntimeError(f"LOD{lod}: expected 6 wheelsets, got {sorted(wheels)}")
        # Bake the cylinder's orientation into the shared wheel mesh.  The node
        # transforms then contain translations only, matching the vanilla axle setup.
        wheel_basis = wheels["w1"].matrix_local.to_3x3().to_4x4()
        wheel_materials, _, _ = export_mesh(f"wheelset_lod{lod}", [(wheels["w1"], wheel_basis)])
        result["wheel_materials"] = wheel_materials
        result["wheel_transforms"] = [
            Matrix.Translation(wheels[f"w{index}"].matrix_local.translation) for index in range(1, 7)
        ]
        result["bogie_transforms"] = [
            bpy.data.objects["b1_grp"].matrix_world.copy(),
            bpy.data.objects["b2_grp"].matrix_world.copy(),
        ]
        for frame_index, frame in enumerate(frames):
            frame_basis = result['bogie_transforms'][frame_index].inverted() @ frame.matrix_world
            mesh_name = f'bogie_frame_b{frame_index+1}_lod{lod}'
            frame_materials, _, _ = export_mesh(mesh_name, [(frame, frame_basis)])
            result['frame_variants'].append(dict(mesh_name=mesh_name, materials=frame_materials))
        result['frame_materials'] = result['frame_variants'][0]['materials']
    if lod < 2:
        for obj in connections:
            bogie = int(obj["connection_bogie"])
            role = obj["connection_role"]
            parent = f"b{bogie}_grp" if role == "bogie_arm" else "RootNode"
            parent_world = bpy.data.objects[parent].matrix_world if parent != "RootNode" else IDENTITY
            tf = parent_world.inverted() @ obj.matrix_world
            mesh_name = f"{obj.name}_lod{lod}"
            mats, vertices, triangles = export_mesh(mesh_name, [(obj, IDENTITY)])
            anchors = {key: list(obj[key]) for key in obj.keys() if key.startswith("conn_")
                       and key.endswith("_world")}
            dimensions = {key: float(obj[key]) for key in obj.keys() if key.startswith("conn_")
                          and key.endswith(("_radius", "_tolerance"))}
            result["connections"].append({
                "name": obj.name, "mesh_name": mesh_name, "materials": mats,
                "transform": tf, "parent": parent, "role": role, "bogie": bogie,
                "side": int(obj["connection_side"]), "vertices": vertices,
                "triangles": triangles, "anchors": anchors, "dimensions": dimensions,
                "source_world": obj.matrix_world.copy(),
            })
        from dynamic_skin_v20 import export_rod_skin
        result["rod_skin"] = export_rod_skin(sys.modules[__name__], connections, result, lod)
        for name in LIGHT_NAMES:
            obj = lights[name]
            if obj is None:
                raise RuntimeError(f"LOD{lod}: missing {name}")
            mats, _, _ = export_mesh(f"{name}_lod{lod}", [(obj, obj.matrix_world.copy())])
            result["light_materials"][name] = mats
        for obj in sorted(extra,key=lambda o:o.name):
            name=f"{obj.name}_lod{lod}"
            # Put each pane origin at its centre for transparent draw sorting.
            center=sum((obj.matrix_world @ v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
            tf=Matrix.Translation(center)
            mats,_,_=export_mesh(name,[(obj,tf.inverted() @ obj.matrix_world)])
            result["extra_meshes"].append((obj.name,name,mats,tf))
    return result


def config_block(lod, exported, detailed=True):
    if detailed:
        axle = f'"vehicle/train/{RESOURCE_KEY}/wheelset_lod{lod}.msh",'
        fake_bogies = "{ }"
        part_lines = [f"        {key} = {{ {exported['node_indices'][name]}, }},"
                      for key, name in (("backBackwardParts", "taillights_bwd"),
                                        ("backForwardParts", "taillights_fwd"),
                                        ("frontBackwardParts", "headlights_bwd"),
                                        ("frontForwardParts", "headlights_fwd"))]
    else:
        axle = f'"vehicle/train/{RESOURCE_KEY}/wheelset_lod{lod}.msh",'
        fake_bogies = "{ }"
        part_lines = [
            "        backBackwardParts = { },",
            "        backForwardParts = { },",
            "        frontBackwardParts = { },",
            "        frontForwardParts = { },",
        ]
    lines = [
        "      {",
        f"        axles = {{ {axle} }},",
        *part_lines,
        "        blinkLightsLeft0 = { },",
        "        blinkLightsLeft1 = { },",
        "        blinkLightsRight0 = { },",
        "        blinkLightsRight1 = { },",
        "        blinkingLights0 = { },",
        "        blinkingLights1 = { },",
        "        brakeLights = { },",
        f"        fakeBogies = {fake_bogies},",
        "        innerBackwardParts = { },",
        "        innerForwardParts = { },",
        "      },",
    ]
    return "\n".join(lines)


def lod_block(lod, exported, visible_from, visible_to):
    children = [mesh_node("body", f"body_lod{lod}", exported["body_materials"])]
    # Index the exact emitted DFS sequence, rather than assuming fixed lamp IDs.
    dfs_names = ["RootNode", "body"]
    gear_children = []
    if lod < 2:
        dfs_names.append("running_gear_skin")
    if True:
        for bogie_index, bogie_transform in enumerate(exported["bogie_transforms"], start=1):
            dfs_names.extend((f"b{bogie_index}_grp", f"b{bogie_index}"))
            frame = exported['frame_variants'][bogie_index-1]
            wheel_nodes = [mesh_node(f"b{bogie_index}", frame['mesh_name'],
                           frame['materials'], indent="            ")]
            for local_index in range(3):
                wheel_index = (bogie_index - 1) * 3 + local_index + 1
                dfs_names.append(f"w{wheel_index}")
                wheel_nodes.append(
                    mesh_node(
                        f"w{wheel_index}",
                        f"wheelset_lod{lod}",
                        exported["wheel_materials"],
                        exported["wheel_transforms"][wheel_index - 1],
                        indent="            ",
                    )
                )
            for conn in exported["connections"]:
                if conn["parent"] == f"b{bogie_index}_grp":
                    wheel_nodes.append(mesh_node(conn["name"], conn["mesh_name"], conn["materials"],
                                                 conn["transform"], indent="            "))
                    dfs_names.append(conn["name"])
            gear_children.append(group_node(f"b{bogie_index}_grp", wheel_nodes, bogie_transform))
    if lod < 2:
        skin=exported["rod_skin"]
        mats=" ".join(f'"{path}",' for path in skin["materials"])
        children.append("\n".join([
            "        {", "          children = {", *gear_children, "          },",
            '          name = "running_gear_skin",',
            f'          skin = "vehicle/train/{RESOURCE_KEY}/{skin["mesh_name"]}.msh",',
            f"          skinMaterials = {{ {mats} }},",
            f"          transf = {tf_matrix(IDENTITY)},", "        },",
        ]))
    else:
        children.extend(gear_children)
    if lod < 2:
        for name in LIGHT_NAMES:
            children.append(mesh_node(name, f"{name}_lod{lod}", exported["light_materials"][name]))
            dfs_names.append(name)
        for name,mesh,mats,tf in exported["extra_meshes"]:
            children.append(mesh_node(name,mesh,mats,tf))
            dfs_names.append(name)
        for conn in exported["connections"]:
            if conn["parent"] == "RootNode" and conn["role"] != "longitudinal_rod":
                children.append(mesh_node(conn["name"], conn["mesh_name"], conn["materials"], conn["transform"]))
                dfs_names.append(conn["name"])
    if exported.get('signage'):
        signage = exported['signage']
        children.append(mesh_node('vehicle_markings', signage['mesh_name'], signage['materials']))
        dfs_names.append('vehicle_markings')
    if len(dfs_names) != len(set(dfs_names)):
        raise RuntimeError("Duplicate exported node names")
    exported["node_indices"] = {name: index for index, name in enumerate(dfs_names)}
    body = "\n".join(children)
    return "\n".join([
        "    {",
        "      node = {",
        "        children = {",
        body,
        "        },",
        '        name = "RootNode",',
        f"        transf = {tf_matrix(IDENTITY)},",
        "      },",
        "      static = false,",
        f"      visibleFrom = {visible_from},",
        f"      visibleTo = {visible_to},",
        "    },",
    ])


def write_model(exports):
    from roof_details_v07 import EXHAUST_OUTLETS
    # Keep visible outlets and native smoke origins driven by the same constants.
    emitters = "\n".join(f'''        {{
          child = 1,
          color = {{ 0.18, 0.18, 0.20, }},
          frequency = 19,
          initialAlpha = 0.22,
          lifeTime = 1.6,
          position = {{ {x}, {y}, {z}, }},
          size01 = {{ 0.26, 3.4, }},
          velocity = {{ 0, 0, 6, }},
          velocityDampingFactor = 2.5,
        }},''' for x,y,z in EXHAUST_OUTLETS)
    lods = "\n".join([
        lod_block(0, exports[0], 0, 120),
        lod_block(1, exports[1], 120, 420),
        lod_block(2, exports[2], 420, 3000),
    ])
    configs = "\n".join([config_block(0, exports[0]), config_block(1, exports[1]),
                          config_block(2, exports[2], detailed=False)])
    model = f'''function data()
return {{
  boundingInfo = {{
    bbMax = {{ 11.85, 1.78, 4.9, }},
    bbMin = {{ -11.85, -1.78, -0.035, }},
  }},
  collider = {{
    params = {{ halfExtents = {{ 11.75, 1.68, 2.45, }}, }},
    transf = {{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 2.45, 1, }},
    type = "BOX",
  }},
  lods = {{
{lods}
  }},
  metadata = {{
    availability = {{ yearFrom = {AVAILABILITY_YEAR}, yearTo = 0, }},
    cost = {{ price = -1, priceScale = 1, }},
    description = {{ description = _("{DESCRIPTION_KEY}_DESC"), name = _("{DESCRIPTION_KEY}_NAME"), }},
    emission = {{ idleEmission = -1, powerEmission = -1, speedEmission = -1, }},
    maintenance = {{ lifespan = 36525, runningCostScale = 1, runningCosts = -1, }},
    particleSystem = {{
      emitters = {{
{emitters}
      }},
    }},
    railVehicle = {{
      blinkInterval = 500,
      configs = {{
{configs}
      }},
      engines = {{ {{ power = 3530, tractiveEffort = 580, type = "DIESEL", }}, }},
      soundSet = {{ horn = "", name = "train_diesel", }},
      topSpeed = 33.333333,
      weight = 150,
    }},
    seatProvider = {{
      crewModels = {{ }},
      drivingLicense = "RAIL",
      seats = {{
        {{ animation = "driving_upright", crew = true, forward = true, group = 1, transf = {{ 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 9.78, -0.48, 2.30, 1, }}, }},
        {{ animation = "driving_upright", crew = true, forward = false, group = 1, transf = {{ -1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1, 0, -9.78, 0.48, 2.30, 1, }}, }},
      }},
    }},
    transportVehicle = {{
      carrier = "RAIL",
      compartmentsList = {{ {{ loadConfigs = {{ {{ cargoEntries = {{ }}, toHide = {{ }}, }}, }}, }}, }},
      groupFileName = "{GROUP_FILE}",
      loadSpeed = 1,
      multipleUnitOnly = false,
      reversible = true,
    }},
    versioning = {{ __version = "_v04", }},
  }},
  version = 1,
}}
end
'''
    os.makedirs(MODEL_DIR, exist_ok=True)
    path = os.path.join(MODEL_DIR, MODEL_STEM + ".mdl")
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(model)
    manifest = {
        "schema_version": 2, "model_stem": MODEL_STEM,
        "scope": "native dual-anchor skinning visual approximation; not rigid mechanical IK; not tested in game",
        "rod_motion": "native-dual-end-skinning",
        "estimated_dimensions": True,
        "dynamic_approximation": "Rigid A eye follows carbody, rigid B eye follows actual bogie; blended shaft may bend and change length. No fabricated yaw event, fake bogie, or Blender-only animation.",
        "lods": [],
    }
    for lod, exported in enumerate(exports):
        entries = []
        for conn in exported["connections"]:
            entry = {key: value for key, value in conn.items() if key not in {"transform", "source_world"}}
            entry["mesh"] = f"vehicle/train/{RESOURCE_KEY}/{conn['mesh_name']}.msh"
            for key in ("transform", "source_world"):
                entry[key] = [float(conn[key][row][col]) for col in range(4) for row in range(4)]
            if conn["role"] == "longitudinal_rod":
                entry["native_index"] = exported["node_indices"]["running_gear_skin"]
                entry["native_node"] = "running_gear_skin"
                entry["rest_geometry_mesh"] = entry["mesh"]
                entry["skin_mesh"] = f"vehicle/train/{RESOURCE_KEY}/{exported['rod_skin']['mesh_name']}.msh"
                entry["skin_binding"] = exported["rod_skin"]["rods"][conn["name"]]
            else:
                entry["native_index"] = exported["node_indices"][conn["name"]]
            entries.append(entry)
        manifest["lods"].append({"lod": lod, "connections": entries,
                                  "node_indices": exported["node_indices"],
                                  "rod_skin": exported.get("rod_skin")})
    manifest_path = os.path.join(ROOT, f"connection_manifest_v21_{MODEL_STEM}.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
    return path


def main():
    exports = []
    for lod in (0, 1, 2):
        exports.append(export_lod(lod))
        print(
            f"LOD{lod}: {exports[-1]['body_vertices']} body vertices, "
            f"{exports[-1]['body_triangles']} body triangles"
        )
    model_path = write_model(exports)
    print("MODEL=" + model_path)


if __name__ == "__main__":
    main()
