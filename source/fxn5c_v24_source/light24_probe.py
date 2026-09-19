"""Isolated optical native probe; never writes the shipping staging directory."""
from pathlib import Path
import sys
import json
import bpy
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
from prepare_scene_v24 import prepare
import roof_revision_v24 as roof
import light_revision_v24 as lights
import export_tpf2 as export
import audit_lights_v24 as audit
from mathutils import Matrix

def main():
    all_results=[]
    for jw,lod in ((False,0),(False,1),(True,0),(True,1)):
        builder=prepare(lod,jw)
        roof.apply(builder,jw)
        report=lights.build(builder,jw,'0096')
        export.MOD_ROOT=str(ROOT/'runtime/light24_probe_mod')
        export.RESOURCE_KEY='light24_probe'
        export.MESH_DIR=str(Path(export.MOD_ROOT)/'res/models/mesh/vehicle/train/light24_probe')
        Path(export.MESH_DIR).mkdir(parents=True,exist_ok=True)
        resources=lights.export_lights(export,builder)
        assert resources['fwd']['materials']==[lights.WHITE,lights.WHITE,lights.RED]
        glass_nodes=[]
        for obj in bpy.context.scene.objects:
            if obj.type!='MESH' or not any('lamp_glass' in m.name for m in obj.data.materials):continue
            name='glass_'+str(len(glass_nodes))+'_lod'+str(lod)
            mats,_,_=export.export_mesh(name,[(obj,obj.matrix_world.copy())])
            glass_nodes.append({'name':name,'mesh':'vehicle/train/light24_probe/'+name+'.msh',
                                'materials':mats,'transf':list(lights.IDENTITY)})
        model={'metadata':{'transportVehicle':{'reversible':True},'railVehicle':{'configs':[{}, {}, {}]}},
               'lods':[{'node':{'name':'RootNode','children':list(glass_nodes),'transf':list(lights.IDENTITY)}} for i in range(3)]}
        lights.patch_mdl(model,{'number':'0096'},{0:resources,1:resources,2:{}})
        lights.validate_configuration(model,'0096')
        audit.RES=Path(export.MOD_ROOT)/'res'
        geometry=audit.Geometry()
        nodes=audit.tree(model['lods'][lod]['node'])
        glass=geometry.lens_triangles(nodes)
        optics=[]
        for direction in (1,-1):
            node=next(n for n,_ in nodes if n['name']=='light24_front_'+('fwd' if direction==1 else 'bwd'))
            optics.append(audit.audit_mesh(geometry,node,direction,'0096',lod,glass))
        all_results.append({'jinwen':jw,'lod':lod,'resources':resources,'optics':optics})
        print('LIGHT24_PROBE_PASS',jw,lod,resources,flush=True)
    (ROOT/'runtime/light24_probe_result.json').write_text(json.dumps(all_results,indent=2),encoding='utf-8')

if __name__=='__main__':main()
