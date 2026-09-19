"""Retain baseline cab UV bytes only after proving a two-ULP-only difference.

Blender's procedural LOD1 UV calculation may round two float32 steps differently
after a save/reload. No geometry, normals, tangents, indices or layout changes
are permitted by this compatibility step. Full independent preservation tests
still verify the resulting resources; this is not an audit exception.
"""
from pathlib import Path
import re
import struct


def check_uv_only(previous, current, descriptor):
    if previous == current:
        return 0
    match = re.search(r'uv0\s*=\s*\{\s*count\s*=\s*(\d+),\s*numComp\s*=\s*2,\s*offset\s*=\s*(\d+)', descriptor)
    if not match:
        raise RuntimeError('Cab mesh has no unambiguous UV vertex attribute')
    size, start = map(int, match.groups()); end = start + size
    if size % 4 or not 0 <= start < end <= len(current):
        raise RuntimeError('Invalid cab UV byte range')
    if len(previous) != len(current) or previous[:start] != current[:start] or previous[end:] != current[end:]:
        raise RuntimeError('Cab resource changed outside UV values; refusing baseline preservation')
    changed = 0
    for (a,), (b,) in zip(struct.iter_unpack('<I', previous[start:end]), struct.iter_unpack('<I', current[start:end])):
        if (a & 0x7f800000) == 0x7f800000 or (b & 0x7f800000) == 0x7f800000:
            raise RuntimeError('Nonfinite cab UV value')
        if (a >> 31) != (b >> 31) or abs(a-b) > 2:
            raise RuntimeError('Cab UV difference exceeds two float32 ULPs')
        changed += a != b
    return changed


def preserve(root, baseline):
    root, baseline = Path(root), Path(baseline)
    results = []
    for model in ('fxn5c', 'fxn5c_jinwen'):
        relative = Path('staging/codex_fxn5c_1/res/models/mesh/vehicle/train') / model / 'cab_interior_lod1.msh'
        old, new = baseline / relative, root / relative
        if old.read_bytes() != new.read_bytes():
            raise RuntimeError('Cab mesh descriptor changed; refusing baseline preservation: '+model)
        old_blob, new_blob = Path(str(old)+'.blob'), Path(str(new)+'.blob')
        previous, current = old_blob.read_bytes(), new_blob.read_bytes()
        count = check_uv_only(previous, current, new.read_text(encoding='utf-8'))
        if count:
            new_blob.write_bytes(previous)
        results.append({'model': model, 'retained_uv_values': count})
    return results


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    print(preserve(root, root.parent/'fxn5c_v19_source'))
