"""Drop orphan glyph curves before packing a mesh-only editable deliverable."""
from pathlib import Path
import bpy

def clean_fonts():
    assert not any(o.type == "FONT" for o in bpy.data.objects)
    for curve in list(bpy.data.curves):
        if not curve.users:
            bpy.data.curves.remove(curve)
    for font in list(bpy.data.fonts):
        if font.filepath and font.filepath != "<builtin>":
            bpy.data.fonts.remove(font, do_unlink=True)
        elif not font.users:
            bpy.data.fonts.remove(font)
    external = [f.filepath for f in bpy.data.fonts if f.filepath and f.filepath != "<builtin>"]
    assert not external, external

if __name__ == "__main__":
    source = Path(__file__).resolve().parent / "fxn5c_source.blend"
    bpy.ops.wm.open_mainfile(filepath=str(source))
    clean_fonts()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(source))
    print("Editable v13 source: orphan glyph curves and external font data removed; mesh geometry unchanged.", flush=True)
