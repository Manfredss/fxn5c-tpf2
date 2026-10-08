"""v0.7 silhouette corrections, reconstructed from production-car photos/video.

The corner land is part of the shell topology, not a decorative strip. Dimensions
are visual estimates. Existing transparent glazing, lamps and running gear stay.
"""
from collections import Counter
import bpy
from geometry_v02 import build as build_body
from geometry_v06 import FrontRoofBuilder, front_loop
from cab_details_v07 import side_window_loop, rebuild_side_cab
from underframe_details_v07 import refine_underframe, add_pilot_returns


class SilhouetteBuilder(FrontRoofBuilder):
    @staticmethod
    def front_half(z):
        if z <= 2.55:
            return 1.48
        if z <= 4.02:
            return 1.48 - (z-2.55)*.05/1.47
        return 1.43 - (z-4.02)*.41/.46

    @staticmethod
    def corner_width(z):
        return .17 if z <= 4.02 else .17-(z-4.02)*.07/.46

    @classmethod
    def side_y(cls, x, z):
        # Evaluate the same explicit triangle planes used by hull(), not a
        # bilinear interpolation across a non-planar cab-side quadrilateral.
        # The diagonal runs from the outer lower vertex to the inner upper
        # vertex in every quadrant. Most of the side glazing then sits on the
        # genuinely flat main side plate, with the taper confined to its nose.
        x=abs(x); z=max(1.58,min(4.48,z))
        levels=(1.58,2.55,3.95,4.02,4.48)
        low,high=next((a,b) for a,b in zip(levels,levels[1:]) if a<=z<=b)
        t=(z-low)/(high-low)
        middle=lambda height:1.65-max(0,height-3.95)*.50/.53
        if x<=9.4:
            return middle(z)
        if x>=cls.front_x(z):
            return cls.front_half(z)

        def row(height,corner_patch):
            nose=cls.front_x(height)
            front=cls.front_half(height)
            corner=(nose-.24,front+cls.corner_width(height),height)
            if corner_patch:
                return corner,(nose,front,height)
            return (9.4,middle(height),height),corner

        corner_patch=x>cls.front_x(z)-.24
        a,b=row(low,corner_patch)
        d,c=row(high,corner_patch)
        diagonal_x=b[0]+t*(d[0]-b[0])
        p,q,r=(a,b,d) if x<=diagonal_x else (b,c,d)
        determinant=(q[0]-p[0])*(r[2]-p[2])-(r[0]-p[0])*(q[2]-p[2])
        u=((x-p[0])*(r[2]-p[2])-(r[0]-p[0])*(z-p[2]))/determinant
        v=((q[0]-p[0])*(z-p[2])-(x-p[0])*(q[2]-p[2]))/determinant
        return p[1]+u*(q[1]-p[1])+v*(r[1]-p[1])

    def hull(self):
        # Three vertices on each cab side instead of a single knife-edge
        # junction. Constant corner offset below the brow makes a broad land.
        levels=(1.58,2.55,3.95,4.02,4.48)
        verts=[]
        for z in levels:
            x=self.front_x(z); y=self.front_half(z)
            corner_y=y+self.corner_width(z)
            side_y=self.side_y(9.4,z)
            ring=[(x,-y),(x,y),(x-.24,corner_y),(9.4,side_y),
                  (-9.4,side_y),(-x+.24,corner_y),(-x,y),(-x,-y),
                  (-x+.24,-corner_y),(-9.4,-side_y),(9.4,-side_y),(x-.24,-corner_y)]
            verts.extend((xx,yy,z) for xx,yy in ring)
        faces=[]
        for k in range(len(levels)-1):
            for j in range(12):
                a=k*12+j; b=k*12+(j+1)%12
                c=(k+1)*12+(j+1)%12; d=(k+1)*12+j
                # Side/corner patches share the same physical diagonal after
                # both X and Y mirroring: outer-low to inner-high. Explicit
                # triangles prevent the Boolean/exporter from choosing a
                # different non-planar quad diagonal than side_y().
                if abs(verts[a][0])<abs(verts[b][0])-1e-8:
                    faces.extend(((a,b,d),(b,c,d)))
                else:
                    faces.extend(((a,b,c),(a,c,d)))
        faces += [tuple(reversed(range(12))),tuple(range(48,60))]
        shell=self.poly("body_open_shell_v07",verts,faces,"blue",solid=True)
        if self.lod==2:
            return
        inner=shell.copy(); inner.data=shell.data.copy()
        bpy.context.collection.objects.link(inner)
        for v in inner.data.vertices:
            v.co.x*=.993; v.co.y*=.947
            v.co.z=3.03+(v.co.z-3.03)*.945
        self.cut(shell,inner)
        for end in (-1,1):
            for side in (-1,1):
                self.cut(shell,self.sheet("front_aperture_cutter_v07",front_loop(side,.004),
                    lambda u,v,e=end:(e*(self.front_x(v)+.35),u,v),"black",.70,(end,0,0)))
                for which in ("front","rear"):
                    self.cut(shell,self.sheet("side_aperture_cutter_v07",side_window_loop(end,which,.004),
                        lambda u,v,s=side:(u,s*(self.side_y(u,v)+.35),v),"black",.70,(0,side,0)))
        self.bevel(shell,.006,2 if self.lod==0 else 1)
        shell["true_window_apertures"]=12
        shell["corner_lands"]=4
        shell["corner_setback_m"]=.24
        shell["detail_v07_component"]="faceted_aperture_shell"

    def cabs(self):
        super().cabs()
        rebuild_side_cab(self)

    def sides(self):
        before=set(bpy.context.scene.objects)
        super().sides()
        # Keep the independent cab door and its inner grab clear of adjacent
        # access covers. These panels lie on the untapered central side plane.
        for obj in set(bpy.context.scene.objects)-before:
            if obj.name.startswith(("small_access_gap_v05","small_access_skin_v05","access_panel_screw")):
                obj.location.x+=.30
            elif obj.name.startswith("auxiliary_grille_"):
                obj.location.x-=.30

    def underframe(self):
        super().underframe()
        refine_underframe(self)

    def coupler(self,end):
        super().coupler(end)
        add_pilot_returns(self,end)

    def roof(self):
        from roof_details_v07 import build_roof
        build_roof(self)


def build(lod,gen):
    for key in list(bpy.context.scene.keys()):
        if key.startswith(("body_detail_","refinement_","silhouette_")):
            del bpy.context.scene[key]
    build_body(lod,gen,SilhouetteBuilder)
    if lod<2:
        panes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("transparent_pane")]
        inner=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("cab_interior")]
        gen.join_objects(inner,"cab_interior")
        for i,obj in enumerate(panes): obj.name=f"glazing_{i:02d}"
        bpy.context.scene["glazing_count"]=len(panes)
        bpy.context.scene["cab_openings"]=12
    for tag,prefix in (("body_v05_component","body_detail_"),("detail_v06_component","refinement_"),
                       ("detail_v07_component","silhouette_")):
        counts=Counter(o.get(tag) for o in bpy.context.scene.objects if o.get(tag))
        for name,count in counts.items(): bpy.context.scene[prefix+name]=count
