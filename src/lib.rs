pub mod assets;
pub mod ast;
pub mod errors;
pub mod parser;
pub mod procedural;
pub mod renderer;
pub mod scene;
pub mod skeleton;
pub mod timeline;
pub mod video;

use std::sync::{Arc, OnceLock};

/// Shared font database for SVG text rendering (loaded once). System fonts
/// (DejaVu etc.) give sets/props real Cyrillic text — lecture titles, tables.
pub fn shared_fontdb() -> Arc<usvg::fontdb::Database> {
    static DB: OnceLock<Arc<usvg::fontdb::Database>> = OnceLock::new();
    DB.get_or_init(|| {
        let mut db = usvg::fontdb::Database::new();
        db.load_system_fonts();
        Arc::new(db)
    })
    .clone()
}

/// usvg options with the shared font database attached.
pub fn svg_options() -> usvg::Options<'static> {
    let mut opts = usvg::Options::default();
    opts.fontdb = shared_fontdb();
    opts
}
