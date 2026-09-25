# Editing and incremental build

## Current release: v0.37

Open the two editable near-LOD scenes in `source/fxn5c_v37_source/`. Blender 5.2 is used. Mid/far scenes are in its `runtime/final37_*.blend`; these selected source scenes are versioned despite the generic runtime ignore rule. Packed textures and relative source texture files are included. No new FBX is supplied for v0.37.

Download `FXN5C_SourceKit_v0.37.zip` from Releases for the complete sibling `fxn5c_v36_source` input baseline. The automatically generated GitHub Source code archives do not contain that baseline. Keep it immutable. `build_v37.py` and `shutters_v37.py` are the authoritative recipe; arbitrary edits to final `.blend` files do not automatically flow back into the native exporter. Small-louver motion uses native `.ani`, not Blender Actions. Large louvers have a fixed open transform.

Run build/normalization and geometry/readback work with Blender; run native and options checks with the appropriate Python interpreter. Dependencies include NumPy, lupa and Pillow; no interpreter or font binaries are bundled. See `source/fxn5c_v37_source/README_V37.md` for the sequence. Historical script imports are retained. A fresh-machine one-command build has not been certified.

Candidate reports describe the tested v0.37 construction. Publication changes descriptions and documentation only; all 1,152 packaged native resource files are unchanged. Therefore candidate hashes for description metadata are historical, not hashes for the public description. See `PUBLICATION_CHECKS_V37.json`. New geometry changes require new checks. Offline previews do not replace gameplay testing.

## Historical v0.24 documentation

The following describes the retained old source, not the current release.

## Editing without a rebuild

Open either `.blend` in `source/fxn5c_v24_source/` with Blender 5.2. Both are editable LOD0 scenes. Packed textures are included; original fonts and reference pictures are not needed merely to inspect the existing mesh lettering. Six static FBXs in `fbx_import/` are provided for interchange, not as fully rigged animations.

## Historical dependencies

The v0.24 build is an incremental native-resource patch, not a generic export of arbitrary edits to the final v0.24 scene. It loads immutable v0.23 scenes, reapplies revision routines and patches native geometry. To contribute geometric changes, understand the revision scripts and extend the pipeline or design a replacement exporter; do not expect edits to the final `.blend` alone to survive a full regeneration.

The SourceKit release attachment supplies these sibling directories:

```text
source/
  fxn5c_v22_source/  # older reconstruction baseline
  fxn5c_v23_source/  # immutable v0.24 input scenes/native resources
  fxn5c_v24_source/  # current scenes, scripts, native game resources
```

Only v0.24 is tracked in the main Git repository to keep historical binary baselines out of routine clones. Extract the SourceKit to a separate working directory when investigating a full rebuild. Keep baseline geometry and native resources unchanged. Runtime LOD caches are intentionally excluded; the uncached fallback path and these redistributed baseline subsets have not yet been end-to-end certified in a clean environment.

Use Blender 5.2 for scripts importing `bpy`; install Python dependencies from `requirements.txt` into the appropriate interpreter. Lua validation needs lupa; do not assume installation into system Python makes it available in Blender. Regenerating lettering requires appropriately licensed fonts listed in THIRD_PARTY_NOTICES.md, or deliberate font replacement.

## Verification sequence

The retained `SOURCE_README_V24.md` describes the original build order and limitations. Important entry points: `build_release_v24.py`; `verify_native_v24.py`; `audit_native_patch_v24.py`; `audit_catalogue_v24.py`; source/front/roof/light audits; native FBX export and audit; then native readback previews.

For the roof saved-source check use `audit_roof_v24.py -- --final` through Blender, not the default reconstruction probe. Existing audit results must not be reused as proof for changed files. Historical packaging scripts expect historical reports and output layout; this public source kit intentionally excludes private runtime logs and is not a byte-for-byte copy of those old source archives.

The public packaging step changes author, description and license documentation only. Its report verifies that all files under the v0.24 native `res/` subtree retain their original SHA-256 values. That is not a substitute for geometry auditing after subsequent modifications or for game testing.

Public `.blend` copies have packed-image paths rebased to relative paths; mesh coordinates, polygon/material assignments and object transforms were fingerprinted before and after saving to check they were unchanged. Historical source trees retain some unused lamp resources for reconstruction; the game ZIP uses the original v0.24 release resource whitelist and excludes those unused files. Original local archives are not overwritten.

The six public FBXs also have local image/document path strings replaced with relative references. Every other parsed FBX property, including geometry arrays and material bindings, was checked unchanged after reserialization. These portability checks do not claim new in-game testing.

## Still to improve

Make the build portable, replace local font-path assumptions, remove unnecessary historical stages, and add clean-environment build tests. No CI job or one-command reproducibility guarantee is claimed in this release.
