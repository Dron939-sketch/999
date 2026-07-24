//! Renderer — evaluates the timeline at each frame and composites 2D entities
//! into pixel buffers using tiny-skia and resvg.
//!
//! Supports both legacy single-SVG characters and new rig-based characters
//! with per-bone part compositing and procedural animation.

use std::cell::RefCell;
use std::collections::hash_map::DefaultHasher;
use std::collections::HashMap;
use std::hash::{Hash, Hasher};
use std::sync::Arc;

use tiny_skia::{Color as SkiaColor, Paint, Pixmap, PixmapPaint, Rect, Transform};

use crate::assets::{AssetRegistry, CharacterAsset};
use crate::ast::Direction;
use crate::errors::AnimError;
use crate::procedural;
use crate::scene::{EntityKind, EntityState, RenderConfig};
use crate::skeleton::{
    self, apply_idle_motion, apply_squash_stretch, apply_walk_cycle, interpolate_skeleton,
    BoneState, CharacterRig,
};
use crate::timeline::{
    evaluate_camera, evaluate_track, CameraKeyframe, PoseEvent, Property, Timeline, TransitionKind,
};

thread_local! {
    /// Parsed-SVG cache keyed by a hash of the exact SVG bytes. Rendering a 52s
    /// clip re-draws the same static set 1300+ times and each character part
    /// many times — parsing (usvg) is the bottleneck. Identical bytes → parse
    /// once, reuse the tree. The static set collapses to a single parse; boiled
    /// character parts reuse per seed value while that seed recurs.
    static SVG_CACHE: RefCell<HashMap<u64, Arc<usvg::Tree>>> = RefCell::new(HashMap::new());

    /// Rasterised-SVG cache: keyed by (bytes, render size, flip). The real cost
    /// of a detailed set is rasterising its ink filter (feTurbulence/displace)
    /// every frame — but under a HELD camera the result is pixel-identical, so we
    /// rasterise once and just re-composite the cached pixmap. This is the big
    /// render-speed win (the parse cache only saves XML parsing).
    static PIXMAP_CACHE: RefCell<HashMap<u64, Arc<Pixmap>>> = RefCell::new(HashMap::new());
}

/// Parse SVG bytes into a tree, reusing a cached parse for identical bytes.
fn parse_svg_cached(bytes: &[u8]) -> Result<Arc<usvg::Tree>, AnimError> {
    let mut hasher = DefaultHasher::new();
    bytes.hash(&mut hasher);
    let key = hasher.finish();
    if let Some(tree) = SVG_CACHE.with(|c| c.borrow().get(&key).cloned()) {
        return Ok(tree);
    }
    let opts = crate::svg_options();
    let tree = Arc::new(
        usvg::Tree::from_data(bytes, &opts)
            .map_err(|e| AnimError::Render(format!("SVG parse error: {e}")))?,
    );
    // Bound memory: boiled parts create many distinct keys over a long clip.
    SVG_CACHE.with(|c| {
        let mut m = c.borrow_mut();
        if m.len() > 8192 {
            m.clear();
        }
        m.insert(key, tree.clone());
    });
    Ok(tree)
}

/// A rendered frame as raw RGBA pixel data.
pub struct Frame {
    pub width: u32,
    pub height: u32,
    pub data: Vec<u8>,
}

/// Render all frames for a scene.
pub fn render_scene(
    config: &RenderConfig,
    timeline: &Timeline,
    initial_entities: &HashMap<String, EntityState>,
    set_name: Option<&str>,
    assets: &AssetRegistry,
    custom_poses: &HashMap<String, Vec<(String, f64)>>,
) -> Result<Vec<Frame>, AnimError> {
    let total_frames = (timeline.duration * config.fps as f64).ceil() as usize;
    let mut frames = Vec::with_capacity(total_frames);

    log::info!(
        "Rendering {} frames ({}x{} @ {} fps, {:.1}s)",
        total_frames,
        config.width,
        config.height,
        config.fps,
        timeline.duration,
    );

    for frame_idx in 0..total_frames {
        let t = frame_idx as f64 / config.fps as f64;
        let frame = render_frame(
            config,
            timeline,
            initial_entities,
            set_name,
            assets,
            custom_poses,
            t,
        )?;
        frames.push(frame);

        if frame_idx % config.fps as usize == 0 {
            log::info!("  Frame {}/{} ({:.1}s)", frame_idx, total_frames, t);
        }
    }

    Ok(frames)
}

/// Render a single frame at time `t`.
pub fn render_frame(
    config: &RenderConfig,
    timeline: &Timeline,
    initial_entities: &HashMap<String, EntityState>,
    set_name: Option<&str>,
    assets: &AssetRegistry,
    custom_poses: &HashMap<String, Vec<(String, f64)>>,
    t: f64,
) -> Result<Frame, AnimError> {
    let w = config.width;
    let h = config.height;

    let mut pixmap =
        Pixmap::new(w, h).ok_or_else(|| AnimError::Render("failed to create pixmap".into()))?;

    pixmap.fill(SkiaColor::from_rgba8(
        config.background.r,
        config.background.g,
        config.background.b,
        config.background.a,
    ));

    let camera = evaluate_camera(&timeline.camera_track, t);

    // Render set (background).
    if let Some(name) = set_name {
        if let Some(set_asset) = assets.sets.get(name) {
            render_svg_to_pixmap(
                &set_asset.svg_data,
                &mut pixmap,
                w,
                h,
                0.5,
                0.5,
                1.0,
                1.0,
                0.0,
                1.0,
                &camera,
                true,
            )?;
        }
    }

    // Evaluate entity states at time t.
    let mut entity_states: Vec<(String, EntityState)> = initial_entities
        .iter()
        .map(|(name, initial)| {
            let mut state = initial.clone();
            for track in &timeline.tracks {
                if track.entity == *name {
                    let value = evaluate_track(track, t);
                    match track.property {
                        Property::X => state.x = value,
                        Property::Y => state.y = value,
                        Property::ScaleX => state.scale_x = value,
                        Property::ScaleY => state.scale_y = value,
                        Property::Rotation => state.rotation = value,
                        Property::Opacity => state.opacity = value,
                    }
                }
            }
            (name.clone(), state)
        })
        .collect();

    entity_states.sort_by_key(|(_, s)| s.layer);

    // Render each entity.
    for (name, state) in &entity_states {
        if state.opacity <= 0.001 {
            continue;
        }

        match state.kind {
            EntityKind::Character => {
                if let Some(char_asset) = assets.characters.get(name) {
                    render_character(
                        char_asset,
                        state,
                        &mut pixmap,
                        w,
                        h,
                        &camera,
                        t,
                        timeline,
                        name,
                        custom_poses,
                    )?;
                }
            }
            EntityKind::Prop => {
                if let Some(prop_asset) = assets.props.get(name) {
                    let flip_x = match state.facing {
                        Direction::Left => -1.0,
                        _ => 1.0,
                    };
                    render_svg_to_pixmap(
                        &prop_asset.svg_data,
                        &mut pixmap,
                        w,
                        h,
                        state.x,
                        state.y,
                        state.scale_x * flip_x,
                        state.scale_y,
                        state.rotation,
                        state.opacity,
                        &camera,
                        false,
                    )?;
                }
            }
        }
    }

    // Apply transitions.
    apply_transitions(&mut pixmap, &timeline.transitions, t)?;

    Ok(Frame {
        width: w,
        height: h,
        data: pixmap.data().to_vec(),
    })
}

/// Render a character (either legacy or rigged).
fn render_character(
    asset: &CharacterAsset,
    state: &EntityState,
    pixmap: &mut Pixmap,
    canvas_w: u32,
    canvas_h: u32,
    camera: &CameraKeyframe,
    t: f64,
    timeline: &Timeline,
    entity_name: &str,
    custom_poses: &HashMap<String, Vec<(String, f64)>>,
) -> Result<(), AnimError> {
    match asset {
        CharacterAsset::Legacy { svg_data, .. } => {
            let flip_x = match state.facing {
                Direction::Left => -1.0,
                _ => 1.0,
            };
            render_svg_to_pixmap(
                svg_data,
                pixmap,
                canvas_w,
                canvas_h,
                state.x,
                state.y,
                state.scale_x * flip_x,
                state.scale_y,
                state.rotation,
                state.opacity,
                camera,
                false,
            )
        }
        CharacterAsset::Rigged(rig) => render_rigged_character(
            rig,
            state,
            pixmap,
            canvas_w,
            canvas_h,
            camera,
            t,
            timeline,
            entity_name,
        ),
        CharacterAsset::Procedural(desc) => render_procedural_character(
            desc,
            state,
            pixmap,
            canvas_w,
            canvas_h,
            camera,
            t,
            timeline,
            entity_name,
            custom_poses,
        ),
    }
}

/// Render a rig-based character with per-bone part compositing.
fn render_rigged_character(
    rig: &CharacterRig,
    state: &EntityState,
    pixmap: &mut Pixmap,
    canvas_w: u32,
    canvas_h: u32,
    camera: &CameraKeyframe,
    t: f64,
    timeline: &Timeline,
    entity_name: &str,
) -> Result<(), AnimError> {
    // Limited animation "on twos": the pose clock ticks at ~12 fps so gestures
    // and cel swaps pop in steps like hand-drawn animation, while the ink boil
    // and idle float below keep running at full rate.
    let pose_time = (t * 12.0).floor() / 12.0;

    // Determine current and previous pose events, and interpolation progress.
    // Overlay events (speech mouth flaps) merge onto the last held body pose,
    // so a gesture — or a lying character — keeps its posture while talking.
    let events: Vec<&PoseEvent> = timeline
        .pose_events
        .iter()
        .filter(|e| e.entity == entity_name)
        .collect();

    let mut current_idx: Option<usize> = None;
    for (i, ev) in events.iter().enumerate() {
        if ev.time <= pose_time {
            current_idx = Some(i);
        }
    }

    let (from_idx, to_idx, pose_t, td) = match current_idx {
        None => (None, if events.is_empty() { None } else { Some(0) }, 0.0, 0.18),
        Some(idx) => {
            // Use the target pose's own transition duration (fast for flaps).
            let td = events
                .get(idx)
                .and_then(|ev| rig.poses.get(&ev.pose))
                .map(|p| p.transition_duration)
                .unwrap_or(0.18) // snappier default than a slow 0.3s slide
                .max(0.01);
            let elapsed = pose_time - events[idx].time;
            if elapsed >= td {
                (Some(idx), Some(idx), 1.0, td)
            } else {
                let prev = if idx > 0 { Some(idx - 1) } else { None };
                (prev, Some(idx), elapsed / td, td)
            }
        }
    };

    let from_pose = resolve_effective_pose(rig, &events, from_idx);
    let to_pose = resolve_effective_pose(rig, &events, to_idx);

    // Hand-drawn timing. Short transitions (mouth flaps, blinks) just ease out.
    // Larger gestures get anticipation (a wind-up away from the target) plus an
    // overshoot, so poses read as struck rather than slid — the core of the
    // Freeman feel. Extrapolation past [0,1] is intentional here.
    let eased_t = if td < 0.15 {
        ease_out_cubic(pose_t)
    } else {
        anticipate_back(pose_t)
    };

    // Get interpolated bone states.
    let mut bone_states =
        interpolate_skeleton(&rig.skeleton, from_pose.as_ref(), to_pose.as_ref(), eased_t);

    // Pose-only state one animation tick (1/12s) earlier — lets us measure how
    // fast each part is moving in THIS gesture, the basis for motion smears.
    // Pose-only (no idle/speak float) so only deliberate motion smears.
    let prev_pose_t = match current_idx {
        Some(idx) => (((pose_time - 1.0 / 12.0) - events[idx].time) / td).clamp(0.0, 1.0),
        None => 0.0,
    };
    let eased_prev = if td < 0.15 {
        ease_out_cubic(prev_pose_t)
    } else {
        anticipate_back(prev_pose_t)
    };
    let mut bone_states_prev =
        interpolate_skeleton(&rig.skeleton, from_pose.as_ref(), to_pose.as_ref(), eased_prev);

    // Detect if the character is moving (for walk cycle).
    let velocity = compute_velocity(timeline, entity_name, t);
    let speed = (velocity.0 * velocity.0 + velocity.1 * velocity.1).sqrt();
    let is_walking = speed > 0.01;

    // Apply procedural animations.
    if is_walking {
        // Walk cycle: phase derived from position for consistent foot placement.
        let walk_phase = (t * 2.5) % 1.0; // ~2.5 steps per second
        let walk_intensity = (speed * 8.0).min(1.0); // scale with speed
        apply_walk_cycle(&mut bone_states, walk_phase, walk_intensity);
    } else {
        // Idle breathing/sway.
        apply_idle_motion(&mut bone_states, &rig.skeleton, t);
    }

    // Apply squash and stretch based on vertical velocity.
    apply_squash_stretch(&mut bone_states, velocity.0, velocity.1);

    // While the character is speaking, the whole body talks — not just the mouth.
    // Detect speech from the cluster of overlay flap events and layer a head nod
    // + gentle hand beat on top. This is the biggest step away from "a puppet
    // with a flapping mouth" toward Freeman's living delivery.
    let speak = speaking_intensity(&events, pose_time);
    if speak > 0.001 {
        apply_speaking_motion(&mut bone_states, t, speak);
    }

    // Match the same idle/walk/squash/speak float on the previous-tick state, so
    // the smear below measures TOTAL on-screen motion between ticks — not a
    // constant pose-vs-float offset (which would smear a talking head forever).
    let t_prev = t - 1.0 / 12.0;
    if is_walking {
        apply_walk_cycle(&mut bone_states_prev, (t_prev * 2.5) % 1.0, (speed * 8.0).min(1.0));
    } else {
        apply_idle_motion(&mut bone_states_prev, &rig.skeleton, t_prev);
    }
    apply_squash_stretch(&mut bone_states_prev, velocity.0, velocity.1);
    let speak_prev = speaking_intensity(&events, pose_time - 1.0 / 12.0);
    if speak_prev > 0.001 {
        apply_speaking_motion(&mut bone_states_prev, t_prev, speak_prev);
    }

    // Compute the character's screen position.
    let cw = canvas_w as f64;
    let ch = canvas_h as f64;
    let target_height = ch * 0.35;
    let base_scale = target_height / rig.height;

    let cam_x = camera.x;
    let cam_y = camera.y;
    let zoom = camera.zoom;
    let screen_x = ((state.x - cam_x) * zoom + 0.5) * cw;
    let screen_y = ((state.y - cam_y) * zoom + 0.5) * ch;

    let char_scale = base_scale * zoom;
    let flip = match state.facing {
        Direction::Left => -1.0_f64,
        _ => 1.0_f64,
    };

    // Per-frame "boil" seed: cycles the ink-filter turbulence so hand-drawn
    // edges wobble frame-to-frame (~9 changes/sec). No-op for parts without a
    // turbulence filter.
    let boil_seed = (t * 5.0) as i64;
    let boil_seed = boil_seed.rem_euclid(4096) as u32 + 1;

    // Two-phase draw. First walk the bone tree to compute each part's world
    // transform (parent transforms propagate to children), collecting drawables;
    // THEN draw them sorted by z_order. This is what makes a hand tuck BEHIND
    // the head when the pose says so — tree order alone would always draw a limb
    // in front of its siblings regardless of intent.
    let mut drawables: Vec<Drawable> = Vec::new();
    collect_bone_drawables(
        &rig.skeleton.root,
        &bone_states,
        &rig.parts,
        screen_x,
        screen_y,
        char_scale,
        flip,
        state.opacity,
        state.scale_x,
        state.scale_y,
        // Whole-character rotation (the `rotate` action): lets a rigged
        // character lie down, lean, etc. Applied as the root rotation.
        state.rotation,
        None,
        &mut drawables,
    );
    // Same collection at the previous tick — pose-only — to measure per-part motion.
    let mut prev_draws: Vec<Drawable> = Vec::new();
    collect_bone_drawables(
        &rig.skeleton.root,
        &bone_states_prev,
        &rig.parts,
        screen_x,
        screen_y,
        char_scale,
        flip,
        state.opacity,
        state.scale_x,
        state.scale_y,
        state.rotation,
        None,
        &mut prev_draws,
    );

    // Motion smears: where a part moved fast since the previous tick, insert 1–2
    // fading ghost copies along its path (drawn BEHIND the real part). This is the
    // motion-blur of hand-drawn animation — the step that kills the "slide". The
    // two lists share tree order, so we pair them by index.
    let mut final_draws: Vec<Drawable> = Vec::with_capacity(drawables.len());
    for (i, d) in drawables.iter().enumerate() {
        if let Some(p) = prev_draws.get(i) {
            let dx = d.x - p.x;
            let dy = d.y - p.y;
            let dpos = (dx * dx + dy * dy).sqrt();
            let motion = dpos + (d.rot - p.rot).abs() * 0.6;
            if motion > 16.0 {
                let ghosts = if motion > 40.0 { 2 } else { 1 };
                for g in 0..ghosts {
                    let f = (g as f64 + 1.0) / (ghosts as f64 + 1.0); // between prev & cur
                    final_draws.push(Drawable {
                        part: d.part,
                        x: p.x + dx * f,
                        y: p.y + dy * f,
                        sx: d.sx,
                        sy: d.sy,
                        rot: p.rot + (d.rot - p.rot) * f,
                        flip: d.flip,
                        opacity: d.opacity * 0.20,
                        pivot: d.pivot,
                        z_order: d.z_order,
                        bend: d.bend,
                        bend_origin: d.bend_origin,
                    });
                }
            }
        }
        final_draws.push(Drawable {
            part: d.part,
            x: d.x,
            y: d.y,
            sx: d.sx,
            sy: d.sy,
            rot: d.rot,
            flip: d.flip,
            opacity: d.opacity,
            pivot: d.pivot,
            z_order: d.z_order,
            bend: d.bend,
            bend_origin: d.bend_origin,
        });
    }

    // Stable sort keeps tree/ghost order among equal z_order (deterministic).
    final_draws.sort_by_key(|d| d.z_order);
    for d in &final_draws {
        render_bone_part(
            d.part, pixmap, d.x, d.y, d.sx, d.sy, d.rot, d.flip, d.opacity, &d.pivot,
            d.bend, d.bend_origin, boil_seed,
        )?;
    }

    Ok(())
}

/// Render a procedurally drawn character.
fn render_procedural_character(
    desc: &procedural::CharacterDesc,
    state: &EntityState,
    pixmap: &mut Pixmap,
    canvas_w: u32,
    canvas_h: u32,
    camera: &CameraKeyframe,
    t: f64,
    timeline: &Timeline,
    entity_name: &str,
    custom_poses: &HashMap<String, Vec<(String, f64)>>,
) -> Result<(), AnimError> {
    let cw = canvas_w as f64;
    let ch = canvas_h as f64;

    // Get pose interpolation.
    let (from_pose_name, to_pose_name, pose_t) = get_pose_interpolation(timeline, entity_name, t);

    // Resolve poses: check custom poses first, then fall back to hardcoded named_pose.
    let resolve_pose = |name: &str| -> procedural::CharacterState {
        if let Some(fields) = custom_poses.get(name) {
            procedural::custom_pose(fields)
        } else {
            procedural::named_pose(name)
        }
    };

    let from_state = resolve_pose(from_pose_name.unwrap_or("idle"));
    let to_state = resolve_pose(to_pose_name.unwrap_or("idle"));
    let mut char_state = procedural::lerp_state_staggered(&from_state, &to_state, pose_t);

    // Detect movement for walk cycle.
    let velocity = compute_velocity(timeline, entity_name, t);
    let speed = (velocity.0 * velocity.0 + velocity.1 * velocity.1).sqrt();
    let is_walking = speed > 0.01;

    if is_walking {
        let walk_phase = (t * 2.5) % 1.0;
        let walk_intensity = (speed * 8.0).min(1.0);
        procedural::apply_walk(&mut char_state, walk_phase, walk_intensity);
    } else {
        procedural::apply_idle(&mut char_state, t);
    }

    // Apply secondary motion (hair follow-through, clothing lag).
    procedural::apply_secondary_motion(&mut char_state, 1.0 / 24.0);

    // Auto-compute body_angle based on movement velocity and facing direction.
    let target_angle = if speed > 0.01 {
        // Moving — turn toward movement direction.
        if velocity.0 > 0.01 {
            75.0 // moving right → 3/4-profile right
        } else if velocity.0 < -0.01 {
            285.0 // moving left → 3/4-profile left
        } else {
            char_state.body_angle // vertical movement, keep current
        }
    } else {
        // Standing still — use facing direction.
        match state.facing {
            Direction::Left => 315.0,  // 3/4 left (not full profile)
            Direction::Right => 45.0,  // 3/4 right
            Direction::Back => 180.0,  // facing away
            Direction::Front => 0.0,   // straight at camera
            _ => 0.0,                  // up/down → front
        }
    };
    // Smooth transition.
    char_state.body_angle =
        procedural::lerp_angle_smooth(char_state.body_angle, target_angle, 0.15);

    // Screen position.
    let cam_x = camera.x;
    let cam_y = camera.y;
    let zoom = camera.zoom;
    let screen_x = ((state.x - cam_x) * zoom + 0.5) * cw;
    let screen_y = ((state.y - cam_y) * zoom + 0.5) * ch;

    // Scale: character's procedural height is ~200 units, we want ~35% of canvas height.
    let target_height = ch * 0.35;
    let scale = (target_height / 200.0) * zoom * state.scale_y;

    let flip = matches!(state.facing, Direction::Left);

    // Foot position (screen_y is character center, foot is at bottom).
    let foot_y = screen_y + target_height * 0.35 * zoom;

    procedural::draw_character(
        desc,
        &char_state,
        pixmap,
        screen_x,
        foot_y,
        scale,
        flip,
        state.opacity,
    );

    Ok(())
}

/// Recursively render bones in the skeleton tree, accumulating transforms.
/// One part ready to be drawn, with its world transform and draw order.
struct Drawable<'a> {
    part: &'a skeleton::PartAsset,
    x: f64,
    y: f64,
    sx: f64,
    sy: f64,
    rot: f64,
    flip: f64,
    opacity: f64,
    pivot: (f64, f64),
    z_order: i32,
    /// Rubber-hose bend: total curl (radians) applied along the part's length,
    /// so it reads as a bending drawing, not a rigid rotated segment.
    bend: f64,
    /// Where the curl originates as a fraction of part height: 0.0 = top row
    /// (limbs hang and curl downward), 1.0 = bottom row (the spine — pelvis
    /// planted, shoulders sweep).
    bend_origin: f64,
}

/// Arc geometry of a bent parent, for mapping child attach points onto the
/// curved drawing: (bend radians, part length, origin row, pivot row) — all in
/// part-pixel units, unflipped part space.
type BendGeom = (f64, f64, f64, f64);

/// Map an attach offset `(ox, oy)` (relative to the parent's pivot) through the
/// parent's bend arc. Returns the displaced offset plus the tangent angle
/// (degrees) the child's frame inherits — this is what keeps the head riding a
/// curved spine instead of hovering where the straight drawing used to be.
fn bend_map_offset(ox: f64, oy: f64, geom: BendGeom) -> (f64, f64, f64) {
    let (bend, len, origin, pivot_row) = geom;
    if bend.abs() < 1e-4 || len <= 0.0 {
        return (ox, oy, 0.0);
    }
    let radius = len / bend;
    let s = (pivot_row + oy) - origin; // signed arc-length from the origin row
    let theta = (s / len) * bend;
    let mx = radius * (1.0 - theta.cos()) + ox * theta.cos();
    let my = (origin - pivot_row) + radius * theta.sin() + ox * theta.sin();
    (mx, my, theta.to_degrees())
}

/// Walk the bone tree computing world transforms (parent → child) and collect a
/// flat list of drawables. Drawing is deferred so the caller can sort by
/// `z_order` — the fix for limbs punching through the head/torso.
#[allow(clippy::too_many_arguments)]
fn collect_bone_drawables<'a>(
    bone: &skeleton::Bone,
    bone_states: &[BoneState],
    parts: &'a HashMap<String, skeleton::PartAsset>,
    parent_x: f64,
    parent_y: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    entity_scale_x: f64,
    entity_scale_y: f64,
    parent_rot: f64,
    parent_bend: Option<BendGeom>,
    out: &mut Vec<Drawable<'a>>,
) {
    // Find this bone's interpolated state.
    let state = bone_states.iter().find(|s| s.name == bone.name);

    let (offset_x, offset_y) = state.map(|s| s.offset).unwrap_or(bone.offset);
    let rotation = state.map(|s| s.rotation).unwrap_or(bone.rotation);
    let (scale_x, scale_y) = state.map(|s| s.scale).unwrap_or(bone.scale);

    // If the parent drawing is bent, this bone's attach point rides the arc.
    let (offset_x, offset_y, arc_rot) = match parent_bend {
        Some(geom) => bend_map_offset(offset_x, offset_y, geom),
        None => (offset_x, offset_y, 0.0),
    };

    // Compute world position of this bone.
    let rot_rad = parent_rot.to_radians();
    let rx = offset_x * rot_rad.cos() - offset_y * rot_rad.sin();
    let ry = offset_x * rot_rad.sin() + offset_y * rot_rad.cos();

    let mut world_x = parent_x + rx * scale * flip * entity_scale_x;
    let mut world_y = parent_y + ry * scale * entity_scale_y;
    let world_rot = parent_rot + (rotation + arc_rot) * flip;

    // Queue this bone's part if it has one. The state's part may be a pose
    // cel-swap (a different drawing); fall back to the bone's default part.
    // Also compute this bone's own bend so children can ride the arc.
    let mut child_bend: Option<BendGeom> = None;
    let mut draw_rot = world_rot;
    // Rotation frame the children build on: limbs pass the rigid world rot
    // (chord compensation is drawing-only), the spine passes its rest-based
    // frame — children pick up their share of the lean from the arc mapping.
    let mut child_rot = world_rot;
    let part_name = state.and_then(|s| s.part.as_ref()).or(bone.part.as_ref());
    if let Some(part_name) = part_name {
        if let Some(part) = parts.get(part_name) {
            // Rubber-hose: joints give part of their bend to a smooth curl
            // along the lower limb segment instead of a sharp hinge corner;
            // the spine curls from a procedural channel (sway, speech). All in
            // unflipped part space — flip is applied at draw/world composition.
            let delta_deg = rotation - bone.rotation;
            let is_spine = bone.name == "torso";
            let joint_bend = if bone.name.contains("forearm") || bone.name.contains("shin") {
                (delta_deg.to_radians() * 0.32).clamp(-0.55, 0.55)
            } else if is_spine {
                // The spine carries its WHOLE lean in the arc: turn grows
                // linearly from 0 at the pelvis to the full pose delta at the
                // shoulders. (Negative: rows above a bottom origin have
                // negative arc-length, so −δ yields +δ turn at the top.)
                -delta_deg.to_radians()
            } else {
                0.0
            };
            let bend_local = (joint_bend + state.map(|s| s.bend).unwrap_or(0.0)).clamp(-1.2, 1.2);
            // The spine bends from the pelvis up (feet stay planted, shoulders
            // sweep); limbs bend from their top joint down.
            let bend_origin = if is_spine { 1.0 } else { 0.0 };
            if is_spine {
                // The rigid rotation stays at rest — the arc does the leaning,
                // so the pelvis row never swings around the neck pivot.
                draw_rot = world_rot - delta_deg * flip;
                child_rot = draw_rot;
            } else {
                // Chord compensation: the arc's chord runs at (start tangent +
                // bend/2), so subtracting half the curl keeps the hand/foot
                // where the pose put it — the elbow/knee softens into a curve
                // but the silhouette of the gesture holds.
                draw_rot = world_rot - (bend_local * flip).to_degrees() * 0.5;
            }
            if bend_local.abs() > 1e-4 {
                child_bend = Some((
                    bend_local,
                    part.height.max(1.0),
                    bend_origin * part.height,
                    bone.pivot.1,
                ));
            }
            if std::env::var("ANIMDSL_DEBUG_BONES").is_ok() {
                eprintln!(
                    "BONE {} x={:.1} y={:.1} rot={:.1} draw_rot={:.1} bend={:.3} flip={} off=({:.1},{:.1}) arc_rot={:.2}",
                    bone.name, world_x, world_y, world_rot, draw_rot, bend_local, flip, offset_x, offset_y, arc_rot
                );
            }
            out.push(Drawable {
                part,
                x: world_x,
                y: world_y,
                sx: scale * scale_x * entity_scale_x,
                sy: scale * scale_y * entity_scale_y,
                rot: draw_rot,
                flip,
                opacity,
                pivot: bone.pivot,
                z_order: state.map(|s| s.z_order).unwrap_or(bone.z_order),
                bend: bend_local * flip,
                bend_origin,
            });
        }
    }

    // Recurse into children (their world transforms build on this bone's).
    for child in &bone.children {
        collect_bone_drawables(
            child,
            bone_states,
            parts,
            world_x,
            world_y,
            scale,
            flip,
            opacity,
            entity_scale_x * scale_x,
            entity_scale_y * scale_y,
            child_rot,
            child_bend,
            out,
        );
    }
}

/// Resolve the effective pose for a pose-event index. A full (non-overlay)
/// event resolves to its named pose. An overlay event (speech mouth flap)
/// resolves to the last held full pose with the overlay's bones merged on top,
/// so the body keeps its gesture while the mouth talks. `None` (before any
/// event) resolves to the rig's "idle" pose.
fn resolve_effective_pose(
    rig: &CharacterRig,
    events: &[&PoseEvent],
    idx: Option<usize>,
) -> Option<skeleton::Pose> {
    let idx = match idx {
        Some(i) => i,
        None => return rig.poses.get("idle").cloned(),
    };
    let ev = events.get(idx)?;
    let pose = rig.poses.get(&ev.pose)?;
    if !ev.overlay {
        return Some(pose.clone());
    }
    // Find the base: the most recent non-overlay event at or before this one.
    let base = events[..idx]
        .iter()
        .rev()
        .find(|e| !e.overlay)
        .and_then(|e| rig.poses.get(&e.pose))
        .or_else(|| rig.poses.get("idle"));
    match base {
        Some(base) => {
            let mut merged = base.clone();
            merged.transition_duration = pose.transition_duration;
            for (bone, bt) in &pose.bones {
                merged.bones.insert(bone.clone(), bt.clone());
            }
            Some(merged)
        }
        None => Some(pose.clone()),
    }
}

/// Ease-out-back: decelerates and overshoots slightly past the target before
/// settling — gives pose changes a snappy, hand-animated feel. t is clamped to
/// [0,1]; the returned value may exceed 1.0 briefly (the overshoot).
fn ease_out_back(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0);
    const C1: f64 = 1.30158;
    const C3: f64 = C1 + 1.0;
    let u = t - 1.0;
    1.0 + C3 * u * u * u + C1 * u * u
}

/// How strongly the character is speaking at time `t` (0..1), inferred from the
/// cluster of overlay mouth-flap events. Ramps smoothly at line boundaries so
/// the talking body-motion fades in/out instead of snapping.
fn speaking_intensity(events: &[&PoseEvent], t: f64) -> f64 {
    let mut s = 0.0;
    for e in events {
        if !e.overlay {
            continue;
        }
        let dt = (e.time - t).abs();
        if dt < 0.4 {
            s += 1.0 - dt / 0.4;
        }
    }
    (s * 0.5).clamp(0.0, 1.0)
}

/// Layer "talking body" motion onto the held pose while speaking: the head nods
/// and turns, the torso gives a little emphasis, and the left hand does a gentle
/// beat gesture. Additive and subtle — the pose still reads, but the delivery is
/// alive. `amt` (0..1) scales the whole thing by how strongly we're speaking.
fn apply_speaking_motion(states: &mut [BoneState], t: f64, amt: f64) {
    let tau = std::f64::consts::TAU;
    let nod = (t * 2.3 * tau).sin();
    for state in states.iter_mut() {
        match state.name.as_str() {
            "head" => {
                state.rotation += nod * 2.2 * amt;
                state.offset.1 += nod * 1.6 * amt;
                state.offset.0 += (t * 0.9 * tau).sin() * 1.2 * amt; // slight turn
            }
            "torso" => {
                state.rotation += nod * 0.5 * amt;
                // Speech pushes a wave through the spine: shoulders lean into
                // the phrase while the pelvis stays planted.
                state.bend += nod * 0.035 * amt;
            }
            "upper_arm_left" => {
                state.rotation += (t * 1.7 * tau).sin() * 3.5 * amt;
            }
            "forearm_left" => {
                state.rotation += (t * 1.7 * tau + 0.6).sin() * 5.0 * amt;
            }
            _ => {}
        }
    }
}

/// Plain ease-out (cubic), no overshoot — for tiny/fast transitions like mouth
/// flaps, where an overshoot or wind-up would look wrong.
fn ease_out_cubic(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0);
    let u = 1.0 - t;
    1.0 - u * u * u
}

/// Anticipation + overshoot: the hallmark of hand-drawn timing. The first ~30%
/// of the move winds up slightly AWAY from the target (extrapolating past the
/// held pose, hence the negative return), then it snaps forward and overshoots
/// before settling. Applied to larger gestures (not mouth flaps) so poses read
/// as struck, not slid — the biggest single step from "puppet" toward Freeman.
fn anticipate_back(t: f64) -> f64 {
    let t = t.clamp(0.0, 1.0);
    const ANTIC: f64 = 0.30; // fraction of the move spent winding up
    if t < ANTIC {
        let u = t / ANTIC; // 0→1 over the wind-up
        -0.10 * (4.0 * u * (1.0 - u)) // dips to ~-0.10 then back to 0
    } else {
        ease_out_back((t - ANTIC) / (1.0 - ANTIC))
    }
}

/// Swap every `seed="N"` in an SVG (feTurbulence) for the given boil seed, so
/// the ink filter's noise — and thus the rough hand-drawn edge — changes each
/// frame. A no-op for SVGs without a turbulence filter.
fn apply_boil(svg: &[u8], seed: u32) -> Vec<u8> {
    let s = match std::str::from_utf8(svg) {
        Ok(s) if s.contains("seed=\"") => s,
        _ => return svg.to_vec(),
    };
    let needle = "seed=\"";
    let mut out = String::with_capacity(s.len() + 8);
    let mut rest = s;
    while let Some(pos) = rest.find(needle) {
        out.push_str(&rest[..pos + needle.len()]);
        out.push_str(&seed.to_string());
        let after = &rest[pos + needle.len()..];
        // Skip the old value up to (but not including) the closing quote.
        match after.find('"') {
            Some(q) => rest = &after[q..],
            None => {
                rest = after;
                break;
            }
        }
    }
    out.push_str(rest);
    out.into_bytes()
}

/// Render a single bone's SVG part at the given world transform.
fn render_bone_part(
    part: &skeleton::PartAsset,
    pixmap: &mut Pixmap,
    world_x: f64,
    world_y: f64,
    scale_x: f64,
    scale_y: f64,
    rotation_deg: f64,
    flip: f64,
    opacity: f64,
    pivot: &(f64, f64),
    bend: f64,
    bend_origin: f64,
    boil_seed: u32,
) -> Result<(), AnimError> {
    let svg_data = apply_boil(&part.svg_data, boil_seed);
    let tree = parse_svg_cached(&svg_data)?;

    let render_sx = scale_x.abs() * flip.abs();
    let render_sy = scale_y.abs();

    let render_w = (part.width * render_sx).ceil() as u32;
    let render_h = (part.height * render_sy).ceil() as u32;

    if render_w == 0 || render_h == 0 {
        return Ok(());
    }

    let mut part_pixmap = Pixmap::new(render_w, render_h)
        .ok_or_else(|| AnimError::Render("failed to create part pixmap".into()))?;

    let render_transform = Transform::from_scale(render_sx as f32, render_sy as f32);
    resvg::render(&tree, render_transform, &mut part_pixmap.as_mut());

    // Flip horizontally if needed.
    if flip < 0.0 {
        flip_pixmap_horizontal(&mut part_pixmap);
    }

    // The pivot point in rendered pixel space.
    let pivot_px = pivot.0 * render_sx;
    let pivot_py = pivot.1 * render_sy;

    // Build the composite transform.
    let tx = world_x as f32;
    let ty = world_y as f32;
    let rot = rotation_deg as f32;

    let transform = Transform::from_translate(tx, ty)
        .pre_concat(Transform::from_rotate(rot))
        .pre_concat(Transform::from_translate(
            -pivot_px as f32,
            -pivot_py as f32,
        ));

    let paint = PixmapPaint {
        opacity: opacity as f32,
        ..Default::default()
    };

    if bend.abs() > 0.02 {
        // Deformable draw: bend the part along its length, so a limb curves
        // like a hand-drawn rubber-hose instead of a rigid segment.
        draw_bent_pixmap(
            pixmap,
            &part_pixmap,
            transform,
            pivot_px as f32,
            bend as f32,
            bend_origin as f32,
            &paint,
        );
    } else {
        pixmap.draw_pixmap(0, 0, part_pixmap.as_ref(), &paint, transform, None);
    }

    Ok(())
}

/// Draw a part pixmap bent into an arc below its pivot — the core of deformable
/// (Live2D/rubber-hose-style) rendering. The part is sliced into horizontal
/// strips; each strip is placed on a circular arc and rotated, so straight
/// pixels become a smooth curve. `base` maps part-pixel space to the frame;
/// `pivot_px` is the pivot column, `bend` the total curl (radians) over the
/// length below the pivot.
fn draw_bent_pixmap(
    target: &mut Pixmap,
    src: &Pixmap,
    base: Transform,
    pivot_px: f32,
    bend: f32,
    bend_origin: f32,
    paint: &PixmapPaint,
) {
    let w = src.width();
    let h = src.height();
    if w == 0 || h == 0 {
        return;
    }
    // Treat the source rows as signed arc-length along an inextensible "hose"
    // measured from the origin row (top for limbs, bottom for the spine): a
    // strip whose top is at source row y lands on a circular arc at that
    // arc-length, rotated by the tangent angle there. The formulas are odd/even
    // in the sign of s, so rows above the origin sweep the mirrored way —
    // exactly what a pelvis-anchored spine needs. Anchoring each strip by its
    // TOP edge (not centre) makes consecutive strips join continuously; a 1px
    // sampling overlap hides the residual gap from using a single angle across
    // a strip's own height.
    let len = (h as f32).max(1.0);
    let origin_row = bend_origin * h as f32;
    let radius = len / bend; // signed arc radius
    // Fine strips (~2px) → the arc reads as a smooth curve, not facets.
    let strips = (h / 2).clamp(8, 48);
    let src_data = src.data();
    let sw = w as usize;
    // Point + tangent angle (deg) at source row y (arc-length s = y - origin).
    let arc = |y: f32| -> (f32, f32, f32) {
        let s = y - origin_row;
        if bend.abs() < 1e-3 {
            return (0.0, y, 0.0);
        }
        let theta = (s / len) * bend; // radians turned at this arc-length
        (
            radius * (1.0 - theta.cos()),
            origin_row + radius * theta.sin(),
            theta.to_degrees(),
        )
    };
    for i in 0..strips {
        let y0 = (i * h / strips).min(h);
        // Sample one extra row past the nominal bottom so strips overlap and
        // leave no seam on the convex side of the curve.
        let y1 = (((i + 1) * h / strips) + 1).min(h);
        if y1 <= y0 {
            continue;
        }
        let sh = y1 - y0;
        let mut strip = match Pixmap::new(w, sh) {
            Some(p) => p,
            None => continue,
        };
        let start = (y0 as usize) * sw * 4;
        let n = (sh as usize) * sw * 4;
        strip.data_mut().copy_from_slice(&src_data[start..start + n]);

        // Anchor the strip's TOP edge (source row y0) onto the arc.
        let (ax, ay, ang_deg) = arc(y0 as f32);
        // Strip-local: its pixel (pivot_px, 0) is the top-anchor; move it to the
        // arc point and rotate the strip by the tangent angle there.
        let strip_local = Transform::from_translate(pivot_px + ax, ay)
            .pre_concat(Transform::from_rotate(ang_deg))
            .pre_concat(Transform::from_translate(-pivot_px, 0.0));
        let t = base.pre_concat(strip_local);
        target.draw_pixmap(0, 0, strip.as_ref(), paint, t, None);
    }
}

// ---------------------------------------------------------------------------
// Pose interpolation helpers
// ---------------------------------------------------------------------------

/// Get the current pose interpolation state for an entity at time t.
/// Returns (from_pose_name, to_pose_name, interpolation_t).
fn get_pose_interpolation<'a>(
    timeline: &'a Timeline,
    entity_name: &str,
    t: f64,
) -> (Option<&'a str>, Option<&'a str>, f64) {
    let events: Vec<&PoseEvent> = timeline
        .pose_events
        .iter()
        .filter(|e| e.entity == entity_name)
        .collect();

    if events.is_empty() {
        return (Some("idle"), Some("idle"), 1.0);
    }

    // Find the most recent pose event at or before time t.
    let mut current_idx = None;
    for (i, event) in events.iter().enumerate() {
        if event.time <= t {
            current_idx = Some(i);
        }
    }

    match current_idx {
        None => {
            // Before any pose event — use idle.
            (Some("idle"), Some(events[0].pose.as_str()), 0.0)
        }
        Some(idx) => {
            let current = &events[idx];
            let transition_dur = 0.3; // default pose transition duration
            let elapsed = t - current.time;

            if elapsed >= transition_dur {
                // Fully transitioned.
                (
                    Some(current.pose.as_str()),
                    Some(current.pose.as_str()),
                    1.0,
                )
            } else {
                // Mid-transition.
                let prev_pose = if idx > 0 {
                    events[idx - 1].pose.as_str()
                } else {
                    "idle"
                };
                let progress = elapsed / transition_dur;
                (Some(prev_pose), Some(current.pose.as_str()), progress)
            }
        }
    }
}

/// Compute the velocity of an entity at time t (for walk detection).
fn compute_velocity(timeline: &Timeline, entity_name: &str, t: f64) -> (f64, f64) {
    let dt = 0.05; // sample interval
    let t0 = (t - dt).max(0.0);
    let t1 = t;

    let mut x0 = 0.5;
    let mut y0 = 0.5;
    let mut x1 = 0.5;
    let mut y1 = 0.5;

    for track in &timeline.tracks {
        if track.entity != entity_name {
            continue;
        }
        match track.property {
            Property::X => {
                x0 = evaluate_track(track, t0);
                x1 = evaluate_track(track, t1);
            }
            Property::Y => {
                y0 = evaluate_track(track, t0);
                y1 = evaluate_track(track, t1);
            }
            _ => {}
        }
    }

    let actual_dt = t1 - t0;
    if actual_dt > 0.001 {
        ((x1 - x0) / actual_dt, (y1 - y0) / actual_dt)
    } else {
        (0.0, 0.0)
    }
}

// ---------------------------------------------------------------------------
// Legacy SVG rendering (for sets, props, and legacy characters)
// ---------------------------------------------------------------------------

fn render_svg_to_pixmap(
    svg_data: &[u8],
    pixmap: &mut Pixmap,
    canvas_w: u32,
    canvas_h: u32,
    norm_x: f64,
    norm_y: f64,
    scale_x: f64,
    scale_y: f64,
    rotation_deg: f64,
    opacity: f64,
    camera: &CameraKeyframe,
    is_background: bool,
) -> Result<(), AnimError> {
    let tree = parse_svg_cached(svg_data)?;

    let svg_size = tree.size();
    let svg_w = svg_size.width() as f64;
    let svg_h = svg_size.height() as f64;

    let cw = canvas_w as f64;
    let ch = canvas_h as f64;

    let (base_scale_x, base_scale_y, px, py) = if is_background {
        // Set fills the scene [0,1]×[0,1]; it must track the camera so that
        // when the camera pans/zooms to a character, the location follows
        // (otherwise the character floats off a detailed set). A flat uniform
        // background looks identical either way, so this is safe for Freeman's
        // white-field grammar and correct for detailed establishing shots.
        let sx = cw / svg_w;
        let sy = ch / svg_h;
        let s = sx.max(sy) * camera.zoom;
        let px = ((0.5 - camera.x) * camera.zoom + 0.5) * cw;
        let py = ((0.5 - camera.y) * camera.zoom + 0.5) * ch;
        (s, s, px, py)
    } else {
        let target_height = ch * 0.3;
        let base = target_height / svg_h;
        let cam_x = camera.x;
        let cam_y = camera.y;
        let zoom = camera.zoom;
        let screen_x = ((norm_x - cam_x) * zoom + 0.5) * cw;
        let screen_y = ((norm_y - cam_y) * zoom + 0.5) * ch;
        (base * zoom, base * zoom, screen_x, screen_y)
    };

    let final_scale_x = base_scale_x * scale_x;
    let final_scale_y = base_scale_y * scale_y;

    let render_w = (svg_w * final_scale_x.abs()).ceil() as u32;
    let render_h = (svg_h * final_scale_y.abs()).ceil() as u32;

    if render_w == 0 || render_h == 0 {
        return Ok(());
    }

    // Reuse the rasterised pixmap when identical bytes render at the same size
    // and flip — under a held camera, that's every frame of the shot.
    let flip_bg = final_scale_x < 0.0;
    let pkey = {
        let mut h = DefaultHasher::new();
        svg_data.hash(&mut h);
        render_w.hash(&mut h);
        render_h.hash(&mut h);
        flip_bg.hash(&mut h);
        h.finish()
    };
    let svg_pixmap: Arc<Pixmap> =
        if let Some(p) = PIXMAP_CACHE.with(|c| c.borrow().get(&pkey).cloned()) {
            p
        } else {
            let mut pm = Pixmap::new(render_w, render_h)
                .ok_or_else(|| AnimError::Render("failed to create SVG pixmap".into()))?;
            let render_transform =
                Transform::from_scale(final_scale_x.abs() as f32, final_scale_y.abs() as f32);
            resvg::render(&tree, render_transform, &mut pm.as_mut());
            if flip_bg {
                flip_pixmap_horizontal(&mut pm);
            }
            let arc = Arc::new(pm);
            PIXMAP_CACHE.with(|c| {
                let mut m = c.borrow_mut();
                if m.len() > 96 {
                    m.clear();
                }
                m.insert(pkey, arc.clone());
            });
            arc
        };

    let dest_x = px - (render_w as f64 / 2.0);
    let dest_y = py - (render_h as f64 / 2.0);

    let transform = if rotation_deg.abs() > 0.01 {
        let cx = dest_x + render_w as f64 / 2.0;
        let cy = dest_y + render_h as f64 / 2.0;
        Transform::from_translate(cx as f32, cy as f32)
            .pre_concat(Transform::from_rotate(rotation_deg as f32))
            .pre_concat(Transform::from_translate(-(cx as f32), -(cy as f32)))
            .pre_concat(Transform::from_translate(dest_x as f32, dest_y as f32))
    } else {
        Transform::from_translate(dest_x as f32, dest_y as f32)
    };

    let paint = PixmapPaint {
        opacity: opacity as f32,
        ..Default::default()
    };

    let pm: &Pixmap = &svg_pixmap;
    pixmap.draw_pixmap(0, 0, pm.as_ref(), &paint, transform, None);

    Ok(())
}

fn flip_pixmap_horizontal(pixmap: &mut Pixmap) {
    let w = pixmap.width() as usize;
    let h = pixmap.height() as usize;
    let data = pixmap.data_mut();

    for y in 0..h {
        for x in 0..w / 2 {
            let left = (y * w + x) * 4;
            let right = (y * w + (w - 1 - x)) * 4;
            for c in 0..4 {
                data.swap(left + c, right + c);
            }
        }
    }
}

fn apply_transitions(
    pixmap: &mut Pixmap,
    transitions: &[crate::timeline::TransitionEvent],
    t: f64,
) -> Result<(), AnimError> {
    for tr in transitions {
        let tr_start = tr.time;
        let tr_end = tr.time + tr.duration;
        if t < tr_start || t > tr_end {
            continue;
        }
        let progress = if tr.duration > 0.0 {
            (t - tr_start) / tr.duration
        } else {
            1.0
        };

        match &tr.kind {
            TransitionKind::FadeBlack => {
                let overlay_alpha = (progress * 255.0) as u8;
                draw_color_overlay(pixmap, 0, 0, 0, overlay_alpha);
            }
            TransitionKind::FadeWhite => {
                let overlay_alpha = (progress * 255.0) as u8;
                draw_color_overlay(pixmap, 255, 255, 255, overlay_alpha);
            }
            TransitionKind::Cut => {
                if progress >= 1.0 {
                    pixmap.fill(SkiaColor::from_rgba8(0, 0, 0, 255));
                }
            }
            TransitionKind::Dissolve => {
                let overlay_alpha = (progress * 255.0) as u8;
                draw_color_overlay(pixmap, 0, 0, 0, overlay_alpha);
            }
            TransitionKind::Wipe(direction) => {
                let w = pixmap.width() as f64;
                let h = pixmap.height() as f64;
                let (rx, ry, rw, rh) = match direction {
                    Direction::Left => (0.0, 0.0, w * progress, h),
                    Direction::Right => (w * (1.0 - progress), 0.0, w * progress, h),
                    Direction::Up => (0.0, 0.0, w, h * progress),
                    Direction::Down => (0.0, h * (1.0 - progress), w, h * progress),
                    // front/back aren't spatial wipe directions — wipe left-to-right.
                    Direction::Front | Direction::Back => (0.0, 0.0, w * progress, h),
                };
                if let Some(rect) = Rect::from_xywh(rx as f32, ry as f32, rw as f32, rh as f32) {
                    let mut paint = Paint::default();
                    paint.set_color(SkiaColor::from_rgba8(0, 0, 0, 255));
                    pixmap.fill_rect(rect, &paint, Transform::identity(), None);
                }
            }
        }
    }
    Ok(())
}

fn draw_color_overlay(pixmap: &mut Pixmap, r: u8, g: u8, b: u8, a: u8) {
    if a == 0 {
        return;
    }
    let w = pixmap.width();
    let h = pixmap.height();
    if let Some(_rect) = Rect::from_xywh(0.0, 0.0, w as f32, h as f32) {
        let mut overlay = Pixmap::new(w, h).unwrap();
        overlay.fill(SkiaColor::from_rgba8(r, g, b, a));
        let paint = PixmapPaint {
            opacity: 1.0,
            ..Default::default()
        };
        pixmap.draw_pixmap(0, 0, overlay.as_ref(), &paint, Transform::identity(), None);
    }
}
