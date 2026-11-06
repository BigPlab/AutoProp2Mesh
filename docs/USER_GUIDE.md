# AutoProp2Mesh User Guide

AutoProp2Mesh lets you build [Prop2Mesh](https://github.com/ACF-Team/Prop2Mesh) contraptions in Blender and export them as an AdvDupe2 file that you paste in Garry's Mod.

It works with Blender 4.2 and newer.

---

## Contents

1. [Concepts](#1-concepts)
2. [Installing and first-time setup](#2-installing-and-first-time-setup)
3. [Quick start: your first export](#3-quick-start-your-first-export)
4. [Entities](#4-entities)
5. [Controllers](#5-controllers)
6. [Parts (your meshes)](#6-parts-your-meshes)
7. [Model parts (prop_physics-style parts)](#7-model-parts-prop_physics-style-parts)
8. [Building bigger things](#8-building-bigger-things)
9. [Previewing in the viewport](#9-previewing-in-the-viewport)
10. [Units, orientation and the paste point](#10-units-orientation-and-the-paste-point)
11. [Exporting and pasting in Garry's Mod](#11-exporting-and-pasting-in-garrys-mod)
12. [Limits and things Prop2Mesh ignores](#12-limits-and-things-prop2mesh-ignores)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Concepts

Prop2Mesh has three layers, and the add-on mirrors them:

| Prop2Mesh | In Blender | What it is |
|---|---|---|
| **Entity** (`sent_prop2mesh`) | An object made with **Add > Prop2Mesh Entity** | The thing you spawn. It has a model of its own, a position and a rotation |
| **Controller** | An entry in the entity's controller list | A colour + material. Everything attached to it renders with that look |
| **Part** | Any mesh, curve, text, … parented under the entity | The geometry. Each part belongs to one controller |

A **model part** is a special part made from a game model, like turning a prop_physics into Prop2Mesh. Only its model name and placement are exported; Prop2Mesh builds it from the model in game.

---

## 2. Installing and first-time setup

### Install

1. In Blender, go to **Edit > Preferences > Get Extensions**.
2. Open the **⌄** menu in the top right and choose **Install from Disk…**.
3. Pick `autoprop2mesh-<version>.zip`.
4. Make sure **AutoProp2Mesh** is ticked under **Add-ons**.

### Point it at your game content

Open the add-on's preferences: **Edit > Preferences > Add-ons > AutoProp2Mesh**, then expand it.

| Setting | What it does |
|---|---|
| **Garry's Mod Folder** | Leave empty to auto-detect it through Steam. The line underneath shows which folder is in use |
| **Extra Content Folders** | Add folders that hold extra content, such as a shared legacy addons tree. A folder can be a content folder itself (it has `models/` or `materials/`), or a folder of such folders, up to three levels deep |
| **Mount Workshop Addons** | Includes your subscribed workshop addons, both `.gma` and old `.bin` items |
| **Mount Games** | Includes the games you enabled in Garry's Mod (CSS, TF2, …) and anything in `cfg/mount.cfg` |
| **Max Texture Size** | The largest texture size loaded for previews. Lower it if Blender gets slow |
| **Rescan Content** | Use this after installing new addons or changing the settings above |

The add-on reads your game files the same way Garry's Mod does: legacy addons, workshop addons, the base game, then mounted games. Nothing is copied or extracted to disk.

> **The first scan takes about 10 seconds** and runs in the background. After that it takes under a second. Its progress shows at the top of the **P2M** sidebar tab.

---

## 3. Quick start: your first export

This builds the simplest case: one entity, one controller, one or more meshes.

1. **Add an entity:** in the 3D viewport, **Add > Prop2Mesh Entity**. A cube (`models/p2m/cube.mdl`) appears at the 3D cursor.
2. **Open the sidebar:** press **N**, then click the **P2M** tab.
3. **Make something:** add any mesh (for example **Add > Mesh > Monkey**) and model it however you like.
4. **Attach it:** select your mesh, then **Shift-click the entity so it is selected last**, and press **Ctrl+P**. Choose **Attach mesh to Controller #0…**.
5. **Style it:** in the sidebar, under **Entity**, pick a **Color** and a **Material** for controller #0. Click 🔍 next to the material to search every material you have.
6. **Export:** **File > Export > AdvDupe2 Prop2Mesh (.txt)**. The file browser opens in your `garrysmod/data/advdupe2` folder. Name the file and click **Export AdvDupe2 (Prop2Mesh)**.
7. **In game:** open the AdvDupe2 tool, find the file in its browser, open it, and paste.

---

## 4. Entities

Select an entity to see the **Entity** panel in the **P2M** sidebar tab.

### The entity's model

This is the model of the `sent_prop2mesh` itself, the thing you grab with the physgun. The model row has three buttons:

| Button | What it does |
|---|---|
| 📁 **Model Browser** | A Hammer-style browser (see below) |
| 🔍 **Search** | A quick type-ahead search over every model path |
| ⟳ **Reload** | Reloads the model from the game files |

You can also type a path straight into the field, such as `models/hunter/plates/plate.mdl`.

### The model browser

The browser opens over the 3D viewport and is laid out like Hammer's:

- **Folder tree (left):** every folder with models in it, from all your mounted content. Click **+** / **−** to expand or collapse a folder, and click a folder's name to show its models. The number on the right is how many models are inside it, including its subfolders.
- **Check subfolders for files:** shows the models of the selected folder *and* everything below it.
- **Filter:** just start typing. Words such as `drum c17` show only models whose path contains all of them. The filter searches below the selected folder; select **All Models** at the top of the tree to search everything.
- **Thumbnail grid:** click anywhere on a thumbnail to select it, and double-click to use it straight away. Scroll with the mouse wheel. The browser opens on the current model's folder, scrolled to it.
- **Tabs (bottom):** **Info** shows a larger preview, triangle and vertex counts and where the model comes from. **Materials** lists its materials, and **Body Groups** lists its body groups and their options.
- **Full path:** shows the selected model's path.
- **Keys:** **OK** or **Enter** uses the selection. **Cancel**, **Esc** or right-click closes the browser without changes.

Both browsers share these controls:

- **Scrolling:** use the mouse wheel, or drag the scrollbars (click a scrollbar's track to jump there). You can also hold the **middle mouse button** and move the mouse up or down: the further you move, the faster it scrolls. A quick middle-click without moving keeps this on until your next click. **Page Up** / **Page Down** also work.
- **Text fields:** click to place the cursor, drag or **Shift+arrows** to select, and double-click to select everything. **Ctrl+A** selects all, and **Ctrl+C** / **Ctrl+X** / **Ctrl+V** copy, cut and paste. **Ctrl+arrows** and **Ctrl+Backspace** / **Ctrl+Delete** work word by word, and **Home** / **End** jump to either end. You can select and copy the model browser's **Full path**, too.

Thumbnails appear as they finish rendering, usually within a second, and are reused for the rest of the session. While the browser is open, the viewport's own header, toolbar and sidebar are hidden. They come back when it closes.

If a model can't be loaded, the entity shows `error.mdl` and the panel says why. If even `error.mdl` is unavailable, it shows a yellow **!** made of blocks. The model path you typed is still what gets exported.

### Moving and rotating

Move and rotate entities like any object; their position and rotation are exported. **Don't scale entities.** Prop2Mesh entities have no scale, so the export ignores it and warns you. Your parts keep their size either way.

---

## 5. Controllers

Each entity has a list of controllers. Use **+** and **−** to add or remove them, and the arrows to reorder them. A controller's position in the list is its index in game (#0, #1, …).

| Setting | What it does in game |
|---|---|
| **Name** | Shown in Blender menus as `"Name"` instead of `#0`. Also exported as the controller's name |
| **Color** | Tints the material. Alpha below 1 makes the controller translucent |
| **Material** | Any Source material path, for example `phoenix_storms/metalset_1-2`. 📁 opens the material browser (see below), and 🔍 is a quick type-ahead search |
| **UV Scale** | Texture size in Source units per repeat. 0 uses Prop2Mesh's default (48). See [§12](#12-limits-and-things-prop2mesh-ignores) |
| **Bump** | Turn on for materials with normal maps, so they light correctly |

The buttons under the controller settings:

- **Attach Selected** attaches the selected objects to this controller.
- **Select Parts** selects everything attached to this controller.
- The part count shows how many objects are attached.

### The material browser

The 📁 button next to a controller's material opens a browser laid out like Hammer's texture browser:

- **Grid:** every material, shown as its texture with the name on a blue bar. Click a tile to select it, and double-click to apply it straight away. Scroll with the mouse wheel.
- **Size:** cycles the tile size between 64×64, 128×128 and 256×256.
- **Filter:** just start typing, for example `metal floor`.
- **Selection:** the selected material's name and its texture resolution are shown in the bottom bar.
- **Opaque / Translucent:** untick one to hide that kind of material. The check runs in the background, so the list fills in as it goes.
- **Only used materials:** shows only materials already used by controllers in this file.
- **Keys:** **Apply** or **Enter** sets the material. **Cancel**, **Esc** or right-click closes the browser without changes.

Removing a controller doesn't delete its parts. They become unassigned, lose the controller look, and are skipped on export until you attach them to another controller.

---

## 6. Parts (your meshes)

### What counts as a part

Any **mesh, curve, surface, metaball or text** object anywhere below an entity is a part. That includes objects parented to other objects that are parented to the entity. Exactly what you see is exported: modifiers, curve bevels and text are all applied.

The entity's own model is never exported as geometry. It is only the entity's model.

### Attaching

The easiest way: select the objects, select the entity **last**, press **Ctrl+P**, and choose **Attach mesh to Controller …**. This parents them to the entity and keeps them exactly where they are.

The Ctrl+P menu still has all of Blender's usual parenting options underneath. The add-on replaces Blender's Ctrl+P popup with an identical one that has the Prop2Mesh entries added. The same entries are also in **Object > Parent**.

### Which controller a part uses

A part uses its own controller if it has one. Otherwise it uses the controller of the nearest object above it, up to the entity. So you can attach a parent object once and everything under it follows.

To change it, select the part and use the controller drop-down in the **Part** panel:

- **Inherit from Parent** follows the object above it.
- **Controller …** pins the part to a specific controller.

A part with no controller (directly or inherited) is shown as **No controller (not exported)**.

### Your own materials are safe

When a part is attached, it shows its controller's material, but its own materials are kept underneath. Unparent it (**Alt+P**) or detach it and they come back.

### Per-part options

These are in the **Part** panel:

| Option | What it does |
|---|---|
| **Shading: Auto** | Flat if every face is flat-shaded. If any face is smooth, it smooths normals, using your *Smooth by Angle* modifier's angle if there is one |
| **Shading: Flat** | Always flat |
| **Shading: Smooth** | Smooths normals between faces that meet below **Smooth Angle** |
| **Render Inside** | Also draws the back faces, so the part is visible from inside |

---

## 7. Model parts (prop_physics-style parts)

A model part places a game model inside a controller, the way Prop2Mesh does when you convert real props. Prop2Mesh rebuilds it from the model in game, so it costs almost nothing in the dupe.

### Adding one

1. **Add > Prop2Mesh Model Part**, or **Add Model Part** in the sidebar.
2. Pick its model with the model field, the 📁 browser or 🔍 search, the same as for entities.
3. Attach it to a controller with **Ctrl+P**, like a mesh.

Model parts take on their controller's colour and material, just like in game. When they aren't attached, they show the model's own textures.

### Placement and scale

The object's position, rotation and **scale** are exported. Scale can be different on each axis.

> If a model part sits under a parent that is scaled unevenly *and* rotated, the part gets skewed. Prop2Mesh can't represent skew, so the export warns you.

### Body groups

If the model has body groups (for example the HL2 ammo crates' "ammo" group), the **Part** panel shows a drop-down for each one. The preview updates immediately, and the selection is exported.

### Clip planes

1. Select the model part and click **Add Clip Plane**. A wireframe square with an arrow appears.
2. **Move and rotate the plane.** The model is cut as you go, and **the side the arrow points to is kept**.
3. Use **Flip Clip Plane** (in the **Clip Plane** panel when the plane is selected) to keep the other side.
4. Add as many planes as you need. To remove one, delete the plane.

As in Prop2Mesh, cuts are left open, not capped. In Blender's default view you can see the inside walls through the cut.

### Shading and UVs

- **Flat Shading:** uses flat shading instead of the model's own normals.
- **Render Inside:** also draws back faces.
- **UVs:** with the controller's **UV Scale** at 0, a model part keeps the model's own texture mapping. With any other value it is box-projected like a mesh. This is the same as Prop2Mesh.

---

## 8. Building bigger things

### Several colours on one entity (emblems, decals)

1. Add one controller per colour or material.
2. Attach each group of meshes to its controller.
3. Export as usual: it is still one entity.

### Whole rigs (several entities)

Parent entities to other entities with Blender's normal **Ctrl+P > Object (Keep Transform)**. The parenting is exported, so the entities paste parented to each other in game.

Each entity owns the parts below it, up to the next entity. Parts under a child entity belong to that child entity, not to its parent.

### Copying entities

**Shift+D** on an entity duplicates it with its controllers. Each copy gets its own materials, so changing the colour on one doesn't change the other.

---

## 9. Previewing in the viewport

| Viewport shading | What you see |
|---|---|
| **Material Preview** | The controller material: texture × colour, with alpha, using Prop2Mesh's texture mapping |
| **Solid**, Color: **Texture** | The same texture × colour, without lighting effects. Fast |
| **Solid**, Color: **Material** | Only flat colours: each controller's colour, and each game model's average texture colour |

Solid view only draws textures when its colour is set to **Texture**. Blender's default is **Material**, so the add-on switches a viewport to **Texture** the first time you add an entity or model part, or attach parts. If you've chosen a colour mode yourself, it is left alone. The **P2M** sidebar tab also has a **Solid Color** setting, to switch back and forth.

Change these in the **Viewport Shading** popover at the top right of the 3D view (the small ⌄ next to the shading buttons).

Parts get a modifier named **P2M UV Preview**. It recreates Prop2Mesh's texture mapping so the preview matches the game. You don't need to touch it; it is added and removed automatically.

---

## 10. Units, orientation and the paste point

- **Units:** by default, 1 Blender unit = 1 Source unit. Change this with **Units / BU** in the **P2M** sidebar tab, or in the export options. Blender may label the units "m"; that doesn't affect anything.
- **Orientation:** Blender and Source both have Z up. An entity's **forward is +X**, which in Blender's default front view points to the right.
- **Paste point:** **Blender's world origin (0, 0, 0) is where AdvDupe2 pastes**, on the surface you aim at. Build on or above the origin so nothing ends up underground.

---

## 11. Exporting and pasting in Garry's Mod

**File > Export > AdvDupe2 Prop2Mesh (.txt)**, or **Export AdvDupe2** in the sidebar.

| Option | Default | What it does |
|---|---|---|
| **Selected Entities Only** | Off | Exports only selected entities. Selecting a part counts as selecting its entity. Off exports every entity in the scene |
| **Include Hidden Parts** | Off | Also exports parts hidden in the viewport |
| **Export Controller Names** | On | Writes controller names into the dupe |
| **Units per BU** | 1.00 | Same as the sidebar setting |

After exporting, Blender's status bar reports the number of entities, controllers and parts, the file size, and any warnings, such as parts with no controller or scaled entities.

**In game:**

1. Equip the **Advanced Duplicator 2** tool.
2. In its file browser, open your file. Files exported to `garrysmod/data/advdupe2` show up there, so you may need to refresh the browser.
3. Paste.

The server's own limits still apply, for example how many Prop2Mesh entities you may spawn.

### Starfall mesh tree (client-side meshes)

**File > Export > Starfall Mesh Tree (folders + manifest)** exports the same scene as client-side [StarfallEx](https://github.com/thegrb93/StarfallEx) meshes instead of Prop2Mesh entities. A small generic Starfall chip downloads the meshes from a GitHub repository and builds them as parented holograms, so nothing has to run on the server.

**One-time setup** (Edit > Preferences > Add-ons > AutoProp2Mesh):

- **Mesh Repository Folder:** a local clone of the GitHub repository the meshes will live in, for example a GitHub Desktop folder.
- The GitHub user, repository and branch are read from the clone's `.git` folder. Fill them in only to override.

**Export:** enter a **Project Name** (the folder created inside the repository). The export writes `<repo>/<project>/`:

```
manifest.json     hierarchy, per-pivot transforms, colors and materials
loader.lua        the Starfall chip, already pointed at your repository
<pivot>/mesh_1.obj, mesh_2.obj ...
```

Commit and push the repository, then paste `loader.lua` into a Starfall chip and spawn it. The chip downloads `manifest.json` and the OBJ files and builds the model around itself.

**How the scene becomes a tree:**

- The Blender parent hierarchy is the tree. A node is a **pivot** when it has children or has no mesh of its own. Pivots keep their own hologram, so they can be animated, and their transform is stored relative to their parent.
- A mesh with no children is a rigid attachment of its parent pivot. Its vertices are baked into the pivot's frame and merged with the pivot's other meshes of the same controller color, material and UV scale. Everything inside one pivot rides on one hologram, so the hologram count stays low.
- Colors, materials and UV scale come from each part's controller, exactly as for the dupe export. Model parts are skipped (they have no mesh data to export).

| Option | Default | What it does |
|---|---|---|
| **Project Name** | the .blend name | Folder created inside the repository. Exporting the same name again replaces that folder |
| **Model Faces** | +X | The direction the model faces in Blender. The whole model is turned so it faces +X in game. A model built facing Blender's front view (-Y) needs the `-Y` setting |
| **Selected Hierarchies Only** | Off | Exports only hierarchies that contain a selected object |
| **Include Hidden Parts** | Off | Also exports hidden parts |
| **Invert Normals** | Off | Flips winding and normals (inside-out meshes) |
| **No Cull** | Off | Draws both sides of every face (one extra hologram per mesh) |

**In game.** The settings at the top of `loader.lua`:

- `REPO_URL` and `PROJECT` pick what to load. Change `PROJECT` to load another project from the same repository.
- `YAW_OFFSET` adds an extra turn about up, on top of the exported **Model Faces** turn.
- `DEBUG = true` shows every pivot as a small magenta cube with a red nub pointing along its forward axis, and lists the pivots in chat.
- Each pivot is available as `P2M.nodes["hull/torso"]` for animation, for example `:setLocalAngles(...)`.

Starfall limits a player to 200 holograms by default (`sf_holograms_max`), and the export reports how many the model needs. GitHub's raw URLs can serve a stale file for a few minutes after a push.


---

## 12. Limits and things Prop2Mesh ignores

These come from Prop2Mesh itself:

- **UV unwraps are ignored.** Prop2Mesh box-projects textures from each part's position, so your UV maps don't carry over to the game. The viewport preview already shows the real result, and **UV Scale** controls the texture size. Model parts with UV Scale 0 are the exception (see [§7](#7-model-parts-prop_physics-style-parts)).
- **Custom normals are ignored.** Shading is either flat or smoothed by angle (see [§6](#6-parts-your-meshes)).
- **Each part holds at most 21,333 triangles.** Larger objects are split into several parts automatically when exporting.
- **The dupe size limit is 32 MB.** You get a warning if a dupe is larger than that. Use model parts and fewer triangles to keep dupes small.
- **Part names are only shown in Prop2Mesh's editor.** Characters other than plain English letters and symbols are replaced with `_`.

---

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| Sidebar says **Garry's Mod install not found** | Set **Garry's Mod Folder** in the add-on preferences, then click **Rescan Content** |
| Sidebar says **indexing…** for a long time | The first scan of many workshop addons can take a little while. Later scans are fast |
| A model shows `error.mdl` or a yellow **!** | The model wasn't found in your content. Check the path, add its addon folder under **Extra Content Folders**, and **Rescan Content** |
| A material shows a pink and black checkerboard | The material or its texture wasn't found. As above: check the path and your content folders |
| A model inside an old workshop item takes a few seconds to appear | Old `.bin` workshop items are compressed and are unpacked in memory the first time. It's quick after that |
| Ctrl+P doesn't show the Prop2Mesh entries | Make sure the **entity is the active (last selected)** object. If another add-on also changes Ctrl+P, use **Object > Parent** instead |
| A part isn't exported | Check the **Part** panel. It needs a controller, and its entity must be included in the export |
| Solid view shows grey or flat colours instead of textures | Set **Solid Color** to **Texture** in the **P2M** sidebar tab (or in Blender's Viewport Shading popover) |
| Solid view is black after enabling the add-on | Switch the viewport shading once, or reopen the file. The preview textures are rebuilt automatically |
| I added new addons in Garry's Mod | Click **Rescan Content** (⟳ next to Export in the sidebar) |
