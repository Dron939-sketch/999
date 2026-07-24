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

/// A complete character rig: skeleton + part assets + poses.
#[derive(Debug, Clone)]
pub struct CharacterRig {
    pub name: String,
    pub skeleton: Skeleton,
    pub parts: HashMap<String, PartAsset>,
    pub poses: HashMap<String, Pose>,
    /// Total bounding height (used for scaling to scene).
    pub height: f64,
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
        z_order: bone.z_order,
    });

    for child in &bone.children {
        interpolate_bone(child, from_pose, to_pose, t, states);
    }
}

// ---------------------------------------------------------------------------
// Procedural animations
// ---------------------------------------------------------------------------

/// Apply idle breathing/swaying animation to bone states.
pub fn apply_idle_motion(states: &mut [BoneState], _skeleton: &Skeleton, time: f64) {
    let tau = 2.0 * PI;
    // Multi-frequency breathing/sway reads more organic than a single sine.
    let breath = (time * 1.05 * tau).sin();
    let sway = (time * 0.33 * tau).sin() * 0.6 + (time * 0.19 * tau).sin() * 0.4;
    // "Animation boil": the jitter target updates ~8x/sec (held on twos/threes),
    // so even a static pose is never perfectly still — like drawn animation.
    let step = (time * 8.0).floor() as i64;

    for state in states.iter_mut() {
        let is_face = state.name.contains("eye")
            || state.name.contains("mouth")
            || state.name.contains("brow");

        // Per-bone procedural micro-float (skipped for facial features).
        if !is_face {
            let h = name_hash(&state.name);
            let jr = hash_unit(h ^ (step as u32).wrapping_mul(2654435761));
            let jx = hash_unit(h.wrapping_add(97) ^ (step as u32).wrapping_mul(40503));
            let jy = hash_unit(h.wrapping_add(191) ^ (step as u32).wrapping_mul(22695477));
            state.rotation += jr * 0.9;
            state.offset.0 += jx * 0.5;
            state.offset.1 += jy * 0.4;
        }

        match state.name.as_str() {
            "torso" => {
                state.scale.1 *= 1.0 + breath * 0.012;
                state.rotation += sway * 0.8;
            }
            "head" => {
                state.offset.1 += breath * 0.9;
                state.rotation += (time * 0.5 * tau).sin() * 0.8 + sway * 0.5;
            }
            name if name.contains("arm") => {
                let phase = if name.contains("right") { PI } else { 0.0 };
                state.rotation += (time * 0.6 * tau + phase).sin() * 1.4;
            }
            _ => {}
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
pub fn apply_squash_stretch(states: &mut [BoneState], velocity_y: f64) {
    let factor = (velocity_y * 0.005).clamp(-0.15, 0.15);
    for state in states.iter_mut() {
        if state.name == "torso" {
            // Stretch when moving fast vertically, squash on deceleration
            state.scale.1 *= 1.0 + factor;
            state.scale.0 *= 1.0 - factor * 0.5; // preserve volume
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
