# Writing the design script

## Contents
- Script shape
- Building geometry with Part
- Fits and tolerances
- Printability (FDM)
- Verification snippets
- Environment pitfalls

## Script shape

One script per design, `designs/<slug>/cad/make_<slug>.py`. It rebuilds everything from scratch every run, so it is the source of truth; never hand-edit the `.FCStd`.

```python
# <Name>: <what it does, in one or two sentences>.
# Parts: <list, and how they go together (snap, slide, dovetail...)>.
# Print: <orientation, supports, material> (if printed).
# Run inside FreeCAD (FreeCAD MCP execute_python_file).
#
# Axes: <where the origin is>, X <direction>, Z up. All mm.
import importlib
import os
import sys

sys.path.insert(0, "<absolute path to this skill>/scripts")
import fc_design as fd

importlib.reload(fd)
import Part

V = fd.V
HERE = os.path.dirname(os.path.abspath(__file__))  # may be unset under exec; fall back to a literal path

# --- Measured (from the user, real objects) ---
PIPE_D = 7.5

# --- Chosen ---
WALL = 2.4
FIT = 0.15  # play per side on sliding fits

# --- Derived ---
BORE_D = PIPE_D + 2 * FIT

# --- Geometry ---
def clip():
    ...
    return shape

# --- Build, save, verify, export ---
d = fd.Design("<absolute path>/designs/<slug>", "<slug>")
d.new_doc()
d.add_part("clip", clip(), (0.3, 0.6, 0.85))
d.save_cad()
d.check()
d.shots()
d.export_browser()
```

Comment the why of each chosen number (what it clears, what it holds), as in the example. Separate measured, chosen and derived values so a change request maps to one line.

Use one `add_part` per physical piece. Pieces that are printed separately or move relative to each other must be separate parts, otherwise `check()` cannot see overlaps between them and the print export cannot lay them out.

Give parts distinct colors and keep a part's color the same across iterations; the user learns them.

## Building geometry with Part

Prefer `Part` (OpenCascade) solids and booleans in a script over PartDesign features; it is easier to rebuild and reason about.

- Primitives: `Part.makeBox(x, y, z, V(x0, y0, z0))`, `Part.makeCylinder(r, h, base, dir)`, `Part.makeCone`, `Part.makeSphere`, `Part.makeTorus`.
- Booleans: `a.fuse(b)`, `a.cut(b)`, `a.common(b)`; follow a fuse of many pieces with `.removeSplitter()` to merge coplanar faces.
- Profiles: build a wire with `Part.makePolygon([V(...), ...])` (closed: repeat the first point), `Part.Face(wire)`, then `face.extrude(V(0, 0, h))` or `face.revolve(V(0,0,0), V(0,0,1), 360)`.
- Smooth transitions: `Part.makeLoft([wire1, wire2], True)`; sweeps: `Part.Wire(path).makePipeShell([profile], True, True)`.
- Fillets and chamfers: `shape.makeFillet(r, [edges])`, `shape.makeChamfer(d, [edges])`. Select edges by geometry (for example edges whose `BoundBox.ZMax` is below 0.01) not by index; indexes change when geometry changes. Fillet before booleans that would complicate the edges, and expect failures with big radii; catch and reduce.
- Placement: `shape.translate(V(...))`, `shape.rotate(V(center), V(axis), degrees)`; `shape.copy()` first if you reuse the original.
- Threads and text: avoid unless asked; they are slow and fragile. For text, `Part.makeWireString` plus `Part.Face` and extrude.

Build the assembly in its use position (parts placed as they sit together), so screenshots show the real thing. Turn parts to print orientation only in the print export.

## Fits and tolerances

Starting points for FDM with a 0.4 mm nozzle; tell the user which you used.

| Fit | Clearance per side |
|---|---|
| Press fit / tight | 0.05 to 0.1 mm |
| Snug slide, turns by hand | 0.15 to 0.2 mm |
| Free slide or rotate | 0.25 to 0.3 mm |
| Separate printed parts that just need to go together | 0.3 to 0.4 mm |
| Holes for screws | screw diameter + 0.2 to 0.4 mm |

Holes printed vertically come out undersized by about 0.1 to 0.2 mm; horizontal holes come out oval. Snap fits: cantilever 1.2 to 2 mm thick, length at least 5x the hook depth, hook depth 0.5 to 1 mm, 30 to 45 degree lead-in; PLA is brittle, PETG forgives more. Split rings that clip on a pipe or faucet: opening 70 to 85 percent of the diameter.

## Printability (FDM)

- Walls at least 1.2 mm (3 perimeters at 0.4 mm), 2 mm or more where loaded.
- Overhangs up to 45 degrees print without support; bridges up to about 10 mm.
- A flat face on the bed for each part, if the design allows. Chamfer (do not fillet) bottom edges that touch the bed.
- Layer lines are weak in tension along Z; orient so the load runs along the layers, especially for clips and hooks.
- Check the part fits the user's bed (default in `export_print`: 180 x 180 x 180 mm, Bambu Lab A1 mini; ask if unsure). Split long parts with a joint (dovetail, lap, pin) rather than shrinking them.

## Verification snippets

Run with `execute_python` after the script, while the document is open.

Measure a gap or distance between two parts:
```python
doc = App.getDocument("<slug>")
a, b = doc.getObjectsByLabel("clip")[0].Shape, doc.getObjectsByLabel("pipe")[0].Shape
print(a.distToShape(b)[0])
```

Section through the model (thin walls, hidden voids):
```python
s = doc.getObjectsByLabel("clip")[0].Shape
cut = s.slice(App.Vector(0, 0, 1), 5.0)  # wires at z = 5
print([round(w.BoundBox.XLength, 2) for w in cut])
```

Close-up screenshot:
```python
v = Gui.getDocument("<slug>").ActiveView
v.viewIsometric(); v.fitAll()
v.zoomIn(); v.zoomIn()  # each step zooms about the view centre; pivy (getCameraNode) may not be loaded
# to aim at a spot: edit the "position"/"focalDistance"/"height" lines of v.getCamera() and pass it to v.setCamera()
v.saveImage("<abs path>/designs/<slug>/cad/shots/closeup.png", 1600, 1200, "White")
```

Show reference objects (the pipe, the faucet, the glass) as separate parts in a neutral grey so screenshots show the fit, and name them `ref_<thing>`. Leave them out of the print export by passing `shapes=` without them.

## Environment pitfalls

- FreeCAD may run as a Flatpak: it can only see paths under the home folder. Keep the script and outputs under the project (not `/tmp`), and pass absolute paths.
- FreeCAD keeps imported modules between runs: `importlib.reload(fd)` after `import fc_design`, as in the template, or helper edits are ignored.
- `__file__` may be undefined when a file runs through the MCP; use absolute paths built from a literal project root.
- glTF export (`ImportGui.export` to `.glb`/`.gltf`) fails with "Cannot save to file" in FreeCAD 1.1; that is why the viewer uses STL per part.
- `new_doc()` closes the previous version of the design, so the user's FreeCAD window always shows the latest one. It raises instead if a document with that name has unsaved edits and is not the design's own saved file. Then ask the user to save or close it; never close it for them.
- `Design` needs an absolute root, and part labels must be plain names (letters, digits, `_`, `-`), because they become file names.
- Long output is paged: read every page with `get_output_page` before deciding a run succeeded.
- Screenshots need the FreeCAD GUI. If `shots()` fails with no GUI, use the browser shots from `serve_viewer.py --shots` instead.
