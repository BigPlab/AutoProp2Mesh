"""OBJ meshes for Starfall's mesh parser, shared by the Starfall mesh tree export.

Format notes (verified against StarfallEx sources):
  * SF.ParseObj needs `o <name>`, `v`, `vt`, `vn` and `f v/vt/vn` faces; faces
    with a missing vt or vn throw. Any unknown tag throws too.
  * SF.ParseObj reverses the vertex order of every face itself, so faces are
    written in Blender's counter-clockwise order with outward normals.
    invert_normals flips both the winding and the normals.
  * A mesh is limited to 65535 vertices (unindexed), so a chunk is at most
    p2m.MAX_PART_TRIANGLES triangles; one `o` group becomes one Starfall mesh.
"""

import re

import numpy as np

from . import p2m

DEFAULT_UV_SIZE = 64.0  # Source units per texture tile when a controller has no UV size


RAW_URL = "https://raw.githubusercontent.com/%s/%s/%s/"


def safe_name(name):
    """File-name safe, lowercase ASCII."""
    s = re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_")
    return s or "entity"


def _face_normals(positions, tris):
    a, b, c = positions[tris[:, 0]], positions[tris[:, 1]], positions[tris[:, 2]]
    return np.cross(b - a, c - a)  # length = 2 * area


def _unit(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return v / n


def corner_normals(positions, tris, vsmooth):
    """Normals per triangle corner, shape (T, 3, 3). vsmooth None = flat,
    otherwise smoothing angle in degrees (>= 180 smooths everything)."""
    fn = _face_normals(positions, tris)
    unit_fn = _unit(fn)
    out = np.repeat(unit_fn[:, None, :], 3, axis=1)
    if not vsmooth:
        return out
    if vsmooth >= 179.999:
        acc = np.zeros_like(positions)
        for k in range(3):
            np.add.at(acc, tris[:, k], fn)  # area weighted
        return _unit(acc)[tris]
    cos_limit = np.cos(np.radians(vsmooth))
    corners = {}
    for t, tri in enumerate(tris.tolist()):
        for k, v in enumerate(tri):
            corners.setdefault(v, []).append((t, k))
    for entries in corners.values():
        if len(entries) < 2:
            continue
        ts = np.array([t for t, _ in entries])
        n = unit_fn[ts]
        weights = (n @ n.T >= cos_limit) * np.linalg.norm(fn[ts], axis=1)[None, :]
        smooth = _unit(weights @ n)
        for (t, k), s in zip(entries, smooth):
            out[t, k] = s
    return out


def box_uvs(corner_pos, face_normals, uv_size):
    """Box projection onto the axis most aligned with each face. (T, 3, 2)"""
    axis = np.argmax(np.abs(face_normals), axis=1)
    drop = {0: (1, 2), 1: (0, 2), 2: (0, 1)}
    out = np.empty((len(corner_pos), 3, 2))
    for ax, (ua, va) in drop.items():
        sel = axis == ax
        out[sel, :, 0] = corner_pos[sel][:, :, ua] / uv_size
        out[sel, :, 1] = corner_pos[sel][:, :, va] / uv_size
    return out


def _fmt(x):
    return p2m._fmt(x, 5)


def obj_file_text(chunks, uv_size, invert_normals=False, single_object=False):
    """OBJ text for a list of PartGeometry chunks (already split). single_object puts
    all chunks in one `o` group, which Starfall turns into one mesh."""
    lines = []
    v_off = vt_off = vn_off = 0
    for n, chunk in enumerate(chunks):
        tris = chunk.triangles
        if len(tris) == 0:
            continue
        used, inverse = np.unique(tris.reshape(-1), return_inverse=True)
        local_tris = inverse.reshape(-1, 3)
        pos = chunk.positions[used]
        normals = corner_normals(pos, local_tris, chunk.vsmooth)            # (T,3,3)
        if invert_normals:
            normals = -normals
        uvs = box_uvs(pos[local_tris], _face_normals(pos, local_tris), uv_size)  # (T,3,2)
        if not single_object or n == 0:
            lines.append("o %s\n" % p2m._ascii(chunk.name).replace(" ", "_"))
        lines += ["v %s %s %s\n" % (_fmt(x), _fmt(y), _fmt(z)) for x, y, z in pos.tolist()]
        lines += ["vt %s %s\n" % (_fmt(u), _fmt(v)) for u, v in uvs.reshape(-1, 2).tolist()]
        lines += ["vn %s %s %s\n" % (_fmt(x), _fmt(y), _fmt(z)) for x, y, z in normals.reshape(-1, 3).tolist()]
        face = []
        for t, (a, b, c) in enumerate(local_tris.tolist()):
            i = t * 3
            corners = ((a, i), (b, i + 1), (c, i + 2))
            if invert_normals:
                corners = corners[::-1]
            face.append("f " + " ".join(
                "%d/%d/%d" % (v_off + v + 1, vt_off + k + 1, vn_off + k + 1) for v, k in corners) + "\n")
        lines += face
        v_off += len(pos)
        vt_off += len(local_tris) * 3
        vn_off += len(local_tris) * 3
    return "".join(lines)


def _lua_str(s):
    out = ['"']
    for ch in s:
        if ch in '"\\':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        elif 32 <= ord(ch) < 127:
            out.append(ch)
        else:
            out.append("_")
    out.append('"')
    return "".join(out)


def raw_base_url(user, repo, branch, subfolder):
    url = RAW_URL % (user.strip(), repo.strip(), (branch.strip() or "main"))
    sub = subfolder.strip().strip("/\\").replace("\\", "/")
    return url + (sub + "/" if sub else "")
