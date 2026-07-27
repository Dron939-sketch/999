//! Asset loader — loads SVG character/set/prop assets.
//! Characters can be either single SVGs (legacy) or rig directories (new).

use std::collections::HashMap;

use serde::Deserialize;
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
    /// Карта поверхностей локации из `<локация>.surfaces.json`, если она есть.
    pub surfaces: Option<Surfaces>,
}

/// КАРТА ПОВЕРХНОСТЕЙ ЛОКАЦИИ: где в кадре пол и на какой высоте горизонт.
///
/// Локация нарисована в перспективе, а пропы живут в плоских долях кадра и
/// ничего о ней не знают. Отсюда крыса, которая на дальней стене того же
/// размера, что на переднем плане, и предметы, наполовину утопленные в пол:
/// якорь пропа — ЦЕНТР его рисунка, а не точка опоры.
///
/// Файл рядом с локацией существовал и раньше — но его не читала ни одна
/// строчка кода. Это была документация, которую никто не соблюдал.
#[derive(Debug, Clone, Deserialize)]
pub struct Surfaces {
    pub floor: Floor,
}

#[derive(Debug, Clone, Copy, Deserialize)]
pub struct Floor {
    /// Задняя кромка пола (у стен) — доля высоты кадра.
    pub back_y: f64,
    /// Передняя кромка пола (низ кадра).
    pub front_y: f64,
}

impl Floor {
    /// Во сколько раз предмет на полу на высоте `y` мельче, чем на передней
    /// кромке. Линейно по глубине: у задней кромки — `far`, у передней — 1.0.
    /// Точка схода лежит выше задней кромки, поэтому за ней ничего не
    /// уменьшается дальше — зажимаем.
    /// `place ... on floor`: заданная точка — СТУПНИ. Возвращает (якорь по y,
    /// множитель масштаба). Формула обязана быть ОДНА на весь конвейер:
    /// кадрирование считает план по якорю и масштабу, рендер рисует по ним же.
    /// Пока грунтовка применялась только при отрисовке, камера наводилась на
    /// негрунтованную точку — планы разъезжались с фигурой, и на среднем плане
    /// персонаж вылезал за кадр.
    pub fn ground(&self, floor_y: f64, scale_y: f64, feet: f64) -> (f64, f64) {
        const FAR: f64 = 0.55;
        let d = self.depth_scale(floor_y, FAR);
        (floor_y - feet * scale_y * d, d)
    }

    pub fn depth_scale(&self, y: f64, far: f64) -> f64 {
        let span = (self.front_y - self.back_y).abs().max(1e-6);
        let t = ((y - self.back_y) / span).clamp(0.0, 1.0);
        far + (1.0 - far) * t
    }
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
    /// Карты фигур всех загруженных персонажей (см. `skeleton::Karta`).
    /// По ним компилятор таймлайна кадрирует планы — у КАЖДОГО персонажа по
    /// его собственным пропорциям, а не по числам, подобранным для одного.
    pub fn kartas(&self) -> HashMap<String, crate::skeleton::Karta> {
        self.characters
            .iter()
            .filter_map(|(name, a)| match a {
                CharacterAsset::Rigged(rig) => rig.karta.map(|k| (name.clone(), k)),
                _ => None,
            })
            .collect()
    }
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

    /// Register a kinetic-typography word as a synthesized SVG prop.
    /// Жирная тушь DejaVu Sans Bold + рваная кромка (turbulence) — слово-удар
    /// в стиле Фримена. Все действия пропов работают из коробки.
    pub fn register_text_prop(
        &mut self,
        name: &str,
        content: &str,
        size: f64,
    ) -> Result<(), AnimError> {
        let size = if size > 0.0 { size } else { 120.0 };
        // Ширина по количеству char'ов (кириллица моноширинно-широкая в Bold —
        // множитель 0.72 подобран по DejaVu), запас на displacement-фильтр.
        let chars = content.chars().count().max(1) as f64;
        let w = (chars * size * 0.72 + size * 0.8).ceil();
        let h = (size * 1.7).ceil();
        let svg = format!(
            r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <filter id="ink" x="-8%" y="-15%" width="116%" height="130%">
      <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="1" seed="4" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="{disp}" xChannelSelector="R" yChannelSelector="G"/>
    </filter>
  </defs>
  <text x="{cx}" y="{by}" filter="url(#ink)" fill="#16160f"
        font-family="DejaVu Sans, sans-serif" font-weight="bold"
        font-size="{size}" text-anchor="middle" letter-spacing="{ls}">{esc}</text>
</svg>"##,
            w = w,
            h = h,
            cx = w / 2.0,
            by = size * 1.18,
            disp = (size * 0.022).clamp(2.0, 4.5),
            ls = size * 0.02,
            esc = content
                .replace('&', "&amp;")
                .replace('<', "&lt;")
                .replace('>', "&gt;"),
        );
        let svg_data = svg.into_bytes();
        let opts = crate::svg_options();
        let tree = usvg::Tree::from_data(&svg_data, &opts).map_err(|e| {
            AnimError::Asset(format!("failed to build text prop '{name}': {e}"))
        })?;
        let tsize = tree.size();
        self.props.insert(
            name.to_string(),
            PropAsset {
                name: name.to_string(),
                path: std::path::PathBuf::from(format!("<text:{content}>")),
                svg_data,
                width: tsize.width() as f64,
                height: tsize.height() as f64,
            },
        );
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

    // Карта поверхностей — необязательный файл рядом: `<локация>.surfaces.json`.
    let surf_path = path.with_extension("surfaces.json");
    let surfaces = match std::fs::read_to_string(&surf_path) {
        Ok(txt) => Some(serde_json::from_str::<Surfaces>(&txt).map_err(|e| {
            AnimError::Asset(format!(
                "карта поверхностей '{}' не разбирается: {}",
                surf_path.display(),
                e
            ))
        })?),
        Err(_) => None,
    };

    Ok(SetAsset {
        name: name.to_string(),
        path: path.to_path_buf(),
        svg_data,
        width: size.width() as f64,
        height: size.height() as f64,
        surfaces,
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
