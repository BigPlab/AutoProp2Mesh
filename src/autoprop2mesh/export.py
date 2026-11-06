"""AdvDupe2 export.

Coordinates: Blender and Source are both right-handed and Z-up, so positions
map straight across (scaled by the scene's Source-units-per-Blender-unit).
Entity forward is +X in both. A Source QAngle (pitch, yaw, roll) is the
rotation Rz(yaw) * Ry(pitch) * Rx(roll), which is Blender's XYZ Euler with
x = roll, y = pitch, z = yaw.

The dupe origin (the point AdvDupe2 pastes at) is Blender's world origin.
"""

import json
import math
import os

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix

from . import entities, modelparts, prefs, props, sync, uvpreview
from .core import ad2, p2m, starfall, tree


def matrix_to_source(matrix, unit_scale):
    """World matrix -> (Source position, Source angle, scale-free matrix)."""
    loc, rot, _scale = matrix.decompose()
    e = rot.to_euler("XYZ")
    ang = (math.degrees(e.y), math.degrees(e.z), math.degrees(e.x))
    pos = (loc.x * unit_scale, loc.y * unit_scale, loc.z * unit_scale)
    frame = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
    return pos, ang, frame


def _smooth_angle(obj, mesh):
    mode = obj.p2m.smooth_mode
    if mode == "FLAT":
        return None
    if mode == "SMOOTH":
        return obj.p2m.smooth_angle or None
    n = len(mesh.polygons)
    if n == 0:
        return None
    flags = np.zeros(n, dtype=bool)
    mesh.polygons.foreach_get("use_smooth", flags)
    if not flags.any():
        return None
    # Blender 4.1+ "Smooth by Angle" modifier: use its angle.
    for mod in obj.modifiers:
        if mod.type == "NODES" and mod.node_group and mod.node_group.name.startswith("Smooth by Angle") \
                and mod.show_viewport:
            for item in mod.node_group.interface.items_tree:
                if getattr(item, "in_out", None) == "INPUT" and item.name == "Angle":
                    value = uvpreview._get_input(mod, item.identifier)
                    if isinstance(value, (int, float)):
                        return math.degrees(float(value))
    return 180.0


def part_geometry(obj, depsgraph, entity_frame_inv, unit_scale):
    ob_eval = obj.evaluated_get(depsgraph)
    try:
        mesh = ob_eval.to_mesh()
    except RuntimeError:
        return None
    if mesh is None:
        return None
    try:
        mesh.calc_loop_triangles()
        nv = len(mesh.vertices)
        nt = len(mesh.loop_triangles)
        if nv == 0 or nt == 0:
            return None
        co = np.empty(nv * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", co)
        tris = np.empty(nt * 3, dtype=np.int32)
        mesh.loop_triangles.foreach_get("vertices", tris)
        vsmooth = _smooth_angle(obj, mesh)
    finally:
        ob_eval.to_mesh_clear()

    m = np.array(entity_frame_inv @ ob_eval.matrix_world, dtype=np.float64)
    pos = co.reshape(-1, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]
    pos *= unit_scale
    tris = tris.reshape(-1, 3)
    if np.linalg.det(m[:3, :3]) < 0:  # mirrored: winding flips
        tris = tris[:, ::-1]
    return p2m.PartGeometry(obj.name, pos, tris, vsmooth, obj.p2m.render_inside)


def model_part_spec(obj, entity_frame_inv, unit_scale, warnings):
    """A model part: only the model path and placement are exported."""
    m = entity_frame_inv @ obj.matrix_world
    loc, rot, scale = m.decompose()
    rebuilt = Matrix.LocRotScale(loc, rot, scale)
    if any(abs(a - b) > 1e-4 for ra, rb in zip(m, rebuilt) for a, b in zip(ra, rb)):
        warnings.append("%s is skewed by a non-uniformly scaled parent; Prop2Mesh cannot represent that" % obj.name)
    e = rot.to_euler("XYZ")
    clips = modelparts.export_clips(modelparts.local_planes(obj), scale, unit_scale)
    if obj.p2m.model_status:
        warnings.append("%s: %s" % (obj.name, obj.p2m.model_status))
    model = obj.p2m.model.strip().replace("\\", "/").lower()
    if model and not model.endswith(".mdl"):
        model += ".mdl"
    return p2m.ModelPartSpec(
        obj.name, model,
        (loc.x * unit_scale, loc.y * unit_scale, loc.z * unit_scale),
        (math.degrees(e.y), math.degrees(e.z), math.degrees(e.x)),
        tuple(scale), clips, obj.p2m.bodygroup_mask(), obj.p2m.model_flat, obj.p2m.render_inside)


def _visible(obj, context):
    try:
        return obj.visible_get(view_layer=context.view_layer)
    except Exception:
        return not obj.hide_viewport


def gather(context, selection_only=False, include_hidden=False):
    """Returns (list of EntitySpec, warnings)."""
    scene = context.scene
    us = props.unit_scale(scene)
    warnings = []
    all_entities = [o for o in scene.objects if o.p2m.is_entity]
    if selection_only:
        chosen = set()
        for o in context.selected_objects:
            if o.p2m.is_entity:
                chosen.add(o)
            else:
                ent = entities.owning_entity(o)
                if ent is not None:
                    chosen.add(ent)
        export_entities = [o for o in all_entities if o in chosen]
    else:
        export_entities = all_entities
    if not export_entities:
        return [], ["No Prop2Mesh entities to export"]
    exported = set(export_entities)

    depsgraph = context.evaluated_depsgraph_get()
    specs = []
    unassigned = 0
    for ent in export_entities:
        pos, ang, frame = matrix_to_source(ent.matrix_world, us)
        scale = ent.matrix_world.to_scale()
        if any(abs(s - 1.0) > 1e-4 for s in scale):
            warnings.append("%s is scaled; entity scale is ignored (parts keep their world size)" % ent.name)
        frame_inv = frame.inverted()

        parent_key = None
        p = ent.parent
        while p is not None:
            if p in exported:
                parent_key = p.name
                break
            p = p.parent

        by_uid = {c.uid: [] for c in ent.p2m.controllers}
        for obj, ctrl in entities.entity_parts(ent, include_unassigned=True):
            if ctrl is None:
                unassigned += 1
                continue
            if not include_hidden and not _visible(obj, context):
                continue
            if obj.p2m.is_model_part:
                by_uid[ctrl.uid].append(model_part_spec(obj, frame_inv, us, warnings))
                continue
            geo = part_geometry(obj, depsgraph, frame_inv, us)
            if geo is not None:
                by_uid[ctrl.uid].append(geo)

        controllers = []
        for c in ent.p2m.controllers:
            controllers.append(p2m.ControllerSpec(
                color=[v * 255.0 for v in c.color], material=c.material.strip(),
                uvs=c.uvs, bump=c.bump, name=c.name.strip(), parts=by_uid[c.uid]))
        specs.append(p2m.EntitySpec(ent.name, ent.p2m.model.strip(), pos, ang, parent_key, controllers))
    if unassigned:
        warnings.append("%d object(s) below entities have no controller and were skipped" % unassigned)
    return specs, warnings


def write_dupe(filepath, specs, export_names=True, author="AutoProp2Mesh"):
    dupe, report = p2m.build_dupe(specs, export_names=export_names)
    data = ad2.encode(dupe, {"name": author})
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(data)
    report["bytes"] = len(data)
    return report


class P2M_OT_export_advdupe2(bpy.types.Operator, ExportHelper):
    """Export Prop2Mesh entities as an AdvDupe2 file"""
    bl_idname = "export_scene.p2m_advdupe2"
    bl_label = "Export AdvDupe2 (Prop2Mesh)"
    bl_options = {"PRESET"}

    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={"HIDDEN"})
    selection_only: BoolProperty(
        name="Selected Entities Only", default=False,
        description="Export only selected entities (or entities owning selected parts)",
    )
    include_hidden: BoolProperty(name="Include Hidden Parts", default=False)
    export_names: BoolProperty(name="Export Controller Names", default=True)

    def invoke(self, context, event):
        directory = prefs.default_dupe_dir()
        name = bpy.path.display_name_from_filepath(bpy.data.filepath) or "p2m_export"
        if directory:
            self.filepath = os.path.join(directory, name + self.filename_ext)
        else:
            self.filepath = name + self.filename_ext
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        sync.full_sync(context.scene)
        specs, warnings = gather(context, self.selection_only, self.include_hidden)
        if not specs:
            self.report({"ERROR"}, warnings[0] if warnings else "Nothing to export")
            return {"CANCELLED"}
        try:
            report = write_dupe(self.filepath, specs, self.export_names)
        except Exception as e:
            self.report({"ERROR"}, "Export failed: %s" % e)
            return {"CANCELLED"}
        for w in warnings + report["warnings"]:
            self.report({"WARNING"}, w)
        if report["bytes"] > p2m.MAX_DUPE_BYTES:
            self.report({"WARNING"}, "Dupe is larger than AdvDupe2's 32 MB limit")
        self.report({"INFO"}, "Exported %d entities, %d controllers, %d parts (%d model parts, %d mesh triangles), %.1f KB to %s" % (
            report["entities"], report["controllers"], report["parts"], report["models"], report["triangles"],
            report["bytes"] / 1024.0, os.path.basename(self.filepath)))
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "selection_only")
        layout.prop(self, "include_hidden")
        layout.prop(self, "export_names")
        layout.prop(context.scene.p2m, "unit_scale", text="Units per BU")


def gather_tree(context, selection_only=False, include_hidden=False):
    """The Blender parent hierarchy above/below P2M entities as TreeNodes.
    Returns (list of root TreeNode, warnings)."""
    scene = context.scene
    us = props.unit_scale(scene)
    warnings = []
    if selection_only:
        seeds = list(context.selected_objects)
    else:
        seeds = [o for o in scene.objects if o.p2m.is_entity]
    root_objs = []
    for o in seeds:
        while o.parent is not None:
            o = o.parent
        if o not in root_objs:
            root_objs.append(o)
    if not root_objs:
        return [], ["No Prop2Mesh entities to export"]

    depsgraph = context.evaluated_depsgraph_get()
    stats = {"no_ctrl": 0}

    def build(obj, parent_frame):
        _pos, _ang, frame = matrix_to_source(obj.matrix_world, us)
        rpos, rang, _ = matrix_to_source(parent_frame.inverted() @ frame, us)
        node = tree.TreeNode(obj.name, rpos, rang)
        if not obj.p2m.is_entity and sync.is_geometry(obj) and (include_hidden or _visible(obj, context)):
            if obj.p2m.is_model_part:
                warnings.append("%s is a model part; the mesh tree export only supports mesh parts" % obj.name)
            else:
                geo = part_geometry(obj, depsgraph, frame.inverted(), us)
                if geo is not None:
                    node.chunks = p2m.split_part(geo)
                    _ent, ctrl = sync.resolve(obj)
                    if ctrl is None:
                        stats["no_ctrl"] += 1
                    else:
                        node.color = tuple(int(round(v * 255.0)) for v in ctrl.color)
                        node.material = ctrl.material.strip() or p2m.DEFAULT_MATERIAL
                        node.uvs = ctrl.uvs
        for child in sorted(obj.children, key=lambda c: c.name):
            if child.p2m.is_clip_plane:
                continue
            c = build(child, frame)
            if c is not None:
                node.children.append(c)
        if not node.chunks and not node.children:
            return None
        return node

    roots = [n for n in (build(o, Matrix.Identity(4)) for o in root_objs) if n is not None]
    if stats["no_ctrl"]:
        warnings.append("%d mesh(es) are not below a controller and use the default color/material" % stats["no_ctrl"])
    if not roots:
        return [], ["Nothing to export: no visible mesh geometry"]
    return roots, warnings


def _previous_export_files(root):
    """OBJ paths (relative, '/'-separated) listed by an earlier export's manifest in
    root; empty if root holds no manifest written by this exporter."""
    try:
        with open(os.path.join(root, tree.MANIFEST_NAME), encoding="utf-8") as f:
            manifest = json.load(f)
        if not isinstance(manifest, dict) or "version" not in manifest or "nodes" not in manifest:
            return set()
        return set(tree.manifest_files(manifest))
    except (OSError, ValueError, TypeError, AttributeError):
        return set()


def _remove_stale(root, rels):
    """Deletes files an earlier export wrote and this one no longer does, then the
    folders that became empty. Anything else in the project folder is left alone."""
    base = os.path.abspath(root)
    for rel in rels:
        path = os.path.abspath(os.path.join(base, *rel.split("/")))
        if not path.startswith(base + os.sep):
            continue
        try:
            os.remove(path)
            folder = os.path.dirname(path)
            while folder != base:
                os.rmdir(folder)  # fails (and stops) at the first non-empty folder
                folder = os.path.dirname(folder)
        except OSError:
            pass


class P2M_OT_export_starfall_tree(bpy.types.Operator):
    """Export the parent hierarchy as a project folder (OBJ tree + manifest.json + loader chip) in the mesh repository"""
    bl_idname = "export_scene.p2m_starfall_tree"
    bl_label = "Export Starfall Mesh Tree"
    bl_options = {"PRESET"}

    project_name: StringProperty(
        name="Project Name", default="",
        description="Folder created inside the mesh repository; the loader chip fetches it by this name")
    selection_only: BoolProperty(
        name="Selected Hierarchies Only", default=False,
        description="Export only the hierarchies that contain selected objects")
    include_hidden: BoolProperty(name="Include Hidden Parts", default=False)
    invert_normals: BoolProperty(
        name="Invert Normals", default=False,
        description="Flip the face winding and normals of the exported OBJs (inside-out meshes)")
    nocull: BoolProperty(
        name="No Cull", default=False,
        description="Show both sides of every face (draws each mesh on two holograms)")
    model_front: EnumProperty(
        name="Model Faces", default="X",
        items=(
            ("X", "+X (Source forward)", "The model already faces +X, the Garry's Mod forward axis"),
            ("-Y", "-Y (Blender front view)", "The model faces the Blender front view (-Y); turned 90 degrees to face +X in game"),
            ("Y", "+Y", "The model faces +Y; turned -90 degrees to face +X in game"),
            ("-X", "-X", "The model faces -X; turned 180 degrees to face +X in game"),
        ),
        description="The direction the model faces in Blender; the loader turns the whole model so it faces +X in game")

    def invoke(self, context, event):
        if not self.project_name:
            self.project_name = bpy.path.display_name_from_filepath(bpy.data.filepath) or "mech"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        repo_dir = prefs.resolved_repo_dir()
        if not repo_dir or not os.path.isdir(repo_dir):
            self.report({"ERROR"}, "Set the Mesh Repository Folder in the add-on preferences")
            return {"CANCELLED"}
        project = starfall.safe_name(self.project_name)
        user, repo, branch = prefs.resolved_github()
        if user and repo:
            repo_url = starfall.raw_base_url(user, repo, branch, "")
        else:
            repo_url = starfall.raw_base_url("USER", "REPO", branch, "")
        sync.full_sync(context.scene)
        roots, warnings = gather_tree(context, self.selection_only, self.include_hidden)
        if not roots:
            self.report({"ERROR"}, warnings[0] if warnings else "Nothing to export")
            return {"CANCELLED"}
        if not (user and repo):
            warnings.append("GitHub user/repository not found: set them in the preferences or edit REPO_URL in %s" % tree.LOADER_NAME)
        root = os.path.join(repo_dir, project)
        try:
            yaw = {"X": 0.0, "-Y": 90.0, "Y": -90.0, "-X": 180.0}[self.model_front]
            manifest, files, report = tree.build(roots, project, self.invert_normals, self.nocull, yaw)
            previous = _previous_export_files(root)
            os.makedirs(root, exist_ok=True)
            for rel, text in files.items():
                path = os.path.join(root, *rel.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="ascii", newline="\n") as f:
                    f.write(text)
            with open(os.path.join(root, tree.MANIFEST_NAME), "w", encoding="utf-8", newline="\n") as f:
                json.dump(manifest, f, indent=1)
            with open(os.path.join(root, tree.LOADER_NAME), "w", encoding="utf-8", newline="\n") as f:
                f.write(tree.loader_code(repo_url, project))
            _remove_stale(root, previous - set(files))  # only after the new export is fully written
        except Exception as e:
            self.report({"ERROR"}, "Export failed: %s" % e)
            return {"CANCELLED"}
        for w in warnings:
            self.report({"WARNING"}, w)
        self.report({"INFO"}, "Exported %d nodes (%d holograms in game), %d OBJ files (%d triangles) to %s; commit and push, then use %s with project \"%s\"" % (
            report["nodes"], report["holograms"], report["files"], report["triangles"], root, repo_url, project))
        if report["holograms"] > 200:
            self.report({"WARNING"}, "%d holograms exceeds Starfall's default limit of 200" % report["holograms"])
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.prop(self, "project_name")
        layout.prop(self, "model_front")
        layout.prop(self, "selection_only")
        layout.prop(self, "include_hidden")
        layout.prop(self, "invert_normals")
        layout.prop(self, "nocull")
        layout.prop(context.scene.p2m, "unit_scale", text="Units per BU")


def menu_func_export(self, context):
    self.layout.operator(P2M_OT_export_advdupe2.bl_idname, text="AdvDupe2 Prop2Mesh (.txt)")
    self.layout.operator(P2M_OT_export_starfall_tree.bl_idname, text="Starfall Mesh Tree (folders + manifest)")


classes = (P2M_OT_export_advdupe2, P2M_OT_export_starfall_tree)
