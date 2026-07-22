//! Video pipeline — encodes rendered frames into an MP4 video via FFmpeg.

use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::errors::AnimError;
use crate::renderer::Frame;

/// Encode a sequence of frames into an MP4 video file.
pub fn encode_video(frames: &[Frame], output: &Path, fps: u32) -> Result<(), AnimError> {
    if frames.is_empty() {
        return Err(AnimError::Video("no frames to encode".into()));
    }

    let width = frames[0].width;
    let height = frames[0].height;

    log::info!(
        "Encoding {} frames to {} ({}x{} @ {} fps)",
        frames.len(),
        output.display(),
        width,
        height,
        fps,
    );

    // Create parent directories if they don't exist.
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|e| {
                AnimError::Video(format!(
                    "failed to create output directory '{}': {e}",
                    parent.display()
                ))
            })?;
        }
    }

    // Spawn FFmpeg process.
    let mut child = Command::new("ffmpeg")
        .args([
            "-y", // overwrite output
            "-f",
            "rawvideo", // input format
            "-pix_fmt",
            "rgba", // input pixel format
            "-s",
            &format!("{width}x{height}"), // frame size
            "-r",
            &fps.to_string(), // frame rate
            "-i",
            "-", // read from stdin
            "-c:v",
            "libx264", // H.264 codec
            "-pix_fmt",
            "yuv420p", // output pixel format
            "-preset",
            "medium", // encoding speed/quality tradeoff
            "-crf",
            "23", // quality (lower = better, 18-28 reasonable)
            "-movflags",
            "+faststart", // optimize for streaming
        ])
        .arg(output.as_os_str())
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| {
            AnimError::Video(format!("failed to start ffmpeg: {e}. Is ffmpeg installed?"))
        })?;

    let stdin = child
        .stdin
        .as_mut()
        .ok_or_else(|| AnimError::Video("failed to open ffmpeg stdin".into()))?;

    // Write each frame's raw RGBA data to FFmpeg's stdin.
    for (i, frame) in frames.iter().enumerate() {
        stdin
            .write_all(&frame.data)
            .map_err(|e| AnimError::Video(format!("failed to write frame {i} to ffmpeg: {e}")))?;
    }

    // Close stdin to signal end of input.
    drop(child.stdin.take());

    // Wait for FFmpeg to finish.
    let output_result = child
        .wait_with_output()
        .map_err(|e| AnimError::Video(format!("ffmpeg process error: {e}")))?;

    if !output_result.status.success() {
        let stderr = String::from_utf8_lossy(&output_result.stderr);
        return Err(AnimError::Video(format!("ffmpeg failed: {stderr}")));
    }

    log::info!("Video encoded successfully: {}", output.display());
    Ok(())
}

/// Encode frames as individual PNG files (useful for debugging).
pub fn encode_png_sequence(frames: &[Frame], output_dir: &Path) -> Result<(), AnimError> {
    std::fs::create_dir_all(output_dir)?;

    for (i, frame) in frames.iter().enumerate() {
        let path = output_dir.join(format!("frame_{:06}.png", i));
        write_png(&path, &frame.data, frame.width, frame.height)?;
    }

    log::info!(
        "Wrote {} PNG frames to {}",
        frames.len(),
        output_dir.display()
    );
    Ok(())
}

fn write_png(path: &Path, data: &[u8], width: u32, height: u32) -> Result<(), AnimError> {
    let file = std::fs::File::create(path)?;
    let w = std::io::BufWriter::new(file);

    let mut encoder = png::Encoder::new(w, width, height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);

    let mut writer = encoder
        .write_header()
        .map_err(|e| AnimError::Render(format!("PNG header error: {e}")))?;

    writer
        .write_image_data(data)
        .map_err(|e| AnimError::Render(format!("PNG write error: {e}")))?;

    Ok(())
}
