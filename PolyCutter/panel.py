"""Panel N de PolyCutter (renderiza desde SESSION/COMMANDS, sin lógica propia)."""

import bpy

from . import config, session


class VIEW3D_PT_polycutter_limbs(bpy.types.Panel):
    bl_label = "PolyCutter Limbs"
    bl_idname = "VIEW3D_PT_polycutter_limbs"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "PolyCutter"

    @classmethod
    def poll(cls, c):
        return c.active_object and c.active_object.type == 'MESH'

    @staticmethod
    def _btn(layout, item):
        row = layout.row(align=True)
        row.enabled = item["enabled"]
        op = row.operator("mesh.polycutter_cmd", text=item["text"],
                          icon=item["icon"], depress=item["active"])
        op.cmd = item["cmd"]

    def draw(self, c):
        s = session.SESSION
        # Sesión huérfana (operador muerto sin cleanup): auto-reset.
        if s.active and not s.alive():
            s.reset()
        col = self.layout.column(align=True)
        col.label(text="Activo: %s" % c.active_object.name, icon='MESH_DATA')
        col.prop(c.scene, "pc_limbs_gap")
        col.prop(c.scene, "pc_limbs_hide")
        col.prop(c.scene, "pc_limbs_transp")
        col.separator()
        if not s.active:
            col.operator("mesh.polycutter_limbs", text="Separar extremidad",
                         icon='MOD_BOOLEAN')
            box = col.box()
            for line in config.PANEL_STEPS:
                box.label(text=line)
            return
        items = {it["cmd"]: it for it in session.command_items(s)}
        col.label(text=session.status_text(s), icon='CURVE_PATH')
        row = col.row(align=True)
        self._btn(row, items["DRAW"])
        self._btn(row, items["MOVE"])
        self._btn(col, items["CLOSE"])
        row = col.row(align=True)
        self._btn(row, items["UNDO"])
        self._btn(row, items["CLEAR"])
        col.separator()
        big = col.column(align=True)
        big.scale_y = 1.6
        self._btn(big, items["APPLY"])
        if not items["APPLY"]["enabled"]:
            col.label(text="Cierra el lazo (mín. %d puntos)" % config.MIN_APPLY,
                      icon='INFO')
        self._btn(col, items["CANCEL"])
