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

ПЛАЩ — НЕ КОНУС. Первая версия строила его гладкой трубой, и это была самая
слабая часть болвана. Между тем настоящий контур у нас уже есть: `torso.svg`
обведён potrace с ПОДЛИННОГО кадра оригинала (`maxresdefault (4).jpg`) вместе с
бахромой подола и щетинистыми плечами — 303 точки. Его полуширина по 49
уровням высоты лежит здесь в `CLOAK_PROFILE`, и плащ строится лофтом по ней.
Форма плеч и раскрытие к груди теперь взяты с оригинала, а не придуманы.

ЧТО ВСЁ ЕЩЁ ПРОКСИ. Руки и ноги — прямые капсулы без сустава. Голова — яйцо, а
у оригинала маска деформируется под мимику. Достаточно, чтобы считать силуэт
под любым углом и сверять с нашим ригом; финальную форму держит плоский
рисунок в Rust-риге, эта модель — измерительный инструмент.
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


# ============================================================================
#  НАСТОЯЩИЙ КОНТУР ПЛАЩА, снятый с подлинного кадра
# ============================================================================
#
#  Это НЕ моя догадка о форме. `torso.svg` в риге обведён potrace с настоящего
#  кадра оригинала (`maxresdefault (4).jpg`) вместе с бахромой подола и
#  щетинистыми плечами — 303 точки. Здесь его полуширина снята по 49 уровням
#  высоты.
#
#  Формат: (доля высоты плаща сверху вниз, доля полуширины от максимальной).
#  Плечи наверху узкие (0.39), к груди контур раскрывается (~1.0), к подолу
#  чуть сужается (0.88) — это реальная форма, а не конус, которым болван
#  строился в первой версии.
CLOAK_PROFILE = [
    (0.0000, 0.3911),
    (0.0208, 0.5391),
    (0.0417, 0.6841),
    (0.0625, 0.7694),
    (0.0833, 0.8419),
    (0.1042, 0.9031),
    (0.1250, 0.9562),
    (0.1458, 1.0000),
    (0.1667, 1.0000),
    (0.1875, 0.9974),
    (0.2083, 0.9936),
    (0.2292, 0.9906),
    (0.2500, 0.9871),
    (0.2708, 0.9828),
    (0.2917, 0.9779),
    (0.3125, 0.9716),
    (0.3333, 0.9670),
    (0.3542, 0.9626),
    (0.3750, 0.9584),
    (0.3958, 0.9548),
    (0.4167, 0.9523),
    (0.4375, 0.9499),
    (0.4583, 0.9470),
    (0.4792, 0.9425),
    (0.5000, 0.9388),
    (0.5208, 0.9347),
    (0.5417, 0.9304),
    (0.5625, 0.9259),
    (0.5833, 0.9221),
    (0.6042, 0.9196),
    (0.6250, 0.9180),
    (0.6458, 0.9166),
    (0.6667, 0.9159),
    (0.6875, 0.9153),
    (0.7083, 0.9148),
    (0.7292, 0.9144),
    (0.7500, 0.9139),
    (0.7708, 0.9135),
    (0.7917, 0.9132),
    (0.8125, 0.9126),
    (0.8333, 0.9122),
    (0.8542, 0.9117),
    (0.8750, 0.9111),
    (0.8958, 0.9104),
    (0.9167, 0.9095),
    (0.9375, 0.9080),
    (0.9583, 0.9024),
    (0.9792, 0.8827),
    (1.0000, 0.8785)
]

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


def add_part(kind, name, radius, radius2, height, z_bottom, x=0.0,
             swing=0.0, segments=64):
    """Один примитив рига: сфера (голова) или конус (конечности).

    ГРАНЁНОСТЬ. Первая версия брала сегменты по умолчанию (32 у конуса), и на
    силуэте фаски были отлично видны — модель читалась угловатой. 64 сегмента
    плюс `shade_smooth` убирают это; для замера ширины разницы нет, а для
    суждения о форме — есть.

    НАКЛОН ВОКРУГ Y, А НЕ X. В первой версии руки наклонялись через
    `rotation_euler.x` — это наклон В ГЛУБИНУ кадра, невидимый в анфас.
    Руки от этого встали прямыми вертикальными брусками рядом с корпусом.
    В сторону наклоняет поворот вокруг Y.

    Сечение эллиптическое (`scale.y = DEPTH_K`) — та же формула проекции, что
    проверена в `proxy3d.py`: полуширина(θ) = sqrt(a²cos²θ + b²sin²θ).
    """
    if kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=radius, segments=segments, ring_count=segments // 2,
            location=(x, 0, z_bottom + height / 2))
    else:
        bpy.ops.mesh.primitive_cone_add(
            radius1=radius, radius2=radius2 if radius2 is not None else radius,
            depth=height, vertices=segments,
            location=(x, 0, z_bottom + height / 2))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale.y = DEPTH_K
    if swing:
        obj.rotation_euler.y = math.radians(swing)
    obj.data.materials.append(flat_black_material())
    bpy.ops.object.shade_smooth()
    return obj



def build_cloak(z_bottom, height):
    """Плащ ЛОФТОМ по настоящему контуру, а не конусом.

    Первая версия строила плащ конусом — гладкая труба, у которой нет ни
    щетинистых плеч, ни бахромы, ни настоящего раскрытия к груди. Между тем
    контур уже есть: `torso.svg` обведён potrace с подлинного кадра, и его
    полуширина по высоте лежит в `CLOAK_PROFILE`.

    Строим кольца по этим уровням и сшиваем в оболочку. Сечение эллиптическое:
    полуось по X из контура, по Z (глубина) — та же, умноженная на DEPTH_K.
    """
    import bmesh
    mesh = bpy.data.meshes.new("cloak")
    obj = bpy.data.objects.new("cloak", mesh)
    bpy.context.collection.objects.link(obj)

    SEG = 64                       # долек по кругу (32 давали видимые фаски)
    max_half = CLOAK_W / 2 * TOTAL_HEIGHT
    bm = bmesh.new()
    rings = []
    for t, wfrac in CLOAK_PROFILE:
        z = z_bottom + height * (1.0 - t)      # t=0 — верх плаща
        a = max_half * wfrac
        b = a * DEPTH_K
        ring = []
        for k in range(SEG):
            ang = 2.0 * math.pi * k / SEG
            ring.append(bm.verts.new((a * math.cos(ang), b * math.sin(ang), z)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(SEG):
            k2 = (k + 1) % SEG
            bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
    # заглушки сверху и снизу, иначе оболочка открыта и силуэт может «просвечивать»
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bm.to_mesh(mesh)
    bm.free()
    obj.data.materials.append(flat_black_material())
    return obj


def build_figure():
    z_shoulder = TOTAL_HEIGHT * (1 - HEAD_BOTTOM)
    z_hem = TOTAL_HEIGHT * (1 - HEM_Y)
    head_h = TOTAL_HEIGHT * HEAD_BOTTOM
    cloak_h = z_shoulder - z_hem

    # ГОЛОВА СТОИТ НА ПЛАЩЕ, А НЕ В НЁМ. Было `z_shoulder - head_h * 0.55`:
    # больше половины сферы уходило под плащ, и на силуэте головы не было видно
    # ВОВСЕ — округлая макушка фигуры оказывалась верхом плаща. Перекрываем
    # ровно подбородком.
    HEAD_SINK = 0.15
    head = add_part("sphere", "head", HEAD_W / 2 * TOTAL_HEIGHT, None, head_h,
                    z_shoulder - head_h * HEAD_SINK)
    head.scale.z = head_h / (HEAD_W * TOTAL_HEIGHT)

    cloak = build_cloak(z_hem, cloak_h)

    # НОГИ-НИТОЧКИ. Было 0.028 роста радиусом — 5.6% роста в диаметре, толстые
    # прямоугольники на силуэте. У оригинала ноги тоньше линии плаща в разы.
    leg_r = 0.009 * TOTAL_HEIGHT
    leg_off = CLOAK_W * TOTAL_HEIGHT * 0.13
    leg_l = add_part("cone", "leg_l", leg_r, leg_r * 0.75, z_hem, 0.0, x=-leg_off)
    leg_r_ = add_part("cone", "leg_r", leg_r, leg_r * 0.75, z_hem, 0.0, x=leg_off)

    # РУКИ ПРИМЫКАЮТ И РАСХОДЯТСЯ. Крепим у линии плеч (0.234 роста — замер по
    # этой же модели), сажаем ВНУТРЬ габарита плаща, чтобы не висели отдельно,
    # и разводим поворотом вокруг Y.
    z_arm_top = TOTAL_HEIGHT * (1 - 0.234)
    arm_r = 0.011 * TOTAL_HEIGHT
    arm_len = 0.38 * TOTAL_HEIGHT
    arm_off = CLOAK_W / 2 * TOTAL_HEIGHT * 0.88
    arm_l = add_part("cone", "arm_l", arm_r, arm_r * 0.55, arm_len,
                     z_arm_top - arm_len, x=-arm_off, swing=-7)
    arm_rr = add_part("cone", "arm_r", arm_r, arm_r * 0.55, arm_len,
                      z_arm_top - arm_len, x=arm_off, swing=7)

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
