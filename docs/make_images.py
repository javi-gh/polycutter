"""Renderiza los fotogramas de demostración del README con Blender (Cycles, CPU).

Uso:
    blender --background --factory-startup --python docs/make_images.py
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\5.2\\python\\bin\\python.exe" docs/montage.py

make_images.py deja los PNG en docs/img/frames/ y montage.py genera
docs/img/hero.png y docs/img/demo.gif (requiere Pillow).
"""

import math
import os

import bpy

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, "img")
FRAMES_DIR = os.path.join(IMG_DIR, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

STEEL = (0.50, 0.53, 0.58)
RED = (0.85, 0.10, 0.05)
BLUE = (0.05, 0.25, 0.95)
Z = 0.62
CUT_X = 0.55

# --------------------------------------------------------------------- escena
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = 720
scene.render.resolution_y = 450
scene.render.resolution_percentage = 100
scene.render.fps = 10
scene.frame_start, scene.frame_end = 1, 64
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass
scene.view_settings.exposure = -0.8

world = bpy.data.worlds.new("World")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.020, 0.026, 0.038, 1.0)
bg.inputs[1].default_value = 0.60
scene.world = world


def new_mat(name, color, rough=0.4):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    return m


def glow_mat(name, color, strength=1.0):
    m = new_mat(name, tuple(c * 0.05 for c in color), rough=0.3)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*color, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return m


mat_a = new_mat("PieceA", STEEL)
mat_b = new_mat("PieceB", STEEL)
mat_floor = new_mat("Floor", (0.030, 0.036, 0.048), rough=0.45)
mat_open = glow_mat("LoopOpen", (0.0, 0.65, 1.0))
mat_closed = glow_mat("LoopClosed", (0.10, 1.0, 0.20))
mat_dot = glow_mat("Dot", (1.0, 0.65, 0.0), 1.6)
mat_dot0 = glow_mat("Dot0", (1.0, 0.05, 0.60), 2.0)
mat_dot0b = glow_mat("Dot0Closed", (0.05, 1.0, 0.15), 2.0)


def shade(ob):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.shade_smooth()
    ob.select_set(False)


def cylinder(name, r, x0, x1, mat):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64, radius=r, depth=(x1 - x0),
        location=((x0 + x1) / 2.0, 0, Z), rotation=(0, math.pi / 2.0, 0))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    shade(ob)
    return ob


def ball(name, r, x, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=48, ring_count=24, radius=r, location=(x, 0, Z))
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    shade(ob)
    return ob


# Piezas: A (izquierda) y B (derecha, con "garra")
pieces_a = [cylinder("ArmA", 0.30, -1.75, CUT_X, mat_a),
            ball("CapA0", 0.30, -1.75, mat_a),
            ball("CapA1", 0.30, CUT_X, mat_a)]
pieces_b = [cylinder("ArmB", 0.30, CUT_X, 1.30, mat_b),
            ball("CapB0", 0.30, CUT_X, mat_b),
            ball("CapB1", 0.30, 1.30, mat_b),
            ball("Paw", 0.50, 1.78, mat_b)]

emp_a = bpy.data.objects.new("PieceA", None)
emp_b = bpy.data.objects.new("PieceB", None)
for e in (emp_a, emp_b):
    scene.collection.objects.link(e)
for ob in pieces_a:
    ob.parent = emp_a
for ob in pieces_b:
    ob.parent = emp_b

# Lazo: anillo de puntos alrededor del corte (plano YZ)
N = 32
LOOP_R = 0.48
angles = [math.radians(-90 + 11.25 * i) for i in range(N)]
ring = [(CUT_X, LOOP_R * math.cos(a), Z + LOOP_R * math.sin(a)) for a in angles]
open_pts = ring[:25]   # deja un hueco para "abrir" el lazo


def curve_obj(name, pts, mat, cyclic):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = 0.015
    cu.bevel_resolution = 3
    cu.resolution_u = 4
    sp = cu.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (*co, 1.0)
    sp.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(name, cu)
    scene.collection.objects.link(ob)
    cu.materials.append(mat)
    return ob


loop_open = curve_obj("LoopOpen", open_pts, mat_open, cyclic=False)
loop_closed = curve_obj("LoopClosed", ring, mat_closed, cyclic=True)


def dot(name, co, r, mat):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=co)
    ob = bpy.context.object
    ob.name = name
    ob.data.materials.append(mat)
    shade(ob)
    return ob


dots = [dot("Dot%d" % i, ring[i], 0.040, mat_dot) for i in range(2, N, 2)]
dot0_on = dot("Dot0Open", ring[0], 0.045, mat_dot0)
dot0_off = dot("Dot0Closed", ring[0], 0.045, mat_dot0b)


def key_hide(ob, frame, hidden):
    ob.hide_render = hidden
    ob.keyframe_insert("hide_render", frame=frame)


def key_color(mat, frame, color):
    b = mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"]
    b.default_value = (*color, 1.0)
    b.keyframe_insert("default_value", frame=frame)


def key_emission(mat, frame, color):
    b = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Color"]
    b.default_value = (*color, 1.0)
    b.keyframe_insert("default_value", frame=frame)


def key_x(ob, frame, x):
    ob.location.x = x
    ob.keyframe_insert("location", index=0, frame=frame)


# Timeline: 1-20 lazo abierto | 21-40 cerrado | 41-64 piezas separadas
for ob in (loop_open, dot0_on):
    key_hide(ob, 1, False)
    key_hide(ob, 21, True)
for ob in (loop_closed, dot0_off):
    key_hide(ob, 1, True)
    key_hide(ob, 21, False)
    key_hide(ob, 41, True)
for ob in dots:
    key_hide(ob, 1, False)
    key_hide(ob, 41, True)

# Al cerrar el lazo los puntos pasan de amarillo a verde.
key_emission(mat_dot, 1, (1.0, 0.65, 0.0))
key_emission(mat_dot, 21, (0.05, 1.0, 0.15))

key_color(mat_a, 1, STEEL)
key_color(mat_a, 41, STEEL)
key_color(mat_a, 50, RED)
key_color(mat_b, 1, STEEL)
key_color(mat_b, 41, STEEL)
key_color(mat_b, 50, BLUE)
key_x(emp_a, 41, 0.0)
key_x(emp_a, 60, -0.62)
key_x(emp_b, 41, 0.0)
key_x(emp_b, 60, 0.62)

# Suelo y luces
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))
floor = bpy.context.object
floor.data.materials.append(mat_floor)

for loc, energy, size in (((3.0, -4.0, 5.0), 500, 4.0),
                          ((-4.0, 2.5, 4.0), 350, 3.0),
                          ((0.0, 5.0, 3.0), 150, 3.0)):
    light = bpy.data.lights.new("Area", 'AREA')
    light.energy = energy
    light.size = size
    lob = bpy.data.objects.new("Area", light)
    lob.location = loc
    scene.collection.objects.link(lob)

# Cámara con leve órbita (encuadre amplio para ver las piezas separadas)
cam_data = bpy.data.cameras.new("Cam")
cam_data.lens = 36
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("Target", None)
target.location = (0.10, 0.0, 0.45)
scene.collection.objects.link(target)
con = cam.constraints.new('TRACK_TO')
con.target = target
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'
cam.location = (4.3, -6.0, 2.8)
cam.keyframe_insert("location", frame=1)
cam.location = (3.9, -6.4, 2.6)
cam.keyframe_insert("location", frame=32)
cam.location = (3.5, -6.8, 2.4)
cam.keyframe_insert("location", frame=64)

# Render de fotogramas (uno de cada dos para el GIF)
# PC_RESUME=1 reanuda un render interrumpido saltando los PNG ya existentes.
RESUME = os.environ.get("PC_RESUME") == "1"
for f in range(1, 64, 2):
    out = os.path.join(FRAMES_DIR, "frame_%04d.png" % f)
    if RESUME and os.path.exists(out) and os.path.getsize(out) > 0:
        print("skip", f)
        continue
    scene.frame_set(f)
    scene.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("render", f)

print("Frames listos en", FRAMES_DIR)
print("Ahora ejecuta docs/montage.py con el Python de Blender para montar GIF y hero.")
