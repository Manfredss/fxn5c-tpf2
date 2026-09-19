# FXN5C v0.24 source

The two `fxn5c_source.blend` / `fxn5c_jinwen_source.blend` files are editable LOD0 scenes. The six FBXs are static native-readback snapshots at LOD0/1/2 with the forward/front lamp configuration selected and the other five conditional lamp instances removed. They do not contain an animated train or lamp-control rig. The game reads MDL/MSH resources, not FBX. Source textures are packed/rebased; fonts and reference images are not distributed.

## Incremental reconstruction and dependencies

This is an incremental v0.23-to-v0.24 source package, not a standalone regeneration environment. Keep an adjacent, immutable `fxn5c_v23_source` directory containing the released v0.23 editable LOD0 scenes and native resources. The build loads those LOD0 scenes and patches their corresponding native meshes. Do not replace that baseline with the newly saved v0.24 scenes.

`prepare_scene_v24.py` first uses local `runtime/baseline24_<style>_lod1.blend` / `lod2.blend` caches. If unavailable, it uses the adjacent v0.23 `runtime/baseline23_<style>_lod*.blend` caches and reapplies the unchanged v0.23 corrections. If those caches are also absent, `prepare_scene_v23.py` reconstructs the older baseline through the retained v0.20–v0.22 pipeline before the v0.23 corrections are reapplied. Its texture fallback can require the adjacent `fxn5c_v22_source` directory. Preserve that older baseline for a clean uncached rebuild; runtime `.blend` caches are deliberately not included in this archive.

Use Blender 5.2 background Python for geometry, source, render and FBX scripts. Requirements are listed in `requirements.txt`; Lua validation uses lupa. Locally installed SimSun, Arial Bold, STXinwei and KaiTi (`simkai.ttf`, used by the inherited front-lettering helper) are needed when regenerating lettering. Their glyph geometry, not the font binaries, is distributed. The user reference pictures are not runtime inputs.

## Build and verification order

1. `build_release_v24.py` in Blender.
2. `verify_native_v24.py`, followed by `audit_native_patch_v24.py` and `audit_catalogue_v24.py`.
3. Blender `audit_sources_v24.py`, then Blender `audit_roof_v24.py -- --final`; run `audit_lights_v24.py` as specified by its native audit entry point. The saved-source audit uses `audit_front_v24.py` without reapplying edits to final saved sources. The roof audit's `--final` mode loads the actual saved sources and checks all 26 native panes; its default mode is only a runtime reconstruction probe. Neither mode is an in-game check.
4. Blender `fbx_native_v24.py`, then Blender `audit_fbx_v24.py`.
5. Blender `render_native_v24.py` only after fresh native verification. Then `ui_icons_v24.py` and `make_review_v24.py`.
6. `package_release_v24.py`, then `release_sanity_v24.py`.

Current reports bind actual input hashes. Do not substitute inherited v0.23 reports, old images or a pre-build source probe for the final native verification. The catalogue audit has an isolated `--fixtures-only` mode; its 555 Lua cases do not test the final emitted models until the normal post-build audit also runs.

## Geometry and visibility implementation

The body patch uses the retained `native_patch_v23.py` triangle-delta method at 10 micrometre positional-key precision. Unchanged native attributes and surviving indices are retained; changed body triangles are replaced. `runtime/patch_inputs_v24` holds before/after evidence, not extra game assets. Roof-related glazing changes are exported under their existing native attachment names. Running gear and rod resources are not a new v0.24 mechanism.

`baseline_tessellation_v24.py` aligns one Jinwen LOD2 baseline roof patch before deformation. The editable five-triangle subdivision and released three-triangle subdivision have the same exact oriented perimeter, material and area. Only those faces are retessellated; no boundary vertices are moved and the 10 micrometre matcher is not relaxed. The build manifest records the bounded proof, which the native audit checks independently.

The AFTER export omits triangles whose float32 positions have an exactly zero cross product. This is an export-only cleanup: it preserves all valid corner indices, positions, normals, UVs and tangents without reevaluating the source polygons. The editable source may retain non-rendering degenerate caps. The BEFORE export and released native baseline are not sanitized; the independent delta audit checks all resulting removals against that actual baseline.

`front_revision_v24.apply_common()` shifts the two ends' existing railway emblem and “复兴” geometry by +0.10 m and clips the Jinwen blue band to a central 1.10 m white gap. `apply_number()` runs after every number variant is generated. Pointwise front-surface offsets and emblem relief are retained. Side lettering is not moved.

`light_revision_v24.py` defines six native conditional instances for front/inner/back positions and forward/backward direction, using two shared direction meshes per detailed LOD. The frozen per-number inner-lamp map is 5 white / 5 red; it is not a claim about real-unit electrical wiring. The new moon-white emitter has its own material and tiny texture, without a global shader replacement. Preview scripts register that material before native loading, select the actual model configuration and record the selected IDs. Singleton preview deduplication is explicitly reported; engine category exclusivity remains untested.

These are selected static geometry, material and configuration checks, not CAD certification, full mechanical simulation or proof that every hidden part is connected. The earlier rod remains an LBS approximation, not an exact rigid bearing mechanism. No game installation, workshop upload or in-game verification is included.
