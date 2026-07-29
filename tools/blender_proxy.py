"""
blender_proxy.py — БОЛВАН В BLENDER: та же геометрия, что в `proxy3d.py`,
но настоящая 3D-примитивная модель вместо приближения через эллипс в Python.

ЗАПУСК. Это НЕ обычный скрипт репозитория (`python3 tools/...`) — он выполняется
ВНУТРИ Blender, у которого свой Python с модулем `bpy`. Здесь его нет
(проверено: ни бинарника, ни `import bpy`), поэтому строить и рендерить модель
может только пользователь на своей машине:

    1. Поставить Blender (бесплатно, blender.org) — один раз.
    2. Открыть Blender → вкладка сверху «Scripting».
    3. Открыть этот файл (Text → Open) или вставить его текст в редактор.
    4. Нажать ▶ Run Script (или Alt+P).

Скрипт сам: строит фигуру из примитивов, рендерит шесть силуэтов под нашими
ракурсами (0/22/45/90/135/180 — те же углы, что в `turnaround.py`) и
экспортирует .glb. Результат появится рядом с сохранённым .blend-файлом (если
файл не сохранён — в `~/freeman_proxy_out/`, путь печатается в консоли
Blender, Window → Toggle System Console на Windows, на Linux/Mac видно в
терминале, из которого запущен Blender).

ЧТО ПРИСЛАТЬ ОБРАТНО. Файл `freeman_proxy.glb` — этого достаточно. Я читаю
его без Blender, чистым Python-парсером glTF, и строю точную ортографическую
проекцию под любой угол — уже не приближением через эллипс, а настоящей
геометрией. PNG-рендеры — бонус, чтобы вы сами сверили форму на глаз ДО того,
как слать файл.

ИЗМЕРЕННЫЕ ПРОПОРЦИИ (доли полного роста фигуры, крона=0, стопы=1). Источники
и надёжность указаны у каждого числа — это НЕ придуманные значения, это то,
что намерено `tools/original_ref.py` (по видео оригинала, 35 кадров с целой
фигурой) и `tools/sheet_ref.py` (по присланному листу разворотов, фигуры
анфас/спина, усреднено по 3 копиям каждая).

ЭТО ПРОКСИ, А НЕ ФИНАЛ. Плащ — конус (у настоящего рисунка подол чуть уже
плеч и рваный край, здесь — гладкий цилиндр). Руки и ноги — прямые капсулы без
сустава. Достаточно, чтобы посчитать силуэт под любым углом и сверить с нашим
ригом; для финальной формы Rust-риг сохраняет плоский рисунок, эта модель
только измерительный инструмент.
"""

import bpy
import math
import os

# ============================================================================
#  ИЗМЕРЕННЫЕ ЧИСЛА
# ============================================================================

TOTAL_HEIGHT = 2.0          # рост фигуры в единицах Blender (масштаб условный)

# Голова: где кончается голова и начинается плащ (доля от роста, от макушки).
# Видео (мaска-ббокс, оригинал): 0.287. Лист (плечо — где ширина силуэта
# скачком растёт): 0.266. Числа независимы и близки — берём среднее.
HEAD_BOTTOM = 0.276

# Ширина головы (доля роста). Видео: 0.202. Лист (маска anfas x3): 0.157.
# Расхождение больше, чем у высоты — лист рисует голову уже видео. Среднее,
# ближе к видео как к настоящему оригиналу, а не AI-реконструкции.
HEAD_W = 0.185

# Подол: где кончается плащ / начинаются ноги (доля роста). Только с листа —
# видео эту величину дать надёжно не смогло (спутывало плащ с ногами).
HEM_Y = 0.786

# Ширина плаща (доля роста), с листа, три фигуры-анфас, среднее.
CLOAK_W = 0.366

# ГЛУБИНА / ШИРИНА — САМОЕ НЕНАДЁЖНОЕ ЧИСЛО ЗДЕСЬ. Ни видео (профиль путался
# с приседом), ни лист (профиль там — согнутая поза со спиральной рукой, не
# нейтральная стойка) не дали годного прямого замера. Взято из подгонки
# эллиптической модели под наш ЖЕ разворот (tools/proxy3d.py, k=0.658) — то
# есть это не независимый источник, а лучшее из того, что есть. ПЕРВЫЙ
# кандидат на замену, если появится чистый стоячий профиль.
DEPTH_K = 0.658

ANGLES = [0, 22, 45, 90, 135, 180]   # тот же ряд, что в turnaround.py

# ============================================================================
#  СЦЕНА
# ============================================================================

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def flat_black_material():
    mat = bpy.data.materials.get("FreemanInk") or bpy.data.materials.new("FreemanInk")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (0.03, 0.03, 0.03, 1.0)
    out = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


def set_paper_background():
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.86, 0.86, 0.84, 1.0)
        bg.inputs["Strength"].default_value = 1.0


def add_part(kind, name, radius, radius2, height, z_bottom, x=0.0, tilt=0.0):
    """Один примитив рига: сфера (голова) или цилиндр/конус (плащ, конечности).

    Сечение делаем ЭЛЛИПТИЧЕСКИМ (scale по Y после постройки) — та же формула
    проекции, что уже проверена в `proxy3d.py`: полуширина(θ) = sqrt(a²cos²θ +
    b²sin²θ), a — по X, b = a·DEPTH_K — по Y (глубина).
    """
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=(x, 0, z_bottom + height / 2))
    else:
        bpy.ops.mesh.primitive_cone_add(radius1=radius, radius2=radius2 if radius2 is not None else radius,
                                        depth=height, location=(x, 0, z_bottom + height / 2))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale.y = DEPTH_K
    if tilt:
        obj.rotation_euler.x = math.radians(tilt)
    obj.data.materials.append(flat_black_material())
    return obj


def build_figure():
    z_shoulder = TOTAL_HEIGHT * (1 - HEAD_BOTTOM)
    z_hem = TOTAL_HEIGHT * (1 - HEM_Y)
    head_h = TOTAL_HEIGHT * HEAD_BOTTOM
    cloak_h = z_shoulder - z_hem

    head = add_part("sphere", "head", HEAD_W / 2 * TOTAL_HEIGHT, None, head_h,
                    z_shoulder - head_h * 0.55)
    head.scale.z = head_h / (HEAD_W * TOTAL_HEIGHT)

    cloak = add_part("cone", "cloak", CLOAK_W / 2 * TOTAL_HEIGHT, CLOAK_W / 2 * TOTAL_HEIGHT * 0.92,
                     cloak_h, z_hem)

    leg_r = 0.028 * TOTAL_HEIGHT
    leg_off = CLOAK_W * TOTAL_HEIGHT * 0.16
    leg_l = add_part("cone", "leg_l", leg_r, leg_r, z_hem, 0.0, x=-leg_off)
    leg_r_ = add_part("cone", "leg_r", leg_r, leg_r, z_hem, 0.0, x=leg_off)

    arm_r = 0.025 * TOTAL_HEIGHT
    arm_len = 0.34 * TOTAL_HEIGHT
    arm_off = CLOAK_W / 2 * TOTAL_HEIGHT + arm_r * 1.1
    arm_l = add_part("cone", "arm_l", arm_r, arm_r * 0.8, arm_len,
                     z_shoulder - arm_len, x=-arm_off, tilt=8)
    arm_rr = add_part("cone", "arm_r", arm_r, arm_r * 0.8, arm_len,
                      z_shoulder - arm_len, x=arm_off, tilt=-8)

    parts = [head, cloak, leg_l, leg_r_, arm_l, arm_rr]
    empty = bpy.data.objects.new("freeman_proxy", None)
    bpy.context.collection.objects.link(empty)
    for p in parts:
        p.parent = empty
    return empty


def setup_camera_and_render(out_dir):
    cam_data = bpy.data.cameras.new("proxy_cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = TOTAL_HEIGHT * 1.3
    cam = bpy.data.objects.new("proxy_cam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (0, -6, TOTAL_HEIGHT * 0.5)
    cam.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x = 640
    scene.render.resolution_y = 720
    scene.render.film_transparent = False
    return cam


def render_turnaround(empty, out_dir):
    scene = bpy.context.scene
    for ang in ANGLES:
        empty.rotation_euler.z = math.radians(ang)
        scene.render.filepath = os.path.join(out_dir, f"proxy_{ang:03d}.png")
        bpy.ops.render.render(write_still=True)
        print(f"  рендер {ang}° -> {scene.render.filepath}")
    empty.rotation_euler.z = 0.0


def export_glb(out_dir):
    path = os.path.join(out_dir, "freeman_proxy.glb")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)
    print(f"  glTF -> {path}")
    return path


def main():
    blend_path = bpy.data.filepath
    out_dir = (os.path.join(os.path.dirname(blend_path), "freeman_proxy_out")
               if blend_path else os.path.expanduser("~/freeman_proxy_out"))
    os.makedirs(out_dir, exist_ok=True)

    clear_scene()
    set_paper_background()
    empty = build_figure()
    setup_camera_and_render(out_dir)
    render_turnaround(empty, out_dir)
    glb = export_glb(out_dir)

    print("\n=== ГОТОВО ===")
    print(f"Папка с результатом: {out_dir}")
    print(f"Пришлите файл: {glb}")
    print("(PNG рядом — для сверки на глаз перед отправкой)\n")


if __name__ == "__main__":
    main()
