# Surface Layer Studio 1.1 — Shipwreck Texture Desk

A Blender-native layered material and image-editing workspace for **Shipwreck Discovery**: corroded hulls, flooded machinery, algae-covered shelving, worn casino interiors, markings, and underwater props.

This update extends the original Surface Layer Studio rather than replacing its materials or paint system. It adds a dedicated two-pane workspace, a searchable material shelf, live procedural weathering, copy-on-edit image tools, and actual Cycles texture baking. The extension runs locally, with no API key, cloud service, downloaded material pack, or generative-AI dependency.

## What is new

| Area | Implemented in 1.1 |
| --- | --- |
| Workspace | Separate **Shipwreck Desk** with a 3D material view and native Image Editor; independent Library / Layers / Paint / Lab / Export tabs in the two sidebars. The source workspace layout is preserved. |
| Preset shelf | **48 editable presets**, six categories, procedural thumbnail guides, search, favorites, and paged browsing. |
| Complete recipes | **Eight** append-only layer recipes: wreck hull, engine room, submerged casino, slot-machine casing, galley shelving, dive signage, timber deck, and pipework. |
| Live weathering | Noise, streaks, cells, cracks, stripes, and tiles; object/world/UV coordinates, seed, coverage, transition, scale, axis stretch, color variation, roughness variation, and bump relief. |
| Placement | Upward/downward-facing accumulation and an adjustable world-Z waterline band, multiplied by the painted UV mask. |
| Image lab | **12** copy-on-edit operations: invert, levels/gamma, blur, grow, shrink, edge, normalize, flip X/Y, half-tile offset, grayscale, and threshold. One previous image per layer can be restored or used for A/B comparison. |
| Mask and normal tools | Seeded 2D paint-mask generation; height/mask-to-normal conversion with OpenGL/DirectX control; eight native mask-brush setting presets. |
| Projection | UV or object-box projection for color/scalar source textures. Tangent normal maps and painted masks remain UV-based. |
| Export | Real flattened BaseColor, Roughness, Metallic, Height, Emission, optional Normal/AO, plus packed **ORM** and a JSON manifest. Unique output folders; source objects and texture paths are retained. |

The existing ordered PBR stack, blend modes, import-by-filename, mask painting, selected-face assignment, UV audit, channel previews, material isolation, packing, and graph repair remain available in **Surface Layers**.

## Install

Use the supplied `surface_layer_studio-1.1.0.zip`, or obtain it from the **Blender integration** workflow's `blender-validation-<version>` artifact. Extract the workflow artifact first; install the inner extension ZIP, not the artifact wrapper. Workflow artifacts expire according to their retention setting.

To build the same extension from this branch, run `python scripts/build_extension.py` with Python 3.11 or newer. This creates `dist/surface_layer_studio-1.1.0.zip`. The older committed `dist/surface_layer_studio-1.0.0.zip` is a historical release, not this upgrade.

In Blender, save your work, then use **Edit → Preferences → Get Extensions → menu → Install from Disk** and select the **1.1.0** extension ZIP. When upgrading, disable the earlier copy and restart Blender before enabling the new one. Do not enable both a legacy add-on copy and the extension copy simultaneously.

Select a mesh, press **N** in the 3D Viewport, open **Shipwreck Desk**, and click **Open Shipwreck Desk**. Alternatively, the same button appears in the original **Surface Layers** panel. If the new sidebars select a different tab, click **Shipwreck Desk** once. Drag a sidebar's left border to widen it when working with large UI scaling.

## First useful workflow

1. Save a copy of your `.blend`. Select a UV-mapped mesh or unwrap it deliberately; the extension does not silently re-unwrap your asset.
2. In **Library**, set the mask size to 1K or 2K and append **Galley metal shelving** or **Wreck hull**. Recipes append layers; they do not clear the current stack. To limit a material to selected faces, create/assign the stack in Edit Mode first.
3. In **Layers**, select rust, algae, or sediment. Adjust coverage and scale, use upward-facing placement for deposited silt, and reduce procedural relief on distant props.
4. In **Paint**, choose a mask brush and **Start mask painting in 3D**. Hide removes local coverage; Reveal restores the procedural layer. Use the right-hand Image Editor for direct image painting and the **Lab** for copy-on-edit cleanup.
5. Finish painting, set channel preview to **Composite**, audit the UVs, and use **Export**. Import the resulting PNGs into your game engine using the manifest's channel and color-space conventions.

For the full workflow and the distinction between a procedural mask and a painted image, read [Shipwreck Desk guide](docs/SHIPWRECK_DESK.md). The [original layer guide](docs/USER_GUIDE.md) covers material assignment, PBR filename detection, paint guards, and shader restoration.

## Safety and limitations

These presets are original procedural **starting materials**, not scanned surfaces, trained AI outputs, or physically simulated corrosion. Import real PBR textures for additional realism. Swatches are 2D guides, not baked previews of the selected object. Barnacle relief does not create silhouette geometry; stencil paint does not generate lettering; glass frosting is an opaque deposit, not a transmission shader.

Regular 0–1 UVs are required for paint masks and export. UDIM authoring, layer groups, PSD round-tripping, mesh-aware curvature generators, arbitrary decal projection, and generative fill are not implemented. This is a specialized workflow upgrade, not a claim of feature parity or overall superiority to Ucupaint or Substance Painter.

The image lab is limited to 16 megapixels and bake resolution to 4K. Several full-resolution working buffers may be allocated: start at 1K/2K, especially on large interiors. The layer collection has no hard-coded count limit, but shader compilation, texture memory, and GPU cost increase with every visible layer. First-time material compilation can be slow. Baking uses Cycles CPU and is synchronous; entire-ship performance has not been benchmarked.

The lab preserves the source of its last edit, not an unlimited image history. Native Blender painting still edits the active image directly. Layer locks guard extension image-edit operations, not every possible edit through Blender's other tools. Pack external source images and save the `.blend` before closing.

## Verification

The implementation has been exercised in **Blender 4.5.11 LTS and 5.2.1 LTS on Linux**. Validation includes 26 pure-Python tests; 799 assertions per version in the new Blender integration script; original source/UI/import/save-reopen regressions; extension manifest validation; and real installation followed by a fresh-process test of the installed copy. The integration script performs an actual small eight-map bake and checks pixels, source preservation, and failure cleanup.

Native-window tests cover the workspace and panels with OpenGL software rendering. They do not establish Vulkan compatibility or production performance on your GPU. Windows/macOS installers and full ship-scale assets were not exercised in this environment. See [validation details](docs/VALIDATION.md) and the per-commit GitHub Actions results.

```sh
python scripts/build_extension.py
python -m pip install 'numpy>=1.26,<3'
python -m unittest discover -s tests -p 'test_*.py' -v
blender --background --factory-startup --threads 2 --python-exit-code 1 \
  --python tests/blender_desk_smoke.py -- --source-root . --output artifacts
```

The workflows rebuild the distributable from source and test both Blender versions. No Ucupaint source code or third-party texture pack is bundled. License: MIT.
