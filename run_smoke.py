"""Smoke test de PolyCutter ejecutado dentro de Blender.

Uso:
    blender --background --factory-startup --python-exit-code 1 --python run_smoke.py
"""

import pathlib
import sys
import traceback

import bpy
from mathutils import Vector


def check(cond, label, results):
    results.append((label, bool(cond)))
    if not cond:
        raise AssertionError(label)


def main():
    root = pathlib.Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    results = []
    import PolyCutter
    from PolyCutter import config, geometry, session

    PolyCutter.register()
    try:
        check(hasattr(bpy.types, "MESH_OT_polycutter_limbs"),
              "operador modal registrado", results)
        check(hasattr(bpy.types, "MESH_OT_polycutter_cmd"),
              "operador puente registrado", results)
        check(hasattr(bpy.types, "VIEW3D_PT_polycutter_limbs"),
              "panel registrado", results)
        check(hasattr(bpy.types.Scene, "pc_limbs_gap"),
              "propiedades de escena", results)

        import mathutils.geometry as mgeo
        check(hasattr(mgeo, "tessellate_polygon"),
              "tessellate_polygon disponible", results)
        check(len(geometry.solvers()) >= 1, "solver booleano disponible", results)

        scene = bpy.context.scene
        check(abs(geometry.mm_to_units(scene, 1.0) - 0.001) < 1e-9,
              "conversion mm", results)

        import math
        pts = [Vector((math.cos(a), math.sin(a), 0.0))
               for a in [i * math.pi / 4 for i in range(8)]]
        nrm = [Vector((0.0, 0.0, 1.0)) for _ in pts]
        me = geometry.membrane(pts, nrm, 0.001, 0.03)
        check(len(me.polygons) > 0, "membrana genera caras", results)
        bpy.data.meshes.remove(me)

        s = session.SESSION
        check(not s.active and not s.alive(), "sesion inactiva al inicio", results)
        check(len(session.command_items(s)) == 7, "tabla de comandos completa", results)
        check(config.VERSION == tuple(PolyCutter.bl_info["version"]),
              "version coherente", results)
    finally:
        PolyCutter.unregister()

    check(not hasattr(bpy.types, "MESH_OT_polycutter_limbs"),
          "desregistro limpio", results)
    print("SMOKE OK: %d comprobaciones" % len(results))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
