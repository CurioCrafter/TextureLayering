# Surface Layer Studio User Guide

## Mental model

The generated material begins with an undercoat, then composites enabled layers from the pinned base upward. The layer list is shown like an image editor: the top row is visually topmost. Each layer factor is:

`paint mask × layer opacity × optional base-texture alpha`

That factor controls base-color blending and the layer's roughness, metallic, normal, height, and emission contribution. A black mask is zero influence, white is full influence, and partial values produce a transition.

The shader uses a UV Image Texture for every mask. Blender's normal Texture Paint engine edits that image, so brush pressure, radius, falloff, UV Editor painting, undo, and viewport projection behave like native Blender tools.

## Preparing a ship

Large ships are easier to author when physically different areas use separate materials: engine room, bridge, crew spaces, cargo deck, and exterior hull are good boundaries. A single huge 4K mask stack for the entire ship wastes memory and makes UV overlap harder to diagnose.

1. Apply or inspect object scale before unwrapping.
2. Mark seams around panel boundaries, door frames, trim, and hidden transitions.
3. Unwrap manually for hero rooms. Smart UV Project is useful for drafts and dense hard-surface interiors but is intentionally never run automatically.
4. Leave padding around islands so paint seam bleed has room.
5. Avoid mirrored UVs anywhere asymmetric grime, text, rust streaks, or unique damage is required.
6. Select the room/panel faces in Edit Mode before creating a stack if the material should apply only there.

## Ship Interior Starter

The preset creates:

1. **Emissive Panels** — blue-white emission for lamps and displays.
2. **Salt & Damp Staining** — pale, rough soft-light staining.
3. **Oil & Engine Grime** — dark, lower-roughness multiply layer.
4. **Rust & Oxidation** — rough orange-brown overlay.
5. **Exposed Edge Metal** — darker metallic wear.
6. **Secondary Paint & Markings** — nonmetallic paint or warning colors.
7. **Painted Steel Base** — pinned visible foundation.

The overlays begin hidden. Select one, choose Reveal, and paint only where it belongs. If you prefer to start with a texture visible everywhere, change **New Overlay Mask** to White or fill that layer's mask white.

## Loading PBR textures

Choose any image in a set with **Import PBR Set**. Files in the same folder are grouped by their shared name and common channel tokens:

- Base Color: `BaseColor`, `Base_Color`, `Albedo`, `Diffuse`, `Color`
- Roughness: `Roughness`, `Rough`
- Metallic: `Metallic`, `Metalness`, `Metal`
- Normal: `NormalGL`, `NormalDX`, `Normal`, `NRM`
- Height: `Height`, `Displacement`, `Disp`, `Bump`
- Ambient Occlusion: `AO`, `AmbientOcclusion`, `Occlusion`
- Emission: `Emission`, `Emissive`, `Emit`

Color and emission images use sRGB. Masks, roughness, metallic, normals, height, and AO use Non-Color. A filename containing `DX` or `DirectX` automatically selects green-channel inversion; everything else defaults to OpenGL.

## Painting masks

1. Select the layer in the list.
2. Confirm the status says **Painting mask: _your layer_**.
3. Set **Stroke Opacity**. Low values build grime gradually; `1.0` is appropriate for sharp paint damage or markings.
4. Click **Start Mask Painting**. The add-on activates the correct material slot, Image Texture node, explicit Image Paint canvas, native 4.5 brush asset, and Texture Paint mode.
5. Use Reveal (white), Hide (black), or Soften.
6. Click **Finish Mask Painting** to leave Texture Paint and restore Edit Mode when that is where painting began.

If the active layer is locked, painting and destructive mask actions are refused. Filling or resizing a mask is destructive to that image, but Blender undo is enabled and the old image is preserved when creating a replacement mask.

## UV and surface warnings

The audit reports:

- no UV map;
- faces whose UV polygon has zero area;
- faces with coordinates outside the regular 0–1 tile;
- groups of faces with exactly matching UV coordinates.

The exact-overlap test catches typical mirrored/stacked islands, but it is not a general polygon-overlap solver. Always inspect the UV Editor when a projected brush appears on an unexpected face.

Materials and their masks are shared Blender datablocks. When the panel reports multiple material users, use **Make Stack Single User** before adding object-specific dirt. It duplicates both the material and every paint mask while continuing to share read-only PBR source textures.

## Saving painted work

Generated masks are internal Blender images and their pixels are stored in the `.blend`. **Protect Painted Work** updates those images and packs any mask that came from an external file. **Pack Source Textures** is separate because PBR source sets can be large and a studio may prefer linked files.

**Export All Masks** writes PNG files to the configured folder. The default `//textures/masks/` is relative to the saved `.blend`; save the project first or choose an absolute directory.

## Repair and restore

Layer metadata and generated nodes are deliberately separate. If someone deletes or disconnects generated shader nodes, the panel reports an unhealthy stack. **Repair Stack** recreates owned nodes while leaving unrelated nodes untouched.

**Disable and Restore Material** removes all generated nodes and reconnects the shader that was attached to Material Output before conversion. Layer metadata and images remain in the file, but the stack is disabled.

## Troubleshooting

**The layer is invisible**

New overlays start with black masks. Paint Reveal or fill the mask white. Also check layer visibility, solo state, layer opacity, and Channel Preview.

**Painting appears somewhere else**

Inspect overlapping or mirrored UV islands. Enable Selected Faces to guard new strokes, or create unique UVs for asymmetric details.

**The whole object changed instead of selected panels**

Material assignment and masks are separate. Enter Edit Mode, select the intended faces, make the layered material active, and use Assign Stack to Selected Faces.

**Another object changed**

The material or mask is shared. Use Make Stack Single User.

**A normal map looks dented instead of raised**

Switch the layer between OpenGL (+Y) and DirectX (-Y).

**The viewport is slow**

Hide unneeded layers, lower mask/source resolution, split the ship into regional materials, and avoid assigning unused normal/height/emission channels. There is no collection cap, but GPU work is necessarily finite.
