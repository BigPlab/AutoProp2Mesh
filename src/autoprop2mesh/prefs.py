import os
import re

import bpy
from bpy.props import BoolProperty, CollectionProperty, IntProperty, StringProperty

from .core import steam


class P2M_SearchPath(bpy.types.PropertyGroup):
    path: StringProperty(
        name="Path", subtype="DIR_PATH",
        description="A content folder (has models/ or materials/), or a folder of such folders",
    )


class P2M_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    gmod_dir: StringProperty(
        name="Garry's Mod Folder", subtype="DIR_PATH",
        description="The GarrysMod install folder (the one containing garrysmod/). Leave empty to auto-detect",
    )
    extra_paths: CollectionProperty(type=P2M_SearchPath)
    extra_paths_index: IntProperty()
    mount_workshop: BoolProperty(name="Mount Workshop Addons", default=True)
    mount_games: BoolProperty(
        name="Mount Games", default=True,
        description="Mount the games enabled in Garry's Mod (cfg/mountdepots.txt and cfg/mount.cfg)",
    )
    texture_size: IntProperty(
        name="Max Texture Size", default=1024, min=64, max=4096,
        description="Largest texture mip level loaded for previews",
    )

    repo_dir: StringProperty(
        name="Mesh Repository Folder", subtype="DIR_PATH",
        description="Local clone of the GitHub repository (e.g. a GitHub Desktop folder) that Starfall mesh projects are exported into",
    )
    github_user: StringProperty(name="GitHub User", description="Leave empty to read it from the repository's git config")
    github_repo: StringProperty(name="GitHub Repository", description="Leave empty to read it from the repository's git config")
    github_branch: StringProperty(name="Branch", description="Leave empty to use the repository's checked-out branch")

    def draw(self, context):
        from . import content
        layout = self.layout
        col = layout.column()
        col.prop(self, "gmod_dir")
        detected = resolved_gmod_dir(self)
        col.label(text="Using: %s" % (detected or "not found"),
                  icon="CHECKMARK" if detected else "ERROR")

        box = layout.box()
        box.label(text="Extra Content Folders")
        row = box.row()
        row.template_list("UI_UL_list", "p2m_paths", self, "extra_paths", self, "extra_paths_index", rows=3)
        sub = row.column(align=True)
        sub.operator("p2m.search_path_add", icon="ADD", text="")
        sub.operator("p2m.search_path_remove", icon="REMOVE", text="")
        if 0 <= self.extra_paths_index < len(self.extra_paths):
            box.prop(self.extra_paths[self.extra_paths_index], "path", text="")

        row = layout.row()
        row.prop(self, "mount_workshop")
        row.prop(self, "mount_games")
        layout.prop(self, "texture_size")

        box = layout.box()
        box.label(text="Starfall Mesh Repository")
        box.prop(self, "repo_dir")
        user, repo, branch = resolved_github(self)
        for prop in ("github_user", "github_repo", "github_branch"):
            box.prop(self, prop)
        box.label(text="Using: %s/%s @ %s" % (user or "?", repo or "?", branch or "?"),
                  icon="CHECKMARK" if user and repo else "ERROR")

        row = layout.row()
        row.label(text=content.status_text())
        row.operator("p2m.rebuild_content", icon="FILE_REFRESH")


class P2M_OT_search_path_add(bpy.types.Operator):
    bl_idname = "p2m.search_path_add"
    bl_label = "Add Content Folder"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        p = get_prefs()
        p.extra_paths.add()
        p.extra_paths_index = len(p.extra_paths) - 1
        return {"FINISHED"}


class P2M_OT_search_path_remove(bpy.types.Operator):
    bl_idname = "p2m.search_path_remove"
    bl_label = "Remove Content Folder"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        p = get_prefs()
        if 0 <= p.extra_paths_index < len(p.extra_paths):
            p.extra_paths.remove(p.extra_paths_index)
            p.extra_paths_index = max(0, p.extra_paths_index - 1)
        return {"FINISHED"}


def get_prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


_detected = []


def resolved_gmod_dir(prefs=None):
    prefs = prefs or get_prefs()
    if prefs and prefs.gmod_dir:
        p = bpy.path.abspath(prefs.gmod_dir).rstrip("\\/")
        if os.path.isdir(os.path.join(p, "garrysmod")):
            return p
        # Accept the garrysmod/ folder itself, too.
        if os.path.basename(p).lower() == "garrysmod" and os.path.isdir(p):
            return os.path.dirname(p)
    if not _detected:
        try:
            _detected.append(steam.find_gmod()[0])
        except Exception:
            _detected.append(None)
    return _detected[0]


def _github_remote(config_text):
    """(user, repo) of the clone's GitHub remote: origin first, else the first GitHub remote."""
    urls = {}
    remote = None
    for line in config_text.splitlines():
        line = line.strip()
        if line.startswith("["):
            m = re.match(r'\[remote\s+"([^"]+)"\]', line)
            remote = m.group(1) if m else None
        elif remote and re.match(r"url\s*=", line):
            urls.setdefault(remote, line.split("=", 1)[1].strip())
    for name in sorted(urls, key=lambda n: n != "origin"):
        m = re.search(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", urls[name])
        if m:
            return m.group(1), m.group(2)
    return None, None


def _git_info(repo_dir):
    """(user, repo, branch) read from a clone's .git folder; any may be None."""
    user = repo = branch = None
    git = os.path.join(repo_dir, ".git")
    try:
        with open(os.path.join(git, "config"), encoding="utf-8", errors="replace") as f:
            user, repo = _github_remote(f.read())
    except OSError:
        pass
    try:
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as f:
            m = re.match(r"ref: refs/heads/(.+)", f.read().strip())
        if m:
            branch = m.group(1)
    except OSError:
        pass
    return user, repo, branch


def resolved_repo_dir(prefs=None):
    prefs = prefs or get_prefs()
    if prefs and prefs.repo_dir:
        return os.path.abspath(bpy.path.abspath(prefs.repo_dir))
    return None


def resolved_github(prefs=None):
    """(user, repo, branch): preferences first, then the clone's git config."""
    prefs = prefs or get_prefs()
    if prefs is None:
        return None, None, None
    repo_dir = resolved_repo_dir(prefs)
    gu, gr, gb = _git_info(repo_dir) if repo_dir else (None, None, None)
    return (prefs.github_user.strip() or gu, prefs.github_repo.strip() or gr,
            prefs.github_branch.strip() or gb or "main")


def default_dupe_dir():
    gmod = resolved_gmod_dir()
    if not gmod:
        return None
    return os.path.join(gmod, "garrysmod", "data", "advdupe2")


classes = (P2M_SearchPath, P2M_AddonPreferences, P2M_OT_search_path_add, P2M_OT_search_path_remove)
