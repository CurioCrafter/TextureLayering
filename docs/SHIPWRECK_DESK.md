# Shipwreck Texture Desk — working guide

## Layout and navigation

**Open Shipwreck Desk** duplicates the current workspace and configures the duplicate as a 3D viewport plus native Image Editor. The original workspace's area layout is retained. Opening the desk again reuses its workspace. Allow Blender's UI event loop to finish the switch before clicking other workspaces. A failed setup reports its status rather than deliberately changing the original layout.

Both sidebars have Library, Layers, Paint, Lab, and Export. Their active tabs are independent, so Library can remain visible next to Lab. These are real Blender editors: orbit, pan, zoom, native image tools, brush assets, and ordinary workspace resizing remain available. Sidebar widths can be dragged wider. The extension does not replace Blender's menus or implement a separate desktop/web image application.

## Library and material recipes

The shelf includes eight presets in each of six categories: Corrosion, Marine growth, Sediment, Hull coatings, Interiors, and Markings. Search matches words in names, categories, and notes. Stars and filtering are saved with the scene, not an online account. Previous/Next move through eight cards per page. The swatches show approximate 2D patterns against a dark backing; they are not exact rendered samples of your geometry or imported maps.

**Add layer** appends an editable layer above the current stack. Its painted mask starts white so the procedural coverage is immediately visible. When the selected mesh has no managed material, the extension first creates a stack using the existing preservation/copy behavior. Existing layers are never cleared by a recipe.

| Recipe | Appended layers, bottom to top |
| --- | --- |
| Wreck hull | Faded naval teal, hull oxide, rust runoff, green biofilm, barnacle crust |
| Flooded engine room | Pitted iron, hull oxide, engine soot, oil seep, fine silt |
| Submerged casino | Faded upholstery, brown algae stain, mineral runoff, fine silt |
| Slot-machine casing | Chrome, rust runoff, verdigris, green biofilm |
| Galley shelving | Oxidized aluminum, hull oxide, accumulated grime, green biofilm, fine silt |
| Dive signage | Hazard stripes, hull oxide, salt residue, green biofilm |
| Timber deck | Teak, waterlogged wood, algal turf, sand dust |
| Pipework | White enamel, flaking oxide, rust runoff, calcareous deposits |

Recipes are surface treatments, not prop generators. Apply the slot-machine recipe to a casing material, not to a whole machine including its screen and controls. Assign separate materials to upholstery, metal, glass, signage, and lamps. The casino recipe describes a stained interior surface; it does not turn a model into a furnished casino.

To keep geometry-specific decisions under your control, UV generation is never automatic during preset application. Use the existing selected-face material tools and UV audit before painting. Make linked objects and materials local before adding presets. For a material shared by multiple objects, use **Make Single User** before painting when those objects need different masks.

## Live weathering versus image masks

A layer combines its painted UV mask with its procedural coverage and optional world-facing/waterline placement. White paint reveals the generated material; it does not force the material into places where the procedural coverage is zero. Black paint hides it. Layer opacity scales the result, while brush stroke opacity affects each stroke.

In Layers, use Coverage and Transition for broad coverage, Scale and Axis scale for feature size and stretch, and Seed for another pattern realization. Object coordinates follow local object units; World coordinates remain world-aligned; UV coordinates follow the layer's chosen map. The up/down controls use the world normal's Z direction. Waterline uses a triangular band around World Z with the specified half-width. These are art-direction masks, not fluid, sunlight, buoyancy, or ecological simulations.

Color and roughness variation use the procedural field. Procedural relief contributes bump detail, controlled jointly with the material's Bump Distance. It is not displacement geometry. An excessive Bump Distance can make thin rust look like large craters. Reduce it on shelving, flat bulkheads, signs, and distant assets.

The Layers black/white/gamma controls operate in the shader without rewriting the painted image. The Lab's similarly named controls instead process an image copy. White must exceed black. Pattern **None** disables live pattern coverage; color/roughness/relief variation can still use a noise field unless their strengths are zero.

The Lab's 2D generator creates a **new painted UV mask**, not a bake of the live 3D generator. Its six patterns are noise, streaks, cells, cracks, stripes, and tiles, plus a constant None option. Stripe and tile layouts are fixed periodic patterns; their 2D seed is not used. Generating a mask while leaving live weathering on combines both masks. Set the live pattern to None to judge the generated image alone.

## Painting and channel images

The eight brush presets change native mask-brush mode, radius, opacity, falloff, and spacing. They are not proprietary stamp alphas. **Start mask painting in 3D** specifically targets the active layer's mask. Reveal paints white, Hide black, and Feather uses Blender's native Soften mode. Blender 5.x's renamed brush and falloff properties are handled separately from 4.5's API.

Choose an Image target and **View / paint** to display a source channel in the native Image Editor. Create a new channel image or import a PBR set when it is empty. Painting a color image uses the native editor and brush controls; the mask brush presets remain grayscale mask tools. Direct native painting is in-place: duplicate or save important source images before painting them.

The source-projection setting offers UV and Object box for color/scalar images. Tangent-space normal maps always retain UV projection; painting masks also remain UV-based. This avoids pretending a tangent normal map can simply be box-projected. Imported image transforms remain editable. World/object procedural scale and UV texture tiling are different settings.

## Image lab

Each operation creates and packs a new image, swaps that channel to the result, and stores one prior image pointer per layer. **Restore last image edit** swaps the most recent edit back and forth for A/B comparison, including the normal-map convention when needed. It is not an unlimited persistent history. Blender Undo is available for the registered edit operators; continue saving versioned `.blend` files.

Invert, Levels/gamma, Blur, Grow, Shrink, Edge, Normalize, Flip X/Y, half-tile Offset, Grayscale, and Threshold are implemented. Grow/Shrink use a square neighborhood; Edge is the difference between grown and shrunken pixels. Offset is a half-image wrap, useful for inspecting seams, not an automatic seamless-texture repair. Grayscale uses luminance weights. Threshold uses the Black control as its cutoff. Non-spatial filters preserve RGBA alpha; flip/offset move alpha with the pixels.

Height/mask-to-normal uses the height image when present, otherwise the painted mask. It does not evaluate live shader relief. DirectX changes the green-channel direction and updates the layer convention. Exporting the composite tangent normal through Export is a different operation and includes the composite material's normal/bump response.

The lab accepts regular RGBA images up to 16 megapixels and rejects UDIM buffers. CPU operations may use several full-size arrays. Work at 1K or 2K before moving a hero surface to 4K. Unsupported/invalid inputs produce an error rather than being silently resized.

## Game texture export

Finish painting, leave Edit Mode, set Channel Preview to Composite, choose an output folder, and bake the active material. The exporter uses a disposable evaluated mesh and copied materials in Cycles CPU. The source object, material slots, source image paths, UVs, and modifiers are not rewritten. Render/bake settings, source visibility, active object, and selection are restored after success or an ordinary handled failure.

BaseColor, Roughness, Metallic, Height, Emission, and ORM are always written. Normal and AO are optional. With both enabled there are eight PNGs. ORM uses **red=AO, green=roughness, blue=metallic**. When AO is off, red is explicitly white rather than a guessed occlusion map. Tangent normals are OpenGL (+Y). BaseColor/Emission are sRGB PNG8; scalar/normal channels are Non-Color PNG8. BaseColor follows the material's color composite, including any existing per-layer AO multiplication.

Only the active material's faces write into the exported maps. The full evaluated geometry is retained during baking so removing neighboring faces does not change split normals or occlusion. Other material regions on that same mesh are treated as opaque occluders; translucent neighboring materials are not faithfully modeled by this helper. Other scene objects remain part of the ordinary Cycles scene.

Every export gets a new timestamp/UUID directory and a manifest listing maps, conventions, material, object, UV map, resolution, and completion status. Failed exports can leave a partial directory explicitly marked incomplete; inspect or delete it. Files are not silently overwritten. Repeated exports consume disk space.

Export supports one regular 0–1 UV tile, with a maximum 4K output. Overlapping UVs still share pixels. Both original and evaluated off-tile UVs are rejected. There is no UDIM export, high-to-low cage workflow, automatic engine-material assignment, or GLB exporter here. Set up the engine material from the PNGs and manifest. Height/Emission are PNG8, not high-dynamic-range EXR; bright emissive information can clip.

## Practical Shipwreck Discovery starting points

For metal shelving, apply Galley shelving to the shelf material, lower the rust coverage, then paint growth into creases and the lower portions by eye. Upward-facing silt can cover horizontal shelf faces without coating the underside equally. This does not detect crevices automatically.

For large hull interiors, divide the ship into sensible material regions and use 1K/2K masks. Use object/world noise for continuous variation and reserve UV masks for intentional placement. Import your own PBR rust or algae textures when a procedural starting material is too simple. Bake distant or mobile/VR surfaces to avoid retaining a large live shader stack at runtime.

For casino props, keep metal casings, fabric, opaque deposits on glass, and emissive panels in separate materials. The included amber, cyan, and phosphor layers provide adjustable emissive colors, but no screen graphics or generated lettering. Barnacles and sponge patches only shade the surface; add geometry separately for silhouettes.

## Persistence and known boundaries

Save a backup before upgrading. New processed images are packed, but native painting still requires normal save discipline. Pack external source textures through Export or the legacy file tools before moving the project. Locks guard the extension's image-edit operations; native Blender tools can still edit an image displayed from a locked layer.

The add-on is local procedural software, not an AI image-generation client. Its original MIT-licensed implementation does not bundle Ucupaint code. Layer groups, PSD import/export, UDIM-mask authoring, curvature-based smart masking, generative fill, and full Photoshop/Ucupaint feature parity are outside 1.1.
