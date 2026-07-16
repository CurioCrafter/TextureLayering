# Surface Layer Studio 1.0.0

Blender 4.5 LTS extension for ordered PBR texture layers with paintable grayscale UV masks.

After installation, select a mesh and open **3D Viewport > Sidebar (`N`) > Surface Layers**. Choose **Create Layer Stack** or **Build Ship Interior Starter**, audit/unwrap UVs, select a layer, and use **Start Mask Painting**. White Reveal paint adds the layer; black Hide paint removes it; Stroke Opacity controls gradual buildup.

The extension supports Base Color, Roughness, Metallic, Normal, Height, AO, and Emission maps, automatic PBR-set import, selected-face material assignment, paint guards, mask export/packing, channel previews, and graph repair.

Version 1.0 creates regular 0–1 UV masks. Layer count has no software cap, but shader and texture cost grows with every visible layer.
