"""
blender_prepare_stl.py — РАЗОБРАТЬ ПРИСЛАННУЮ STL-МОДЕЛЬ НА ЧАСТИ.

ЗАЧЕМ. Модель приехала как одна оболочка под 3D-печать: голова, цилиндр, руки и
торс СПЛАВЛЕНЫ (108 218 вершин в одном куске), отдельно только ноги, трость и
опорная площадка. Для печати так и надо, для анимации — наоборот. Пока лицо не
отделено, его приходится угадывать по геометрии, и на части ракурсов угадывание
ошибается: светлое пятно уезжает на затылок (проверено, видно на 45° и 315°).

ЗАПУСК. Внутри Blender, у него свой Python с `bpy`:
    1. Blender → вкладка «Scripting».
    2. Text → Open → этот файл (или вставить текст).
    3. Указать путь к STL в STL_PATH ниже.
    4. ▶ Run Script (Alt+P).

Что появится: объекты `body`, `face`, `leg_l`, `leg_r`, `cane` в сцене, восемь
PNG-ракурсов и `freeman_parts.glb` рядом с .blend (или в ~/freeman_parts_out/).

ЧТО СКРИПТ ДЕЛАЕТ НАДЁЖНО
  · выкидывает опорную площадку для печати (нижняя оболочка);
  · разделяет несвязанные куски и даёт им имена по положению;
  · вешает материалы: лицо светлое (#eef1ec), остальное тушь (#0e0e0e) —
    ровно наши цвета из рига;
  · рендерит разворот ортографической камерой под углами `turnaround.py`;
  · экспортирует .glb, который я читаю без Blender.

ЧТО СКРИПТ ДЕЛАЕТ С ОГОВОРКОЙ
  · ОТДЕЛЯЕТ ЛИЦО. Лица как отдельной поверхности в модели нет, поэтому оно
    ищется по геометрии: полоса высоты под полями шляпы и выше плеч, и в ней
    грани, смотрящие ВПЕРЁД. Направление «вперёд» считается ОДИН РАЗ в системе
    самой модели — это и есть починка той ошибки, из-за которой пятно уезжало
    при повороте.
    Полоса задаётся двумя числами (`HEAD_TOP`, `HEAD_BOT`) — если лицо
    отделилось не там, правятся они, а не код. Скрипт печатает, сколько граней
    попало, и это первое, на что смотреть.

ЧЕГО СКРИПТ НЕ ДЕЛАЕТ, И ЭТО НЕ ЛЕНЬ
  · НЕ ОСНАЩАЕТ СКЕЛЕТОМ. Автоматическая развесовка по сплавленному мешу на
    108 тысяч вершин даёт мусор в суставах — это ручная работа.
  · НЕ МЕНЯЕТ ПОЗУ. Модель приехала с рукой у шляпы и опорой на трость.
    Нейтральную стойку из неё без скелета не получить, а разворот меряют по
    стойке.
"""

import bpy
import bmesh
import math
import os
from mathutils import Vector

# ============================================================================
#  ЧТО ПРАВИТЬ
# ============================================================================

STL_PATH = ""            # ← путь к mr_freeman.stl. Пусто = взять уже открытую сцену

# Полоса высоты, в которой ищется лицо (доли роста от макушки, макушка = 0).
# Границы взяты из профиля ширины модели: поля шляпы кончаются к 0.13, плечи
# начинаются к 0.34. Если лицо отделилось не там — править ЭТИ два числа.
HEAD_TOP = 0.13
HEAD_BOT = 0.34

# Насколько «вперёд» должна смотреть грань, чтобы считаться лицом (косинус).
# 0.35 ≈ 70° от направления взгляда. Больше — уже пятно, меньше — заезжает на бока.
FACE_COS = 0.35

ANGLES = [0, 22, 45, 90, 135, 180, 225, 315]

INK = (0.055, 0.055, 0.050, 1.0)      # #0e0e0e — тушь рига
PAPER_FACE = (0.933, 0.945, 0.925, 1.0)  # #eef1ec — светлая маска рига
BG = (0.86, 0.86, 0.84, 1.0)


def log(*a):
    print("[prepare]", *a)


def flat_material(name, rgba):
    """Плоская заливка без света: канон — тушь без объёма."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = rgba
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def import_stl():
    if not STL_PATH:
        log("STL_PATH пуст — работаю с тем, что уже в сцене")
        return
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    # У Blender 4.x свой оператор импорта; у 3.x — старый. Пробуем оба.
    try:
        bpy.ops.wm.stl_import(filepath=STL_PATH)
    except AttributeError:
        bpy.ops.import_mesh.stl(filepath=STL_PATH)
    log("импортирован:", os.path.basename(STL_PATH))


def split_loose():
    """Разделить несвязанные куски и назвать их по положению."""
    obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.mesh.separate(type="LOOSE")
    parts = [o for o in bpy.context.selected_objects if o.type == "MESH"]
    log("несвязанных кусков:", len(parts))

    def zmin(o):
        return min((o.matrix_world @ v.co).z for v in o.data.vertices)

    def nverts(o):
        return len(o.data.vertices)

    # ОПОРНАЯ ПЛОЩАДКА — самый нижний и плоский кусок. Её надо выкинуть: на
    # силуэте она читается чёрной полосой под ногами.
    def flatness(o):
        zs = [(o.matrix_world @ v.co).z for v in o.data.vertices]
        return max(zs) - min(zs)

    base = min(parts, key=lambda o: (flatness(o), zmin(o)))
    if flatness(base) < 0.1 * max(flatness(o) for o in parts):
        log("выкидываю опорную площадку:", nverts(base), "вершин")
        bpy.data.objects.remove(base, do_unlink=True)
        parts.remove(base)

    parts.sort(key=nverts, reverse=True)
    parts[0].name = "body"
    rest = parts[1:]
    # ноги — самые высокие из оставшихся, трость — самая тонкая и длинная
    rest.sort(key=lambda o: -nverts(o))
    names = ["leg_a", "leg_b", "cane"] + [f"part{i}" for i in range(9)]
    for o, nm in zip(rest, names):
        o.name = nm
    log("части:", ", ".join(f"{o.name}({nverts(o)})" for o in parts))
    return parts[0]


def facing_direction(body):
    """Куда смотрит фигура. Считается ОДИН РАЗ, в системе модели.

    Именно отсутствие этого шага давало уезжающее пятно: я отбирал лицо по
    нормали относительно фиксированной оси кадра, а при повороте «вперёд»
    становилось другим направлением. Здесь направление определяется по самой
    модели и дальше не меняется.

    Признак: лицо — самая выступающая часть головы. Берём полосу головы и
    смотрим, в какую сторону по Y она выдаётся сильнее относительно корпуса.
    """
    me = body.data
    zs = [v.co.z for v in me.vertices]
    z1, z0 = max(zs), min(zs)
    H = z1 - z0
    head = [v.co for v in me.vertices
            if z1 - H * HEAD_BOT < v.co.z < z1 - H * HEAD_TOP]
    torso = [v.co for v in me.vertices if v.co.z < z1 - H * HEAD_BOT]
    if not head or not torso:
        log("ВНИМАНИЕ: полоса головы пуста — правь HEAD_TOP/HEAD_BOT")
        return Vector((0, -1, 0))
    hy = sum(c.y for c in head) / len(head)
    ty = sum(c.y for c in torso) / len(torso)
    d = Vector((0, -1, 0)) if hy < ty else Vector((0, 1, 0))
    log(f"направление взгляда: {'-Y' if d.y < 0 else '+Y'} "
        f"(голова {hy:.2f}, корпус {ty:.2f})")
    return d


def separate_face(body, fwd):
    """Отделить лицо в свой объект по полосе высоты и направлению нормали."""
    me = body.data
    bpy.ops.object.select_all(action="DESELECT")
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(me)
    for f in bm.faces:
        f.select = False
    zs = [v.co.z for v in bm.verts]
    z1, z0 = max(zs), min(zs)
    H = z1 - z0
    hi, lo = z1 - H * HEAD_TOP, z1 - H * HEAD_BOT
    n = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if lo < c.z < hi and f.normal.dot(fwd) > FACE_COS:
            f.select = True
            n += 1
    bmesh.update_edit_mesh(me)
    log(f"граней в лице: {n} (полоса {HEAD_TOP}..{HEAD_BOT} роста, "
        f"косинус > {FACE_COS})")
    if n == 0:
        log("ВНИМАНИЕ: лицо не найдено — правь HEAD_TOP/HEAD_BOT или FACE_COS")
        bpy.ops.object.mode_set(mode="OBJECT")
        return None
    bpy.ops.mesh.separate(type="SELECTED")
    bpy.ops.object.mode_set(mode="OBJECT")
    face = [o for o in bpy.context.selected_objects if o is not body][-1]
    face.name = "face"
    return face


def paint(face):
    ink = flat_material("Ink", INK)
    light = flat_material("MaskLight", PAPER_FACE)
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        o.data.materials.clear()
        o.data.materials.append(light if o is face else ink)
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = BG


def render_turnaround(out_dir):
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    zs = [(o.matrix_world @ v.co).z for o in objs for v in o.data.vertices]
    xs = [(o.matrix_world @ v.co).x for o in objs for v in o.data.vertices]
    ys = [(o.matrix_world @ v.co).y for o in objs for v in o.data.vertices]
    cz = (max(zs) + min(zs)) / 2
    H = max(zs) - min(zs)
    pivot = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, cz))

    empty = bpy.data.objects.new("turn_pivot", None)
    bpy.context.collection.objects.link(empty)
    empty.location = pivot
    for o in objs:
        o.parent = empty
        o.matrix_parent_inverse = empty.matrix_world.inverted()

    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = H * 1.15
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (pivot.x, pivot.y - H * 4, cz)
    cam.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.camera = cam

    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    sc.render.resolution_x, sc.render.resolution_y = 420, 720
    sc.render.film_transparent = False
    os.makedirs(out_dir, exist_ok=True)
    for a in ANGLES:
        empty.rotation_euler.z = math.radians(a)
        sc.render.filepath = os.path.join(out_dir, f"turn_{a:03d}.png")
        bpy.ops.render.render(write_still=True)
        log("рендер", a, "°")
    return empty


def main():
    import_stl()
    body = split_loose()
    fwd = facing_direction(body)
    face = separate_face(body, fwd)
    paint(face)
    blend = bpy.data.filepath
    out = (os.path.join(os.path.dirname(blend), "freeman_parts_out")
           if blend else os.path.join(os.path.expanduser("~"), "freeman_parts_out"))
    render_turnaround(out)
    glb = os.path.join(out, "freeman_parts.glb")
    bpy.ops.export_scene.gltf(filepath=glb, export_format="GLB")
    log("ГОТОВО. Результат в:", out)
    log("Прислать обратно: freeman_parts.glb")
    log("Если лицо отделилось не там — правь HEAD_TOP/HEAD_BOT и прогони снова.")


main()
