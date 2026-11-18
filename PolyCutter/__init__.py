"""PolyCutter 1.0 — lazo editable sobre mallas para separar extremidades.

Licencia: GPL-3.0-or-later (ver LICENSE).

1.0.0 — primera versión pública:
- Lazo editable con puntos individuales (arrastrar, insertar, borrar).
- Cerrar el lazo sin cortar; aplicar el corte con botón.
- HUD y panel sincronizados desde una única tabla de comandos.
- Corte booleano robusto (MANIFOLD/EXACT) con separación en 2 piezas cerradas.
"""

bl_info = {
    "name": "PolyCutter Limbs (separar piezas)",
    "author": "PolyCutter",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "Vista 3D > N > PolyCutter",
    "description": "Rodea una extremidad con un lazo editable (puntos individuales) y sepárala con un botón",
    "category": "Mesh",
}

import bpy
from bpy.props import BoolProperty, FloatProperty

from . import config, geometry, hud, operators, panel, session

CLASSES = (
    operators.MESH_OT_polycutter_limbs,
    operators.MESH_OT_polycutter_cmd,
    panel.VIEW3D_PT_polycutter_limbs,
)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    session.SESSION.reset()
    bpy.types.Scene.pc_limbs_gap = FloatProperty(
        name="Grosor de corte (mm)", default=0.3, min=0.0)
    bpy.types.Scene.pc_limbs_hide = BoolProperty(name="Ocultar original", default=True)
    bpy.types.Scene.pc_limbs_transp = FloatProperty(
        name="Transparencia", default=0.3, min=0, max=1, subtype='FACTOR')


def unregister():
    for name in ("pc_limbs_gap", "pc_limbs_hide", "pc_limbs_transp"):
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as exc:
            config.log("unregister %s: %s" % (cls.__name__, exc))


if __name__ == "__main__":
    register()
