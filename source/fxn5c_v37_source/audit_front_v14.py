"""Geometric acceptance on reconstructed game meshes, not feature counters."""
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from geometry_v07 import SilhouetteBuilder
from front_lamps_v14 import lower_frame
from front_details_v10 import circle
from nose_shell_v14 import corner_x, front_half
from mathutils.kdtree import KDTree


def points(obj):
    return list({tuple(round(c,6) for c in obj.matrix_world@v.co) for v in obj.data.vertices})


def tree_for(obj):
    return BVHTree.FromPolygons([obj.matrix_world@v.co for v in obj.data.vertices],
                                [list(p.vertices) for p in obj.data.polygons])


def audit(root, version='v14'):
    path=Path(root)/f"front_geometry_audit_{version}.json"
    r={"status":"RUNNING","scope":"native LOD0 geometry; not a game or dimensional-certification test",
       "lower_fixture_planes":[],"upper_cover_depth":[],"upper_cavity_rays":[],
       "lower_emitter_positions":[],"plough_protrusion":[],"tread_contacts":[],
       "coupler_throats":[],"cradle_openings":[],"inboard_lamp_clearance":[],"outboard_lamp_clearance":[],"photo_lamp_spacing":[]}
    try:
        body=bpy.data.objects["body"]; tree=tree_for(body)
        for obj in bpy.context.scene.objects:
            if not obj.name.startswith("glazing_"): continue
            ps=points(obj); center=sum((Vector(p) for p in ps),Vector())/len(ps)
            end=1 if center.x>0 else -1; side=1 if center.y>0 else -1
            if center.z<2.3:
                kind="red" if abs(center.y)>1.4 else "white"
                origin,tangent,normal=lower_frame(end,side,kind)
                error=(center-(origin+normal*.030)).length
                plane_error=max(abs((Vector(p)-origin).dot(normal)-.030) for p in ps)
                p=obj.data.polygons[0]
                a,b,c=[obj.matrix_world@obj.data.vertices[i].co for i in p.vertices[:3]]
                actual=(b-a).cross(c-a).normalized()
                alignment=actual.dot(normal)
                assert error<2e-5 and plane_error<2e-5 and alignment>.999,(obj.name,error,plane_error,alignment)
                r["lower_fixture_planes"].append({"node":obj.name,"type":"outboard" if kind=="red" else "inboard","center":list(center),
                    "normal":list(actual),"expected_normal":list(normal),"center_error_m":error})
            elif center.z>4.1 and max(p[1] for p in ps)-min(p[1] for p in ps)>.6:
                offsets=[end*p[0]-SilhouetteBuilder.front_x(p[2]) for p in ps]
                assert max(abs(d+.005) for d in offsets)<2e-5
                r["upper_cover_depth"].append({"node":obj.name,"x_offsets_from_shell":offsets})
        assert len(r["lower_fixture_planes"])==8 and len(r["upper_cover_depth"])==2
        # Broad independent photo-derived placement bounds, not just checking
        # the exporter against the same placement helper used by the builder.
        for end in (-1,1):
            for side in (-1,1):
                pair={p["type"]:p["center"] for p in r["lower_fixture_planes"]
                      if p["center"][0]*end>0 and p["center"][1]*side>0}
                ratio=abs(pair["inboard"][1]/pair["outboard"][1])
                dz=pair["outboard"][2]-pair["inboard"][2]
                assert .75<ratio<.82 and 0<dz<.05,(end,side,ratio,dz)
                r["photo_lamp_spacing"].append({"end":end,"side":side,"inner_outer_offset_ratio":ratio,"height_difference_m":dz})
        # Both outer lenses must face the track longitudinal axis, independent
        # of the oblique mounting skin. Do not use skin normals for this test.
        assert all(p["normal"][0]*(1 if p["center"][0]>0 else -1)>.99999
                   and abs(p["normal"][1])<1e-5 for p in r["lower_fixture_planes"])
        r["all_lower_lamps_face_longitudinally"]=True
        vertices=[body.matrix_world@v.co for v in body.data.vertices]
        candidates=[p for p in vertices if abs(p.x)>10.75 and abs(p.y)>1.39 and 1.93<p.z<2.18]
        kd=KDTree(len(candidates))
        for i,p in enumerate(candidates): kd.insert(p,i)
        kd.balance()
        r["compact_return_contacts"]=[]
        for end in (-1,1):
            for side in (-1,1):
                base,_,_=lower_frame(end,side,"red")
                for u,v in circle(.114,8):
                    y=base.y+side*u; z=base.z+v
                    rear=Vector((end*(corner_x(y,z)+.001),y,z))
                    front=Vector((base.x+end*.002,base.y+side*u*.109/.114,base.z+v*.109/.114))
                    for label,p in (("skin_edge",rear),("fixture_edge",front)):
                        _,_,distance=kd.find(p)
                        assert distance<2e-5,(end,side,label,distance)
                    # v14's ring spans the actual kinked shell and remains
                    # longitudinal-facing. The shallower .30-slope photo fit
                    # limits the visible forward projection to 23 mm, while
                    # retaining strict native contacts and <60 mm total depth.
                    # This bounded adapter envelope is not a factory dimension.
                    assert abs(front.x-rear.x)<.060,('outboard_return_too_deep',front,rear)
                    assert end*(front.x-rear.x)<=.023,('outboard_return_too_proud',front,rear)
                    r["compact_return_contacts"].append({"end":end,"side":side,"rear":list(rear),
                        "front":list(front),"depth_m":end*(front.x-rear.x)})
        for end in (-1,1):
            for y in (-.20,-.15,-.10,0,.10,.15,.20):
                for z in (4.22,4.27,4.32):
                    hit,_,_,_=tree.ray_cast(Vector((end*11,y,z)),Vector((-end,0,0)),1.3)
                    assert hit is not None
                    depth=end*hit.x-SilhouetteBuilder.front_x(z)
                    r["upper_cavity_rays"].append({"end":end,"y":y,"z":z,"offset":depth})
                    assert -.155<depth<-.017,(end,y,z,depth)
            for side in (-1,1):
                for kind,node in (("white","headlights_fwd" if end==1 else "headlights_bwd"),
                                  ("red","taillights_bwd" if end==1 else "taillights_fwd")):
                    ps=[Vector(p) for p in points(bpy.data.objects[node]) if p[2]<2.3 and p[1]*side>0]
                    center=sum(ps,Vector())/len(ps)
                    base,_,normal=lower_frame(end,side,"white")
                    assert (center-base-normal*.020).length<2e-5
                    r["lower_emitter_positions"].append({"end":end,"side":side,"color":kind,"position":"inboard","center":list(center)})
                for kind in ("white","red"):
                    for dy in (-.03,0,.03):
                        for dz in (-.03,0,.03):
                            lamp_base,_,_=lower_frame(end,side,kind)
                            y=lamp_base.y+dy; z=lamp_base.z+dz
                            hit,_,_,_=tree.ray_cast(Vector((end*12,y,z)),Vector((-end,0,0)),1.5)
                            assert hit is not None and end*(hit.x-lamp_base.x)<.0201,(kind,end,side,hit)
                            r[("inboard" if kind=="white" else "outboard")+"_lamp_clearance"].append({"end":end,"y":y,"z":z,"clear":True})
                for y in (side*1.08,side*1.23):
                    hit,_,_,_=tree.ray_cast(Vector((end*11.30,y,.34)),Vector((-end,0,0)),.30)
                    assert hit is not None and abs(end*hit.x-11.105)<.009,(end,y,hit)
                    r["tread_contacts"].append({"end":end,"y":y,"black_plate_x":hit.x})
                # Probe the two bracket webs separately: they intentionally sit
                # forward of the backing plate at z=.34, tapering into it above.
                for y in (side*1.00,side*1.31):
                    hit,_,_,_=tree.ray_cast(Vector((end*11.30,y,.34)),Vector((-end,0,0)),.30)
                    assert hit is not None and 11.105<end*hit.x<11.130,(end,y,hit)
                    r["tread_contacts"].append({"end":end,"y":y,"attachment_web_x":hit.x})
            hit,_,_,_=tree.ray_cast(Vector((end*12,0,.292)),Vector((-end,0,0)),1)
            assert hit is not None and 11.49<end*hit.x<11.55,(end,hit)
            r["plough_protrusion"].append({"end":end,"center_tip_x":hit.x,"black_plate_x":end*11.105})
            # Open vertical space between fixed jaw and knuckle, not a black tile.
            hit,_,_,_=tree.ray_cast(Vector((end*11.52,0,1.29)),Vector((0,0,-1)),.46)
            assert hit is None,("coupler throat filled",end,hit)
            r["coupler_throats"].append({"end":end,"x":end*11.52,"open":True})
        painted=[]
        for poly in body.data.polygons:
            if not body.data.materials[poly.material_index].name.endswith("/yellow"): continue
            ps=[body.matrix_world@body.data.vertices[i].co for i in poly.vertices]
            if max(p.z for p in ps)<.8:
                painted.extend(ps)
        assert painted and max(abs(p.y) for p in painted)<.802
        r["central_warning_paint_halfwidth"]=max(abs(p.y) for p in painted)
        # Production front silhouette: no flat shoulder above the two sloping
        # edges from the central high point to the outer bottom corners.
        envelope_error=max(p.z-(.715-.55*abs(p.y)) for p in painted)
        assert envelope_error<2e-5,envelope_error
        r["central_triangular_top_envelope_error_m"]=envelope_error
        for index,cx in ((1,6.7),(2,-6.7)):
            t=tree_for(bpy.data.objects[f"b{index}"])
            for side in (-1,1):
                for axle in (-1.8,0,1.8):
                    for dx in (-.433,.433):
                        # v19 cradle is photo-fitted 0.20 m lower. The full
                        # rounded-window shape is independently audited by
                        # audit_bogie_v20; retain this integration clearance.
                        hit,_,_,_=t.ray_cast(Vector((cx+axle+dx,side*1.35,.387)),Vector((0,-side,0)),.39)
                        assert hit is None,('v19 lower cradle window',index,side,axle,dx,hit)
                        r["cradle_openings"].append({"bogie":index,"side":side,"axle":axle,"dx":dx,"clear":True})
        assert len(r["lower_emitter_positions"])==8
        assert all(abs(p["center"][1])<1.3 for p in r["lower_emitter_positions"])
        r["inboard_red_white_modes"]=True
        r["outboard_default_emission"]=False
        # Inspect actual native paint/hardware triangles, independently of the
        # source object tags. This catches flat text left hovering at old X.
        finish=[]
        for end in (-1,1):
            paint=[]; number=[]; hardware=[]
            for poly in body.data.polygons:
                material=body.data.materials[poly.material_index].name.rsplit('/',1)[-1]
                if material not in {'white','metal','spring_steel'}: continue
                ps=[body.matrix_world@body.data.vertices[i].co for i in poly.vertices]
                if not all(p.x*end>10.9 for p in ps): continue
                if material=='white' and all(abs(p.y)<.90 and 1.65<p.z<2.42 for p in ps):
                    paint.extend(ps)
                    if all(p.z<1.94 for p in ps): number.extend(ps)
                    normal=(ps[1]-ps[0]).cross(ps[2]-ps[0]).normalized()
                    assert normal.x*end>.9999
                if material in {'metal','spring_steel'} and all(.66<abs(p.y)<.86 and 1.775<p.z<2.365 for p in ps):
                    hardware.extend(ps)
            assert len(paint)>300 and len(number)>100 and len(hardware)>500
            plane_error=max(abs(end*p.x-11.0416) for p in paint)
            assert plane_error<2e-5,('floating_front_paint',end,plane_error)
            number_bounds=(min(p.z for p in number),max(p.z for p in number))
            assert number_bounds[0]>=1.792-2e-5 and number_bounds[1]<=1.9088+2e-5
            hardware_bounds=(min(end*p.x for p in hardware),max(end*p.x for p in hardware))
            assert hardware_bounds[0]>=11.04049-2e-5 and hardware_bounds[1]<=11.1001
            finish.append({'end':end,'paint_triangles':len(paint)//3,
                           'paint_plane_error_m':plane_error,'number_z_bounds':number_bounds,
                           'grab_hardware_triangles':len(hardware)//3,'grab_hardware_abs_x_bounds':hardware_bounds})
        r['front_finish_native_geometry']=finish
        r["status"]="PASS"
    except Exception as exc:
        r.update({"status":"FAIL","error":repr(exc)})
        path.write_text(json.dumps(r,indent=2),encoding="utf-8"); raise
    path.write_text(json.dumps(r,indent=2),encoding="utf-8")
    print("V14 FRONT NATIVE PASS: 8 forward lamp planes, compact skin returns, recessed upper glass, plough/treads/Janney throats",flush=True)
    return r
