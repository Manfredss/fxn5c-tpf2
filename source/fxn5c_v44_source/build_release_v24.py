"""Incremental v23→v24 body/pane delta; keep all running gear byte-identical."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,sys,math,re
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime'))
BASE=ROOT.parent/'fxn5c_v23_source'
MOD=ROOT/'staging/codex_fxn5c_1'
import generate_fxn5c as gen
import export_tpf2 as export
from prepare_scene_v24 import prepare,rebase_textures
import roof_revision_v24 as roof
import front_revision_v24 as front
import light_revision_v24 as lights
from body_revision_v23 import apply_number_weight
from livery_revision_v21 import _replace_signage
from roster_v21 import ROSTER
from native_patch_v23 import patch,sha
from verify_native import read_lua
from build_release_v23 import ancestor_bogie

def lua_literal(value,depth=0):
    """Full literal tables (the old mesh serializer handled numbers only)."""
    pad='  '*depth;child='  '*(depth+1)
    if isinstance(value,bool):return 'true' if value else 'false'
    if value is None:return 'nil'
    if isinstance(value,str):
        escaped=''.join('\\\\' if c=='\\' else '\\"' if c=='"' else
            ('\\'+str(ord(c)).zfill(3)) if ord(c)<32 or ord(c)==127 else c for c in value)
        return '"'+escaped+'"'
    if isinstance(value,(int,float)):
        assert math.isfinite(value)
        return repr(value)
    if isinstance(value,list):return '{\n'+''.join(child+lua_literal(v,depth+1)+',\n' for v in value)+pad+'}'
    if isinstance(value,dict):
        reserved={'and','break','do','else','elseif','end','false','for','function','goto',
                  'if','in','local','nil','not','or','repeat','return','then','true','until','while'}
        def key(k):
            return k if isinstance(k,str) and k not in reserved and re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',k) else '['+lua_literal(k)+']'
        return '{\n'+''.join(child+key(k)+' = '+lua_literal(v,depth+1)+',\n' for k,v in value.items())+pad+'}'
    raise TypeError(type(value))

def normalize_empty(value):
    if isinstance(value,list):return [normalize_empty(v) for v in value] if value else {}
    if isinstance(value,dict):return {k:normalize_empty(v) for k,v in value.items()}
    return value

def walk(node):
    yield node
    for child in node.get('children',[]):yield from walk(child)

def body_items():
    objects=[o for o in bpy.context.scene.objects if o.type=='MESH' and '|bounding_box' not in o.name and not o.name.startswith('bounds|')]
    selected=[o for o in objects if not ancestor_bogie(o) and not o.get('connection_role')
        and not o.get('livery21_variable') and o.name not in export.LIGHT_NAMES and not o.get('light24_emitter')
        and o.name!='cab_interior' and not o.name.startswith('glazing_')]
    return [(o,o.matrix_world.copy()) for o in sorted(selected,key=lambda o:o.name)]

def snapshot(style,lod,phase):
    export.MESH_DIR=str(ROOT/'runtime/patch_inputs_v24'/style)
    name=f'body_{phase}_lod{lod}'
    mats,verts,tris=export.export_mesh(name,body_items())
    result={'file':f'runtime/patch_inputs_v24/{style}/{name}.msh','materials':mats,'triangles':tris}
    if phase=='after':
        result['export_sanitization']=roof.sanitize_after_export(ROOT/result['file'])
        result['triangles']=result['export_sanitization']['triangles']
    return result

def geometry_hash(obj):
    import struct
    h=hashlib.sha256()
    for v in obj.data.vertices:h.update(struct.pack('<3f',*(obj.matrix_world@v.co)))
    for p in obj.data.polygons:h.update(str(tuple(p.vertices)).encode())
    return h.hexdigest()

def save_source(path):
    from source_hygiene_v13 import clean_fonts
    for obj in list(bpy.context.scene.objects):
        if obj.type in {'LIGHT','CAMERA'}:bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.object.camera_add(location=(22,-32,11))
    camera=bpy.context.object;camera.data.type='ORTHO';camera.data.ortho_scale=25.5
    gen.point_camera(camera,(0,0,2.1));bpy.context.scene.camera=camera
    clean_fonts();rebase_textures();bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))

def write_models(records,panes,lamp_resources):
    by_ref={r['mesh_ref']:r for r in records}
    model_rows={r['stem']:r for r in ROSTER}
    model_rows.update(fxn5c_menu_cr=ROSTER[0],fxn5c_menu_jinwen=next(r for r in ROSTER if r['jinwen']))
    for stem,row in model_rows.items():
        relative=f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{stem}.mdl'
        model=read_lua(BASE/relative);style='fxn5c_jinwen' if row['jinwen'] else 'fxn5c'
        for index,lod in enumerate(model['lods']):
            for node in walk(lod['node']):
                if node.get('mesh') in by_ref:node['materials']=by_ref[node['mesh']]['materials']
                for pane in panes:
                    if pane['style']==style and pane['lod']==index and pane['name']==node['name']:
                        node['materials']=pane['materials'];node['transf']=pane['transf']
        lights.patch_mdl(model,row,lamp_resources[style])
        literal=lua_literal(model)
        # read_lua uses an identity translator for inspection; restore these
        # two executable localization calls when writing the game resource.
        for value in model['metadata']['description'].values():
            token=lua_literal(value)
            assert literal.count(token)==1,('ambiguous localized field',stem,value)
            literal=literal.replace(token,'_('+token+')',1)
        (ROOT/relative).write_text('function data()\nreturn '+literal+'\nend\n',encoding='utf-8')
        assert read_lua(ROOT/relative)==normalize_empty(model),('model Lua roundtrip failed',stem)

def rewrite_model_metadata():
    """Reuse hash-verified current geometry for a metadata-only finalization."""
    path=ROOT/'native_patch_manifest_v24.json'
    manifest=json.loads(path.read_text(encoding='utf-8'))
    for row in manifest['patches']+manifest['panes']:
        assert sha(ROOT/row['target'])==row['mesh_sha256']
        assert sha(ROOT/(row['target']+'.blob'))==row['blob_sha256']
    for row in manifest['sources']:assert sha(ROOT/row['file'])==row['sha256']
    for name,digest in manifest['inputs_sha256'].items():
        if name!='build_release_v24.py':assert sha(ROOT/name)==digest,('geometry recipe changed',name)
    write_models(manifest['patches'],manifest['panes'],manifest['lights'])
    manifest['metadata_finalization']={'localized_name_and_description_calls':True,'geometry_reused_without_modification':True}
    manifest['inputs_sha256']['build_release_v24.py']=sha(Path(__file__))
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('V24_MODEL_METADATA_FINALIZED',flush=True)

def main():
    records=[];sources=[];signage=[];panes=[];lamp_resources={};changes=[]
    for jw in (False,True):
        style='fxn5c_jinwen' if jw else 'fxn5c'
        baseline=read_lua(BASE/f'staging/codex_fxn5c_1/res/models/model/vehicle/train/{style}.mdl')
        rows=[r for r in ROSTER if r['jinwen']==jw];lamp_resources[style]={}
        for lod in (0,1,2):
            builder=prepare(lod,jw)
            pane_before={o.name:geometry_hash(o) for o in bpy.context.scene.objects if o.name.startswith('glazing_')}
            prior=snapshot(style,lod,'before')
            edits={'baseline_tessellation':builder.baseline24_tessellation,
                   'roof':roof.apply(builder,jw),'front':front.apply_common(builder,jw)}
            bpy.context.view_layer.update();gen.ensure_uvs()
            after=snapshot(style,lod,'after')
            nodes={n['name']:n for n in walk(baseline['lods'][lod]['node'])}
            ref=nodes['body']['mesh'];relative='staging/codex_fxn5c_1/res/models/mesh/'+ref
            proof=patch(BASE/relative,ROOT/prior['file'],ROOT/after['file'],ROOT/relative,
                nodes['body']['materials'],prior['materials'],after['materials'])
            records.append(dict(style=style,jinwen=jw,lod=lod,attachment='body',mesh_ref=ref,target=relative,
                baseline='../fxn5c_v23_source/'+relative,before=prior,after=after,baseline_materials=nodes['body']['materials'],**proof))
            export.MESH_DIR=str(MOD/'res/models/mesh/vehicle/train'/style)
            for name,old_hash in pane_before.items():
                obj=bpy.data.objects.get(name)
                assert obj is not None,('Lost inherited glass node',name)
                if geometry_hash(obj)==old_hash:continue
                centre=sum((obj.matrix_world@v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
                tf=Matrix.Translation(centre)
                mesh_name=f'{name}_lod{lod}'
                mats,verts,tris=export.export_mesh(mesh_name,[(obj,tf.inverted()@obj.matrix_world)])
                mesh_ref=f'vehicle/train/{style}/{mesh_name}.msh'
                assert mesh_ref==nodes[name]['mesh']
                target='staging/codex_fxn5c_1/res/models/mesh/'+mesh_ref
                panes.append(dict(style=style,lod=lod,name=name,mesh_ref=mesh_ref,materials=mats,
                    transf=[tf[r][c] for c in range(4) for r in range(4)],triangles=tris,vertices=verts,target=target,
                    mesh_sha256=sha(ROOT/target),blob_sha256=sha(ROOT/(target+'.blob'))))
            export.select_vehicle(rows[0])
            edits['lights']=lights.build(builder,jw,rows[0]['number'])
            lamp_resources[style][lod]=lights.export_lights(export,builder)
            for index,row in enumerate(rows):
                _replace_signage(builder,jw,row['number'],row['depot'])
                if lod<2:
                    apply_number_weight(builder);front.apply_number(builder)
                export.select_vehicle(row)
                signs=export.export_signage(lod)
                if signs:signage.append(dict(model=row['stem'],number=row['number'],lod=lod,**signs))
                if index==0 and lod==0:
                    save_source(ROOT/(style+'_source.blend'))
                    sources.append(dict(file=style+'_source.blend',sha256=sha(ROOT/(style+'_source.blend'))))
            changes.append(dict(style=style,lod=lod,changes=edits))
            print('BUILD24',style,lod,proof['removed_triangles'],proof['added_triangles'],flush=True)
    write_models(records,panes,lamp_resources)
    for filename in ('mod.lua','strings.lua'):
        text=(BASE/'staging/codex_fxn5c_1'/filename).read_text(encoding='utf-8')
        (MOD/filename).write_text(text.replace('v0.23','v0.24').replace('minorVersion = 23','minorVersion = 24'),encoding='utf-8')
    inputs=('roof_revision_v24.py','front_revision_v24.py','light_revision_v24.py','prepare_scene_v24.py','baseline_tessellation_v24.py','build_release_v24.py','native_patch_v23.py')
    manifest=dict(status='BUILT_PENDING_AUDIT',patches=records,panes=panes,sources=sources,signage=signage,
        lights=lamp_resources,scene_changes=changes,inputs_sha256={n:sha(ROOT/n) for n in inputs},
        scope='Roof/front body delta, reseated upper glass, new per-vehicle directional optics; running gear retained',game_verified=False)
    (ROOT/'native_patch_manifest_v24.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print('v24 build complete',flush=True)

if __name__=='__main__':
    rewrite_model_metadata() if '--models-only' in sys.argv else main()
