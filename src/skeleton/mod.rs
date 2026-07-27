//! Skeleton rig system — defines characters as hierarchical bone trees
//! where each bone owns an SVG part that can be independently transformed.
//!
//! A character rig is defined by a JSON file alongside SVG parts:
//! ```text
//! character_name/
//!   rig.json        — skeleton definition, poses, pivot points
//!   torso.svg       — individual part SVGs
//!   head.svg
//!   arm_left.svg
//!   arm_right.svg
//!   leg_left.svg
//!   leg_right.svg
//!   ...
//! ```

use std::collections::HashMap;
use std::f64::consts::PI;
use std::path::Path;

use serde::{Deserialize, Serialize};

use crate::errors::AnimError;

/// КАРТА ФИГУРЫ: где у персонажа что находится относительно его якоря.
///
/// Все величины — доли ВЫСОТЫ кадра на единицу `scales` (кроме `mask_dx`,
/// который в долях ШИРИНЫ), отсчёт от точки, куда ставит `place`. Снимаются
/// замером с рендера: `python3 tools/karta.py --rig <папка> --write`.
///
/// Зачем в риге, а не в движке. Кадрирование планов раньше держалось на
/// постоянных, подобранных на глаз для ОДНОГО персонажа ростом 1.0. Стоило
/// фигуре подрасти — крупный план срезал макушку; появись второй персонаж с
/// другими пропорциями — те же числа врали бы уже на нём. Карта принадлежит
/// персонажу, поэтому и лежит рядом с его скелетом.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Karta {
    /// Макушка (отрицательное — выше якоря).
    pub crown: f64,
    /// Центр глаз.
    pub eyes: f64,
    /// Низ головы/маски (подбородок).
    pub chin: f64,
    /// Ступни.
    pub feet: f64,
    /// Смещение центра головы по X, в долях ШИРИНЫ кадра.
    #[serde(default)]
    pub mask_dx: f64,
    /// Ширина головы, в долях ВЫСОТЫ кадра.
    #[serde(default)]
    pub mask_w: f64,
}

/// A complete character rig: skeleton + part assets + poses.
#[derive(Debug, Clone)]
pub struct CharacterRig {
    pub name: String,
    pub skeleton: Skeleton,
    pub parts: HashMap<String, PartAsset>,
    pub poses: HashMap<String, Pose>,
    /// Total bounding height (used for scaling to scene).
    pub height: f64,
    /// Замеренная карта фигуры (см. `Karta`). Нет — планы считаются по
    /// историческим постоянным, как до появления карты.
    pub karta: Option<Karta>,
}

/// The skeleton: a tree of bones.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Skeleton {
    pub root: Bone,
}

/// A single bone in the hierarchy.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Bone {
    pub name: String,
    /// The SVG part file this bone renders (if any).
    #[serde(default)]
    pub part: Option<String>,
    /// Pivot point relative to the part's own coordinate space.
    #[serde(default)]
    pub pivot: (f64, f64),
    /// Offset from parent bone's pivot.
    #[serde(default)]
    pub offset: (f64, f64),
    /// Default rotation in degrees.
    #[serde(default)]
    pub rotation: f64,
    /// Default scale.
    #[serde(default = "default_scale")]
    pub scale: (f64, f64),
    /// Draw order (higher = in front).
    #[serde(default)]
    pub z_order: i32,
    /// Child bones.
    #[serde(default)]
    pub children: Vec<Bone>,
}

fn default_scale() -> (f64, f64) {
    (1.0, 1.0)
}

/// A named pose: per-bone transform overrides.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Pose {
    pub name: String,
    /// Map of bone_name -> transform override.
    pub bones: HashMap<String, BoneTransform>,
    /// How long the transition to this pose takes by default (seconds).
    #[serde(default = "default_transition")]
    pub transition_duration: f64,
}

fn default_transition() -> f64 {
    0.3
}

/// Per-bone transform override within a pose.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoneTransform {
    #[serde(default)]
    pub rotation: Option<f64>,
    #[serde(default)]
    pub offset: Option<(f64, f64)>,
    #[serde(default)]
    pub scale: Option<(f64, f64)>,
    /// Swap the bone's drawing for this pose (frame-by-frame "cel" swap, like a
    /// Flash symbol keyframe): the named `<part>.svg` replaces the default part.
    #[serde(default)]
    pub part: Option<String>,
    /// Override the bone's draw order for this pose. Lets a limb go BEHIND the
    /// head/torso in poses where it should (e.g. a hand tucked behind the head),
    /// then return in front for others — no more limbs punching through.
    #[serde(default)]
    pub z_order: Option<i32>,
}

/// A loaded SVG part.
#[derive(Debug, Clone)]
pub struct PartAsset {
    pub name: String,
    pub svg_data: Vec<u8>,
    pub width: f64,
    pub height: f64,
}

/// Rig definition file (JSON).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RigDefinition {
    pub name: String,
    pub height: f64,
    pub skeleton: Skeleton,
    pub poses: HashMap<String, Pose>,
    /// Замеренная карта фигуры. Необязательна: риг без неё работает, просто
    /// планы считаются по историческим постоянным.
    #[serde(default)]
    pub karta: Option<Karta>,
}

/// Load a character rig from a directory.
pub fn load_rig(name: &str, dir: &Path) -> Result<CharacterRig, AnimError> {
    let rig_path = dir.join("rig.json");
    let rig_json = std::fs::read_to_string(&rig_path).map_err(|e| {
        AnimError::Asset(format!(
            "failed to read rig definition for '{}' at {}: {}",
            name,
            rig_path.display(),
            e
        ))
    })?;

    let rig_def: RigDefinition = serde_json::from_str(&rig_json)
        .map_err(|e| AnimError::Asset(format!("failed to parse rig.json for '{}': {}", name, e)))?;

    // Load all SVG parts referenced in the skeleton...
    let mut parts = HashMap::new();
    collect_parts(&rig_def.skeleton.root, dir, &mut parts)?;
    // ...and any alternate drawings referenced only in pose cel-swaps.
    for pose in rig_def.poses.values() {
        for bt in pose.bones.values() {
            if let Some(ref part_name) = bt.part {
                load_part(part_name, dir, &mut parts)?;
            }
        }
    }

    Ok(CharacterRig {
        name: name.to_string(),
        skeleton: rig_def.skeleton,
        parts,
        poses: rig_def.poses,
        height: rig_def.height,
        karta: rig_def.karta,
    })
}

fn collect_parts(
    bone: &Bone,
    dir: &Path,
    parts: &mut HashMap<String, PartAsset>,
) -> Result<(), AnimError> {
    if let Some(ref part_name) = bone.part {
        load_part(part_name, dir, parts)?;
    }

    for child in &bone.children {
        collect_parts(child, dir, parts)?;
    }

    Ok(())
}

/// Load a single `<part_name>.svg` into the parts map (idempotent).
fn load_part(
    part_name: &str,
    dir: &Path,
    parts: &mut HashMap<String, PartAsset>,
) -> Result<(), AnimError> {
    if parts.contains_key(part_name) {
        return Ok(());
    }
    let svg_path = dir.join(format!("{}.svg", part_name));
    let svg_data = std::fs::read(&svg_path).map_err(|e| {
        AnimError::Asset(format!(
            "failed to read part '{}' from {}: {}",
            part_name,
            svg_path.display(),
            e
        ))
    })?;

    let opts = crate::svg_options();
    let tree = usvg::Tree::from_data(&svg_data, &opts).map_err(|e| {
        AnimError::Asset(format!("failed to parse SVG for part '{}': {}", part_name, e))
    })?;

    let size = tree.size();
    parts.insert(
        part_name.to_string(),
        PartAsset {
            name: part_name.to_string(),
            svg_data,
            width: size.width() as f64,
            height: size.height() as f64,
        },
    );
    Ok(())
}

// ---------------------------------------------------------------------------
// Pose interpolation
// ---------------------------------------------------------------------------

/// Interpolated bone state at a given time.
#[derive(Debug, Clone)]
pub struct BoneState {
    pub name: String,
    pub part: Option<String>,
    pub pivot: (f64, f64),
    pub offset: (f64, f64),
    pub rotation: f64,
    pub scale: (f64, f64),
    pub z_order: i32,
    /// Rubber-hose curl (radians) the drawing takes along its length — driven
    /// procedurally (spine sway, speech emphasis), added to any joint-derived
    /// bend at render time. 0.0 = rigid part.
    pub bend: f64,
}

/// Compute the interpolated bone states for a skeleton, blending between two poses.
pub fn interpolate_skeleton(
    skeleton: &Skeleton,
    from_pose: Option<&Pose>,
    to_pose: Option<&Pose>,
    t: f64, // 0.0 = fully `from`, 1.0 = fully `to`
) -> Vec<BoneState> {
    let mut states = Vec::new();
    interpolate_bone(&skeleton.root, from_pose, to_pose, t, &mut states);
    states
}

fn interpolate_bone(
    bone: &Bone,
    from_pose: Option<&Pose>,
    to_pose: Option<&Pose>,
    t: f64,
    states: &mut Vec<BoneState>,
) {
    let from_bt = from_pose.and_then(|p| p.bones.get(&bone.name));
    let to_bt = to_pose.and_then(|p| p.bones.get(&bone.name));

    let from_rot = from_bt.and_then(|bt| bt.rotation).unwrap_or(bone.rotation);
    let to_rot = to_bt.and_then(|bt| bt.rotation).unwrap_or(bone.rotation);

    let from_offset = from_bt.and_then(|bt| bt.offset).unwrap_or(bone.offset);
    let to_offset = to_bt.and_then(|bt| bt.offset).unwrap_or(bone.offset);

    let from_scale = from_bt.and_then(|bt| bt.scale).unwrap_or(bone.scale);
    let to_scale = to_bt.and_then(|bt| bt.scale).unwrap_or(bone.scale);

    // Smooth interpolation using ease-in-out
    let t_smooth = smooth_step(t);

    // Cel swap: drawings don't tween — snap to the target pose's part past the
    // midpoint, else the source pose's part, else the bone's default drawing.
    let part = if t >= 0.5 {
        to_bt
            .and_then(|bt| bt.part.clone())
            .or_else(|| bone.part.clone())
    } else {
        from_bt
            .and_then(|bt| bt.part.clone())
            .or_else(|| bone.part.clone())
    };

    // Draw order is discrete too — snap it the same way as the cel, so a limb
    // switches behind/in-front cleanly at the midpoint instead of z-fighting.
    let z_order = if t >= 0.5 {
        to_bt.and_then(|bt| bt.z_order).unwrap_or(bone.z_order)
    } else {
        from_bt.and_then(|bt| bt.z_order).unwrap_or(bone.z_order)
    };

    states.push(BoneState {
        name: bone.name.clone(),
        part,
        pivot: bone.pivot,
        offset: (
            lerp(from_offset.0, to_offset.0, t_smooth),
            lerp(from_offset.1, to_offset.1, t_smooth),
        ),
        rotation: lerp_angle(from_rot, to_rot, t_smooth),
        scale: (
            lerp(from_scale.0, to_scale.0, t_smooth),
            lerp(from_scale.1, to_scale.1, t_smooth),
        ),
        z_order,
        bend: 0.0,
    });

    for child in &bone.children {
        interpolate_bone(child, from_pose, to_pose, t, states);
    }
}

// ---------------------------------------------------------------------------
// Procedural animations
// ---------------------------------------------------------------------------

/// Per-occurrence pose variance: nudges non-facial bone rotation/offset by a
/// small amount that's stable for the ENTIRE hold of one pose occurrence (not
/// per-frame — that's `apply_idle_motion`'s job). A rig reuses the exact same
/// numbers every time a named pose fires; a hand artist never traces an old
/// page twice. This is the cheap stand-in: seed from (entity, pose, start
/// time) so the same "confident" pose on freeman at t=4s and on a clone at
/// t=19s reads as two distinct drawings, while a single occurrence stays
/// internally consistent across its own frames (no swimming mid-hold).
pub fn apply_pose_variance(states: &mut [BoneState], seed: u64) {
    for state in states.iter_mut() {
        let is_face = state.name.contains("eye")
            || state.name.contains("mouth")
            || state.name.contains("brow")
            || state.name == "hat"
            || state.name == "cane";
        if is_face {
            continue;
        }
        let h = name_hash(&state.name) as u64 ^ seed.wrapping_mul(0x9E37_79B9_7F4A_7C15);
        let r = hash_unit((h ^ (h >> 32)) as u32);
        let ox = hash_unit((h.wrapping_add(97) ^ (h >> 17)) as u32);
        let oy = hash_unit((h.wrapping_add(191) ^ (h >> 23)) as u32);
        state.rotation += r * 3.2;
        state.offset.0 += ox * 1.6;
        state.offset.1 += oy * 1.6;
    }
}

/// Apply idle breathing/swaying animation to bone states.
pub fn apply_idle_motion(states: &mut [BoneState], _skeleton: &Skeleton, time: f64) {
    let tau = 2.0 * PI;
    // Multi-frequency breathing/sway reads more organic than a single sine.
    let breath = (time * 1.05 * tau).sin();
    let sway = (time * 0.33 * tau).sin() * 0.6 + (time * 0.19 * tau).sin() * 0.4;
    // Very slow weight-shift (~8s period): the body subtly leans side to side,
    // head leads/counters it — reads as a living body holding its weight, not a
    // frozen puppet. Low frequency, so it's life, not the tremor we calmed.
    let shift = (time * 0.12 * tau).sin();
    // АСИММЕТРИЯ ПОКОЯ (SIMILARITY.md §5): у оригинала фигура «развинченная» —
    // маска всегда чуть наклонена, плечи не на одной высоте. Идеально ровная
    // симметричная стойка читается как кукла, а не как рисунок. Постоянные
    // (не колеблющиеся) смещения — характер позы, а не движение.
    const HEAD_TILT: f64 = 4.0;        // градусы: наклон маски (было 0.055 —
                                       // значение писали как радианы, а поле
                                       // в ГРАДУСАХ, и наклона фактически не было)
    const SHOULDER_SKEW: f64 = 1.2;    // градусы: одно плечо выше другого
    for state in states.iter_mut() {
        match state.name.as_str() {
            "head" => state.rotation += HEAD_TILT,
            "upper_arm_left" => state.rotation -= SHOULDER_SKEW,
            "upper_arm_right" => state.rotation += SHOULDER_SKEW * 0.6,
            _ => {}
        }
    }

    // "Animation boil": the jitter target updates ~5x/sec (held on fours), so a
    // static pose is never perfectly still — but calm, not a tremor.
    for state in states.iter_mut() {
        let is_face = state.name.contains("eye")
            || state.name.contains("mouth")
            || state.name.contains("brow");

        // Per-bone procedural micro-float (skipped for facial features).
        // SMOOTH coherent drift, not a stepped random jump: earlier this
        // resampled a hash ~5×/sec, which made every limb TWITCH (read as
        // «дёрганье»). Now each bone floats on slow, low-amplitude sines with a
        // per-bone phase — the figure breathes without jittering. The hand-drawn
        // «redrawn» wobble is carried by the ink line-boil (outline), not by
        // shaking the skeleton.
        if !is_face {
            let h = name_hash(&state.name);
            let ph1 = hash_unit(h) * PI;
            let ph2 = hash_unit(h ^ 0x9E37_79B9) * PI;
            let f = 0.14 + hash_unit(h ^ 0x1234_5678).abs() * 0.08; // ~0.14–0.22 Hz, slow
            state.rotation += (time * f * tau + ph1).sin() * 0.06;
            state.offset.0 += (time * f * 0.7 * tau + ph2).sin() * 0.045;
            state.offset.1 += (time * f * 0.5 * tau + ph1).sin() * 0.035;
        }

        match state.name.as_str() {
            // NOTE: amplitudes deliberately SMALL. On-twos steps this idle every
            // 1/12s; loud idle → visible «дёрганье» ×N characters. A held drawing
            // must nearly HOLD (like the original) — life comes from deliberate
            // gestures + the occasional blink, not constant breathing/bobbing.
            "torso" => {
                state.scale.1 *= 1.0 + breath * 0.008; // faint breathing
                state.offset.0 += shift * 0.7; // slow weight shift
                state.rotation += sway * 0.3 + shift * 0.25;
                state.bend += sway * 0.02 + shift * 0.025 + breath * 0.005;
            }
            "head" => {
                state.offset.1 += breath * 0.5;
                // very slow "looking" life, small
                state.offset.0 += shift * 0.5 + (time * 0.19 * tau).sin() * 0.35;
                state.rotation += (time * 0.29 * tau).sin() * 0.45 + sway * 0.2 - shift * 0.3;
            }
            name if name.contains("thigh") => {
                state.offset.0 += shift * 0.22;
            }
            name if name.contains("arm") => {
                let phase = if name.contains("right") { PI } else { 0.0 };
                state.rotation += (time * 0.5 * tau + phase).sin() * 0.5 + shift * 0.22;
            }
            _ => {}
        }

        // Auto-blink: deterministic, ~every 3.4–4.6s the lids snap shut for
        // ~0.12s. Cel-swapped eyes (part overrides) are unaffected only in
        // scale, so the blink reads on any eye drawing. Instant life on every
        // character with zero scripting.
        if state.name.starts_with("eye") {
            // Shared cycle for both eyes (hash of the common prefix), so the
            // lids close together.
            let cycle = 3.4 + hash_unit(name_hash("eye")).abs() * 1.2;
            let ph = time % cycle as f64;
            let lids_shut = ph < 0.12;
            if lids_shut {
                let k = (ph / 0.12 * PI).sin(); // 0→1→0
                state.scale.1 *= (1.0 - 0.92 * k).max(0.06);
            }

            // --- Микро-саккады (дарты взгляда) --------------------------------
            // Огромные глаза Фримена «мертвеют» между морганиями, если зрачок
            // не двигается. Настоящий взгляд НЕ плывёт — он ДЁРГАЕТСЯ: держит
            // точку фиксации ~0.9–1.5с, затем МГНОВЕННО прыгает на новую
            // (саккада ~1 кадр). Детерминированно; общий хэш «gaze» → оба глаза
            // смотрят в одну точку (не косят). Амплитуда крошечная — глаз крупный
            // на экране, поэтому смещение баесится к центру (gx*|gx|): почти все
            // дарты мелкие, изредка — заметный взгляд в сторону.
            let sac = std::env::var("ANIMDSL_SACCADE_AMP").ok()
                .and_then(|v| v.parse::<f64>().ok())
                .unwrap_or(1.0);
            if !lids_shut && sac > 0.0 {
                let hold = 0.95 + hash_unit(name_hash("gaze")).abs() * 0.55; // 0.95–1.5с
                let idx = (time / hold).floor() as i64 as u32;
                let gx = hash_unit(idx.wrapping_mul(2_654_435_761) ^ 0x00A5_A5A5);
                let gy = hash_unit(idx.wrapping_mul(40_503) ^ 0x0000_1357);
                state.offset.0 += gx * gx.abs() * 6.0 * sac; // взгляд по горизонтали шире
                state.offset.1 += gy * gy.abs() * 3.5 * sac; // по вертикали — уже
            }
        }
    }
}

/// Small stable hash of a bone name, for per-bone procedural noise.
fn name_hash(name: &str) -> u32 {
    let mut h: u32 = 2166136261;
    for b in name.bytes() {
        h ^= b as u32;
        h = h.wrapping_mul(16777619);
    }
    h
}

/// Deterministic hash → [-1, 1].
fn hash_unit(mut x: u32) -> f64 {
    x ^= x >> 13;
    x = x.wrapping_mul(1274126177);
    x ^= x >> 16;
    (x as f64 / u32::MAX as f64) * 2.0 - 1.0
}

/// Apply walk cycle procedural animation.
/// `walk_phase` goes from 0.0 to 1.0 per step cycle.
pub fn apply_walk_cycle(states: &mut [BoneState], walk_phase: f64, speed: f64) {
    let phase = walk_phase * 2.0 * PI;

    for state in states.iter_mut() {
        match state.name.as_str() {
            "torso" => {
                // Body bobs up and down
                state.offset.1 += (phase * 2.0).sin().abs() * -3.0 * speed;
                // Slight lean in movement direction
                state.rotation += (phase).sin() * 1.5 * speed;
            }
            "head" => {
                // Head stays more stable (counteracts body movement)
                state.offset.1 += (phase * 2.0).sin().abs() * 1.5 * speed;
                state.rotation += -(phase).sin() * 0.8 * speed;
            }
            "arm_left" => {
                // Arms swing opposite to legs
                state.rotation += (phase).sin() * 25.0 * speed;
            }
            "arm_right" => {
                state.rotation += (-phase).sin() * 25.0 * speed;
            }
            "leg_left" => {
                // Legs alternate forward/back
                state.rotation += (phase).sin() * 20.0 * speed;
            }
            "leg_right" => {
                state.rotation += (-phase).sin() * 20.0 * speed;
            }
            _ => {}
        }
    }
}

/// Apply anticipation before an action (wind-up).
/// `t` goes 0.0 -> 1.0 during the anticipation phase.
pub fn apply_anticipation(states: &mut [BoneState], t: f64) {
    // Crouch down slightly, pull back
    let crouch = (t * PI).sin(); // peaks at t=0.5
    for state in states.iter_mut() {
        match state.name.as_str() {
            "torso" => {
                state.offset.1 += crouch * 5.0;
                state.scale.1 *= 1.0 - crouch * 0.03;
                state.scale.0 *= 1.0 + crouch * 0.02;
            }
            "leg_left" | "leg_right" => {
                state.rotation += crouch * -5.0;
            }
            _ => {}
        }
    }
}

/// Apply squash and stretch based on vertical velocity.
pub fn apply_squash_stretch(states: &mut [BoneState], velocity_x: f64, velocity_y: f64) {
    // Stretch ALONG the direction of motion and squash across it — the classic
    // squash/stretch of hand-drawn animation, giving fast moves weight. Applied
    // to the torso, which propagates to the whole body. Volume roughly kept.
    let fy = (velocity_y * 0.006).clamp(-0.17, 0.17);
    let fx = (velocity_x * 0.006).clamp(-0.17, 0.17);
    for state in states.iter_mut() {
        if state.name == "torso" {
            state.scale.1 *= 1.0 + fy - fx.abs() * 0.5;
            state.scale.0 *= 1.0 + fx - fy.abs() * 0.5;
        }
    }
}

/// Apply follow-through/overshoot to a rotation.
/// `t` is time since the action started, `settle_time` is how long it takes to settle.
pub fn overshoot(target: f64, t: f64, settle_time: f64) -> f64 {
    if t >= settle_time {
        return target;
    }
    let progress = t / settle_time;
    // Damped spring overshoot
    let overshoot_amount = (-progress * 4.0).exp() * (progress * 8.0 * PI).sin() * 0.15;
    target * (1.0 + overshoot_amount)
}

// ---------------------------------------------------------------------------
// Math helpers
// ---------------------------------------------------------------------------

fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * t
}

/// Lerp angles, taking the shortest path.
fn lerp_angle(a: f64, b: f64, t: f64) -> f64 {
    let mut diff = b - a;
    while diff > 180.0 {
        diff -= 360.0;
    }
    while diff < -180.0 {
        diff += 360.0;
    }
    a + diff * t
}

/// Smooth step (ease-in-out).
fn smooth_step(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0);
    t * t * (3.0 - 2.0 * t)
}
