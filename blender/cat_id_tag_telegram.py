"""
QR-жетон → ТЕЛЕГРАМ (t.me/kirimba256). Только QR + маленькое ушко с дыркой.
(Аналог cat_id_tag.py, но QR ведёт прямо в Telegram, и STL — отдельные файлы.)

Принцип (просто и надёжно):
  - белая плашка — ровно по размеру QR (никаких лишних полей; тихая зона
    уже встроена в матрицу QR через border), сверху маленькая округлая
    выпуклость («ушко») с отверстием под кольцо;
  - чёрный QR лежит СВЕРХУ, НИЗКИМ слоем, низом ровно на поверхности плашки
    (касание, НЕ пересечение объёмов) → нет z-файтинга и не отрывается;
  - модули QR — сплошные кубики (низкий слой = печать заполнит на 100%);
  - экспорт двух STL: плашка и накладка.

В Bambu: Import qr_1_plate.stl → правый клик → Add part → Load qr_2_inlay.stl.
Плашке белый филамент, накладке — чёрный. (Имена постоянные — удобно Reload.)

Печать (P1S, AMS): сопло 0.4 · слой 0.16 · без поддержек · матовый филамент.
"""

import bpy
import math
import sys
import os
import subprocess

# =========================
# НАСТРОЙКИ
# =========================
QR_URL = "t.me/kirimba256"

EXPORT_DIR = ""

QR_MODULE_MM = 1.5       # размер модуля QR (1.5–2.0 хорошо читается телефоном)
QUIET_MODULES = 2        # тихая зона (белое поле вокруг QR) — встроена в плашку
MODULE_GAP_MM = 0.10     # микрозазор между кубиками QR (манифольд; печать сольёт)

RAISE_HEIGHT = 0.6       # высота чёрного над плашкой: НИЗКО = не отрывается и сплошной

TAG_THICKNESS = 4.0      # толщина белой плашки (толстая = прочная, не сломается)
CORNER_RADIUS = 1.5      # лёгкое скругление углов квадрата (не залезает в QR)

# Ушко сверху (маленькая округлая выпуклость с отверстием)
HOLE_DIAMETER = 4.0      # отверстие под кольцо/карабин
TAB_WALL = 1.8           # стенка вокруг отверстия (радиус ушка = hole_r + TAB_WALL)

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


def _arc(cx, cy, r, a0, a1, seg):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / seg),
             cy + r * math.sin(a0 + (a1 - a0) * i / seg)) for i in range(seg + 1)]


def plate_outline(w, h, r, tab_r, seg=6, tab_seg=24):
    """Квадрат со скруглёнными углами + округлое ушко сверху по центру."""
    p = []
    p += _arc(w / 2 - r, -h / 2 + r, r, -math.pi / 2, 0, seg)        # низ-право
    p += _arc(w / 2 - r,  h / 2 - r, r, 0, math.pi / 2, seg)         # верх-право
    p += _arc(0.0,        h / 2,     tab_r, 0, math.pi, tab_seg)     # ушко (дуга)
    p += _arc(-w / 2 + r, h / 2 - r, r, math.pi / 2, math.pi, seg)   # верх-лево
    p += _arc(-w / 2 + r, -h / 2 + r, r, math.pi, 3 * math.pi / 2, seg)  # низ-лево
    # убрать дубли подряд (стыки дуг)
    out = []
    for pt in p:
        if not out or abs(pt[0] - out[-1][0]) > 1e-6 or abs(pt[1] - out[-1][1]) > 1e-6:
            out.append(pt)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-6 and abs(out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def extrude_poly(name, pts, z, location=(0, 0, 0), mat=None, bevel=0.4):
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
    if bevel:
        bev = o.modifiers.new("bev", "BEVEL")
        bev.width = bevel
        bev.segments = 2
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
qr_span = n * QR_MODULE_MM          # плашка ровно по QR (тихая зона внутри матрицы)
W = H = qr_span
T = TAG_THICKNESS
hole_r = HOLE_DIAMETER / 2
tab_r = hole_r + TAB_WALL           # радиус ушка
hole_y = H / 2                      # центр дырки — на верхней кромке (внутри ушка)

print("QR %dx%d, модуль %.2f мм | плашка %.1f x %.1f x %.1f мм | "
      "ушко r=%.1f, дырка ⌀%.1f | чёрное h=%.1f"
      % (n, n, QR_MODULE_MM, W, H, T, tab_r, HOLE_DIAMETER, RAISE_HEIGHT))

# Белая плашка (квадрат по QR + округлое ушко) + отверстие
outline = plate_outline(W, H, CORNER_RADIUS, tab_r)
plate = extrude_poly("QR_PLATE", outline, T, mat=mat_white)
apply_mods(plate)
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=hole_r,
                                    depth=T + 4, location=(0, hole_y, T / 2))
boolean_cut(plate, bpy.context.object)
plate.name = "QR_PLATE"

# Чёрный QR СВЕРХУ (низ на поверхности плашки, касание без пересечения)
inlay = create_qr_mesh("QR_INLAY", matrix, QR_MODULE_MM, TOP_Z, RAISE_HEIGHT,
                       0.0, 0.0, mat_black, MODULE_GAP_MM)

# Камера сверху
bpy.ops.object.light_add(type="AREA", location=(0, 0, 120))
bpy.context.object.data.energy = 600
bpy.context.object.data.size = 150
bpy.ops.object.camera_add(location=(0, 0, 150), rotation=(0, 0, 0))
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

plate_path = os.path.join(out_dir, "qr_tg_1_plate.stl")
inlay_path = os.path.join(out_dir, "qr_tg_2_inlay.stl")
export_stl(plate, plate_path)
export_stl(inlay, inlay_path)

bpy.ops.object.select_all(action="DESELECT")
plate.select_set(True)
inlay.select_set(True)

print("=" * 52)
print("ГОТОВО (только QR + ушко, накладка сверху):")
print("  1) ПЛАШКА  →", plate_path)
print("  2) НАКЛАДКА →", inlay_path)
print("Bambu: Import плашку → Add part → Load накладку. Белый/чёрный.")
print("QR ведёт на:", QR_URL)
