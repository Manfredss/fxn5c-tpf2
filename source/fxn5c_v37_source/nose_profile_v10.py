"""Photo-estimated lower nose planes, distinct from the retained window lands.

These are modeling dimensions, not a manufacturer drawing. Coordinates use the
positive cab/side; caller mirrors X/Y. Two explicit triangles match hull().
"""
from mathutils import Vector
from geometry_v07 import SilhouetteBuilder


def front_half(z):
    if z<=2.55:
        return 1.30+.18*max(0,min(1,(z-1.58)/.97))
    return SilhouetteBuilder.front_half(z)


def corner_width(z):
    return 1.65-front_half(z) if z<=2.55 else SilhouetteBuilder.corner_width(z)


def corner_x(y,z):
    """Intersect a longitudinal line with the ACTUAL piecewise triangle plane."""
    y=abs(y)
    a=Vector((11.04,1.30,1.58)); b=Vector((10.80,1.65,1.58))
    c=Vector((10.80,1.65,2.55)); d=Vector((11.04,1.48,2.55))
    diagonal_y=1.30+.35*(z-1.58)/.97
    p,q,r=(a,b,c) if y>=diagonal_y else (a,c,d)
    n=(q-p).cross(r-p)
    return p.x-(n.y*(y-p.y)+n.z*(z-p.z))/n.x


def corner_point(end,side,z,fraction):
    y=front_half(z)+corner_width(z)*fraction
    x=corner_x(y,z) if z<=2.55 else SilhouetteBuilder.front_x(z)-.24*fraction
    return Vector((end*x,side*y,z))


def corner_normal(end,side,z,fraction):
    across=corner_point(end,side,z,fraction+.0001)-corner_point(end,side,z,fraction-.0001)
    up=corner_point(end,side,z+.0001,fraction)-corner_point(end,side,z-.0001,fraction)
    n=across.cross(up).normalized()
    if n.dot(Vector((end,side,0)))<0: n.negate()
    return n


def rebuild_grey_belt(b):
    import bpy
    for o in list(bpy.context.scene.objects):
        if o.name.startswith(('nose_lower_grey','nose_grey_belt_v10')):
            bpy.data.objects.remove(o,do_unlink=True)
    lo,hi=1.58,1.78
    for end in (-1,1):
        b.poly('nose_grey_belt_v10',[(end*11.046,-front_half(lo),lo),
            (end*11.046,front_half(lo),lo),(end*11.046,front_half(hi),hi),
            (end*11.046,-front_half(hi),hi)],[(0,1,2,3)],'dark',normal=(end,0,0))
        for side in (-1,1):
            # Include where the existing shell diagonal meets each height;
            # otherwise a decorative quad would bridge across the real fold.
            points=[]
            for z in (lo,hi):
                for y in (front_half(z),1.30+.35*(z-1.58)/.97,1.65):
                    points.append((end*(corner_x(y,z)+.005),side*y,z))
            faces=[f for f in [(0,1,4),(0,4,3),(1,2,5),(1,5,4)]
                   if (Vector(points[f[1]])-Vector(points[f[0]])).cross(Vector(points[f[2]])-Vector(points[f[0]])).length>1e-9]
            b.poly('nose_grey_belt_v10',points,faces,'dark',normal=(end,side,0))
