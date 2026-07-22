//! Parser — converts DSL source text into AST via pest.

use pest::Parser;
use pest_derive::Parser;

use crate::ast::*;
use crate::errors::AnimError;

#[derive(Parser)]
#[grammar = "parser/animdsl.pest"]
pub struct AnimDslParser;

type Pair<'a> = pest::iterators::Pair<'a, Rule>;

/// Parse a full `.anim` source file into a Program AST.
pub fn parse(source: &str) -> Result<Program, AnimError> {
    let pairs = AnimDslParser::parse(Rule::program, source)
        .map_err(|e| AnimError::Parse(format!("{e}")))?;

    let mut items = Vec::new();

    for pair in pairs {
        match pair.as_rule() {
            Rule::program => {
                for inner in pair.into_inner() {
                    match inner.as_rule() {
                        Rule::top_level_item => {
                            items.push(parse_top_level_item(inner)?);
                        }
                        Rule::EOI => {}
                        _ => {}
                    }
                }
            }
            _ => {}
        }
    }

    Ok(Program { items })
}

fn parse_top_level_item(pair: Pair) -> Result<TopLevelItem, AnimError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::import_decl => Ok(TopLevelItem::Import(parse_import(inner)?)),
        Rule::config_block => Ok(TopLevelItem::Config(parse_config(inner)?)),
        Rule::pose_decl => Ok(TopLevelItem::PoseDef(parse_pose_decl(inner)?)),
        Rule::scene_decl => Ok(TopLevelItem::Scene(parse_scene(inner)?)),
        r => Err(AnimError::Parse(format!(
            "unexpected top-level rule: {r:?}"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Imports
// ---------------------------------------------------------------------------

fn parse_import(pair: Pair) -> Result<ImportDecl, AnimError> {
    let mut inner = pair.into_inner();
    let kind_pair = inner.next().unwrap();
    let kind = match kind_pair.as_str() {
        "character" => ImportKind::Character,
        "set" => ImportKind::Set,
        "prop" => ImportKind::Prop,
        s => return Err(AnimError::Parse(format!("unknown import kind: {s}"))),
    };
    let name = inner.next().unwrap().as_str().to_string();
    let path = parse_string_literal(inner.next().unwrap());

    Ok(ImportDecl { kind, name, path })
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

fn parse_config(pair: Pair) -> Result<ConfigBlock, AnimError> {
    let mut entries = Vec::new();
    for inner in pair.into_inner() {
        if inner.as_rule() == Rule::config_entry {
            let mut parts = inner.into_inner();
            let key = parts.next().unwrap().as_str().to_string();
            let value = parse_value(parts.next().unwrap())?;
            entries.push(ConfigEntry { key, value });
        }
    }
    Ok(ConfigBlock { entries })
}

// ---------------------------------------------------------------------------
// Custom Pose Definitions
// ---------------------------------------------------------------------------

fn parse_pose_decl(pair: Pair) -> Result<PoseDefDecl, AnimError> {
    let mut inner = pair.into_inner();
    let name = parse_string_literal(inner.next().unwrap());
    let mut fields = Vec::new();
    for entry in inner {
        if entry.as_rule() == Rule::pose_entry {
            let mut parts = entry.into_inner();
            let field_name = parts.next().unwrap().as_str().to_string();
            let value = parts.next().unwrap().as_str().parse::<f64>().unwrap();
            fields.push(PoseField {
                name: field_name,
                value,
            });
        }
    }
    Ok(PoseDefDecl { name, fields })
}

// ---------------------------------------------------------------------------
// Scenes
// ---------------------------------------------------------------------------

fn parse_scene(pair: Pair) -> Result<SceneDecl, AnimError> {
    let mut inner = pair.into_inner();
    let name = parse_string_literal(inner.next().unwrap());

    let mut params = Vec::new();
    let mut body = Vec::new();

    for part in inner {
        match part.as_rule() {
            Rule::scene_params => {
                for param_pair in part.into_inner() {
                    if param_pair.as_rule() == Rule::scene_param {
                        let mut kv = param_pair.into_inner();
                        let key = kv.next().unwrap().as_str().to_string();
                        let value = parse_value(kv.next().unwrap())?;
                        params.push(SceneParam { key, value });
                    }
                }
            }
            Rule::scene_statement => {
                body.push(parse_scene_statement(part)?);
            }
            _ => {}
        }
    }

    Ok(SceneDecl { name, params, body })
}

// ---------------------------------------------------------------------------
// Scene statements
// ---------------------------------------------------------------------------

fn parse_scene_statement(pair: Pair) -> Result<SceneStatement, AnimError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::place_stmt => Ok(SceneStatement::Place(parse_place(inner)?)),
        Rule::wait_stmt => {
            let dur = parse_duration(inner.into_inner().next().unwrap());
            Ok(SceneStatement::Wait(dur))
        }
        Rule::together_block => {
            let stmts = inner
                .into_inner()
                .filter(|p| p.as_rule() == Rule::scene_statement)
                .map(parse_scene_statement)
                .collect::<Result<Vec<_>, _>>()?;
            Ok(SceneStatement::Together(stmts))
        }
        Rule::do_block => {
            let stmts = inner
                .into_inner()
                .filter(|p| p.as_rule() == Rule::scene_statement)
                .map(parse_scene_statement)
                .collect::<Result<Vec<_>, _>>()?;
            Ok(SceneStatement::Do(stmts))
        }
        Rule::camera_stmt => Ok(SceneStatement::Camera(parse_camera(inner)?)),
        Rule::transition_stmt => Ok(SceneStatement::Transition(parse_transition(inner)?)),
        Rule::let_stmt => Ok(SceneStatement::Let(parse_let(inner)?)),
        Rule::action_stmt => Ok(SceneStatement::Action(parse_action(inner)?)),
        r => Err(AnimError::Parse(format!(
            "unexpected scene statement: {r:?}"
        ))),
    }
}

// ---------------------------------------------------------------------------
// Place
// ---------------------------------------------------------------------------

fn parse_place(pair: Pair) -> Result<PlaceStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();

    let mut position = Position::Named(NamedPosition::Center);
    let mut facing = None;
    let mut layer = None;

    for part in inner {
        match part.as_rule() {
            Rule::position => {
                position = parse_position(part)?;
            }
            Rule::facing_clause => {
                let dir_pair = part.into_inner().next().unwrap();
                facing = Some(parse_direction(dir_pair));
            }
            Rule::layer_clause => {
                let num = part
                    .into_inner()
                    .next()
                    .unwrap()
                    .as_str()
                    .parse::<i32>()
                    .unwrap();
                layer = Some(num);
            }
            _ => {}
        }
    }

    Ok(PlaceStmt {
        entity,
        position,
        facing,
        layer,
    })
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

fn parse_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::move_action => parse_move_action(inner),
        Rule::pose_action => parse_pose_action(inner),
        Rule::show_action => parse_show_action(inner),
        Rule::hide_action => parse_hide_action(inner),
        Rule::enter_action => parse_enter_action(inner),
        Rule::exit_action => parse_exit_action(inner),
        Rule::scale_action => parse_scale_action(inner),
        Rule::rotate_action => parse_rotate_action(inner),
        Rule::fade_action => parse_fade_action(inner),
        r => Err(AnimError::Parse(format!("unexpected action: {r:?}"))),
    }
}

fn parse_move_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let target = parse_position(inner.next().unwrap())?;
    let duration = parse_duration(inner.next().unwrap());
    let easing = inner
        .next()
        .map(|p| parse_easing(p.into_inner().next().unwrap()));

    Ok(ActionStmt::MoveTo {
        entity,
        target,
        duration,
        easing,
    })
}

fn parse_pose_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let pose = parse_string_literal(inner.next().unwrap());

    Ok(ActionStmt::Pose { entity, pose })
}

fn parse_show_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::Show {
        entity,
        duration,
        easing,
    })
}

fn parse_hide_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::Hide {
        entity,
        duration,
        easing,
    })
}

fn parse_enter_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let from = parse_direction(inner.next().unwrap());
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::Enter {
        entity,
        from,
        duration,
        easing,
    })
}

fn parse_exit_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let to = parse_direction(inner.next().unwrap());
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::Exit {
        entity,
        to,
        duration,
        easing,
    })
}

fn parse_scale_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let factor = inner.next().unwrap().as_str().parse::<f64>().unwrap();
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::Scale {
        entity,
        factor,
        duration,
        easing,
    })
}

fn parse_rotate_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let angle = inner.next().unwrap().as_str().parse::<f64>().unwrap();
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::Rotate {
        entity,
        angle,
        duration,
        easing,
    })
}

fn parse_fade_action(pair: Pair) -> Result<ActionStmt, AnimError> {
    let mut inner = pair.into_inner();
    let entity = inner.next().unwrap().as_str().to_string();
    let opacity = inner.next().unwrap().as_str().parse::<f64>().unwrap();
    let (duration, easing) = parse_optional_over_easing(&mut inner);

    Ok(ActionStmt::FadeTo {
        entity,
        opacity,
        duration,
        easing,
    })
}

// ---------------------------------------------------------------------------
// Camera
// ---------------------------------------------------------------------------

fn parse_camera(pair: Pair) -> Result<CameraStmt, AnimError> {
    let cmd = pair
        .into_inner()
        .next()
        .unwrap() // camera_command
        .into_inner()
        .next()
        .unwrap();

    match cmd.as_rule() {
        Rule::camera_shot => {
            let mut inner = cmd.into_inner();
            let shot_pair = inner.next().unwrap();
            let shot = parse_shot_type(shot_pair);
            let target = inner.next().map(|p| p.as_str().to_string());
            Ok(CameraStmt::ShotType { shot, target })
        }
        Rule::camera_zoom => {
            let mut inner = cmd.into_inner();
            let target = inner.next().unwrap().as_str().to_string();
            let duration = parse_duration(inner.next().unwrap());
            let easing = inner
                .next()
                .map(|p| parse_easing(p.into_inner().next().unwrap()));
            Ok(CameraStmt::ZoomTo {
                target,
                duration,
                easing,
            })
        }
        Rule::camera_pan => {
            let mut inner = cmd.into_inner();
            let target_pair = inner.next().unwrap();
            let target = match target_pair.as_rule() {
                Rule::identifier => PanTarget::Entity(target_pair.as_str().to_string()),
                Rule::coord_pair => {
                    let (x, y) = parse_coord_pair(target_pair);
                    PanTarget::Position(Position::Coords(x, y))
                }
                _ => {
                    return Err(AnimError::Parse(format!(
                        "unexpected camera pan target: {:?}",
                        target_pair.as_rule()
                    )));
                }
            };
            let duration = parse_duration(inner.next().unwrap());
            let easing = inner
                .next()
                .map(|p| parse_easing(p.into_inner().next().unwrap()));
            Ok(CameraStmt::PanTo {
                target,
                duration,
                easing,
            })
        }
        Rule::camera_shake => {
            let mut inner = cmd.into_inner();
            let duration = parse_duration(inner.next().unwrap());
            let intensity = inner
                .next()
                .map(|p| p.as_str().parse::<f64>().unwrap())
                .unwrap_or(5.0);
            Ok(CameraStmt::Shake {
                duration,
                intensity,
            })
        }
        Rule::camera_reset => {
            let mut inner = cmd.into_inner();
            let duration = inner.next().map(parse_duration);
            Ok(CameraStmt::Reset { duration })
        }
        r => Err(AnimError::Parse(format!(
            "unexpected camera command: {r:?}"
        ))),
    }
}

fn parse_shot_type(pair: Pair) -> ShotType {
    match pair.as_str() {
        "wide" => ShotType::Wide,
        "medium" => ShotType::Medium,
        "close-up" => ShotType::CloseUp,
        "extreme-close-up" => ShotType::ExtremeCloseUp,
        "two-shot" => ShotType::TwoShot,
        "over-shoulder" => ShotType::OverShoulder,
        _ => ShotType::Wide,
    }
}

// ---------------------------------------------------------------------------
// Transitions
// ---------------------------------------------------------------------------

fn parse_transition(pair: Pair) -> Result<TransitionStmt, AnimError> {
    let kind = pair
        .into_inner()
        .next()
        .unwrap() // transition_kind
        .into_inner()
        .next()
        .unwrap();

    match kind.as_rule() {
        Rule::transition_fade_black => {
            let dur = parse_duration(kind.into_inner().next().unwrap());
            Ok(TransitionStmt::FadeBlack(dur))
        }
        Rule::transition_fade_white => {
            let dur = parse_duration(kind.into_inner().next().unwrap());
            Ok(TransitionStmt::FadeWhite(dur))
        }
        Rule::transition_dissolve => {
            let dur = parse_duration(kind.into_inner().next().unwrap());
            Ok(TransitionStmt::Dissolve(dur))
        }
        Rule::transition_cut => Ok(TransitionStmt::Cut),
        Rule::transition_wipe => {
            let mut inner = kind.into_inner();
            let direction = parse_direction(inner.next().unwrap());
            let duration = parse_duration(inner.next().unwrap());
            Ok(TransitionStmt::Wipe {
                direction,
                duration,
            })
        }
        r => Err(AnimError::Parse(format!("unexpected transition: {r:?}"))),
    }
}

// ---------------------------------------------------------------------------
// Let bindings
// ---------------------------------------------------------------------------

fn parse_let(pair: Pair) -> Result<LetStmt, AnimError> {
    let mut inner = pair.into_inner();
    let name = inner.next().unwrap().as_str().to_string();
    let kind_pair = inner.next().unwrap(); // let_kind
    let prop_pair = kind_pair.into_inner().next().unwrap(); // let_prop

    match prop_pair.as_rule() {
        Rule::let_prop => {
            let mut parts = prop_pair.into_inner();
            let label = parse_string_literal(parts.next().unwrap());
            let path = parse_string_literal(parts.next().unwrap());
            let position = parts.next().map(|p| parse_position(p)).transpose()?;
            Ok(LetStmt {
                name,
                kind: LetKind::Prop {
                    label,
                    path,
                    position,
                },
            })
        }
        r => Err(AnimError::Parse(format!("unexpected let kind: {r:?}"))),
    }
}

// ---------------------------------------------------------------------------
// Shared parsing helpers
// ---------------------------------------------------------------------------

fn parse_position(pair: Pair) -> Result<Position, AnimError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::named_position => Ok(Position::Named(parse_named_position(inner))),
        Rule::coord_pair => {
            let (x, y) = parse_coord_pair(inner);
            Ok(Position::Coords(x, y))
        }
        Rule::relative_position => {
            let mut parts = inner.into_inner();
            let relation = parse_relation(parts.next().unwrap());
            let entity = parts.next().unwrap().as_str().to_string();
            Ok(Position::Relative { relation, entity })
        }
        r => Err(AnimError::Parse(format!("unexpected position: {r:?}"))),
    }
}

fn parse_named_position(pair: Pair) -> NamedPosition {
    match pair.as_str() {
        "left" => NamedPosition::Left,
        "right" => NamedPosition::Right,
        "center" => NamedPosition::Center,
        "left-third" => NamedPosition::LeftThird,
        "right-third" => NamedPosition::RightThird,
        "top-left" => NamedPosition::TopLeft,
        "top-right" => NamedPosition::TopRight,
        "bottom-left" => NamedPosition::BottomLeft,
        "bottom-right" => NamedPosition::BottomRight,
        "top" => NamedPosition::Top,
        "bottom" => NamedPosition::Bottom,
        "left-edge" => NamedPosition::LeftEdge,
        "right-edge" => NamedPosition::RightEdge,
        "offscreen-left" => NamedPosition::Offscreen(Direction::Left),
        "offscreen-right" => NamedPosition::Offscreen(Direction::Right),
        "offscreen-up" => NamedPosition::Offscreen(Direction::Up),
        "offscreen-down" => NamedPosition::Offscreen(Direction::Down),
        _ => NamedPosition::Center,
    }
}

fn parse_coord_pair(pair: Pair) -> (f64, f64) {
    let mut inner = pair.into_inner();
    let x = inner.next().unwrap().as_str().parse::<f64>().unwrap();
    let y = inner.next().unwrap().as_str().parse::<f64>().unwrap();
    (x, y)
}

fn parse_relation(pair: Pair) -> Relation {
    match pair.as_str() {
        "near" => Relation::Near,
        "behind" => Relation::Behind,
        "in-front-of" => Relation::InFrontOf,
        "above" => Relation::Above,
        "below" => Relation::Below,
        "left-of" => Relation::LeftOf,
        "right-of" => Relation::RightOf,
        _ => Relation::Near,
    }
}

fn parse_direction(pair: Pair) -> Direction {
    match pair.as_str() {
        "left" => Direction::Left,
        "right" => Direction::Right,
        "up" => Direction::Up,
        "down" => Direction::Down,
        _ => Direction::Right,
    }
}

fn parse_duration(pair: Pair) -> Duration {
    let s = pair.as_str();
    // Strip trailing 's'
    let num = s.trim_end_matches('s').parse::<f64>().unwrap();
    Duration::seconds(num)
}

fn parse_easing(pair: Pair) -> Easing {
    match pair.as_str() {
        "linear" => Easing::Linear,
        "ease-in" => Easing::EaseIn,
        "ease-out" => Easing::EaseOut,
        "ease-in-out" => Easing::EaseInOut,
        _ => Easing::Linear,
    }
}

fn parse_value(pair: Pair) -> Result<Value, AnimError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::duration => Ok(Value::Duration(parse_duration(inner))),
        Rule::number => Ok(Value::Number(inner.as_str().parse::<f64>().unwrap())),
        Rule::string_literal => Ok(Value::String(parse_string_literal(inner))),
        Rule::color_literal => Ok(Value::Color(parse_color(inner.as_str())?)),
        Rule::boolean => Ok(Value::Bool(inner.as_str() == "true")),
        Rule::identifier => Ok(Value::Identifier(inner.as_str().to_string())),
        r => Err(AnimError::Parse(format!("unexpected value: {r:?}"))),
    }
}

fn parse_string_literal(pair: Pair) -> String {
    let s = pair.as_str();
    // Strip surrounding quotes
    s[1..s.len() - 1].to_string()
}

fn parse_color(s: &str) -> Result<Color, AnimError> {
    let hex = s.trim_start_matches('#');
    if hex.len() == 6 {
        let r = u8::from_str_radix(&hex[0..2], 16).unwrap();
        let g = u8::from_str_radix(&hex[2..4], 16).unwrap();
        let b = u8::from_str_radix(&hex[4..6], 16).unwrap();
        Ok(Color::rgb(r, g, b))
    } else if hex.len() == 8 {
        let r = u8::from_str_radix(&hex[0..2], 16).unwrap();
        let g = u8::from_str_radix(&hex[2..4], 16).unwrap();
        let b = u8::from_str_radix(&hex[4..6], 16).unwrap();
        let a = u8::from_str_radix(&hex[6..8], 16).unwrap();
        Ok(Color::rgba(r, g, b, a))
    } else {
        Err(AnimError::Parse(format!("invalid color: {s}")))
    }
}

fn parse_optional_over_easing(
    inner: &mut pest::iterators::Pairs<Rule>,
) -> (Option<Duration>, Option<Easing>) {
    let mut duration = None;
    let mut easing = None;

    for part in inner {
        match part.as_rule() {
            Rule::duration => {
                duration = Some(parse_duration(part));
            }
            Rule::easing_clause => {
                easing = Some(parse_easing(part.into_inner().next().unwrap()));
            }
            _ => {}
        }
    }

    (duration, easing)
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_minimal_scene() {
        let source = r#"
scene "test" (duration: 5s) {
    place alice at center
    wait 1s
}
"#;
        let program = parse(source).expect("should parse");
        assert_eq!(program.items.len(), 1);

        if let TopLevelItem::Scene(scene) = &program.items[0] {
            assert_eq!(scene.name, "test");
            assert_eq!(scene.body.len(), 2);
        } else {
            panic!("expected scene");
        }
    }

    #[test]
    fn test_parse_import() {
        let source = r#"import character alice from "./assets/alice.svg"
"#;
        let program = parse(source).expect("should parse");
        assert_eq!(program.items.len(), 1);

        if let TopLevelItem::Import(imp) = &program.items[0] {
            assert_eq!(imp.kind, ImportKind::Character);
            assert_eq!(imp.name, "alice");
            assert_eq!(imp.path, "./assets/alice.svg");
        } else {
            panic!("expected import");
        }
    }

    #[test]
    fn test_parse_config() {
        let source = r#"
config {
    width: 1920
    height: 1080
    fps: 24
    background: #1a1a2e
}
"#;
        let program = parse(source).expect("should parse");
        assert_eq!(program.items.len(), 1);

        if let TopLevelItem::Config(cfg) = &program.items[0] {
            assert_eq!(cfg.entries.len(), 4);
        } else {
            panic!("expected config");
        }
    }

    #[test]
    fn test_parse_full_scene() {
        let source = r#"
import character alice from "./assets/alice.svg"
import character bob from "./assets/bob.svg"
import set office from "./assets/office.svg"

config {
    width: 1920
    height: 1080
    fps: 24
}

scene "confrontation" (duration: 10s, set: office) {
    place alice at left-third facing right
    place bob at right-third facing left

    do {
        alice moves-to center over 1.5s ease-out
        alice pose "pointing"
        wait 0.5s
    }

    together {
        bob pose "surprised"
        camera zoom-to alice over 0.8s
    }

    wait 1s

    together {
        camera pan-to bob over 0.6s
        alice pose "idle"
    }

    bob moves-to right-edge over 2s ease-in
    bob exits right over 1s

    transition fade-black 1s
}
"#;
        let program = parse(source).expect("should parse");
        assert_eq!(program.items.len(), 5); // 3 imports + 1 config + 1 scene
    }

    #[test]
    fn test_parse_pose_decl() {
        let source = r#"
pose "drinking" {
    arm-right-angle: -70
    elbow-right-bend: 0.8
    head-nod: 10
    mouth-smile: 0.3
    mouth-open: 0.1
}
"#;
        let program = parse(source).expect("should parse");
        assert_eq!(program.items.len(), 1);

        if let TopLevelItem::PoseDef(pose) = &program.items[0] {
            assert_eq!(pose.name, "drinking");
            assert_eq!(pose.fields.len(), 5);
            assert_eq!(pose.fields[0].name, "arm-right-angle");
            assert_eq!(pose.fields[0].value, -70.0);
            assert_eq!(pose.fields[1].name, "elbow-right-bend");
            assert_eq!(pose.fields[1].value, 0.8);
            assert_eq!(pose.fields[4].name, "mouth-open");
            assert_eq!(pose.fields[4].value, 0.1);
        } else {
            panic!("expected PoseDef");
        }
    }

    #[test]
    fn test_parse_pose_with_scene() {
        let source = r#"
pose "drinking" {
    arm-right-angle: -70
    elbow-right-bend: 0.8
}

scene "test" (duration: 5s) {
    place alice at center
    alice pose "drinking"
}
"#;
        let program = parse(source).expect("should parse");
        assert_eq!(program.items.len(), 2); // 1 pose + 1 scene

        if let TopLevelItem::PoseDef(pose) = &program.items[0] {
            assert_eq!(pose.name, "drinking");
        } else {
            panic!("expected PoseDef as first item");
        }

        if let TopLevelItem::Scene(scene) = &program.items[1] {
            assert_eq!(scene.name, "test");
        } else {
            panic!("expected Scene as second item");
        }
    }
}
