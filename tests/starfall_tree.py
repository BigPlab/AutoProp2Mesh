"""Starfall mesh tree export test, run headless (no Garry's Mod install needed):

    blender -b --factory-startup --python tests/starfall_tree.py

Builds a rotated entity with a rotated pivot below it, rigid mesh children of
several controllers and an object big enough to need splitting, exports the
tree, and checks that: pivots are found, rigid children are merged per
color/material, every pivot's composed Source transform reproduces Blender's
world matrix, the baked vertices land where Blender's evaluated geometry is,
the OBJ files are in the format Starfall's parser accepts, and large groups
are split below Starfall's per-mesh vertex limit.
"""
import math
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import bpy
import numpy as np
from mathutils import Euler

failures = []


def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        failures.append(msg)


import autoprop2mesh as addon
from autoprop2mesh import entities, export, sync
from autoprop2mesh.core import p2m, tree

addon.register()
print("Blender", bpy.app.version_string)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
ctx = bpy.context
scene = ctx.scene


def add_part(parent, controller, location):
    bpy.ops.mesh.primitive_cube_add(size=4, location=(0, 0, 0))
    obj = ctx.active_object
    obj.parent = parent
    obj.location = location
    obj.rotation_euler = Euler((0.2, 0.1, 0.4), "XYZ")
    obj.p2m.controller_uid = controller.uid
    return obj


try:
    # --- scene ------------------------------------------------------------
    ent = bpy.data.objects.new("Mech", bpy.data.meshes.new("Mech"))
    scene.collection.objects.link(ent)
    ent.p2m.is_entity = True
    ent.location = (10, 20, 30)
    ent.rotation_euler = Euler((math.radians(15), math.radians(25), math.radians(40)), "XYZ")
    red = entities.add_controller(ent, "red")
    red.color = (1.0, 0.0, 0.0, 1.0)
    red.material = "hunter/myplastic"
    blue = entities.add_controller(ent, "blue")
    blue.color = (0.0, 0.0, 1.0, 1.0)
    blue.material = "phoenix_storms/metalset_1-2"
    blue.uvs = 24

    arm = bpy.data.objects.new("Arm", None)
    scene.collection.objects.link(arm)
    arm.parent = ent
    arm.location = (5, 0, 2)
    arm.rotation_euler = Euler((0.3, 0.0, 0.5), "XYZ")

    arm_members = [add_part(arm, red, (1, 0, 0)), add_part(arm, red, (0, 3, 0)), add_part(arm, blue, (0, 0, 4))]
    direct = add_part(ent, red, (-6, 0, 0))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=140, ring_count=80, radius=5, location=(0, 0, 0))
    big = ctx.active_object
    big.parent = ent
    big.location = (0, -8, 0)
    big.p2m.controller_uid = blue.uid
    ctx.view_layer.update()
    sync.full_sync(scene)

    # --- gather + build ---------------------------------------------------
    roots, warnings = export.gather_tree(ctx)
    check(len(roots) == 1 and roots[0].name == "Mech", "one root hierarchy: %s" % [r.name for r in roots])
    manifest, files, report = tree.build(roots, "test", yaw=90.0)
    check(manifest["yaw"] == 90.0 and manifest["version"] == 2, "manifest carries yaw and version")

    root = manifest["nodes"][0]
    check([c["name"] for c in root.get("children", [])] == ["Arm"], "Arm is a child pivot of the entity")
    arm_node = root["children"][0]
    check(not arm_node.get("children"), "rigid cubes are merged into Arm, not separate nodes")
    check(report["nodes"] == 2, "2 nodes exported (entity and Arm), got %d" % report["nodes"])

    # --- merging per color/material --------------------------------------
    arm_colors = sorted(tuple(m["color"]) for m in arm_node["meshes"])
    check(arm_colors == [(0, 0, 255, 255), (255, 0, 0, 255)], "Arm has one mesh per controller color: %s" % arm_colors)
    root_red = [m for m in root["meshes"] if tuple(m["color"]) == (255, 0, 0, 255)]
    root_blue = [m for m in root["meshes"] if tuple(m["color"]) == (0, 0, 255, 255)]
    check(len(root_red) == 1, "entity's direct red cube is one mesh")
    check(all(m["material"] == "phoenix_storms/metalset_1-2" for m in root_blue), "controller material exported")

    # --- OBJ format and splitting ----------------------------------------
    problems = []
    for path, text in files.items():
        per = {"o": 0, "v": 0, "vt": 0, "vn": 0, "f": 0}
        for line in text.splitlines():
            parts = line.split()
            if not parts or parts[0] not in per:
                continue
            per[parts[0]] += 1
            if parts[0] == "f" and (len(parts) != 4 or any(len(t.split("/")) != 3 for t in parts[1:])):
                problems.append("%s: face is not a triangle of v/vt/vn corners: %s" % (path, line))
        if per["o"] != 1:
            problems.append("%s: %d object groups (Starfall makes one mesh per group)" % (path, per["o"]))
        if per["f"] * 3 != per["vt"] or per["f"] * 3 != per["vn"]:
            problems.append("%s: vt/vn are per face corner, got %s" % (path, per))
        if per["f"] > p2m.MAX_PART_TRIANGLES:
            problems.append("%s: %d triangles exceeds the per-mesh limit" % (path, per["f"]))
    check(not problems, "OBJ files are Starfall-parsable, one mesh each, within the triangle limit %s" % problems[:3])
    check(len(root_blue) >= 2, "oversized blue group is split into %d meshes" % len(root_blue))
    check(report["holograms"] == sum(max(1, len(n["meshes"])) for n in (root, arm_node)),
          "hologram count reported (%d)" % report["holograms"])

    # --- transforms: composed manifest == Blender world matrix -----------
    def world_of(node, parent):
        rot = parent[0] @ tree.source_rotation(node["ang"])
        pos = parent[0] @ np.array(node["pos"]) + parent[1]
        return rot, pos

    ident = (np.eye(3), np.zeros(3))
    w_root = world_of(root, ident)
    w_arm = world_of(arm_node, w_root)
    for name, obj, w in (("entity", ent, w_root), ("Arm", arm, w_arm)):
        loc, rotq, _scale = obj.matrix_world.decompose()
        check(np.allclose(w[1], np.array(loc), atol=1e-3), "%s position matches Blender world (%s)" % (name, np.round(w[1], 3)))
        check(np.allclose(w[0], np.array(rotq.to_matrix()), atol=1e-4), "%s rotation matches Blender world" % name)

    # --- baked vertices land on Blender's evaluated geometry --------------
    depsgraph = ctx.evaluated_depsgraph_get()

    def blender_points(objs):
        pts = []
        for o in objs:
            ev = o.evaluated_get(depsgraph)
            me = ev.to_mesh()
            pts.append(np.array([ev.matrix_world @ v.co for v in me.vertices]))
            ev.to_mesh_clear()
        return np.vstack(pts)

    def obj_points(node, world):
        pts = []
        for m in node["meshes"]:
            for line in files[m["file"]].splitlines():
                if line.startswith("v "):
                    pts.append([float(x) for x in line.split()[1:4]])
        return np.array(pts) @ world[0].T + world[1]

    def nearest_gap(a, b):
        worst = 0.0
        for i in range(0, len(a), 200):
            d = np.linalg.norm(a[i:i + 200, None, :] - b[None, :, :], axis=2).min(axis=1)
            worst = max(worst, float(d.max()))
        return worst

    got, want = obj_points(arm_node, w_arm), blender_points(arm_members)
    gap = max(nearest_gap(got, want), nearest_gap(want, got))
    check(len(got) == len(want) and gap < 1e-3, "Arm's merged vertices equal its cubes' world vertices (gap %.2e)" % gap)

    # A split group repeats the vertices along the cut in both files, so only the point sets are compared.
    got, want = obj_points(root, w_root), blender_points([direct, big])
    gap = max(nearest_gap(got, want), nearest_gap(want, got))
    check(len(got) >= len(want) and gap < 1e-3,
          "entity's merged and split vertices equal Blender's world vertices (%d vs %d, gap %.2e)" % (len(got), len(want), gap))

    # --- loader chip ------------------------------------------------------
    code = tree.loader_code("https://raw.githubusercontent.com/user/repo/main/", "proj")
    check('"https://raw.githubusercontent.com/user/repo/main/"' in code and '"proj"' in code, "loader points at the repo and project")
    check("__REPO_URL__" not in code and "__PROJECT__" not in code, "loader has no unreplaced placeholders")
    check("local DEBUG = false" in code and "local YAW_OFFSET = 0" in code, "loader exposes DEBUG and YAW_OFFSET")
except Exception:
    traceback.print_exc()
    check(False, "starfall tree test crashed")

addon.unregister()
print("\nRESULT:", "ALL PASSED" if not failures else "%d FAILED" % len(failures))
sys.exit(1 if failures else 0)
