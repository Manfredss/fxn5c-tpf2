"""Measure roof structure on the reconstructed native opaque mesh, in Blender."""
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from roof_details_v07 import EXHAUST_OUTLETS, DECK_SECTIONS, deck_z


def audit(root,version="v14"):
    body=bpy.data.objects["body"]
    tree=BVHTree.FromPolygons([body.matrix_world@v.co for v in body.data.vertices],
                             [list(p.vertices) for p in body.data.polygons])
    result={"status":"RUNNING","scope":"native opaque roof mesh ray checks; NOT in-game smoke testing",
            "samples":[],"particle_origins":[list(p) for p in EXHAUST_OUTLETS]}
    path=Path(root)/f"roof_geometry_audit_{version}.json"

    def sample(name,x,y,expected_z,tolerance=.010):
        hit,normal,face,distance=tree.ray_cast(Vector((x,y,4.90)),Vector((0,0,-1)),.65)
        actual=None if hit is None else float(hit.z)
        passed=hit is not None and abs(actual-expected_z)<tolerance
        result["samples"].append({"name":name,"x":x,"y":y,"expected_z":expected_z,
                                  "native_z":actual,"tolerance_m":tolerance,"pass":passed})
        assert passed,(name,actual,expected_z)
        if name=='continuous_cab_hood_crown':
            alignment=min(body.data.corner_normals[i].vector.dot(normal) for i in body.data.polygons[face].loop_indices)
            assert alignment>.99999,('Roof sheet shading differs from geometric plane',alignment)
            result['samples'][-1]['shading_normal_alignment']=alignment

    try:
        for x,y,z in EXHAUST_OUTLETS:
            # The outlet centres must reach the dark pocket floor, not an
            # uncut cover or a hidden duplicate central exhaust assembly.
            sample("open_lateral_exhaust_floor",x,y,4.501,.007)
        sample("solid_centre_between_outlets",-1.70,0,4.640,.006)
        for x,length,top in DECK_SECTIONS:
            # Use stations clear of access lids, seams, screws and lifting eyes.
            station=-2.72 if x<0 else 4.55
            for y in (-1.13,0,1.13):
                sample("planar_trapezoid_deck",station,y,deck_z(y,top),.008)
        from roof_cab_v13 import HOOD_STATIONS
        for end in (-1,1):
            for x in (7.53,7.80,9.40,9.63,9.87):
                a,c=next((a,c) for a,c in zip(HOOD_STATIONS,HOOD_STATIONS[1:]) if a[0]<=x<=c[0])
                t=(x-a[0])/(c[0]-a[0]); crown=a[4]+t*(c[4]-a[4])
                sample("continuous_cab_hood_crown",end*x,0,crown,.006)
            # The equipment bay is genuinely open down to the original shell,
            # not a solid slab covering the AC's side louvers. Avoid thin grates.
            for y in (-.81,.81):
                hit,normal,face,distance=tree.ray_cast(Vector((end*8.67,y,4.86)),Vector((0,0,-1)),.5)
                assert hit is not None and hit.z<4.59,('AC side bay covered',end,y,hit)
                result['samples'].append({'name':'open_ac_side_bay','end':end,'y':y,'native_z':float(hit.z),'pass':True})
        result["status"]="PASS"
    except Exception as error:
        result.update({"status":"FAIL","error":str(error)})
        path.write_text(json.dumps(result,indent=2),encoding="utf-8")
        raise
    path.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("V14 NATIVE ROOF: outlets, decks, retained v13 cab hoods and open AC side bays PASS",flush=True)
    return result
