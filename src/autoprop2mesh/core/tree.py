"""Starfall mesh-tree export: the Blender parent hierarchy becomes a folder tree
of OBJ files plus a manifest.json, and a generic client-side loader chip
rebuilds it as parented holograms.

A node is a pivot (it keeps its own hologram, so it can be animated and can have
children) when it has children or has no mesh. A mesh with no children is a rigid
attachment of its parent pivot: its vertices are baked into the pivot's frame and
merged with the pivot's other meshes of the same color, material and UV scale, so
everything in a pivot folder such as `arm` rides on one hologram.

Layout (a pivot gets a folder holding its merged meshes):

    manifest.json
    loader.lua
    hull/mesh_1.obj             (the hull pivot's merged meshes)
    hull/torso/mesh_1.obj
    hull/torso/mesh_2.obj       (a second color/material group)

Every manifest node has a position/angle relative to its parent node (Source
units, QAngle pitch/yaw/roll) and a list of meshes {file, color, material}.
"""

import numpy as np

from . import p2m, starfall

MANIFEST_NAME = "manifest.json"
LOADER_NAME = "loader.lua"


class TreeNode:
    def __init__(self, name, pos, ang, chunks=(), color=(255, 255, 255, 255),
                 material=p2m.DEFAULT_MATERIAL, uvs=0):
        self.name = name
        self.pos = pos            # relative to the parent node, Source units
        self.ang = ang            # (pitch, yaw, roll) degrees, relative to the parent node
        self.chunks = list(chunks)  # PartGeometry chunks in this node's frame
        self.color = color
        self.material = material
        self.uvs = uvs
        self.children = []


def _unique(name, used):
    base = starfall.safe_name(name)
    candidate, i = base, 2
    while candidate.lower() in used:
        candidate = "%s_%d" % (base, i)
        i += 1
    used.add(candidate.lower())
    return candidate


def _vec(v, decimals=5):
    return [round(float(x), decimals) + 0.0 for x in v]


def source_rotation(ang):
    """3x3 matrix of a Source (pitch, yaw, roll) angle: Rz(yaw) Ry(pitch) Rx(roll)."""
    p, y, r = np.radians(ang)
    cp, sp, cy, sy, cr, sr = np.cos(p), np.sin(p), np.cos(y), np.sin(y), np.cos(r), np.sin(r)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    return rz @ ry @ rx


def is_pivot(node):
    return bool(node.children) or not node.chunks


def _in_frame(chunks, pos, ang):
    """The chunks moved from a child's frame into its parent's frame."""
    rot = source_rotation(ang)
    out = []
    for c in chunks:
        moved = c.positions @ rot.T + np.asarray(pos, dtype=np.float64)
        out.append(p2m.PartGeometry(c.name, moved, c.triangles, c.vsmooth, c.vinside))
    return out


def _with_back_faces(chunks):
    """Render Inside parts also draw their back faces: add a copy with the winding
    reversed (its normals then point inward). Starfall has no per-mesh equivalent."""
    out = []
    for c in chunks:
        out.append(c)
        if c.vinside:
            out.append(p2m.PartGeometry(c.name + ".in", c.positions, c.triangles[:, ::-1], c.vsmooth, False))
    return out


def mesh_groups(node, nocull=False):
    """[(color, material, uvs, [chunks in node's frame])] for the node's own mesh and
    its rigid (childless mesh) children, merged per color/material/UV scale.
    Render Inside parts get back faces, unless nocull already draws both sides."""
    groups = {}

    def add(owner, chunks):
        if chunks:
            if not nocull:
                chunks = _with_back_faces(chunks)
            key = (tuple(int(c) for c in owner.color), owner.material, int(owner.uvs))
            groups.setdefault(key, []).extend(chunks)

    add(node, node.chunks)
    for child in node.children:
        if not is_pivot(child):
            add(child, _in_frame(child.chunks, child.pos, child.ang))
    return [(k[0], k[1], k[2], v) for k, v in groups.items()]


def _batches(chunks):
    """Packs chunks into batches of at most MAX_PART_TRIANGLES (one Starfall mesh each)."""
    batch, count = [], 0
    for piece in chunks:  # already split to at most MAX_PART_TRIANGLES each
        n = len(piece.triangles)
        if batch and count + n > p2m.MAX_PART_TRIANGLES:
            yield batch
            batch, count = [], 0
        batch.append(piece)
        count += n
    if batch:
        yield batch


def _emit(node, parent_dir, used, files, report, invert_normals, nocull):
    name = _unique(node.name, used)
    node_dir = parent_dir + name + "/"
    out = {"name": node.name, "pos": _vec(node.pos), "ang": _vec(node.ang)}
    meshes = []
    for color, material, uvs, chunks in mesh_groups(node, nocull):
        size = uvs if uvs > 0 else starfall.DEFAULT_UV_SIZE
        for batch in _batches(chunks):
            path = "%smesh_%d.obj" % (node_dir, len(meshes) + 1)
            files[path] = starfall.obj_file_text(batch, float(size), invert_normals, single_object=True)
            report["triangles"] += sum(len(c.triangles) for c in batch)
            # The loader puts every mesh on a 1x1x1 cube hologram whose own render bounds
            # are tiny, so the mesh's real bounds are needed or big meshes get culled.
            pts = np.vstack([c.positions[np.unique(c.triangles)] for c in batch if len(c.triangles)])
            meshes.append({"file": path, "color": list(color), "material": material,
                           "bounds": [_vec(pts.min(axis=0)), _vec(pts.max(axis=0))]})
    out["meshes"] = meshes
    report["holograms"] += max(1, len(meshes) * (2 if nocull else 1))  # nocull draws each mesh twice
    pivots = [c for c in node.children if is_pivot(c)]
    if pivots:
        child_used = set()
        out["children"] = [_emit(c, node_dir, child_used, files, report, invert_normals, nocull) for c in pivots]
    report["nodes"] += 1
    return out


def manifest_files(manifest):
    """Relative paths of the OBJ files a manifest lists (version 1 had one per node)."""
    out = []

    def walk(node):
        out.extend(m["file"] for m in node.get("meshes", ()))
        if node.get("file"):
            out.append(node["file"])
        for c in node.get("children", ()):
            walk(c)

    for n in manifest.get("nodes", ()):
        walk(n)
    return out


def build(roots, name="mech", invert_normals=False, nocull=False, yaw=0.0):
    """roots: list of TreeNode. Returns (manifest dict, files{relpath: text}, report)."""
    files = {}
    report = {"triangles": 0, "files": 0, "nodes": 0, "holograms": 0}
    used = set()
    nodes = [_emit(r, "", used, files, report, invert_normals, nocull) for r in roots]
    report["files"] = len(files)
    manifest = {"version": 2, "name": name, "nocull": bool(nocull), "yaw": float(yaw), "nodes": nodes}
    return manifest, files, report


# --------------------------------------------------------------------------
# Loader chip
# --------------------------------------------------------------------------

LOADER_TEMPLATE = r'''--@name P2M Mesh Tree
--@author AutoProp2Mesh
--@client

-- Generated by AutoProp2Mesh (the same chip works for every project; change PROJECT).
-- Place this chip where the model's origin should be: the tree is parented to it.
-- Downloads manifest.json, then every OBJ it lists (several at a time), and builds
-- one hologram per node (its mesh, parented to its parent's hologram).
-- Uses about one hologram per node; Starfall's default cap is 200 (sf_holograms_max).
--
-- Animate by moving nodes:  P2M.nodes["hull/torso"]:setLocalAngles(Angle(0, yaw, 0))
-- The only things to edit: the repository's raw URL and the project folder inside it.
local REPO_URL = __REPO_URL__
local PROJECT = __PROJECT__
-- Extra turn of the whole model about the chip's up axis, added to the export's own
-- forward-axis setting (manifest "yaw"). 90 turns a Blender -Y-facing model to face +X.
local YAW_OFFSET = 0
-- Show every pivot (the node holograms that carry parts and can be animated) as a small magenta
-- cube with a red nub along its forward (+X) axis. Costs up to two extra holograms per pivot.
local DEBUG = false
local BASE_URL = REPO_URL .. PROJECT .. "/"
-- Not models/holograms/cube.mdl: Starfall draws a mesh turned 90 degrees about up on that model
-- (measured in game), while this model draws it in the hologram's own frame.
local HOLO_MODEL = "models/hunter/blocks/cube1x1x1.mdl"

P2M = {nodes = {}, loaded = false}

-- Downloads run in parallel (as many as Starfall allows); results land in `bodies`.
-- bodies[name] is the text, false if the request failed, nil while pending.
local bodies, queue, queued = {}, {}, 0
local wake  -- resumes the loader; defined below. Download callbacks call it.

local function want(name)
    if bodies[name] == nil and not queue[name] then
        queue[name] = true
        queued = queued + 1
        queue[queued] = name
    end
end

local next_request = 1
local pump
function pump()
    while next_request <= queued and http.canRequest() do
        local name = queue[next_request]
        next_request = next_request + 1
        local url = BASE_URL .. name
        http.get(url, function(b, _, _, code)
                if code ~= 200 then
                    print("P2M: HTTP " .. tostring(code) .. " for " .. url)
                    bodies[name] = false
                else
                    bodies[name] = b
                end
                pump()  -- a request slot just freed up
                wake()
            end,
            function(reason)
                bodies[name] = false
                print("P2M: failed to download " .. url .. ": " .. tostring(reason))
                pump()
                wake()
            end)
    end
end

local function get(name)
    want(name)
    while bodies[name] == nil do coroutine.yield("wait") end  -- idle until a download callback wakes the loader
    local body = bodies[name]
    bodies[name] = nil  -- the OBJ text is only needed once
    queue[name] = nil
    return body
end

-- A node's meshes; manifest version 1 had a single file/color/material on the node.
local function meshList(node)
    if node.meshes then return node.meshes end
    if node.file then return {{file = node.file, color = node.color, material = node.material}} end
    return {}
end

local function files(node, out)
    for _, m in ipairs(meshList(node)) do out[#out + 1] = m.file end
    for _, c in ipairs(node.children or {}) do files(c, out) end
    return out
end

local warned = false
local function newHolo(parent)
    while not hologram.canSpawn() do
        if not warned then
            warned = true
            print("P2M: out of holograms (Starfall limit); remove other hologram chips and respawn")
        end
        coroutine.yield("spawn")
    end
    local h = hologram.create(parent:getPos(), parent:getAngles(), HOLO_MODEL)
    h:setParent(parent)
    return h
end

-- A node (pivot) is one hologram: it carries its first mesh (the hologram limit is
-- low, so no separate invisible anchor when there is a mesh) and its child pivots
-- are parented to it. Further meshes of the node (other colors/materials) ride on
-- extra holograms parented to it. Nodes without a mesh get an invisible hologram.
local function build(node, parent, path, nocull, yaw)
    path = path == "" and node.name or (path .. "/" .. node.name)
    local anchor = newHolo(parent)
    local pos, ang = Vector(node.pos[1], node.pos[2], node.pos[3]), Angle(node.ang[1], node.ang[2], node.ang[3])
    if yaw then pos, ang = localToWorld(pos, ang, Vector(0, 0, 0), Angle(0, yaw, 0)) end  -- roots only
    anchor:setLocalPos(pos)
    anchor:setLocalAngles(ang)
    P2M.nodes[path] = anchor

    local drawn = false
    for _, m in ipairs(meshList(node)) do
        local body = get(m.file)
        if body then
            local ok, mat = pcall(material.load, m.material)
            local c = m.color
            for _, msh in pairs(mesh.createFromObj(body, true, false)) do
                for _, mode in ipairs(nocull and {0, 1} or {0}) do
                    local h = anchor
                    if drawn then
                        h = newHolo(anchor)
                        h:setLocalPos(Vector(0, 0, 0))
                        h:setLocalAngles(Angle(0, 0, 0))
                    end
                    drawn = true
                    h:setMesh(msh)
                    if m.bounds then
                        local b = m.bounds
                        h:setRenderBounds(Vector(b[1][1], b[1][2], b[1][3]), Vector(b[2][1], b[2][2], b[2][3]))
                    end
                    if nocull then h:setCullMode(mode) end
                    if ok and mat then h:setMeshMaterial(mat) end
                    h:setColor(Color(c[1], c[2], c[3], c[4]))
                end
            end
        end
    end
    if DEBUG then
        local function paint(h, r, g, b)
            h:setMaterial("models/debug/debugwhite")
            h:setColor(Color(r, g, b))
        end
        if drawn then  -- the anchor carries a mesh, so the marker is a child
            local marker = newHolo(anchor)
            marker:setLocalPos(Vector(0, 0, 0))
            marker:setLocalAngles(Angle(0, 0, 0))
            marker:setScale(Vector(0.25, 0.25, 0.25))
            paint(marker, 255, 0, 255)
        else           -- no mesh: the anchor itself is the marker
            anchor:setScale(Vector(0.25, 0.25, 0.25))
            paint(anchor, 255, 0, 255)
        end
        local nub = newHolo(anchor)
        nub:setLocalPos(Vector(18, 0, 0))
        nub:setLocalAngles(Angle(0, 0, 0))
        nub:setScale(Vector(0.5, 0.1, 0.1))
        paint(nub, 255, 0, 0)
    elseif not drawn then
        anchor:setNoDraw(true)
    end
    for _, child in ipairs(node.children or {}) do
        build(child, anchor, path, nocull)
    end
end

local function load()
    local text = get("manifest.json")
    if not text then return end
    local manifest = json.decode(text)
    print("P2M: loading " .. manifest.name)
    local started = timer.systime()
    for _, node in ipairs(manifest.nodes) do
        for _, f in ipairs(files(node, {})) do want(f) end  -- start every download up front
    end
    local yaw = (manifest.yaw or 0) + YAW_OFFSET
    for _, node in ipairs(manifest.nodes) do
        build(node, chip(), "", manifest.nocull, yaw)
    end
    P2M.loaded = true
    if DEBUG then
        for path in pairs(P2M.nodes) do print("P2M pivot: " .. path) end
    end
    print(string.format("P2M: done, %d nodes in %.1fs", table.count(P2M.nodes), timer.systime() - started))
end

-- Needs the client to grant the permissions Starfall asks for (http, mesh, material, hologram, parenting).
-- The think hook only exists while there is work to do. When the loader has to wait (for a download,
-- or for a free hologram slot) the hook is removed, so an idle chip costs nothing; download callbacks
-- and a timer put it back. Starfall's threaded mesh parser yields every ~100 lines, so while parsing
-- the loader keeps resuming within the tick as long as there is quota.
local co = coroutine.create(load)
local hooked = false

local function sleep()
    if hooked then
        hooked = false
        hook.remove("think", "p2m_loader")
    end
end

local function step()
    pump()
    local me = chip()
    local budget, resumes, res = quotaMax() * 0.7, 0, nil
    while coroutine.status(co) ~= "dead" and resumes < 2000
            and me:getQuotaUsed() < budget and quotaAverage() < quotaMax() * 0.9 do
        local ok
        ok, res = coroutine.resume(co)
        resumes = resumes + 1
        if not ok then
            print("P2M: load failed: " .. tostring(res))
            break
        end
        if res == "wait" or res == "spawn" then break end
    end
    if coroutine.status(co) == "dead" then
        sleep()
    elseif res == "wait" then
        sleep()  -- a download callback wakes us
        if next_request <= queued then timer.simple(0.5, wake) end  -- requests still held back by canRequest: retry
    elseif res == "spawn" then
        sleep()  -- no callback announces a free hologram slot, so poll slowly
        timer.simple(0.5, wake)
    end
end

function wake()
    if hooked or coroutine.status(co) == "dead" then return end
    hooked = true
    hook.add("think", "p2m_loader", step)
end

wake()
'''


def loader_code(repo_url, project):
    """repo_url: raw base of the repository, ending in '/' (starfall.raw_base_url)."""
    return (LOADER_TEMPLATE.replace("__REPO_URL__", starfall._lua_str(repo_url))
            .replace("__PROJECT__", starfall._lua_str(project)))
