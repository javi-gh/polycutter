"""Configuración compartida de PolyCutter (sin imports de bpy)."""

VERSION = (1, 0, 0)

# Imprime trazas internas extra cuando está a True.
DEBUG = False

# --- interacción (píxeles) ---
PICK_PX = 16          # radio para agarrar un punto
PICK_SCALE = 1.4      # multiplicador al pulsar (más tolerante)
CLOSE_PX = 22         # radio del punto verde para cerrar el lazo
SEG_PX = 22           # radio para detectar un segmento (Shift+clic)
MIN_STROKE_PX = 5     # distancia mínima entre puntos al dibujar

# --- reglas del lazo ---
MIN_PTS = 3           # mínimo para cerrar el lazo
MIN_APPLY = 6         # mínimo para aplicar el corte
RIM_STEPS = (0.015, 0.03, 0.06)   # márgenes de la "cama" de la membrana
KEEPALIVE_S = 2.5     # segundos sin respuesta antes de considerar muerta la sesión

# --- HUD ---
HUD_FONT = 13
HUD_PAD = 12
HUD_GAP = 6
HUD_H = 28
HUD_Y = 52
HUD_MARGIN = 8

COLORS = {
    "fill": (1.0, 0.10, 0.10, 0.12),
    "fill_hot": (1.0, 0.10, 0.10, 0.30),
    "line": (0.0, 0.90, 1.0, 1.0),
    "line_hot": (0.10, 1.0, 0.40, 1.0),
    "point0": (1.0, 0.10, 0.80, 1.0),
    "point0_hot": (0.10, 1.0, 0.20, 1.0),
    "point": (1.0, 0.90, 0.10, 1.0),
    "hover": (1.0, 1.0, 1.0, 1.0),
    "drag": (1.0, 0.55, 0.05, 1.0),
    "hud_text": (1.0, 1.0, 1.0, 0.95),
    "hud_text_dim": (1.0, 1.0, 1.0, 0.40),
    "btn": (0.16, 0.16, 0.19, 0.88),
    "btn_hover": (0.32, 0.32, 0.38, 0.95),
    "btn_active": (0.18, 0.45, 0.90, 0.95),
    "btn_off": (0.12, 0.12, 0.12, 0.55),
    "btn_apply": (0.12, 0.60, 0.25, 0.95),
    "btn_apply_hover": (0.20, 0.75, 0.35, 0.98),
}

UI_HINT = ("D dibujar · M mover (clic en punto: arrastrar · Shift+clic: insertar · X: borrar) · "
           "C cerrar/abrir · Ctrl+Z deshacer · Ctrl+Enter aplicar · Esc cancelar")

PANEL_STEPS = (
    "1. Dibuja alrededor de la pieza (LMB)",
    "2. Suelta y orbita (MMB) para la espalda",
    "3. Cierra el lazo (clic en el punto verde o C)",
    "4. Ajusta puntos con «Mover»",
    "5. Pulsa «Aplicar corte»",
)


def log(msg):
    """Log interno con prefijo común."""
    print("PolyCutter:", msg)
