"""Monta hero.png y demo.gif a partir de docs/img/frames/ (requiere Pillow).

Uso (Python de Blender, que ya trae Pillow):
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\5.2\\python\\bin\\python.exe" docs/montage.py
"""

import glob
import os

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, "img")
FRAMES_DIR = os.path.join(IMG_DIR, "frames")


def load(f):
    return Image.open(os.path.join(FRAMES_DIR, "frame_%04d.png" % f)).convert("RGB")


files = sorted(glob.glob(os.path.join(FRAMES_DIR, "frame_*.png")))
if not files:
    raise SystemExit("No hay frames en docs/img/frames; ejecuta make_images.py primero.")

# Tira horizontal con tres momentos: lazo abierto, cerrado y piezas separadas.
hero = [load(15), load(35), load(63)]
w, h = hero[0].size
gap = 12
canvas = Image.new("RGB", (w * 3 + gap * 2, h), (10, 12, 16))
for i, im in enumerate(hero):
    canvas.paste(im, (i * (w + gap), 0))
hero_path = os.path.join(IMG_DIR, "hero.png")
canvas.save(hero_path, optimize=True)

# GIF animado (640x400, 90 ms por frame, paleta global de 128 colores).
# La paleta se calcula con varios fotogramas y con recortes ampliados del lazo
# para conservar los acentos de color (cian, verde, amarillo, magenta).
W, H = 640, 400
imgs = [Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS) for p in files]
sample = Image.new("RGB", (W, H * 8))
for i, idx in enumerate((0, 4, 8, 12, 16, 20, 24, 31)):
    sample.paste(imgs[idx], (0, i * H))
box = (int(W * 0.44), int(H * 0.28), int(W * 0.66), int(H * 0.62))
bw, bh = box[2] - box[0], box[3] - box[1]
tiles = []
for i in (0, 10, 17, 24):
    t = imgs[i].crop(box).resize((bw * 3, bh * 3), Image.LANCZOS)
    tiles.extend([t, t, t])  # triple peso a los acentos de color
extra = Image.new("RGB", (W, H * 8 + sum(t.size[1] for t in tiles)))
extra.paste(sample, (0, 0))
y = H * 8
for t in tiles:
    extra.paste(t, (0, y))
    y += t.size[1]
pal = extra.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
frames = [im.quantize(palette=pal, dither=Image.Dither.FLOYDSTEINBERG) for im in imgs]
gif_path = os.path.join(IMG_DIR, "demo.gif")
frames[0].save(gif_path, save_all=True, append_images=frames[1:],
               duration=90, loop=0, optimize=True)

for p in (hero_path, gif_path):
    print("%s  %.1f KB" % (p, os.path.getsize(p) / 1024.0))
