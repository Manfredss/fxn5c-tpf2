"""Drop entirely exact-zero snapshot slots, retaining original attribute bytes."""
from pathlib import Path
import numpy as np
from verify_native import read_lua
from native_merge_v22 import lua_literal
from roof_revision_v24 import sanitize_after_export


def clean_snapshot(path, materials):
    path=Path(path);desc=read_lua(path);raw=Path(str(path)+'.blob').read_bytes()
    assert len(desc['subMeshes'])==len(materials)
    a=desc['vertexAttr']['position']
    pts=np.frombuffer(raw,dtype='<f4',offset=a['offset'],count=a['count']//4).reshape(-1,3).astype(np.float64)
    kept=[];mats=[]
    for sub,material in zip(desc['subMeshes'],materials):
        b=sub['indices']['position']
        ids=np.frombuffer(raw,dtype='<u4',offset=b['offset'],count=b['count']//4).reshape(-1,3)
        p=pts[ids]
        valid=np.any(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])!=0,axis=1)
        if valid.any():kept.append(sub);mats.append(material)
    assert kept,'empty snapshot'
    if len(kept)!=len(materials):
        desc['subMeshes']=kept
        path.write_text('function data()\nreturn '+lua_literal(desc)+'\nend\n',encoding='utf8')
    sanitize_after_export(path)
    return mats
