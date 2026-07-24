//! Renderer — evaluates the timeline at each frame and composites 2D entities
//! into pixel buffers using tiny-skia and resvg.
//!
//! Supports both legacy single-SVG characters and new rig-based characters
//! with per-bone part compositing and procedural animation.

use std::collections::HashMap;

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
    // Determine current and previous pose, and interpolation progress.
    let (from_pose_name, to_pose_name, pose_t) = get_pose_interpolation(timeline, entity_name, t);

    let from_pose = from_pose_name.and_then(|n| rig.poses.get(n));
    let to_pose = to_pose_name.and_then(|n| rig.poses.get(n));

    let _transition_dur = to_pose.map(|p| p.transition_duration).unwrap_or(0.3);

    // Ease pose transitions with a slight overshoot ("ease-out-back") so gestures
    // snap and settle like hand-drawn animation instead of sliding linearly.
    let eased_t = ease_out_back(pose_t);

    // Get interpolated bone states.
    let mut bone_states = interpolate_skeleton(&rig.skeleton, from_pose, to_pose, eased_t);

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
    apply_squash_stretch(&mut bone_states, velocity.1);

    // Sort bones by z_order for correct draw order.
    bone_states.sort_by_key(|b| b.z_order);

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
    let boil_seed = (t * 9.0) as i64;
    let boil_seed = boil_seed.rem_euclid(4096) as u32 + 1;

    // Render each bone part.
    render_bone_tree(
        &rig.skeleton.root,
        &bone_states,
        &rig.parts,
        pixmap,
        screen_x,
        screen_y,
        char_scale,
        flip,
        state.opacity,
        state.scale_x,
        state.scale_y,
        0.0, // parent rotation accumulator
        boil_seed,
    )?;

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
fn render_bone_tree(
    bone: &skeleton::Bone,
    bone_states: &[BoneState],
    parts: &HashMap<String, skeleton::PartAsset>,
    pixmap: &mut Pixmap,
    parent_x: f64,
    parent_y: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    entity_scale_x: f64,
    entity_scale_y: f64,
    parent_rot: f64,
    boil_seed: u32,
) -> Result<(), AnimError> {
    // Find this bone's interpolated state.
    let state = bone_states.iter().find(|s| s.name == bone.name);

    let (offset_x, offset_y) = state.map(|s| s.offset).unwrap_or(bone.offset);
    let rotation = state.map(|s| s.rotation).unwrap_or(bone.rotation);
    let (scale_x, scale_y) = state.map(|s| s.scale).unwrap_or(bone.scale);

    // Compute world position of this bone.
    let rot_rad = parent_rot.to_radians();
    let rx = offset_x * rot_rad.cos() - offset_y * rot_rad.sin();
    let ry = offset_x * rot_rad.sin() + offset_y * rot_rad.cos();

    let world_x = parent_x + rx * scale * flip * entity_scale_x;
    let world_y = parent_y + ry * scale * entity_scale_y;
    let world_rot = parent_rot + rotation * flip;

    // Render this bone's part if it has one.
    if let Some(ref part_name) = bone.part {
        if let Some(part) = parts.get(part_name) {
            render_bone_part(
                part,
                pixmap,
                world_x,
                world_y,
                scale * scale_x * entity_scale_x,
                scale * scale_y * entity_scale_y,
                world_rot,
                flip,
                opacity,
                &bone.pivot,
                boil_seed,
            )?;
        }
    }

    // Render children.
    for child in &bone.children {
        render_bone_tree(
            child,
            bone_states,
            parts,
            pixmap,
            world_x,
            world_y,
            scale,
            flip,
            opacity,
            entity_scale_x * scale_x,
            entity_scale_y * scale_y,
            world_rot,
            boil_seed,
        )?;
    }

    Ok(())
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
    boil_seed: u32,
) -> Result<(), AnimError> {
    let opts = usvg::Options::default();
    let svg_data = apply_boil(&part.svg_data, boil_seed);
    let tree = usvg::Tree::from_data(&svg_data, &opts)
        .map_err(|e| AnimError::Render(format!("SVG parse error: {e}")))?;

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

    pixmap.draw_pixmap(0, 0, part_pixmap.as_ref(), &paint, transform, None);

    Ok(())
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
    let opts = usvg::Options::default();
    let tree = usvg::Tree::from_data(svg_data, &opts)
        .map_err(|e| AnimError::Render(format!("SVG parse error: {e}")))?;

    let svg_size = tree.size();
    let svg_w = svg_size.width() as f64;
    let svg_h = svg_size.height() as f64;

    let cw = canvas_w as f64;
    let ch = canvas_h as f64;

    let (base_scale_x, base_scale_y, px, py) = if is_background {
        let sx = cw / svg_w;
        let sy = ch / svg_h;
        let s = sx.max(sy);
        (s, s, cw / 2.0, ch / 2.0)
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

    let mut svg_pixmap = Pixmap::new(render_w, render_h)
        .ok_or_else(|| AnimError::Render("failed to create SVG pixmap".into()))?;

    let render_transform =
        Transform::from_scale(final_scale_x.abs() as f32, final_scale_y.abs() as f32);

    resvg::render(&tree, render_transform, &mut svg_pixmap.as_mut());

    if final_scale_x < 0.0 {
        flip_pixmap_horizontal(&mut svg_pixmap);
    }

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

    pixmap.draw_pixmap(0, 0, svg_pixmap.as_ref(), &paint, transform, None);

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
