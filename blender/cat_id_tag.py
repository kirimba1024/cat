"""
QR-жетон (Blender 3.x / 4.x): чёрное НАКЛАДКОЙ СВЕРХУ (без вырезов, без пересечений).
Раскладка: ДЫРКА · ПАРКУРОВНА · QR · T.ME/KIRIMBA256.

Принцип (просто и надёжно):
  - белая плашка — цельная (только круглая дырка под кольцо);
  - чёрное (QR + буквы) лежит СВЕРХУ, низом ровно на поверхности плашки
    (касание, НЕ пересечение объёмов) → нет z-файтинга;
  - экспорт двух STL: плашка и накладка.

В Bambu: Import qr_1_plate.stl → правый клик → Add part → Load qr_2_inlay.stl.
Плашке белый филамент, накладке — чёрный. (Имена постоянные — удобно Reload.)

Печать (P1S, AMS): сопло 0.4 · слой 0.2 · без поддержек · матовый филамент.
"""

import bpy
import math
import sys
import os
import subprocess

# =========================
# НАСТРОЙКИ
# =========================
QR_URL = "kirimba1024.github.io/cat"
CAT_NAME = "Паркуровна"
BOTTOM_TEXT = "t.me/kirimba256"

EXPORT_DIR = ""

QR_MODULE_MM = 1.5
QUIET_MODULES = 2        # тихая зона (меньше = текст ближе к QR)
MODULE_GAP_MM = 0.10     # зазор между кубиками QR (манифольд; печать сольёт)
RAISE_HEIGHT = 1.0       # высота чёрного над плашкой (повыше, не плоско)

TAG_THICKNESS = 2.0
CORNER_RADIUS = 4.0
EDGE_MM = 3.0            # белое поле по бокам (доп. тихая зона слева/справа)

NAME_SIZE = 5.0
NAME_BOLD = 0.32         # жирность (палочки толще)
NAME_SPACING = 1.25      # межбуквенный интервал (чтобы не слипались)
NAME_GAP = 1.0           # QR ↔ имя — вплотную
BOTTOM_SIZE = 4.0        # крупнее (внизу есть место)
BOTTOM_BOLD = 0.26
BOTTOM_SPACING = 1.25
BOTTOM_GAP = 1.0         # QR ↔ нижняя строка — вплотную

HOLE_DIAMETER = 5.0
HOLE_GAP = 3.0           # имя ↔ дырка
MARGIN = 2.5             # поле у верх/низ краёв

BASE_COLOR = (1.0, 1.0, 1.0, 1.0)
BLACK_COLOR = (0.0, 0.0, 0.0, 1.0)
TOP_Z = TAG_THICKNESS


# =========================
# ФУНКЦИИ
# =========================
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def make_mat(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = color
    return m


def rounded_rect_points(w, h, r, seg=12):
    pts = []
    centers = [(w / 2 - r, h / 2 - r), (-w / 2 + r, h / 2 - r),
               (-w / 2 + r, -h / 2 + r), (w / 2 - r, -h / 2 + r)]
    rngs = [(0, math.pi / 2), (math.pi / 2, math.pi),
            (math.pi, 3 * math.pi / 2), (3 * math.pi / 2, 2 * math.pi)]
    for (cx, cy), (a0, a1) in zip(centers, rngs):
        for i in range(seg + 1):
            a = a0 + (a1 - a0) * i / seg
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def rounded_box(name, w, h, z, r, location=(0, 0, 0), mat=None):
    pts = rounded_rect_points(w, h, r)
    verts = [(x, y, 0) for x, y in pts] + [(x, y, z) for x, y in pts]
    n = len(pts)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, j + n, i + n))
    me = bpy.data.meshes.new(name + "_m")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.location = location
    if mat:
        o.data.materials.append(mat)
    bev = o.modifiers.new("bev", "BEVEL")
    bev.width = 0.4
    bev.segments = 3
    return o


def add_text(name, text, size, x, y, z_bottom, mat, bold=0.0, spacing=1.0):
    e = RAISE_HEIGHT / 2
    bpy.ops.object.text_add(location=(x, y, z_bottom + e))
    o = bpy.context.object
    o.name = name
    o.data.body = text
    o.data.align_x = "CENTER"
    o.data.align_y = "CENTER"
    o.data.size = size
    o.data.offset = bold
    o.data.space_character = spacing   # межбуквенный интервал
    o.data.extrude = e
    o.data.resolution_u = 16
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.convert(target="MESH")
    o = bpy.context.object
    me = o.data
    me.materials.clear()
    me.materials.append(mat)
    for p in me.polygons:
        p.material_index = 0
    return o


def create_qr_mesh(name, matrix, module, z, thickness, x0, y0, mat, gap):
    """Модули — отдельные ровные кубики с микрозазором (манифольд)."""
    n = len(matrix)
    span = n * module
    half = (module - gap) / 2
    verts, faces = [], []

    def add_box(cx, cy):
        i = len(verts)
        verts.extend([
            (cx - half, cy - half, z), (cx + half, cy - half, z),
            (cx + half, cy + half, z), (cx - half, cy + half, z),
            (cx - half, cy - half, z + thickness), (cx + half, cy - half, z + thickness),
            (cx + half, cy + half, z + thickness), (cx - half, cy + half, z + thickness),
        ])
        faces.extend([
            (i + 0, i + 3, i + 2, i + 1), (i + 4, i + 5, i + 6, i + 7),
            (i + 0, i + 1, i + 5, i + 4), (i + 1, i + 2, i + 6, i + 5),
            (i + 2, i + 3, i + 7, i + 6), (i + 3, i + 0, i + 4, i + 7),
        ])

    for row in range(n):
        for col in range(n):
            if matrix[row][col]:
                cx = x0 - span / 2 + module * col + module / 2
                cy = y0 + span / 2 - module * row - module / 2
                add_box(cx, cy)

    me = bpy.data.meshes.new(name + "_m")
    me.from_pydata(verts, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    o.data.materials.append(mat)
    return o


def boolean_cut(target, cutter):
    bpy.context.view_layer.objects.active = target
    m = target.modifiers.new("bool", "BOOLEAN")
    m.operation = "DIFFERENCE"
    m.solver = "EXACT"
    m.object = cutter
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def apply_mods(o):
    bpy.context.view_layer.objects.active = o
    for m in list(o.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print("skip mod", m.name, e)


def join(objs, name):
    objs = [o for o in objs if o is not None]
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    r = bpy.context.view_layer.objects.active
    r.name = name
    return r


def export_stl(o, path):
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    try:
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True,
                              apply_modifiers=True)
    except AttributeError:
        bpy.ops.export_mesh.stl(filepath=path, use_selection=True)
    print("STL:", path)


def ensure_qrcode():
    try:
        import qrcode
        return qrcode
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "ensurepip"])
            subprocess.check_call([sys.executable, "-m", "pip", "install", "qrcode"])
            import qrcode
            return qrcode
        except Exception as e:
            print("qrcode install fail:", e)
            return None


def get_qr_matrix(data, border):
    qrcode = ensure_qrcode()
    if qrcode is None:
        return None
    qr = qrcode.QRCode(version=None,
                       error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=1, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


# =========================
# ПОСТРОЕНИЕ
# =========================
clear_scene()
bpy.context.scene.unit_settings.system = "METRIC"
bpy.context.scene.unit_settings.scale_length = 0.001

mat_white = make_mat("WHITE_PLATE", BASE_COLOR)
mat_black = make_mat("BLACK_INLAY", BLACK_COLOR)

matrix = get_qr_matrix(QR_URL, QUIET_MODULES)
if matrix is None:
    raise RuntimeError("Нет модуля qrcode.")

n = len(matrix)
qr_span = n * QR_MODULE_MM

name_half = NAME_SIZE * 0.40
bot_half = BOTTOM_SIZE * 0.40
hole_r = HOLE_DIAMETER / 2

name_y = qr_span / 2 + NAME_GAP + name_half
hole_y = name_y + name_half + HOLE_GAP + hole_r
bottom_y = -qr_span / 2 - BOTTOM_GAP - bot_half

top_edge = hole_y + hole_r + MARGIN
bot_edge = bottom_y - bot_half - MARGIN
plate_h = top_edge - bot_edge
plate_cy = (top_edge + bot_edge) / 2
plate_w = qr_span + 2 * EDGE_MM
T = TAG_THICKNESS

print("QR %dx%d, модуль %.2f мм | плашка %.1f x %.1f x %.1f мм | чёрное h=%.1f"
      % (n, n, QR_MODULE_MM, plate_w, plate_h, T, RAISE_HEIGHT))

# Белая плашка + круглая дырка
plate = rounded_box("QR_PLATE", plate_w, plate_h, T, CORNER_RADIUS,
                    location=(0, plate_cy, 0), mat=mat_white)
apply_mods(plate)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=HOLE_DIAMETER / 2,
                                    depth=T + 4, location=(0, hole_y, T / 2))
boolean_cut(plate, bpy.context.object)
plate.name = "QR_PLATE"

# Чёрное СВЕРХУ (низ на поверхности плашки, касание без пересечения)
parts = []
parts.append(create_qr_mesh("QR_CODE", matrix, QR_MODULE_MM, TOP_Z, RAISE_HEIGHT,
                            0.0, 0.0, mat_black, MODULE_GAP_MM))
parts.append(add_text("NAME", CAT_NAME.upper(), NAME_SIZE, 0.0, name_y,
                      TOP_Z, mat_black, bold=NAME_BOLD, spacing=NAME_SPACING))
parts.append(add_text("BOTTOM", BOTTOM_TEXT.upper(), BOTTOM_SIZE, 0.0, bottom_y,
                      TOP_Z, mat_black, bold=BOTTOM_BOLD, spacing=BOTTOM_SPACING))
inlay = join(parts, "QR_INLAY")

# Камера сверху
bpy.ops.object.light_add(type="AREA", location=(0, plate_cy, 120))
bpy.context.object.data.energy = 600
bpy.context.object.data.size = 150
bpy.ops.object.camera_add(location=(0, plate_cy, 150), rotation=(0, 0, 0))
bpy.context.scene.camera = bpy.context.object

# =========================
# ЭКСПОРТ
# =========================
if EXPORT_DIR:
    out_dir = bpy.path.abspath(EXPORT_DIR)
elif bpy.data.filepath:
    out_dir = bpy.path.abspath("//")
else:
    out_dir = os.path.join(os.path.expanduser("~"), "Desktop")
os.makedirs(out_dir, exist_ok=True)

plate_path = os.path.join(out_dir, "qr_1_plate.stl")
inlay_path = os.path.join(out_dir, "qr_2_inlay.stl")
export_stl(plate, plate_path)
export_stl(inlay, inlay_path)

bpy.ops.object.select_all(action="DESELECT")
plate.select_set(True)
inlay.select_set(True)

print("=" * 52)
print("ГОТОВО (накладка сверху, без пересечений):")
print("  1) ПЛАШКА  →", plate_path)
print("  2) НАКЛАДКА →", inlay_path)
print("Bambu: Import плашку → Add part → Load накладку. Белый/чёрный.")
print("QR ведёт на:", QR_URL)
