//! AnimDSL — CLI entry point.
//!
//! Usage:
//!   animdsl render scene.anim -o output.mp4
//!   animdsl render scene.anim --png-dir ./frames
//!   animdsl check scene.anim

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use anyhow::Result;
use clap::{Parser, Subcommand};

use animdsl::assets::AssetRegistry;
use animdsl::ast::{LetKind, SceneStatement, TopLevelItem};
use animdsl::errors::AnimError;
use animdsl::renderer;
use animdsl::scene::{resolve_scene, EntityKind, RenderConfig};
use animdsl::timeline;
use animdsl::video;

#[derive(Parser)]
#[command(
    name = "animdsl",
    version,
    about = "A DSL for generating 2D animated movie scenes"
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Render a .anim file to video or image sequence.
    Render {
        /// Path to the .anim source file.
        input: PathBuf,

        /// Output video file path (e.g., output.mp4).
        #[arg(short, long)]
        output: Option<PathBuf>,

        /// Output directory for PNG frame sequence (alternative to video).
        #[arg(long)]
        png_dir: Option<PathBuf>,

        /// Override FPS.
        #[arg(long)]
        fps: Option<u32>,

        /// Override width.
        #[arg(long)]
        width: Option<u32>,

        /// Override height.
        #[arg(long)]
        height: Option<u32>,
    },

    /// Parse and validate a .anim file without rendering.
    Check {
        /// Path to the .anim source file.
        input: PathBuf,
    },

    /// Print JSON timing of speech blocks (lips/speaks) in absolute video time.
    Timing {
        /// Path to the .anim source file.
        input: PathBuf,
    },

    /// Parse a .anim file and dump the AST as JSON.
    Dump {
        /// Path to the .anim source file.
        input: PathBuf,
    },
}

/// Сколько раз сработал перехват паники resvg на фильтре смещения.
static INK_FALLBACKS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);

/// Гасит ШТАТНУЮ панику resvg, которую движок уже ловит сам.
///
/// `render_bone_part` оборачивает `resvg::render` в `catch_unwind`: у
/// `feDisplacementMap` в resvg 0.44 есть size-assertion, которая срабатывает на
/// некоторых размерах растра, и деталь просто дорисовывается без ink-фильтра.
/// Ошибки в этом нет — силуэт верный, дрожь контура всё равно даёт пост-процесс
/// `apply_line_boil`.
///
/// Но штатный хук паники печатал при этом полный backtrace с `animdsl::main` в
/// стеке. В логе прогона это выглядит как падение рендера: ровно на этом я и
/// потерял час, бисектя сцену, которая на самом деле собралась целиком. Теперь
/// известная паника не печатается вовсе, а в конце прогона выводится честная
/// строка «сколько раз пришлось снять фильтр». Любая ДРУГАЯ паника печатается
/// как раньше — глушим по тексту сообщения, а не всё подряд.
fn install_quiet_ink_panic_hook() {
    let prev = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |info| {
        let msg = info
            .payload()
            .downcast_ref::<&str>()
            .map(|s| s.to_string())
            .or_else(|| info.payload().downcast_ref::<String>().cloned())
            .unwrap_or_default();
        let known = msg.contains("src.width == map.width")
            || msg.contains("src.height == map.height");
        if known {
            INK_FALLBACKS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            return;
        }
        prev(info);
    }));
}

fn report_ink_fallbacks() {
    let n = INK_FALLBACKS.load(std::sync::atomic::Ordering::Relaxed);
    if n > 0 {
        eprintln!(
            "  [ink] {n} раз(а) деталь дорисована без SVG-фильтра: resvg не смог \
             применить feDisplacementMap на этом размере растра. Силуэт верный, \
             дрожь контура даёт пост-процесс кадра — на картинке не сказывается."
        );
    }
}

fn main() -> Result<()> {
    env_logger::init();
    install_quiet_ink_panic_hook();
    let cli = Cli::parse();

    match cli.command {
        Commands::Render {
            input,
            output,
            png_dir,
            fps,
            width,
            height,
        } => {
            let output = output.unwrap_or_else(|| input.with_extension("mp4"));
            cmd_render(&input, &output, png_dir.as_deref(), fps, width, height)?;
        }
        Commands::Check { input } => {
            cmd_check(&input)?;
        }
        Commands::Timing { input } => {
            cmd_timing(&input)?;
        }
        Commands::Dump { input } => {
            cmd_dump(&input)?;
        }
    }

    report_ink_fallbacks();
    Ok(())
}

fn cmd_render(
    input: &Path,
    output: &Path,
    png_dir: Option<&Path>,
    fps_override: Option<u32>,
    width_override: Option<u32>,
    height_override: Option<u32>,
) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let base_dir = input
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf();

    // Parse.
    let program = animdsl::parser::parse(&source)?;

    // Extract config.
    let mut config = RenderConfig::default();
    for item in &program.items {
        if let TopLevelItem::Config(cfg) = item {
            config = RenderConfig::from_config_block(cfg);
        }
    }

    // Apply CLI overrides.
    if let Some(fps) = fps_override {
        config.fps = fps;
    }
    if let Some(w) = width_override {
        config.width = w;
    }
    if let Some(h) = height_override {
        config.height = h;
    }

    // Load assets.
    let mut assets = AssetRegistry::new();
    let imports: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Import(imp) = item {
                Some(imp.clone())
            } else {
                None
            }
        })
        .collect();
    assets.load_imports(&imports, &base_dir)?;

    // Load inline (`let name = prop("label", "path") at ...`) props declared in
    // any scene. Without this the prop's asset is never registered and the prop
    // never renders. Scan all scenes (including nested together/do blocks).
    for item in &program.items {
        if let TopLevelItem::Scene(scene) = item {
            load_let_props(&scene.body, &mut assets, &base_dir)?;
        }
    }

    // Extract custom pose definitions.
    let mut custom_poses: HashMap<String, Vec<(String, f64)>> = HashMap::new();
    for item in &program.items {
        if let TopLevelItem::PoseDef(pose_def) = item {
            let fields: Vec<(String, f64)> = pose_def
                .fields
                .iter()
                .map(|f| (f.name.clone(), f.value))
                .collect();
            custom_poses.insert(pose_def.name.clone(), fields);
        }
    }

    // Process each scene.
    let scenes: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Scene(scene) = item {
                Some(scene)
            } else {
                None
            }
        })
        .collect();

    if scenes.is_empty() {
        return Err(AnimError::Scene("no scenes found in source file".into()).into());
    }

    let mut all_frames = Vec::new();

    for scene_decl in &scenes {
        log::info!("Processing scene: {}", scene_decl.name);

        let resolved = resolve_scene(scene_decl, &assets)?;
        let compiled_timeline = timeline::compile_full(
            &resolved,
            &assets.kartas(),
            resolved
                .set_name
                .as_deref()
                .and_then(|n| assets.sets.get(n))
                .and_then(|s| s.surfaces.as_ref())
                .map(|s| s.floor),
        )?;

        // Check for character overlaps before rendering.
        let character_names: Vec<String> = resolved
            .entities
            .iter()
            .filter(|(_, e)| e.kind == EntityKind::Character)
            .map(|(name, _)| name.clone())
            .collect();
        timeline::check_overlaps(&compiled_timeline, &resolved.entities, &character_names)?;

        let frames = renderer::render_scene(
            &config,
            &compiled_timeline,
            &resolved.entities,
            resolved.set_name.as_deref(),
            &assets,
            &custom_poses,
        )?;
        all_frames.extend(frames);
    }

    // Freeman-style black & white ("ink") post-process.
    if config.monochrome {
        for frame in &mut all_frames {
            apply_monochrome(&mut frame.data, config.mono_contrast as f32);
        }
    }

    // Hand-drawn line boil: the ink outline resettles every held drawing-frame,
    // as if redrawn — the single biggest gap between a rigged puppet and real
    // frame-by-frame animation. Runs on the post-monochrome near-binary image,
    // so "edge" simply means a black/white transition.
    if config.line_boil > 0.0 {
        for (i, frame) in all_frames.iter_mut().enumerate() {
            apply_line_boil(
                &mut frame.data,
                frame.width,
                frame.height,
                i as u32,
                config.on_twos,
                config.line_boil as f32,
            );
        }
    }

    // Aged-film post: vignette + grain (the last layer of the Freeman look).
    if config.film_grain > 0.0 || config.vignette > 0.0 {
        for (i, frame) in all_frames.iter_mut().enumerate() {
            apply_film(
                &mut frame.data,
                frame.width,
                frame.height,
                // Зерно ДЕРЖИТСЯ вместе с рисунком (on-twos), а не пересчитывается
                // каждый кадр: иначе шум «кипит» на 24fps поверх анимации на 12
                // и читается как дёрганье персонажа. Замер: film-grain 0.30 даёт
                // покадровую разницу 4.39 против 1.98 без зерна — больше половины
                // всей дрожи кадра приходило именно отсюда.
                (i as u32) / config.on_twos.max(1),
                config.film_grain as f32,
                config.vignette as f32,
            );
        }
    }

    // ПЛЁНОЧНЫЕ МЕЛОЧИ (MELOCHI.md, группа А): мерцание экспозиции, гуляние
    // кадра в тракте, царапины, пылинки. Дают ощущение «снято», а не
    // «сгенерировано». Всё детерминировано от номера кадра — golden воспроизводим.
    if config.film_flicker > 0.0 || config.gate_weave > 0.0
        || config.film_scratch > 0.0 || config.film_dust > 0.0
    {
        for (i, frame) in all_frames.iter_mut().enumerate() {
            apply_filmstock(
                &mut frame.data,
                frame.width,
                frame.height,
                i as u32,
                config.film_flicker as f32,
                config.gate_weave as f32,
                config.film_scratch as f32,
                config.film_dust as f32,
            );
        }
    }

    // Drifting particles (snow/ash) — Freeman's atmospheric layer.
    if config.snow > 0.0 {
        for (i, frame) in all_frames.iter_mut().enumerate() {
            apply_snow(
                &mut frame.data,
                frame.width,
                frame.height,
                i as u32,
                config.snow as f32,
            );
        }
    }

    // Output.
    if let Some(dir) = png_dir {
        video::encode_png_sequence(&all_frames, dir)?;
    }

    video::encode_video(&all_frames, output, config.fps)?;

    println!(
        "Rendered {} scene(s), {} frames -> {}",
        scenes.len(),
        all_frames.len(),
        output.display(),
    );

    Ok(())
}

/// Convert an RGBA frame buffer to a high-contrast black & white "ink" image
/// in place. Alpha is preserved. This is what gives the Freeman-style lecture
/// videos their stark hand-inked, mostly-monochrome look.
fn apply_monochrome(data: &mut [u8], contrast: f32) {
    // Contrast strength around mid-grey. ~1.1 keeps gradient shading (fabric
    // sheen, facial form); high values (2–4) blow out to a stark 2-tone
    // silhouette — the flat-ink "Mr. Freeman" look.
    let contrast = if contrast > 0.0 { contrast } else { 1.12 };
    for px in data.chunks_exact_mut(4) {
        let (r, g, b) = (px[0] as f32, px[1] as f32, px[2] as f32);
        // Цветное пятно (фишка студии): насыщенный пиксель ПЕРЕЖИВАЕТ
        // монохромный проход и остаётся единственным цветом в ч/б кадре.
        // Раньше правило пропускало только КРАСНОЕ, и цветной плакат на стене —
        // ровно та деталь, ради которой приём и заводился, — уходил в серое.
        // Теперь спасается любой достаточно насыщенный цвет, а не один оттенок.
        let mx = r.max(g).max(b);
        let mn = r.min(g).min(b);
        if mx - mn > 55.0 && mx > 90.0 {
            // Подтягиваем насыщенность и слегка притемняем: цвет должен
            // БИТЬ на фоне туши, а не выглядеть выцветшей фотографией.
            let mid = (r + g + b) / 3.0;
            let boost = |c: f32| ((mid + (c - mid) * 1.35) * 0.92).clamp(0.0, 255.0);
            px[0] = boost(r) as u8;
            px[1] = boost(g) as u8;
            px[2] = boost(b) as u8;
            continue;
        }
        // Rec. 601 luma.
        let luma = 0.299 * r + 0.587 * g + 0.114 * b;
        // Apply an S-curve style contrast around 128.
        let adjusted = ((luma - 128.0) * contrast + 128.0).clamp(0.0, 255.0);
        let v = adjusted as u8;
        px[0] = v;
        px[1] = v;
        px[2] = v;
        // px[3] (alpha) untouched.
    }
}

/// Register the asset for every inline `let name = prop("label", "path")` in a
/// scene body (recursing into together/do blocks), so the prop actually renders.
fn load_let_props(
    stmts: &[SceneStatement],
    assets: &mut AssetRegistry,
    base_dir: &Path,
) -> Result<()> {
    for stmt in stmts {
        match stmt {
            SceneStatement::Let(let_stmt) => match &let_stmt.kind {
                LetKind::Prop { label, path, .. } => {
                    if !assets.props.contains_key(&let_stmt.name) {
                        assets.load_dynamic_prop(&let_stmt.name, label, path, base_dir)?;
                    }
                }
                LetKind::Text { content, size, .. } => {
                    if !assets.props.contains_key(&let_stmt.name) {
                        assets.register_text_prop(
                            &let_stmt.name,
                            content,
                            size.unwrap_or(120.0),
                        )?;
                    }
                }
            },
            SceneStatement::Together(inner) | SceneStatement::Do(inner) => {
                load_let_props(inner, assets, base_dir)?;
            }
            _ => {}
        }
    }
    Ok(())
}

/// Drifting particles (snow / ash specks) — a light atmospheric layer. Each
/// particle has a fixed column and fall speed derived from its id, so motion is
/// smooth and fully deterministic (reproducible renders). Density scales the
/// particle count. Specks are drawn as soft light dots blended over the frame.
fn apply_snow(data: &mut [u8], width: u32, height: u32, frame: u32, density: f32) {
    let w = width as i64;
    let h = height as i64;
    let count = ((w * h) as f32 * 0.00008 * density).round() as u32;
    let t = frame as f32;
    for id in 0..count {
        let mut n = (id as u64).wrapping_mul(0x9E3779B97F4A7C15);
        n ^= n >> 29;
        let hx = (n & 0xFFFF) as f32 / 65535.0;
        let hs = ((n >> 16) & 0xFF) as f32 / 255.0; // скорость/глубина
        let hd = ((n >> 24) & 0xFF) as f32 / 255.0; // фаза покачивания
        let speed = 0.5 + hs * 1.6;
        let sway = ((t * 0.045 + hd * 6.28).sin()) * 8.0;
        let x = (hx * w as f32 + sway).rem_euclid(w as f32);
        let y = (t * speed + hd * h as f32).rem_euclid(h as f32);
        // Крупные мягкие хлопья: радиус 1.5–4 px, ближние ярче и больше
        let r = 1.5 + hs * 2.8;
        let bright = 190.0 + hs * 60.0;
        let ir = r.ceil() as i64;
        for dy in -ir..=ir {
            for dx in -ir..=ir {
                let px = x as i64 + dx;
                let py = y as i64 + dy;
                if px < 0 || px >= w || py < 0 || py >= h { continue; }
                let d2 = (dx as f32 - (x - x.floor())).powi(2) + (dy as f32 - (y - y.floor())).powi(2);
                let fall = (1.0 - (d2.sqrt() / r)).clamp(0.0, 1.0);
                if fall <= 0.0 { continue; }
                let a = 0.75 * fall * fall; // мягкая кромка
                let idx = ((py * w + px) * 4) as usize;
                for c in 0..3 {
                    let base = data[idx + c] as f32;
                    data[idx + c] = (base * (1.0 - a) + bright * a).min(255.0) as u8;
                }
            }
        }
    }
}

/// Hand-drawn "line boil": every held drawing-frame, ink OUTLINE pixels
/// resettle to a new position along a smooth per-stroke noise field — as if
/// the line were redrawn — while flat fills and background stay perfectly
/// solid (only real black/white transitions move). This is the mechanism a
/// pose-interpolated rig structurally lacks: two holds of the "same" drawing
/// are never pixel-identical in hand animation. Deterministic per
/// (pixel, boil_step) so renders stay reproducible.
fn apply_line_boil(data: &mut [u8], width: u32, height: u32, frame: u32, on_twos: u32, strength: f32) {
    if strength <= 0.0 {
        return;
    }
    let w = width as i64;
    let h = height as i64;
    let stride = (w * 4) as usize;
    // Resettle once per held drawing-frame, not every rendered frame — the
    // wobble reads as re-inking on the same cadence as the pose itself holds,
    // not as video noise crawling underneath a static pose.
    let hold = on_twos.max(1);
    let boil_step = frame / hold;

    let src = data.to_vec();
    let luma = |idx: usize| -> f32 {
        0.299 * src[idx] as f32 + 0.587 * src[idx + 1] as f32 + 0.114 * src[idx + 2] as f32
    };

    // Coherent low-frequency value noise (bilinear-interpolated hash grid) so
    // neighbouring pixels along a stroke wobble together as one line, not as
    // per-pixel static.
    let cell = 22.0_f32;
    let hash2 = |cx: i64, cy: i64, salt: u32| -> f32 {
        let mut n = (cx as u32)
            .wrapping_mul(374761393)
            .wrapping_add((cy as u32).wrapping_mul(668265263))
            .wrapping_add(boil_step.wrapping_mul(2246822519))
            .wrapping_add(salt.wrapping_mul(3266489917));
        n ^= n >> 13;
        n = n.wrapping_mul(1274126177);
        n ^= n >> 16;
        (n as f32 / u32::MAX as f32) * 2.0 - 1.0
    };
    let noise_at = |x: f32, y: f32, salt: u32| -> f32 {
        let gx = x / cell;
        let gy = y / cell;
        let x0 = gx.floor() as i64;
        let y0 = gy.floor() as i64;
        let fx = gx - x0 as f32;
        let fy = gy - y0 as f32;
        let sx = fx * fx * (3.0 - 2.0 * fx);
        let sy = fy * fy * (3.0 - 2.0 * fy);
        let n00 = hash2(x0, y0, salt);
        let n10 = hash2(x0 + 1, y0, salt);
        let n01 = hash2(x0, y0 + 1, salt);
        let n11 = hash2(x0 + 1, y0 + 1, salt);
        let nx0 = n00 * (1.0 - sx) + n10 * sx;
        let nx1 = n01 * (1.0 - sx) + n11 * sx;
        nx0 * (1.0 - sy) + nx1 * sy
    };

    for y in 0..h {
        for x in 0..w {
            let idx = (y as usize) * stride + (x as usize) * 4;
            let l0 = luma(idx);
            let lr = if x + 1 < w { luma(idx + 4) } else { l0 };
            let ld = if y + 1 < h { luma(idx + stride) } else { l0 };
            let edge = (l0 - lr).abs().max((l0 - ld).abs());
            if edge < 40.0 {
                continue; // flat fill or background — stays rock solid
            }
            let dx = noise_at(x as f32, y as f32, 1) * strength;
            let dy = noise_at(x as f32, y as f32, 2) * strength;
            let sx = (x as f32 + dx).round() as i64;
            let sy = (y as f32 + dy).round() as i64;
            if sx < 0 || sx >= w || sy < 0 || sy >= h {
                continue;
            }
            let sidx = (sy as usize) * stride + (sx as usize) * 4;
            data[idx] = src[sidx];
            data[idx + 1] = src[sidx + 1];
            data[idx + 2] = src[sidx + 2];
            data[idx + 3] = src[sidx + 3];
        }
    }
}

/// Плёночные мелочи: то, из-за чего кадр выглядит снятым на плёнку, а не
/// отрендеренным. Четыре независимых эффекта, каждый opt-in:
///   * `flicker`  — экспозиция плавает покадрово (главный признак плёнки);
///   * `weave`    — весь кадр гуляет на доли пикселя (лентопротяжный тракт);
///   * `scratch`  — редкие вертикальные царапины, живут несколько кадров;
///   * `dust`     — точки-пылинки и ворсинки, каждый кадр новые.
/// Всё детерминировано от номера кадра (без RNG) — рендер воспроизводим,
/// golden-diff не ломается.
fn apply_filmstock(
    data: &mut [u8], width: u32, height: u32, frame: u32,
    flicker: f32, weave: f32, scratch: f32, dust: f32,
) {
    let w = width as i64;
    let h = height as i64;
    // дешёвый детерминированный хэш
    let hash = |a: i64, b: i64| -> u32 {
        let mut x = (a.wrapping_mul(73_856_093) ^ b.wrapping_mul(19_349_663)) as u32;
        x ^= x >> 13; x = x.wrapping_mul(0x85eb_ca6b); x ^= x >> 16; x
    };
    let f = frame as i64;

    // --- мерцание экспозиции: две несинхронные волны + шум кадра ----------
    if flicker > 0.0 {
        let t = frame as f32;
        let wave = (t * 0.9).sin() * 0.6 + (t * 2.7).sin() * 0.4;
        let jit = (hash(f, 7) % 1000) as f32 / 1000.0 - 0.5;
        let k = 1.0 + flicker * (wave * 0.5 + jit * 0.5);
        for px in data.chunks_exact_mut(4) {
            for c in 0..3 {
                px[c] = ((px[c] as f32 * k).clamp(0.0, 255.0)) as u8;
            }
        }
    }

    // --- гуляние кадра: сдвиг на 0..~2px, низкая частота -------------------
    if weave > 0.0 {
        let t = frame as f32;
        let dx = ((t * 0.37).sin() * 1.6 + (t * 1.13).sin() * 0.5) * weave;
        let dy = ((t * 0.29).cos() * 1.2 + (t * 0.91).cos() * 0.4) * weave;
        let (dx, dy) = (dx.round() as i64, dy.round() as i64);
        if dx != 0 || dy != 0 {
            let src = data.to_vec();
            for y in 0..h {
                let sy = (y + dy).clamp(0, h - 1);
                for x in 0..w {
                    let sx = (x + dx).clamp(0, w - 1);
                    let di = ((y * w + x) * 4) as usize;
                    let si = ((sy * w + sx) * 4) as usize;
                    data[di..di + 4].copy_from_slice(&src[si..si + 4]);
                }
            }
        }
    }

    // --- царапины: вертикальные линии, живут 3..15 кадров ------------------
    if scratch > 0.0 {
        let life = 9i64;
        let era = f / life;                 // «эпоха» — набор царапин
        let n = (scratch * 2.5).ceil() as i64;
        for s in 0..n {
            let hs = hash(era, s * 31 + 5);
            if (hs % 100) as f32 > scratch * 100.0 { continue; }  // редкость
            let sx = (hs / 100) as i64 % w;
            let bright = (hs % 2) == 0;      // светлая или тёмная царапина
            let y0 = (hash(era, s * 17) as i64) % h;
            let len = h / 2 + (hash(era, s * 41) as i64) % (h / 2);
            for y in y0..(y0 + len).min(h) {
                let i = ((y * w + sx) * 4) as usize;
                for c in 0..3 {
                    let v = data[i + c] as i32;
                    data[i + c] = if bright { (v + 60).min(255) as u8 }
                                  else { (v - 55).max(0) as u8 };
                }
            }
        }
    }

    // --- пылинки/ворс: точки, каждый кадр новые ---------------------------
    if dust > 0.0 {
        let n = (dust * 6.0).ceil() as i64;
        for d in 0..n {
            let hd = hash(f, d * 97 + 11);
            let px = (hd as i64) % w;
            let py = ((hd / 7) as i64) % h;
            let dark = (hd % 3) != 0;
            let r = 1 + ((hd / 13) % 2) as i64;   // 1..2 px
            for yy in (py - r).max(0)..(py + r).min(h - 1) {
                for xx in (px - r).max(0)..(px + r).min(w - 1) {
                    let i = ((yy * w + xx) * 4) as usize;
                    for c in 0..3 {
                        let v = data[i + c] as i32;
                        data[i + c] = if dark { (v - 90).max(0) as u8 }
                                      else { (v + 70).min(255) as u8 };
                    }
                }
            }
        }
    }
}

/// Aged-film post-process: a soft vignette plus per-pixel, per-frame grain —
/// the "shot on old stock" layer that finishes the Mr. Freeman look. Grain is
/// deterministic (hash of x,y,frame) so renders are reproducible.
fn apply_film(data: &mut [u8], width: u32, height: u32, frame: u32, grain: f32, vignette: f32) {
    let w = width as i64;
    let h = height as i64;
    let cx = w as f32 * 0.5;
    let cy = h as f32 * 0.5;
    let max_d2 = cx * cx + cy * cy;
    let grain_amp = grain * 46.0;
    for y in 0..h {
        for x in 0..w {
            let idx = ((y * w + x) * 4) as usize;
            let mut r = data[idx] as f32;
            let mut g = data[idx + 1] as f32;
            let mut b = data[idx + 2] as f32;

            if vignette > 0.0 {
                let dx = x as f32 - cx;
                let dy = y as f32 - cy;
                let d2 = (dx * dx + dy * dy) / max_d2;
                let f = 1.0 - vignette * d2 * d2; // soft falloff, strong at corners
                r *= f;
                g *= f;
                b *= f;
            }

            if grain > 0.0 {
                // cheap integer hash → [-1, 1]
                let mut hsh = (x as u32)
                    .wrapping_mul(374761393)
                    .wrapping_add((y as u32).wrapping_mul(668265263))
                    .wrapping_add(frame.wrapping_mul(2246822519));
                hsh ^= hsh >> 13;
                hsh = hsh.wrapping_mul(1274126177);
                hsh ^= hsh >> 16;
                let n = (hsh as f32 / u32::MAX as f32) * 2.0 - 1.0;
                let gg = n * grain_amp;
                r += gg;
                g += gg;
                b += gg;
            }

            data[idx] = r.clamp(0.0, 255.0) as u8;
            data[idx + 1] = g.clamp(0.0, 255.0) as u8;
            data[idx + 2] = b.clamp(0.0, 255.0) as u8;
        }
    }
}

fn cmd_check(input: &Path) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let base_dir = input
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf();

    let program = animdsl::parser::parse(&source)?;

    let mut n_imports = 0;
    let mut n_scenes = 0;
    let mut has_config = false;

    for item in &program.items {
        match item {
            TopLevelItem::Import(_) => n_imports += 1,
            TopLevelItem::Config(_) => has_config = true,
            TopLevelItem::Scene(_) => n_scenes += 1,
            TopLevelItem::PoseDef(_) => {}
        }
    }

    // Load assets so we can resolve scenes and check overlaps.
    let mut assets = AssetRegistry::new();
    let imports: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Import(imp) = item {
                Some(imp.clone())
            } else {
                None
            }
        })
        .collect();
    assets.load_imports(&imports, &base_dir)?;
    for item in &program.items {
        if let TopLevelItem::Scene(scene) = item {
            load_let_props(&scene.body, &mut assets, &base_dir)?;
        }
    }

    // Resolve each scene, compile its timeline, and check for overlaps.
    let scenes: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Scene(scene) = item {
                Some(scene)
            } else {
                None
            }
        })
        .collect();

    for scene_decl in &scenes {
        let resolved = resolve_scene(scene_decl, &assets)?;
        let compiled_timeline = timeline::compile_full(
            &resolved,
            &assets.kartas(),
            resolved
                .set_name
                .as_deref()
                .and_then(|n| assets.sets.get(n))
                .and_then(|s| s.surfaces.as_ref())
                .map(|s| s.floor),
        )?;

        let character_names: Vec<String> = resolved
            .entities
            .iter()
            .filter(|(_, e)| e.kind == EntityKind::Character)
            .map(|(name, _)| name.clone())
            .collect();
        timeline::check_overlaps(&compiled_timeline, &resolved.entities, &character_names)?;
    }

    println!("OK: {}", input.display());
    println!("  Imports: {n_imports}");
    println!("  Config:  {}", if has_config { "yes" } else { "no" });
    println!("  Scenes:  {n_scenes}");
    println!("  Overlaps: none detected");

    Ok(())
}

fn cmd_dump(input: &Path) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let program = animdsl::parser::parse(&source)?;
    let json = serde_json::to_string_pretty(&program)?;
    println!("{json}");
    Ok(())
}

/// Print speech-block timing as JSON: for every group of overlay mouth events
/// (one group = one voiced line, produced by prep_lipsync or `speaks`), the
/// absolute video-time at which it starts. The factory uses this to place the
/// voice track EXACTLY where the mouth moves — sync by construction, no
/// hand-maintained timecodes.
fn cmd_timing(input: &Path) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let base_dir = input
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf();
    let program = animdsl::parser::parse(&source)?;

    let mut assets = AssetRegistry::new();
    let imports: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Import(imp) = item {
                Some(imp.clone())
            } else {
                None
            }
        })
        .collect();
    assets.load_imports(&imports, &base_dir)?;
    for item in &program.items {
        if let TopLevelItem::Scene(scene) = item {
            load_let_props(&scene.body, &mut assets, &base_dir)?;
        }
    }

    let mut blocks: Vec<(f64, f64)> = Vec::new(); // (start_abs, end_abs)
    let mut offset = 0.0;
    for item in &program.items {
        if let TopLevelItem::Scene(scene_decl) = item {
            let resolved = resolve_scene(scene_decl, &assets)?;
            let tl = timeline::compile_full(
            &resolved,
            &assets.kartas(),
            resolved
                .set_name
                .as_deref()
                .and_then(|n| assets.sets.get(n))
                .and_then(|s| s.surfaces.as_ref())
                .map(|s| s.floor),
        )?;
            for (s0, e0) in &tl.speech_blocks {
                blocks.push((offset + s0, offset + e0));
            }
            offset += tl.duration;
        }
    }

    let items: Vec<String> = blocks
        .iter()
        .enumerate()
        .map(|(i, (s, e))| format!("{{\"index\":{},\"start\":{:.3},\"end\":{:.3}}}", i + 1, s, e))
        .collect();
    println!("{{\"total\":{:.3},\"blocks\":[{}]}}", offset, items.join(","));
    Ok(())
}
