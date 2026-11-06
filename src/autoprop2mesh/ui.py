import bpy

from . import content, entities, modelparts, props, sync
from .export import P2M_OT_export_advdupe2, P2M_OT_export_starfall_tree


class P2M_UL_controllers(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        sub = row.row()
        sub.ui_units_x = 1.5
        sub.prop(item, "color", text="")
        row.label(text="#%d  %s" % (index, item.name) if item.name else "#%d" % index)
        row.label(text=item.material, icon="MATERIAL")


class P2M_PT_main(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "P2M"
    bl_label = "Prop2Mesh"

    def draw(self, context):
        layout = self.layout
        ready = content.is_ready()
        layout.label(text=content.status_text(), icon="CHECKMARK" if ready else "TIME")
        row = layout.row(align=True)
        row.operator("object.p2m_add_entity", icon="ADD", text="Add Entity")
        row.operator("object.p2m_add_model_part", icon="MESH_ICOSPHERE", text="Add Model Part")
        layout.prop(context.scene.p2m, "unit_scale", text="Units / BU")
        shading = getattr(context.space_data, "shading", None)
        if shading is not None and shading.type == "SOLID":
            row = layout.row(align=True)
            row.label(text="Solid Color:")
            row.prop(shading, "color_type", text="")
        row = layout.row(align=True)
        row.operator(P2M_OT_export_advdupe2.bl_idname, icon="EXPORT", text="Export AdvDupe2")
        row.operator(P2M_OT_export_starfall_tree.bl_idname, icon="EXPORT", text="Export Starfall Meshes")
        row.operator("p2m.rebuild_content", icon="FILE_REFRESH", text="")


class P2M_PT_entity(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "P2M"
    bl_label = "Entity"
    bl_parent_id = "P2M_PT_main"

    @classmethod
    def poll(cls, context):
        return entities.context_entity(context) is not None

    def draw(self, context):
        layout = self.layout
        ent = entities.context_entity(context)
        p = ent.p2m
        layout.label(text=ent.name, icon="OUTLINER_OB_MESH")

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(p, "model", text="")
        op = row.operator("p2m.model_browser", text="", icon="FILEBROWSER")
        op.entity = ent.name
        op = row.operator("p2m.search_model", text="", icon="VIEWZOOM")
        op.entity = ent.name
        op = row.operator("p2m.reload_model", text="", icon="FILE_REFRESH")
        op.entity = ent.name
        if p.model_status:
            col.label(text=p.model_status, icon="ERROR")

        layout.label(text="Controllers")
        row = layout.row()
        row.template_list("P2M_UL_controllers", "", p, "controllers", p, "active_controller", rows=4)
        side = row.column(align=True)
        side.operator("p2m.controller_add", icon="ADD", text="").entity = ent.name
        side.operator("p2m.controller_remove", icon="REMOVE", text="").entity = ent.name
        side.separator()
        op = side.operator("p2m.controller_move", icon="TRIA_UP", text="")
        op.entity, op.direction = ent.name, "UP"
        op = side.operator("p2m.controller_move", icon="TRIA_DOWN", text="")
        op.entity, op.direction = ent.name, "DOWN"

        if not 0 <= p.active_controller < len(p.controllers):
            return
        ctrl = p.controllers[p.active_controller]
        box = layout.box()
        col = box.column()
        col.prop(ctrl, "name")
        col.prop(ctrl, "color")
        row = col.row(align=True)
        row.prop(ctrl, "material")
        op = row.operator("p2m.material_browser", text="", icon="FILEBROWSER")
        op.entity, op.uid = ent.name, ctrl.uid
        op = row.operator("p2m.search_material", text="", icon="VIEWZOOM")
        op.entity, op.uid = ent.name, ctrl.uid
        row = col.row()
        row.prop(ctrl, "uvs")
        row.prop(ctrl, "bump")
        parts = [o for o, c in entities.entity_parts(ent) if c.uid == ctrl.uid]
        col.label(text="%d part object(s)" % len(parts), icon="MESH_DATA")
        row = col.row(align=True)
        op = row.operator("p2m.attach", text="Attach Selected", icon="LINKED")
        op.entity, op.uid = ent.name, ctrl.uid
        op = row.operator("p2m.select_parts", text="Select Parts", icon="RESTRICT_SELECT_OFF")
        op.entity, op.uid = ent.name, ctrl.uid


class P2M_MT_part_controller(bpy.types.Menu):
    bl_label = "Controller"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        ent = entities.owning_entity(obj) if obj else None
        if ent is None:
            return
        layout.operator("p2m.set_part_controller", text="Inherit from Parent").uid = -1
        for c in ent.p2m.controllers:
            layout.operator("p2m.set_part_controller", text="Controller %s" % props.controller_label(ent, c)).uid = c.uid


class P2M_PT_part(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "P2M"
    bl_label = "Part"
    bl_parent_id = "P2M_PT_main"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and not obj.p2m.is_entity and not obj.p2m.is_clip_plane             and (sync.is_geometry(obj) or obj.type == "EMPTY")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        if obj.p2m.is_model_part:
            self.draw_model_part(context, obj)
        ent, ctrl = sync.resolve(obj)
        if ent is None:
            layout.label(text="Not part of a Prop2Mesh entity", icon="INFO")
            layout.label(text="Select it, then the entity, and press Ctrl+P")
            return
        layout.label(text="Entity: %s" % ent.name, icon="OUTLINER_OB_MESH")
        if ctrl is not None:
            label = "Controller %s" % props.controller_label(ent, ctrl)
            if obj.p2m.controller_uid < 0:
                label += " (inherited)"
        else:
            label = "No controller (not exported)"
        layout.menu("P2M_MT_part_controller", text=label, icon="MATERIAL")
        if obj.p2m.is_model_part:
            col = layout.column()
            col.prop(obj.p2m, "model_flat")
            col.prop(obj.p2m, "render_inside")
        elif sync.is_geometry(obj):
            col = layout.column()
            col.prop(obj.p2m, "smooth_mode")
            if obj.p2m.smooth_mode == "SMOOTH":
                col.prop(obj.p2m, "smooth_angle")
            col.prop(obj.p2m, "render_inside")

    def draw_model_part(self, context, obj):
        layout = self.layout
        p = obj.p2m
        col = layout.column(align=True)
        col.label(text="Model Part", icon="MESH_CUBE")
        row = col.row(align=True)
        row.prop(p, "model", text="")
        row.operator("p2m.model_browser", text="", icon="FILEBROWSER").entity = obj.name
        row.operator("p2m.search_model", text="", icon="VIEWZOOM").entity = obj.name
        row.operator("p2m.reload_model", text="", icon="FILE_REFRESH").entity = obj.name
        if p.model_status:
            col.label(text=p.model_status, icon="ERROR")
        groups = [bg for bg in p.bodygroups if "\n" in bg.options]
        if groups:
            box = layout.box()
            box.label(text="Body Groups")
            for bg in groups:
                box.prop(bg, "choice", text=bg.name or "Group")
        row = layout.row(align=True)
        planes = modelparts.clip_plane_objects(obj)
        row.operator("p2m.add_clip_plane", icon="MOD_BOOLEAN")
        row.label(text="%d clip plane(s)" % len(planes))
        layout.separator()


class P2M_PT_clip_plane(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "P2M"
    bl_label = "Clip Plane"
    bl_parent_id = "P2M_PT_main"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.p2m.is_clip_plane

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        part = obj.parent
        layout.label(text="Cuts: %s" % (part.name if part else "(no model part)"), icon="MOD_BOOLEAN")
        layout.label(text="Keeps the side the arrow points to")
        row = layout.row(align=True)
        row.operator("p2m.flip_clip_plane", icon="ARROW_LEFTRIGHT")
        row.operator("p2m.add_clip_plane", text="Add Another", icon="ADD")


class P2M_MT_parent_set(bpy.types.Menu):
    """Replacement for the Ctrl+P "Set Parent To" popup (which is built in C
    and cannot be extended) with Prop2Mesh entries added."""
    bl_label = "Set Parent To"
    bl_idname = "P2M_MT_parent_set"

    def draw(self, context):
        layout = self.layout
        active = context.active_object
        if active is not None and active.p2m.is_entity:
            for c in active.p2m.controllers:
                op = layout.operator("p2m.attach", text="Attach mesh to Controller %s..." % props.controller_label(active, c),
                                     icon="LINKED")
                op.entity, op.uid = active.name, c.uid
            if not len(active.p2m.controllers):
                layout.label(text="Entity has no controllers", icon="INFO")
            layout.separator()

        layout.operator_context = "EXEC_DEFAULT"
        op = layout.operator("object.parent_set", text="Object")
        op.type = "OBJECT"
        op = layout.operator("object.parent_set", text="Object (Keep Transform)")
        op.type, op.keep_transform = "OBJECT", True
        layout.operator("object.parent_no_inverse_set", text="Object (Without Inverse)")
        op = layout.operator("object.parent_no_inverse_set", text="Object (Keep Transform Without Inverse)")
        op.keep_transform = True

        extra = {
            "ARMATURE": (("ARMATURE", "Armature Deform"), ("ARMATURE_NAME", "   With Empty Groups"),
                         ("ARMATURE_AUTO", "   With Automatic Weights"), ("ARMATURE_ENVELOPE", "   With Envelope Weights"),
                         ("BONE", "Bone"), ("BONE_RELATIVE", "Bone Relative")),
            "CURVE": (("CURVE", "Curve Deform"), ("FOLLOW", "Follow Path"), ("PATH_CONST", "Path Constraint")),
            "LATTICE": (("LATTICE", "Lattice Deform"),),
        }.get(active.type if active else None, ())
        for t, label in extra:
            op = layout.operator("object.parent_set", text=label)
            op.type = t


def menu_object_parent(self, context):
    active = context.active_object
    if active is None or not active.p2m.is_entity:
        return
    layout = self.layout
    layout.separator()
    for c in active.p2m.controllers:
        op = layout.operator("p2m.attach", text="Attach mesh to Controller %s..." % props.controller_label(active, c),
                             icon="LINKED")
        op.entity, op.uid = active.name, c.uid


def menu_add(self, context):
    self.layout.operator("object.p2m_add_entity", text="Prop2Mesh Entity", icon="MESH_CUBE")
    self.layout.operator("object.p2m_add_model_part", text="Prop2Mesh Model Part", icon="MESH_ICOSPHERE")


# Sub-panels show in registration order: the active object's own panel
# (part / clip plane) comes before its entity's.
classes = (P2M_UL_controllers, P2M_PT_main, P2M_MT_part_controller, P2M_PT_part, P2M_PT_clip_plane,
           P2M_PT_entity, P2M_MT_parent_set)

_keymaps = []


def register():
    from .export import menu_func_export
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.VIEW3D_MT_add.append(menu_add)
    bpy.types.VIEW3D_MT_object_parent.append(menu_object_parent)
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="Object Mode", space_type="EMPTY")
        kmi = km.keymap_items.new("wm.call_menu", "P", "PRESS", ctrl=True)
        kmi.properties.name = P2M_MT_parent_set.bl_idname
        _keymaps.append((km, kmi))


def unregister():
    from .export import menu_func_export
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    bpy.types.VIEW3D_MT_object_parent.remove(menu_object_parent)
    bpy.types.VIEW3D_MT_add.remove(menu_add)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
