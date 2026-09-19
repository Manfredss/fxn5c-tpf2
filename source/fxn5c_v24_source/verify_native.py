"""Evaluate our native Lua tables and audit the exported, instanced geometry.

Requires lupa. Does not start the game and is not an in-game playability test.
"""
from pathlib import Path
from collections import Counter
import json
import math
import struct
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT / "runtime"))
from lupa import LuaRuntime
MOD=ROOT/"staging/codex_fxn5c_1"
RES=MOD/"res"
EXPECTED_PITCH=1.8  # Retained after the corrected wheel-circle photo fit.


def plain(value):
    if hasattr(value,"items"):
        result={k:plain(v) for k,v in value.items()}
        if result and set(result)==set(range(1,len(result)+1)):
            return [result[i] for i in range(1,len(result)+1)]
        return result
    return value


def read_lua(path):
    lua=LuaRuntime(register_eval=False)
    lua.execute("function _(s) return s end")
    lua.execute(path.read_text(encoding="utf-8"))
    return plain(lua.globals().data())


def matrix_mul(a,b):
    return [sum(a[k*4+r]*b[c*4+k] for k in range(4)) for c in range(4) for r in range(4)]


def transform(m,p):
    return [sum(m[k*4+r]*p[k] for k in range(3))+m[12+r] for r in range(3)]


def main(model_stem='fxn5c'):
    # Evaluate every generated Lua table, not only token-match the model.
    files=[p for p in MOD.rglob("*") if p.suffix in {".lua",".mdl",".msh",".mtl"}]
    for path in files:
        assert isinstance(read_lua(path),dict),path
    model=read_lua(RES/f"models/model/vehicle/train/{model_stem}.mdl")
    jinwen = model_stem == 'fxn5c_jinwen'
    meshes={}
    descriptors={}
    for path in (RES/"models/mesh").rglob("*.msh"):
        desc=read_lua(path)
        blob=Path(str(path)+".blob").read_bytes()
        attributes={}
        for name,attr in desc["vertexAttr"].items():
            assert attr["count"]%(4*attr["numComp"])==0
            assert attr["offset"]+attr["count"]<=len(blob)
            vals=struct.unpack_from("<"+str(attr["count"]//4)+"f",blob,attr["offset"])
            assert all(math.isfinite(v) for v in vals),(path,name)
            attributes[name]=list(zip(*[iter(vals)]*attr["numComp"]))
        vertex_count=len(attributes["position"])
        assert all(len(v)==vertex_count for v in attributes.values()),path
        assert all(abs(sum(v*v for v in n)-1)<1e-4 for n in attributes["normal"]),path
        for normal,tangent in zip(attributes["normal"],attributes["tangent"]):
            assert abs(sum(v*v for v in tangent[:3])-1)<1e-4,(path,"tangent length")
            assert abs(sum(n*t for n,t in zip(normal,tangent)))<1e-4,(path,"tangent orthogonality")
            assert abs(abs(tangent[3])-1)<1e-4,(path,"tangent handedness")
        tris=0
        for sub in desc["subMeshes"]:
            for name,idx in sub["indices"].items():
                assert idx["offset"]+idx["count"]<=len(blob)
                assert idx["count"]%12==0
                indices=struct.unpack_from("<"+str(idx["count"]//4)+"I",blob,idx["offset"])
                assert max(indices)<len(attributes[name]),path
            tris+=sub["indices"]["position"]["count"]//12
        ref=path.relative_to(RES/"models/mesh").as_posix()
        descriptors[ref]=desc
        meshes[ref]={"triangles":tris,"attributes":attributes,"submeshes":len(desc["subMeshes"])}

    reports=[]
    identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    external_mats=set()
    for lod_idx,lod in enumerate(model["lods"]):
        nodes=[]
        def walk(node,parent_tf,parent_index=None):
            index=len(nodes)
            tf=matrix_mul(parent_tf,node["transf"])
            nodes.append((node,tf,parent_index))
            for child in node.get("children",[]):
                walk(child,tf,index)
        walk(lod["node"],identity)
        by_name={n[0]["name"]:(i,n) for i,n in enumerate(nodes)}
        assert len(by_name)==len(nodes),"duplicate names"
        expected_connections={f"conn17_{part}_b{bogie}_s{side}"
                              for part in ("body_A","arm_B") for bogie in (1,2)
                              for side in ("p","m")} if lod_idx<2 else set()
        assert {name for name in by_name if name.startswith("conn17_")}==expected_connections
        assert {name for name in by_name if name.startswith("w") and name[1:].isdigit()}=={f"w{i}" for i in range(1,7)}
        assert {name for name in by_name if name.startswith("b") and name.endswith("_grp")}=={"b1_grp","b2_grp"}
        for bogie in (1,2):
            grpidx,grp=by_name[f"b{bogie}_grp"]
            children=grp[0]["children"]
            expected_children=[f"b{bogie}"]+[f"w{i}" for i in range((bogie-1)*3+1,bogie*3+1)]
            if lod_idx<2:
                expected_children += [f"conn17_arm_B_b{bogie}_s{side}" for side in ("m","p")]
            assert [n["name"] for n in children]==expected_children
            expected_owner='running_gear_skin' if lod_idx<2 else 'RootNode'
            assert nodes[grp[2]][0]['name']==expected_owner,"bogie group owner mismatch"
            assert abs(grp[1][12]-(6.7 if bogie==1 else -6.7))<1e-5
        for name in expected_connections:
            _,(node,_,parent_idx)=by_name[name]
            expected_parent=f"b{name.split('_b')[1][0]}_grp" if name.startswith("conn17_arm_B_") else "RootNode"
            assert nodes[parent_idx][0]["name"]==expected_parent,(name,"wrong connection parent")
            assert node["mesh"]==f"vehicle/train/{model_stem}/{name}_lod{lod_idx}.msh"
        wheel_x=[]
        for i in range(1,7):
            _,node=by_name[f"w{i}"]
            wheel_x.append(round(node[1][12],4))
            assert abs(node[1][14]-.625)<1e-5
        assert wheel_x==[8.5,6.7,4.9,-4.9,-6.7,-8.5],wheel_x
        config=model["metadata"]["railVehicle"]["configs"][lod_idx]
        assert config["axles"]==[f"vehicle/train/{model_stem}/wheelset_lod{lod_idx}.msh"]
        assert not config["fakeBogies"],"v19 does not claim verified fake-bogie linkage"
        if lod_idx<2:
            skin_idx,(skin_node,skin_tf,skin_parent)=by_name['running_gear_skin']
            assert skin_parent==0 and skin_tf==identity
            assert skin_node['skin']==f'vehicle/train/{model_stem}/connection_rods_lod{lod_idx}.msh'
            skeleton=[]
            def collect_skin(n):
                skeleton.append(n['name'])
                for c in n.get('children',[]): collect_skin(c)
            collect_skin(skin_node)
            assert len(skeleton)==15 and skeleton[1]=='b1_grp' and skeleton[8]=='b2_grp'
            weights=meshes[skin_node['skin']]['attributes']['jointWeights']
            assert len(weights)>0
            for packed in weights:
                assert len(packed)==4 and all(math.floor(v) in (0,1,8) for v in packed)
                assert abs(sum(v-math.floor(v) for v in packed)-.999)<1e-12
        if lod_idx<2:
            for key,name in {"frontForwardParts":"headlights_fwd","backForwardParts":"taillights_fwd",
                              "frontBackwardParts":"headlights_bwd","backBackwardParts":"taillights_bwd"}.items():
                assert config[key]==[by_name[name][0]],(key,config[key],by_name[name][0])
        else:
            assert all(not config[key] for key in ("frontForwardParts","backForwardParts","frontBackwardParts","backBackwardParts"))
        assert by_name["body"][0]==1
        assert all(e["child"]==by_name["body"][0] for e in model["metadata"]["particleSystem"]["emitters"])
        assert all(seat["group"]==by_name["body"][0] for seat in model["metadata"]["seatProvider"]["seats"])
        counts=Counter()
        low=[float("inf")]*3
        high=[-float("inf")]*3
        triangles=0
        for node,tf,parent in nodes:
            ref=node.get("mesh") or node.get('skin')
            if not ref:
                continue
            mesh=meshes[ref]
            node_materials=node.get('materials',node.get('skinMaterials'))
            assert len(node_materials)==mesh["submeshes"],ref
            for mat in node_materials:
                if not (RES/"models/material"/mat).exists():
                    assert mat in {"vehicle/train/emissive/train_all_lights.mtl","vehicle/train/emissive/train_red_lights.mtl"},mat
                    external_mats.add(mat)
            counts[ref]+=1
            triangles+=mesh["triangles"]
            for p in mesh["attributes"]["position"]:
                q=transform(tf,p)
                for axis in range(3):
                    low[axis]=min(low[axis],q[axis])
                    high[axis]=max(high[axis],q[axis])
        assert sum(v for k,v in counts.items() if "wheelset" in k)==6
        assert sum(v for k,v in counts.items() if "bogie_frame" in k)==2
        for axis in range(3):
            assert low[axis]>=model["boundingInfo"]["bbMin"][axis]-1e-4,(lod_idx,"min",low)
            assert high[axis]<=model["boundingInfo"]["bbMax"][axis]+1e-4,(lod_idx,"max",high)
        reports.append({"lod":lod_idx,"instanced_triangles":triangles,"nodes":len(nodes),
                        "bounds_min":low,"bounds_max":high,"mesh_instance_counts":dict(counts),"axle_x":wheel_x})
    assert reports[0]["instanced_triangles"]>reports[1]["instanced_triangles"]>reports[2]["instanced_triangles"]
    assert reports[0]["instanced_triangles"]<500000
    # v19 clips both liveries into the distant shell rather than dropping their
    # defining stripes. Measured builds remain <5k; retain a bounded 6k cap.
    assert reports[2]["instanced_triangles"]<6000
    feature_path=ROOT/"geometry_features_v20.json"
    features=json.loads(feature_path.read_text(encoding="utf-8"))
    for feature in features[:2]:
        for name,count in {"louver_bank":12,"folded_louver_blades_v05":12,"equipment_lid":12}.items():
            assert feature["body_details"]["body_detail_"+name]==count,(feature["lod"],name)
    assert not features[2]["body_details"],"High-detail carbody must not leak into distant LOD"
    assert features[0]["body_details"]["body_detail_roof_lifting_eye"]==14
    for feature in features[:2]:
        for name,count in {"angular_surround":2,"angular_front_pane":4,
                           "angle_cock":8,"air_hose":8,"end_jumper":4,"radiator_cassette":1,
                           "roof_access_lid":2,
                           "cab_aircon_unit":2}.items():
            assert feature["refinements"]["refinement_"+name]==count,(feature["lod"],name)
    assert not features[2]["refinements"],"Refinements leaked into distant LOD"
    for feature in features[:2]:
        for name,count in {"faceted_aperture_shell":1,"side_cab_door":4,
                           "trapezoid_side_pane":4,"rectangular_side_pane":4,
                           "relocated_air_reservoir":2,"relocated_reservoir_end":4,
                           "pilot_side_return":4,"pilot_corner_fold":4,
                           "trapezoid_roof_deck":2,"lateral_exhaust":2,
                           "trapezoid_vent_rib":4,"ac_lid_fan_grille":2}.items():
            assert feature["silhouette"]["silhouette_"+name]==count,(feature["lod"],name)
        assert "refinement_rectangular_exhaust" not in feature["refinements"]
        assert "refinement_arched_roof_rib" not in feature["refinements"]
    assert not features[2]["silhouette"],"Near-view parts leaked into distant LOD"
    for feature in features[:2]:
        assert feature["silhouette13"]["silhouette13_continuous_cab_hood"]==2, feature["silhouette13"]
    assert not features[2]["silhouette13"], "v13 near-view parts leaked into distant LOD"
    for frame in features[0]["frames"]:
        for name,count in {"primary_coil":12,"axlebox_housing":6,"traction_motor_casing":3,
                           "sand_pipe":4,"curved_tread_brake_shoe":12,
                           "slotted_axlebox_cradle":6,
                           "low_centre_station":2,"tall_end_station":4}.items():
            assert frame["component_"+name]==count,(name,frame)
    assert model["collider"]["transf"][14]==2.45
    emitters=model["metadata"]["particleSystem"]["emitters"]
    assert [e["position"] for e in emitters]==[[-1.7,-.76,4.675],[-1.7,.76,4.675]]
    assert all(e["frequency"]==19 for e in emitters)
    for path in (RES/"models/material/vehicle/train/fxn5c").glob("*.mtl"):
        mat=read_lua(path)
        assert mat["type"] in {"PHYSICAL_NRML_MAP","PHYS_TRANSPARENT","EMISSIVE","SKINNING_PHYS_NRML_MAP"}
        for key,val in mat["params"].items():
            if key.startswith("map_"):
                assert (RES/"textures"/val["fileName"]).exists(),val
    for lod in model["lods"][:2]:
        children=lod["node"]["children"]
        assert any(n["name"]=="cab_interior" for n in children)
        panes=[n for n in children if n["name"].startswith("glazing_")]
        assert len(panes)==26,len(panes)
        for pane in panes:
            assert len(pane["materials"])==1
            mat=read_lua(RES/"models/material"/pane["materials"][0])
            assert mat["type"]=="PHYS_TRANSPARENT"
            assert mat["params"]["alpha_test"]["sorted"] is True
    for name in ("lamp_white","lamp_red"):
        mat=read_lua(RES/f"models/material/vehicle/train/fxn5c/{name}.mtl")
        assert mat["type"]=="EMISSIVE"
        assert min(mat["params"]["emissive_scale"]["emissiveScale"])>0
    report={"status":"PASS","scope":"static native-resource verification; NOT an in-game test",
            "lua_files_evaluated":len(files),"lods":reports,"base_game_materials":sorted(external_mats),
            "detail_components_checked":True,"transparent_panes_per_detailed_lod":26,
            "dedicated_emissive_materials":2,"carbody_details":features[0]["body_details"],
            "front_roof_pipe_refinements":features[0]["refinements"],
            "silhouette_corrections":features[0]["silhouette"],
            "tangent_basis_checked":True,"game_installation_modified":False}
    (ROOT/("native_scene_jinwen.json" if jinwen else "native_scene.json")).write_text(json.dumps(model),encoding="utf-8")
    (ROOT/"native_meshes.json").write_text(json.dumps(descriptors),encoding="utf-8")
    for feature in features[:2]:
        expected={"flush_brow_vent":4,
                  "corrected_directional_light_groups":4,
                  "segmented_exhaust_lip":2}
        for name,count in expected.items():
            assert feature["evidence"]["evidence_"+name]==count,(feature["lod"],name,feature["evidence"])
    for frame in features[0]['frames']:
        assert frame['component_seated_primary_coil']==12
        assert frame['component_stepped_bogie_equipment_lid']==4
    assert not features[2]["evidence"]
    report["evidence_led_corrections"]=features[0]["evidence"]
    for feature in features[:2]:
        for name,count in {"recessed_upper_lamp_cavity":2,"flush_upper_cover":2,
                           "front_white_fixture":4,"corner_red_fixture":4,
                           "central_plough_half":4,"black_side_tread":4,
                           "janney_fixed_head":2,"janney_knuckle":2}.items():
            assert feature["front09"]["front09_"+name]==count,(feature["lod"],name)
    report["front_end_corrections"]=features[0]["front09"]
    for feature in features[:2]:
        for name,count in {'integrated_shallow_nose_shell':1,'compact_outer_lamp_return':4,
                           'vertical_filter_bank':4,'vertical_filter_insert':8,
                           'radiator_grid_fixing':14,'faceted_exhaust_duct':2,
                           'segmented_exhaust_mouth':2,'thin_anticlimber_shelf':12,'paired_roof_access_lid':2}.items():
            assert feature['production12']['production12_'+name]==count,(feature['lod'],name)
        assert not feature['front10'], 'Obsolete v10 outer adapter/shell must not survive'
        assert 'body_detail_service_skin_v05' not in feature['body_details']
    report["production_reconstruction"]=features[0]["production12"]
    report["v13_cab_hoods"]=features[0]["silhouette13"]
    for feature in features[:2]:
        assert feature["emblem11"]=={"emblem11_open_arc":2,"emblem11_rail_section":2}
        assert feature["front11"]["front11_inboard_folded_panel"]==4
        for name,count in {"nose_paint":6,"returned_nose_grip":4,"oval_grab_mount":8,"grab_mount_hex_bolt":8}.items():
            assert feature['front11']['front11_'+name]==count,(feature['lod'],name)
    report["emblem_corrections"]=features[0]["emblem11"]
    report["shallow_nose_panels"]=features[0]["front11"]
    report['variant']=model_stem
    report['feature_count_scope']='CR base build; Jinwen roof and paint audited separately'
    (ROOT/("validation_jinwen_v20.json" if jinwen else "validation_v20.json")).write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main('fxn5c_jinwen' if '--jinwen' in sys.argv else 'fxn5c')
