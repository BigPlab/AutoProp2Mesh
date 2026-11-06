# AutoProp2Mesh

A Blender 4.2 – 5.2 extension for building [Prop2Mesh](https://github.com/ACF-Team/Prop2Mesh) entities in Blender and exporting them as AdvDupe2 (revision 5) dupes for Garry's Mod. 

This was built with Claude Opus 5.5 as a test of its capabilities; I'm only going to semi-maintain this project for my personal use cases, but PR's are welcome if something breaks or you want something

**New here? Read the [User Guide](docs/USER_GUIDE.md).**

## Install

1. Download `autoprop2mesh-<version>.zip` from the latest release on the **Releases** page. Or build it yourself with `python tools/build_extension.py`, which writes it to `build/`.
2. In Blender, go to **Edit > Preferences > Get Extensions**, open the drop-down menu, choose **Install from Disk…**, and pick the zip.
3. In the extension's preferences:
   - The Garry's Mod folder is auto-detected through Steam.
   - Add any extra content folders, e.g. a shared legacy addons tree. A folder counts as content if it holds `models/` or `materials/`, and folders of such folders also work.

The first content scan takes about 10 seconds and runs in the background. After that, a cached index makes it take about 0.5 seconds.

## Workflow

| Step | How |
|---|---|
| Add an entity | **Add > Prop2Mesh Entity**, or the **P2M** sidebar tab (N panel) |
| Pick its model | Use the model field in the sidebar. 📁 opens the model browser (with previews), 🔍 searches by path |
| Add controllers | Use the controller list in the sidebar. Each controller has a name, color + alpha, material, UV scale and bump |
| Attach geometry | Select the objects, then the entity last, and press **Ctrl+P > Attach mesh to Controller …** |
| Nest entities | Parent an entity to another entity (normal Ctrl+P). The parenting is exported |
| Export | **File > Export > AdvDupe2 Prop2Mesh (.txt)**. It defaults to `garrysmod/data/advdupe2` |
| Export for Starfall | **File > Export > Starfall Mesh Tree**. Writes OBJ meshes and a manifest into a local clone of a GitHub repository; a Starfall chip builds them client-side. See the [User Guide](docs/USER_GUIDE.md#starfall-mesh-tree-client-side-meshes) |

- **Parts:** any mesh, curve, surface, metaball or text object below an entity is a part, including indirect children. A part uses its own controller, or inherits the one set on the nearest object above it.
- **Exported geometry:** the evaluated geometry (with modifiers applied). The entity's own model is never exported as geometry; it is only the entity's `Model`.
- **Materials:** parts get their controller's material in object-linked slots, so their own materials are kept and come back when they are detached or unparented.
- **Preview:** Material Preview shows the texture × color with Prop2Mesh's box-projected UVs. Solid view with **Color: Texture** shows the same thing, and **Color: Material** shows the flat controller color.
- **Shading:** set per part in the sidebar. **Auto** exports flat or smooth from the mesh, using the *Smooth by Angle* modifier's angle when one is present.
- **Coordinates:** 1 Blender unit = 1 Source unit by default (change it in the sidebar's *Units / BU*). Positions map straight across, and +X is the entity's forward. Blender's world origin is the point the dupe pastes at.

## Model parts

A model part is a Prop2Mesh part built from a game model, just like a prop_physics turned into P2M. Only the model path and placement are exported, never vertices.

| Step | How |
|---|---|
| Add one | **Add > Prop2Mesh Model Part** (or *Add Model Part* in the sidebar), then attach it with **Ctrl+P** like a mesh |
| Model | The same model field, browser and search as entities |
| Body groups | Pick from the drop-downs in the Part panel. They are previewed and exported as P2M's bodygroup mask |
| Scale | The object's scale (non-uniform is fine) |
| Clipping | **Add Clip Plane** creates a child plane. Move and rotate it to cut the model live. The arrow points to the side that is kept, and **Flip** reverses it. Like P2M, cuts are left open |
| Shading | Model normals, or **Flat Shading**, plus **Render Inside** |

With a controller UV scale of 0, model parts keep the model's own UVs; otherwise they are box-projected like meshes, which is what Prop2Mesh does.

## Things Prop2Mesh itself ignores

- **UVs:** Prop2Mesh box-projects UVs from vertex positions, so your UV unwraps don't carry over. The preview shows the real result.
- **Normals:** normals are recomputed from faces (flat, or smoothed by angle), so custom split normals are lost.
- **Triangle limit:** a single part is limited to 21,333 triangles. Larger objects are split into several parts automatically.

## Layout

```
src/autoprop2mesh/
  core/            pure Python + numpy, no bpy (testable outside Blender)
    vfs.py         GMod GAME search path: legacy addons, workshop GMA/.bin, VPKs, mounted games
    archives.py    VPK, GMA and legacy .bin readers (no extraction to disk)
    studiomdl.py   MDL/VVD/VTX loader      vtf.py  VTF decoder     vmt.py  VMT parser
    ad2.py         AdvDupe2 rev 5 codec    gmod_lzma.py  util.Compress format
    p2m.py         Prop2Mesh part lists (mesh + model parts) and dupe entities
    starfall.py    OBJ writer for Starfall's mesh parser (used by tree.py)
    tree.py        Starfall mesh tree: pivots, merged meshes, manifest.json and the loader chip
    clipping.py    port of P2M's applyClippingPlane
    raster.py      software renderer for model browser previews
  content.py       content -> Blender meshes, images, materials
  materials.py     controller materials      uvpreview.py  Geometry Nodes UV preview
  modelparts.py    model parts, body groups, clip planes
  sync.py          keeps parts bound to their controller
  export.py        gather + coordinate conversion + export operator
  browser.py, ops.py, ui.py, props.py, prefs.py
tests/blender_integration.py   end-to-end test (needs a GMod install)
tests/clip_stress.py           clip plane stress test (needs a GMod install)
tests/starfall_tree.py          Starfall mesh tree export test (no GMod install needed)
tools/build_extension.py       builds the release zip (used by the GitHub workflow)
```

## Testing

These need a Garry's Mod install:

```
blender -b --factory-startup --python tests/blender_integration.py
blender -b --factory-startup --python tests/clip_stress.py
```

The Starfall mesh tree test does not need Garry's Mod:

```
blender -b --factory-startup --python tests/starfall_tree.py
```

## Releases

Every push to `main` (or `master`) runs `.github/workflows/release.yml`. It builds the zip with `tools/build_extension.py` and publishes it as a GitHub release named after the commit date (UTC) and the commit count, for example `2026.10.01.42`.

Blender only accepts three-part semantic versions in the manifest, so the extension version inside the zip is written as `2026.1001.42`. It carries the same date and count, and every later build still compares as newer.
