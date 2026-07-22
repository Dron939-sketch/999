# Contributing to animdsl

This document is a technical guide to the animdsl codebase, written for contributors (including AI agents). It covers the project structure, module responsibilities, data flow, build instructions, and patterns for adding new features.

---

## Project Overview

- **Language:** Rust (2021 edition)
- **Total Rust code:** ~7,665 lines across 12 source files
- **PEG grammar:** 345 lines (`animdsl.pest`)
- **Tests:** 6 passing (all parser tests)
- **Compiler warnings:** 29, all in `procedural/mod.rs` (unused variables and `mut` bindings)

animdsl is a domain-specific language and rendering pipeline for procedural character animation. It takes `.anim` source files, parses them into an AST, compiles timelines, renders frames using procedural drawing (no sprites), and encodes the result as an MP4 video.

---

## File Layout

```
animdsl/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── main.rs
│   ├── errors.rs
│   ├── ast/mod.rs
│   ├── parser/
│   │   ├── mod.rs
│   │   └── animdsl.pest
│   ├── assets/mod.rs
│   ├── scene/mod.rs
│   ├── timeline/mod.rs
│   ├── procedural/mod.rs    # 3,318 lines -- procedural rendering
│   ├── renderer/mod.rs
│   ├── skeleton/mod.rs
│   └── video/mod.rs
├── examples/
│   ├── assets/
│   │   ├── characters/
│   │   │   ├── procedural/  # 6 JSON character definitions
│   │   │   ├── *_rig/       # legacy rig SVGs
│   │   │   └── *.svg        # legacy character SVGs
│   │   └── sets/            # 5 SVG backgrounds
│   ├── the-last-barista.anim # primary demo (508 lines, 15 custom poses)
│   ├── the-signal-v3.anim   # secondary demo
│   └── *.mp4                 # rendered outputs
└── frames/                   # temp frame output
```

---

## Module Architecture

### `src/lib.rs` (10 lines)

Re-exports all public modules. Nothing else.

### `src/main.rs` (305 lines)

CLI entry point using clap. Defines three subcommands:

- **`render`** -- Full pipeline: parse, load assets, extract custom poses, resolve scenes, compile timelines, check overlaps, render frames, encode video.
- **`check`** -- Parse + validate + overlap detection, without rendering. Useful for fast validation.
- **`dump`** -- Parse + JSON dump of the AST.

### `src/parser/animdsl.pest` (345 lines)

PEG grammar definition using pest. Key grammar rules:

- `program` -- top-level entry point
- `top_level_item` -- one of: `import_decl`, `config_block`, `pose_decl`, `scene_decl`
- `scene_statement` -- statements within a scene block
- `action_stmt` -- action commands (9 variants)
- `camera_command` -- camera control commands (5 variants)
- `transition_kind` -- scene transition types
- `position` -- spatial positioning
- `pose_decl` -- custom pose definition
- `pose_field` -- individual field within a pose

### `src/parser/mod.rs` (844 lines)

Pest-to-AST parser. Recursive descent through pest pairs into AST nodes.

- **Key function:** `pub fn parse(source: &str) -> Result<Program, AnimError>`
- Contains 6 unit tests (the only tests in the project).

### `src/ast/mod.rs` (377 lines)

All AST data structures. Key types:

| Type | Variants / Purpose |
|---|---|
| `Program` | Root node of the AST |
| `TopLevelItem` | `Import`, `Config`, `PoseDef`, `Scene` |
| `SceneStatement` | `Place`, `Action`, `Wait`, `Together`, `Do`, `Camera`, `Transition`, `Let` |
| `ActionStmt` | 9 variants (movement, expression, etc.) |
| `CameraStmt` | 5 variants |
| `PoseDefDecl` | Custom pose definition |
| `PoseField` | Single field within a pose |

### `src/errors.rs` (30 lines)

Error types using thiserror. Variants:

- `Parse(String)`
- `Asset(String)`
- `Scene(String)`
- `Timeline(String)`
- `Render(String)`
- `Overlap(String)`

### `src/assets/mod.rs` (216 lines)

Asset loading. Loads character JSON files into `CharacterDesc`, and SVG files for sets and props.

Character JSON schema:

```
name, body (height/build/skin_color), face (shape/eye_size/eye_color/
eyebrow_thickness/nose_size/lip_fullness), hair (color/style/length),
outfit (top/bottom/shoes/accessories)
```

### `src/scene/mod.rs` (286 lines)

Scene resolution. Takes AST scenes + loaded assets and produces `ResolvedScene` with `EntityState` tracking position, opacity, scale, rotation, facing, and pose for each entity.

- **Key function:** `resolve_position()` converts `Position` enum to `(f64, f64)`.
- `EntityState` has an `EntityKind` enum: `Character`, `Set`, `Prop`.

### `src/timeline/mod.rs` (905 lines)

Timeline compiler, evaluator, and overlap checker.

- **`compile()`** -- Converts `SceneStatements` into flat keyframe tracks. Handles sequential/parallel timing, `together` blocks, enter/exit animations.
- **`evaluate_track()`** -- Samples a property track at time `t` with easing interpolation.
- **`evaluate_camera()`** -- Samples camera state at time `t`.
- **`check_overlaps()`** -- Samples character positions at 0.1s intervals. Errors if two visible characters are within 0.12 normalized units horizontally and 0.15 vertically.

Key types: `Timeline`, `Track`, `Keyframe`, `PoseEvent`, `CameraTrack`, `CameraKeyframe`, `TransitionEvent`.

### `src/procedural/mod.rs` (3,318 lines)

The largest and most important module. Procedural character rendering using tiny-skia.

**Key public types:**

- `CharacterDesc` -- Static character description (loaded from JSON).
- `CharacterState` -- Dynamic per-frame state (joints, expressions, body angle, secondary motion).
- `Expression` -- Facial expression sub-state (eyebrows, eyes, mouth).

**Key public functions:**

| Function | Purpose |
|---|---|
| `draw_character()` | Renders a full character to a `Pixmap` given desc + state |
| `draw_set_procedural()` | Renders procedural backgrounds |
| `named_pose(name)` | Returns a `CharacterState` for one of 9 hardcoded poses: idle, thinking, pointing, surprised, angry, menacing, scared, excited, typing |
| `custom_pose(fields)` | Builds `CharacterState` from custom pose field/value pairs |
| `apply_idle(state)` | Organic idle animation (multi-frequency breathing, micro head movements, weight shift) |
| `apply_walk(state, speed, phase)` | Walk cycle with staggered joint timing (hip then knee then foot, shoulder then elbow) |
| `apply_secondary_motion(state, dt)` | Damped spring physics for hair swing and clothing swing |
| `lerp_state(a, b, t)` | Linear interpolation of all `CharacterState` fields |
| `lerp_state_staggered(a, b, t)` | Staggered interpolation (torso leads, extremities follow) |
| `lerp_angle_smooth(current, target, factor)` | Exponential decay angle interpolation |

**Drawing pipeline within `draw_character()`:**

1. Compute perspective factors from `body_angle` (`front_factor`, `turn_factor`)
2. Compute body proportions from `CharacterDesc` (height, build, etc.)
3. Draw back arm (farther from camera)
4. Draw back leg
5. Draw torso (organic shape with curved shoulders, waist, hips)
6. Draw neck
7. Draw front leg
8. Draw front arm
9. Draw head (with perspective-adjusted face features)

**Body angle system:**

- `body_angle`: 0 degrees = front, 45 = 3/4 right, 90 = profile right, 180 = back, 270 = profile left
- `front_factor = cos(angle)` -- how much of the front is visible
- `turn_factor = sin(angle)` -- left/right turn amount
- Affects: torso width, shoulder asymmetry, arm width/position, leg spread, head feature offset, ear visibility, eye scaling, nose protrusion, back view face hiding

**Helper functions** (bottom of file): `draw_outlined_path`, `shade_color`, `draw_limb_segment`, `fill_rect`, `fill_circle`, `fill_circle_t`, `solid_paint`, `tilt_transform`, `lerp`, `stroke_circle_t`, `lerp_angle`, `lerp_angle_smooth`.

### `src/renderer/mod.rs` (849 lines)

Frame rendering orchestrator.

- **Key function:** `render_scene()` takes a resolved scene, compiled timeline, custom poses, and config, and renders all frames.

Per-frame pipeline: evaluate tracks, resolve entity positions/opacity/scale, draw set background, draw each character (via procedural module), apply camera transform, apply transitions, write PNG frame.

`render_procedural_character()` is the bridge between the timeline and the procedural module. It computes velocity from position delta, auto-computes `body_angle` from velocity/facing, resolves poses (custom first, fallback to `named_pose()`), interpolates between from/to poses, applies idle/walk animation, applies secondary motion, and calls `draw_character()`.

Custom pose resolution: checks `HashMap<String, Vec<(String, f64)>>` first, falls back to `named_pose()`.

### `src/skeleton/mod.rs` (400 lines)

Bone-based rig system from v2. Partially superseded by the procedural module but still compiled. Contains `Skeleton`, `Bone`, `RigDef` types and FK/IK solving. Not actively used in the current rendering pipeline.

### `src/video/mod.rs` (125 lines)

FFmpeg encoding. Spawns an ffmpeg process, pipes PNG frames to stdin, produces MP4.

- **Key function:** `encode_video()`

---

## Data Flow

```
.anim source
    |
    v
parser::parse() --> ast::Program
    |
    v
assets::load() --> AssetRegistry (CharacterDescs, SVGs)
    |
    v
main.rs extracts custom_poses: HashMap<String, Vec<(String, f64)>>
    |
    v
scene::resolve() --> ResolvedScene (per scene)
    |
    v
timeline::compile() --> Timeline (keyframe tracks + pose events + camera + transitions)
    |
    v
timeline::check_overlaps() --> Ok(()) or Error
    |
    v
renderer::render_scene() --> Vec<Pixmap> (frames)
    |
    v
video::encode_video() --> .mp4 file
```

---

## Dependencies (12 crates)

| Crate | Version | Purpose |
|---|---|---|
| pest / pest_derive | 2.7 | PEG parser generator |
| usvg | 0.44 | SVG parsing |
| resvg | 0.44 | SVG rendering |
| tiny-skia | 0.11 | 2D rasterization (core drawing library) |
| png | 0.17 | PNG encoding |
| palette | 0.7 | Color math |
| clap | 4 | CLI argument parsing |
| thiserror | 2 | Error derive macros |
| anyhow | 1 | Error context/propagation |
| serde / serde_json | 1 | Serialization (character JSON, AST dump) |
| log | 0.4 | Logging facade |
| env_logger | 0.11 | Log output |

---

## Build and Test

```bash
cargo build                # dev build
cargo build --release      # optimized build (needed for fast rendering)
cargo test                 # run all 6 tests

# Validate a .anim file without rendering
cargo run -- check examples/the-last-barista.anim

# Render to video
cargo run -- render examples/the-last-barista.anim -o output.mp4

# Render with logging enabled (release mode recommended)
RUST_LOG=info cargo run --release -- render examples/the-last-barista.anim -o output.mp4

# Dump AST as JSON
cargo run -- dump examples/the-last-barista.anim
```

---

## Key Design Decisions

1. **No external animation tools.** Everything is drawn from code using tiny-skia primitives (bezier paths, fills, strokes). There are no pre-drawn sprites or external animation software in the pipeline.

2. **Procedural characters.** Characters are defined by JSON parameters (height, build, hair style, clothing) and drawn frame-by-frame from those parameters. This means any character attribute can be changed without redrawing assets.

3. **Custom poses in the DSL.** Pose definitions are authored in the `.anim` file rather than hardcoded in Rust. There are 23 controllable fields covering all joints and facial expressions.

4. **Overlap detection.** The system prevents characters from intersecting by checking positions at 0.1-second intervals before rendering begins. This catches errors early.

5. **Body angle system.** Characters render from different perspectives (front, 3/4, profile, back) based on movement direction and facing. The perspective is computed continuously, not snapped to discrete angles.

6. **Staggered joint timing.** Pose transitions do not move all joints simultaneously. The torso leads and extremities follow, producing more natural motion.

7. **Secondary motion.** Damped spring physics on hair and clothing produces follow-through effects without manual keyframing.

---

## Known Issues and Warnings

- 29 compiler warnings in `procedural/mod.rs` (unused variables and `mut` bindings). These could be cleaned up without affecting functionality.
- `skeleton/mod.rs` is partially superseded by the procedural system. It still compiles but is not used in the active rendering pipeline.
- The overlap check boundary (0.12 normalized units) is tight. Characters positioned exactly at the boundary may trigger false positives.
- No audio support. The pipeline produces video only.
- The walk cycle vertical bob can be visible at certain speeds.

---

## Adding New Features

### Adding a new pose field

1. Add the field to `CharacterState` in `procedural/mod.rs`.
2. Update `Default for CharacterState` to set a sensible default value.
3. Update `lerp_state()` and `lerp_state_staggered()` to interpolate the new field.
4. Add `"field-name"` to the `pose_field` rule in `animdsl.pest`.
5. Add a match arm in `custom_pose()` in `procedural/mod.rs` to map the field name to the struct field.
6. Use the field in the relevant draw function(s) within the procedural module.

### Adding a new action type

1. Add a grammar rule in `animdsl.pest` under `action_stmt`.
2. Add a variant to `ActionStmt` in `ast/mod.rs`.
3. Add a parser function in `parser/mod.rs` to handle the new grammar rule.
4. Handle the new variant in `timeline/mod.rs` inside `compile_action()`.
5. Handle it in `renderer/mod.rs` if it affects rendering.

### Adding a new clothing type

1. Add a variant to `ClothingKind` in `assets/mod.rs`.
2. Add drawing logic in `draw_torso()` in `procedural/mod.rs`.

### Adding a new camera command

1. Add a grammar rule under `camera_command` in `animdsl.pest`.
2. Add a variant to `CameraStmt` in `ast/mod.rs`.
3. Parse it in `parser/mod.rs` inside `parse_camera()`.
4. Handle it in `timeline/mod.rs` inside `compile_camera()`.
