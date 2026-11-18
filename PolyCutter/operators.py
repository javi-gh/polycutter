"""Operadores de PolyCutter: sesión modal del lazo y puente de comandos."""

import bpy
from bpy.props import StringProperty
from mathutils import Vector

from . import config, geometry, hud, session
from .geometry import CutError


def _over_ui(area, event):
    """True si el cursor está sobre una región de UI del área 3D."""
    for r in area.regions:
        if r.type == 'WINDOW':
            continue
        if (r.width > 1 and r.height > 1
                and r.x <= event.mouse_x < r.x + r.width
                and r.y <= event.mouse_y < r.y + r.height):
            return True
    return False


class MESH_OT_polycutter_limbs(bpy.types.Operator):
    """Dibuja un lazo sobre la malla, permite editarlo y separa la pieza."""

    bl_idname = "mesh.polycutter_limbs"
    bl_label = "Separar extremidad"
    bl_description = ("Dibuja un lazo alrededor de la pieza, edítalo (mover puntos) "
                      "y aplica el corte con el botón")
    bl_options = {'REGISTER', 'UNDO'}

    NAV = frozenset({
        'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM',
        'HOME', 'NUMPAD_PERIOD', 'NUMPAD_0', 'NUMPAD_1', 'NUMPAD_2', 'NUMPAD_3',
        'NUMPAD_4', 'NUMPAD_5', 'NUMPAD_6', 'NUMPAD_7', 'NUMPAD_8', 'NUMPAD_9'})

    # ------------------------------------------------------------- ciclo de vida
    def invoke(self, context, event):
        s = session.SESSION
        if s.active and s.alive():
            self.report({'WARNING'}, "PolyCutter ya está activo")
            return {'CANCELLED'}
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not context.area or context.area.type != 'VIEW_3D':
            self.report({'ERROR'}, "Selecciona una malla en Vista 3D")
            return {'CANCELLED'}
        if obj.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        s.reset()
        s.active = True
        s.obj = obj
        s.area = context.area
        s.space = context.area.spaces.active
        s.region = next((r for r in context.area.regions if r.type == 'WINDOW'), context.region)
        s.rv3d = s.space.region_3d
        s.prev_x = (s.space.shading.show_xray, s.space.shading.xray_alpha)
        s.space.shading.show_xray = True
        s.space.shading.xray_alpha = context.scene.pc_limbs_transp
        s.h2 = bpy.types.SpaceView3D.draw_handler_add(hud.draw_hud, (), 'WINDOW', 'POST_PIXEL')
        s.h3 = bpy.types.SpaceView3D.draw_handler_add(hud.draw_scene, (), 'WINDOW', 'POST_VIEW')
        s.timer = context.window_manager.event_timer_add(0.05, window=context.window)
        s.touch()
        hud.reset_caches()
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _cleanup(self):
        s = session.SESSION
        for attr in ("h2", "h3"):
            h = getattr(s, attr, None)
            if h:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
                except ValueError:
                    pass
                setattr(s, attr, None)
        if s.timer:
            try:
                bpy.context.window_manager.event_timer_remove(s.timer)
            except Exception as exc:
                config.log("timer: %s" % exc)
            s.timer = None
        if s.space is not None and s.prev_x is not None:
            try:
                s.space.shading.show_xray, s.space.shading.xray_alpha = s.prev_x
            except (ReferenceError, RuntimeError):
                pass
        area = s.area
        s.reset()
        hud.reset_caches()
        if area is not None:
            try:
                area.tag_redraw()
            except ReferenceError:
                pass

    def cancel(self, context):
        self._cleanup()

    def _sync(self):
        s = session.SESSION
        s.touch()
        try:
            s.area.tag_redraw()
        except (ReferenceError, AttributeError):
            pass

    # ------------------------------------------------------------------ picking
    def _screen(self, s, idx):
        scr = hud.projection(s)
        return scr[idx] if 0 <= idx < len(scr) else None

    def _near(self, s, coord):
        if s.closed or len(s.pts) < config.MIN_PTS:
            return False
        p = self._screen(s, 0)
        return p is not None and (Vector(coord) - p).length <= config.CLOSE_PX

    def _hover_index(self, s, coord, radius=None):
        radius = config.PICK_PX if radius is None else radius
        scr = hud.projection(s)
        best, bi, c = radius, None, Vector(coord)
        for i, p in enumerate(scr):
            if p is not None:
                d = (c - p).length
                if d < best:
                    best, bi = d, i
        return bi

    def _nearest_segment(self, s, coord, radius=None):
        radius = config.SEG_PX if radius is None else radius
        n = len(s.pts)
        if n < 2:
            return None
        scr = hud.projection(s)
        best, bi, c = radius, None, Vector(coord)
        count = n if s.closed else n - 1
        for i in range(count):
            a, b = scr[i], scr[(i + 1) % n]
            if a is None or b is None:
                continue
            ab = b - a
            l2 = ab.length_squared
            t = 0.0 if l2 < 1e-9 else max(0.0, min(1.0, (c - a).dot(ab) / l2))
            d = (c - (a + ab * t)).length
            if d < best:
                best, bi = d, i
        return bi

    # -------------------------------------------------------------- mutaciones
    @staticmethod
    def _fix_strokes(s):
        s.strokes = sorted({k for k in s.strokes if 0 <= k < len(s.pts)})

    def _insert(self, s, idx, p, n):
        s.pts.insert(idx, p)
        s.nrm.insert(idx, n)
        s.strokes = [k + 1 if k >= idx else k for k in s.strokes]
        s.changed()

    def _delete(self, s, idx):
        s.pts.pop(idx)
        s.nrm.pop(idx)
        s.strokes = [k - 1 if k > idx else k for k in s.strokes]
        self._fix_strokes(s)
        if len(s.pts) < config.MIN_PTS:
            s.closed = False
        s.hover = None
        s.changed()

    def _undo(self, s):
        s.drawing = False
        if s.strokes:
            k = s.strokes.pop()
            s.pts, s.nrm = s.pts[:k], s.nrm[:k]
            s.changed()
        if len(s.pts) < config.MIN_PTS:
            s.closed = False
        s.hover = None

    def _start_drag(self, s, idx, coord):
        """Inicia el arrastre exclusivamente del punto `idx` (sin tocar vecinos)."""
        p = self._screen(s, idx)
        s.drag = {"idx": idx, "start": Vector(coord),
                  "s0": p.copy() if p else Vector(coord)}
        s.hover = idx

    def _drag_to(self, context, s, coord):
        d = s.drag
        i = d["idx"]
        if i >= len(s.pts):
            return
        delta = Vector(coord) - d["start"]
        p, n, _ = geometry.snap_to_surface(
            s.obj, context.evaluated_depsgraph_get(), s.region, s.rv3d,
            d["s0"] + delta, snap=True)
        if p:
            s.pts[i] = p
            s.nrm[i] = n
            s.changed()

    # ------------------------------------------------------------------- modal
    def modal(self, context, event):
        try:
            return self._modal(context, event)
        except Exception as exc:
            config.log("modal: %s" % exc)
            self._cleanup()
            self.report({'ERROR'}, "Error: %s" % exc)
            return {'CANCELLED'}

    def _modal(self, context, event):
        s = session.SESSION
        if not s.active:
            return {'CANCELLED'}
        if event.type == 'TIMER':
            s.touch()
            for cmd in s.take():
                res = self._command(context, cmd)
                if res != {'RUNNING_MODAL'}:
                    return res
            return {'PASS_THROUGH'}
        self._sync()
        if event.type in self.NAV:
            return {'PASS_THROUGH'}
        r = s.region
        coord = (event.mouse_x - r.x, event.mouse_y - r.y)
        s.last = coord
        press = event.value in {'PRESS', 'DOUBLE_CLICK'}
        inside = (0 <= coord[0] < r.width and 0 <= coord[1] < r.height
                  and not _over_ui(s.area, event))

        if event.type == 'ESC' and press:
            return self._command(context, 'CANCEL')

        if s.drag is not None:
            if event.type == 'MOUSEMOVE':
                self._drag_to(context, s, coord)
            elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                s.drag = None
            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            s.drawing = False
            return {'PASS_THROUGH'}

        if not inside:
            if event.type == 'MOUSEMOVE':
                s.hover = s.hud_hover = None
            return {'PASS_THROUGH'}

        if event.type == 'MOUSEMOVE':
            s.hud_hover = hud.hud_at(s, coord)
            if s.drawing:
                self._stroke_to(context, s, coord)
                return {'RUNNING_MODAL'}
            s.hover = self._hover_index(s, coord)
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and press:
            cmd = hud.hud_at(s, coord)
            if cmd:
                return self._command(context, cmd)
            return self._left_press(context, event, s, coord)

        if press:
            return self._key(context, event, s)
        return {'PASS_THROUGH'}

    def _stroke_to(self, context, s, coord):
        if s.pts:
            last = self._screen(s, len(s.pts) - 1)
            if last and (Vector(coord) - last).length < config.MIN_STROKE_PX:
                return
        p, n, _ = geometry.snap_to_surface(
            s.obj, context.evaluated_depsgraph_get(), s.region, s.rv3d, coord)
        if p:
            s.pts.append(p)
            s.nrm.append(n)
            s.changed()
            self._sync()

    def _left_press(self, context, event, s, coord):
        dg = context.evaluated_depsgraph_get()
        if event.shift:
            seg = self._nearest_segment(s, coord)
            if seg is not None:
                p, n, _ = geometry.snap_to_surface(
                    s.obj, dg, s.region, s.rv3d, coord, snap=False)
                if p:
                    self._insert(s, seg + 1, p, n)
                    self._start_drag(s, seg + 1, coord)
            self._sync()
            return {'RUNNING_MODAL'}
        if s.mode == 'MOVE' or event.ctrl:
            idx = self._hover_index(s, coord, config.PICK_PX * config.PICK_SCALE)
            if idx is not None:
                self._start_drag(s, idx, coord)
            return {'RUNNING_MODAL'}
        if not s.closed and self._near(s, coord):
            s.closed = True
            s.hover = 0
            self._sync()
            return {'RUNNING_MODAL'}
        idx = self._hover_index(s, coord, config.PICK_PX * config.PICK_SCALE)
        if idx is not None:
            self._start_drag(s, idx, coord)
            return {'RUNNING_MODAL'}
        if s.closed:
            self.report({'INFO'}, "El lazo está cerrado: muévelo o ábrelo (C) para seguir dibujando")
            return {'RUNNING_MODAL'}
        p, n, _ = geometry.snap_to_surface(s.obj, dg, s.region, s.rv3d, coord)
        if p:
            s.strokes.append(len(s.pts))
            s.pts.append(p)
            s.nrm.append(n)
            s.changed()
            s.drawing = True
            self._sync()
        return {'RUNNING_MODAL'}

    def _key(self, context, event, s):
        t = event.type
        if t in {'RET', 'NUMPAD_ENTER'}:
            return self._command(context, 'APPLY') if event.ctrl else {'RUNNING_MODAL'}
        if t == 'BACK_SPACE' or (t == 'Z' and event.ctrl):
            return self._command(context, 'UNDO')
        if not event.ctrl:
            if t in {'D', 'M', 'C'}:
                return self._command(context, {'D': 'DRAW', 'M': 'MOVE', 'C': 'CLOSE'}[t])
            if t in {'X', 'DEL'}:
                idx = self._hover_index(s, s.last, config.PICK_PX * config.PICK_SCALE)
                if idx is not None:
                    self._delete(s, idx)
                    self._sync()
                else:
                    self.report({'INFO'}, "Pon el cursor sobre un punto para borrarlo")
                return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}

    def _command(self, context, cmd):
        s = session.SESSION
        n = len(s.pts)
        if cmd == 'CANCEL':
            self._cleanup()
            return {'CANCELLED'}
        if cmd == 'APPLY':
            if not s.closed or n < config.MIN_APPLY:
                self.report({'WARNING'}, "Cierra el lazo (mínimo %d puntos) antes de aplicar el corte"
                            % config.MIN_APPLY)
                return {'RUNNING_MODAL'}
            obj, pts, nrm = s.obj, list(s.pts), list(s.nrm)
            self._cleanup()
            return self._cut(context, obj, pts, nrm)
        if cmd in {'DRAW', 'MOVE'}:
            s.mode, s.hover = cmd, None
        elif cmd == 'CLOSE':
            if s.closed:
                s.closed = False
            elif n >= config.MIN_PTS:
                s.closed = True
            else:
                self.report({'INFO'}, "Se necesitan al menos %d puntos para cerrar el lazo"
                            % config.MIN_PTS)
        elif cmd == 'UNDO':
            self._undo(s)
        elif cmd == 'CLEAR':
            s.pts, s.nrm, s.strokes, s.closed = [], [], [], False
            s.drawing = False
            s.hover = None
            s.changed()
        self._sync()
        return {'RUNNING_MODAL'}

    # -------------------------------------------------------------------- corte
    def _cut(self, context, obj, pts0, nrm0):
        """Pipeline completo: membrana -> solidify -> booleana -> 2 piezas."""
        sc = context.scene
        diag = geometry.diag_of(obj)
        pts, nrm = [], []
        for p, n in zip(pts0, nrm0):
            if not pts or (p - pts[-1]).length > diag * 1e-4:
                pts.append(p)
                nrm.append(n)
        if len(pts) >= 2 and (pts[0] - pts[-1]).length <= diag * 1e-4:
            pts.pop()
            nrm.pop()
        if len(pts) < config.MIN_APPLY:
            self.report({'ERROR'}, "Lazo insuficiente")
            return {'CANCELLED'}
        thick = max(geometry.mm_to_units(sc, sc.pc_limbs_gap), diag * 1e-7)
        dg = context.evaluated_depsgraph_get()
        base = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), depsgraph=dg)
        base.transform(obj.matrix_world)
        coll = context.collection
        src = bpy.data.objects.new("pc_src", base)
        coll.objects.link(src)
        context.window.cursor_set('WAIT')
        last = None
        try:
            for rim in config.RIM_STEPS:
                try:
                    mem = geometry.membrane(pts, nrm, thick, rim)
                except CutError as exc:
                    last = exc
                    continue
                cutme = geometry.solidify(mem, thick, coll)
                bpy.data.meshes.remove(mem)
                cut = bpy.data.objects.new("pc_cut", cutme)
                coll.objects.link(cut)
                res = geometry.boolean_diff(src, cut, dg)
                bpy.data.objects.remove(cut, do_unlink=True)
                bpy.data.meshes.remove(cutme)
                if res is None:
                    last = CutError("Boolean no produjo geometría")
                    continue
                try:
                    ma, mb = geometry.split_two(res)
                except CutError as exc:
                    last = exc
                    bpy.data.meshes.remove(res)
                    continue
                bpy.data.meshes.remove(res)
                made = []
                for me, sfx in ((ma, "_A"), (mb, "_B")):
                    me.name = obj.name + sfx
                    ob = bpy.data.objects.new(me.name, me)
                    coll.objects.link(ob)
                    made.append(ob)
                if sc.pc_limbs_hide:
                    obj.hide_set(True)
                for o in list(context.selected_objects):
                    o.select_set(False)
                for o in made:
                    o.select_set(True)
                context.view_layer.objects.active = made[0]
                self.report({'INFO'}, "Pieza separada: %s y %s (cerradas)"
                            % (made[0].name, made[1].name))
                return {'FINISHED'}
            self.report({'ERROR'}, str(last or "No se pudo separar"))
            return {'CANCELLED'}
        finally:
            context.window.cursor_set('DEFAULT')
            bpy.data.objects.remove(src, do_unlink=True)
            if base.users == 0:
                bpy.data.meshes.remove(base)


class MESH_OT_polycutter_cmd(bpy.types.Operator):
    """Puente entre los botones del panel y la sesión modal."""

    bl_idname = "mesh.polycutter_cmd"
    bl_label = "Orden PolyCutter"
    bl_options = {'INTERNAL'}

    cmd: StringProperty()

    @classmethod
    def poll(cls, context):
        return session.SESSION.active

    def execute(self, context):
        s = session.SESSION
        if s.active:
            s.submit(self.cmd)
        return {'FINISHED'}
