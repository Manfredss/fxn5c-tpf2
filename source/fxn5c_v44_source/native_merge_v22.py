"""Append static detail streams without changing any existing native vertex.

The original skeleton and model tree must stay unchanged: adding mesh nodes
inside running_gear_skin would renumber its encoded skin joints.
"""
from pathlib import Path
import hashlib
import re
import struct
from verify_native import read_lua


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lua_literal(value, depth=0):
    if isinstance(value, dict):
        return '{\n' + ''.join('  '*(depth+1)+str(k)+' = '+lua_literal(v,depth+1)+',\n' for k,v in value.items())+'  '*depth+'}'
    if isinstance(value, list):
        return '{\n'+''.join('  '*(depth+1)+lua_literal(v,depth+1)+',\n' for v in value)+'  '*depth+'}'
    return str(value)


def merge(baseline, addition, target):
    baseline,addition,target=map(Path,(baseline,addition,target))
    a,b=read_lua(baseline),read_lua(addition)
    ba,bb=Path(str(baseline)+'.blob').read_bytes(),Path(str(addition)+'.blob').read_bytes()
    assert set(a['vertexAttr'])==set(b['vertexAttr'])=={'position','normal','tangent','uv0'}
    count=a['vertexAttr']['position']['count']//12
    blob=bytearray();attrs={};prefixes={}
    for name in ('position','uv0','normal','tangent'):
        aa,ab=a['vertexAttr'][name],b['vertexAttr'][name]
        assert aa['numComp']==ab['numComp']
        old=ba[aa['offset']:aa['offset']+aa['count']]
        extra=bb[ab['offset']:ab['offset']+ab['count']]
        attrs[name]={'count':len(old)+len(extra),'numComp':aa['numComp'],'offset':len(blob)}
        blob.extend(old);blob.extend(extra)
        prefixes[name]=hashlib.sha256(old).hexdigest()
    subs=[]
    for desc,raw,shift in ((a,ba,0),(b,bb,count)):
        for sub in desc['subMeshes']:
            ref=sub['indices']['position']
            assert all(v==ref for v in sub['indices'].values()),'Only unified indexed static streams supported'
            indices=raw[ref['offset']:ref['offset']+ref['count']]
            if shift:
                values=struct.unpack('<'+str(len(indices)//4)+'I',indices)
                indices=struct.pack('<'+str(len(values))+'I',*(i+shift for i in values))
            block={'count':len(indices),'offset':len(blob)}
            subs.append({'indices':{name:dict(block) for name in attrs}})
            blob.extend(indices)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('function data()\nreturn '+lua_literal({'subMeshes':subs,'vertexAttr':attrs})+'\nend\n',encoding='utf-8')
    Path(str(target)+'.blob').write_bytes(blob)
    return {'baseline_vertices':count,'added_vertices':b['vertexAttr']['position']['count']//12,
            'added_triangles':sum(s['indices']['position']['count']//12 for s in b['subMeshes']),
            'original_attribute_prefix_sha256':prefixes,'mesh_sha256':sha(target),'blob_sha256':sha(str(target)+'.blob')}


def append_model_materials(text, mesh_ref, baseline_materials, addition_materials):
    pattern=r'(materials\s*=\s*\{)([^}]*)(\},\s*mesh\s*=\s*"'+re.escape(mesh_ref)+r'")'
    def replace(match):
        assert re.findall(r'"([^"\n]+)"',match[2])==baseline_materials,mesh_ref
        return match[1]+' '+' '.join('"'+m+'",' for m in baseline_materials+addition_materials)+' '+match[3]
    out,count=re.subn(pattern,replace,text)
    assert count==1,(mesh_ref,count)
    return out
