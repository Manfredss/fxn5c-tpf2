"""Reimport all six static native-readback FBXs and verify face/material counts."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
import sys
import bpy

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import generate_fxn5c as gen


def matkey(name):
    return re.sub(r'\.\d{3}$','',Path(name).name).removesuffix('.mtl').removesuffix('_skin19')


def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)


def main():
    desc=json.loads((ROOT/'native_meshes.json').read_text(encoding='utf-8'))
    inputs={};rows=[]
    for style,lod in ((s,l) for s in ('fxn5c','fxn5c_jinwen') for l in (0,1,2)):
        modelpath=ROOT/f'native_scene_{style}.json'
        model=json.loads(modelpath.read_text(encoding='utf-8'))
        expected=Counter()
        for node in walk(model['lods'][lod]['node']):
            field='mesh' if 'mesh' in node else 'skin' if 'skin' in node else None
            if field is None:continue
            materials=node['materials' if field=='mesh' else 'skinMaterials']
            for sub,mat in zip(desc[node[field]]['subMeshes'],materials):
                expected[matkey(mat)]+=sub['indices']['position']['count']//12
        folder='vehicle-train-fxn5c-jinwen' if style.endswith('jinwen') else 'vehicle-train-fxn5c'
        path=ROOT/'fbx_import'/folder/f'fxn5c_lod{lod}.fbx'
        gen.clear_scene()
        bpy.ops.import_scene.fbx(filepath=str(path))
        actual=Counter();meshes=0
        for obj in bpy.context.scene.objects:
            if obj.type!='MESH':continue
            meshes+=1
            obj.data.calc_loop_triangles()
            for tri in obj.data.loop_triangles:
                mat=obj.data.materials[tri.material_index]
                assert mat is not None,('missing FBX material',obj.name)
                actual[matkey(mat.name)]+=1
        assert actual==expected,(style,'FBX face/material mismatch',actual-expected,expected-actual)
        rows.append({'style':style,'lod':lod,'mesh_objects':meshes,'triangles':sum(actual.values()),
                     'material_triangle_counts':dict(actual),'exact_native_material_counts':True})
        for file in (path,modelpath,ROOT/'native_meshes.json'):
            inputs[file.relative_to(ROOT).as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
    inputs[Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report={'status':'PASS','scope':'reimported LOD0/1/2 FBX face/material counts vs current native; not game runtime',
            'models':rows,'inputs_sha256':inputs}
    (ROOT/'fbx_audit_v23.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()


