//! Error types for AnimDSL.

use thiserror::Error;

#[derive(Debug, Error)]
pub enum AnimError {
    #[error("Parse error: {0}")]
    Parse(String),

    #[error("Asset error: {0}")]
    Asset(String),

    #[error("Scene error: {0}")]
    Scene(String),

    #[error("Timeline error: {0}")]
    Timeline(String),

    #[error("Render error: {0}")]
    Render(String),

    #[error("Video error: {0}")]
    Video(String),

    #[error("Overlap error: {0}")]
    Overlap(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}
