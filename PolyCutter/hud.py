"""HUD y vista previa 3D, con cachés de layout, proyección y batches GPU."""

import blf
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector

from . import config, session


def _shader():
    return gpu.shader.from_builtin('UNIFORM_COLOR')


class ProjectionCache:
    """Proyección 3D->2D de los puntos; invalida por vista o edición."""

    def __init__(self):
        self.key = None
        self.scr = []

    @staticmethod
    def _key_for(s):
        m = s.rv3d.view_matrix
        vals = tuple(round(v, 6) for row in m for v in row)
        return (s.region.width, s.region.height, vals, s.pts_version, len(s.pts))

    def ensure(self, s):
        key = self._key_for(s)
        if key != self.key:
            self.scr = [view3d_utils.location_3d_to_region_2d(s.region, s.rv3d, p)
                        for p in s.pts]
            self.key = key
        return self.scr


class BatchCache:
    """Batches GPU reutilizables mientras el lazo no cambie."""

    def __init__(self):
        self.key = None
        self.line = self.fill = self.first = self.rest = None

    def ensure(self, s):
        key = (s.pts_version, s.closed, len(s.pts))
        if key == self.key:
            return
        pts = [tuple(p) for p in s.pts]
        sh = _shader()
        line = list(pts)
        if s.closed and pts:
            line.append(pts[0])
        self.line = batch_for_shader(sh, 'LINE_STRIP', {"pos": line}) if len(line) >= 2 else None
        self.first = batch_for_shader(sh, 'POINTS', {"pos": [pts[0]]}) if pts else None
        self.rest = batch_for_shader(sh, 'POINTS', {"pos": pts[1:]}) if len(pts) > 1 else None
        self.fill = None
        if len(pts) >= 3:
            cen = sum(s.pts, Vector()) / len(pts)
            tris = []
            for i in range(len(pts)):
                tris += [tuple(cen), pts[i], pts[(i + 1) % len(pts)]]
            self.fill = batch_for_shader(sh, 'TRIS', {"pos": tris})
        self.key = key


class HudLayout:
    """Layout de la barra de botones; se recalcula solo si cambia el estado."""

    def __init__(self):
        self.key = None
        self.rects = []

    def get(self, s):
        items = session.command_items(s)
        key = (s.region.width,
               tuple((it["text"], it["enabled"], it["active"]) for it in items))
        if key == self.key:
            return self.rects
        blf.size(0, config.HUD_FONT)
        pad, gap, h = config.HUD_PAD, config.HUD_GAP, config.HUD_H
        widths = [blf.dimensions(0, it["text"])[0] + 2 * pad for it in items]
        total = sum(widths) + gap * (len(items) - 1)
        x = max(config.HUD_MARGIN, (s.region.width - total) / 2)
        rects = []
        for it, w in zip(items, widths):
            rects.append((it, x, config.HUD_Y, x + w, config.HUD_Y + h))
            x += w + gap
        self.key, self.rects = key, rects
        return rects


_proj = ProjectionCache()
_batches = BatchCache()
_layout = HudLayout()


def reset_caches():
    """Libera las cachés entre sesiones."""
    _proj.__init__()
    _batches.__init__()
    _layout.__init__()


def projection(s):
    return _proj.ensure(s)


def hud_at(s, coord):
    """Comando cuyo botón contiene `coord`, o None."""
    for it, x0, y0, x1, y1 in _layout.get(s):
        if x0 <= coord[0] <= x1 and y0 <= coord[1] <= y1:
            return it["cmd"]
    return None


def _hot(s):
    """True si el lazo debe verse 'caliente' (cerrado o cursor sobre el punto verde)."""
    if s.closed:
        return True
    if len(s.pts) < config.MIN_PTS:
        return False
    p = projection(s)[0]
    return p is not None and (Vector(s.last) - p).length <= config.CLOSE_PX


def draw_scene():
    """Handler POST_VIEW: relleno, lazo, puntos y resaltado del punto activo."""
    s = session.SESSION
    if not s.active or not s.pts:
        return
    sh = _shader()
    sh.bind()
    gpu.state.blend_set('ALPHA')
    gpu.state.depth_test_set('NONE')
    gpu.state.line_width_set(2.5)
    try:
        _batches.ensure(s)
        hot = _hot(s)
        colors = config.COLORS
        if _batches.fill is not None:
            gpu.state.depth_mask_set(False)
            sh.uniform_float("color", colors["fill_hot"] if hot else colors["fill"])
            _batches.fill.draw(sh)
            gpu.state.depth_mask_set(True)
        if _batches.line is not None:
            sh.uniform_float("color", colors["line_hot"] if hot else colors["line"])
            _batches.line.draw(sh)
        if hot and not s.closed and len(s.pts) >= 2:
            b = batch_for_shader(sh, 'LINE_STRIP',
                                 {"pos": [tuple(s.pts[-1]), tuple(s.pts[0])]})
            sh.uniform_float("color", colors["line_hot"])
            b.draw(sh)
        gpu.state.point_size_set(12)
        if _batches.first is not None:
            sh.uniform_float("color", colors["point0_hot"] if hot else colors["point0"])
            _batches.first.draw(sh)
        if _batches.rest is not None:
            gpu.state.point_size_set(9)
            sh.uniform_float("color", colors["point"])
            _batches.rest.draw(sh)
        hi = s.drag["idx"] if s.drag else s.hover
        if hi is not None and 0 <= hi < len(s.pts):
            gpu.state.point_size_set(16)
            b = batch_for_shader(sh, 'POINTS', {"pos": [tuple(s.pts[hi])]})
            sh.uniform_float("color", colors["drag"] if s.drag else colors["hover"])
            b.draw(sh)
    finally:
        gpu.state.point_size_set(1)
        gpu.state.line_width_set(1)
        gpu.state.depth_mask_set(True)
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.blend_set('NONE')


def draw_hud():
    """Handler POST_PIXEL: barra de botones, estado y ayuda."""
    s = session.SESSION
    if not s.active:
        return
    rects = _layout.get(s)
    sh = _shader()
    sh.bind()
    gpu.state.blend_set('ALPHA')
    try:
        for it, x0, y0, x1, y1 in rects:
            if not it["enabled"]:
                col = config.COLORS["btn_off"]
            elif it["cmd"] == 'APPLY':
                col = (config.COLORS["btn_apply_hover"] if s.hud_hover == it["cmd"]
                       else config.COLORS["btn_apply"])
            elif it["active"]:
                col = config.COLORS["btn_active"]
            elif s.hud_hover == it["cmd"]:
                col = config.COLORS["btn_hover"]
            else:
                col = config.COLORS["btn"]
            sh.uniform_float("color", col)
            quad = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            batch_for_shader(sh, 'TRI_FAN', {"pos": quad}).draw(sh)
            blf.color(0, *(config.COLORS["hud_text"] if it["enabled"]
                           else config.COLORS["hud_text_dim"]))
            blf.position(0, x0 + config.HUD_PAD, y0 + 8, 0)
            blf.draw(0, it["text"])
    finally:
        gpu.state.blend_set('NONE')
    blf.size(0, config.HUD_FONT)
    blf.color(0, *config.COLORS["hud_text"])
    blf.position(0, 24, 34, 0)
    blf.draw(0, session.status_text(s))
    blf.color(0, *config.COLORS["hud_text_dim"])
    blf.position(0, 24, 16, 0)
    blf.draw(0, config.UI_HINT)
