//! Timeline compiler — transforms scene statements into a flat list of
//! keyframe tracks that can be evaluated at any time `t`.

use std::collections::HashMap;

use crate::ast::*;
use crate::errors::AnimError;
use crate::scene::{resolve_position, EntityState, ResolvedScene};

/// A compiled timeline for one scene.
#[derive(Debug)]
pub struct Timeline {
    pub duration: f64,
    pub tracks: Vec<Track>,
    pub pose_events: Vec<PoseEvent>,
    pub camera_track: CameraTrack,
    pub transitions: Vec<TransitionEvent>,
}

/// A track of keyframes for a single entity property.
#[derive(Debug, Clone)]
pub struct Track {
    pub entity: String,
    pub property: Property,
    pub keyframes: Vec<Keyframe>,
}

/// The animatable properties.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Property {
    X,
    Y,
    ScaleX,
    ScaleY,
    Rotation,
    Opacity,
}

/// A single keyframe: at time `t`, the value is `value`, interpolated with `easing`.
#[derive(Debug, Clone)]
pub struct Keyframe {
    pub time: f64,
    pub value: f64,
    pub easing: Easing,
}

/// Pose changes are discrete (not interpolated).
#[derive(Debug, Clone)]
pub struct PoseEvent {
    pub time: f64,
    pub entity: String,
    pub pose: String,
}

/// Camera keyframes.
#[derive(Debug)]
pub struct CameraTrack {
    pub keyframes: Vec<CameraKeyframe>,
}

#[derive(Debug, Clone)]
pub struct CameraKeyframe {
    pub time: f64,
    /// Camera center in normalized coords.
    pub x: f64,
    pub y: f64,
    /// Zoom level (1.0 = full scene visible).
    pub zoom: f64,
    pub easing: Easing,
    /// Optional shake intensity (0 = no shake).
    pub shake: f64,
}

/// Transition events (fade-black, dissolve, etc.).
#[derive(Debug, Clone)]
pub struct TransitionEvent {
    pub time: f64,
    pub kind: TransitionKind,
    pub duration: f64,
}

#[derive(Debug, Clone)]
pub enum TransitionKind {
    FadeBlack,
    FadeWhite,
    Cut,
    Dissolve,
    Wipe(Direction),
}

/// Compile a resolved scene into a timeline.
pub fn compile(scene: &ResolvedScene) -> Result<Timeline, AnimError> {
    let mut compiler = TimelineCompiler {
        time: 0.0,
        tracks: HashMap::new(),
        pose_events: Vec::new(),
        camera_keyframes: vec![CameraKeyframe {
            time: 0.0,
            x: 0.5,
            y: 0.5,
            zoom: 1.0,
            easing: Easing::Linear,
            shake: 0.0,
        }],
        transitions: Vec::new(),
        entities: scene.entities.clone(),
    };

    compiler.compile_statements(&scene.statements)?;

    // Convert the tracks HashMap into a Vec<Track>.
    let tracks = compiler
        .tracks
        .into_iter()
        .flat_map(|(entity, props)| {
            props.into_iter().map(move |(property, keyframes)| Track {
                entity: entity.clone(),
                property,
                keyframes,
            })
        })
        .collect();

    // Use the longer of the declared duration or the actual action timeline.
    let actual_duration = compiler.time;
    let duration = scene.duration.max(actual_duration);

    Ok(Timeline {
        duration,
        tracks,
        pose_events: compiler.pose_events,
        camera_track: CameraTrack {
            keyframes: compiler.camera_keyframes,
        },
        transitions: compiler.transitions,
    })
}

struct TimelineCompiler {
    time: f64,
    /// entity -> property -> keyframes
    tracks: HashMap<String, HashMap<Property, Vec<Keyframe>>>,
    pose_events: Vec<PoseEvent>,
    camera_keyframes: Vec<CameraKeyframe>,
    transitions: Vec<TransitionEvent>,
    entities: HashMap<String, EntityState>,
}

impl TimelineCompiler {
    fn compile_statements(&mut self, stmts: &[SceneStatement]) -> Result<(), AnimError> {
        for stmt in stmts {
            self.compile_statement(stmt)?;
        }
        Ok(())
    }

    fn compile_statement(&mut self, stmt: &SceneStatement) -> Result<(), AnimError> {
        match stmt {
            SceneStatement::Place(_) => {
                // Already handled during scene resolution.
                Ok(())
            }
            SceneStatement::Wait(dur) => {
                self.time += dur.as_secs();
                Ok(())
            }
            SceneStatement::Action(action) => self.compile_action(action),
            SceneStatement::Together(stmts) => {
                // All statements in a together block start at the same time.
                let start_time = self.time;
                let mut max_end = self.time;
                for s in stmts {
                    self.time = start_time;
                    self.compile_statement(s)?;
                    max_end = max_end.max(self.time);
                }
                self.time = max_end;
                Ok(())
            }
            SceneStatement::Do(stmts) => {
                // Sequential — just compile each in order.
                self.compile_statements(stmts)
            }
            SceneStatement::Camera(cam) => self.compile_camera(cam),
            SceneStatement::Transition(tr) => self.compile_transition(tr),
            SceneStatement::Let(_) => {
                // Let bindings are handled during asset loading.
                Ok(())
            }
        }
    }

    fn compile_action(&mut self, action: &ActionStmt) -> Result<(), AnimError> {
        match action {
            ActionStmt::MoveTo {
                entity,
                target,
                duration,
                easing,
            } => {
                let (tx, ty) = resolve_position(target, &self.entities)?;
                let easing = easing.unwrap_or(Easing::EaseInOut);
                let dur = duration.as_secs();

                self.ensure_current_keyframe(entity, Property::X);
                self.ensure_current_keyframe(entity, Property::Y);

                self.add_keyframe(entity, Property::X, self.time + dur, tx, easing);
                self.add_keyframe(entity, Property::Y, self.time + dur, ty, easing);

                // Update entity state.
                if let Some(e) = self.entities.get_mut(entity) {
                    e.x = tx;
                    e.y = ty;
                }

                self.time += dur;
            }
            ActionStmt::Pose { entity, pose } => {
                self.pose_events.push(PoseEvent {
                    time: self.time,
                    entity: entity.clone(),
                    pose: pose.clone(),
                });
                if let Some(e) = self.entities.get_mut(entity) {
                    e.pose = pose.clone();
                }
            }
            ActionStmt::Show {
                entity,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.3);
                let easing = easing.unwrap_or(Easing::EaseIn);

                self.ensure_current_keyframe(entity, Property::Opacity);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 1.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.opacity = 1.0;
                    e.visible = true;
                }

                self.time += dur;
            }
            ActionStmt::Hide {
                entity,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.3);
                let easing = easing.unwrap_or(Easing::EaseOut);

                self.ensure_current_keyframe(entity, Property::Opacity);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 0.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.opacity = 0.0;
                }

                self.time += dur;
            }
            ActionStmt::Enter {
                entity,
                from,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(1.0);
                let easing = easing.unwrap_or(Easing::EaseOut);

                // Auto-register entity if not already placed.
                if !self.entities.contains_key(entity) {
                    self.entities.insert(
                        entity.clone(),
                        crate::scene::EntityState::new_character(entity),
                    );
                }

                // Start off-screen, move to current position.
                let target_x = self.entities.get(entity).map(|e| e.x).unwrap_or(0.5);
                let target_y = self.entities.get(entity).map(|e| e.y).unwrap_or(0.5);

                let (start_x, start_y) = match from {
                    Direction::Left => (-0.2, target_y),
                    Direction::Right => (1.2, target_y),
                    Direction::Up => (target_x, -0.2),
                    Direction::Down => (target_x, 1.2),
                };

                // Set start position.
                self.set_keyframe(entity, Property::X, self.time, start_x, Easing::Linear);
                self.set_keyframe(entity, Property::Y, self.time, start_y, Easing::Linear);
                self.set_keyframe(entity, Property::Opacity, self.time, 0.0, Easing::Linear);

                // Animate to target.
                self.add_keyframe(entity, Property::X, self.time + dur, target_x, easing);
                self.add_keyframe(entity, Property::Y, self.time + dur, target_y, easing);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 1.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.x = target_x;
                    e.y = target_y;
                    e.opacity = 1.0;
                    e.visible = true;
                }

                self.time += dur;
            }
            ActionStmt::Exit {
                entity,
                to,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(1.0);
                let easing = easing.unwrap_or(Easing::EaseIn);

                let current_x = self.entities.get(entity).map(|e| e.x).unwrap_or(0.5);
                let current_y = self.entities.get(entity).map(|e| e.y).unwrap_or(0.5);

                let (end_x, end_y) = match to {
                    Direction::Left => (-0.2, current_y),
                    Direction::Right => (1.2, current_y),
                    Direction::Up => (current_x, -0.2),
                    Direction::Down => (current_x, 1.2),
                };

                self.ensure_current_keyframe(entity, Property::X);
                self.ensure_current_keyframe(entity, Property::Y);
                self.ensure_current_keyframe(entity, Property::Opacity);

                self.add_keyframe(entity, Property::X, self.time + dur, end_x, easing);
                self.add_keyframe(entity, Property::Y, self.time + dur, end_y, easing);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 0.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.x = end_x;
                    e.y = end_y;
                    e.opacity = 0.0;
                }

                self.time += dur;
            }
            ActionStmt::Scale {
                entity,
                factor,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.5);
                let easing = easing.unwrap_or(Easing::EaseInOut);

                self.ensure_current_keyframe(entity, Property::ScaleX);
                self.ensure_current_keyframe(entity, Property::ScaleY);

                self.add_keyframe(entity, Property::ScaleX, self.time + dur, *factor, easing);
                self.add_keyframe(entity, Property::ScaleY, self.time + dur, *factor, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.scale_x = *factor;
                    e.scale_y = *factor;
                }

                self.time += dur;
            }
            ActionStmt::Rotate {
                entity,
                angle,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.5);
                let easing = easing.unwrap_or(Easing::EaseInOut);

                self.ensure_current_keyframe(entity, Property::Rotation);
                self.add_keyframe(entity, Property::Rotation, self.time + dur, *angle, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.rotation = *angle;
                }

                self.time += dur;
            }
            ActionStmt::FadeTo {
                entity,
                opacity,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.5);
                let easing = easing.unwrap_or(Easing::EaseInOut);

                self.ensure_current_keyframe(entity, Property::Opacity);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, *opacity, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.opacity = *opacity;
                }

                self.time += dur;
            }
        }
        Ok(())
    }

    fn compile_camera(&mut self, cam: &CameraStmt) -> Result<(), AnimError> {
        match cam {
            CameraStmt::ShotType { shot, target } => {
                let (x, y, zoom) = match shot {
                    ShotType::Wide => (0.5, 0.5, 1.0),
                    ShotType::Medium => {
                        if let Some(name) = target {
                            let e = self.entities.get(name).ok_or_else(|| {
                                AnimError::Timeline(format!("unknown entity: {name}"))
                            })?;
                            (e.x, e.y, 1.5)
                        } else {
                            (0.5, 0.5, 1.5)
                        }
                    }
                    ShotType::CloseUp => {
                        if let Some(name) = target {
                            let e = self.entities.get(name).ok_or_else(|| {
                                AnimError::Timeline(format!("unknown entity: {name}"))
                            })?;
                            (e.x, e.y - 0.1, 2.5) // slightly above center for face
                        } else {
                            (0.5, 0.4, 2.5)
                        }
                    }
                    ShotType::ExtremeCloseUp => {
                        if let Some(name) = target {
                            let e = self.entities.get(name).ok_or_else(|| {
                                AnimError::Timeline(format!("unknown entity: {name}"))
                            })?;
                            (e.x, e.y - 0.15, 4.0)
                        } else {
                            (0.5, 0.35, 4.0)
                        }
                    }
                    ShotType::TwoShot => (0.5, 0.5, 1.2),
                    ShotType::OverShoulder => (0.5, 0.45, 1.8),
                };

                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x,
                    y,
                    zoom,
                    easing: Easing::EaseInOut,
                    shake: 0.0,
                });
            }
            CameraStmt::ZoomTo {
                target,
                duration,
                easing,
            } => {
                let e = self
                    .entities
                    .get(target)
                    .ok_or_else(|| AnimError::Timeline(format!("unknown entity: {target}")))?;
                let dur = duration.as_secs();
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x: e.x,
                    y: e.y - 0.1,
                    zoom: 2.5,
                    easing: easing.unwrap_or(Easing::EaseInOut),
                    shake: 0.0,
                });
                self.time += dur;
            }
            CameraStmt::PanTo {
                target,
                duration,
                easing,
            } => {
                let (x, y) = match target {
                    PanTarget::Entity(name) => {
                        let e = self.entities.get(name).ok_or_else(|| {
                            AnimError::Timeline(format!("unknown entity: {name}"))
                        })?;
                        (e.x, e.y)
                    }
                    PanTarget::Position(pos) => resolve_position(pos, &self.entities)?,
                };
                let dur = duration.as_secs();
                // Keep same zoom level as last camera keyframe.
                let last_zoom = self.camera_keyframes.last().map(|k| k.zoom).unwrap_or(1.0);
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x,
                    y,
                    zoom: last_zoom,
                    easing: easing.unwrap_or(Easing::EaseInOut),
                    shake: 0.0,
                });
                self.time += dur;
            }
            CameraStmt::Shake {
                duration,
                intensity,
            } => {
                let dur = duration.as_secs();
                let last = self
                    .camera_keyframes
                    .last()
                    .cloned()
                    .unwrap_or(CameraKeyframe {
                        time: 0.0,
                        x: 0.5,
                        y: 0.5,
                        zoom: 1.0,
                        easing: Easing::Linear,
                        shake: 0.0,
                    });

                // Start shake.
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x: last.x,
                    y: last.y,
                    zoom: last.zoom,
                    easing: Easing::Linear,
                    shake: *intensity,
                });

                // End shake.
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x: last.x,
                    y: last.y,
                    zoom: last.zoom,
                    easing: Easing::Linear,
                    shake: 0.0,
                });

                self.time += dur;
            }
            CameraStmt::Reset { duration } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.0);
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x: 0.5,
                    y: 0.5,
                    zoom: 1.0,
                    easing: Easing::EaseInOut,
                    shake: 0.0,
                });
                self.time += dur;
            }
        }
        Ok(())
    }

    fn compile_transition(&mut self, tr: &TransitionStmt) -> Result<(), AnimError> {
        let (kind, dur) = match tr {
            TransitionStmt::FadeBlack(d) => (TransitionKind::FadeBlack, d.as_secs()),
            TransitionStmt::FadeWhite(d) => (TransitionKind::FadeWhite, d.as_secs()),
            TransitionStmt::Cut => (TransitionKind::Cut, 0.0),
            TransitionStmt::Dissolve(d) => (TransitionKind::Dissolve, d.as_secs()),
            TransitionStmt::Wipe {
                direction,
                duration,
            } => (TransitionKind::Wipe(*direction), duration.as_secs()),
        };

        self.transitions.push(TransitionEvent {
            time: self.time,
            kind,
            duration: dur,
        });

        self.time += dur;
        Ok(())
    }

    // -----------------------------------------------------------------------
    // Keyframe helpers
    // -----------------------------------------------------------------------

    fn ensure_current_keyframe(&mut self, entity: &str, property: Property) {
        // Read the current value first, before borrowing tracks mutably.
        let value = self.get_entity_property(entity, property);
        let time = self.time;

        let props = self
            .tracks
            .entry(entity.to_string())
            .or_insert_with(HashMap::new);
        let keyframes = props.entry(property).or_insert_with(Vec::new);

        if keyframes.is_empty() {
            keyframes.push(Keyframe {
                time,
                value,
                easing: Easing::Linear,
            });
        }
    }

    fn add_keyframe(
        &mut self,
        entity: &str,
        property: Property,
        time: f64,
        value: f64,
        easing: Easing,
    ) {
        let props = self
            .tracks
            .entry(entity.to_string())
            .or_insert_with(HashMap::new);
        let keyframes = props.entry(property).or_insert_with(Vec::new);
        keyframes.push(Keyframe {
            time,
            value,
            easing,
        });
    }

    fn set_keyframe(
        &mut self,
        entity: &str,
        property: Property,
        time: f64,
        value: f64,
        easing: Easing,
    ) {
        let props = self
            .tracks
            .entry(entity.to_string())
            .or_insert_with(HashMap::new);
        let keyframes = props.entry(property).or_insert_with(Vec::new);
        keyframes.push(Keyframe {
            time,
            value,
            easing,
        });
    }

    fn get_entity_property(&self, entity: &str, property: Property) -> f64 {
        if let Some(e) = self.entities.get(entity) {
            match property {
                Property::X => e.x,
                Property::Y => e.y,
                Property::ScaleX => e.scale_x,
                Property::ScaleY => e.scale_y,
                Property::Rotation => e.rotation,
                Property::Opacity => e.opacity,
            }
        } else {
            match property {
                Property::Opacity => 1.0,
                Property::ScaleX | Property::ScaleY => 1.0,
                _ => 0.0,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Evaluation — sample the timeline at a given time `t`
// ---------------------------------------------------------------------------

/// Evaluate a single property track at time `t`.
pub fn evaluate_track(track: &Track, t: f64) -> f64 {
    let kfs = &track.keyframes;
    if kfs.is_empty() {
        return 0.0;
    }
    if kfs.len() == 1 || t <= kfs[0].time {
        return kfs[0].value;
    }
    if t >= kfs.last().unwrap().time {
        return kfs.last().unwrap().value;
    }

    // Find the two surrounding keyframes.
    for i in 0..kfs.len() - 1 {
        if t >= kfs[i].time && t < kfs[i + 1].time {
            let dt = kfs[i + 1].time - kfs[i].time;
            if dt == 0.0 {
                return kfs[i + 1].value;
            }
            let progress = (t - kfs[i].time) / dt;
            let eased = apply_easing(progress, kfs[i + 1].easing);
            return lerp(kfs[i].value, kfs[i + 1].value, eased);
        }
    }

    kfs.last().unwrap().value
}

/// Evaluate the camera state at time `t`.
pub fn evaluate_camera(camera_track: &CameraTrack, t: f64) -> CameraKeyframe {
    let kfs = &camera_track.keyframes;
    if kfs.is_empty() {
        return CameraKeyframe {
            time: t,
            x: 0.5,
            y: 0.5,
            zoom: 1.0,
            easing: Easing::Linear,
            shake: 0.0,
        };
    }
    if kfs.len() == 1 || t <= kfs[0].time {
        return kfs[0].clone();
    }
    if t >= kfs.last().unwrap().time {
        return kfs.last().unwrap().clone();
    }

    for i in 0..kfs.len() - 1 {
        if t >= kfs[i].time && t < kfs[i + 1].time {
            let dt = kfs[i + 1].time - kfs[i].time;
            if dt == 0.0 {
                return kfs[i + 1].clone();
            }
            let progress = (t - kfs[i].time) / dt;
            let eased = apply_easing(progress, kfs[i + 1].easing);
            return CameraKeyframe {
                time: t,
                x: lerp(kfs[i].x, kfs[i + 1].x, eased),
                y: lerp(kfs[i].y, kfs[i + 1].y, eased),
                zoom: lerp(kfs[i].zoom, kfs[i + 1].zoom, eased),
                easing: kfs[i + 1].easing,
                shake: lerp(kfs[i].shake, kfs[i + 1].shake, eased),
            };
        }
    }

    kfs.last().unwrap().clone()
}

/// Check for character overlaps throughout a timeline.
/// Returns an error if any two characters overlap at any point.
///
/// Characters are sampled at 0.1s intervals. Two characters overlap if their
/// horizontal bounding boxes intersect (based on a base width of 0.12, scaled
/// by `scale_x`) AND they are on a similar vertical plane (within 0.15).
/// Characters that are offscreen or nearly invisible are excluded.
pub fn check_overlaps(
    timeline: &Timeline,
    initial_entities: &HashMap<String, EntityState>,
    character_names: &[String],
) -> Result<(), AnimError> {
    const BASE_WIDTH: f64 = 0.12;
    const Y_THRESHOLD: f64 = 0.15;
    const OPACITY_THRESHOLD: f64 = 0.01;
    const TIME_STEP: f64 = 0.1;

    if character_names.len() < 2 {
        return Ok(());
    }

    // Build a lookup: for each character, find the tracks for X, Y, Opacity, ScaleX.
    struct CharTracks<'a> {
        x: Option<&'a Track>,
        y: Option<&'a Track>,
        opacity: Option<&'a Track>,
        scale_x: Option<&'a Track>,
    }

    let mut char_tracks: HashMap<&str, CharTracks> = HashMap::new();
    for name in character_names {
        char_tracks.insert(
            name.as_str(),
            CharTracks {
                x: None,
                y: None,
                opacity: None,
                scale_x: None,
            },
        );
    }

    for track in &timeline.tracks {
        if let Some(ct) = char_tracks.get_mut(track.entity.as_str()) {
            match track.property {
                Property::X => ct.x = Some(track),
                Property::Y => ct.y = Some(track),
                Property::Opacity => ct.opacity = Some(track),
                Property::ScaleX => ct.scale_x = Some(track),
                _ => {}
            }
        }
    }

    // Helper to get a property value at time t, falling back to initial state.
    let get_value = |name: &str, tracks: &CharTracks, prop: Property, t: f64| -> f64 {
        let track_opt = match prop {
            Property::X => tracks.x,
            Property::Y => tracks.y,
            Property::Opacity => tracks.opacity,
            Property::ScaleX => tracks.scale_x,
            _ => None,
        };
        if let Some(track) = track_opt {
            evaluate_track(track, t)
        } else if let Some(entity) = initial_entities.get(name) {
            match prop {
                Property::X => entity.x,
                Property::Y => entity.y,
                Property::Opacity => entity.opacity,
                Property::ScaleX => entity.scale_x,
                _ => 0.0,
            }
        } else {
            match prop {
                Property::Opacity | Property::ScaleX => 1.0,
                _ => 0.5,
            }
        }
    };

    // Sample through time.
    let num_steps = ((timeline.duration / TIME_STEP).ceil() as usize).max(1);
    for step in 0..=num_steps {
        let t = (step as f64 * TIME_STEP).min(timeline.duration);

        // Collect visible, on-screen character positions.
        struct CharPos {
            name: String,
            x: f64,
            y: f64,
            half_width: f64,
        }

        let mut visible_chars: Vec<CharPos> = Vec::new();

        for name in character_names {
            let tracks = &char_tracks[name.as_str()];

            let opacity = get_value(name, tracks, Property::Opacity, t);
            if opacity < OPACITY_THRESHOLD {
                continue;
            }

            let x = get_value(name, tracks, Property::X, t);
            let y = get_value(name, tracks, Property::Y, t);

            // Skip offscreen characters.
            if x < -0.1 || x > 1.1 {
                continue;
            }

            let scale_x = get_value(name, tracks, Property::ScaleX, t);
            let half_width = (BASE_WIDTH * scale_x) / 2.0;

            visible_chars.push(CharPos {
                name: name.clone(),
                x,
                y,
                half_width,
            });
        }

        // Check all pairs.
        for i in 0..visible_chars.len() {
            for j in (i + 1)..visible_chars.len() {
                let a = &visible_chars[i];
                let b = &visible_chars[j];

                let dx = (a.x - b.x).abs();
                let dy = (a.y - b.y).abs();
                let min_x_dist = a.half_width + b.half_width;

                if dx < min_x_dist && dy < Y_THRESHOLD {
                    return Err(AnimError::Overlap(format!(
                        "Character overlap detected at t={:.1}s: '{}' and '{}' are at positions \
                         ({:.2}, {:.2}) and ({:.2}, {:.2}) which are too close \
                         (distance: {:.2}, minimum: {:.2})",
                        t, a.name, b.name, a.x, a.y, b.x, b.y, dx, min_x_dist,
                    )));
                }
            }
        }
    }

    Ok(())
}

fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * t
}

fn apply_easing(t: f64, easing: Easing) -> f64 {
    match easing {
        Easing::Linear => t,
        Easing::EaseIn => t * t,
        Easing::EaseOut => 1.0 - (1.0 - t) * (1.0 - t),
        Easing::EaseInOut => {
            if t < 0.5 {
                2.0 * t * t
            } else {
                1.0 - (-2.0 * t + 2.0).powi(2) / 2.0
            }
        }
    }
}
