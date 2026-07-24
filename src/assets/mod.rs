//! Asset loader — loads SVG character/set/prop assets.
//! Characters can be either single SVGs (legacy) or rig directories (new).

use std::collections::HashMap;
use std::path::{Path, PathBuf};

use crate::ast::{ImportDecl, ImportKind};
use crate::errors::AnimError;
use crate::procedural::CharacterDesc;
use crate::skeleton::CharacterRig;

/// A loaded character — legacy SVG, rig-based, or procedural.
#[derive(Debug, Clone)]
pub enum CharacterAsset {
    /// Legacy single-SVG character.
    Legacy {
        name: String,
        path: PathBuf,
        svg_data: Vec<u8>,
        width: f64,
        height: f64,
    },
    /// Rig-based character with separate parts.
    Rigged(CharacterRig),
    /// Procedurally drawn character (no external assets).
    Procedural(CharacterDesc),
}

impl CharacterAsset {
    pub fn name(&self) -> &str {
        match self {
            CharacterAsset::Legacy { name, .. } => name,
            CharacterAsset::Rigged(rig) => &rig.name,
            CharacterAsset::Procedural(desc) => &desc.name,
        }
    }
}

/// A loaded set (background) asset.
#[derive(Debug, Clone)]
pub struct SetAsset {
    pub name: String,
    pub path: PathBuf,
    pub svg_data: Vec<u8>,
    pub width: f64,
    pub height: f64,
}

/// A loaded prop asset.
#[derive(Debug, Clone)]
pub struct PropAsset {
    pub name: String,
    pub path: PathBuf,
    pub svg_data: Vec<u8>,
    pub width: f64,
    pub height: f64,
}

/// Registry of all loaded assets.
#[derive(Debug, Default)]
pub struct AssetRegistry {
    pub characters: HashMap<String, CharacterAsset>,
    pub sets: HashMap<String, SetAsset>,
    pub props: HashMap<String, PropAsset>,
}

impl AssetRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    /// Load all assets from import declarations.
    pub fn load_imports(
        &mut self,
        imports: &[ImportDecl],
        base_dir: &Path,
    ) -> Result<(), AnimError> {
        for import in imports {
            let full_path = base_dir.join(&import.path);
            match import.kind {
                ImportKind::Character => {
                    let asset = load_character(&import.name, &full_path)?;
                    self.characters.insert(import.name.clone(), asset);
                }
                ImportKind::Set => {
                    let asset = load_set(&import.name, &full_path)?;
                    self.sets.insert(import.name.clone(), asset);
                }
                ImportKind::Prop => {
                    let asset = load_prop(&import.name, &full_path)?;
                    self.props.insert(import.name.clone(), asset);
                }
            }
        }
        Ok(())
    }

    /// Load a prop dynamically (from a let binding).
    pub fn load_dynamic_prop(
        &mut self,
        name: &str,
        label: &str,
        path_str: &str,
        base_dir: &Path,
    ) -> Result<(), AnimError> {
        let full_path = base_dir.join(path_str);
        let mut asset = load_prop(label, &full_path)?;
        asset.name = name.to_string();
        self.props.insert(name.to_string(), asset);
        Ok(())
    }
}

fn load_character(name: &str, path: &Path) -> Result<CharacterAsset, AnimError> {
    // If it's a directory with rig.json, treat as a rig.
    if path.is_dir() {
        let rig_json = path.join("rig.json");
        if rig_json.exists() {
            let rig = crate::skeleton::load_rig(name, path)?;
            return Ok(CharacterAsset::Rigged(rig));
        }
    }

    // If it's a .json file, treat as a procedural character description.
    if path.extension().map(|e| e == "json").unwrap_or(false) {
        let json = std::fs::read_to_string(path).map_err(|e| {
            AnimError::Asset(format!(
                "failed to read character description '{}' from {}: {}",
                name,
                path.display(),
                e
            ))
        })?;
        let desc: CharacterDesc = serde_json::from_str(&json).map_err(|e| {
            AnimError::Asset(format!(
                "failed to parse character description for '{}': {}",
                name, e
            ))
        })?;
        return Ok(CharacterAsset::Procedural(desc));
    }

    // Otherwise, legacy single-SVG.
    let svg_data = std::fs::read(path).map_err(|e| {
        AnimError::Asset(format!(
            "failed to read character '{}' from {}: {}",
            name,
            path.display(),
            e
        ))
    })?;

    let opts = crate::svg_options();
    let tree = usvg::Tree::from_data(&svg_data, &opts)
        .map_err(|e| AnimError::Asset(format!("failed to parse SVG for '{}': {}", name, e)))?;

    let size = tree.size();

    Ok(CharacterAsset::Legacy {
        name: name.to_string(),
        path: path.to_path_buf(),
        svg_data,
        width: size.width() as f64,
        height: size.height() as f64,
    })
}

fn load_set(name: &str, path: &Path) -> Result<SetAsset, AnimError> {
    let svg_data = std::fs::read(path).map_err(|e| {
        AnimError::Asset(format!(
            "failed to read set '{}' from {}: {}",
            name,
            path.display(),
            e
        ))
    })?;

    let opts = crate::svg_options();
    let tree = usvg::Tree::from_data(&svg_data, &opts)
        .map_err(|e| AnimError::Asset(format!("failed to parse SVG for set '{}': {}", name, e)))?;

    let size = tree.size();

    Ok(SetAsset {
        name: name.to_string(),
        path: path.to_path_buf(),
        svg_data,
        width: size.width() as f64,
        height: size.height() as f64,
    })
}

fn load_prop(name: &str, path: &Path) -> Result<PropAsset, AnimError> {
    let svg_data = std::fs::read(path).map_err(|e| {
        AnimError::Asset(format!(
            "failed to read prop '{}' from {}: {}",
            name,
            path.display(),
            e
        ))
    })?;

    let opts = crate::svg_options();
    let tree = usvg::Tree::from_data(&svg_data, &opts)
        .map_err(|e| AnimError::Asset(format!("failed to parse SVG for prop '{}': {}", name, e)))?;

    let size = tree.size();

    Ok(PropAsset {
        name: name.to_string(),
        path: path.to_path_buf(),
        svg_data,
        width: size.width() as f64,
        height: size.height() as f64,
    })
}
