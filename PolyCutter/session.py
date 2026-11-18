"""Estado de la sesión de corte y tabla única de comandos de UI."""

import time

from . import config


class Session:
    """Única fuente de verdad de una sesión PolyCutter.

    El operador modal la muta; el panel y el HUD solo la leen.
    """

    def __init__(self):
        # Monotónica a propósito: nunca se reinicia para no colisionar
        # con las claves de caché del HUD entre sesiones.
        self.pts_version = 0
        self.reset()

    def reset(self):
        """Restablece la sesión y libera referencias a datablocks."""
        self.active = False
        self.obj = None
        self.area = None
        self.space = None
        self.region = None
        self.rv3d = None
        self.pts, self.nrm, self.strokes = [], [], []
        self.closed = False
        self.mode = 'DRAW'
        self.drawing = False
        self.drag = None
        self.hover = None
        self.hud_hover = None
        self.last = (0, 0)
        self.prev_x = None
        self.h2 = self.h3 = None
        self.timer = None
        self.stamp = 0.0
        self._pending = []

    @property
    def n(self):
        return len(self.pts)

    # --- keepalive ---------------------------------------------------
    def touch(self):
        self.stamp = time.monotonic()

    def alive(self):
        """True si hay sesión y el operador sigue respondiendo."""
        return self.active and (time.monotonic() - self.stamp) < config.KEEPALIVE_S

    # --- comandos desde el panel --------------------------------------
    def submit(self, cmd):
        """Encola un comando del panel (se ejecuta en el próximo tick)."""
        if len(self._pending) < 32:
            self._pending.append(cmd)

    def take(self):
        """Devuelve y vacía los comandos pendientes."""
        cmds, self._pending = self._pending, []
        return cmds

    def changed(self):
        """Marca los puntos como modificados (invalida cachés de dibujo)."""
        self.pts_version += 1


SESSION = Session()


def command_items(s):
    """Comandos de UI resueltos: única fuente para HUD y panel."""
    n = s.n
    return [
        {"cmd": "DRAW", "text": "Dibujar", "icon": 'NONE', "key": "D",
         "enabled": True, "active": s.mode == 'DRAW'},
        {"cmd": "MOVE", "text": "Mover", "icon": 'NONE', "key": "M",
         "enabled": True, "active": s.mode == 'MOVE'},
        {"cmd": "CLOSE", "text": "Abrir lazo" if s.closed else "Cerrar lazo",
         "icon": 'MESH_CIRCLE', "key": "C",
         "enabled": n >= config.MIN_PTS, "active": s.closed},
        {"cmd": "UNDO", "text": "Deshacer tramo", "icon": 'BACK', "key": "Ctrl+Z",
         "enabled": bool(s.strokes), "active": False},
        {"cmd": "CLEAR", "text": "Borrar todo", "icon": 'NONE', "key": "",
         "enabled": n > 0, "active": False},
        {"cmd": "APPLY", "text": "APLICAR CORTE", "icon": 'CHECKMARK', "key": "Ctrl+Enter",
         "enabled": s.closed and n >= config.MIN_APPLY, "active": False},
        {"cmd": "CANCEL", "text": "Cancelar", "icon": 'X', "key": "Esc",
         "enabled": True, "active": False},
    ]


def status_text(s):
    """Texto de estado compartido por HUD y panel."""
    return "Puntos: %d  |  Lazo: %s  |  Modo: %s" % (
        s.n,
        "cerrado" if s.closed else "abierto",
        "MOVER" if s.mode == 'MOVE' else "DIBUJAR",
    )
