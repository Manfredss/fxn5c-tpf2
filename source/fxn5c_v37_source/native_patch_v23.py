"""Replace only source-changed triangles in an immutable released native mesh.

10-micrometre position keys locate triangles across Blender float arithmetic.
Original attributes remain an exact byte prefix; surviving original indices
are untouched. No skeleton or wheel transform is rebuilt here.
"""
from collections import Counter
from pathlib import Path
import hashlib
import sys
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'runtime'))
from verify_native import read_lua
from native_merge_v22 import lua_literal,sha

ATTRS=('position','uv0','normal','tangent')


def decode(path,materials):
    path=Path(path);desc=read_lua(path);raw=Path(str(path)+'.blob').read_bytes()
    assert len(desc['subMeshes'])==len(materials)
    arrays={};rawattrs={}
    for key in ATTRS:
        a=desc['vertexAttr'][key]
        rawattrs[key]=raw[a['offset']:a['offset']+a['count']]
        arrays[key]=np.frombuffer(rawattrs[key],dtype='<f4').reshape(-1,a['numComp'])
    rows=[]
    for i,(sub,material) in enumerate(zip(desc['subMeshes'],materials)):
        a=sub['indices']['position'];assert all(v==a for v in sub['indices'].values())
        indices=np.frombuffer(raw,dtype='<u4',offset=a['offset'],count=a['count']//4).reshape(-1,3)
        q=np.rint(arrays['position'][indices].astype(np.float64)*100000).astype('<i4')
        for index,points in zip(indices,q):
            # Three cyclic permutations of the same 36-byte int32 triple.
            # Byte slices preserve exactly the prior signature while avoiding
            # three tiny NumPy allocations for every single triangle.
            packed=points.tobytes()
            cycles=[packed,packed[12:]+packed[:12],packed[24:]+packed[:24]]
            rows.append(((material,min(cycles)),i,index))
    return desc,arrays,rawattrs,rows


def write(path,old,after,oldraw,rows,newrows,oldmaterials,aftermaterials):
    extra_indices=np.asarray([int(v) for _,_,ids in newrows for v in ids],dtype=np.int64)
    blob=bytearray();attrs={}
    for key in ATTRS:
        extra=after[key][extra_indices].astype('<f4').tobytes()
        attrs[key]={'count':len(oldraw[key])+len(extra),'numComp':old[key].shape[1],'offset':len(blob)}
        blob.extend(oldraw[key]);blob.extend(extra)
    materials=list(oldmaterials);groups=[[] for _ in materials]
    for _,slot,indices in rows:groups[slot].extend(int(v) for v in indices)
    offset=len(old['position'])
    for n,(signature,slot,indices) in enumerate(newrows):
        material=aftermaterials[slot]
        if material not in materials:materials.append(material);groups.append([])
        destination=materials.index(material)
        groups[destination].extend((offset+3*n,offset+3*n+1,offset+3*n+2))
    subs=[];actual=[]
    for material,indices in zip(materials,groups):
        if not indices:continue
        block={'count':4*len(indices),'offset':len(blob)}
        blob.extend(np.asarray(indices,dtype='<u4').tobytes())
        subs.append({'indices':{key:dict(block) for key in ATTRS}});actual.append(material)
    path=Path(path)
    path.write_text('function data()\nreturn '+lua_literal({'subMeshes':subs,'vertexAttr':attrs})+'\nend\n',encoding='utf-8')
    Path(str(path)+'.blob').write_bytes(blob)
    return actual,len(extra_indices)


def patch(baseline,before,after,target,baseline_materials,before_materials,after_materials):
    _,oa,oraw,original=decode(baseline,baseline_materials)
    _,ba,braw,prior=decode(before,before_materials)
    _,na,nraw,current=decode(after,after_materials)
    prior_counts=Counter(key for key,_,_ in prior);new_counts=Counter(key for key,_,_ in current)
    remove=prior_counts-new_counts;add=new_counts-prior_counts
    original_counts=Counter(key for key,_,_ in original)
    missing=remove-original_counts
    assert not missing,('changed source triangles absent from native baseline',str(target),sum(missing.values()),list(missing)[:2])
    remaining=remove.copy();keep=[]
    for row in original:
        if remaining[row[0]]:remaining[row[0]]-=1
        else:keep.append(row)
    remaining=add.copy();extra=[]
    for row in current:
        if remaining[row[0]]:remaining[row[0]]-=1;extra.append(row)
    assert sum(remaining.values())==0
    mats,vertices=write(target,oa,na,oraw,keep,extra,baseline_materials,after_materials)
    return {'materials':mats,'removed_triangles':sum(remove.values()),'added_triangles':len(extra),
            'retained_triangles':len(keep),'original_vertices':len(oa['position']),'added_vertices':vertices,
            'position_key_tolerance_m':.00001,
            'original_attribute_prefix_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in oraw.items()},
            'mesh_sha256':sha(target),'blob_sha256':sha(str(target)+'.blob')}


def set_model_materials(text,mesh_ref,oldmaterials,newmaterials):
    from native_merge_v22 import append_model_materials
    # Same tight resource-specific replacement, but the new set may remove
    # emptied original slots as well as adding new colors.
    import re
    pattern=r'(materials\s*=\s*\{)([^}]*)(\},\s*mesh\s*=\s*"'+re.escape(mesh_ref)+r'")'
    def replace(m):
        assert re.findall(r'"([^"\n]+)"',m[2])==oldmaterials,mesh_ref
        return m[1]+' '+' '.join('"'+s+'",' for s in newmaterials)+' '+m[3]
    value,n=re.subn(pattern,replace,text);assert n==1,(mesh_ref,n)
    return value
