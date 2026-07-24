//! AnimDSL — CLI entry point.
//!
//! Usage:
//!   animdsl render scene.anim -o output.mp4
//!   animdsl render scene.anim --png-dir ./frames
//!   animdsl check scene.anim

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use anyhow::Result;
use clap::{Parser, Subcommand};

use animdsl::assets::AssetRegistry;
use animdsl::ast::TopLevelItem;
use animdsl::errors::AnimError;
use animdsl::renderer;
use animdsl::scene::{resolve_scene, EntityKind, RenderConfig};
use animdsl::timeline;
use animdsl::video;

#[derive(Parser)]
#[command(
    name = "animdsl",
    version,
    about = "A DSL for generating 2D animated movie scenes"
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Render a .anim file to video or image sequence.
    Render {
        /// Path to the .anim source file.
        input: PathBuf,

        /// Output video file path (e.g., output.mp4).
        #[arg(short, long)]
        output: Option<PathBuf>,

        /// Output directory for PNG frame sequence (alternative to video).
        #[arg(long)]
        png_dir: Option<PathBuf>,

        /// Override FPS.
        #[arg(long)]
        fps: Option<u32>,

        /// Override width.
        #[arg(long)]
        width: Option<u32>,

        /// Override height.
        #[arg(long)]
        height: Option<u32>,
    },

    /// Parse and validate a .anim file without rendering.
    Check {
        /// Path to the .anim source file.
        input: PathBuf,
    },

    /// Parse a .anim file and dump the AST as JSON.
    Dump {
        /// Path to the .anim source file.
        input: PathBuf,
    },
}

fn main() -> Result<()> {
    env_logger::init();
    let cli = Cli::parse();

    match cli.command {
        Commands::Render {
            input,
            output,
            png_dir,
            fps,
            width,
            height,
        } => {
            let output = output.unwrap_or_else(|| input.with_extension("mp4"));
            cmd_render(&input, &output, png_dir.as_deref(), fps, width, height)?;
        }
        Commands::Check { input } => {
            cmd_check(&input)?;
        }
        Commands::Dump { input } => {
            cmd_dump(&input)?;
        }
    }

    Ok(())
}

fn cmd_render(
    input: &Path,
    output: &Path,
    png_dir: Option<&Path>,
    fps_override: Option<u32>,
    width_override: Option<u32>,
    height_override: Option<u32>,
) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let base_dir = input
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf();

    // Parse.
    let program = animdsl::parser::parse(&source)?;

    // Extract config.
    let mut config = RenderConfig::default();
    for item in &program.items {
        if let TopLevelItem::Config(cfg) = item {
            config = RenderConfig::from_config_block(cfg);
        }
    }

    // Apply CLI overrides.
    if let Some(fps) = fps_override {
        config.fps = fps;
    }
    if let Some(w) = width_override {
        config.width = w;
    }
    if let Some(h) = height_override {
        config.height = h;
    }

    // Load assets.
    let mut assets = AssetRegistry::new();
    let imports: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Import(imp) = item {
                Some(imp.clone())
            } else {
                None
            }
        })
        .collect();
    assets.load_imports(&imports, &base_dir)?;

    // Extract custom pose definitions.
    let mut custom_poses: HashMap<String, Vec<(String, f64)>> = HashMap::new();
    for item in &program.items {
        if let TopLevelItem::PoseDef(pose_def) = item {
            let fields: Vec<(String, f64)> = pose_def
                .fields
                .iter()
                .map(|f| (f.name.clone(), f.value))
                .collect();
            custom_poses.insert(pose_def.name.clone(), fields);
        }
    }

    // Process each scene.
    let scenes: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Scene(scene) = item {
                Some(scene)
            } else {
                None
            }
        })
        .collect();

    if scenes.is_empty() {
        return Err(AnimError::Scene("no scenes found in source file".into()).into());
    }

    let mut all_frames = Vec::new();

    for scene_decl in &scenes {
        log::info!("Processing scene: {}", scene_decl.name);

        let resolved = resolve_scene(scene_decl, &assets)?;
        let compiled_timeline = timeline::compile(&resolved)?;

        // Check for character overlaps before rendering.
        let character_names: Vec<String> = resolved
            .entities
            .iter()
            .filter(|(_, e)| e.kind == EntityKind::Character)
            .map(|(name, _)| name.clone())
            .collect();
        timeline::check_overlaps(&compiled_timeline, &resolved.entities, &character_names)?;

        let frames = renderer::render_scene(
            &config,
            &compiled_timeline,
            &resolved.entities,
            resolved.set_name.as_deref(),
            &assets,
            &custom_poses,
        )?;
        all_frames.extend(frames);
    }

    // Freeman-style black & white ("ink") post-process.
    if config.monochrome {
        for frame in &mut all_frames {
            apply_monochrome(&mut frame.data);
        }
    }

    // Output.
    if let Some(dir) = png_dir {
        video::encode_png_sequence(&all_frames, dir)?;
    }

    video::encode_video(&all_frames, output, config.fps)?;

    println!(
        "Rendered {} scene(s), {} frames -> {}",
        scenes.len(),
        all_frames.len(),
        output.display(),
    );

    Ok(())
}

/// Convert an RGBA frame buffer to a high-contrast black & white "ink" image
/// in place. Alpha is preserved. This is what gives the Freeman-style lecture
/// videos their stark hand-inked, mostly-monochrome look.
fn apply_monochrome(data: &mut [u8]) {
    // Contrast strength around mid-grey. >1.0 pushes lights lighter and darks
    // darker, which reads as bold ink strokes on paper.
    const CONTRAST: f32 = 1.35;
    for px in data.chunks_exact_mut(4) {
        // Rec. 601 luma.
        let luma = 0.299 * px[0] as f32 + 0.587 * px[1] as f32 + 0.114 * px[2] as f32;
        // Apply an S-curve style contrast around 128.
        let adjusted = ((luma - 128.0) * CONTRAST + 128.0).clamp(0.0, 255.0);
        let v = adjusted as u8;
        px[0] = v;
        px[1] = v;
        px[2] = v;
        // px[3] (alpha) untouched.
    }
}

fn cmd_check(input: &Path) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let base_dir = input
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .to_path_buf();

    let program = animdsl::parser::parse(&source)?;

    let mut n_imports = 0;
    let mut n_scenes = 0;
    let mut has_config = false;

    for item in &program.items {
        match item {
            TopLevelItem::Import(_) => n_imports += 1,
            TopLevelItem::Config(_) => has_config = true,
            TopLevelItem::Scene(_) => n_scenes += 1,
            TopLevelItem::PoseDef(_) => {}
        }
    }

    // Load assets so we can resolve scenes and check overlaps.
    let mut assets = AssetRegistry::new();
    let imports: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Import(imp) = item {
                Some(imp.clone())
            } else {
                None
            }
        })
        .collect();
    assets.load_imports(&imports, &base_dir)?;

    // Resolve each scene, compile its timeline, and check for overlaps.
    let scenes: Vec<_> = program
        .items
        .iter()
        .filter_map(|item| {
            if let TopLevelItem::Scene(scene) = item {
                Some(scene)
            } else {
                None
            }
        })
        .collect();

    for scene_decl in &scenes {
        let resolved = resolve_scene(scene_decl, &assets)?;
        let compiled_timeline = timeline::compile(&resolved)?;

        let character_names: Vec<String> = resolved
            .entities
            .iter()
            .filter(|(_, e)| e.kind == EntityKind::Character)
            .map(|(name, _)| name.clone())
            .collect();
        timeline::check_overlaps(&compiled_timeline, &resolved.entities, &character_names)?;
    }

    println!("OK: {}", input.display());
    println!("  Imports: {n_imports}");
    println!("  Config:  {}", if has_config { "yes" } else { "no" });
    println!("  Scenes:  {n_scenes}");
    println!("  Overlaps: none detected");

    Ok(())
}

fn cmd_dump(input: &Path) -> Result<()> {
    let source = std::fs::read_to_string(input)?;
    let program = animdsl::parser::parse(&source)?;
    let json = serde_json::to_string_pretty(&program)?;
    println!("{json}");
    Ok(())
}
