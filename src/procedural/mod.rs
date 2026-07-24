//! Procedural character drawing — generates characters from descriptions,
//! drawing every frame fresh with correct deformation, expression, and pose.
//!
//! No pre-made assets. Characters are defined by parameters and drawn
//! using bezier curves, shapes, and procedural geometry.

use std::f64::consts::PI;
use tiny_skia::{
    Color as SkiaColor, FillRule, LineCap, LineJoin, Paint, Path, PathBuilder, Pixmap, PixmapPaint,
    Stroke, Transform,
};

use serde::{Deserialize, Serialize};

// ---------------------------------------------------------------------------
// Character Description (what the DSL defines)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CharacterDesc {
    pub name: String,
    pub body: BodyDesc,
    pub face: FaceDesc,
    pub hair: HairDesc,
    pub outfit: OutfitDesc,
}

fn one() -> f64 {
    1.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BodyDesc {
    /// 0.0=very short, 0.5=average, 1.0=very tall
    pub height: f64,
    /// 0.0=very thin, 0.5=average, 1.0=heavy
    pub build: f64,
    pub skin_color: [u8; 3],
    /// Head size multiplier (1.0 = default). <1 reads taller / more elegant.
    #[serde(default = "one")]
    pub head_scale: f64,
    /// Leg length multiplier (1.0 = default). >1 lengthens the figure.
    #[serde(default = "one")]
    pub leg_scale: f64,
    /// Limb thickness multiplier for arms and legs (1.0 = default). >1 is less
    /// spindly / more solid.
    #[serde(default = "one")]
    pub limb_thickness: f64,
    /// Shoulder / upper-torso width multiplier (1.0 = default). >1 broadens the
    /// shoulders for a stronger V-taper.
    #[serde(default = "one")]
    pub shoulder_scale: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaceDesc {
    /// 0.0=round, 1.0=angular/sharp
    pub shape: f64,
    pub eye_size: f64,
    pub eye_color: [u8; 3],
    /// 0.0=thin, 1.0=thick
    pub eyebrow_thickness: f64,
    /// 0.0=small, 1.0=large
    pub nose_size: f64,
    /// 0.0=thin, 1.0=full
    pub lip_fullness: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HairDesc {
    pub color: [u8; 3],
    pub style: HairStyle,
    /// 0.0=very short, 1.0=very long
    pub length: f64,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum HairStyle {
    SlickedBack,
    Messy,
    Straight,
    Wavy,
    Short,
    Buzz,
    /// No hair — a clean, shiny scalp. Used for characters like Fredi.
    Bald,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OutfitDesc {
    pub top: ClothingItem,
    pub bottom: ClothingItem,
    pub shoes: ShoeDesc,
    #[serde(default)]
    pub accessories: Vec<Accessory>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClothingItem {
    pub kind: ClothingKind,
    pub color: [u8; 3],
    #[serde(default)]
    pub secondary_color: Option<[u8; 3]>,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum ClothingKind {
    TrenchCoat,
    Suit,
    /// Formal tailcoat: peaked lapels, white shirt front, pocket square, tails.
    Tailcoat,
    Hoodie,
    TShirt,
    Dress,
    Pants,
    Jeans,
    Skirt,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShoeDesc {
    pub color: [u8; 3],
    pub kind: ShoeKind,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum ShoeKind {
    Formal,
    Sneakers,
    Boots,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Accessory {
    pub kind: AccessoryKind,
    pub color: [u8; 3],
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum AccessoryKind {
    Hat,
    Fedora,
    Glasses,
    Tie,
    /// A bow tie worn at the collar (formal / "Fredi" look).
    BowTie,
    /// A walking cane held in the right hand, reaching to the ground.
    Cane,
    Scarf,
    Belt,
}

// ---------------------------------------------------------------------------
// Pose + Expression (runtime state for each frame)
// ---------------------------------------------------------------------------

/// Full character state for one frame — every parameter needed to draw.
#[derive(Debug, Clone)]
pub struct CharacterState {
    /// Normalized body position curve (line of action).
    /// Bends the whole body along a curve. -1.0 to 1.0 (lean left/right).
    pub line_of_action: f64,

    /// Torso bend/twist.
    pub torso_bend: f64,
    /// Torso squash (1.0 = normal, <1 = squashed, >1 = stretched).
    pub torso_squash: f64,

    /// Shoulder positions relative to torso (-1 to 1, up/down).
    pub shoulder_left: f64,
    pub shoulder_right: f64,

    /// Arm angles (degrees from hanging down, 0=down, -90=forward, 90=back).
    pub arm_left_angle: f64,
    pub arm_right_angle: f64,
    /// Elbow bend (0=straight, 1=fully bent).
    pub elbow_left_bend: f64,
    pub elbow_right_bend: f64,

    /// Leg spread and angles.
    pub leg_left_angle: f64,
    pub leg_right_angle: f64,
    /// Knee bend (0=straight, 1=fully bent).
    pub knee_left_bend: f64,
    pub knee_right_bend: f64,

    /// Head tilt (degrees, negative = left, positive = right).
    pub head_tilt: f64,
    /// Head nod (degrees, negative = looking up, positive = looking down).
    pub head_nod: f64,

    /// Facial expression parameters (all 0.0 to 1.0).
    pub expression: Expression,

    /// Vertical offset from ground (for jumping/bobbing).
    pub y_offset: f64,

    /// Secondary motion: hair swing angle (follows head movement with delay)
    pub hair_swing: f64,
    /// Secondary motion: clothing swing (follows body movement with delay)
    pub clothing_swing: f64,
    /// Previous frame's head_tilt for computing hair inertia
    pub prev_head_tilt: f64,
    /// Previous frame's line_of_action for clothing inertia
    pub prev_line_of_action: f64,

    /// Body rotation angle in degrees. 0=facing camera, 90=profile right,
    /// 180=back, 270=profile left. Continuous value.
    pub body_angle: f64,
}

#[derive(Debug, Clone)]
pub struct Expression {
    /// -1.0=angry/furrowed, 0.0=neutral, 1.0=raised/surprised
    pub eyebrow_left: f64,
    pub eyebrow_right: f64,
    /// 0.0=closed, 1.0=normal, 1.5=wide
    pub eye_open_left: f64,
    pub eye_open_right: f64,
    /// -1.0=looking left, 0.0=center, 1.0=looking right
    pub eye_direction: f64,
    /// -1.0=frown, 0.0=neutral, 1.0=smile
    pub mouth_smile: f64,
    /// 0.0=closed, 1.0=fully open
    pub mouth_open: f64,
}

impl Default for Expression {
    fn default() -> Self {
        Self {
            eyebrow_left: 0.0,
            eyebrow_right: 0.0,
            eye_open_left: 1.0,
            eye_open_right: 1.0,
            eye_direction: 0.0,
            mouth_smile: 0.1,
            mouth_open: 0.0,
        }
    }
}

impl Default for CharacterState {
    fn default() -> Self {
        Self {
            line_of_action: 0.0,
            torso_bend: 0.0,
            torso_squash: 1.0,
            shoulder_left: 0.0,
            shoulder_right: 0.0,
            arm_left_angle: 10.0,
            arm_right_angle: -10.0,
            elbow_left_bend: 0.05,
            elbow_right_bend: 0.05,
            leg_left_angle: 3.0,
            leg_right_angle: -3.0,
            knee_left_bend: 0.0,
            knee_right_bend: 0.0,
            head_tilt: 0.0,
            head_nod: 0.0,
            expression: Expression::default(),
            y_offset: 0.0,
            hair_swing: 0.0,
            clothing_swing: 0.0,
            prev_head_tilt: 0.0,
            prev_line_of_action: 0.0,
            body_angle: 0.0,
        }
    }
}

// ---------------------------------------------------------------------------
// Named poses and expressions for the DSL
// ---------------------------------------------------------------------------

/// Get a named pose (body state without expression).
pub fn named_pose(name: &str) -> CharacterState {
    let mut s = CharacterState::default();
    match name {
        "idle" => {}
        "thinking" => {
            s.arm_right_angle = -80.0;
            s.elbow_right_bend = 0.85;
            s.head_tilt = -8.0;
            s.head_nod = 5.0;
            s.line_of_action = -0.05;
            s.expression.eyebrow_left = -0.2;
            s.expression.eyebrow_right = 0.3;
            s.expression.mouth_smile = -0.1;
        }
        "pointing" => {
            s.arm_right_angle = -70.0;
            s.elbow_right_bend = 0.05;
            s.torso_bend = 5.0;
            s.line_of_action = 0.1;
            s.expression.eyebrow_left = -0.3;
            s.expression.eyebrow_right = -0.3;
            s.expression.mouth_smile = -0.2;
        }
        "surprised" => {
            s.arm_left_angle = 40.0;
            s.arm_right_angle = -40.0;
            s.elbow_left_bend = 0.3;
            s.elbow_right_bend = 0.3;
            s.shoulder_left = -0.3;
            s.shoulder_right = -0.3;
            s.torso_squash = 0.95;
            s.line_of_action = -0.05;
            s.expression.eyebrow_left = 0.8;
            s.expression.eyebrow_right = 0.8;
            s.expression.eye_open_left = 1.4;
            s.expression.eye_open_right = 1.4;
            s.expression.mouth_open = 0.7;
            s.expression.mouth_smile = 0.0;
        }
        "angry" => {
            s.torso_bend = 8.0;
            s.line_of_action = 0.15;
            s.arm_left_angle = 35.0;
            s.arm_right_angle = -35.0;
            s.elbow_left_bend = 0.5;
            s.elbow_right_bend = 0.5;
            s.head_nod = -5.0;
            s.expression.eyebrow_left = -0.7;
            s.expression.eyebrow_right = -0.7;
            s.expression.eye_open_left = 0.8;
            s.expression.eye_open_right = 0.8;
            s.expression.mouth_smile = -0.6;
            s.expression.mouth_open = 0.15;
        }
        "menacing" => {
            s.torso_bend = 5.0;
            s.line_of_action = 0.1;
            s.arm_left_angle = 18.0;
            s.arm_right_angle = -18.0;
            s.leg_left_angle = 8.0;
            s.leg_right_angle = -8.0;
            s.expression.eyebrow_left = -0.5;
            s.expression.eyebrow_right = -0.5;
            s.expression.eye_open_left = 0.7;
            s.expression.eye_open_right = 0.7;
            s.expression.mouth_smile = 0.3;
        }
        "scared" => {
            s.torso_squash = 0.92;
            s.shoulder_left = 0.4;
            s.shoulder_right = 0.4;
            s.arm_left_angle = 15.0;
            s.arm_right_angle = -15.0;
            s.elbow_left_bend = 0.7;
            s.elbow_right_bend = 0.7;
            s.head_nod = 8.0;
            s.line_of_action = -0.1;
            s.expression.eyebrow_left = 0.6;
            s.expression.eyebrow_right = 0.6;
            s.expression.eye_open_left = 1.3;
            s.expression.eye_open_right = 1.3;
            s.expression.mouth_open = 0.3;
            s.expression.mouth_smile = -0.4;
        }
        "excited" => {
            s.torso_squash = 1.05;
            s.y_offset = -5.0;
            s.arm_left_angle = 50.0;
            s.arm_right_angle = -50.0;
            s.elbow_left_bend = 0.3;
            s.elbow_right_bend = 0.3;
            s.expression.eyebrow_left = 0.5;
            s.expression.eyebrow_right = 0.5;
            s.expression.eye_open_left = 1.2;
            s.expression.eye_open_right = 1.2;
            s.expression.mouth_smile = 0.8;
            s.expression.mouth_open = 0.3;
        }
        "typing" => {
            s.torso_bend = 5.0;
            s.head_nod = 10.0;
            s.arm_left_angle = -45.0;
            s.arm_right_angle = 45.0;
            s.elbow_left_bend = 0.7;
            s.elbow_right_bend = 0.7;
            s.expression.eye_open_left = 0.85;
            s.expression.eye_open_right = 0.85;
            s.expression.eye_direction = 0.0;
        }
        _ => {}
    }
    s
}

/// Build a CharacterState from custom pose field definitions.
/// Starts from default (idle) and overrides specified fields.
pub fn custom_pose(fields: &[(String, f64)]) -> CharacterState {
    let mut s = CharacterState::default();
    for (name, value) in fields {
        match name.as_str() {
            "line-of-action" => s.line_of_action = *value,
            "torso-bend" => s.torso_bend = *value,
            "torso-squash" => s.torso_squash = *value,
            "shoulder-left" => s.shoulder_left = *value,
            "shoulder-right" => s.shoulder_right = *value,
            "arm-left-angle" => s.arm_left_angle = *value,
            "arm-right-angle" => s.arm_right_angle = *value,
            "elbow-left-bend" => s.elbow_left_bend = *value,
            "elbow-right-bend" => s.elbow_right_bend = *value,
            "leg-left-angle" => s.leg_left_angle = *value,
            "leg-right-angle" => s.leg_right_angle = *value,
            "knee-left-bend" => s.knee_left_bend = *value,
            "knee-right-bend" => s.knee_right_bend = *value,
            "head-tilt" => s.head_tilt = *value,
            "head-nod" => s.head_nod = *value,
            "y-offset" => s.y_offset = *value,
            "body-angle" => s.body_angle = *value,
            "eyebrow-left" => s.expression.eyebrow_left = *value,
            "eyebrow-right" => s.expression.eyebrow_right = *value,
            "eye-open-left" => s.expression.eye_open_left = *value,
            "eye-open-right" => s.expression.eye_open_right = *value,
            "eye-direction" => s.expression.eye_direction = *value,
            "mouth-smile" => s.expression.mouth_smile = *value,
            "mouth-open" => s.expression.mouth_open = *value,
            _ => {} // ignore unknown fields
        }
    }
    s
}

/// Interpolate between two character states.
pub fn lerp_state(a: &CharacterState, b: &CharacterState, t: f64) -> CharacterState {
    let t = t.clamp(0.0, 1.0);
    let t = t * t * (3.0 - 2.0 * t); // smooth step

    CharacterState {
        line_of_action: lerp(a.line_of_action, b.line_of_action, t),
        torso_bend: lerp(a.torso_bend, b.torso_bend, t),
        torso_squash: lerp(a.torso_squash, b.torso_squash, t),
        shoulder_left: lerp(a.shoulder_left, b.shoulder_left, t),
        shoulder_right: lerp(a.shoulder_right, b.shoulder_right, t),
        arm_left_angle: lerp(a.arm_left_angle, b.arm_left_angle, t),
        arm_right_angle: lerp(a.arm_right_angle, b.arm_right_angle, t),
        elbow_left_bend: lerp(a.elbow_left_bend, b.elbow_left_bend, t),
        elbow_right_bend: lerp(a.elbow_right_bend, b.elbow_right_bend, t),
        leg_left_angle: lerp(a.leg_left_angle, b.leg_left_angle, t),
        leg_right_angle: lerp(a.leg_right_angle, b.leg_right_angle, t),
        knee_left_bend: lerp(a.knee_left_bend, b.knee_left_bend, t),
        knee_right_bend: lerp(a.knee_right_bend, b.knee_right_bend, t),
        head_tilt: lerp(a.head_tilt, b.head_tilt, t),
        head_nod: lerp(a.head_nod, b.head_nod, t),
        y_offset: lerp(a.y_offset, b.y_offset, t),
        hair_swing: lerp(a.hair_swing, b.hair_swing, t),
        clothing_swing: lerp(a.clothing_swing, b.clothing_swing, t),
        prev_head_tilt: lerp(a.prev_head_tilt, b.prev_head_tilt, t),
        prev_line_of_action: lerp(a.prev_line_of_action, b.prev_line_of_action, t),
        body_angle: lerp_angle(a.body_angle, b.body_angle, t),
        expression: Expression {
            eyebrow_left: lerp(a.expression.eyebrow_left, b.expression.eyebrow_left, t),
            eyebrow_right: lerp(a.expression.eyebrow_right, b.expression.eyebrow_right, t),
            eye_open_left: lerp(a.expression.eye_open_left, b.expression.eye_open_left, t),
            eye_open_right: lerp(a.expression.eye_open_right, b.expression.eye_open_right, t),
            eye_direction: lerp(a.expression.eye_direction, b.expression.eye_direction, t),
            mouth_smile: lerp(a.expression.mouth_smile, b.expression.mouth_smile, t),
            mouth_open: lerp(a.expression.mouth_open, b.expression.mouth_open, t),
        },
    }
}

/// Interpolate between two character states with staggered joint timing.
/// Torso/hips lead, extremities follow with delay, creating more natural transitions.
pub fn lerp_state_staggered(a: &CharacterState, b: &CharacterState, t: f64) -> CharacterState {
    let t = t.clamp(0.0, 1.0);

    // Staggered timing: each group uses a delayed+rescaled t through smoothstep.
    let smooth = |raw: f64| -> f64 {
        let c = raw.clamp(0.0, 1.0);
        c * c * (3.0 - 2.0 * c)
    };

    // Torso/hips lead (use t directly).
    let t_torso = smooth(t);
    // Shoulders: slight delay.
    let t_shoulder = smooth(((t - 0.05).max(0.0)) / 0.95);
    // Elbows: more delay.
    let t_elbow = smooth(((t - 0.10).max(0.0)) / 0.90);
    // Head: small delay.
    let t_head = smooth(((t - 0.03).max(0.0)) / 0.97);
    // Legs: staggered like arms (hip leads, knee follows).
    let t_leg_upper = smooth(t); // hip-level, same as torso
    let t_knee = smooth(((t - 0.10).max(0.0)) / 0.90);
    // Expression: follows body.
    let t_expr = smooth(((t - 0.08).max(0.0)) / 0.92);

    CharacterState {
        // Torso (leads).
        line_of_action: lerp(a.line_of_action, b.line_of_action, t_torso),
        torso_bend: lerp(a.torso_bend, b.torso_bend, t_torso),
        torso_squash: lerp(a.torso_squash, b.torso_squash, t_torso),

        // Shoulders (slight delay).
        shoulder_left: lerp(a.shoulder_left, b.shoulder_left, t_shoulder),
        shoulder_right: lerp(a.shoulder_right, b.shoulder_right, t_shoulder),

        // Arms: shoulder timing for upper arm, elbow timing for bend.
        arm_left_angle: lerp(a.arm_left_angle, b.arm_left_angle, t_shoulder),
        arm_right_angle: lerp(a.arm_right_angle, b.arm_right_angle, t_shoulder),
        elbow_left_bend: lerp(a.elbow_left_bend, b.elbow_left_bend, t_elbow),
        elbow_right_bend: lerp(a.elbow_right_bend, b.elbow_right_bend, t_elbow),

        // Legs: hip-level leads, knees follow.
        leg_left_angle: lerp(a.leg_left_angle, b.leg_left_angle, t_leg_upper),
        leg_right_angle: lerp(a.leg_right_angle, b.leg_right_angle, t_leg_upper),
        knee_left_bend: lerp(a.knee_left_bend, b.knee_left_bend, t_knee),
        knee_right_bend: lerp(a.knee_right_bend, b.knee_right_bend, t_knee),

        // Head (small delay).
        head_tilt: lerp(a.head_tilt, b.head_tilt, t_head),
        head_nod: lerp(a.head_nod, b.head_nod, t_head),

        y_offset: lerp(a.y_offset, b.y_offset, t_torso),

        // Secondary motion: interpolate at torso rate.
        hair_swing: lerp(a.hair_swing, b.hair_swing, t_torso),
        clothing_swing: lerp(a.clothing_swing, b.clothing_swing, t_torso),
        prev_head_tilt: lerp(a.prev_head_tilt, b.prev_head_tilt, t_torso),
        prev_line_of_action: lerp(a.prev_line_of_action, b.prev_line_of_action, t_torso),
        body_angle: lerp_angle(a.body_angle, b.body_angle, t_torso),

        // Expression (follows body).
        expression: Expression {
            eyebrow_left: lerp(a.expression.eyebrow_left, b.expression.eyebrow_left, t_expr),
            eyebrow_right: lerp(
                a.expression.eyebrow_right,
                b.expression.eyebrow_right,
                t_expr,
            ),
            eye_open_left: lerp(
                a.expression.eye_open_left,
                b.expression.eye_open_left,
                t_expr,
            ),
            eye_open_right: lerp(
                a.expression.eye_open_right,
                b.expression.eye_open_right,
                t_expr,
            ),
            eye_direction: lerp(
                a.expression.eye_direction,
                b.expression.eye_direction,
                t_expr,
            ),
            mouth_smile: lerp(a.expression.mouth_smile, b.expression.mouth_smile, t_expr),
            mouth_open: lerp(a.expression.mouth_open, b.expression.mouth_open, t_expr),
        },
    }
}

/// Apply idle breathing and micro-movements with organic overlapping motion.
pub fn apply_idle(state: &mut CharacterState, time: f64) {
    // Breathing: primary cycle with a secondary harmonic for organic feel.
    let breath_primary = (time * 1.2 * 2.0 * PI).sin();
    let breath_secondary = (time * 2.7 * 2.0 * PI).sin(); // faster subtle harmonic
    let breath = breath_primary * 0.8 + breath_secondary * 0.2;

    state.torso_squash += breath * 0.012;
    // Shoulders rise/fall with breathing.
    state.shoulder_left += breath * 0.06;
    state.shoulder_right += breath * 0.06;

    // Weight shift: subtle alternating leg bend using slow cycle.
    let weight_shift = (time * 0.25 * 2.0 * PI).sin();
    state.leg_left_angle += weight_shift * 1.5;
    state.leg_right_angle -= weight_shift * 1.5;
    state.knee_left_bend += (weight_shift * 0.5 + 0.5) * 0.04; // slight bend on weighted leg
    state.knee_right_bend += (-weight_shift * 0.5 + 0.5) * 0.04;
    // Body sway follows weight shift.
    state.line_of_action += weight_shift * 0.012;

    // Head micro-movements: overlapping sine waves at different frequencies.
    let head_drift_slow = (time * 0.3 * 2.0 * PI).sin();
    let head_drift_med = (time * 0.7 * 2.0 * PI).sin();
    let head_drift_fast = (time * 1.3 * 2.0 * PI).sin();
    state.head_tilt += head_drift_slow * 0.25 + head_drift_med * 0.15 + head_drift_fast * 0.05;
    state.head_nod += (time * 0.4 * 2.0 * PI).sin() * 0.3 + (time * 0.9 * 2.0 * PI).sin() * 0.1;

    // Arms: subtle idle drift, slightly out of phase with each other.
    let arm_drift_l = (time * 0.45 * 2.0 * PI).sin() + (time * 1.1 * 2.0 * PI).sin() * 0.3;
    let arm_drift_r =
        (time * 0.45 * 2.0 * PI + 1.2).sin() + (time * 1.1 * 2.0 * PI + 0.8).sin() * 0.3;
    state.arm_left_angle += arm_drift_l * 0.7;
    state.arm_right_angle += arm_drift_r * 0.7;

    // Occasional blink with slight asymmetry.
    let blink_cycle = (time * 0.3) % 1.0;
    if blink_cycle > 0.95 {
        let blink_t = (blink_cycle - 0.95) / 0.05;
        let blink = 1.0 - (blink_t * PI).sin();
        state.expression.eye_open_left *= blink;
        state.expression.eye_open_right *= blink;
    }
    // Secondary blink (different timing, sometimes just one eye).
    let blink2 = (time * 0.13 + 0.47) % 1.0;
    if blink2 > 0.97 {
        let blink_t = (blink2 - 0.97) / 0.03;
        let blink = 1.0 - (blink_t * PI).sin();
        state.expression.eye_open_left *= blink;
    }
}

/// Apply walk cycle with staggered joint timing based on phase (0..1) and speed.
pub fn apply_walk(state: &mut CharacterState, phase: f64, speed: f64) {
    let s = speed.min(1.0);

    // Phase offsets for staggered joint timing.
    let hip_phase = phase * 2.0 * PI;
    let knee_phase = (phase - 0.15) * 2.0 * PI; // knee lags hip by 15%
    let foot_phase = (phase - 0.30) * 2.0 * PI; // foot lags hip by 30% (used for future foot roll)
    let _ = foot_phase; // reserved for future foot-roll animation
    let shoulder_phase = phase * 2.0 * PI;
    let elbow_phase = (phase - 0.10) * 2.0 * PI; // elbow lags shoulder by 10%

    // --- Legs with staggered hip -> knee -> foot ---
    // Hip drives the leg angle.
    state.leg_left_angle += hip_phase.sin() * 25.0 * s;
    state.leg_right_angle += (-hip_phase).sin() * 25.0 * s;

    // Knee bend follows hip with delay.
    // Extra knee bend at back of stride (toe-off): when leg is behind, bend more.
    let left_toe_off = (-hip_phase).sin().max(0.0); // positive when leg is back
    let right_toe_off = hip_phase.sin().max(0.0);
    state.knee_left_bend = (knee_phase.sin().max(0.0)) * 0.4 * s + left_toe_off * 0.2 * s; // toe-off extra bend
    state.knee_right_bend = ((-knee_phase).sin().max(0.0)) * 0.4 * s + right_toe_off * 0.2 * s;

    // Heel strike: straighten the leg at front of stride.
    let left_contact = hip_phase.sin().max(0.0); // positive when leg is forward
    let right_contact = (-hip_phase).sin().max(0.0);
    state.knee_left_bend *= 1.0 - left_contact * 0.3; // reduce bend on contact
    state.knee_right_bend *= 1.0 - right_contact * 0.3;

    // --- Arms swing opposite to legs, with staggered shoulder -> elbow ---
    state.arm_left_angle += (-shoulder_phase).sin() * 20.0 * s;
    state.arm_right_angle += shoulder_phase.sin() * 20.0 * s;
    state.elbow_left_bend += ((-elbow_phase).sin().max(0.0)) * 0.3 * s;
    state.elbow_right_bend += (elbow_phase.sin().max(0.0)) * 0.3 * s;

    // --- Torso: slight rotation lag behind hip movement ---
    let torso_lag_phase = (phase - 0.05) * 2.0 * PI; // torso lags hips slightly
    state.torso_bend += torso_lag_phase.sin() * 2.5 * s;
    state.line_of_action += torso_lag_phase.sin() * 0.03 * s;

    // Body bob (double frequency — oscillates up/down around zero).
    state.y_offset += -(hip_phase * 2.0).sin() * 2.0 * s;

    // --- Head: counter-rotates to stabilize, with a small delay ---
    let head_phase = (phase - 0.08) * 2.0 * PI; // head reacts with delay
    state.head_tilt += -head_phase.sin() * 1.2 * s;
    state.head_nod += (head_phase * 2.0).sin().abs() * 1.5 * s;

    // Shoulder alternation (follows torso timing).
    state.shoulder_left += torso_lag_phase.sin() * 0.18 * s;
    state.shoulder_right += (-torso_lag_phase).sin() * 0.18 * s;
}

/// Apply secondary motion (hair follow-through, clothing lag) using damped spring model.
///
/// Call this each frame after pose/walk/idle have been applied.
/// `dt` is the time step in seconds (e.g. 1/24 for 24fps).
pub fn apply_secondary_motion(state: &mut CharacterState, dt: f64) {
    // Damped spring parameters.
    // Natural frequency ~3Hz (bouncy hair), damping ratio ~0.4 (underdamped).
    let omega_n = 3.0 * 2.0 * PI; // natural angular frequency (rad/s)
    let zeta = 0.4; // damping ratio (underdamped)

    // --- Hair swing: follows head_tilt changes ---
    let head_delta = state.head_tilt - state.prev_head_tilt;
    // Target hair swing is opposite to head movement direction (follow-through).
    let hair_target = -head_delta * 8.0; // amplify the delta for visible swing

    // Damped spring update for hair:
    // acceleration = omega_n^2 * (target - current) - 2 * zeta * omega_n * velocity
    // We approximate velocity from the difference and integrate.
    let hair_error = hair_target - state.hair_swing;
    let spring_force = omega_n * omega_n * hair_error;
    let damping_force = 2.0 * zeta * omega_n * state.hair_swing;
    state.hair_swing += (spring_force - damping_force) * dt;
    // Clamp to prevent explosion.
    state.hair_swing = state.hair_swing.clamp(-15.0, 15.0);

    // --- Clothing swing: follows line_of_action changes ---
    let loa_delta = state.line_of_action - state.prev_line_of_action;
    let clothing_target = -loa_delta * 200.0; // amplify (line_of_action is small range)

    let clothing_omega = 2.5 * 2.0 * PI; // slightly lower freq for heavier cloth
    let clothing_zeta = 0.5; // slightly more damped than hair
    let clothing_error = clothing_target - state.clothing_swing;
    let clothing_spring = clothing_omega * clothing_omega * clothing_error;
    let clothing_damp = 2.0 * clothing_zeta * clothing_omega * state.clothing_swing;
    state.clothing_swing += (clothing_spring - clothing_damp) * dt;
    state.clothing_swing = state.clothing_swing.clamp(-10.0, 10.0);

    // Store current values for next frame.
    state.prev_head_tilt = state.head_tilt;
    state.prev_line_of_action = state.line_of_action;
}

// ---------------------------------------------------------------------------
// The actual drawing engine
// ---------------------------------------------------------------------------

/// Draw a complete character onto a pixmap.
pub fn draw_character(
    desc: &CharacterDesc,
    state: &CharacterState,
    pixmap: &mut Pixmap,
    cx: f64,      // center x in pixels
    cy_foot: f64, // foot y position in pixels
    scale: f64,   // overall scale
    flip: bool,   // mirror horizontally
    opacity: f64,
) {
    let flip_sign: f64 = if flip { -1.0 } else { 1.0 };

    // --- Perspective factors from body_angle ---
    let angle_rad = (state.body_angle % 360.0).to_radians();
    // How much we see the front (-1 to 1, positive = front visible)
    let front_factor = angle_rad.cos(); // 1.0 at 0°, 0.0 at 90°, -1.0 at 180°
                                        // How much we're turned left/right (-1 to 1)
    let turn_factor = angle_rad.sin(); // 0.0 at 0°, 1.0 at 90°, 0.0 at 180°, -1.0 at 270°
                                       // Is the front visible at all?
    let _front_visible = front_factor > -0.2;
    // Is this more of a back view?
    let back_view = front_factor < 0.0;

    // Character proportions based on description.
    let height_factor = 0.7 + desc.body.height * 0.6; // 0.7 to 1.3
    let width_factor = 0.7 + desc.body.build * 0.6;

    // Per-character proportion multipliers (default 1.0, see BodyDesc).
    let head_scale = desc.body.head_scale;
    let leg_scale = desc.body.leg_scale;
    let limb_thickness = desc.body.limb_thickness;
    let shoulder_scale = desc.body.shoulder_scale;

    let total_h = 200.0 * height_factor * scale;
    let head_r = 22.0 * scale * (1.0 + desc.body.build * 0.1) * head_scale;
    let neck_h = 8.0 * scale;
    let torso_h = 65.0 * height_factor * scale * state.torso_squash;
    let torso_w = 40.0 * width_factor * scale / state.torso_squash.max(0.5)
        * (0.4 + 0.6 * front_factor.abs());
    let leg_h = 70.0 * height_factor * scale * leg_scale;
    let arm_len = 60.0 * height_factor * scale * (0.85 + 0.15 * leg_scale);
    let arm_w = 8.0 * width_factor * scale * limb_thickness;
    let leg_w = 10.0 * width_factor * scale * limb_thickness;

    // Shoulder offsets for turned body (broadened by shoulder_scale).
    let near_shoulder_offset = (torso_w * 0.5 + turn_factor * torso_w * 0.15) * shoulder_scale;
    let far_shoulder_offset = (torso_w * 0.5 - turn_factor * torso_w * 0.15) * shoulder_scale;

    // Arm width scaling based on depth.
    let far_arm_w = arm_w * (0.7 + 0.3 * front_factor.abs());
    let near_arm_w = arm_w;

    // Leg spread narrows when turned.
    let leg_spread = torso_w * 0.22 * (0.3 + 0.7 * front_factor.abs());

    // Positions from foot upward.
    let foot_y = cy_foot + state.y_offset * scale;
    let hip_y = foot_y - leg_h;
    let shoulder_y = hip_y - torso_h;
    let neck_y = shoulder_y - neck_h;
    let head_y = neck_y - head_r;

    // Line of action: offset x positions.
    let loa = state.line_of_action;
    let hip_x = cx;
    let shoulder_x = cx + loa * 30.0 * scale * flip_sign;
    let head_x = shoulder_x
        + loa * 15.0 * scale * flip_sign
        + state.torso_bend.to_radians().sin() * 10.0 * scale * flip_sign
        + turn_factor * head_r * 0.3; // Head shifts in turn direction

    let skin = desc.body.skin_color;

    // --- Draw order: back arm, back leg, torso, front leg, front arm, head ---

    // Determine which arm is near/far based on turn direction.
    // When turning right (turn_factor > 0.3), left arm is far, right arm is near.
    // When turning left (turn_factor < -0.3), right arm is far, left arm is near.
    let left_is_far = turn_factor > 0.3;
    let right_is_far = turn_factor < -0.3;

    let left_arm_shoulder_offset = if left_is_far {
        far_shoulder_offset
    } else {
        near_shoulder_offset
    };
    let right_arm_shoulder_offset = if right_is_far {
        far_shoulder_offset
    } else {
        near_shoulder_offset
    };
    let left_arm_w = if left_is_far { far_arm_w } else { near_arm_w };
    let right_arm_w = if right_is_far { far_arm_w } else { near_arm_w };

    // Back arm (left arm when facing right).
    draw_arm(
        pixmap,
        desc,
        state,
        shoulder_x - left_arm_shoulder_offset * flip_sign
            + state.shoulder_left * 5.0 * scale * flip_sign,
        shoulder_y + state.shoulder_left * 8.0 * scale,
        state.arm_left_angle * flip_sign,
        state.elbow_left_bend,
        arm_len,
        left_arm_w,
        scale,
        flip_sign,
        opacity,
        skin,
        &desc.outfit.top,
        true,
    );

    // Back leg (left).
    draw_leg(
        pixmap,
        desc,
        state,
        hip_x - leg_spread * flip_sign,
        hip_y,
        state.leg_left_angle * flip_sign,
        state.knee_left_bend,
        leg_h,
        leg_w,
        scale,
        flip_sign,
        opacity,
        skin,
        &desc.outfit,
        true,
    );

    // Torso.
    draw_torso(
        pixmap,
        desc,
        state,
        shoulder_x,
        shoulder_y,
        hip_x,
        hip_y,
        torso_w,
        torso_h,
        scale,
        flip_sign,
        opacity,
        turn_factor,
        front_factor,
    );

    // Tailcoat tails — hang behind the legs (drawn after torso, before legs).
    if desc.outfit.top.kind == ClothingKind::Tailcoat {
        draw_tailcoat_tails(
            pixmap,
            hip_x,
            hip_y,
            leg_h,
            torso_w * 0.55,
            scale,
            state.clothing_swing,
            desc.outfit.top.color,
            opacity,
        );
    }

    // Neck.
    draw_neck(
        pixmap,
        head_x,
        neck_y,
        shoulder_x,
        shoulder_y,
        6.0 * scale,
        opacity,
        skin,
    );

    // Front leg (right).
    draw_leg(
        pixmap,
        desc,
        state,
        hip_x + leg_spread * flip_sign,
        hip_y,
        state.leg_right_angle * flip_sign,
        state.knee_right_bend,
        leg_h,
        leg_w,
        scale,
        flip_sign,
        opacity,
        skin,
        &desc.outfit,
        false,
    );

    // Cane held in the right hand, drawn before the arm so the hand grips it.
    if desc
        .outfit
        .accessories
        .iter()
        .any(|a| a.kind == AccessoryKind::Cane)
    {
        let r_sx = shoulder_x
            + right_arm_shoulder_offset * flip_sign
            + state.shoulder_right * 5.0 * scale * flip_sign;
        let r_sy = shoulder_y + state.shoulder_right * 8.0 * scale;
        let (grip_x, grip_y) = arm_hand_pos(
            r_sx,
            r_sy,
            state.arm_right_angle * flip_sign,
            state.elbow_right_bend,
            arm_len,
        );
        draw_cane(pixmap, grip_x, grip_y, foot_y, scale, opacity);
    }

    // Front arm (right arm when facing right).
    draw_arm(
        pixmap,
        desc,
        state,
        shoulder_x
            + right_arm_shoulder_offset * flip_sign
            + state.shoulder_right * 5.0 * scale * flip_sign,
        shoulder_y + state.shoulder_right * 8.0 * scale,
        state.arm_right_angle * flip_sign,
        state.elbow_right_bend,
        arm_len,
        right_arm_w,
        scale,
        flip_sign,
        opacity,
        skin,
        &desc.outfit.top,
        false,
    );

    // Head + face.
    draw_head(
        pixmap,
        desc,
        state,
        head_x,
        head_y,
        head_r,
        scale,
        flip_sign,
        opacity,
        turn_factor,
        front_factor,
        back_view,
    );

    // Bow tie — drawn last so it sits on top of the collar/neck. Skipped from
    // the back where the collar isn't visible.
    if !back_view {
        for acc in &desc.outfit.accessories {
            if acc.kind == AccessoryKind::BowTie {
                draw_bowtie(
                    pixmap,
                    head_x,
                    shoulder_y - 2.0 * scale,
                    scale,
                    acc.color,
                    opacity,
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Individual part drawing functions
// ---------------------------------------------------------------------------

fn draw_torso(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    state: &CharacterState,
    sx: f64,
    sy: f64,
    hx: f64,
    hy: f64,
    w: f64,
    h: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    turn_factor: f64,
    _front_factor: f64,
) {
    let color = desc.outfit.top.color;

    // Organic torso shape with curved shoulders, waist indentation, and chest curvature.
    // Asymmetric shoulder widths when turned. shoulder_scale broadens the top
    // (shoulders + chest) without widening the waist/hips → a stronger V-taper.
    let sh_scale = desc.body.shoulder_scale;
    let base_shoulder_w = w * 0.5 * sh_scale;
    // When turn_factor > 0 (turning right), right side is near (wider), left is far (narrower).
    let near_sw_scale = 1.0 + turn_factor.abs() * 0.1;
    let far_sw_scale = 1.0 - turn_factor.abs() * 0.3;
    let shoulder_w_pos = base_shoulder_w
        * if turn_factor > 0.0 {
            near_sw_scale
        } else {
            far_sw_scale
        }; // positive X side
    let shoulder_w_neg = base_shoulder_w
        * if turn_factor > 0.0 {
            far_sw_scale
        } else {
            near_sw_scale
        }; // negative X side
    let hip_w = w * 0.4;
    let waist_w = w * 0.35 + desc.body.build * w * 0.08; // narrower at waist, wider for heavier builds
    let chest_w = w * 0.48 * (0.5 + 0.5 * sh_scale);
    let bend = state.torso_bend.to_radians();

    // Key y positions along the torso.
    let chest_y = lerp(sy, hy, 0.25);
    let waist_y = lerp(sy, hy, 0.6);

    let mut pb = PathBuilder::new();

    // Start at left shoulder — curved shoulder top (asymmetric).
    pb.move_to((sx - shoulder_w_neg) as f32, sy as f32);
    // Curved shoulder line across top (slight upward arc).
    pb.quad_to(
        sx as f32,
        (sy - 3.0 * scale) as f32,
        (sx + shoulder_w_pos) as f32,
        sy as f32,
    );

    // Right side: shoulder -> chest (slight outward curve for chest).
    pb.cubic_to(
        (sx + shoulder_w_pos + 1.0 * scale) as f32,
        (lerp(sy, chest_y, 0.5)) as f32,
        (lerp(sx + chest_w, hx + chest_w, 0.3) + bend.sin() * 3.0 * scale) as f32,
        chest_y as f32,
        (lerp(sx + chest_w, hx + waist_w, 0.5) + bend.sin() * 5.0 * scale) as f32,
        waist_y as f32,
    );
    // Right side: waist -> hip (outward again for hips).
    pb.cubic_to(
        (lerp(hx + waist_w, hx + hip_w, 0.4) + bend.sin() * 6.0 * scale) as f32,
        lerp(waist_y, hy, 0.4) as f32,
        (hx + hip_w + bend.sin() * 4.0 * scale) as f32,
        (hy - 2.0 * scale) as f32,
        (hx + hip_w) as f32,
        hy as f32,
    );

    // Bottom edge.
    pb.line_to((hx - hip_w) as f32, hy as f32);

    // Left side: hip -> waist.
    pb.cubic_to(
        (hx - hip_w - bend.sin() * 4.0 * scale) as f32,
        (hy - 2.0 * scale) as f32,
        (lerp(hx - waist_w, hx - hip_w, 0.4) - bend.sin() * 6.0 * scale) as f32,
        lerp(waist_y, hy, 0.4) as f32,
        (lerp(sx - chest_w, hx - waist_w, 0.5) - bend.sin() * 5.0 * scale) as f32,
        waist_y as f32,
    );
    // Left side: waist -> chest -> shoulder.
    pb.cubic_to(
        (lerp(sx - chest_w, hx - chest_w, 0.3) - bend.sin() * 3.0 * scale) as f32,
        chest_y as f32,
        (sx - shoulder_w_neg - 1.0 * scale) as f32,
        (lerp(sy, chest_y, 0.5)) as f32,
        (sx - shoulder_w_neg) as f32,
        sy as f32,
    );
    pb.close();

    if let Some(path) = pb.finish() {
        draw_outlined_path(pixmap, &path, color, opacity, Transform::identity());

        // Two-tone shading: shadow on the right side.
        let shadow_color = shade_color(color, 0.18);
        let shadow_paint = solid_paint(
            shadow_color[0],
            shadow_color[1],
            shadow_color[2],
            opacity * 0.5,
        );
        let mut spb = PathBuilder::new();
        // Right half of the torso for shading.
        spb.move_to(sx as f32, sy as f32);
        spb.line_to((sx + shoulder_w_pos) as f32, sy as f32);
        spb.cubic_to(
            (sx + shoulder_w_pos + 1.0 * scale) as f32,
            (lerp(sy, chest_y, 0.5)) as f32,
            (lerp(sx + chest_w, hx + chest_w, 0.3) + bend.sin() * 3.0 * scale) as f32,
            chest_y as f32,
            (lerp(sx + chest_w, hx + waist_w, 0.5) + bend.sin() * 5.0 * scale) as f32,
            waist_y as f32,
        );
        spb.cubic_to(
            (lerp(hx + waist_w, hx + hip_w, 0.4) + bend.sin() * 6.0 * scale) as f32,
            lerp(waist_y, hy, 0.4) as f32,
            (hx + hip_w + bend.sin() * 4.0 * scale) as f32,
            (hy - 2.0 * scale) as f32,
            (hx + hip_w) as f32,
            hy as f32,
        );
        spb.line_to(hx as f32, hy as f32);
        spb.close();
        if let Some(shadow_path) = spb.finish() {
            pixmap.fill_path(
                &shadow_path,
                &shadow_paint,
                FillRule::Winding,
                Transform::identity(),
                None,
            );
        }
    }

    // Outfit details.
    match desc.outfit.top.kind {
        ClothingKind::Suit => {
            // Lapels and tie.
            if let Some(sec) = desc.outfit.top.secondary_color {
                let mut tie_paint = solid_paint(sec[0], sec[1], sec[2], opacity);
                let mut pb = PathBuilder::new();
                pb.move_to(sx as f32 - 3.0, sy as f32 + 5.0);
                pb.line_to(sx as f32, (sy + h * 0.6) as f32);
                pb.line_to(sx as f32 + 3.0, sy as f32 + 5.0);
                pb.close();
                if let Some(path) = pb.finish() {
                    pixmap.fill_path(
                        &path,
                        &tie_paint,
                        FillRule::Winding,
                        Transform::identity(),
                        None,
                    );
                }
            }
            // Collar lines.
            let mut line_paint = solid_paint(
                color[0].saturating_sub(25),
                color[1].saturating_sub(25),
                color[2].saturating_sub(25),
                opacity,
            );
            let stroke = Stroke {
                width: 1.5,
                ..Stroke::default()
            };
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32 - 2.0, sy as f32);
            pb.line_to(sx as f32 - 6.0, (sy + 20.0 * scale) as f32);
            if let Some(path) = pb.finish() {
                pixmap.stroke_path(&path, &line_paint, &stroke, Transform::identity(), None);
            }
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32 + 2.0, sy as f32);
            pb.line_to(sx as f32 + 6.0, (sy + 20.0 * scale) as f32);
            if let Some(path) = pb.finish() {
                pixmap.stroke_path(&path, &line_paint, &stroke, Transform::identity(), None);
            }
        }
        ClothingKind::Tailcoat => {
            // Satin peaked lapels — a touch lighter than the jacket for sheen.
            let satin = [
                color[0].saturating_add(46),
                color[1].saturating_add(46),
                color[2].saturating_add(50),
            ];
            let satin_paint = solid_paint(satin[0], satin[1], satin[2], opacity);
            let waist_y = lerp(sy, hy, 0.52);

            // Left lapel (our left).
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32, (sy + 3.0 * scale) as f32);
            pb.line_to((sx - w * 0.42) as f32, (sy + 1.0 * scale) as f32);
            pb.line_to((sx - w * 0.30) as f32, lerp(sy, hy, 0.26) as f32);
            pb.line_to((sx - w * 0.06) as f32, waist_y as f32);
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &satin_paint, FillRule::Winding, Transform::identity(), None);
            }
            // Right lapel (mirror).
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32, (sy + 3.0 * scale) as f32);
            pb.line_to((sx + w * 0.42) as f32, (sy + 1.0 * scale) as f32);
            pb.line_to((sx + w * 0.30) as f32, lerp(sy, hy, 0.26) as f32);
            pb.line_to((sx + w * 0.06) as f32, waist_y as f32);
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &satin_paint, FillRule::Winding, Transform::identity(), None);
            }

            // White shirt front — a V narrowing to the waist button.
            let shirt = [236u8, 233, 226];
            let mut pb = PathBuilder::new();
            pb.move_to((sx - w * 0.13) as f32, (sy + 4.0 * scale) as f32);
            pb.line_to((sx + w * 0.13) as f32, (sy + 4.0 * scale) as f32);
            pb.line_to((sx + w * 0.035) as f32, waist_y as f32);
            pb.line_to((sx - w * 0.035) as f32, waist_y as f32);
            pb.close();
            if let Some(path) = pb.finish() {
                draw_outlined_path(pixmap, &path, shirt, opacity, Transform::identity());
            }

            // Ink outlines along the lapel edges.
            let ink = [10u8, 10, 12];
            let ink_paint = solid_paint(ink[0], ink[1], ink[2], opacity);
            let ink_stroke = Stroke {
                width: 1.4,
                line_join: LineJoin::Round,
                ..Stroke::default()
            };
            for s in [-1.0f64, 1.0] {
                let mut pb = PathBuilder::new();
                pb.move_to((sx + s * w * 0.42) as f32, (sy + 1.0 * scale) as f32);
                pb.line_to((sx + s * w * 0.30) as f32, lerp(sy, hy, 0.26) as f32);
                pb.line_to((sx + s * w * 0.06) as f32, waist_y as f32);
                if let Some(path) = pb.finish() {
                    pixmap.stroke_path(&path, &ink_paint, &ink_stroke, Transform::identity(), None);
                }
            }

            // Waist button.
            fill_rect(
                pixmap,
                sx - 2.0 * scale,
                waist_y - 1.5 * scale,
                4.0 * scale,
                4.0 * scale,
                &satin_paint,
            );

            // Pocket square — small white peak on the wearer's left breast.
            let px = sx + w * 0.22;
            let py = lerp(sy, hy, 0.24);
            let mut pb = PathBuilder::new();
            pb.move_to((px - 4.0 * scale) as f32, py as f32);
            pb.line_to((px + 4.0 * scale) as f32, py as f32);
            pb.line_to(px as f32, (py + 6.0 * scale) as f32);
            pb.close();
            if let Some(path) = pb.finish() {
                draw_outlined_path(pixmap, &path, shirt, opacity, Transform::identity());
            }
        }
        ClothingKind::TrenchCoat => {
            // Belt — offset slightly by clothing swing.
            let cloth_sw = state.clothing_swing * scale * 0.2;
            let belt_y = lerp(sy, hy, 0.55);
            let belt_w = w * 0.48;
            let mut belt_paint = solid_paint(
                color[0].saturating_sub(30),
                color[1].saturating_sub(30),
                color[2].saturating_sub(30),
                opacity,
            );
            fill_rect(
                pixmap,
                sx - belt_w + cloth_sw,
                belt_y,
                belt_w * 2.0,
                4.0 * scale,
                &belt_paint,
            );
            // Buckle.
            let mut buckle = solid_paint(200, 180, 80, opacity);
            fill_rect(
                pixmap,
                sx - 3.0 * scale + cloth_sw,
                belt_y - 1.0,
                6.0 * scale,
                6.0 * scale,
                &buckle,
            );
            // Lapels.
            let mut lapel = solid_paint(
                color[0].saturating_sub(15),
                color[1].saturating_sub(15),
                color[2].saturating_sub(15),
                opacity,
            );
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32 - 3.0, sy as f32);
            pb.line_to(sx as f32, (sy + h * 0.3) as f32);
            pb.line_to(sx as f32 - 10.0 * scale as f32, (sy + 5.0) as f32);
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(
                    &path,
                    &lapel,
                    FillRule::Winding,
                    Transform::identity(),
                    None,
                );
            }
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32 + 3.0, sy as f32);
            pb.line_to(sx as f32, (sy + h * 0.3) as f32);
            pb.line_to(sx as f32 + 10.0 * scale as f32, (sy + 5.0) as f32);
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(
                    &path,
                    &lapel,
                    FillRule::Winding,
                    Transform::identity(),
                    None,
                );
            }
        }
        ClothingKind::Hoodie => {
            // Front pocket — offset by clothing swing.
            let cloth_sw = state.clothing_swing * scale * 0.15;
            let pocket_y = lerp(sy, hy, 0.5);
            let pocket_w = w * 0.35;
            let pocket_h = h * 0.2;
            let mut pocket_paint = solid_paint(
                color[0].saturating_sub(15),
                color[1].saturating_sub(15),
                color[2].saturating_sub(15),
                opacity,
            );
            fill_rect(
                pixmap,
                sx - pocket_w + cloth_sw,
                pocket_y,
                pocket_w * 2.0,
                pocket_h,
                &pocket_paint,
            );
            // Hoodie strings.
            let mut string_paint = solid_paint(200, 210, 220, opacity);
            let stroke = Stroke {
                width: 1.2,
                ..Stroke::default()
            };
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32 - 4.0, sy as f32 + 2.0);
            pb.line_to(sx as f32 - 5.0, (sy + 18.0 * scale) as f32);
            if let Some(path) = pb.finish() {
                pixmap.stroke_path(&path, &string_paint, &stroke, Transform::identity(), None);
            }
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32 + 4.0, sy as f32 + 2.0);
            pb.line_to(sx as f32 + 5.0, (sy + 18.0 * scale) as f32);
            if let Some(path) = pb.finish() {
                pixmap.stroke_path(&path, &string_paint, &stroke, Transform::identity(), None);
            }
        }
        _ => {}
    }

}

/// Draw a bow tie centered at (cx, cy): two triangular wings meeting at a knot.
fn draw_bowtie(pixmap: &mut Pixmap, cx: f64, cy: f64, scale: f64, color: [u8; 3], opacity: f64) {
    let paint = solid_paint(color[0], color[1], color[2], opacity);
    let wing = 7.5 * scale; // half-width of one wing
    let hh = 5.0 * scale; // half-height of a wing
    let knot = 2.0 * scale; // half-width of the central knot

    // Left wing (triangle: knot -> outer-top -> outer-bottom).
    let mut pb = PathBuilder::new();
    pb.move_to((cx - knot) as f32, cy as f32);
    pb.line_to((cx - knot - wing) as f32, (cy - hh) as f32);
    pb.line_to((cx - knot - wing) as f32, (cy + hh) as f32);
    pb.close();
    // Right wing (mirror).
    pb.move_to((cx + knot) as f32, cy as f32);
    pb.line_to((cx + knot + wing) as f32, (cy - hh) as f32);
    pb.line_to((cx + knot + wing) as f32, (cy + hh) as f32);
    pb.close();
    if let Some(path) = pb.finish() {
        pixmap.fill_path(&path, &paint, FillRule::Winding, Transform::identity(), None);
        // Dark outline for the ink look.
        let dark = shade_color(color, 0.35);
        let ol_paint = solid_paint(dark[0], dark[1], dark[2], opacity);
        let ol_stroke = Stroke {
            width: 1.0,
            line_join: LineJoin::Round,
            ..Stroke::default()
        };
        pixmap.stroke_path(&path, &ol_paint, &ol_stroke, Transform::identity(), None);
    }

    // Central knot.
    fill_rect(
        pixmap,
        cx - knot,
        cy - hh * 0.7,
        knot * 2.0,
        hh * 1.4,
        &paint,
    );
}

/// Two swallowtail panels hanging from the hips — the tails of a tailcoat.
fn draw_tailcoat_tails(
    pixmap: &mut Pixmap,
    hip_x: f64,
    hip_y: f64,
    leg_h: f64,
    half_w: f64,
    scale: f64,
    swing: f64,
    color: [u8; 3],
    opacity: f64,
) {
    let tail_len = leg_h * 0.72;
    let sway = swing * scale * 0.3;
    for side in [-1.0f64, 1.0] {
        let top_in = hip_x + side * half_w * 0.06;
        let top_out = hip_x + side * half_w * 0.52;
        let mid_out = hip_x + side * half_w * 0.66;
        let tip_x = hip_x + side * half_w * 0.40 + sway;
        let mut pb = PathBuilder::new();
        pb.move_to(top_in as f32, (hip_y - 3.0 * scale) as f32);
        pb.line_to(top_out as f32, hip_y as f32);
        // Outer edge curves down to a hanging point.
        pb.quad_to(
            mid_out as f32,
            (hip_y + tail_len * 0.45) as f32,
            tip_x as f32,
            (hip_y + tail_len) as f32,
        );
        // Inner edge curves back up to the waist.
        pb.quad_to(
            (hip_x + side * half_w * 0.10) as f32,
            (hip_y + tail_len * 0.4) as f32,
            top_in as f32,
            (hip_y - 3.0 * scale) as f32,
        );
        pb.close();
        if let Some(path) = pb.finish() {
            draw_outlined_path(pixmap, &path, color, opacity, Transform::identity());
        }
    }
}

/// A walking cane from the hand grip down to the ground: dark shaft, a light
/// silver knob at the top and a ferrule at the tip.
fn draw_cane(pixmap: &mut Pixmap, hand_x: f64, hand_y: f64, ground_y: f64, scale: f64, opacity: f64) {
    let shaft = [34u8, 32, 36];
    let width = 2.8 * scale;
    let top_y = hand_y - 4.0 * scale;

    // Shaft (slight taper toward the tip).
    let mut pb = PathBuilder::new();
    pb.move_to((hand_x - width * 0.5) as f32, top_y as f32);
    pb.line_to((hand_x + width * 0.5) as f32, top_y as f32);
    pb.line_to((hand_x + width * 0.35) as f32, ground_y as f32);
    pb.line_to((hand_x - width * 0.35) as f32, ground_y as f32);
    pb.close();
    if let Some(path) = pb.finish() {
        draw_outlined_path(pixmap, &path, shaft, opacity, Transform::identity());
    }

    // Silver knob.
    let knob = [206u8, 206, 212];
    let r = 4.2 * scale;
    let mut pb = PathBuilder::new();
    let steps = 20;
    for i in 0..=steps {
        let a = (i as f64 / steps as f64) * 2.0 * PI;
        let px = hand_x + a.cos() * r;
        let py = top_y + a.sin() * r * 0.9;
        if i == 0 {
            pb.move_to(px as f32, py as f32);
        } else {
            pb.line_to(px as f32, py as f32);
        }
    }
    pb.close();
    if let Some(path) = pb.finish() {
        draw_outlined_path(pixmap, &path, knob, opacity, Transform::identity());
    }

    // Ferrule at the tip.
    fill_rect(
        pixmap,
        hand_x - width * 0.45,
        ground_y - 4.0 * scale,
        width * 0.9,
        4.0 * scale,
        &solid_paint(knob[0], knob[1], knob[2], opacity),
    );
}

fn draw_neck(
    pixmap: &mut Pixmap,
    hx: f64,
    ny: f64,
    sx: f64,
    sy: f64,
    w: f64,
    opacity: f64,
    skin: [u8; 3],
) {
    let mut pb = PathBuilder::new();
    pb.move_to((hx - w * 0.5) as f32, ny as f32);
    pb.line_to((sx - w * 0.6) as f32, sy as f32);
    pb.line_to((sx + w * 0.6) as f32, sy as f32);
    pb.line_to((hx + w * 0.5) as f32, ny as f32);
    pb.close();
    if let Some(path) = pb.finish() {
        draw_outlined_path(pixmap, &path, skin, opacity, Transform::identity());
    }
}

/// Forward-kinematics for the hand position of an arm, matching `draw_arm`.
/// Used to attach held props (e.g. a cane) to the hand.
fn arm_hand_pos(sx: f64, sy: f64, angle: f64, elbow_bend: f64, length: f64) -> (f64, f64) {
    let rad = angle.to_radians();
    let upper_len = length * 0.5;
    let lower_len = length * 0.5;
    let elbow_x = sx + rad.sin() * upper_len;
    let elbow_y = sy + rad.cos() * upper_len;
    let elbow_angle = rad + elbow_bend * PI * 0.5 * if angle > 0.0 { 1.0 } else { -1.0 };
    let hand_x = elbow_x + elbow_angle.sin() * lower_len;
    let hand_y = elbow_y + elbow_angle.cos() * lower_len;
    (hand_x, hand_y)
}

fn draw_arm(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    _state: &CharacterState,
    sx: f64,
    sy: f64,
    angle: f64,
    elbow_bend: f64,
    length: f64,
    width: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    skin: [u8; 3],
    top: &ClothingItem,
    is_back: bool,
) {
    let rad = angle.to_radians();
    let upper_len = length * 0.5;
    let lower_len = length * 0.5;

    // Upper arm endpoint.
    let elbow_x = sx + rad.sin() * upper_len;
    let elbow_y = sy + rad.cos() * upper_len;

    // Lower arm bends at elbow.
    let elbow_angle = rad + elbow_bend * PI * 0.5 * if angle > 0.0 { 1.0 } else { -1.0 };
    let hand_x = elbow_x + elbow_angle.sin() * lower_len;
    let hand_y = elbow_y + elbow_angle.cos() * lower_len;

    let darken = if is_back { 20_u8 } else { 0 };

    // Sleeve (upper arm).
    let sleeve_color = [
        top.color[0].saturating_sub(darken),
        top.color[1].saturating_sub(darken),
        top.color[2].saturating_sub(darken),
    ];
    draw_limb_segment(
        pixmap,
        sx,
        sy,
        elbow_x,
        elbow_y,
        width,
        opacity,
        sleeve_color,
    );

    // Forearm (sleeve color — sleeves cover most of the forearm).
    let skin_dark = [
        skin[0].saturating_sub(darken),
        skin[1].saturating_sub(darken),
        skin[2].saturating_sub(darken),
    ];
    draw_limb_segment(
        pixmap,
        elbow_x,
        elbow_y,
        hand_x,
        hand_y,
        width * 0.85,
        opacity,
        sleeve_color,
    );

    // Elbow joint circle — smooth the joint visually.
    let elbow_r = width * 0.3;
    {
        let mut pb = PathBuilder::new();
        let k = 0.5522847498_f64;
        let kr = k * elbow_r;
        pb.move_to(elbow_x as f32, (elbow_y - elbow_r) as f32);
        pb.cubic_to(
            (elbow_x + kr) as f32,
            (elbow_y - elbow_r) as f32,
            (elbow_x + elbow_r) as f32,
            (elbow_y - kr) as f32,
            (elbow_x + elbow_r) as f32,
            elbow_y as f32,
        );
        pb.cubic_to(
            (elbow_x + elbow_r) as f32,
            (elbow_y + kr) as f32,
            (elbow_x + kr) as f32,
            (elbow_y + elbow_r) as f32,
            elbow_x as f32,
            (elbow_y + elbow_r) as f32,
        );
        pb.cubic_to(
            (elbow_x - kr) as f32,
            (elbow_y + elbow_r) as f32,
            (elbow_x - elbow_r) as f32,
            (elbow_y + kr) as f32,
            (elbow_x - elbow_r) as f32,
            elbow_y as f32,
        );
        pb.cubic_to(
            (elbow_x - elbow_r) as f32,
            (elbow_y - kr) as f32,
            (elbow_x - kr) as f32,
            (elbow_y - elbow_r) as f32,
            elbow_x as f32,
            (elbow_y - elbow_r) as f32,
        );
        pb.close();
        if let Some(path) = pb.finish() {
            // Elbow is inside the sleeve — fill with sleeve colour, not skin.
            draw_outlined_path(pixmap, &path, sleeve_color, opacity, Transform::identity());
        }
    }
    let _ = skin_dark;

    // Hand — shaped based on pose.
    let hand_w = width * 0.55;
    let hand_h = width * 0.7;

    // Direction the lower arm is pointing.
    let arm_dx = hand_x - elbow_x;
    let arm_dy = hand_y - elbow_y;
    let arm_seg_len = (arm_dx * arm_dx + arm_dy * arm_dy).sqrt().max(0.001);
    let arm_nx = -arm_dy / arm_seg_len;
    let arm_ny = arm_dx / arm_seg_len;
    let arm_tx = arm_dx / arm_seg_len;
    let arm_ty = arm_dy / arm_seg_len;

    let is_pointing = elbow_bend < 0.1 && angle < -60.0;
    let is_fist = elbow_bend > 0.7;

    let mut pb = PathBuilder::new();
    if is_pointing {
        let base_l_x = hand_x + arm_nx * hand_w * 0.4;
        let base_l_y = hand_y + arm_ny * hand_w * 0.4;
        let base_r_x = hand_x - arm_nx * hand_w * 0.4;
        let base_r_y = hand_y - arm_ny * hand_w * 0.4;
        let tip_x = hand_x + arm_tx * hand_h * 1.8;
        let tip_y = hand_y + arm_ty * hand_h * 1.8;
        let finger_w = hand_w * 0.15;

        pb.move_to(base_l_x as f32, base_l_y as f32);
        pb.quad_to(
            (hand_x + arm_tx * hand_h * 0.6 + arm_nx * hand_w * 0.35) as f32,
            (hand_y + arm_ty * hand_h * 0.6 + arm_ny * hand_w * 0.35) as f32,
            (hand_x + arm_tx * hand_h * 0.8 + arm_nx * finger_w) as f32,
            (hand_y + arm_ty * hand_h * 0.8 + arm_ny * finger_w) as f32,
        );
        pb.line_to(tip_x as f32, tip_y as f32);
        pb.line_to(
            (hand_x + arm_tx * hand_h * 0.8 - arm_nx * finger_w) as f32,
            (hand_y + arm_ty * hand_h * 0.8 - arm_ny * finger_w) as f32,
        );
        pb.quad_to(
            (hand_x + arm_tx * hand_h * 0.6 - arm_nx * hand_w * 0.35) as f32,
            (hand_y + arm_ty * hand_h * 0.6 - arm_ny * hand_w * 0.35) as f32,
            base_r_x as f32,
            base_r_y as f32,
        );
        pb.close();
    } else if is_fist {
        let fist_w = hand_w * 1.1;
        let fist_h = hand_h * 0.7;
        let c_x = hand_x + arm_tx * fist_h * 0.3;
        let c_y = hand_y + arm_ty * fist_h * 0.3;

        let tl_x = c_x - arm_nx * fist_w + arm_tx * (-fist_h * 0.5);
        let tl_y = c_y - arm_ny * fist_w + arm_ty * (-fist_h * 0.5);
        let tr_x = c_x + arm_nx * fist_w + arm_tx * (-fist_h * 0.5);
        let tr_y = c_y + arm_ny * fist_w + arm_ty * (-fist_h * 0.5);
        let br_x = c_x + arm_nx * fist_w + arm_tx * (fist_h * 0.5);
        let br_y = c_y + arm_ny * fist_w + arm_ty * (fist_h * 0.5);
        let bl_x = c_x - arm_nx * fist_w + arm_tx * (fist_h * 0.5);
        let bl_y = c_y - arm_ny * fist_w + arm_ty * (fist_h * 0.5);

        pb.move_to(lerp(tl_x, tr_x, 0.2) as f32, lerp(tl_y, tr_y, 0.2) as f32);
        pb.line_to(lerp(tl_x, tr_x, 0.8) as f32, lerp(tl_y, tr_y, 0.8) as f32);
        pb.quad_to(
            tr_x as f32,
            tr_y as f32,
            lerp(tr_x, br_x, 0.2) as f32,
            lerp(tr_y, br_y, 0.2) as f32,
        );
        pb.line_to(lerp(tr_x, br_x, 0.8) as f32, lerp(tr_y, br_y, 0.8) as f32);
        pb.quad_to(
            br_x as f32,
            br_y as f32,
            lerp(br_x, bl_x, 0.2) as f32,
            lerp(br_y, bl_y, 0.2) as f32,
        );
        pb.line_to(lerp(br_x, bl_x, 0.8) as f32, lerp(br_y, bl_y, 0.8) as f32);
        pb.quad_to(
            bl_x as f32,
            bl_y as f32,
            lerp(bl_x, tl_x, 0.2) as f32,
            lerp(bl_y, tl_y, 0.2) as f32,
        );
        pb.line_to(lerp(bl_x, tl_x, 0.8) as f32, lerp(bl_y, tl_y, 0.8) as f32);
        pb.quad_to(
            tl_x as f32,
            tl_y as f32,
            lerp(tl_x, tr_x, 0.2) as f32,
            lerp(tl_y, tr_y, 0.2) as f32,
        );
        pb.close();
    } else {
        let palm_w_prox = hand_w * 0.45;
        let palm_w_dist = hand_w * 0.35;
        let palm_len = hand_h * 0.55;
        let finger_len = hand_h * 0.35;

        let hpb_l_x = hand_x + arm_nx * palm_w_prox;
        let hpb_l_y = hand_y + arm_ny * palm_w_prox;
        let hpb_r_x = hand_x - arm_nx * palm_w_prox;
        let hpb_r_y = hand_y - arm_ny * palm_w_prox;
        let pt_l_x = hand_x + arm_tx * palm_len + arm_nx * palm_w_dist;
        let pt_l_y = hand_y + arm_ty * palm_len + arm_ny * palm_w_dist;
        let pt_r_x = hand_x + arm_tx * palm_len - arm_nx * palm_w_dist;
        let pt_r_y = hand_y + arm_ty * palm_len - arm_ny * palm_w_dist;

        pb.move_to(hpb_l_x as f32, hpb_l_y as f32);
        pb.line_to(pt_l_x as f32, pt_l_y as f32);

        for i in 0..4 {
            let t = (i as f64 + 0.5) / 4.0;
            let fx = lerp(pt_l_x, pt_r_x, t);
            let fy = lerp(pt_l_y, pt_r_y, t);
            let ftip_x = fx + arm_tx * finger_len;
            let ftip_y = fy + arm_ty * finger_len;
            pb.quad_to(
                ftip_x as f32,
                ftip_y as f32,
                lerp(pt_l_x, pt_r_x, (i as f64 + 1.0) / 4.0) as f32,
                lerp(pt_l_y, pt_r_y, (i as f64 + 1.0) / 4.0) as f32,
            );
        }

        pb.line_to(hpb_r_x as f32, hpb_r_y as f32);
        pb.quad_to(
            (hand_x - arm_tx * hand_w * 0.15) as f32,
            (hand_y - arm_ty * hand_w * 0.15) as f32,
            hpb_l_x as f32,
            hpb_l_y as f32,
        );
        pb.close();
    }

    if let Some(path) = pb.finish() {
        draw_outlined_path(pixmap, &path, skin_dark, opacity, Transform::identity());
    }
}

fn draw_leg(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    _state: &CharacterState,
    hx: f64,
    hy: f64,
    angle: f64,
    knee_bend: f64,
    length: f64,
    width: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    skin: [u8; 3],
    outfit: &OutfitDesc,
    is_back: bool,
) {
    let rad = angle.to_radians();
    let upper_len = length * 0.5;
    let lower_len = length * 0.5;

    let knee_x = hx + rad.sin() * upper_len;
    let knee_y = hy + rad.cos() * upper_len;

    let knee_angle = rad - knee_bend * PI * 0.4;
    let foot_x = knee_x + knee_angle.sin() * lower_len;
    let foot_y = knee_y + knee_angle.cos() * lower_len;

    let darken = if is_back { 15_u8 } else { 0 };
    let pant_color = [
        outfit.bottom.color[0].saturating_sub(darken),
        outfit.bottom.color[1].saturating_sub(darken),
        outfit.bottom.color[2].saturating_sub(darken),
    ];

    // Upper leg.
    draw_limb_segment(pixmap, hx, hy, knee_x, knee_y, width, opacity, pant_color);
    // Lower leg.
    draw_limb_segment(
        pixmap,
        knee_x,
        knee_y,
        foot_x,
        foot_y,
        width * 0.9,
        opacity,
        pant_color,
    );

    // Knee joint circle — smooth the joint visually.
    let knee_r = width * 0.35;
    {
        let mut kpb = PathBuilder::new();
        let kk = 0.5522847498_f64;
        let kkr = kk * knee_r;
        kpb.move_to(knee_x as f32, (knee_y - knee_r) as f32);
        kpb.cubic_to(
            (knee_x + kkr) as f32,
            (knee_y - knee_r) as f32,
            (knee_x + knee_r) as f32,
            (knee_y - kkr) as f32,
            (knee_x + knee_r) as f32,
            knee_y as f32,
        );
        kpb.cubic_to(
            (knee_x + knee_r) as f32,
            (knee_y + kkr) as f32,
            (knee_x + kkr) as f32,
            (knee_y + knee_r) as f32,
            knee_x as f32,
            (knee_y + knee_r) as f32,
        );
        kpb.cubic_to(
            (knee_x - kkr) as f32,
            (knee_y + knee_r) as f32,
            (knee_x - knee_r) as f32,
            (knee_y + kkr) as f32,
            (knee_x - knee_r) as f32,
            knee_y as f32,
        );
        kpb.cubic_to(
            (knee_x - knee_r) as f32,
            (knee_y - kkr) as f32,
            (knee_x - kkr) as f32,
            (knee_y - knee_r) as f32,
            knee_x as f32,
            (knee_y - knee_r) as f32,
        );
        kpb.close();
        if let Some(path) = kpb.finish() {
            draw_outlined_path(pixmap, &path, pant_color, opacity, Transform::identity());
        }
    }

    // Shoe — more substantial with proper sole and heel.
    let shoe_color = outfit.shoes.color;
    let shoe_c = [
        shoe_color[0].saturating_sub(darken),
        shoe_color[1].saturating_sub(darken),
        shoe_color[2].saturating_sub(darken),
    ];
    let shoe_w = width * 1.4;
    let shoe_h = width * 0.6;

    // Main shoe body.
    {
        let mut shoe_pb = PathBuilder::new();
        shoe_pb.move_to((foot_x - shoe_w * 0.35) as f32, foot_y as f32);
        shoe_pb.quad_to(
            (foot_x - shoe_w * 0.1) as f32,
            (foot_y - shoe_h * 0.3) as f32,
            (foot_x + shoe_w * 0.2) as f32,
            (foot_y - shoe_h * 0.1) as f32,
        );
        shoe_pb.quad_to(
            (foot_x + shoe_w * 0.65) as f32,
            (foot_y - shoe_h * 0.05) as f32,
            (foot_x + shoe_w * 0.65) as f32,
            (foot_y + shoe_h * 0.4) as f32,
        );
        shoe_pb.line_to((foot_x + shoe_w * 0.65) as f32, (foot_y + shoe_h) as f32);
        shoe_pb.line_to((foot_x - shoe_w * 0.4) as f32, (foot_y + shoe_h) as f32);
        // Heel bump.
        shoe_pb.line_to(
            (foot_x - shoe_w * 0.4) as f32,
            (foot_y + shoe_h + shoe_h * 0.25) as f32,
        );
        shoe_pb.line_to(
            (foot_x - shoe_w * 0.25) as f32,
            (foot_y + shoe_h + shoe_h * 0.25) as f32,
        );
        shoe_pb.line_to((foot_x - shoe_w * 0.2) as f32, (foot_y + shoe_h) as f32);
        shoe_pb.line_to((foot_x - shoe_w * 0.4) as f32, (foot_y + shoe_h) as f32);
        shoe_pb.line_to(
            (foot_x - shoe_w * 0.4) as f32,
            (foot_y + shoe_h * 0.3) as f32,
        );
        shoe_pb.quad_to(
            (foot_x - shoe_w * 0.4) as f32,
            foot_y as f32,
            (foot_x - shoe_w * 0.35) as f32,
            foot_y as f32,
        );
        shoe_pb.close();
        if let Some(path) = shoe_pb.finish() {
            draw_outlined_path(pixmap, &path, shoe_c, opacity, Transform::identity());
        }
    }

    // Sole — darker shade.
    {
        let sole_color = shade_color(shoe_c, 0.3);
        let mut sole_pb = PathBuilder::new();
        sole_pb.move_to(
            (foot_x - shoe_w * 0.4) as f32,
            (foot_y + shoe_h * 0.7) as f32,
        );
        sole_pb.line_to(
            (foot_x + shoe_w * 0.65) as f32,
            (foot_y + shoe_h * 0.7) as f32,
        );
        sole_pb.line_to((foot_x + shoe_w * 0.65) as f32, (foot_y + shoe_h) as f32);
        sole_pb.line_to((foot_x - shoe_w * 0.4) as f32, (foot_y + shoe_h) as f32);
        sole_pb.close();
        if let Some(path) = sole_pb.finish() {
            draw_outlined_path(pixmap, &path, sole_color, opacity, Transform::identity());
        }
    }

    // Sneaker stripe.
    if outfit.shoes.kind == ShoeKind::Sneakers {
        let mut stripe = solid_paint(255, 255, 255, opacity * 0.8);
        let stroke = Stroke {
            width: 1.5,
            line_cap: LineCap::Round,
            ..Stroke::default()
        };
        let mut stpb = PathBuilder::new();
        stpb.move_to(
            (foot_x - shoe_w * 0.15) as f32,
            (foot_y + shoe_h * 0.2) as f32,
        );
        stpb.line_to(
            (foot_x + shoe_w * 0.45) as f32,
            (foot_y + shoe_h * 0.2) as f32,
        );
        if let Some(path) = stpb.finish() {
            pixmap.stroke_path(&path, &stripe, &stroke, Transform::identity(), None);
        }
    }
}

fn draw_head(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    state: &CharacterState,
    cx: f64,
    cy: f64,
    r: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    turn_factor: f64,
    front_factor: f64,
    back_view: bool,
) {
    let skin = desc.body.skin_color;
    let tilt_rad = (state.head_tilt * flip).to_radians();
    let nod_rad = state.head_nod.to_radians();

    // Squash head slightly with nod.
    let head_sx = 1.0 + nod_rad.abs() * 0.05;
    let head_sy = 1.0 - nod_rad.abs() * 0.03;

    let mut rx = r * head_sx;
    let ry = r * head_sy;

    // --- Expression-based face deformation ---
    let open = state.expression.mouth_open;
    let avg_brow = (state.expression.eyebrow_left + state.expression.eyebrow_right) * 0.5;
    // Jaw stretch when mouth very open (>0.6).
    let jaw_stretch = if open > 0.6 {
        (open - 0.6) * 0.125
    } else {
        0.0
    };
    // Angry: narrow at brow level.
    let angry_narrow = if avg_brow < -0.5 {
        (avg_brow + 0.5) * 0.04
    } else {
        0.0
    };
    // Surprised: widen eyes area slightly.
    let surprise_widen = if avg_brow > 0.5 {
        (avg_brow - 0.5) * 0.04
    } else {
        0.0
    };
    rx += rx * (angry_narrow + surprise_widen);

    // Hair (drawn behind head).
    draw_hair_back(
        pixmap,
        desc,
        cx,
        cy,
        rx,
        ry,
        scale,
        flip,
        opacity,
        tilt_rad,
        state.hair_swing,
    );

    // Head shape (slightly oval, affected by face shape).
    let jaw_factor = desc.face.shape; // 0=round, 1=angular

    // Reusable head-path builder (off_x shifts for shadow crescent).
    let build_head_path = |off_x: f64, extra_jaw: f64| -> Option<tiny_skia::Path> {
        let eff_ry = ry * (1.0 + jaw_stretch + extra_jaw);
        let hcx = cx + off_x;
        let jaw_w = rx * (0.85 - jaw_factor * 0.15);
        let mut pb = PathBuilder::new();
        pb.move_to((hcx - rx) as f32, cy as f32);
        pb.quad_to(
            (hcx - rx) as f32,
            (cy - ry) as f32,
            hcx as f32,
            (cy - ry) as f32,
        );
        pb.quad_to(
            (hcx + rx) as f32,
            (cy - ry) as f32,
            (hcx + rx) as f32,
            cy as f32,
        );
        pb.quad_to(
            (hcx + rx) as f32,
            (cy + eff_ry * 0.5) as f32,
            (hcx + jaw_w) as f32,
            (cy + eff_ry * (0.7 + jaw_factor * 0.2)) as f32,
        );
        pb.quad_to(
            (hcx + jaw_w * 0.3) as f32,
            (cy + eff_ry * (1.0 + jaw_factor * 0.1)) as f32,
            hcx as f32,
            (cy + eff_ry * (1.0 + jaw_factor * 0.05)) as f32,
        );
        pb.quad_to(
            (hcx - jaw_w * 0.3) as f32,
            (cy + eff_ry * (1.0 + jaw_factor * 0.1)) as f32,
            (hcx - jaw_w) as f32,
            (cy + eff_ry * (0.7 + jaw_factor * 0.2)) as f32,
        );
        pb.quad_to(
            (hcx - rx) as f32,
            (cy + eff_ry * 0.5) as f32,
            (hcx - rx) as f32,
            cy as f32,
        );
        pb.close();
        pb.finish()
    };

    let transform = tilt_transform(tilt_rad, cx, cy);

    // Main head fill + two-tone shading + dark outline.
    if let Some(head_path) = build_head_path(0.0, 0.0) {
        let paint = solid_paint(skin[0], skin[1], skin[2], opacity);
        pixmap.fill_path(&head_path, &paint, FillRule::Winding, transform, None);

        // Two-tone shading: crescent shadow on the right side of the head.
        let shadow_c = shade_color(skin, 0.15);
        let shadow_paint = solid_paint(shadow_c[0], shadow_c[1], shadow_c[2], opacity * 0.55);
        if let Some(shadow_path) = build_head_path(rx * 0.2, 0.0) {
            pixmap.fill_path(
                &shadow_path,
                &shadow_paint,
                FillRule::Winding,
                transform,
                None,
            );
        }

        // Dark outline around head (2px, skin darkened 40 per channel).
        let ol_c = [
            skin[0].saturating_sub(40),
            skin[1].saturating_sub(40),
            skin[2].saturating_sub(40),
        ];
        let ol_paint = solid_paint(ol_c[0], ol_c[1], ol_c[2], opacity);
        let head_stroke = Stroke {
            width: 2.0,
            line_cap: LineCap::Round,
            line_join: LineJoin::Round,
            ..Stroke::default()
        };
        pixmap.stroke_path(&head_path, &ol_paint, &head_stroke, transform, None);
    }

    // Ears with outlines — perspective-aware visibility.
    let ear_y = cy;
    let ear_c = [
        skin[0].saturating_sub(10),
        skin[1].saturating_sub(10),
        skin[2].saturating_sub(10),
    ];
    let ear_ol = [
        skin[0].saturating_sub(40),
        skin[1].saturating_sub(40),
        skin[2].saturating_sub(40),
    ];
    let ear_r = r * 0.18;
    // Near ear is more visible, far ear hides when turned.
    let near_ear_scale = 1.0 + turn_factor.abs() * 0.3;
    let far_ear_scale = (1.0 - turn_factor.abs() * 1.5).max(0.0);
    // Left ear: at cx - rx * 0.95. If turn_factor > 0 (turning right), left ear is far.
    let left_ear_scale = if turn_factor > 0.0 {
        far_ear_scale
    } else {
        near_ear_scale
    };
    let right_ear_scale = if turn_factor > 0.0 {
        near_ear_scale
    } else {
        far_ear_scale
    };
    for &(ear_x, ear_sc) in &[
        (cx - rx * 0.95, left_ear_scale),
        (cx + rx * 0.95, right_ear_scale),
    ] {
        if ear_sc > 0.05 {
            let scaled_ear_r = ear_r * ear_sc;
            let ep = solid_paint(ear_c[0], ear_c[1], ear_c[2], opacity);
            fill_circle_t(pixmap, ear_x, ear_y, scaled_ear_r, &ep, tilt_rad, cx, cy);
            let eop = solid_paint(ear_ol[0], ear_ol[1], ear_ol[2], opacity);
            stroke_circle_t(
                pixmap,
                ear_x,
                ear_y,
                scaled_ear_r,
                &eop,
                1.5,
                tilt_rad,
                cx,
                cy,
            );
        }
    }

    // Eye geometry — computed once for both face drawing and accessories.
    let eye_y = cy - ry * 0.05 + nod_rad * 3.0;
    let eye_spacing = rx * 0.38;
    let eye_r = r * 0.14 * desc.face.eye_size.max(0.5);

    // Face feature offset — features shift in the turn direction.
    let face_offset = turn_factor * rx * 0.4;

    // Eye scaling for far/near eyes.
    let far_eye_scale = (0.2 + 0.8 * front_factor.abs()).max(0.0);

    if !back_view {
        // Determine which eye is far based on turn direction.
        // turn_factor > 0 (turning right): left eye is far
        let left_eye_r = if turn_factor > 0.0 {
            eye_r * far_eye_scale
        } else {
            eye_r
        };
        let right_eye_r = if turn_factor > 0.0 {
            eye_r
        } else {
            eye_r * far_eye_scale
        };

        // Left eye (don't draw if too small / hidden behind head in profile).
        if left_eye_r > eye_r * 0.15 {
            draw_eye(
                pixmap,
                desc,
                state,
                cx + face_offset - eye_spacing * flip,
                eye_y,
                left_eye_r,
                state.expression.eye_open_left,
                state.expression.eyebrow_left,
                scale,
                flip,
                opacity,
                tilt_rad,
                cx,
                cy,
            );
        }
        // Right eye.
        if right_eye_r > eye_r * 0.15 {
            draw_eye(
                pixmap,
                desc,
                state,
                cx + face_offset + eye_spacing * flip,
                eye_y,
                right_eye_r,
                state.expression.eye_open_right,
                state.expression.eyebrow_right,
                scale,
                flip,
                opacity,
                tilt_rad,
                cx,
                cy,
            );
        }

        // Nose with bridge highlight — profile-aware position.
        let nose_y = cy + ry * 0.2 + nod_rad * 2.0;
        let nose_size = r * 0.08 * (0.5 + desc.face.nose_size * 0.8);
        let nose_c = [
            skin[0].saturating_sub(15),
            skin[1].saturating_sub(15),
            skin[2].saturating_sub(15),
        ];
        let nose_paint = solid_paint(nose_c[0], nose_c[1], nose_c[2], opacity);
        // When nearly profile, nose protrudes beyond the head silhouette.
        let nose_x = cx + face_offset + turn_factor.signum() * nose_size * 0.8 * turn_factor.abs();
        {
            let mut pb = PathBuilder::new();
            pb.move_to(nose_x as f32, (nose_y - nose_size) as f32);
            pb.quad_to(
                (nose_x + nose_size * 1.2) as f32,
                (nose_y + nose_size * 0.5) as f32,
                nose_x as f32,
                (nose_y + nose_size) as f32,
            );
            pb.quad_to(
                (nose_x - nose_size * 1.2) as f32,
                (nose_y + nose_size * 0.5) as f32,
                nose_x as f32,
                (nose_y - nose_size) as f32,
            );
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &nose_paint, FillRule::Winding, transform, None);
            }
        }
        // Small lighter spot on the nose bridge.
        let hl_paint = solid_paint(
            skin[0].saturating_add(25),
            skin[1].saturating_add(25),
            skin[2].saturating_add(25),
            opacity * 0.5,
        );
        fill_circle_t(
            pixmap,
            nose_x - nose_size * 0.15,
            nose_y - nose_size * 0.35,
            nose_size * 0.3,
            &hl_paint,
            tilt_rad,
            cx,
            cy,
        );

        // Mouth (jaw-stretch-aware positioning).
        let eff_ry_bottom = ry * (1.0 + jaw_stretch);
        let mouth_y = cy + eff_ry_bottom * 0.5 + nod_rad * 1.5;
        draw_mouth(
            pixmap,
            desc,
            state,
            cx + face_offset,
            mouth_y,
            r,
            scale,
            opacity,
            tilt_rad,
            cx,
            cy,
        );
    }
    // back_view: don't draw eyes, nose, mouth — just the hair back is already drawn

    // Hair (front).
    draw_hair_front(
        pixmap,
        desc,
        cx,
        cy,
        rx,
        ry,
        scale,
        flip,
        opacity,
        tilt_rad,
        state.hair_swing,
    );

    // Accessories.
    for acc in &desc.outfit.accessories {
        match acc.kind {
            AccessoryKind::Fedora => {
                draw_fedora(
                    pixmap,
                    cx,
                    cy - ry * 0.75,
                    rx * 1.5,
                    r * 0.5,
                    acc.color,
                    opacity,
                    tilt_rad,
                    cx,
                    cy,
                );
            }
            AccessoryKind::Glasses => {
                if !back_view {
                    draw_glasses(
                        pixmap,
                        cx + face_offset,
                        eye_y,
                        eye_spacing,
                        eye_r,
                        acc.color,
                        opacity,
                        tilt_rad,
                        cx,
                        cy,
                    );
                }
            }
            AccessoryKind::Tie => {
                // Handled in torso drawing.
            }
            _ => {}
        }
    }
}

fn draw_eye(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    state: &CharacterState,
    cx: f64,
    cy: f64,
    r: f64,
    openness: f64,
    eyebrow_pos: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    tilt: f64,
    rot_cx: f64,
    rot_cy: f64,
) {
    let transform = tilt_transform(tilt, rot_cx, rot_cy);

    // Eye white.
    let eye_h = r * openness.max(0.1);
    let white_paint = solid_paint(240, 240, 240, opacity);

    // Build the eye-white path (reused for outline & eyelid lines).
    let build_eye_path = || -> Option<tiny_skia::Path> {
        let mut pb = PathBuilder::new();
        pb.move_to((cx - r) as f32, cy as f32);
        pb.quad_to(
            (cx - r) as f32,
            (cy - eye_h) as f32,
            cx as f32,
            (cy - eye_h) as f32,
        );
        pb.quad_to(
            (cx + r) as f32,
            (cy - eye_h) as f32,
            (cx + r) as f32,
            cy as f32,
        );
        pb.quad_to(
            (cx + r) as f32,
            (cy + eye_h) as f32,
            cx as f32,
            (cy + eye_h) as f32,
        );
        pb.quad_to(
            (cx - r) as f32,
            (cy + eye_h) as f32,
            (cx - r) as f32,
            cy as f32,
        );
        pb.finish()
    };

    if let Some(eye_path) = build_eye_path() {
        // Fill eye white.
        pixmap.fill_path(&eye_path, &white_paint, FillRule::Winding, transform, None);

        // Dark outline around eye white (1px, dark gray).
        let eye_ol_paint = solid_paint(50, 50, 50, opacity);
        let eye_ol_stroke = Stroke {
            width: 1.0,
            line_cap: LineCap::Round,
            line_join: LineJoin::Round,
            ..Stroke::default()
        };
        pixmap.stroke_path(&eye_path, &eye_ol_paint, &eye_ol_stroke, transform, None);
    }

    // Upper eyelid line — thick curved line along top of eye (makes cartoon eyes alive).
    {
        let mut pb = PathBuilder::new();
        pb.move_to((cx - r) as f32, cy as f32);
        pb.quad_to(
            (cx - r) as f32,
            (cy - eye_h) as f32,
            cx as f32,
            (cy - eye_h) as f32,
        );
        pb.quad_to(
            (cx + r) as f32,
            (cy - eye_h) as f32,
            (cx + r) as f32,
            cy as f32,
        );
        if let Some(lid_path) = pb.finish() {
            let lid_paint = solid_paint(30, 30, 30, opacity);
            let lid_stroke = Stroke {
                width: 2.0,
                line_cap: LineCap::Round,
                ..Stroke::default()
            };
            pixmap.stroke_path(&lid_path, &lid_paint, &lid_stroke, transform, None);
        }
    }

    // Lower eyelash hint — thin line along bottom (0.5px).
    {
        let mut pb = PathBuilder::new();
        pb.move_to((cx - r * 0.8) as f32, (cy + eye_h * 0.6) as f32);
        pb.quad_to(
            cx as f32,
            (cy + eye_h * 1.05) as f32,
            (cx + r * 0.8) as f32,
            (cy + eye_h * 0.6) as f32,
        );
        if let Some(lash_path) = pb.finish() {
            let lash_paint = solid_paint(60, 50, 50, opacity * 0.6);
            let lash_stroke = Stroke {
                width: 0.5,
                line_cap: LineCap::Round,
                ..Stroke::default()
            };
            pixmap.stroke_path(&lash_path, &lash_paint, &lash_stroke, transform, None);
        }
    }

    // Iris + pupil.
    if openness > 0.15 {
        let iris_r = r * 0.55;
        let pupil_r = r * 0.3;
        let look_x = state.expression.eye_direction * r * 0.25;
        let ec = desc.face.eye_color;

        // Darker ring around iris edge (draw slightly larger circle first).
        let ring_c = shade_color(ec, 0.25);
        let ring_paint = solid_paint(ring_c[0], ring_c[1], ring_c[2], opacity);
        fill_circle_t(
            pixmap,
            cx + look_x,
            cy,
            iris_r * 1.08,
            &ring_paint,
            tilt,
            rot_cx,
            rot_cy,
        );

        // Iris fill.
        let iris_paint = solid_paint(ec[0], ec[1], ec[2], opacity);
        fill_circle_t(
            pixmap,
            cx + look_x,
            cy,
            iris_r,
            &iris_paint,
            tilt,
            rot_cx,
            rot_cy,
        );

        // Pupil.
        let pupil_paint = solid_paint(10, 10, 10, opacity);
        fill_circle_t(
            pixmap,
            cx + look_x,
            cy,
            pupil_r,
            &pupil_paint,
            tilt,
            rot_cx,
            rot_cy,
        );

        // Highlight (slightly larger than before).
        let hl = solid_paint(255, 255, 255, opacity * 0.8);
        fill_circle_t(
            pixmap,
            cx + look_x - iris_r * 0.25,
            cy - iris_r * 0.25,
            r * 0.16,
            &hl,
            tilt,
            rot_cx,
            rot_cy,
        );
    }

    // Eyebrow — filled tapered shape instead of stroked line.
    let brow_y = cy - r * (1.3 + eyebrow_pos * 0.3);
    let brow_w = r * 1.1;
    let brow_thickness = (1.5 + desc.face.eyebrow_thickness * 2.0) * 0.5;
    let hair_c = desc.hair.color;
    let brow_paint = solid_paint(hair_c[0], hair_c[1], hair_c[2], opacity);

    // Angle based on expression.
    let inner_y = brow_y + eyebrow_pos * 2.0;
    let outer_y = brow_y - eyebrow_pos * 1.5;
    let mid_y = brow_y - eyebrow_pos.abs() * 1.0;
    let dir = if cx < rot_cx { -1.0 } else { 1.0 };

    // Inner end (thicker) and outer end (thinner).
    let inner_x = cx + brow_w * dir * 0.5;
    let outer_x = cx - brow_w * dir * 0.5;
    let thick_inner = brow_thickness * 1.2; // thick end
    let thick_outer = brow_thickness * 0.5; // thin end
    let thick_mid = brow_thickness * 1.0;

    {
        let mut pb = PathBuilder::new();
        // Top edge of brow.
        pb.move_to(outer_x as f32, (outer_y - thick_outer) as f32);
        pb.quad_to(
            cx as f32,
            (mid_y - thick_mid) as f32,
            inner_x as f32,
            (inner_y - thick_inner) as f32,
        );
        // Bottom edge of brow (reverse direction).
        pb.line_to(inner_x as f32, (inner_y + thick_inner) as f32);
        pb.quad_to(
            cx as f32,
            (mid_y + thick_mid) as f32,
            outer_x as f32,
            (outer_y + thick_outer) as f32,
        );
        pb.close();
        if let Some(path) = pb.finish() {
            pixmap.fill_path(&path, &brow_paint, FillRule::Winding, transform, None);
        }
    }
}

fn draw_mouth(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    state: &CharacterState,
    cx: f64,
    cy: f64,
    head_r: f64,
    scale: f64,
    opacity: f64,
    tilt: f64,
    rot_cx: f64,
    rot_cy: f64,
) {
    let transform = tilt_transform(tilt, rot_cx, rot_cy);
    let mouth_w = head_r * 0.35 * (0.7 + desc.face.lip_fullness * 0.6);
    let smile = state.expression.mouth_smile;
    let open = state.expression.mouth_open;

    if open > 0.1 {
        // Open mouth — dark interior.
        let mouth_h = head_r * 0.12 * open;
        let mouth_paint = solid_paint(60, 20, 20, opacity);
        let mut pb = PathBuilder::new();
        pb.move_to((cx - mouth_w) as f32, cy as f32);
        pb.quad_to(
            (cx - mouth_w * 0.5) as f32,
            (cy - smile * mouth_h * 0.3) as f32,
            cx as f32,
            (cy - smile * mouth_h * 0.5) as f32,
        );
        pb.quad_to(
            (cx + mouth_w * 0.5) as f32,
            (cy - smile * mouth_h * 0.3) as f32,
            (cx + mouth_w) as f32,
            cy as f32,
        );
        pb.quad_to(
            (cx + mouth_w * 0.5) as f32,
            (cy + mouth_h) as f32,
            cx as f32,
            (cy + mouth_h) as f32,
        );
        pb.quad_to(
            (cx - mouth_w * 0.5) as f32,
            (cy + mouth_h) as f32,
            (cx - mouth_w) as f32,
            cy as f32,
        );
        if let Some(path) = pb.finish() {
            pixmap.fill_path(&path, &mouth_paint, FillRule::Winding, transform, None);
        }

        // Teeth hint — thin white strip at top of mouth opening.
        if mouth_h > 1.0 {
            let teeth_h = mouth_h * 0.25;
            let top_y = cy - smile * mouth_h * 0.5;
            let teeth_paint = solid_paint(240, 235, 230, opacity * 0.85);
            let mut pb = PathBuilder::new();
            pb.move_to((cx - mouth_w * 0.7) as f32, (top_y + 0.5) as f32);
            pb.quad_to(
                cx as f32,
                (top_y + 0.5) as f32,
                (cx + mouth_w * 0.7) as f32,
                (top_y + 0.5) as f32,
            );
            pb.line_to((cx + mouth_w * 0.7) as f32, (top_y + teeth_h) as f32);
            pb.quad_to(
                cx as f32,
                (top_y + teeth_h + 1.0) as f32,
                (cx - mouth_w * 0.7) as f32,
                (top_y + teeth_h) as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &teeth_paint, FillRule::Winding, transform, None);
            }
        }

        // Tongue hint — small pink/red curved shape at bottom of mouth opening.
        if mouth_h > 2.0 {
            let tongue_paint = solid_paint(180, 70, 70, opacity * 0.7);
            let tongue_w = mouth_w * 0.45;
            let tongue_y = cy + mouth_h;
            let mut pb = PathBuilder::new();
            pb.move_to((cx - tongue_w) as f32, tongue_y as f32);
            pb.quad_to(
                cx as f32,
                (tongue_y - mouth_h * 0.4) as f32,
                (cx + tongue_w) as f32,
                tongue_y as f32,
            );
            pb.quad_to(
                cx as f32,
                (tongue_y + mouth_h * 0.15) as f32,
                (cx - tongue_w) as f32,
                tongue_y as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &tongue_paint, FillRule::Winding, transform, None);
            }
        }

        // Lip outline — thin darker line around mouth edges.
        {
            let lip_ol_paint = solid_paint(40, 15, 15, opacity * 0.8);
            let lip_stroke = Stroke {
                width: 1.0,
                line_cap: LineCap::Round,
                line_join: LineJoin::Round,
                ..Stroke::default()
            };
            let mut pb = PathBuilder::new();
            pb.move_to((cx - mouth_w) as f32, cy as f32);
            pb.quad_to(
                (cx - mouth_w * 0.5) as f32,
                (cy - smile * mouth_h * 0.3) as f32,
                cx as f32,
                (cy - smile * mouth_h * 0.5) as f32,
            );
            pb.quad_to(
                (cx + mouth_w * 0.5) as f32,
                (cy - smile * mouth_h * 0.3) as f32,
                (cx + mouth_w) as f32,
                cy as f32,
            );
            pb.quad_to(
                (cx + mouth_w * 0.5) as f32,
                (cy + mouth_h) as f32,
                cx as f32,
                (cy + mouth_h) as f32,
            );
            pb.quad_to(
                (cx - mouth_w * 0.5) as f32,
                (cy + mouth_h) as f32,
                (cx - mouth_w) as f32,
                cy as f32,
            );
            if let Some(path) = pb.finish() {
                pixmap.stroke_path(&path, &lip_ol_paint, &lip_stroke, transform, None);
            }
        }
    } else {
        // Closed mouth — thicker line with subtle lip coloring.
        let lip_c = desc.body.skin_color;
        let curve = smile * head_r * 0.08;

        // Subtle lip fill (slightly pink/red tinted area around the line).
        {
            let lip_fill_c = [
                ((lip_c[0] as f64 * 0.85 + 180.0 * 0.15).min(255.0)) as u8,
                ((lip_c[1] as f64 * 0.85 + 60.0 * 0.15).min(255.0)) as u8,
                ((lip_c[2] as f64 * 0.85 + 60.0 * 0.15).min(255.0)) as u8,
            ];
            let lip_fill_paint =
                solid_paint(lip_fill_c[0], lip_fill_c[1], lip_fill_c[2], opacity * 0.3);
            let lip_thickness = 1.5 + desc.face.lip_fullness * 1.5;
            let mut pb = PathBuilder::new();
            pb.move_to((cx - mouth_w) as f32, cy as f32);
            pb.quad_to(
                cx as f32,
                (cy - curve - lip_thickness) as f32,
                (cx + mouth_w) as f32,
                cy as f32,
            );
            pb.quad_to(
                cx as f32,
                (cy - curve + lip_thickness) as f32,
                (cx - mouth_w) as f32,
                cy as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &lip_fill_paint, FillRule::Winding, transform, None);
            }
        }

        // Main closed mouth line (slightly thicker than before).
        let lip_paint = solid_paint(
            lip_c[0].saturating_sub(50),
            lip_c[1].saturating_sub(50),
            lip_c[2].saturating_sub(50),
            opacity,
        );
        let stroke = Stroke {
            width: (2.0 + desc.face.lip_fullness * 1.2) as f32,
            line_cap: LineCap::Round,
            ..Stroke::default()
        };
        let mut pb = PathBuilder::new();
        pb.move_to((cx - mouth_w) as f32, cy as f32);
        pb.quad_to(
            cx as f32,
            (cy - curve) as f32,
            (cx + mouth_w) as f32,
            cy as f32,
        );
        if let Some(path) = pb.finish() {
            pixmap.stroke_path(&path, &lip_paint, &stroke, transform, None);
        }
    }
}

fn draw_hair_back(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    cx: f64,
    cy: f64,
    rx: f64,
    ry: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    tilt: f64,
    hair_swing: f64,
) {
    let c = desc.hair.color;
    let paint = solid_paint(c[0], c[1], c[2], opacity);
    let dark_c = shade_color(c, 0.30);
    let ol_paint = solid_paint(dark_c[0], dark_c[1], dark_c[2], opacity);
    let ol_stroke = Stroke {
        width: 1.5,
        line_cap: LineCap::Round,
        line_join: LineJoin::Round,
        ..Stroke::default()
    };
    // Horizontal offset from hair swing (secondary motion).
    let swing_offset = hair_swing * scale * 0.3;

    match desc.hair.style {
        HairStyle::Straight | HairStyle::Wavy => {
            if desc.hair.length > 0.3 {
                let hair_len = ry * (0.5 + desc.hair.length * 1.2);
                let transform = tilt_transform(tilt, cx, cy);
                let mut pb = PathBuilder::new();
                // Top anchored near head, bottom tips sway with swing.
                pb.move_to((cx - rx * 0.9) as f32, (cy - ry * 0.2) as f32);
                pb.quad_to(
                    (cx - rx * 1.1 + swing_offset * 0.5) as f32,
                    (cy + hair_len * 0.5) as f32,
                    (cx - rx * 0.7 + swing_offset) as f32,
                    (cy + hair_len) as f32,
                );
                pb.line_to(
                    (cx + rx * 0.7 + swing_offset) as f32,
                    (cy + hair_len) as f32,
                );
                pb.quad_to(
                    (cx + rx * 1.1 + swing_offset * 0.5) as f32,
                    (cy + hair_len * 0.5) as f32,
                    (cx + rx * 0.9) as f32,
                    (cy - ry * 0.2) as f32,
                );
                pb.close();
                if let Some(path) = pb.finish() {
                    pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
                    // Outline.
                    pixmap.stroke_path(&path, &ol_paint, &ol_stroke, transform, None);
                }

                // Hair strand lines (3-4 curved lines in slightly darker shade).
                let strand_c = shade_color(c, 0.15);
                let strand_paint =
                    solid_paint(strand_c[0], strand_c[1], strand_c[2], opacity * 0.5);
                let strand_stroke = Stroke {
                    width: 0.8,
                    line_cap: LineCap::Round,
                    ..Stroke::default()
                };
                for i in 0..4 {
                    let t = (i as f64 + 1.0) / 5.0;
                    let sx = cx + rx * (t * 1.4 - 0.7) + swing_offset * t;
                    let mut pb = PathBuilder::new();
                    pb.move_to(sx as f32, (cy - ry * 0.1) as f32);
                    pb.quad_to(
                        (sx + swing_offset * 0.3) as f32,
                        (cy + hair_len * 0.5) as f32,
                        (sx + swing_offset * 0.6) as f32,
                        (cy + hair_len * 0.9) as f32,
                    );
                    if let Some(path) = pb.finish() {
                        pixmap.stroke_path(&path, &strand_paint, &strand_stroke, transform, None);
                    }
                }
            }
        }
        _ => {}
    }
}

fn draw_hair_front(
    pixmap: &mut Pixmap,
    desc: &CharacterDesc,
    cx: f64,
    cy: f64,
    rx: f64,
    ry: f64,
    scale: f64,
    flip: f64,
    opacity: f64,
    tilt: f64,
    hair_swing: f64,
) {
    let c = desc.hair.color;
    let paint = solid_paint(c[0], c[1], c[2], opacity);
    let transform = tilt_transform(tilt, cx, cy);
    // Horizontal offset from hair swing (secondary motion) — front hair uses smaller offset.
    let sw = hair_swing * scale * 0.15;

    // Common outline setup.
    let dark_c = shade_color(c, 0.30);
    let ol_paint = solid_paint(dark_c[0], dark_c[1], dark_c[2], opacity);
    let ol_stroke = Stroke {
        width: 1.5,
        line_cap: LineCap::Round,
        line_join: LineJoin::Round,
        ..Stroke::default()
    };

    // Helper: draw hair strand lines across the front hair cap.
    let draw_front_strands = |pixmap: &mut Pixmap, top_y: f64, bottom_y: f64| {
        let strand_c = shade_color(c, 0.15);
        let strand_paint = solid_paint(strand_c[0], strand_c[1], strand_c[2], opacity * 0.4);
        let strand_stroke = Stroke {
            width: 0.7,
            line_cap: LineCap::Round,
            ..Stroke::default()
        };
        for i in 0..5 {
            let t = (i as f64 + 1.0) / 6.0;
            let sx = cx + rx * (t * 1.6 - 0.8);
            let mut pb = PathBuilder::new();
            pb.move_to(sx as f32, top_y as f32);
            pb.quad_to(
                (sx + sw * 0.5) as f32,
                ((top_y + bottom_y) * 0.5) as f32,
                (sx + sw * 0.3) as f32,
                bottom_y as f32,
            );
            if let Some(path) = pb.finish() {
                pixmap.stroke_path(&path, &strand_paint, &strand_stroke, transform, None);
            }
        }
    };

    match desc.hair.style {
        HairStyle::SlickedBack => {
            let mut pb = PathBuilder::new();
            pb.move_to((cx - rx * 0.9) as f32, (cy - ry * 0.1) as f32);
            pb.quad_to(
                (cx - rx) as f32,
                (cy - ry * 0.8) as f32,
                cx as f32,
                (cy - ry * 0.95) as f32,
            );
            pb.quad_to(
                (cx + rx) as f32,
                (cy - ry * 0.8) as f32,
                (cx + rx * 0.9) as f32,
                (cy - ry * 0.1) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.6) as f32,
                (cy - ry * 0.5) as f32,
                cx as f32,
                (cy - ry * 0.55) as f32,
            );
            pb.quad_to(
                (cx - rx * 0.6) as f32,
                (cy - ry * 0.5) as f32,
                (cx - rx * 0.9) as f32,
                (cy - ry * 0.1) as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
                pixmap.stroke_path(&path, &ol_paint, &ol_stroke, transform, None);
            }
            draw_front_strands(pixmap, cy - ry * 0.9, cy - ry * 0.5);
        }
        HairStyle::Messy => {
            let mut pb = PathBuilder::new();
            pb.move_to((cx - rx * 0.85) as f32, (cy - ry * 0.1) as f32);
            pb.quad_to(
                (cx - rx * 0.9) as f32,
                (cy - ry * 0.9) as f32,
                (cx - rx * 0.3) as f32,
                (cy - ry * 1.05) as f32,
            );
            // Spikes — curved tips (quad_to for curved spike tips instead of line_to).
            pb.quad_to(
                (cx - rx * 0.25 + sw) as f32,
                (cy - ry * 1.18) as f32,
                (cx - rx * 0.2 + sw) as f32,
                (cy - ry * 1.25) as f32,
            );
            pb.quad_to(
                (cx - rx * 0.05 + sw * 0.8) as f32,
                (cy - ry * 1.08) as f32,
                (cx + sw * 0.7) as f32,
                (cy - ry * 1.0) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.08 + sw * 0.9) as f32,
                (cy - ry * 1.18) as f32,
                (cx + rx * 0.15 + sw) as f32,
                (cy - ry * 1.3) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.22 + sw * 0.85) as f32,
                (cy - ry * 1.1) as f32,
                (cx + rx * 0.3 + sw * 0.7) as f32,
                (cy - ry * 1.0) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.38 + sw * 0.9) as f32,
                (cy - ry * 1.08) as f32,
                (cx + rx * 0.45 + sw) as f32,
                (cy - ry * 1.15) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.9) as f32,
                (cy - ry * 0.9) as f32,
                (cx + rx * 0.85) as f32,
                (cy - ry * 0.1) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.6) as f32,
                (cy - ry * 0.5) as f32,
                cx as f32,
                (cy - ry * 0.5) as f32,
            );
            pb.quad_to(
                (cx - rx * 0.6) as f32,
                (cy - ry * 0.5) as f32,
                (cx - rx * 0.85) as f32,
                (cy - ry * 0.1) as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
                pixmap.stroke_path(&path, &ol_paint, &ol_stroke, transform, None);
            }
            draw_front_strands(pixmap, cy - ry * 1.0, cy - ry * 0.5);
        }
        HairStyle::Straight | HairStyle::Wavy => {
            // Top hair cap.
            let mut pb = PathBuilder::new();
            pb.move_to((cx - rx * 0.9) as f32, (cy - ry * 0.1) as f32);
            pb.quad_to(
                (cx - rx * 1.0) as f32,
                (cy - ry * 0.9) as f32,
                cx as f32,
                (cy - ry * 0.95) as f32,
            );
            pb.quad_to(
                (cx + rx * 1.0) as f32,
                (cy - ry * 0.9) as f32,
                (cx + rx * 0.9) as f32,
                (cy - ry * 0.1) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.6) as f32,
                (cy - ry * 0.55) as f32,
                cx as f32,
                (cy - ry * 0.55) as f32,
            );
            pb.quad_to(
                (cx - rx * 0.6) as f32,
                (cy - ry * 0.55) as f32,
                (cx - rx * 0.9) as f32,
                (cy - ry * 0.1) as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
                pixmap.stroke_path(&path, &ol_paint, &ol_stroke, transform, None);
            }
            draw_front_strands(pixmap, cy - ry * 0.9, cy - ry * 0.55);
        }
        HairStyle::Short | HairStyle::Buzz => {
            let mut pb = PathBuilder::new();
            pb.move_to((cx - rx * 0.85) as f32, (cy - ry * 0.15) as f32);
            pb.quad_to(
                (cx - rx * 0.9) as f32,
                (cy - ry * 0.85) as f32,
                cx as f32,
                (cy - ry * 0.9) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.9) as f32,
                (cy - ry * 0.85) as f32,
                (cx + rx * 0.85) as f32,
                (cy - ry * 0.15) as f32,
            );
            pb.quad_to(
                (cx + rx * 0.55) as f32,
                (cy - ry * 0.5) as f32,
                cx as f32,
                (cy - ry * 0.5) as f32,
            );
            pb.quad_to(
                (cx - rx * 0.55) as f32,
                (cy - ry * 0.5) as f32,
                (cx - rx * 0.85) as f32,
                (cy - ry * 0.15) as f32,
            );
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
                pixmap.stroke_path(&path, &ol_paint, &ol_stroke, transform, None);
            }
            // Short hair: just 3 strand lines.
            let strand_c = shade_color(c, 0.15);
            let strand_paint = solid_paint(strand_c[0], strand_c[1], strand_c[2], opacity * 0.35);
            let strand_stroke = Stroke {
                width: 0.6,
                line_cap: LineCap::Round,
                ..Stroke::default()
            };
            for i in 0..3 {
                let t = (i as f64 + 1.0) / 4.0;
                let sx = cx + rx * (t * 1.4 - 0.7);
                let mut pb = PathBuilder::new();
                pb.move_to(sx as f32, (cy - ry * 0.85) as f32);
                pb.quad_to(
                    sx as f32,
                    (cy - ry * 0.65) as f32,
                    sx as f32,
                    (cy - ry * 0.5) as f32,
                );
                if let Some(path) = pb.finish() {
                    pixmap.stroke_path(&path, &strand_paint, &strand_stroke, transform, None);
                }
            }
        }
        HairStyle::Bald => {
            // No hair at all — the head skin is the scalp. Add a soft highlight
            // on the crown so the bald head reads as shiny rather than flat.
            let highlight = solid_paint(255, 255, 255, opacity * 0.16);
            let hx = cx - rx * 0.22;
            let hy = cy - ry * 0.42;
            let hrx = rx * 0.34;
            let hry = ry * 0.26;
            let mut pb = PathBuilder::new();
            let steps = 24;
            for i in 0..=steps {
                let a = (i as f64 / steps as f64) * 2.0 * PI;
                let px = hx + a.cos() * hrx;
                let py = hy + a.sin() * hry;
                if i == 0 {
                    pb.move_to(px as f32, py as f32);
                } else {
                    pb.line_to(px as f32, py as f32);
                }
            }
            pb.close();
            if let Some(path) = pb.finish() {
                pixmap.fill_path(&path, &highlight, FillRule::Winding, transform, None);
            }
        }
    }
}

fn draw_fedora(
    pixmap: &mut Pixmap,
    cx: f64,
    cy: f64,
    brim_w: f64,
    crown_h: f64,
    color: [u8; 3],
    opacity: f64,
    tilt: f64,
    rot_cx: f64,
    rot_cy: f64,
) {
    let transform = tilt_transform(tilt, rot_cx, rot_cy);
    let mut paint = solid_paint(color[0], color[1], color[2], opacity);
    let mut dark = solid_paint(
        color[0].saturating_sub(20),
        color[1].saturating_sub(20),
        color[2].saturating_sub(20),
        opacity,
    );

    // Crown.
    let mut pb = PathBuilder::new();
    pb.move_to((cx - brim_w * 0.4) as f32, cy as f32);
    pb.quad_to(
        (cx - brim_w * 0.35) as f32,
        (cy - crown_h) as f32,
        cx as f32,
        (cy - crown_h * 0.9) as f32,
    );
    pb.quad_to(
        (cx + brim_w * 0.35) as f32,
        (cy - crown_h) as f32,
        (cx + brim_w * 0.4) as f32,
        cy as f32,
    );
    pb.close();
    if let Some(path) = pb.finish() {
        pixmap.fill_path(&path, &paint, FillRule::Winding, transform, None);
    }

    // Brim.
    let mut pb = PathBuilder::new();
    pb.move_to((cx - brim_w * 0.5) as f32, (cy + 2.0) as f32);
    pb.quad_to(
        cx as f32,
        (cy - 3.0) as f32,
        (cx + brim_w * 0.5) as f32,
        (cy + 2.0) as f32,
    );
    pb.quad_to(
        cx as f32,
        (cy + 6.0) as f32,
        (cx - brim_w * 0.5) as f32,
        (cy + 2.0) as f32,
    );
    if let Some(path) = pb.finish() {
        pixmap.fill_path(&path, &dark, FillRule::Winding, transform, None);
    }

    // Band.
    let stroke = Stroke {
        width: 2.5,
        ..Stroke::default()
    };
    let mut band = solid_paint(
        color[0].saturating_sub(40),
        color[1].saturating_sub(40),
        color[2].saturating_sub(40),
        opacity,
    );
    let mut pb = PathBuilder::new();
    pb.move_to((cx - brim_w * 0.38) as f32, cy as f32);
    pb.quad_to(
        cx as f32,
        (cy - 2.0) as f32,
        (cx + brim_w * 0.38) as f32,
        cy as f32,
    );
    if let Some(path) = pb.finish() {
        pixmap.stroke_path(&path, &band, &stroke, transform, None);
    }
}

fn draw_glasses(
    pixmap: &mut Pixmap,
    cx: f64,
    eye_y: f64,
    spacing: f64,
    eye_r: f64,
    color: [u8; 3],
    opacity: f64,
    tilt: f64,
    rot_cx: f64,
    rot_cy: f64,
) {
    let transform = tilt_transform(tilt, rot_cx, rot_cy);
    let mut paint = solid_paint(color[0], color[1], color[2], opacity);
    let stroke = Stroke {
        width: 1.8,
        line_cap: LineCap::Round,
        line_join: LineJoin::Round,
        ..Stroke::default()
    };

    // Round lenses — the signature "Fredi" look.
    let lens_r = eye_r * 1.55;

    // Helper: build a circle path centered at (ccx, ccy).
    let circle_path = |ccx: f64, ccy: f64, r: f64| -> Option<Path> {
        let mut pb = PathBuilder::new();
        let steps = 28;
        for i in 0..=steps {
            let a = (i as f64 / steps as f64) * 2.0 * PI;
            let px = ccx + a.cos() * r;
            let py = ccy + a.sin() * r;
            if i == 0 {
                pb.move_to(px as f32, py as f32);
            } else {
                pb.line_to(px as f32, py as f32);
            }
        }
        pb.close();
        pb.finish()
    };

    // Semi-tinted lens fill + a diagonal glint — reads as dark glasses without
    // fully hiding the eyes (Statham/Woland).
    let tint = solid_paint(26, 26, 32, opacity * 0.5);
    let glint = solid_paint(240, 240, 245, opacity * 0.4);
    let lx = cx - spacing;
    let rx_pos = cx + spacing;
    for &cxl in &[lx, rx_pos] {
        if let Some(path) = circle_path(cxl, eye_y, lens_r) {
            pixmap.fill_path(&path, &tint, FillRule::Winding, transform, None);
            pixmap.stroke_path(&path, &paint, &stroke, transform, None);
        }
        // Glint: a short diagonal stroke across the upper-left of the lens.
        let mut gb = PathBuilder::new();
        gb.move_to((cxl - lens_r * 0.55) as f32, (eye_y - lens_r * 0.15) as f32);
        gb.line_to((cxl - lens_r * 0.1) as f32, (eye_y - lens_r * 0.6) as f32);
        if let Some(path) = gb.finish() {
            let gstroke = Stroke {
                width: 1.6,
                line_cap: LineCap::Round,
                ..Stroke::default()
            };
            pixmap.stroke_path(&path, &glint, &gstroke, transform, None);
        }
    }
    let lens_w = lens_r;

    // Bridge.
    let mut pb = PathBuilder::new();
    pb.move_to((lx + lens_w) as f32, eye_y as f32);
    pb.line_to((rx_pos - lens_w) as f32, eye_y as f32);
    if let Some(path) = pb.finish() {
        pixmap.stroke_path(&path, &paint, &stroke, transform, None);
    }
}

// ---------------------------------------------------------------------------
// Drawing primitives
// ---------------------------------------------------------------------------

fn draw_limb_segment(
    pixmap: &mut Pixmap,
    x1: f64,
    y1: f64,
    x2: f64,
    y2: f64,
    width: f64,
    opacity: f64,
    color: [u8; 3],
) {
    // Tapered filled bezier shape instead of a stroked line.
    // Proximal end (x1,y1) is wider, distal end (x2,y2) is narrower,
    // with a slight muscle bulge at the midpoint on one side.

    let dx = x2 - x1;
    let dy = y2 - y1;
    let seg_len = (dx * dx + dy * dy).sqrt().max(0.001);

    // Perpendicular unit vector (points "left" relative to direction).
    let nx = -dy / seg_len;
    let ny = dx / seg_len;

    // Width at proximal (1.0x), midpoint bulge side (1.1x), distal (0.75x).
    let prox_half = width * 0.5;
    let mid_half = width * 0.5 * 1.1;
    let mid_half_flat = width * 0.5 * 0.95; // non-bulge side
    let dist_half = width * 0.5 * 0.75;

    // Midpoint of the segment.
    let mx = (x1 + x2) * 0.5;
    let my = (y1 + y2) * 0.5;

    // Corner points.
    // Proximal left/right.
    let p_l_x = x1 + nx * prox_half;
    let p_l_y = y1 + ny * prox_half;
    let p_r_x = x1 - nx * prox_half;
    let p_r_y = y1 - ny * prox_half;

    // Distal left/right.
    let d_l_x = x2 + nx * dist_half;
    let d_l_y = y2 + ny * dist_half;
    let d_r_x = x2 - nx * dist_half;
    let d_r_y = y2 - ny * dist_half;

    // Midpoint control bulge side (left side = muscle bulge).
    let ml_x = mx + nx * mid_half;
    let ml_y = my + ny * mid_half;
    // Midpoint control flat side (right side).
    let mr_x = mx - nx * mid_half_flat;
    let mr_y = my - ny * mid_half_flat;

    let mut pb = PathBuilder::new();
    // Start at proximal left.
    pb.move_to(p_l_x as f32, p_l_y as f32);
    // Cubic bezier along the left (bulge) side to distal left.
    pb.cubic_to(
        (p_l_x + dx * 0.2) as f32,
        (p_l_y + dy * 0.2) as f32,
        (ml_x - dx * 0.1) as f32,
        (ml_y - dy * 0.1) as f32,
        ml_x as f32,
        ml_y as f32,
    );
    pb.cubic_to(
        (ml_x + dx * 0.1) as f32,
        (ml_y + dy * 0.1) as f32,
        (d_l_x - dx * 0.2) as f32,
        (d_l_y - dy * 0.2) as f32,
        d_l_x as f32,
        d_l_y as f32,
    );
    // Line across the distal end.
    pb.line_to(d_r_x as f32, d_r_y as f32);
    // Cubic bezier along the right (flat) side back to proximal right.
    pb.cubic_to(
        (d_r_x - dx * 0.2) as f32,
        (d_r_y - dy * 0.2) as f32,
        (mr_x + dx * 0.1) as f32,
        (mr_y + dy * 0.1) as f32,
        mr_x as f32,
        mr_y as f32,
    );
    pb.cubic_to(
        (mr_x - dx * 0.1) as f32,
        (mr_y - dy * 0.1) as f32,
        (p_r_x + dx * 0.2) as f32,
        (p_r_y + dy * 0.2) as f32,
        p_r_x as f32,
        p_r_y as f32,
    );
    // Close across proximal end.
    pb.close();

    if let Some(path) = pb.finish() {
        draw_outlined_path(pixmap, &path, color, opacity, Transform::identity());

        // Two-tone shading: shadow on the right (flat) side.
        let shadow_color = shade_color(color, 0.18);
        let shadow_paint = solid_paint(
            shadow_color[0],
            shadow_color[1],
            shadow_color[2],
            opacity * 0.5,
        );
        // Build a shadow half covering the right side of the limb.
        let mut spb = PathBuilder::new();
        // Centerline of the limb.
        spb.move_to(x1 as f32, y1 as f32);
        spb.line_to(x2 as f32, y2 as f32);
        spb.line_to(d_r_x as f32, d_r_y as f32);
        spb.cubic_to(
            (d_r_x - dx * 0.2) as f32,
            (d_r_y - dy * 0.2) as f32,
            (mr_x + dx * 0.1) as f32,
            (mr_y + dy * 0.1) as f32,
            mr_x as f32,
            mr_y as f32,
        );
        spb.cubic_to(
            (mr_x - dx * 0.1) as f32,
            (mr_y - dy * 0.1) as f32,
            (p_r_x + dx * 0.2) as f32,
            (p_r_y + dy * 0.2) as f32,
            p_r_x as f32,
            p_r_y as f32,
        );
        spb.close();
        if let Some(shadow_path) = spb.finish() {
            pixmap.fill_path(
                &shadow_path,
                &shadow_paint,
                FillRule::Winding,
                Transform::identity(),
                None,
            );
        }
    }
}

fn fill_rect(pixmap: &mut Pixmap, x: f64, y: f64, w: f64, h: f64, paint: &Paint) {
    if let Some(rect) = tiny_skia::Rect::from_xywh(x as f32, y as f32, w as f32, h as f32) {
        pixmap.fill_rect(rect, paint, Transform::identity(), None);
    }
}

fn fill_circle(pixmap: &mut Pixmap, cx: f64, cy: f64, r: f64, paint: &Paint) {
    fill_circle_t(pixmap, cx, cy, r, paint, 0.0, 0.0, 0.0);
}

fn fill_circle_t(
    pixmap: &mut Pixmap,
    cx: f64,
    cy: f64,
    r: f64,
    paint: &Paint,
    tilt: f64,
    rot_cx: f64,
    rot_cy: f64,
) {
    let transform = tilt_transform(tilt, rot_cx, rot_cy);
    let mut pb = PathBuilder::new();
    // Approximate circle with 4 cubic beziers.
    let k = 0.5522847498; // magic number for cubic bezier circle
    let kr = k * r;
    pb.move_to(cx as f32, (cy - r) as f32);
    pb.cubic_to(
        (cx + kr) as f32,
        (cy - r) as f32,
        (cx + r) as f32,
        (cy - kr) as f32,
        (cx + r) as f32,
        cy as f32,
    );
    pb.cubic_to(
        (cx + r) as f32,
        (cy + kr) as f32,
        (cx + kr) as f32,
        (cy + r) as f32,
        cx as f32,
        (cy + r) as f32,
    );
    pb.cubic_to(
        (cx - kr) as f32,
        (cy + r) as f32,
        (cx - r) as f32,
        (cy + kr) as f32,
        (cx - r) as f32,
        cy as f32,
    );
    pb.cubic_to(
        (cx - r) as f32,
        (cy - kr) as f32,
        (cx - kr) as f32,
        (cy - r) as f32,
        cx as f32,
        (cy - r) as f32,
    );
    pb.close();
    if let Some(path) = pb.finish() {
        pixmap.fill_path(&path, paint, FillRule::Winding, transform, None);
    }
}

fn stroke_circle_t(
    pixmap: &mut Pixmap,
    cx: f64,
    cy: f64,
    r: f64,
    paint: &Paint,
    width: f64,
    tilt: f64,
    rot_cx: f64,
    rot_cy: f64,
) {
    let transform = tilt_transform(tilt, rot_cx, rot_cy);
    let mut pb = PathBuilder::new();
    let k = 0.5522847498;
    let kr = k * r;
    pb.move_to(cx as f32, (cy - r) as f32);
    pb.cubic_to(
        (cx + kr) as f32,
        (cy - r) as f32,
        (cx + r) as f32,
        (cy - kr) as f32,
        (cx + r) as f32,
        cy as f32,
    );
    pb.cubic_to(
        (cx + r) as f32,
        (cy + kr) as f32,
        (cx + kr) as f32,
        (cy + r) as f32,
        cx as f32,
        (cy + r) as f32,
    );
    pb.cubic_to(
        (cx - kr) as f32,
        (cy + r) as f32,
        (cx - r) as f32,
        (cy + kr) as f32,
        (cx - r) as f32,
        cy as f32,
    );
    pb.cubic_to(
        (cx - r) as f32,
        (cy - kr) as f32,
        (cx - kr) as f32,
        (cy - r) as f32,
        cx as f32,
        (cy - r) as f32,
    );
    pb.close();
    if let Some(path) = pb.finish() {
        let stroke = Stroke {
            width: width as f32,
            line_cap: LineCap::Round,
            line_join: LineJoin::Round,
            ..Stroke::default()
        };
        pixmap.stroke_path(&path, paint, &stroke, transform, None);
    }
}

fn shade_color(color: [u8; 3], amount: f64) -> [u8; 3] {
    [
        (color[0] as f64 * (1.0 - amount)).max(0.0).min(255.0) as u8,
        (color[1] as f64 * (1.0 - amount)).max(0.0).min(255.0) as u8,
        (color[2] as f64 * (1.0 - amount)).max(0.0).min(255.0) as u8,
    ]
}

fn draw_outlined_path(
    pixmap: &mut Pixmap,
    path: &tiny_skia::Path,
    fill_color: [u8; 3],
    opacity: f64,
    transform: Transform,
) {
    let fill_paint = solid_paint(fill_color[0], fill_color[1], fill_color[2], opacity);
    pixmap.fill_path(path, &fill_paint, FillRule::Winding, transform, None);

    let outline_color = [
        fill_color[0].saturating_sub(40),
        fill_color[1].saturating_sub(40),
        fill_color[2].saturating_sub(40),
    ];
    let outline_paint = solid_paint(
        outline_color[0],
        outline_color[1],
        outline_color[2],
        opacity,
    );
    let stroke = Stroke {
        width: 1.5,
        line_cap: LineCap::Round,
        line_join: LineJoin::Round,
        ..Stroke::default()
    };
    pixmap.stroke_path(path, &outline_paint, &stroke, transform, None);
}

fn draw_shaded_path(
    pixmap: &mut Pixmap,
    path: &tiny_skia::Path,
    fill_color: [u8; 3],
    opacity: f64,
    transform: Transform,
    shade_clip_path: Option<&tiny_skia::Path>,
) {
    // Draw the main fill + outline.
    draw_outlined_path(pixmap, path, fill_color, opacity, transform);

    // Draw shadow on the right side for a "light from upper-left" effect.
    if let Some(clip_path) = shade_clip_path {
        let shadow_color = shade_color(fill_color, 0.18);
        let shadow_paint = solid_paint(
            shadow_color[0],
            shadow_color[1],
            shadow_color[2],
            opacity * 0.6,
        );
        // Use the clip path as the shadow shape (pre-computed right-half of the shape).
        pixmap.fill_path(clip_path, &shadow_paint, FillRule::Winding, transform, None);
    }
}

fn solid_paint(r: u8, g: u8, b: u8, opacity: f64) -> Paint<'static> {
    let mut paint = Paint::default();
    paint.set_color(SkiaColor::from_rgba8(r, g, b, (opacity * 255.0) as u8));
    paint.anti_alias = true;
    paint
}

fn tilt_transform(tilt: f64, cx: f64, cy: f64) -> Transform {
    if tilt.abs() < 0.001 {
        Transform::identity()
    } else {
        Transform::from_translate(cx as f32, cy as f32)
            .pre_concat(Transform::from_rotate(tilt.to_degrees() as f32))
            .pre_concat(Transform::from_translate(-(cx as f32), -(cy as f32)))
    }
}

fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * t
}

/// Shortest-path angle interpolation (for use in lerp_state / lerp_state_staggered).
fn lerp_angle(a: f64, b: f64, t: f64) -> f64 {
    let mut diff = (b - a) % 360.0;
    if diff > 180.0 {
        diff -= 360.0;
    }
    if diff < -180.0 {
        diff += 360.0;
    }
    (a + diff * t) % 360.0
}

/// Smooth exponential-decay angle interpolation (for per-frame convergence).
pub fn lerp_angle_smooth(current: f64, target: f64, factor: f64) -> f64 {
    let mut diff = (target - current) % 360.0;
    if diff > 180.0 {
        diff -= 360.0;
    }
    if diff < -180.0 {
        diff += 360.0;
    }
    (current + diff * factor) % 360.0
}
