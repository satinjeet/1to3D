"""Helpers for design scripts that run inside FreeCAD (via the FreeCAD MCP execute_python_file tool).

A design script imports this module, builds its Part shapes, then calls the helpers:

    import importlib, sys
    sys.path.insert(0, "<skill dir>/scripts")
    import fc_design as fd
    importlib.reload(fd)  # FreeCAD keeps modules loaded between runs

    d = fd.Design("<abs path>/designs/<slug>", "<slug>")  # must be absolute
    doc = d.new_doc()
    d.add_part("body", shape, (0.3, 0.6, 0.85))
    d.save_cad()       # cad/<slug>.FCStd and cad/<slug>.step
    d.check()          # validity, volumes, bounding boxes, overlaps between parts
    d.shots()          # cad/shots/*.png from FreeCAD's 3D view
    d.export_browser() # browser/index.html, manifest.json, parts/*.stl

Everything is in mm. Z is up.
"""
import json
import os
import re
import shutil

import FreeCAD as App
import Mesh
import MeshPart
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
VIEWER = os.path.join(HERE, "..", "assets", "viewer.html")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")  # slugs and labels end up in file names

VIEWS = {
    "iso": "viewIsometric",
    "front": "viewFront",
    "top": "viewTop",
    "right": "viewRight",
    "rear": "viewRear",
    "bottom": "viewBottom",
    "left": "viewLeft",
}


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in rgb[:3])


def _mesh(shape, fine=False):
    lin, ang = (0.02, 0.2) if fine else (0.05, 0.3)
    return MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang)


class Design:
    def __init__(self, root, slug):
        # A relative root would resolve against FreeCAD's working folder, not the project.
        if not os.path.isabs(root):
            raise ValueError("Design root must be an absolute path, got %r" % root)
        if not NAME.match(slug):
            raise ValueError("slug must be letters, digits, '_' or '-', got %r" % slug)
        self.root = os.path.normpath(root)
        self.slug = slug
        self.cad = os.path.join(self.root, "cad")
        self.browser = os.path.join(self.root, "browser")
        self.doc = None
        self.parts = []  # (label, shape, color)
        self.objects = []

    # --- Model ---
    def new_doc(self):
        """Close an earlier version of this design and start a clean one.

        Refuses to close a same-named document that is not this design's saved file and has unsaved changes,
        so the user's own work in FreeCAD is never thrown away.
        """
        ours = os.path.join(self.cad, self.slug + ".FCStd")
        for old in list(App.listDocuments().values()):
            if self.slug not in (old.Name, old.Label):  # Name mangles "-" to "_"
                continue
            mine = old.FileName and os.path.normpath(old.FileName) == ours
            if not mine and (not old.FileName or old.isTouched()):
                raise RuntimeError("FreeCAD document %r is open with unsaved work; save or close it first" % old.Name)
            App.closeDocument(old.Name)
        self.doc = App.newDocument(self.slug)
        self.parts = []
        self.objects = []
        return self.doc

    def add_part(self, label, shape, color=(0.6, 0.6, 0.65)):
        """One printable or separate piece. Color is RGB 0..1. The label becomes a file name."""
        if not NAME.match(label):
            raise ValueError("part label must be letters, digits, '_' or '-', got %r" % label)
        o = self.doc.addObject("Part::Feature", label)
        o.Shape = shape
        try:
            o.ViewObject.ShapeColor = tuple(color)
        except AttributeError:  # no GUI
            pass
        self.objects.append(o)
        self.parts.append((label, shape, tuple(color)))
        return o

    def save_cad(self):
        os.makedirs(self.cad, exist_ok=True)
        self.doc.recompute()
        self.doc.saveAs(os.path.join(self.cad, self.slug + ".FCStd"))
        Part.export(self.objects, os.path.join(self.cad, self.slug + ".step"))
        print("saved", self.cad)

    # --- Verification ---
    def check(self, min_overlap=0.01):
        """Print per-part facts and any overlap between parts. Returns a dict, also written to cad/check.json."""
        report = {"parts": [], "overlaps": [], "problems": []}
        for label, s, _ in self.parts:
            bb = s.BoundBox
            info = {
                "label": label,
                "valid": s.isValid(),
                "solids": len(s.Solids),
                "volume_mm3": round(s.Volume, 1),
                "size_mm": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
                "min_mm": [round(bb.XMin, 2), round(bb.YMin, 2), round(bb.ZMin, 2)],
            }
            report["parts"].append(info)
            if not info["valid"]:
                report["problems"].append("%s: shape is not valid" % label)
            if info["solids"] != 1:
                report["problems"].append("%s: %d solids (expected 1)" % (label, info["solids"]))
        for i in range(len(self.parts)):
            for j in range(i + 1, len(self.parts)):
                a, b = self.parts[i], self.parts[j]
                if not a[1].BoundBox.intersect(b[1].BoundBox):
                    continue
                v = a[1].common(b[1]).Volume
                if v > min_overlap:
                    report["overlaps"].append({"a": a[0], "b": b[0], "volume_mm3": round(v, 2)})
        os.makedirs(self.cad, exist_ok=True)
        with open(os.path.join(self.cad, "check.json"), "w") as f:
            json.dump(report, f, indent=2)
        print(json.dumps(report, indent=2))
        return report

    def shots(self, views=("iso", "front", "top", "right"), size=(1600, 1200), out_dir=None, prefix=""):
        """Save PNGs of FreeCAD's 3D view. Returns the paths. Needs the FreeCAD GUI."""
        import FreeCADGui as Gui

        out_dir = out_dir or os.path.join(self.cad, "shots")
        os.makedirs(out_dir, exist_ok=True)
        gdoc = Gui.getDocument(self.doc.Name)
        Gui.ActiveDocument = gdoc
        view = gdoc.ActiveView
        paths = []
        for name in views:
            getattr(view, VIEWS[name])()
            view.fitAll()
            p = os.path.join(out_dir, "%s%s.png" % (prefix, name))
            view.saveImage(p, size[0], size[1], "White")
            paths.append(p)
        view.viewIsometric()
        view.fitAll()
        print("\n".join(paths))
        return paths

    # --- Browser viewer ---
    def export_browser(self):
        """Write browser/parts/*.stl, browser/manifest.json and browser/index.html (three.js viewer).

        FreeCAD 1.1 here cannot write glTF, so each part goes out as STL and the colors ride in the manifest.
        """
        parts_dir = os.path.join(self.browser, "parts")
        if os.path.isdir(parts_dir):
            shutil.rmtree(parts_dir)
        os.makedirs(parts_dir)
        entries = []
        total = None
        for label, s, col in self.parts:
            fn = "%s.stl" % label
            _mesh(s).write(os.path.join(parts_dir, fn))
            bb = s.BoundBox
            total = bb if total is None else total.united(bb)
            entries.append({
                "label": label,
                "file": "parts/" + fn,
                "color": _hex(col),
                "size_mm": [round(bb.XLength, 2), round(bb.YLength, 2), round(bb.ZLength, 2)],
                "volume_mm3": round(s.Volume, 1),
            })
        manifest = {
            "name": self.slug,
            "units": "mm",
            "up": "z",
            "size_mm": [round(total.XLength, 2), round(total.YLength, 2), round(total.ZLength, 2)] if total else [0, 0, 0],
            "parts": entries,
        }
        with open(os.path.join(self.browser, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        shutil.copyfile(VIEWER, os.path.join(self.browser, "index.html"))
        print("browser viewer in", self.browser)

    # --- Usable assets ---
    def export_print(self, shapes=None, bed=(180.0, 180.0, 180.0), margin=10.0, gap=8.0, fine=True, out_name="3d-print"):
        """Per-part STL plus one plate (3MF and STL) laid out in a row along Y, centred on the bed.

        shapes: list of (label, shape) already turned to their print orientation; default is the parts as modelled.
        bed: build volume in mm (default Bambu Lab A1 mini). Raises if a part or the plate does not fit.
        """
        if not NAME.match(out_name):
            raise ValueError("out_name must be letters, digits, '_' or '-', got %r" % out_name)
        shapes = shapes or [(lbl, s) for lbl, s, _ in self.parts]
        if not shapes:
            raise ValueError("no parts to export")
        # Check every part against the bed before writing anything.
        placed, y = [], 0.0
        for label, s in shapes:
            if not NAME.match(label):
                raise ValueError("part label must be letters, digits, '_' or '-', got %r" % label)
            q = s.copy()
            bb = q.BoundBox
            q.translate(V(-bb.XMin, -bb.YMin, -bb.ZMin))
            for axis, length, limit in (("X", bb.XLength, bed[0]), ("Y", bb.YLength, bed[1]), ("Z", bb.ZLength, bed[2])):
                lim = limit - (2 * margin if axis != "Z" else 0)
                if length > lim:
                    raise ValueError("%s is %.1f mm in %s, bed allows %.1f" % (label, length, axis, lim))
            placed.append((label, q))
        out = os.path.join(self.root, out_name)
        os.makedirs(out, exist_ok=True)
        for label, q in placed:
            _mesh(q, fine).write(os.path.join(out, "%s_%s.stl" % (self.slug, label)))
            q.translate(V(0, y, 0))
            y += q.BoundBox.YLength + gap
        plate_x = max(q.BoundBox.XLength for _, q in placed)
        plate_y = y - gap
        fits = plate_x <= bed[0] - 2 * margin and plate_y <= bed[1] - 2 * margin
        if fits:
            meshes = []
            try:
                for label, q in placed:
                    q.translate(V((bed[0] - plate_x) / 2, (bed[1] - plate_y) / 2, 0))
                    m = self.doc.addObject("Mesh::Feature", "plate_" + label)
                    m.Mesh = _mesh(q, fine)
                    meshes.append(m)
                Mesh.export(meshes, os.path.join(out, "%s_plate.3mf" % self.slug))
                Mesh.export(meshes, os.path.join(out, "%s_plate.stl" % self.slug))
            finally:  # never leave temporary plate objects in the user's document
                for m in meshes:
                    self.doc.removeObject(m.Name)
                self.doc.recompute()
        else:
            print("parts fit one at a time but not on one plate (%.0f x %.0f mm); no plate file written" % (plate_x, plate_y))
        print("print files in", out)
        return out

    def export_mesh_formats(self, out_name="mesh", formats=("obj", "stl")):
        """Whole assembly as mesh files for other tools (Blender, game engines, renderers)."""
        if not NAME.match(out_name):
            raise ValueError("out_name must be letters, digits, '_' or '-', got %r" % out_name)
        out = os.path.join(self.root, out_name)
        os.makedirs(out, exist_ok=True)
        for ext in formats:
            Mesh.export(self.objects, os.path.join(out, "%s.%s" % (self.slug, ext)))
        print("mesh files in", out)
        return out
