"""Native mesh spatial regressions for retained side and roof details in v14."""
import json
from pathlib import Path
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def audit(root, version='v14'):
    body=bpy.data.objects['body']
    tree=BVHTree.FromPolygons([body.matrix_world@v.co for v in body.data.vertices],
                            [list(p.vertices) for p in body.data.polygons])
    report={'status':'RUNNING','scope':'native LOD0 spatial regression, not measured real-vehicle dimensions',
            'filter_relief':[],'roof_grid':[],'thin_shelves':[]}
    def ray(p,d,limit):
        point,normal,index,distance=tree.ray_cast(Vector(p),Vector(d),limit)
        assert point is not None,(p,d)
        return point
    try:
        for side in (-1,1):
            for centre in (4.1,4.84):
                pitch=(.71-.118)/34
                fin=centre-(.71-.118)/2+8*pitch
                gap=fin+pitch*.55
                for z in (2.45,3.35):
                    p=ray((fin,side*2,z),(0,-side,0),.5)
                    q=ray((gap,side*2,z),(0,-side,0),.5)
                    relief=side*(p.y-q.y)
                    assert .017<relief<.03,(side,centre,z,relief)
                    report['filter_relief'].append({'side':side,'x':centre,'z':z,'fin_y':p.y,'gap_y':q.y,'relief_m':relief})
        # Measured grid height at nine intersections; rays in adjacent gaps
        # see the recessed machinery or roof, not another opaque cover.
        for i in (20,46,77):
            for j in (12,36,59):
                x=-7.18+i*3.16/106; y=-1.07+j*2.14/72
                p=ray((x,y,4.9),(0,0,-1),.6)
                assert abs(p.z-4.591)<.002,(i,j,p)
                report['roof_grid'].append({'i':i,'j':j,'point':list(p)})
        for end in (-1,1):
            for side in (-1,1):
                for z in (1.592,1.676,1.765):
                    p=ray((end*11.10,side*.44,z+.025),(0,0,-1),.04)
                    assert abs(p.z-(z+.005))<.001,(end,side,z,p)
                    report['thin_shelves'].append({'end':end,'side':side,'top_z':p.z})
        report['status']='PASS'
    except Exception as exc:
        report['status']='FAIL';report['error']=repr(exc)
        (Path(root)/f'detail_geometry_audit_{version}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        raise
    (Path(root)/f'detail_geometry_audit_{version}.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('V14 NATIVE FILTER / ROOF GRID / THIN SHELF CHECKS PASS',flush=True)
    return report
