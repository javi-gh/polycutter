"""Kernel geométrico de PolyCutter: snapping, membrana, sólido y booleanas."""

import bpy
import bmesh
from mathutils import Vector

try:
    from mathutils.geometry import tessellate_polygon
except ImportError:  # pragma: no cover - respaldo para builds sin la función
    tessellate_polygon = None


class CutError(Exception):
    """Error controlado del proceso de corte."""


def mm_to_units(scene, value):
    """Convierte milímetros del usuario a unidades de escena."""
    scale = scene.unit_settings.scale_length or 1.0
    return value * 0.001 / scale


def diag_of(obj):
    """Diagonal del bounding box del objeto en coordenadas de mundo."""
    cs = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    return max((mx - mn).length, 1e-6)


def solvers():
    """Boolean solvers disponibles, de mejor a peor."""
    prop = bpy.types.BooleanModifier.bl_rna.properties.get("solver")
    available = {i.identifier for i in prop.enum_items} if prop else {"EXACT"}
    return [s for s in ("MANIFOLD", "EXACT") if s in available] or ["EXACT"]


def snap_to_surface(obj, dg, region, rv3d, coord, snap=True):
    """Proyecta una coordenada de pantalla sobre la malla evaluada.

    Devuelve (posición_mundo, normal_mundo, tipo) donde tipo es
    'SURFACE', 'VERT', 'EDGE' o 'NONE'.
    """
    from bpy_extras import view3d_utils

    ev = obj.evaluated_get(dg)
    mw = ev.matrix_world
    inv = mw.inverted_safe()
    me = ev.data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    ok, loc, nor, fi = ev.ray_cast(inv @ o, (inv.to_3x3() @ d).normalized(), distance=1e6)
    if not ok:
        return None, None, 'NONE'
    lw = mw @ loc
    nw = (mw.to_3x3().inverted_safe().transposed() @ nor).normalized()
    best, bd, kind = lw, 18.0, 'SURFACE'
    if snap and fi is not None and fi < len(me.polygons):
        poly = me.polygons[fi]
        c2 = Vector(coord)
        for vi in poly.vertices:
            vw = mw @ me.vertices[vi].co
            s = view3d_utils.location_3d_to_region_2d(region, rv3d, vw)
            if s and (c2 - s).length < bd:
                bd, best, kind = (c2 - s).length, vw, 'VERT'
        if kind != 'VERT':
            for va, vb in poly.edge_keys:
                a = mw @ me.vertices[va].co
                b = mw @ me.vertices[vb].co
                ab = b - a
                l2 = ab.length_squared
                if l2 < 1e-12:
                    continue
                t = max(0.0, min(1.0, (lw - a).dot(ab) / l2))
                pw = a + ab * t
                s = view3d_utils.location_3d_to_region_2d(region, rv3d, pw)
                if s and (c2 - s).length < bd:
                    bd, best, kind = (c2 - s).length, pw, 'EDGE'
    return best, nw, kind


def _triangulate_face(pts):
    """Respaldo de tessellate_polygon usando bmesh."""
    bm = bmesh.new()
    try:
        vs = [bm.verts.new(p) for p in pts]
        try:
            face = bm.faces.new(vs)
        except ValueError:
            return []
        bmesh.ops.triangulate(bm, faces=[face])
        bm.verts.index_update()
        return [tuple(v.index for v in f.verts) for f in bm.faces]
    finally:
        bm.free()


def membrane(pts, nrm, thick, rim):
    """Construye la membrana que corta la malla a partir del lazo.

    Tessela el lazo, lo subdivide y suaviza, y le añade una "cama"
    exterior orientada por las normales para que el sólido atraviese
    la superficie del modelo.
    """
    n = len(pts)
    tris = tessellate_polygon([pts]) if tessellate_polygon else _triangulate_face(pts)
    if not tris:
        raise CutError("El lazo se cruza a sí mismo; rehazlo sin cruces.")
    idx = {id(p): i for i, p in enumerate(pts)}

    def vid(v):
        if isinstance(v, int):
            return v
        i = idx.get(id(v))
        return i if i is not None else min(range(n), key=lambda k: (pts[k] - v).length_squared)

    faces, seen = [], set()
    for t in tris:
        f = tuple(vid(v) for v in t)
        if len(set(f)) != 3:
            continue
        key = tuple(sorted(f))
        if key in seen:
            continue
        seen.add(key)
        faces.append(f)
    if not faces:
        raise CutError("No se pudo rellenar el lazo.")

    me = bpy.data.meshes.new("pc_membrane")
    bm = bmesh.new()
    try:
        me.from_pydata([tuple(p) for p in pts], [], faces)
        me.update()
        bm.from_mesh(me)
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=3, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
        for _ in range(20):
            inner = [v for v in bm.verts if not v.is_boundary]
            if not inner:
                break
            bmesh.ops.smooth_vert(bm, verts=inner, factor=0.5,
                                  use_axis_x=True, use_axis_y=True, use_axis_z=True)
        center = sum(pts, Vector()) / n
        nn = Vector()
        for a, b in zip(pts, pts[1:] + pts[:1]):
            nn += a.cross(b)
        if nn.length < 1e-9:
            nn = Vector((0, 0, 1))
        nn.normalize()
        local_diag = max((p - center).length for p in pts) * 2 or 1.0
        over = max(thick * 1.5, local_diag * rim)
        ns = [v.normalized() if v.length > 1e-9 else nn.copy() for v in nrm]
        for _ in range(3):
            ns = [(ns[i - 1] * 0.25 + ns[i] * 0.5 + ns[(i + 1) % n] * 0.25).normalized()
                  for i in range(n)]
        outer = []
        for p, no in zip(pts, ns):
            rad = p - center
            rad -= nn * rad.dot(nn)
            tn = no - nn * no.dot(nn)
            if rad.length > 1e-9:
                rad.normalize()
            if tn.length > 1e-9:
                tn.normalize()
                if rad.length > 1e-9 and tn.dot(rad) < 0:
                    tn.negate()
            out = rad + tn * 0.5
            if out.length < 1e-9:
                out = no.copy()
            out.normalize()
            outer.append(p + out * over)
        bedges = [e for e in bm.edges if e.is_boundary]
        adj = {}
        for e in bedges:
            a, b = e.verts
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        if not adj or any(len(v) != 2 for v in adj.values()):
            raise CutError("El borde de la membrana no es continuo.")
        start = min(adj, key=lambda v: (v.co - pts[0]).length_squared)
        ring, prev, cur = [], None, start
        for _ in range(len(adj) + 1):
            ring.append(cur)
            nxt = [v for v in adj[cur] if v is not prev]
            if not nxt:
                break
            f = nxt[0]
            if f is start:
                break
            prev, cur = cur, f
        if len(ring) != len(adj):
            raise CutError("La membrana tiene varios bordes.")

        def map_ring(co):
            best, bp = 1e30, outer[0]
            for i in range(n):
                a, b = pts[i], pts[(i + 1) % n]
                ab = b - a
                l2 = ab.length_squared
                t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, (co - a).dot(ab) / l2))
                d = (co - a.lerp(b, t)).length_squared
                if d < best:
                    best, bp = d, outer[i].lerp(outer[(i + 1) % n], t)
            return bp

        ov = [bm.verts.new(map_ring(v.co)) for v in ring]
        for i, v in enumerate(ring):
            j = (i + 1) % len(ring)
            try:
                bm.faces.new((v, ring[j], ov[j], ov[i]))
            except ValueError:
                pass
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(me)
        me.update()
        return me
    except Exception:
        bpy.data.meshes.remove(me)
        raise
    finally:
        bm.free()


def solidify(me, thick, coll):
    """Convierte la membrana en un sólido cerrado aplicando SOLIDIFY."""
    ob = bpy.data.objects.new("pc_sol", me)
    coll.objects.link(ob)
    mod = ob.modifiers.new("sol", 'SOLIDIFY')
    mod.thickness, mod.offset, mod.use_even_offset, mod.use_rim = thick, 0.0, True, True
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    res = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(ob, do_unlink=True)
    return res


def boolean_diff(src, cut, dg):
    """Resta `cut` a `src` probando los solvers disponibles."""
    for sol in solvers():
        mod = src.modifiers.new("b", 'BOOLEAN')
        mod.operation, mod.solver, mod.object = 'DIFFERENCE', sol, cut
        if hasattr(mod, "use_hole_tolerant"):
            mod.use_hole_tolerant = True
        dg.update()
        res = bpy.data.meshes.new_from_object(src.evaluated_get(dg), depsgraph=dg)
        src.modifiers.remove(mod)
        if res and res.polygons:
            return res
        if res:
            bpy.data.meshes.remove(res)
    return None


def split_two(me):
    """Separa la malla en las dos piezas conexas principales (A y B)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.faces.index_update()
    remaining = set(bm.faces)
    recs = []
    while remaining:
        seed = remaining.pop()
        comp, stack = {seed}, [seed]
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in remaining:
                        remaining.remove(g)
                        comp.add(g)
                        stack.append(g)
        area = sum(max(f.calc_area(), 1e-14) for f in comp)
        cen = sum((f.calc_center_median() * max(f.calc_area(), 1e-14) for f in comp),
                  Vector()) / area
        vs = {v for f in comp for v in f.verts}
        mn = next(iter(vs)).co.copy()
        mx = mn.copy()
        for v in vs:
            for a in range(3):
                mn[a] = min(mn[a], v.co[a])
                mx[a] = max(mx[a], v.co[a])
        recs.append({"faces": comp, "area": area, "center": cen, "diag": (mx - mn).length})
    recs.sort(key=lambda r: r["area"], reverse=True)
    if len(recs) < 2:
        bm.free()
        raise CutError("El lazo no separó la pieza: debe rodear COMPLETAMENTE la extremidad.")
    la = recs[0]["area"]
    ld = max(r["diag"] for r in recs)
    subs = [r for r in recs if r["area"] / la >= 1e-5 or r["diag"] / ld >= 0.01]
    if len(subs) < 2:
        bm.free()
        raise CutError("Solo se obtuvo una pieza útil; el lazo no atraviesa toda la extremidad.")
    a, b = subs[0], subs[1]
    ga, gb = set(a["faces"]), set(b["faces"])
    for r in recs[2:]:
        t = ga if (r["center"] - a["center"]).length_squared <= \
            (r["center"] - b["center"]).length_squared else gb
        t.update(r["faces"])
    outs = []
    for g, name in ((ga, "A"), (gb, "B")):
        w = bm.copy()
        try:
            keep = {f.index for f in g}
            rm = [f for f in w.faces if f.index not in keep]
            if rm:
                bmesh.ops.delete(w, geom=rm, context='FACES')
            loose = [v for v in w.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(w, geom=loose, context='VERTS')
            bmesh.ops.recalc_face_normals(w, faces=list(w.faces))
            m = bpy.data.meshes.new(name)
            w.to_mesh(m)
            m.update()
            outs.append(m)
        finally:
            w.free()
    bm.free()
    return outs
