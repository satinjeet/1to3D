# Asset types

Each type goes in `designs/<slug>/<type>/`. Offer the types that fit how the user will use the design; do not make all of them.
After making any of them, verify (files exist and are non-empty, part count right, sizes right) and list them in README.md under "Assets".

## 3d-print/ (FDM or resin printing)

Make with `d.export_print(shapes=[(label, shape_in_print_orientation), ...], bed=(x, y, z))`.

- Turn each part to its best print orientation first (largest flat face down, overhangs under 45 degrees, load along layers). Rotate a copy: `s = shape.copy(); s.rotate(V(0,0,0), V(1,0,0), 90)`. The helper drops each part onto the bed.
- Leave reference objects (`ref_*`) out.
- Outputs: `<slug>_<part>.stl` per part, plus `<slug>_plate.3mf` and `<slug>_plate.stl` with all parts laid out and centred on the bed (only if they fit on one plate; otherwise say how many plates).
- Verify the plate: load the plate STL as a temporary part in a fresh document, or screenshot it, and confirm parts sit flat and apart.
- If Bambu Studio, OrcaSlicer or PrusaSlicer is installed, tell the user they can open the 3MF directly. Add print notes to README.md: material, supports needed and where, any parts needing brim.

## step/ (CAD exchange)

The `cad/<slug>.step` already exists; copy it here if the user wants a deliverable folder, or point to it. STEP keeps exact geometry for Fusion 360, Onshape, SolidWorks, or a machine shop.

## mesh/ (Blender, game engines, renderers, web)

`d.export_mesh_formats(formats=("obj", "stl"))`. OBJ keeps parts as separate objects. Units are mm; tell Blender users to set the import scale to 0.001 for metres.

## blender/

If `blender` is on PATH, make a real `.blend`: write a small script that imports `mesh/<slug>.obj` with scale 0.001, assigns each part a material in its viewer color, and saves `blender/<slug>.blend`; run `blender --background --python <script>`. If Blender is not installed, make `mesh/` instead and say how to import it.

## drawings/ (dimensioned 2D drawings)

Use the TechDraw workbench from a script: a page with front, top and side views and key dimensions, exported to PDF and SVG. Useful for a machinist or for checking dimensions by hand.

## laser/ or cnc/ (2D profiles)

For flat parts: take a section or the bottom face outline (`shape.slice(V(0,0,1), z)`), and export it as DXF with `importDXF.export` or as SVG. State the stock thickness and kerf assumption.

## Anything else

If the user names a format FreeCAD can write (IGES, BREP, AMF, PLY, VRML, IFC), export it with `Part.export`, `Mesh.export` or `ImportGui.export` into a folder named after its use. If FreeCAD cannot write it, say so and offer the nearest format.
