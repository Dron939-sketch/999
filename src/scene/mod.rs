//! Scene graph — resolves AST declarations into concrete positioned entities
//! ready for timeline compilation.

use std::collections::HashMap;

use crate::assets::AssetRegistry;
use crate::ast::*;
use crate::errors::AnimError;

/// Global rendering configuration resolved from the config block.
#[derive(Debug, Clone)]
pub struct RenderConfig {
    pub width: u32,
    pub height: u32,
    pub fps: u32,
    pub background: Color,
    /// When true, frames are post-processed to high-contrast black & white
    /// ("ink" look) — used for the Freeman-style lecture videos.
    pub monochrome: bool,
    /// Contrast strength for the monochrome post-process. ~1.1 keeps gradient
    /// shading; crank it (2–4) for a stark 2-tone silhouette ("ink" Freeman).
    pub mono_contrast: f64,
}

impl Default for RenderConfig {
    fn default() -> Self {
        Self {
            width: 1920,
            height: 1080,
            fps: 24,
            background: Color::rgb(0, 0, 0),
            monochrome: false,
            mono_contrast: 1.12,
        }
    }
}

impl RenderConfig {
    pub fn from_config_block(block: &ConfigBlock) -> Self {
        let mut cfg = Self::default();
        for entry in &block.entries {
            match entry.key.as_str() {
                "width" => {
                    if let Value::Number(n) = &entry.value {
                        cfg.width = *n as u32;
                    }
                }
                "height" => {
                    if let Value::Number(n) = &entry.value {
                        cfg.height = *n as u32;
                    }
                }
                "fps" => {
                    if let Value::Number(n) = &entry.value {
                        cfg.fps = *n as u32;
                    }
                }
                "background" => {
                    if let Value::Color(c) = &entry.value {
                        cfg.background = c.clone();
                    }
                }
                "monochrome" => match &entry.value {
                    Value::Bool(b) => cfg.monochrome = *b,
                    // Also accept `monochrome: 1` / `monochrome: 0`.
                    Value::Number(n) => cfg.monochrome = *n != 0.0,
                    _ => {}
                },
                "mono-contrast" => {
                    if let Value::Number(n) = &entry.value {
                        cfg.mono_contrast = *n;
                    }
                }
                _ => {}
            }
        }
        cfg
    }
}

/// A resolved scene ready for timeline compilation.
#[derive(Debug)]
pub struct ResolvedScene {
    pub name: String,
    pub duration: f64,
    pub set_name: Option<String>,
    pub entities: HashMap<String, EntityState>,
    pub statements: Vec<SceneStatement>,
}

/// The state of a single entity in the scene at a given time.
#[derive(Debug, Clone)]
pub struct EntityState {
    pub name: String,
    pub kind: EntityKind,
    pub x: f64,
    pub y: f64,
    pub scale_x: f64,
    pub scale_y: f64,
    pub rotation: f64,
    pub opacity: f64,
    pub pose: String,
    pub facing: Direction,
    pub layer: i32,
    pub visible: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntityKind {
    Character,
    Prop,
}

impl EntityState {
    pub fn new_character(name: &str) -> Self {
        Self {
            name: name.to_string(),
            kind: EntityKind::Character,
            x: 0.5,
            y: 0.5,
            scale_x: 1.0,
            scale_y: 1.0,
            rotation: 0.0,
            opacity: 1.0,
            pose: "idle".to_string(),
            facing: Direction::Right,
            layer: 0,
            visible: true,
        }
    }

    pub fn new_prop(name: &str) -> Self {
        Self {
            name: name.to_string(),
            kind: EntityKind::Prop,
            x: 0.5,
            y: 0.5,
            scale_x: 1.0,
            scale_y: 1.0,
            rotation: 0.0,
            opacity: 1.0,
            pose: "default".to_string(),
            facing: Direction::Right,
            layer: -1, // props behind characters by default
            visible: true,
        }
    }
}

/// Resolve a named position to normalized (0.0–1.0) coordinates.
pub fn resolve_named_position(pos: &NamedPosition) -> (f64, f64) {
    match pos {
        NamedPosition::Left => (0.2, 0.5),
        NamedPosition::Right => (0.8, 0.5),
        NamedPosition::Center => (0.5, 0.5),
        NamedPosition::LeftThird => (0.33, 0.5),
        NamedPosition::RightThird => (0.67, 0.5),
        NamedPosition::TopLeft => (0.2, 0.2),
        NamedPosition::TopRight => (0.8, 0.2),
        NamedPosition::BottomLeft => (0.2, 0.8),
        NamedPosition::BottomRight => (0.8, 0.8),
        NamedPosition::Top => (0.5, 0.15),
        NamedPosition::Bottom => (0.5, 0.85),
        NamedPosition::LeftEdge => (0.05, 0.5),
        NamedPosition::RightEdge => (0.95, 0.5),
        NamedPosition::Offscreen(Direction::Left) => (-0.2, 0.5),
        NamedPosition::Offscreen(Direction::Right) => (1.2, 0.5),
        NamedPosition::Offscreen(Direction::Up) => (0.5, -0.2),
        NamedPosition::Offscreen(Direction::Down) => (0.5, 1.2),
        // front/back have no offscreen edge — treat as below the frame.
        NamedPosition::Offscreen(Direction::Front | Direction::Back) => (0.5, 1.2),
    }
}

/// Resolve any Position variant to (x, y) in normalized coordinates.
pub fn resolve_position(
    pos: &Position,
    entities: &HashMap<String, EntityState>,
) -> Result<(f64, f64), AnimError> {
    match pos {
        Position::Named(named) => Ok(resolve_named_position(named)),
        Position::Coords(x, y) => Ok((*x, *y)),
        Position::Relative { relation, entity } => {
            let target = entities
                .get(entity)
                .ok_or_else(|| AnimError::Scene(format!("unknown entity: {entity}")))?;
            let offset = match relation {
                Relation::Near => (0.05, 0.0),
                Relation::Behind => (-0.1, 0.0),
                Relation::InFrontOf => (0.1, 0.0),
                Relation::Above => (0.0, -0.1),
                Relation::Below => (0.0, 0.1),
                Relation::LeftOf => (-0.1, 0.0),
                Relation::RightOf => (0.1, 0.0),
            };
            Ok((target.x + offset.0, target.y + offset.1))
        }
    }
}

/// Resolve a SceneDecl into a ResolvedScene.
pub fn resolve_scene(
    scene: &SceneDecl,
    assets: &AssetRegistry,
) -> Result<ResolvedScene, AnimError> {
    // Extract scene parameters.
    let mut duration = 10.0;
    let mut set_name = None;

    for param in &scene.params {
        match param.key.as_str() {
            "duration" => {
                if let Value::Duration(d) = &param.value {
                    duration = d.as_secs();
                }
            }
            "set" => {
                if let Value::Identifier(name) = &param.value {
                    set_name = Some(name.clone());
                }
            }
            _ => {}
        }
    }

    // Build initial entity states from place statements.
    let mut entities = HashMap::new();

    for stmt in &scene.body {
        if let SceneStatement::Place(place) = stmt {
            let kind = if assets.characters.contains_key(&place.entity) {
                EntityKind::Character
            } else if assets.props.contains_key(&place.entity) {
                EntityKind::Prop
            } else {
                // Assume character if not found yet — might be defined later.
                EntityKind::Character
            };

            let mut state = match kind {
                EntityKind::Character => EntityState::new_character(&place.entity),
                EntityKind::Prop => EntityState::new_prop(&place.entity),
            };

            let (x, y) = resolve_position(&place.position, &entities)?;
            state.x = x;
            state.y = y;

            if let Some(facing) = place.facing {
                state.facing = facing;
            }

            if let Some(layer) = place.layer {
                state.layer = layer;
            }

            entities.insert(place.entity.clone(), state);
        }
    }

    // Also register entities that are referenced via `enters` but not `place`d.
    // They start offscreen and invisible.
    register_entering_entities(&scene.body, assets, &mut entities);

    Ok(ResolvedScene {
        name: scene.name.clone(),
        duration,
        set_name,
        entities,
        statements: scene.body.clone(),
    })
}

/// Recursively scan statements for Enter actions and register any entities
/// that weren't already placed.
fn register_entering_entities(
    stmts: &[SceneStatement],
    assets: &AssetRegistry,
    entities: &mut HashMap<String, EntityState>,
) {
    for stmt in stmts {
        match stmt {
            SceneStatement::Action(ActionStmt::Enter { entity, .. }) => {
                if !entities.contains_key(entity) {
                    let kind = if assets.characters.contains_key(entity) {
                        EntityKind::Character
                    } else if assets.props.contains_key(entity) {
                        EntityKind::Prop
                    } else {
                        EntityKind::Character
                    };
                    let mut state = match kind {
                        EntityKind::Character => EntityState::new_character(entity),
                        EntityKind::Prop => EntityState::new_prop(entity),
                    };
                    state.opacity = 0.0; // starts invisible
                    state.visible = false;
                    entities.insert(entity.clone(), state);
                }
            }
            SceneStatement::Together(inner) | SceneStatement::Do(inner) => {
                register_entering_entities(inner, assets, entities);
            }
            _ => {}
        }
    }
}
