import sys,json,struct
from pathlib import Path
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'fxn5c_v23_source/runtime'))
from lupa import LuaRuntime
base=Path('G:/SteamLibrary/steamapps/common/Transport Fever 2/res/models')
def plain(v):
    if hasattr(v,'items'):
        d={k:plain(x) for k,x in v.items()}
        return [d[i] for i in range(1,len(d)+1)] if d and set(d)==set(range(1,len(d)+1)) else d
    return v
def lua(raw):
    vm=LuaRuntime();vm.execute('function _(s) return s end')
    vm.execute(raw.decode());return plain(vm.globals().data())
with ZipFile(base/'model.zip') as models,ZipFile(base/'mesh.zip') as meshes,ZipFile(base/'mesh-blob.zip') as blobs:
    for stem in ('br_185_traxx_v2','br_218_v2','eurodual_v2'):
        model=lua(models.read('model/vehicle/train/'+stem+'.mdl'));nodes=[]
        def walk(n):
            nodes.append(n)
            for c in n.get('children',[]):walk(c)
        walk(model['lods'][0]['node'])
        result={'model':stem,'modes':{}}
        for k,v in model['metadata']['railVehicle']['configs'][0].items():
            if not k.endswith('Parts'):continue
            rows=[]
            for idx in v:
                n=nodes[idx];row={'index':idx,'node':n['name'],'mesh':n['mesh'],'materials':n['materials']}
                desc=lua(meshes.read('mesh/'+n['mesh']));a=desc['vertexAttr']['position']
                raw=blobs.read('mesh/'+n['mesh']+'.blob')
                vals=struct.unpack_from('<'+str(a['count']//4)+'f',raw,a['offset'])
                p=list(zip(*[iter(vals)]*3));row['bounds']=[[min(v[j] for v in p),max(v[j] for v in p)] for j in range(3)]
                rows.append(row)
            result['modes'][k]=rows
        print(json.dumps(result,indent=2))
