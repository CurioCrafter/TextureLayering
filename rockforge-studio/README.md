# RockForge Studio 1.0.0

A standalone Blender add-on for seeded geological formations, editable quad meshes, real PBR texture baking, and game exports. This is a new implementation, not a dependency on the previous failed RockForge/ReefForge downloads.

## GitHub downloads

Download the files from the **RockForge Studio 1.0.0** release in this repository. Install **RockForge-Studio-1.0.0.zip**. **RockForge-Studio-Complete.zip** contains that installer, source code, tests, three Blender example scenes, GLB exports, LODs, 2K textures, actual renders, topology views, and verification records. **SHA256SUMS.txt** records the hashes of the release assets.

Release page: https://github.com/CurioCrafter/TextureLayering/releases/tag/rockforge-studio-v1.0.0

The release workflow publishes only after native installation tests and example-scene reopen checks pass. GitHub hosts these release files; they do not depend on a ChatGPT sandbox link. The implementation is isolated in `rockforge-studio/` on the `rockforge-studio` branch. The existing texture editor and main branch are unchanged.

## Real output

The pictures below are native Blender renders of generated **low-poly meshes with baked textures**, not concept art or high-detail source meshes substituted for the exported assets. The topology images show the editable quad cage.

![Jointed basalt](https://github.com/CurioCrafter/TextureLayering/releases/download/rockforge-studio-v1.0.0/Basalt.jpg)
![Actual editable quad topology](https://github.com/CurioCrafter/TextureLayering/releases/download/rockforge-studio-v1.0.0/Basalt-topology.jpg)
![Coastal limestone](https://github.com/CurioCrafter/TextureLayering/releases/download/rockforge-studio-v1.0.0/Limestone.jpg)
![Fractured slate](https://github.com/CurioCrafter/TextureLayering/releases/download/rockforge-studio-v1.0.0/Slate.jpg)

## Installation

In Blender choose **Edit > Preferences > Add-ons > Install from Disk**, select `RockForge-Studio-1.0.0.zip`, and enable **RockForge Studio**. In the 3D View press **N**, then open **RockForge**. Install the small installer ZIP, not the Complete ZIP or repository source archive.

The legacy add-on ZIP contains one `rockforge_studio/` module folder. No pip dependencies, API keys, paid services, or external texture downloads are required. The example Blender scenes open without installing the generator.

## Workflow

Choose a geology preset, seed, mesh budget, and output folder. **Build Mesh** constructs and retopologizes a formation. **Build + Bake** also writes and packs BaseColor, tangent-space Normal, Roughness, and AO maps. Each operation creates a new asset rather than replacing an existing asset. It appears at the 3D cursor. A hidden high-detail source is retained in its collection and parented to the low mesh, so moving the asset also moves its bake source.

**Bake Active** updates textures from the retained source. **Export GLB** exports only the selected baked low mesh or LOD with embedded textures. **LODs** creates hidden 50% and 25% meshes. **Collision** makes a hidden convex hull. Reveal these objects in the Outliner; select a baked LOD to export it separately.

**Variations** generates consecutive seeds in a spaced row without baking every option. Select useful versions and bake those. **Load Settings from Active** restores the shape parameters saved on a generated rock. **Inspect Topology** writes the mesh report to a Blender text block called `RockForge Mesh Report`.

The optional **Reference retopology** operator creates a clay quad copy of a closed manifold mesh. It transfers **shape only**, not the reference's textures, and preserves the original mesh, materials, and visibility.

## Presets and controls

Six starting presets: jointed basalt, coastal limestone, fractured slate, bedded sandstone, fractured granite, and submerged bedrock. Shape controls include width, depth, height, joint-block count, angularity, erosion, bedding, tilt, algae, and wetness. Formation choices are an outcrop, ridge, or single boulder.

The seed determines the high-detail shape. Native QuadriFlow may produce slightly different topology across Blender versions and thread configurations. **Target quads is approximate.** Six thousand quads is approximately twelve thousand game triangles. Use the actual mesh report, not the requested target, for final budgets.

Source resolution is measured in voxels across the longest dimension. Start at 128–176. Textures range from 512 to 4096 pixels. Use 512 for iteration and 2048 for close-up assets. High resolution, large block counts, and 4K bakes need more memory and processing. Native remeshing and baking are synchronous: Blender can appear busy until the operation completes.

## Implementation

Obliquely fractured polyhedral blocks are joined over an irregular rock base and voxel-unioned. Detached debris is discarded, then spatially continuous geometric erosion adds weathering. Native QuadriFlow builds an editable quad cage and projection conforms it to the detailed surface. UVs are generated after retopology. Invalid/nonmanifold or non-quad results are rejected rather than silently replaced with a decimated triangle mesh.

The seamless source shaders combine mineral variation, granular weathering, warped hairline fractures, bedding, microrelief, algae, and wetness. Cycles performs actual selected-to-active texture baking. PNGs are both written to disk and packed into the Blender scene. Baking and export share a shortest-diagonal triangulation modifier; the editable base mesh remains all quads. The topology pictures intentionally show those original quad edges.

The GLB material includes normal data and packed occlusion/roughness. The extra material settings group matches the tested Blender 4.5/5.2 glTF import schemas. Game exports exclude the source high mesh, studio floor, lights, and camera.

## Validation and limits

The release workflow tests the actual ZIP in clean Blender profiles: installation, registration, properties, generation, all-quad topology, manifoldness, volume, connectivity, UV bounds, deterministic source shapes, settings restore, actual bakes, texture files, render-state restoration, GLB parsing and native reimport, LOD reduction/export, convex collision, reference preservation, batch variations, saving, unregistering, and reregistering. Eighteen preset/seed/formation combinations are also exercised. See the release's **Verification.json** for actual results.

This is not a promise of perfect topology or photorealism for every possible parameter combination. Structural checks do not prove optimal quad flow or exclude every self-intersection. Low polygon budgets can soften creases; extreme cavities need visual inspection. LODs reuse normal maps and require viewing-distance checks. Convex collision does not preserve caves. Reference texture transfer is not implemented. A polygon count is not a Meta Quest frame-rate guarantee.

## Reproduce

```sh
python build.py
blender --background --factory-startup --threads 4 --python-exit-code 1 --python tests/verify.py -- dist/RockForge-Studio-1.0.0.zip output/verification45
blender --background --factory-startup --threads 4 --python-exit-code 1 --python tests/produce.py -- matrix output
blender --background --factory-startup --threads 4 --python-exit-code 1 --python tests/produce.py -- gallery output BASALT
```

Repeat gallery generation for LIMESTONE and SLATE. The GitHub workflow also runs Blender 5.2.1, reopens saved scenes, captures a real GUI window in Xvfb, verifies archive integrity, and publishes release assets.

Code license: GPL-3.0-or-later. The generated example geometry and procedural texture pixels do not contain third-party scan assets or downloaded image textures. The original user-supplied reference `.blend` is not redistributed.
