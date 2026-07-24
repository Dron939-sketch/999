//! AST — Abstract Syntax Tree for the animation DSL.
//!
//! This represents the parsed structure of a `.anim` file before
//! it's compiled into a timeline.

use serde::{Deserialize, Serialize};

/// Top-level program: a list of top-level items (imports, scenes, config).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Program {
    pub items: Vec<TopLevelItem>,
}

/// A top-level item in the DSL source.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TopLevelItem {
    Import(ImportDecl),
    Config(ConfigBlock),
    PoseDef(PoseDefDecl),
    Scene(SceneDecl),
}

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

/// `import character alice from "./assets/alice.svg"`
/// `import set office from "./assets/office.svg"`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImportDecl {
    pub kind: ImportKind,
    pub name: String,
    pub path: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ImportKind {
    Character,
    Set,
    Prop,
}

// ---------------------------------------------------------------------------
// Custom Pose Definitions
// ---------------------------------------------------------------------------

/// A custom pose definition.
/// ```text
/// pose "drinking" {
///     arm-right-angle: -70
///     elbow-right-bend: 0.8
/// }
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoseDefDecl {
    pub name: String,
    pub fields: Vec<PoseField>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PoseField {
    pub name: String,
    pub value: f64,
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

/// Global configuration block.
/// ```text
/// config {
///     width: 1920
///     height: 1080
///     fps: 24
///     background: #1a1a2e
/// }
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigBlock {
    pub entries: Vec<ConfigEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigEntry {
    pub key: String,
    pub value: Value,
}

// ---------------------------------------------------------------------------
// Scenes
// ---------------------------------------------------------------------------

/// A scene declaration.
/// ```text
/// scene "confrontation" (duration: 10s, set: office) {
///     ...
/// }
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SceneDecl {
    pub name: String,
    pub params: Vec<SceneParam>,
    pub body: Vec<SceneStatement>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SceneParam {
    pub key: String,
    pub value: Value,
}

// ---------------------------------------------------------------------------
// Scene statements
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SceneStatement {
    Place(PlaceStmt),
    Action(ActionStmt),
    Wait(Duration),
    Together(Vec<SceneStatement>),
    Do(Vec<SceneStatement>),
    Camera(CameraStmt),
    Transition(TransitionStmt),
    Let(LetStmt),
}

/// `place alice at left-third facing right`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlaceStmt {
    pub entity: String,
    pub position: Position,
    pub facing: Option<Direction>,
    pub layer: Option<i32>,
}

/// A let binding for inline prop/entity creation.
/// `let door = prop("door", "./assets/door.svg") at center`
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LetStmt {
    pub name: String,
    pub kind: LetKind,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LetKind {
    Prop {
        label: String,
        path: String,
        position: Option<Position>,
    },
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ActionStmt {
    MoveTo {
        entity: String,
        target: Position,
        duration: Duration,
        easing: Option<Easing>,
    },
    Pose {
        entity: String,
        pose: String,
    },
    /// `freeman speaks for 3s` — auto-cycles phoneme mouth poses for the
    /// duration (advances scene time, like a wait that talks).
    Speak {
        entity: String,
        duration: Duration,
    },
    Show {
        entity: String,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
    Hide {
        entity: String,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
    Enter {
        entity: String,
        from: Direction,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
    Exit {
        entity: String,
        to: Direction,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
    Scale {
        entity: String,
        factor: f64,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
    Rotate {
        entity: String,
        angle: f64,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
    FadeTo {
        entity: String,
        opacity: f64,
        duration: Option<Duration>,
        easing: Option<Easing>,
    },
}

// ---------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CameraStmt {
    /// `camera wide` / `camera close-up alice`
    ShotType {
        shot: ShotType,
        target: Option<String>,
    },
    /// `camera zoom-to alice over 0.8s`
    ZoomTo {
        target: String,
        duration: Duration,
        easing: Option<Easing>,
    },
    /// `camera pan-to bob over 0.6s`
    PanTo {
        target: PanTarget,
        duration: Duration,
        easing: Option<Easing>,
    },
    /// `camera shake 0.3s intensity 5`
    Shake { duration: Duration, intensity: f64 },
    /// `camera reset over 0.5s`
    Reset { duration: Option<Duration> },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PanTarget {
    Entity(String),
    Position(Position),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ShotType {
    Wide,
    Medium,
    CloseUp,
    ExtremeCloseUp,
    TwoShot,
    OverShoulder,
}

// ---------------------------------------------------------------------------
// Transitions
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransitionStmt {
    FadeBlack(Duration),
    FadeWhite(Duration),
    Cut,
    Dissolve(Duration),
    Wipe {
        direction: Direction,
        duration: Duration,
    },
}

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

/// A position — either semantic or explicit coordinates.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Position {
    /// Named positions: left, right, center, left-third, right-third, etc.
    Named(NamedPosition),
    /// Explicit coordinates: (x, y) in normalized 0.0-1.0 space.
    Coords(f64, f64),
    /// Relative to an entity: `near alice`, `behind bob`
    Relative { relation: Relation, entity: String },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum NamedPosition {
    Left,
    Right,
    Center,
    LeftThird,
    RightThird,
    TopLeft,
    TopRight,
    BottomLeft,
    BottomRight,
    Top,
    Bottom,
    LeftEdge,
    RightEdge,
    Offscreen(Direction),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Relation {
    Near,
    Behind,
    InFrontOf,
    Above,
    Below,
    LeftOf,
    RightOf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Direction {
    Left,
    Right,
    Up,
    Down,
    /// Facing the camera (used for Freeman-style monologues to camera).
    Front,
    /// Facing away from the camera.
    Back,
}

/// Duration in seconds.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Duration(pub f64);

impl Duration {
    pub fn seconds(s: f64) -> Self {
        Self(s)
    }

    pub fn as_secs(&self) -> f64 {
        self.0
    }
}

/// Easing function for interpolation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Easing {
    Linear,
    EaseIn,
    EaseOut,
    EaseInOut,
    // Can extend with cubic-bezier later
}

/// A generic value used in config entries and scene params.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Value {
    Number(f64),
    String(String),
    Duration(Duration),
    Color(Color),
    Identifier(String),
    Bool(bool),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Color {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

impl Color {
    pub fn rgb(r: u8, g: u8, b: u8) -> Self {
        Self { r, g, b, a: 255 }
    }

    pub fn rgba(r: u8, g: u8, b: u8, a: u8) -> Self {
        Self { r, g, b, a }
    }
}
