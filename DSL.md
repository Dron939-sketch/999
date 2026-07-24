# AnimDSL Language Specification

This document is the definitive reference for the AnimDSL language. AnimDSL is a
domain-specific language for describing procedural character animations. Scripts
are written in `.anim` files and compiled into rendered animation sequences.

---

## Table of Contents

1. [File Structure](#file-structure)
2. [Imports](#imports)
3. [Config Block](#config-block)
4. [Custom Pose Definitions](#custom-pose-definitions)
5. [Scene Declarations](#scene-declarations)
6. [Scene Statements](#scene-statements)
   - [Place](#place)
   - [Wait](#wait)
   - [Actions](#actions)
   - [Together (Parallel Execution)](#together-parallel-execution)
   - [Do (Explicit Sequential)](#do-explicit-sequential)
   - [Camera](#camera)
   - [Transitions](#transitions)
   - [Let Bindings](#let-bindings)
7. [Positions](#positions)
8. [Directions](#directions)
9. [Easing Functions](#easing-functions)
10. [Value Types](#value-types)
11. [Comments](#comments)
12. [Character Definition (JSON)](#character-definition-json)
13. [Overlap Detection](#overlap-detection)
14. [Best Practices and Tips](#best-practices-and-tips)

---

## File Structure

A `.anim` file is organized into four top-level sections, in this order:

1. **Import declarations** -- load external assets (characters, sets, props)
2. **Config block** -- global rendering settings
3. **Custom pose definitions** -- reusable pose templates
4. **Scene declarations** -- the animation content itself

All four sections are optional, but a useful script will contain at least one
scene. The order above must be respected: imports come before config, config
before poses, and poses before scenes.

---

## Imports

Import declarations load external assets into the script. There are three asset
types:

| Keyword     | Asset Type | File Format | Description                    |
|-------------|------------|-------------|--------------------------------|
| `character` | Character  | JSON        | Procedural character definition |
| `set`       | Set        | SVG         | Background / environment        |
| `prop`      | Prop       | SVG         | Overlay asset (object, icon)    |

### Syntax

```
import character <name> from "<path>"
import set <name> from "<path>"
import prop <name> from "<path>"
```

### Examples

```
import character detective from "assets/characters/procedural/detective.json"
import character informant from "assets/characters/procedural/informant.json"
import set alley from "assets/sets/dark-alley.svg"
import prop briefcase from "assets/props/briefcase.svg"
```

The `<name>` becomes the identifier used to reference the asset throughout the
rest of the script. Paths are relative to the `.anim` file location (which is
inside the `examples/` directory).

---

## Config Block

The config block sets global rendering parameters for the entire script.

### Syntax

```
config {
    width: <pixels>
    height: <pixels>
    fps: <integer>
    background: <hex-color>
}
```

### Fields

| Key          | Type      | Description                          | Example    |
|--------------|-----------|--------------------------------------|------------|
| `width`      | Integer   | Output width in pixels               | `1280`     |
| `height`     | Integer   | Output height in pixels              | `720`      |
| `fps`        | Integer   | Frames per second                    | `30`       |
| `background` | Hex color | Default background color             | `#1a1410`  |
| `monochrome` | Boolean   | Post-process every frame to high-contrast black & white ("ink" look) | `false` |

### Example

```
config {
    width: 1280
    height: 720
    fps: 30
    background: #1a1410
    monochrome: true
}
```

`monochrome: true` converts each rendered frame to a stark grayscale image with
boosted contrast — the hand-inked, mostly black-and-white look used by the
Freeman-style Лекторий lecture videos (see `examples/lektorij/`).

All fields are optional. If the config block is omitted entirely, the system
uses built-in defaults.

---

## Custom Pose Definitions

Poses describe the physical posture and facial expression of a character at a
given moment. Custom poses are defined at the top level and can be referenced by
name from any scene.

### Syntax

```
pose "<name>" {
    <field>: <number>
    ...
}
```

### Available Fields (23 total)

#### Body

| Field             | Description                        | Default |
|-------------------|------------------------------------|---------|
| `line-of-action`  | Overall body curve / flow          | 0.0     |
| `torso-bend`      | Forward/backward torso lean        | 0.0     |
| `torso-squash`    | Vertical compression of torso      | 0.0     |
| `shoulder-left`   | Left shoulder raise/lower          | 0.0     |
| `shoulder-right`  | Right shoulder raise/lower         | 0.0     |

#### Arms

| Field              | Description                       | Default |
|--------------------|-----------------------------------|---------|
| `arm-left-angle`   | Left arm rotation (degrees)       | 0.0     |
| `arm-right-angle`  | Right arm rotation (degrees)      | 0.0     |
| `elbow-left-bend`  | Left elbow bend amount (0-1)      | 0.0     |
| `elbow-right-bend` | Right elbow bend amount (0-1)     | 0.0     |

#### Legs

| Field              | Description                       | Default |
|--------------------|-----------------------------------|---------|
| `leg-left-angle`   | Left leg rotation (degrees)       | 0.0     |
| `leg-right-angle`  | Right leg rotation (degrees)      | 0.0     |
| `knee-left-bend`   | Left knee bend amount (0-1)       | 0.0     |
| `knee-right-bend`  | Right knee bend amount (0-1)      | 0.0     |

#### Head

| Field        | Description                            | Default |
|--------------|----------------------------------------|---------|
| `head-tilt`  | Side-to-side head tilt (degrees)       | 0.0     |
| `head-nod`   | Up/down head nod (degrees)             | 0.0     |

#### Position

| Field         | Description                           | Default |
|---------------|---------------------------------------|---------|
| `y-offset`    | Vertical offset from ground plane     | 0.0     |
| `body-angle`  | Explicit body rotation (degrees)      | 0.0     |

#### Expression

| Field            | Description                          | Default |
|------------------|--------------------------------------|---------|
| `eyebrow-left`   | Left eyebrow raise/lower            | 0.0     |
| `eyebrow-right`  | Right eyebrow raise/lower           | 0.0     |
| `eye-open-left`  | Left eye openness (0=closed, 1=open)| 1.0     |
| `eye-open-right` | Right eye openness (0=closed, 1=open)| 1.0    |
| `eye-direction`  | Horizontal gaze direction           | 0.0     |
| `mouth-smile`    | Smile amount (-1 to 1)              | 0.0     |
| `mouth-open`     | Mouth openness (0=closed, 1=open)   | 0.0     |

Any field not specified in a pose definition falls back to its default value
(0.0 for most fields, 1.0 for `eye-open-left` and `eye-open-right`).

### Built-in Poses

The following poses are available without explicit definition:

`idle`, `thinking`, `pointing`, `surprised`, `angry`, `menacing`, `scared`,
`excited`, `typing`

These serve as reasonable defaults and can be used directly in scene statements.
Custom poses with the same name will override the built-in version.

### Example

```
pose "drinking" {
    arm-right-angle: -80
    elbow-right-bend: 0.9
    head-nod: 8
    mouth-open: 0.15
    mouth-smile: 0.2
}
```

This defines a pose where the character's right arm is raised and bent at the
elbow (as if holding a cup), with the head tilted slightly down and a subtle
smile.

---

## Scene Declarations

Scenes are the primary containers for animation content. Each scene has a name,
optional parameters, and a body of statements.

### Syntax

```
scene "<name>" (duration: <N>s, set: <set-name>) {
    <statements>
}
```

### Parameters

| Parameter  | Type       | Default | Description                      |
|------------|------------|---------|----------------------------------|
| `duration` | Duration   | `10s`   | Total scene length               |
| `set`      | Identifier | --      | Background set to use            |

### Example

```
scene "confrontation" (duration: 8s, set: alley) {
    place detective at left-third facing right
    place informant at right-third facing left
    wait 1s
    detective moves-to center over 2s ease-in-out
}
```

---

## Scene Statements

The following statement types are available inside scene bodies.

### Place

Places an entity at a position before the scene timeline begins. Entities must
be placed before they can be used in actions.

```
place <entity> at <position> [facing <direction>] [layer <integer>]
```

- `facing` controls the initial orientation of the entity.
- `layer` controls draw order (higher layers render on top).

```
place detective at left facing right
place briefcase at center layer 3
```

### Wait

Pauses the timeline for the specified duration before the next statement
executes.

```
wait <duration>
```

```
wait 2s
wait 0.5s
```

### Actions

There are 9 action types that animate entities over time. All actions follow the
pattern:

```
<entity> <action> <arguments> [over <duration>] [<easing>]
```

#### enters

Moves an entity onto screen from the specified direction.

```
<entity> enters <direction> [over <duration>] [<easing>]
```

```
detective enters left over 2s ease-out
```

#### exits

Moves an entity off screen in the specified direction.

```
<entity> exits <direction> [over <duration>] [<easing>]
```

```
informant exits right over 1.5s ease-in
```

#### moves-to

Moves an entity to a new position.

```
<entity> moves-to <position> over <duration> [<easing>]
```

```
detective moves-to center over 2s ease-in-out
detective moves-to (0.6, 0.5) over 1s linear
```

#### pose

Changes the entity's pose. The transition between the current pose and the new
pose is interpolated smoothly.

```
<entity> pose "<pose-name>"
```

```
detective pose "thinking"
informant pose "drinking"
```

#### shows

Makes a hidden entity visible, with an optional fade-in.

```
<entity> shows [over <duration>] [<easing>]
```

```
briefcase shows over 0.5s ease-out
```

#### hides

Makes an entity invisible, with an optional fade-out.

```
<entity> hides [over <duration>] [<easing>]
```

```
briefcase hides over 0.3s ease-in
```

#### scales

Changes the scale of an entity (1.0 = default size).

```
<entity> scales <number> [over <duration>] [<easing>]
```

```
briefcase scales 1.5 over 0.5s ease-out
```

#### rotates

Rotates an entity by the specified number of degrees.

```
<entity> rotates <number> [over <duration>] [<easing>]
```

```
briefcase rotates 45 over 1s ease-in-out
```

#### fades-to

Changes the opacity of an entity (0.0 = fully transparent, 1.0 = fully opaque).

```
<entity> fades-to <number> [over <duration>] [<easing>]
```

```
informant fades-to 0.3 over 2s ease-out
```

### Together (Parallel Execution)

Executes all contained statements simultaneously. The `together` block completes
when the longest contained statement finishes.

```
together {
    <statement>
    <statement>
    ...
}
```

```
together {
    detective moves-to center over 2s ease-in-out
    informant moves-to right-edge over 2s ease-in
    camera zoom-to detective over 2s ease-in-out
}
```

### Do (Explicit Sequential)

Executes contained statements one after another. This is the default execution
mode for scene bodies, but `do` blocks are useful inside `together` blocks to
create sequential sub-sequences that run in parallel with other statements.

```
do {
    <statement>
    <statement>
}
```

```
together {
    do {
        detective moves-to center over 1s ease-out
        detective pose "pointing"
    }
    informant moves-to right-edge over 2s ease-in
}
```

In this example, the detective moves and then changes pose (sequentially), while
the informant moves simultaneously.

### Camera

Camera statements control the virtual camera. There are 6 shot types and 4
motion commands.

#### Shot Types

Shot types set the camera framing instantly. They can optionally target a
specific entity.

| Shot Type          | Description                                       |
|--------------------|---------------------------------------------------|
| `wide`             | Full scene view                                   |
| `medium`           | Waist-up framing                                  |
| `close-up`         | Head and shoulders                                |
| `extreme-close-up` | Face only                                         |
| `two-shot`         | Framing two characters                            |
| `over-shoulder`    | Over one character's shoulder toward another      |

```
camera wide
camera close-up detective
camera two-shot
camera over-shoulder informant
```

#### Motion Commands

| Command   | Description                                          |
|-----------|------------------------------------------------------|
| `zoom-to` | Smoothly zooms to frame an entity                    |
| `pan-to`  | Smoothly pans to an entity or coordinate             |
| `shake`   | Applies a camera shake effect                        |
| `reset`   | Returns camera to default wide position              |

```
camera zoom-to detective over 1.5s ease-in-out
camera pan-to informant over 2s ease-out
camera pan-to (0.3, 0.5) over 1s linear
camera shake 0.5s intensity 3
camera shake 1s
camera reset over 1s
camera reset
```

The `shake` command accepts an optional `intensity` parameter (default is 1).
Higher values produce more violent shaking. The `pan-to` command accepts either
an entity name or a coordinate pair as its target.

### Transitions

Transitions create visual bridges between scenes or moments within a scene.

| Type         | Description                              |
|--------------|------------------------------------------|
| `fade-black` | Fades to/from black                      |
| `fade-white` | Fades to/from white                      |
| `dissolve`   | Cross-dissolve between frames            |
| `wipe`       | Directional wipe                         |
| `cut`        | Instant cut (no duration)                |

```
transition fade-black 1s
transition fade-white 0.5s
transition dissolve 2s
transition wipe left 1s
transition wipe down 0.5s
transition cut
```

The `wipe` transition requires a direction. The `cut` transition takes no
duration.

### Let Bindings

Let bindings create named prop instances within a scene. This is useful for
introducing props dynamically without a top-level import.

```
let <name> = prop("<label>", "<path>") [at <position>]
```

```
let envelope = prop("secret-envelope", "assets/props/envelope.svg") at center
let phone = prop("phone", "assets/props/phone.svg") at near detective
```

The `<label>` is a human-readable name for the prop. The `<path>` is the file
path to the SVG asset. The optional `at` clause sets the initial position.

---

## Positions

Positions specify where entities are placed or moved to on the canvas.

### Named Positions

There are 17 built-in named positions. Coordinates are normalized (0.0 to 1.0),
with the origin at the top-left corner.

| Name              | Coordinates    | Description                        |
|-------------------|----------------|------------------------------------|
| `center`          | (0.50, 0.50)  | Dead center of the canvas          |
| `left`            | (0.20, 0.50)  | Left side, vertically centered     |
| `right`           | (0.80, 0.50)  | Right side, vertically centered    |
| `left-third`      | (0.33, 0.50)  | Left third mark                    |
| `right-third`     | (0.67, 0.50)  | Right third mark                   |
| `left-edge`       | (0.05, 0.50)  | Near the left edge                 |
| `right-edge`      | (0.95, 0.50)  | Near the right edge                |
| `top`             | (0.50, 0.15)  | Top center                         |
| `bottom`          | (0.50, 0.85)  | Bottom center                      |
| `top-left`        | (0.20, 0.20)  | Upper-left quadrant                |
| `top-right`       | (0.80, 0.20)  | Upper-right quadrant               |
| `bottom-left`     | (0.20, 0.80)  | Lower-left quadrant                |
| `bottom-right`    | (0.80, 0.80)  | Lower-right quadrant               |
| `offscreen-left`  | (-0.20, 0.50) | Off screen to the left             |
| `offscreen-right` | (1.20, 0.50)  | Off screen to the right            |
| `offscreen-up`    | (0.50, -0.20) | Off screen above                   |
| `offscreen-down`  | (0.50, 1.20)  | Off screen below                   |

### Coordinate Pairs

Explicit coordinates can be specified as a parenthesized pair of normalized
floating-point values:

```
(0.7, 0.3)
(0.0, 1.0)
(0.5, 0.5)
```

Values range from 0.0 to 1.0, where (0.0, 0.0) is the top-left corner and
(1.0, 1.0) is the bottom-right corner. Values outside this range (such as the
offscreen positions) are valid and place entities beyond the visible canvas.

### Relative Positions

Relative positions are computed based on another entity's current location:

| Syntax                  | Description                              |
|-------------------------|------------------------------------------|
| `near <entity>`         | Close to the entity                      |
| `behind <entity>`       | Behind the entity (depth-wise)           |
| `in-front-of <entity>`  | In front of the entity (depth-wise)      |
| `above <entity>`        | Above the entity                         |
| `below <entity>`        | Below the entity                         |
| `left-of <entity>`      | To the left of the entity                |
| `right-of <entity>`     | To the right of the entity               |

```
place briefcase at near detective
informant moves-to behind detective over 2s
```

---

## Directions

Directions are used for `enters`, `exits`, `facing`, and `wipe` transitions:

- `left`
- `right`
- `up`
- `down`
- `front` — facing (or, for wipes, treated as a left-to-right wipe). Use
  `facing front` for a character talking straight at the camera (body angle 0°),
  as in the Freeman-style lecture monologues.
- `back` — facing away from the camera (body angle 180°).

`front`/`back` are meaningful for `facing`; for spatial actions (`enters`,
`exits`, `wipe`) they fall back to a sensible default.

---

## Easing Functions

Easing functions control the acceleration curve of animated transitions. They
are specified as a trailing keyword on any action that has an `over` duration.

| Easing         | Description                                        |
|----------------|----------------------------------------------------|
| `linear`       | Constant speed from start to finish                |
| `ease-in`      | Starts slow, accelerates                           |
| `ease-out`     | Starts fast, decelerates                           |
| `ease-in-out`  | Starts slow, speeds up, then slows down            |

If no easing is specified, the system uses a default (typically `ease-in-out`
for movement actions).

---

## Value Types

AnimDSL supports the following primitive value types:

| Type       | Syntax              | Examples                         |
|------------|---------------------|----------------------------------|
| Duration   | `<number>s`         | `1.5s`, `0.3s`, `10s`           |
| Number     | Integer or float    | `42`, `-3.14`, `0.5`, `1.0`     |
| String     | Double-quoted       | `"hello"`, `"drinking"`         |
| Color      | Hex notation        | `#ff00aa`, `#ff00aacc` (w/ alpha)|
| Boolean    | Keyword             | `true`, `false`                  |
| Identifier | Hyphenated name     | `my-character`, `dark-alley`     |

Duration values are always a number immediately followed by `s` with no space.
Colors use standard hex notation: 6 digits for RGB, 8 digits for RGBA.
Identifiers may contain letters, digits, and hyphens, but must start with a
letter.

---

## Comments

Single-line comments begin with `//` and extend to the end of the line.

```
// This is a comment
place detective at left  // inline comment
```

There are no multi-line or block comments.

---

## Character Definition (JSON)

Characters are defined in external JSON files and loaded via `import character`.
The JSON schema describes the procedural parameters used to generate a
character's visual appearance.

### Full Schema

```json
{
  "name": "string",
  "body": {
    "height": 0.0-1.0,
    "build": 0.0-1.0,
    "skin_color": [R, G, B]
  },
  "face": {
    "shape": 0.0-1.0,
    "eye_size": 0.5-1.2,
    "eye_color": [R, G, B],
    "eyebrow_thickness": 0.0-1.0,
    "nose_size": 0.0-1.0,
    "lip_fullness": 0.0-1.0
  },
  "hair": {
    "color": [R, G, B],
    "style": "SlickedBack|Messy|Straight|Wavy|Short|Buzz|Bald",
    "length": 0.0-1.0
  },
  "outfit": {
    "top": {
      "kind": "TrenchCoat|Suit|Hoodie|TShirt|Dress",
      "color": [R, G, B],
      "secondary_color": [R, G, B]
    },
    "bottom": {
      "kind": "Pants|Jeans|Skirt",
      "color": [R, G, B]
    },
    "shoes": {
      "kind": "Formal|Sneakers|Boots",
      "color": [R, G, B]
    },
    "accessories": [
      {
        "kind": "Hat|Fedora|Glasses|Tie|Scarf|Belt",
        "color": [R, G, B]
      }
    ]
  }
}
```

### Field Reference

#### body

| Field        | Type      | Range     | Description                        |
|--------------|-----------|-----------|------------------------------------|
| `height`     | Float     | 0.0 - 1.0| Character height (short to tall)   |
| `build`      | Float     | 0.0 - 1.0| Body build (slim to stocky)        |
| `skin_color` | [R, G, B] | 0-255 each| Skin color as RGB                 |

#### face

| Field               | Type      | Range      | Description                   |
|---------------------|-----------|------------|-------------------------------|
| `shape`             | Float     | 0.0 - 1.0 | Face shape (narrow to wide)   |
| `eye_size`          | Float     | 0.5 - 1.2 | Eye size multiplier           |
| `eye_color`         | [R, G, B] | 0-255 each| Iris color                    |
| `eyebrow_thickness` | Float     | 0.0 - 1.0 | Eyebrow thickness             |
| `nose_size`         | Float     | 0.0 - 1.0 | Nose size (small to large)    |
| `lip_fullness`      | Float     | 0.0 - 1.0 | Lip fullness                  |

#### hair

| Field    | Type      | Range     | Description                          |
|----------|-----------|-----------|--------------------------------------|
| `color`  | [R, G, B] | 0-255 each| Hair color                          |
| `style`  | String    | Enum      | One of: SlickedBack, Messy, Straight, Wavy, Short, Buzz, Bald |
| `length` | Float     | 0.0 - 1.0| Hair length (buzzcut to long)        |

`Bald` draws no hair — a clean scalp with a soft crown highlight (used by Fredi).

#### outfit

The `outfit` object contains `top`, `bottom`, `shoes`, and an optional
`accessories` array.

**top**: `kind` is one of `TrenchCoat`, `Suit`, `Hoodie`, `TShirt`, `Dress`.
`color` and `secondary_color` are RGB arrays.

**bottom**: `kind` is one of `Pants`, `Jeans`, `Skirt`. `color` is an RGB array.

**shoes**: `kind` is one of `Formal`, `Sneakers`, `Boots`. `color` is an RGB
array.

**accessories**: An array of objects, each with a `kind` (one of `Hat`,
`Fedora`, `Glasses`, `Tie`, `BowTie`, `Scarf`, `Belt`) and a `color` RGB array.
`Glasses` renders as round lenses; `BowTie` renders a bow at the collar (the
signature "Fredi" look).

### Example Character File

```json
{
  "name": "Detective Marlowe",
  "body": {
    "height": 0.7,
    "build": 0.5,
    "skin_color": [210, 180, 150]
  },
  "face": {
    "shape": 0.5,
    "eye_size": 0.9,
    "eye_color": [80, 120, 90],
    "eyebrow_thickness": 0.6,
    "nose_size": 0.5,
    "lip_fullness": 0.4
  },
  "hair": {
    "color": [40, 30, 20],
    "style": "SlickedBack",
    "length": 0.3
  },
  "outfit": {
    "top": {
      "kind": "TrenchCoat",
      "color": [80, 70, 55],
      "secondary_color": [60, 50, 40]
    },
    "bottom": {
      "kind": "Pants",
      "color": [50, 45, 40]
    },
    "shoes": {
      "kind": "Formal",
      "color": [30, 25, 20]
    },
    "accessories": [
      { "kind": "Fedora", "color": [70, 60, 50] },
      { "kind": "Tie", "color": [120, 30, 30] }
    ]
  }
}
```

---

## Overlap Detection

The rendering system performs automatic overlap detection to prevent characters
from occupying the same space. This check is a hard error -- overlapping
characters will cause the script to fail before any frames are rendered.

### How It Works

- The system samples character positions at **0.1-second intervals** throughout
  each scene.
- Two characters are considered overlapping if they are within **0.12 normalized
  units horizontally** and **0.15 normalized units vertically** of each other.
- Characters that are **offscreen** (outside the 0.0-1.0 visible range) or
  **invisible** (opacity of 0 or hidden via `hides`) are excluded from overlap
  checks.

### Resolving Overlaps

If the system reports an overlap error, you must adjust your script so that no
two characters occupy the same space at the same time. Common fixes include:

- Staggering movement timings so characters do not cross paths
- Using different positions that maintain sufficient spacing
- Hiding one character before moving another into its position
- Adjusting the paths so characters move around each other

---

## Best Practices and Tips

### Always place before acting

Every entity must be placed with a `place` statement before it can be used in
any action. Attempting to animate an entity that has not been placed will result
in an error.

```
// Correct
place detective at left facing right
detective moves-to center over 2s

// Wrong -- detective has not been placed
detective moves-to center over 2s
```

### Use together blocks for simultaneous actions

By default, statements in a scene execute sequentially. If two actions should
happen at the same time, wrap them in a `together` block. Nest `do` blocks
inside `together` when you need sequential sub-chains running in parallel.

```
together {
    detective moves-to left-third over 2s ease-out
    do {
        wait 0.5s
        informant enters right over 1.5s ease-out
    }
}
```

### Characters auto-turn based on movement and facing

Characters automatically turn to face the direction they are moving. If a
character moves from left to right, they will face right. If a character moves
from right to left, they will face left. The `facing` keyword on `place`
overrides this for the initial orientation. You do not need to manually manage
facing in most cases.

### Custom poses interpolate smoothly

When a character transitions between poses (via the `pose` action), the system
smoothly interpolates all 23 fields from the current values to the target
values. This means you can chain multiple pose changes and the character will
animate fluidly between them without any snapping.

```
detective pose "thinking"
wait 2s
detective pose "pointing"
wait 1s
detective pose "idle"
```

### Use body-angle for explicit rotation

The `body-angle` field in pose definitions gives you direct control over the
character's body rotation in degrees. This is distinct from the automatic facing
behavior and allows for more expressive posing, such as having a character turn
partially away from the camera.

```
pose "looking-away" {
    body-angle: 30
    head-tilt: -10
    eye-direction: -0.5
}
```

### Keep scene durations accurate

Set scene durations to match or slightly exceed the total time your animations
require. If a scene's duration is shorter than the actions within it, later
actions may be clipped. If it is much longer, there will be dead time at the end.

### Use named positions for readability

While coordinate pairs like `(0.33, 0.5)` are precise, named positions like
`left-third` are more readable and maintainable. Use named positions when they
match your intent, and reserve coordinate pairs for precise positioning that
named positions do not cover.

### Structure complex scenes with do and together

For scenes with complex choreography, build your timeline with nested `together`
and `do` blocks. This makes the timing relationships between actions explicit
and easier to reason about.

```
together {
    do {
        transition fade-black 0.5s
        wait 0.5s
        transition fade-black 0.5s
    }
    do {
        camera shake 0.3s intensity 2
        wait 0.3s
        camera zoom-to detective over 0.7s ease-out
    }
}
```

---

## Complete Example

The following is a complete `.anim` script demonstrating most language features:

```
// Import assets
import character detective from "assets/characters/procedural/detective.json"
import character informant from "assets/characters/procedural/informant.json"
import set alley from "assets/sets/dark-alley.svg"
import prop briefcase from "assets/props/briefcase.svg"

// Rendering configuration
config {
    width: 1920
    height: 1080
    fps: 30
    background: #0a0a0f
}

// Custom poses
pose "drinking" {
    arm-right-angle: -80
    elbow-right-bend: 0.9
    head-nod: 8
    mouth-open: 0.15
    mouth-smile: 0.2
}

pose "looking-around" {
    head-tilt: 15
    eye-direction: 0.7
    eyebrow-left: 0.3
    eyebrow-right: -0.1
}

// Scene: the meeting
scene "the-meeting" (duration: 15s, set: alley) {
    place detective at left-third facing right
    camera wide

    wait 1s
    informant enters right over 2s ease-out
    wait 0.5s

    camera medium

    together {
        detective pose "looking-around"
        informant moves-to right-third over 1s ease-out
    }

    wait 1s
    camera two-shot

    let envelope = prop("envelope", "assets/props/envelope.svg") at near informant
    informant pose "pointing"
    wait 0.5s
    envelope shows over 0.3s ease-out

    together {
        detective moves-to center over 1.5s ease-in-out
        camera zoom-to detective over 1.5s ease-in-out
    }

    detective pose "thinking"
    wait 2s

    transition fade-black 1s
}
```
