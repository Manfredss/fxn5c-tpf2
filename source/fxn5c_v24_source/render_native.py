"""Re-import native .msh/.blob + evaluated .mdl hierarchy for visual export QA.

Run verify_native.py first, then this script with Blender --background.
The render is a Blender reconstruction of game resources, NOT a game screenshot.
"""
import json
import os
from pathlib import Path
import struct
import sys
import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen
MOD=ROOT/"staging/codex_fxn5c_1"
_SKINS=[]


def update_skin_pose(*unused):
    """Evaluate the emitted jointWeights, not a hand-authored preview rig.

    This reconstructs native skin math for QA; it is not an engine playtest.
    Called explicitly after a pose change, and just before every render.
    """
    bpy.context.view_layer.update()
    for skin in _SKINS:
        obj=skin['object']
        if obj.name not in bpy.data.objects:
            continue
        inv=obj.matrix_world.inverted()
        matrices=[inv @ bone.matrix_world @ bind for bone,bind in zip(skin['bones'],skin['inverse_bind'])]
        normal_matrices=[m.to_3x3() for m in matrices]
        for vertex,rest,influences in zip(obj.data.vertices,skin['rest'],skin['weights']):
            vertex.co=sum((weight*(matrices[joint] @ rest) for joint,weight in influences),Vector())
        normals=[]
        for rest,influences in zip(skin['normals'],skin['weights']):
            normal=sum((weight*(normal_matrices[joint] @ rest) for joint,weight in influences),Vector())
            normals.append(normal.normalized())
        obj.data.update()
        obj.data.normals_split_custom_set([normals[loop.vertex_index] for loop in obj.data.loops])


def load_native(jinwen=False, model_stem=None, lod_index=0):
    # These descriptors must come from verification of the current export.
    # Reject stale offsets explicitly rather than interpreting another blob version.
    resources=list((MOD/"res/models/mesh").rglob("*.msh*"))
    resources.extend((MOD/"res/models/model/vehicle/train").glob("*.mdl"))
    latest_resource=max(path.stat().st_mtime for path in resources)
    scene_file = f"native_scene_{model_stem}.json" if model_stem else ("native_scene_jinwen.json" if jinwen else "native_scene.json")
    for name in (scene_file,"native_meshes.json"):
        path=ROOT/name
        if not path.is_file() or path.stat().st_mtime<latest_resource:
            raise RuntimeError("Run verify_native.py to completion after export, before render_native.py")
    _SKINS.clear()
    # Native visibility probes hide five lamp instances. Operator selection
    # ignores hide_set objects, so a following model load must remove the
    # complete old cohort directly or stale gates survive under .001 names.
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj,do_unlink=True)
    assert not bpy.context.scene.objects, 'Old native cohort survived reset'
    gen.clear_scene()
    for key in gen.MATERIAL_SPECS:
        gen.material(key)
    # Mesh descriptors consist solely of literal tables. Use the independent
    # validator's JSON export so Blender needs no Lua dependency installed.
    model=json.loads((ROOT/scene_file).read_text(encoding="utf-8"))
    descriptors=json.loads((ROOT/"native_meshes.json").read_text(encoding="utf-8"))
    cache={}
    def getmesh(ref,materials):
        if ref in cache:
            return cache[ref]
        desc=descriptors[ref]
        path=MOD/"res/models/mesh"/ref
        blob=Path(str(path)+".blob").read_bytes()
        a=desc["vertexAttr"]["position"]
        vals=struct.unpack_from("<"+str(a["count"]//4)+"f",blob,a["offset"])
        verts=list(zip(*[iter(vals)]*3))
        a=desc["vertexAttr"]["normal"]
        vals=struct.unpack_from("<"+str(a["count"]//4)+"f",blob,a["offset"])
        normals=list(zip(*[iter(vals)]*3))
        a=desc["vertexAttr"]["uv0"]
        vals=struct.unpack_from("<"+str(a["count"]//4)+"f",blob,a["offset"])
        uvs=list(zip(*[iter(vals)]*2))
        faces=[]
        matindices=[]
        for i,sub in enumerate(desc["subMeshes"]):
            attr=sub["indices"]["position"]
            inds=struct.unpack_from("<"+str(attr["count"]//4)+"I",blob,attr["offset"])
            faces.extend(zip(*[iter(inds)]*3))
            matindices.extend([i]*(len(inds)//3))
        mesh=bpy.data.meshes.new(ref)
        mesh.from_pydata(verts,[],faces)
        uv_layer=mesh.uv_layers.new(name="UVMap")
        for loop in mesh.loops:
            uv_layer.data[loop.index].uv=uvs[loop.vertex_index]
        for path in materials:
            name=Path(path).stem.removesuffix('_skin19')
            if name in gen.MATERIAL_SPECS or name in gen.EMISSIVE:
                mat=gen.material(name)
            else:
                mat=gen.emissive_material(name,(1,.015,.008,1) if "red" in name else (1,.88,.65,1),2)
            mesh.materials.append(mat)
        for poly,idx in zip(mesh.polygons,matindices):
            poly.material_index=idx
            poly.use_smooth=True
        mesh.update()
        mesh.normals_split_custom_set([normals[loop.vertex_index] for loop in mesh.loops])
        cache[ref]=mesh
        return mesh
    skin_nodes=[]
    node_objects={}
    def visit(node,parent=None):
        mesh=getmesh(node["mesh"],node["materials"]) if "mesh" in node else None
        obj=bpy.data.objects.new(node["name"],mesh)
        assert obj.name==node['name'],('Native node namespace collision',node['name'],obj.name)
        bpy.context.collection.objects.link(obj)
        obj.parent=parent
        t=node["transf"]
        obj.matrix_local=Matrix([[t[c*4+r] for c in range(4)] for r in range(4)])
        node_objects[node['name']]=obj
        if 'skin' in node:
            skin_nodes.append((node,obj))
        for child in node.get("children",[]):
            visit(child,obj)
    visit(model["lods"][lod_index]["node"])
    bpy.context.view_layer.update()
    for node,root_obj in skin_nodes:
        skeleton=[]
        def flatten(n):
            skeleton.append(node_objects[n['name']])
            for c in n.get('children',[]):
                flatten(c)
        flatten(node)
        assert len(skeleton)<=40
        ref=node['skin']
        mesh=getmesh(ref,node['skinMaterials']).copy()
        obj=bpy.data.objects.new(node['name']+'_native_skin',mesh)
        assert obj.name==node['name']+'_native_skin',('Native skin namespace collision',obj.name)
        bpy.context.collection.objects.link(obj)
        obj.parent=root_obj
        obj.matrix_local=Matrix.Identity(4)
        a=descriptors[ref]['vertexAttr']['jointWeights']
        blob=Path(str(MOD/'res/models/mesh'/ref)+'.blob').read_bytes()
        vals=struct.unpack_from('<'+str(a['count']//4)+'f',blob,a['offset'])
        weights=[]
        for encoded in zip(*[iter(vals)]*4):
            influences=[(int(v),(v-int(v))/.999) for v in encoded if v-int(v)>0]
            assert all(0<=j<len(skeleton) for j,w in influences)
            weights.append(influences)
        normal_a=descriptors[ref]['vertexAttr']['normal']
        vals=struct.unpack_from('<'+str(normal_a['count']//4)+'f',blob,normal_a['offset'])
        normals=[Vector(v) for v in zip(*[iter(vals)]*3)]
        _SKINS.append({'object':obj,'bones':skeleton,'inverse_bind':[bone.matrix_world.inverted() @ root_obj.matrix_world for bone in skeleton],
                       'rest':[v.co.copy() for v in mesh.vertices], 'weights':weights,'normals':normals})
    update_skin_pose()
    expected_names=set(node_objects)|{node['name']+'_native_skin' for node,_ in skin_nodes}
    assert {obj.name for obj in bpy.context.scene.objects}==expected_names, 'Mixed native cohorts'
    if update_skin_pose not in bpy.app.handlers.render_pre:
        bpy.app.handlers.render_pre.append(update_skin_pose)


def main():
    load_native()
    from audit_cab_v14 import audit
    audit(ROOT,version="v14")
    from audit_roof_v14 import audit as roof_audit
    roof_audit(ROOT,version="v14")
    from audit_front_v14 import audit as details_audit
    details_audit(ROOT)
    from audit_emblem_v14 import audit as emblem_audit
    emblem_audit(ROOT)
    from audit_details_v14 import audit as production_audit
    production_audit(ROOT)
    if "--audit-only" in sys.argv:
        print("NATIVE ROUNDTRIP AUDITS COMPLETE (no rerender; not in-game)")
        return
    gen.PREVIEW_DIR=os.path.join(str(ROOT),"native_preview")
    gen.render_preview()
    # A separate curve-following pose tests the actual exported parent hierarchy.
    bpy.data.objects["b1_grp"].rotation_euler.z=.15
    bpy.data.objects["b2_grp"].rotation_euler.z=-.15
    cam=bpy.context.scene.camera
    cam.location=(16,-24,18)
    cam.data.ortho_scale=25
    gen.point_camera(cam,(0,0,1.8))
    bpy.context.scene.render.filepath=os.path.join(gen.PREVIEW_DIR,"bogie_pivot_test.png")
    bpy.ops.render.render(write_still=True)
    bpy.data.objects["b1_grp"].rotation_euler.z=0
    bpy.data.objects["b2_grp"].rotation_euler.z=0
    from render_reference_v08 import render as render_reference
    render_reference(gen,name="reference_0051_v14")
    print("NATIVE ROUNDTRIP RENDER COMPLETE (not in-game)")


if __name__=="__main__":
    main()
