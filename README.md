# Surface Layer Studio

Surface Layer Studio is a Blender 4.5 LTS extension for building and painting ordered PBR material layers directly on UV-mapped meshes. It was designed around detailed ship interiors: painted steel, exposed edges, rust, oil, damp staining, markings, and emissive control panels can each live on an independent grayscale mask.

White mask paint reveals a layer, black hides it, gray creates partial transitions. Brush opacity controls each stroke; layer opacity controls the finished layer. The stack remains editable and the generated shader can be repaired from metadata at any time.

## Included features

- Dynamic top-to-bottom layer list with no hard-coded layer count.
- Independent UV paint mask per layer.
- Native Blender Texture Paint brushes with Reveal, Hide, Soften, radius, stroke opacity, pressure, falloff, spacing, and airbrush controls.
- Base Color, Roughness, Metallic, Normal, Height/Bump, Ambient Occlusion, and Emission channels.
- Normal, Multiply, Overlay, Soft Light, Screen, Add, Darken, and Lighten color blends.
- OpenGL and DirectX normal-map handling.
- Per-layer tint, channel strength, UV map, offset, scale, and rotation.
- Solo, visibility, lock, duplicate, reorder, mask inversion, fill, resize, preview, and repair operations.
- PBR-set auto-import from common filename suffixes such as `BaseColor`, `Roughness`, `Metallic`, `NormalDX`, `Height`, `AO`, and `Emissive`.
- Assign the complete stack to selected faces and optionally guard paint strokes to selected faces.
- UV audit for missing/zero-area/out-of-tile/exact-overlap cases plus explicit Smart UV Project.
- A practical seven-layer **Ship Interior Starter**.
- Independent single-user copies of shared materials and all masks.
- Embedded generated masks, packing for external mask/source images, and PNG mask export.
- Channel previews for mask, base color, roughness, metallic, normal, height, and emission.

## Install in Blender 4.5.11

Download the tested [Surface Layer Studio 1.0.0 extension ZIP](dist/surface_layer_studio-1.0.0.zip), then:

1. Open **Edit > Preferences > Get Extensions**.
2. Open the dropdown in the upper-right and choose **Install from Disk**.
3. Select `dist/surface_layer_studio-1.0.0.zip`.
4. Enable **Surface Layer Studio** if Blender does not enable it automatically.
5. In a 3D Viewport, press `N` and open the **Surface Layers** tab.

The release zip is an official Blender Extension archive. Its `blender_manifest.toml` requires Blender 4.5.0 or newer and declares file access because PBR images can be loaded and masks can be exported.

## First ship-interior workflow

1. Select the interior mesh. To limit the whole material to certain panels, enter Edit Mode and select those faces first.
2. Open **Surface Layers** and choose **Build Ship Interior Starter**. Existing materials are copied by default; selected Edit Mode faces receive a separate material slot.
3. Open **Surface Scope & UV**. Run **Audit UVs**. If the mesh is not unwrapped, use **Smart UV Project** deliberately or open Blender's UV Editing workspace and unwrap it yourself.
4. Select a layer. Use **Import PBR Set** or assign individual channel images in **Layer Textures & PBR**.
5. New overlay masks start black. Open **Paint Layer Mask**, choose **Reveal**, set **Stroke Opacity**, then click **Start Mask Painting**. Paint in either the 3D Viewport or Image Editor.
6. Use **Hide** to remove coverage, **Soften** for transitions, and **Selected Faces** to prevent new strokes spilling onto unselected faces.
7. Use **Layer Opacity** for the final contribution. This is intentionally separate from Stroke Opacity.
8. Use **Files, Preview & Stack > Protect Painted Work**. Generated masks are already embedded in the `.blend`; external masks can be packed, and all masks can be exported as PNG files.

## Three different kinds of scope

- **Material assignment** decides which mesh faces use the entire stack.
- **Layer mask** decides where one layer appears on those faces.
- **Selected-face paint guard** only prevents new strokes outside selected faces; it does not erase existing pixels.

Keeping these separate avoids a common Blender failure mode where a user expects a layer mask to change material slots, or expects face selection to rewrite old paint.

## Important limitations

- Version 1.0 creates regular 0–1 UV masks. Source textures may be tiled images, but the add-on does not yet create or fill UDIM paint masks.
- Mirrored or overlapping UVs share pixels. A stroke can therefore appear on every face using the same UV area; the UV audit reports exact overlaps but cannot prove every geometric overlap.
- “Unlimited layers” means the collection has no software cap. Every visible layer adds shader nodes, texture sampling, compilation time, and image memory. The verified 20-layer test rebuilt in about 1.2 seconds on this machine, but production performance depends on hardware, texture resolution, and channel count.
- A byte RGBA mask is roughly 16 MB at 2K and 64 MB at 4K before mipmaps/driver overhead. Use 4K only on hero surfaces; split a ship interior into sensible material regions.
- Surface Layer Studio preserves an existing shader link and works on a material copy by default. It cannot translate an arbitrary custom shader into editable PBR channels, so the layered result starts from the material's basic color/roughness/metallic values. **Disable and Restore Material** reconnects the preserved shader.
- Flattened PBR baking, curvature generators, triplanar layers, decals, groups, and UDIM-mask authoring are not part of this release. They were excluded rather than shipped as fragile placeholders.

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for channel naming, troubleshooting, and a detailed ship workflow.

## Verification

The repository contains pure-Python tests and Blender 4.5.11 source, save/reopen, extension validation, package inspection, and installed-copy smoke scripts. Run `scripts/verify.ps1` after changing the add-on.
